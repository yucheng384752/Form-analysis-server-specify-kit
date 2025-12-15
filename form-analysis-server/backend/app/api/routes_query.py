"""
資料查詢路由

提供查詢已匯入資料的API端點。
支援P1/P2/P3三種不同類型的資料查詢。
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, date

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.record import Record, DataType

# 獲取日誌記錄器
logger = get_logger(__name__)

# 建立路由器
router = APIRouter(
    tags=["資料查詢"]
)


class QueryRecord(BaseModel):
    """查詢記錄回應模型"""
    id: str
    lot_no: str
    data_type: str
    production_date: Optional[str]
    created_at: str
    display_name: str
    
    # P1專用欄位
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    notes: Optional[str] = None
    
    # P2專用欄位
    sheet_width: Optional[float] = None
    thickness1: Optional[float] = None
    thickness2: Optional[float] = None
    thickness3: Optional[float] = None
    thickness4: Optional[float] = None
    thickness5: Optional[float] = None
    thickness6: Optional[float] = None
    thickness7: Optional[float] = None
    appearance: Optional[int] = None
    rough_edge: Optional[int] = None
    slitting_result: Optional[int] = None
    
    # P3專用欄位
    p3_no: Optional[str] = None
    
    # 額外資料欄位 (來自CSV的其他欄位，包含溫度資料等)
    additional_data: Optional[Dict[str, Any]] = None


class LotGroupResponse(BaseModel):
    """批號分組查詢回應模型"""
    lot_no: str
    p1_count: int
    p2_count: int
    p3_count: int
    total_count: int
    latest_production_date: Optional[str]
    created_at: str


class LotGroupListResponse(BaseModel):
    """批號分組列表回應模型"""
    total_count: int
    page: int
    page_size: int
    groups: List[LotGroupResponse]


class QueryResponse(BaseModel):
    """查詢回應模型"""
    total_count: int
    page: int
    page_size: int
    records: List[QueryRecord]


class RecordStats(BaseModel):
    """記錄統計模型"""
    total_records: int
    unique_lots: int
    p1_records: int
    p2_records: int
    p3_records: int
    latest_production_date: Optional[str]
    earliest_production_date: Optional[str]


@router.get(
    "/lots",
    response_model=LotGroupListResponse,
    summary="查詢批號分組",
    description="""
    查詢批號並按P1/P2/P3分組統計
    
    **查詢參數：**
    - search: 搜尋關鍵字，可搜尋 lot_no
    - page: 頁碼（從1開始）
    - page_size: 每頁記錄數量
    
    **回傳內容：**
    - total_count: 總批號數
    - page: 當前頁碼 
    - page_size: 每頁大小
    - groups: 批號分組列表
    """
)
async def query_lot_groups(
    search: Optional[str] = Query(None, description="搜尋批號關鍵字"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db)
) -> LotGroupListResponse:
    """查詢批號分組"""
    try:
        logger.info("開始查詢批號分組", search=search, page=page, page_size=page_size)
        
        # 簡化查詢：先獲取所有lot_no，然後分別統計
        lot_query = (
            select(
                Record.lot_no,
                func.count().label('total_count'),
                func.max(Record.production_date).label('latest_production_date'),
                func.max(Record.created_at).label('latest_created_at')
            )
            .group_by(Record.lot_no)
        )
        
        # 添加搜尋條件到基礎查詢
        if search and search.strip():
            search_filter = f"%{search.strip()}%"
            lot_query = lot_query.where(Record.lot_no.ilike(search_filter))
        
        # 計算總批號數
        count_subquery = lot_query.subquery()
        count_query = select(func.count()).select_from(count_subquery)
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # 分頁查詢基礎資料
        offset = (page - 1) * page_size
        final_query = lot_query.order_by(func.max(Record.created_at).desc()).offset(offset).limit(page_size)
        
        result = await db.execute(final_query)
        lot_rows = result.fetchall()
        
        # 為每個lot_no分別查詢P1/P2/P3數量
        groups = []
        for row in lot_rows:
            lot_no = row.lot_no
            
            # 查詢各資料類型的數量
            p1_count_query = select(func.count()).where(
                and_(Record.lot_no == lot_no, Record.data_type == DataType.P1)
            )
            p2_count_query = select(func.count()).where(
                and_(Record.lot_no == lot_no, Record.data_type == DataType.P2)
            )
            p3_count_query = select(func.count()).where(
                and_(Record.lot_no == lot_no, Record.data_type == DataType.P3)
            )
            
            p1_result = await db.execute(p1_count_query)
            p2_result = await db.execute(p2_count_query)
            p3_result = await db.execute(p3_count_query)
            
            p1_count = p1_result.scalar() or 0
            p2_count = p2_result.scalar() or 0
            p3_count = p3_result.scalar() or 0
            
            groups.append(LotGroupResponse(
                lot_no=row.lot_no,
                p1_count=p1_count,
                p2_count=p2_count,
                p3_count=p3_count,
                total_count=row.total_count,
                latest_production_date=row.latest_production_date.isoformat() if row.latest_production_date else None,
                created_at=row.latest_created_at.isoformat()
            ))
        
        logger.info("批號分組查詢完成", search=search, total_count=total_count, returned_count=len(groups))
        
        return LotGroupListResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            groups=groups
        )

        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"查詢批號分組時發生錯誤：{str(e)}"
        )


@router.get(
    "/records/advanced",
    response_model=QueryResponse,
    summary="高級搜尋資料記錄",
    description="""
    使用多個條件進行高級搜尋
    
    **查詢參數（所有參數均為選填，支援模糊搜尋）：**
    - lot_no: 批號（模糊搜尋）
    - production_date_from: 生產日期起始（YYYY-MM-DD）
    - production_date_to: 生產日期結束（YYYY-MM-DD）
    - machine_no: 機台號碼（模糊搜尋，如: P24, P21）
    - mold_no: 下膠編號/模具編號（模糊搜尋，如: 238-2）
    - product_name: P3規格/產品名稱（模糊搜尋）
    - data_type: 資料類型 (P1/P2/P3)
    - page: 頁碼（從1開始）
    - page_size: 每頁記錄數量
    
    **回傳內容：**
    - total_count: 總記錄數
    - page: 當前頁碼
    - page_size: 每頁大小
    - records: 記錄列表
    """
)
async def advanced_search_records(
    lot_no: Optional[str] = Query(None, description="批號（模糊搜尋）"),
    production_date_from: Optional[date] = Query(None, description="生產日期起始（YYYY-MM-DD）"),
    production_date_to: Optional[date] = Query(None, description="生產日期結束（YYYY-MM-DD）"),
    machine_no: Optional[str] = Query(None, description="機台號碼（模糊搜尋）"),
    mold_no: Optional[str] = Query(None, description="下膠編號/模具編號（模糊搜尋）"),
    product_name: Optional[str] = Query(None, description="P3規格/產品名稱（模糊搜尋）"),
    data_type: Optional[DataType] = Query(None, description="資料類型 (P1/P2/P3)"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """高級搜尋資料記錄 - 支援多條件模糊搜尋"""
    try:
        logger.info("開始高級搜尋", 
                   lot_no=lot_no,
                   production_date_from=production_date_from,
                   production_date_to=production_date_to,
                   machine_no=machine_no,
                   mold_no=mold_no,
                   product_name=product_name,
                   data_type=data_type,
                   page=page,
                   page_size=page_size)
        
        # 建構查詢條件列表
        conditions = []
        
        # 批號模糊搜尋
        if lot_no and lot_no.strip():
            conditions.append(Record.lot_no.ilike(f"%{lot_no.strip()}%"))
        
        # 生產日期範圍搜尋
        if production_date_from:
            conditions.append(Record.production_date >= production_date_from)
        if production_date_to:
            conditions.append(Record.production_date <= production_date_to)
        
        # 機台號碼模糊搜尋（P3專用）
        if machine_no and machine_no.strip():
            conditions.append(Record.machine_no.ilike(f"%{machine_no.strip()}%"))
        
        # 模具編號模糊搜尋（P3專用）
        if mold_no and mold_no.strip():
            conditions.append(Record.mold_no.ilike(f"%{mold_no.strip()}%"))
        
        # 產品名稱模糊搜尋（P3規格）
        if product_name and product_name.strip():
            conditions.append(Record.product_name.ilike(f"%{product_name.strip()}%"))
        
        # 資料類型過濾
        if data_type:
            conditions.append(Record.data_type == data_type)
        
        # 如果沒有任何條件，返回空結果
        if not conditions:
            logger.warning("高級搜尋沒有提供任何搜尋條件")
            return QueryResponse(
                total_count=0,
                page=page,
                page_size=page_size,
                records=[]
            )
        
        # 組合查詢
        query_stmt = select(Record).where(and_(*conditions))
        
        # 計算總數
        count_query = select(func.count(Record.id)).where(and_(*conditions))
        result = await db.execute(count_query)
        total_count = result.scalar() or 0
        
        # 分頁查詢
        offset = (page - 1) * page_size
        query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)
        
        result = await db.execute(query_stmt)
        records = result.scalars().all()
        
        # 轉換為回應格式
        query_records = []
        for record in records:
            query_record = QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                data_type=record.data_type.value,
                production_date=record.production_date.isoformat() if record.production_date else None,
                created_at=record.created_at.isoformat(),
                display_name=record.display_name,
                additional_data=record.additional_data
            )
            
            # 根據資料類型設置對應欄位
            if record.data_type == DataType.P1:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            elif record.data_type == DataType.P2:
                query_record.sheet_width = record.sheet_width
                query_record.thickness1 = record.thickness1
                query_record.thickness2 = record.thickness2
                query_record.thickness3 = record.thickness3
                query_record.thickness4 = record.thickness4
                query_record.thickness5 = record.thickness5
                query_record.thickness6 = record.thickness6
                query_record.thickness7 = record.thickness7
                query_record.appearance = record.appearance
                query_record.rough_edge = record.rough_edge
                query_record.slitting_result = record.slitting_result
            elif record.data_type == DataType.P3:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            
            query_records.append(query_record)
        
        logger.info("高級搜尋完成", 
                   total_count=total_count,
                   returned_count=len(query_records),
                   conditions_count=len(conditions))
        
        return QueryResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            records=query_records
        )
        
    except Exception as e:
        logger.error("高級搜尋失敗", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"高級搜尋時發生錯誤：{str(e)}"
        )


@router.get(
    "/records",
    response_model=QueryResponse,
    summary="查詢資料記錄",
    description="""
    查詢指定批號和資料類型的記錄
    
    **查詢參數：**
    - lot_no: 批號（必填）
    - data_type: 資料類型 (P1/P2/P3，選填)
    - page: 頁碼（從1開始）
    - page_size: 每頁記錄數量
    
    **回傳內容：**
    - total_count: 總記錄數
    - page: 當前頁碼
    - page_size: 每頁大小
    - records: 記錄列表
    """
)
async def query_records(
    lot_no: str = Query(..., description="批號"),
    data_type: Optional[DataType] = Query(None, description="資料類型 (P1/P2/P3)"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """查詢指定批號的資料記錄"""
    try:
        logger.info("開始查詢資料記錄", lot_no=lot_no, data_type=data_type, page=page, page_size=page_size)
        
        # 建構查詢條件
        conditions = [Record.lot_no == lot_no]
        if data_type:
            conditions.append(Record.data_type == data_type)
        
        query_stmt = select(Record).where(and_(*conditions))
        
        # 計算總數
        count_query = select(func.count(Record.id)).where(and_(*conditions))
        result = await db.execute(count_query)
        total_count = result.scalar() or 0
        
        # 分頁查詢
        offset = (page - 1) * page_size
        query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)
        
        result = await db.execute(query_stmt)
        records = result.scalars().all()
        
        # 轉換為回應格式
        query_records = []
        for record in records:
            query_record = QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                data_type=record.data_type.value,
                production_date=record.production_date.isoformat() if record.production_date else None,
                created_at=record.created_at.isoformat(),
                display_name=record.display_name,
                additional_data=record.additional_data  # 包含所有額外欄位
            )
            
            # 根據資料類型設置對應欄位
            if record.data_type == DataType.P1:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            elif record.data_type == DataType.P2:
                query_record.sheet_width = record.sheet_width
                query_record.thickness1 = record.thickness1
                query_record.thickness2 = record.thickness2
                query_record.thickness3 = record.thickness3
                query_record.thickness4 = record.thickness4
                query_record.thickness5 = record.thickness5
                query_record.thickness6 = record.thickness6
                query_record.thickness7 = record.thickness7
                query_record.appearance = record.appearance
                query_record.rough_edge = record.rough_edge
                query_record.slitting_result = record.slitting_result
            elif record.data_type == DataType.P3:
                query_record.p3_no = record.p3_no
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            
            query_records.append(query_record)
        
        logger.info("查詢完成", lot_no=lot_no, data_type=data_type, total_count=total_count, returned_count=len(query_records))
        
        return QueryResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            records=query_records
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"查詢資料時發生錯誤：{str(e)}"
        )


@router.get(
    "/lots/suggestions",
    response_model=List[str],
    summary="取得批號搜尋建議",
    description="根據輸入關鍵字提供lot_no的自動完成建議"
)
async def get_lot_suggestions(
    query: str = Query(..., min_length=1, description="搜尋關鍵字"),
    limit: int = Query(10, ge=1, le=50, description="建議數量限制"),
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """
    取得批號搜尋建議
    
    Args:
        query: 搜尋關鍵字
        limit: 建議數量限制
        db: 資料庫會話
    
    Returns:
        List[str]: lot_no建議列表
    """
    try:
        # 查詢符合條件的lot_no，按字母順序排序並去重
        query_filter = f"%{query.strip()}%"
        sql_query = (
            select(Record.lot_no)
            .where(Record.lot_no.ilike(query_filter))
            .distinct()
            .order_by(Record.lot_no)
            .limit(limit)
        )
        
        result = await db.execute(sql_query)
        suggestions = [row[0] for row in result.fetchall()]
        
        return suggestions
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"取得建議時發生錯誤：{str(e)}"
        )


@router.get(
    "/records/{record_id}",
    response_model=QueryRecord,
    summary="取得單筆記錄",
    description="根據記錄ID取得詳細資訊"
)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> QueryRecord:
    """
    取得單筆記錄
    
    Args:
        record_id: 記錄ID
        db: 資料庫會話
    
    Returns:
        QueryRecord: 記錄詳情
    """
    try:
        query = select(Record).where(Record.id == record_id)
        result = await db.execute(query)
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail="找不到指定的記錄"
            )
        
        query_record = QueryRecord(
            id=str(record.id),
            lot_no=record.lot_no,
            data_type=record.data_type.value,
            production_date=record.production_date.isoformat() if record.production_date else None,
            created_at=record.created_at.isoformat(),
            display_name=record.display_name
        )
        
        # 根據資料類型設置對應欄位
        if record.data_type == DataType.P1:
            query_record.product_name = record.product_name
            query_record.quantity = record.quantity
            query_record.notes = record.notes
        elif record.data_type == DataType.P2:
            query_record.sheet_width = record.sheet_width
            query_record.thickness1 = record.thickness1
            query_record.thickness2 = record.thickness2
            query_record.thickness3 = record.thickness3
            query_record.thickness4 = record.thickness4
            query_record.thickness5 = record.thickness5
            query_record.thickness6 = record.thickness6
            query_record.thickness7 = record.thickness7
            query_record.appearance = record.appearance
            query_record.rough_edge = record.rough_edge
            query_record.slitting_result = record.slitting_result
        elif record.data_type == DataType.P3:
            query_record.p3_no = record.p3_no
            query_record.product_name = record.product_name
            query_record.quantity = record.quantity
            query_record.notes = record.notes
        
        return query_record
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"取得記錄時發生錯誤：{str(e)}"
        )


@router.get(
    "/records/stats",
    response_model=RecordStats,
    summary="取得記錄統計資訊",
    description="取得資料庫中記錄的統計資訊，包含總數、P1/P2/P3分類統計等"
)
async def get_record_stats(
    db: AsyncSession = Depends(get_db)
) -> RecordStats:
    """
    取得記錄統計資訊
    
    Args:
        db: 資料庫會話
    
    Returns:
        RecordStats: 統計資訊
    """
    try:
        # 總記錄數
        total_query = select(func.count(Record.id))
        total_result = await db.execute(total_query)
        total_records = total_result.scalar() or 0
        
        if total_records == 0:
            return RecordStats(
                total_records=0,
                unique_lots=0,
                p1_records=0,
                p2_records=0,
                p3_records=0,
                latest_production_date=None,
                earliest_production_date=None
            )
        
        # 唯一批號數
        unique_lots_query = select(func.count(func.distinct(Record.lot_no)))
        unique_lots_result = await db.execute(unique_lots_query)
        unique_lots = unique_lots_result.scalar() or 0
        
        # P1/P2/P3分類統計
        type_stats_query = select(
            Record.data_type,
            func.count()
        ).group_by(Record.data_type)
        type_stats_result = await db.execute(type_stats_query)
        type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}
        
        p1_records = type_stats.get(DataType.P1, 0)
        p2_records = type_stats.get(DataType.P2, 0)
        p3_records = type_stats.get(DataType.P3, 0)
        
        # 最新和最早生產日期
        date_query = select(func.max(Record.production_date), func.min(Record.production_date))
        date_result = await db.execute(date_query)
        date_row = date_result.first()
        
        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None
        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None
        
        return RecordStats(
            total_records=total_records,
            unique_lots=unique_lots,
            p1_records=p1_records,
            p2_records=p2_records,
            p3_records=p3_records,
            latest_production_date=latest_date,
            earliest_production_date=earliest_date
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"取得統計資訊時發生錯誤：{str(e)}"
        )


@router.post(
    "/records/create-test-data",
    summary="創建測試資料",
    description="為演示目的創建一些測試記錄（僅開發環境使用）"
)
async def create_test_data(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    創建測試資料
    
    Args:
        db: 資料庫會話
    
    Returns:
        dict: 創建結果
    """
    try:
        test_records = [
            # P1 測試資料
            Record(
                lot_no="2503033_01",
                data_type=DataType.P1,
                product_name="產品A",
                quantity=100,
                production_date=date(2024, 1, 15),
                notes="測試產品"
            ),
            Record(
                lot_no="2503033_01",
                data_type=DataType.P1,
                product_name="產品B",
                quantity=200,
                production_date=date(2024, 1, 16),
                notes="另一個測試產品"
            ),
            # P2 測試資料
            Record(
                lot_no="2503033_01",
                data_type=DataType.P2,
                sheet_width=7.985,
                thickness1=319.0,
                thickness2=325.0,
                thickness3=320.0,
                thickness4=319.0,
                thickness5=319.0,
                thickness6=326.0,
                thickness7=324.0,
                appearance=0,
                rough_edge=1,
                slitting_result=1,
                production_date=date(2024, 1, 15)
            ),
            # P3 測試資料
            Record(
                lot_no="2503033_01",
                data_type=DataType.P3,
                p3_no="2503033012345",
                product_name="產品A",
                quantity=100,
                production_date=date(2024, 1, 15),
                notes="測試產品"
            )
        ]
        
        for record in test_records:
            db.add(record)
        
        await db.commit()
        
        return {
            "message": "測試資料創建成功",
            "created_records": len(test_records)
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"創建測試資料時發生錯誤：{str(e)}"
        )