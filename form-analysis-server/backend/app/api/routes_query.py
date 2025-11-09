"""
資料查詢路由

提供查詢已匯入資料的API端點。
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, date

from app.core.database import get_db
from app.models.record import Record


# 建立路由器
router = APIRouter(
    prefix="/api",
    tags=["資料查詢"]
)


class QueryRecord(BaseModel):
    """查詢記錄回應模型"""
    id: str
    lot_no: str
    product_name: str
    quantity: int
    production_date: str
    created_at: str


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
    unique_products: int
    total_quantity: int
    latest_production_date: Optional[str]
    earliest_production_date: Optional[str]


@router.get(
    "/records",
    response_model=QueryResponse,
    summary="查詢資料記錄",
    description="""
    查詢已匯入的資料記錄
    
    **查詢參數：**
    - keyword: 搜尋關鍵字，可搜尋 lot_no 或 product_name
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
    search: Optional[str] = Query(None, description="搜尋關鍵字", alias="search"),
    keyword: Optional[str] = Query(None, description="搜尋關鍵字（向後相容）", alias="keyword"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """
    查詢資料記錄
    
    Args:
        search: 搜尋關鍵字（主要參數）
        keyword: 搜尋關鍵字（向後相容）
        page: 頁碼
        page_size: 每頁記錄數
        db: 資料庫會話
        
    Returns:
        QueryResponse: 查詢結果
    """
    try:
        # 使用search參數，如果沒有則使用keyword（向後相容）
        search_term = search or keyword
        
        # 建構查詢條件
        query_stmt = select(Record)
        
        if search_term and search_term.strip():
            keyword_filter = f"%{search_term.strip()}%"
            query_stmt = query_stmt.where(
                or_(
                    Record.lot_no.ilike(keyword_filter),
                    Record.product_name.ilike(keyword_filter)
                )
            )
        
        # 計算總數
        count_query = select(func.count(Record.id))
        if search_term and search_term.strip():
            keyword_filter = f"%{search_term.strip()}%"
            count_query = count_query.where(
                or_(
                    Record.lot_no.ilike(keyword_filter),
                    Record.product_name.ilike(keyword_filter)
                )
            )
        
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
            query_records.append(QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                product_name=record.product_name,
                quantity=record.quantity,
                production_date=record.production_date.isoformat(),
                created_at=record.created_at.isoformat()
            ))
        
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
    "/records/stats",
    response_model=RecordStats,
    summary="取得記錄統計資訊",
    description="取得資料庫中記錄的統計資訊，包含總數、種類等"
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
                unique_products=0,
                total_quantity=0,
                latest_production_date=None,
                earliest_production_date=None
            )
        
        # 唯一批號數
        unique_lots_query = select(func.count(func.distinct(Record.lot_no)))
        unique_lots_result = await db.execute(unique_lots_query)
        unique_lots = unique_lots_result.scalar() or 0
        
        # 唯一產品數
        unique_products_query = select(func.count(func.distinct(Record.product_name)))
        unique_products_result = await db.execute(unique_products_query)
        unique_products = unique_products_result.scalar() or 0
        
        # 總數量
        total_quantity_query = select(func.sum(Record.quantity))
        total_quantity_result = await db.execute(total_quantity_query)
        total_quantity = total_quantity_result.scalar() or 0
        
        # 最新和最早生產日期
        date_query = select(func.max(Record.production_date), func.min(Record.production_date))
        date_result = await db.execute(date_query)
        date_row = date_result.first()
        
        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None
        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None
        
        return RecordStats(
            total_records=total_records,
            unique_lots=unique_lots,
            unique_products=unique_products,
            total_quantity=total_quantity,
            latest_production_date=latest_date,
            earliest_production_date=earliest_date
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"取得統計資訊時發生錯誤：{str(e)}"
        )


@router.get(
    "/records/suggestions",
    response_model=List[str],
    summary="取得搜尋建議",
    description="根據輸入關鍵字提供lot_no的自動完成建議"
)
async def get_suggestions(
    query: str = Query(..., min_length=1, description="搜尋關鍵字"),
    limit: int = Query(10, ge=1, le=50, description="建議數量限制"),
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """
    取得搜尋建議
    
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
        
        return QueryRecord(
            id=str(record.id),
            lot_no=record.lot_no,
            product_name=record.product_name,
            quantity=record.quantity,
            production_date=record.production_date.isoformat(),
            created_at=record.created_at.isoformat()
        )
        
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
    description="取得資料庫中記錄的統計資訊，包含總數、種類等"
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
                unique_products=0,
                total_quantity=0,
                latest_production_date=None,
                earliest_production_date=None
            )
        
        # 唯一批號數
        unique_lots_query = select(func.count(func.distinct(Record.lot_no)))
        unique_lots_result = await db.execute(unique_lots_query)
        unique_lots = unique_lots_result.scalar() or 0
        
        # 唯一產品數
        unique_products_query = select(func.count(func.distinct(Record.product_name)))
        unique_products_result = await db.execute(unique_products_query)
        unique_products = unique_products_result.scalar() or 0
        
        # 總數量
        total_quantity_query = select(func.sum(Record.quantity))
        total_quantity_result = await db.execute(total_quantity_query)
        total_quantity = total_quantity_result.scalar() or 0
        
        # 最新和最早生產日期
        date_query = select(func.max(Record.production_date), func.min(Record.production_date))
        date_result = await db.execute(date_query)
        date_row = date_result.first()
        
        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None
        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None
        
        return RecordStats(
            total_records=total_records,
            unique_lots=unique_lots,
            unique_products=unique_products,
            total_quantity=total_quantity,
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
    summary="創建測試數據",
    description="為演示目的創建一些測試記錄（僅開發環境使用）"
)
async def create_test_data(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    創建測試數據
    
    Args:
        db: 資料庫會話
        
    Returns:
        dict: 創建結果
    """
    try:
        test_records = [
            Record(
                lot_no="1234567_01",
                product_name="測試產品A",
                quantity=100,
                production_date=date(2024, 1, 15)
            ),
            Record(
                lot_no="1234567_02", 
                product_name="測試產品B",
                quantity=200,
                production_date=date(2024, 1, 16)
            ),
            Record(
                lot_no="1234568_01",
                product_name="測試產品C",
                quantity=150,
                production_date=date(2024, 1, 17)
            ),
            Record(
                lot_no="2345678_01",
                product_name="高級產品A",
                quantity=80,
                production_date=date(2024, 2, 1)
            ),
            Record(
                lot_no="2345678_02",
                product_name="高級產品B", 
                quantity=120,
                production_date=date(2024, 2, 2)
            )
        ]
        
        for record in test_records:
            db.add(record)
        
        await db.commit()
        
        return {
            "message": "測試數據創建成功",
            "created_records": len(test_records)
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"創建測試數據時發生錯誤：{str(e)}"
        )