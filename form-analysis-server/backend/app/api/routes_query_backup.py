""""""

資料查詢路由資料查詢路由



提供查詢已匯入資料的API端點。提供查詢已匯入資料的API端點。

支援P1/P2/P3三種不同類型的資料查詢。支援P1/P2/P3三種不同類型的資料查詢。

""""""



from typing import List, Optional, Dict, Anyfrom typing import List, Optional, Dict, Any

from uuid import UUIDfrom uuid import UUID



from fastapi import APIRouter, Depends, HTTPException, Queryfrom fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy import select, func, or_, and_from sqlalchemy import select, func, or_, and_

from sqlalchemy.ext.asyncio import AsyncSessionfrom sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModelfrom pydantic import BaseModel

from datetime import datetime, datefrom datetime import datetime, date



from app.core.database import get_dbfrom app.core.database import get_db

from app.core.logging import get_loggerfrom app.core.logging import get_logger

from app.models.record import Record, DataTypefrom app.models.record import Record, DataType



# 獲取日誌記錄器# 獲取日誌記錄器

logger = get_logger(__name__)logger = get_logger(__name__)





# 建立路由器# 建立路由器

router = APIRouter(router = APIRouter(

    tags=["資料查詢"]    tags=["資料查詢"]

))





class QueryRecord(BaseModel):class QueryRecord(BaseModel):

    """查詢記錄回應模型"""    """查詢記錄回應模型"""

    id: str    id: str

    lot_no: str    lot_no: str

    data_type: str    data_type: str

    production_date: Optional[str]    production_date: Optional[str]

    created_at: str    created_at: str

    display_name: str    display_name: str

        

    # P1專用欄位    # P1專用欄位

    product_name: Optional[str] = None    product_name: Optional[str] = None

    quantity: Optional[int] = None    quantity: Optional[int] = None

    notes: Optional[str] = None    notes: Optional[str] = None

        

    # P2專用欄位    # P2專用欄位

    sheet_width: Optional[float] = None    sheet_width: Optional[float] = None

    thickness1: Optional[float] = None    thickness1: Optional[float] = None

    thickness2: Optional[float] = None    thickness2: Optional[float] = None

    thickness3: Optional[float] = None    thickness3: Optional[float] = None

    thickness4: Optional[float] = None    thickness4: Optional[float] = None

    thickness5: Optional[float] = None    thickness5: Optional[float] = None

    thickness6: Optional[float] = None    thickness6: Optional[float] = None

    thickness7: Optional[float] = None    thickness7: Optional[float] = None

    appearance: Optional[int] = None    appearance: Optional[int] = None

    rough_edge: Optional[int] = None    rough_edge: Optional[int] = None

    slitting_result: Optional[int] = None    slitting_result: Optional[int] = None

        

    # P3專用欄位    # P3專用欄位

    p3_no: Optional[str] = None    p3_no: Optional[str] = None





class LotGroupResponse(BaseModel):class LotGroupResponse(BaseModel):

    """批號分組查詢回應模型"""    """批號分組查詢回應模型"""

    lot_no: str    lot_no: str

    p1_count: int    p1_count: int

    p2_count: int    p2_count: int

    p3_count: int    p3_count: int

    total_count: int    total_count: int

    latest_production_date: Optional[str]    latest_production_date: Optional[str]

    created_at: str    created_at: str





class LotGroupListResponse(BaseModel):class LotGroupListResponse(BaseModel):

    """批號分組列表回應模型"""    """批號分組列表回應模型"""

    total_count: int    total_count: int

    page: int    page: int

    page_size: int    page_size: int

    groups: List[LotGroupResponse]    groups: List[LotGroupResponse]





class QueryResponse(BaseModel):class QueryResponse(BaseModel):

    """查詢回應模型"""    """查詢回應模型"""

    total_count: int    total_count: int

    page: int    page: int

    page_size: int    page_size: int

    records: List[QueryRecord]    records: List[QueryRecord]





class RecordStats(BaseModel):class RecordStats(BaseModel):

    """記錄統計模型"""    """記錄統計模型"""

    total_records: int    total_records: int

    unique_lots: int    unique_lots: int

    p1_records: int    p1_records: int

    p2_records: int    p2_records: int

    p3_records: int    p3_records: int

    latest_production_date: Optional[str]    latest_production_date: Optional[str]

    earliest_production_date: Optional[str]    earliest_production_date: Optional[str]





@router.get(@router.get(

    "/lots",    "/lots",

    response_model=LotGroupListResponse,    response_model=LotGroupListResponse,

    summary="查詢批號分組",    summary="查詢批號分組",

    description="""    description="""

    查詢批號並按P1/P2/P3分組統計    查詢批號並按P1/P2/P3分組統計

        

    **查詢參數：**    **查詢參數：**

    - search: 搜尋關鍵字，可搜尋 lot_no    - search: 搜尋關鍵字，可搜尋 lot_no

    - page: 頁碼（從1開始）    - page: 頁碼（從1開始）

    - page_size: 每頁記錄數量    - page_size: 每頁記錄數量

        

    **回傳內容：**    **回傳內容：**

    - total_count: 總批號數    - total_count: 總批號數

    - page: 當前頁碼     - page: 當前頁碼 

    - page_size: 每頁大小    - page_size: 每頁大小

    - groups: 批號分組列表    - groups: 批號分組列表

    """    """

))

async def query_lot_groups(async def query_lot_groups(

    search: Optional[str] = Query(None, description="搜尋批號關鍵字"),    search: Optional[str] = Query(None, description="搜尋批號關鍵字"),

    page: int = Query(1, ge=1, description="頁碼"),    page: int = Query(1, ge=1, description="頁碼"),

    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),

    db: AsyncSession = Depends(get_db)    db: AsyncSession = Depends(get_db)

) -> LotGroupListResponse:) -> LotGroupListResponse:

    """查詢批號分組"""    """查詢批號分組"""

    try:    try:

        logger.info("開始查詢批號分組", search=search, page=page, page_size=page_size)        logger.info("開始查詢批號分組", search=search, page=page, page_size=page_size)

                

        # 基礎查詢：按lot_no分組統計P1/P2/P3數量        # 基礎查詢：按lot_no分組統計P1/P2/P3數量

        base_query = (        base_query = (

            select(            select(

                Record.lot_no,                Record.lot_no,

                func.sum(func.case((Record.data_type == DataType.P1, 1), else_=0)).label('p1_count'),                func.sum(func.case((Record.data_type == DataType.P1, 1), else_=0)).label('p1_count'),

                func.sum(func.case((Record.data_type == DataType.P2, 1), else_=0)).label('p2_count'),                func.sum(func.case((Record.data_type == DataType.P2, 1), else_=0)).label('p2_count'),

                func.sum(func.case((Record.data_type == DataType.P3, 1), else_=0)).label('p3_count'),                func.sum(func.case((Record.data_type == DataType.P3, 1), else_=0)).label('p3_count'),

                func.count().label('total_count'),                func.count().label('total_count'),

                func.max(Record.production_date).label('latest_production_date'),                func.max(Record.production_date).label('latest_production_date'),

                func.max(Record.created_at).label('latest_created_at')                func.max(Record.created_at).label('latest_created_at')

            )            )

            .group_by(Record.lot_no)            .group_by(Record.lot_no)

        )        )

                

        # 添加搜尋條件        # 添加搜尋條件

        if search and search.strip():        if search and search.strip():

            search_filter = f"%{search.strip()}%"            search_filter = f"%{search.strip()}%"

            base_query = base_query.where(Record.lot_no.ilike(search_filter))            base_query = base_query.where(Record.lot_no.ilike(search_filter))

                

        # 計算總批號數        # 計算總批號數

        count_subquery = base_query.subquery()        count_subquery = base_query.subquery()

        count_query = select(func.count()).select_from(count_subquery)        count_query = select(func.count()).select_from(count_subquery)

        count_result = await db.execute(count_query)        count_result = await db.execute(count_query)

        total_count = count_result.scalar() or 0        total_count = count_result.scalar() or 0

                

        # 分頁查詢        # 分頁查詢

        offset = (page - 1) * page_size        offset = (page - 1) * page_size

        final_query = base_query.order_by(func.max(Record.created_at).desc()).offset(offset).limit(page_size)        final_query = base_query.order_by(func.max(Record.created_at).desc()).offset(offset).limit(page_size)

                

        result = await db.execute(final_query)        result = await db.execute(final_query)

        rows = result.fetchall()        rows = result.fetchall()

                

        # 轉換為回應格式        # 轉換為回應格式

        groups = []        groups = []

        for row in rows:        for row in rows:

            groups.append(LotGroupResponse(            groups.append(LotGroupResponse(

                lot_no=row.lot_no,                lot_no=row.lot_no,

                p1_count=row.p1_count,                p1_count=row.p1_count,

                p2_count=row.p2_count,                p2_count=row.p2_count,

                p3_count=row.p3_count,                p3_count=row.p3_count,

                total_count=row.total_count,                total_count=row.total_count,

                latest_production_date=row.latest_production_date.isoformat() if row.latest_production_date else None,                latest_production_date=row.latest_production_date.isoformat() if row.latest_production_date else None,

                created_at=row.latest_created_at.isoformat()                created_at=row.latest_created_at.isoformat()

            ))            ))

                

        logger.info("批號分組查詢完成", search=search, total_count=total_count, returned_count=len(groups))        logger.info("批號分組查詢完成", search=search, total_count=total_count, returned_count=len(groups))

                

        return LotGroupListResponse(        return LotGroupListResponse(

            total_count=total_count,            total_count=total_count,

            page=page,            page=page,

            page_size=page_size,            page_size=page_size,

            groups=groups            groups=groups

        )        )

                

    except Exception as e:    except Exception as e:

        raise HTTPException(        raise HTTPException(

            status_code=500,            status_code=500,

            detail=f"查詢批號分組時發生錯誤：{str(e)}"            detail=f"查詢批號分組時發生錯誤：{str(e)}"

        )        )





@router.get(@router.get(

    "/records",    "/records",

    response_model=QueryResponse,    response_model=QueryResponse,

    summary="查詢資料記錄",    summary="查詢資料記錄",

    description="""    description="""

    查詢指定批號和資料類型的記錄    查詢指定批號和資料類型的記錄

        

    **查詢參數：**    **查詢參數：**

    - lot_no: 批號（必填）    - lot_no: 批號（必填）

    - data_type: 資料類型 (P1/P2/P3，選填)    - data_type: 資料類型 (P1/P2/P3，選填)

    - page: 頁碼（從1開始）    - page: 頁碼（從1開始）

    - page_size: 每頁記錄數量    - page_size: 每頁記錄數量

        

    **回傳內容：**    **回傳內容：**

    - total_count: 總記錄數    - total_count: 總記錄數

    - page: 當前頁碼    - page: 當前頁碼

    - page_size: 每頁大小    - page_size: 每頁大小

    - records: 記錄列表    - records: 記錄列表

    """    """

))

async def query_records(async def query_records(

    lot_no: str = Query(..., description="批號"),    lot_no: str = Query(..., description="批號"),

    data_type: Optional[DataType] = Query(None, description="資料類型 (P1/P2/P3)"),    data_type: Optional[DataType] = Query(None, description="資料類型 (P1/P2/P3)"),

    page: int = Query(1, ge=1, description="頁碼"),    page: int = Query(1, ge=1, description="頁碼"),

    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),

    db: AsyncSession = Depends(get_db)    db: AsyncSession = Depends(get_db)

) -> QueryResponse:) -> QueryResponse:

    """查詢指定批號的資料記錄"""    """查詢指定批號的資料記錄"""

    try:    try:

        logger.info("開始查詢資料記錄", lot_no=lot_no, data_type=data_type, page=page, page_size=page_size)        logger.info("開始查詢資料記錄", lot_no=lot_no, data_type=data_type, page=page, page_size=page_size)

                

        # 建構查詢條件        # 建構查詢條件

        conditions = [Record.lot_no == lot_no]        conditions = [Record.lot_no == lot_no]

        if data_type:        if data_type:

            conditions.append(Record.data_type == data_type)            conditions.append(Record.data_type == data_type)

                

        query_stmt = select(Record).where(and_(*conditions))        query_stmt = select(Record).where(and_(*conditions))

                

        # 計算總數        # 計算總數

        count_query = select(func.count(Record.id)).where(and_(*conditions))        count_query = select(func.count(Record.id)).where(and_(*conditions))

        result = await db.execute(count_query)        result = await db.execute(count_query)

        total_count = result.scalar() or 0        total_count = result.scalar() or 0

                

        # 分頁查詢        # 分頁查詢

        offset = (page - 1) * page_size        offset = (page - 1) * page_size

        query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)        query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)

                

        result = await db.execute(query_stmt)        result = await db.execute(query_stmt)

        records = result.scalars().all()        records = result.scalars().all()

                

        # 轉換為回應格式        # 轉換為回應格式

        query_records = []        query_records = []

        for record in records:        for record in records:

            query_record = QueryRecord(            query_record = QueryRecord(

                id=str(record.id),                id=str(record.id),

                lot_no=record.lot_no,                lot_no=record.lot_no,

                data_type=record.data_type.value,                data_type=record.data_type.value,

                production_date=record.production_date.isoformat() if record.production_date else None,                production_date=record.production_date.isoformat() if record.production_date else None,

                created_at=record.created_at.isoformat(),                created_at=record.created_at.isoformat(),

                display_name=record.display_name                display_name=record.display_name

            )            )

                        

            # 根據資料類型設置對應欄位            # 根據資料類型設置對應欄位

            if record.data_type == DataType.P1:            if record.data_type == DataType.P1:

                query_record.product_name = record.product_name                query_record.product_name = record.product_name

                query_record.quantity = record.quantity                query_record.quantity = record.quantity

                query_record.notes = record.notes                query_record.notes = record.notes

            elif record.data_type == DataType.P2:            elif record.data_type == DataType.P2:

                query_record.sheet_width = record.sheet_width                query_record.sheet_width = record.sheet_width

                query_record.thickness1 = record.thickness1                query_record.thickness1 = record.thickness1

                query_record.thickness2 = record.thickness2                query_record.thickness2 = record.thickness2

                query_record.thickness3 = record.thickness3                query_record.thickness3 = record.thickness3

                query_record.thickness4 = record.thickness4                query_record.thickness4 = record.thickness4

                query_record.thickness5 = record.thickness5                query_record.thickness5 = record.thickness5

                query_record.thickness6 = record.thickness6                query_record.thickness6 = record.thickness6

                query_record.thickness7 = record.thickness7                query_record.thickness7 = record.thickness7

                query_record.appearance = record.appearance                query_record.appearance = record.appearance

                query_record.rough_edge = record.rough_edge                query_record.rough_edge = record.rough_edge

                query_record.slitting_result = record.slitting_result                query_record.slitting_result = record.slitting_result

            elif record.data_type == DataType.P3:            elif record.data_type == DataType.P3:

                query_record.p3_no = record.p3_no                query_record.p3_no = record.p3_no

                query_record.product_name = record.product_name                query_record.product_name = record.product_name

                query_record.quantity = record.quantity                query_record.quantity = record.quantity

                query_record.notes = record.notes                query_record.notes = record.notes

                        

            query_records.append(query_record)            query_records.append(query_record)

                

        logger.info("查詢完成", lot_no=lot_no, data_type=data_type, total_count=total_count, returned_count=len(query_records))        logger.info("查詢完成", lot_no=lot_no, data_type=data_type, total_count=total_count, returned_count=len(query_records))

                

        return QueryResponse(        return QueryResponse(

            total_count=total_count,            total_count=total_count,

            page=page,            page=page,

            page_size=page_size,            page_size=page_size,

            records=query_records            records=query_records

        )        )

                

    except Exception as e:    except Exception as e:

        raise HTTPException(        raise HTTPException(

            status_code=500,            status_code=500,

            detail=f"查詢資料時發生錯誤：{str(e)}"            detail=f"查詢資料時發生錯誤：{str(e)}"

        )        )





@router.get(@router.get(

    "/lots/suggestions",    "/records/stats",

    response_model=List[str],    response_model=RecordStats,

    summary="取得批號搜尋建議",    summary="取得記錄統計資訊",

    description="根據輸入關鍵字提供lot_no的自動完成建議"    description="取得資料庫中記錄的統計資訊，包含總數、種類等"

))

async def get_lot_suggestions(async def get_record_stats(

    query: str = Query(..., min_length=1, description="搜尋關鍵字"),    db: AsyncSession = Depends(get_db)

    limit: int = Query(10, ge=1, le=50, description="建議數量限制"),) -> RecordStats:

    db: AsyncSession = Depends(get_db)    """

) -> List[str]:    取得記錄統計資訊

    """    

    取得批號搜尋建議    Args:

            db: 資料庫會話

    Args:        

        query: 搜尋關鍵字    Returns:

        limit: 建議數量限制        RecordStats: 統計資訊

        db: 資料庫會話    """

            try:

    Returns:        # 總記錄數

        List[str]: lot_no建議列表        total_query = select(func.count(Record.id))

    """        total_result = await db.execute(total_query)

    try:        total_records = total_result.scalar() or 0

        # 查詢符合條件的lot_no，按字母順序排序並去重        

        query_filter = f"%{query.strip()}%"        if total_records == 0:

        sql_query = (            return RecordStats(

            select(Record.lot_no)                total_records=0,

            .where(Record.lot_no.ilike(query_filter))                unique_lots=0,

            .distinct()                unique_products=0,

            .order_by(Record.lot_no)                total_quantity=0,

            .limit(limit)                latest_production_date=None,

        )                earliest_production_date=None

                    )

        result = await db.execute(sql_query)        

        suggestions = [row[0] for row in result.fetchall()]        # 唯一批號數

                unique_lots_query = select(func.count(func.distinct(Record.lot_no)))

        return suggestions        unique_lots_result = await db.execute(unique_lots_query)

                unique_lots = unique_lots_result.scalar() or 0

    except Exception as e:        

        raise HTTPException(        # 唯一產品數

            status_code=500,        unique_products_query = select(func.count(func.distinct(Record.product_name)))

            detail=f"取得建議時發生錯誤：{str(e)}"        unique_products_result = await db.execute(unique_products_query)

        )        unique_products = unique_products_result.scalar() or 0

        

        # 總數量

@router.get(        total_quantity_query = select(func.sum(Record.quantity))

    "/records/{record_id}",        total_quantity_result = await db.execute(total_quantity_query)

    response_model=QueryRecord,        total_quantity = total_quantity_result.scalar() or 0

    summary="取得單筆記錄",        

    description="根據記錄ID取得詳細資訊"        # 最新和最早生產日期

)        date_query = select(func.max(Record.production_date), func.min(Record.production_date))

async def get_record(        date_result = await db.execute(date_query)

    record_id: UUID,        date_row = date_result.first()

    db: AsyncSession = Depends(get_db)        

) -> QueryRecord:        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None

    """        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None

    取得單筆記錄        

            return RecordStats(

    Args:            total_records=total_records,

        record_id: 記錄ID            unique_lots=unique_lots,

        db: 資料庫會話            unique_products=unique_products,

                    total_quantity=total_quantity,

    Returns:            latest_production_date=latest_date,

        QueryRecord: 記錄詳情            earliest_production_date=earliest_date

    """        )

    try:        

        query = select(Record).where(Record.id == record_id)    except Exception as e:

        result = await db.execute(query)        raise HTTPException(

        record = result.scalar_one_or_none()            status_code=500,

                    detail=f"取得統計資訊時發生錯誤：{str(e)}"

        if not record:        )

            raise HTTPException(

                status_code=404,

                detail="找不到指定的記錄"@router.get(

            )    "/lots/suggestions",

            response_model=List[str],

        query_record = QueryRecord(    summary="取得批號搜尋建議",

            id=str(record.id),    description="根據輸入關鍵字提供lot_no的自動完成建議"

            lot_no=record.lot_no,)

            data_type=record.data_type.value,async def get_lot_suggestions(

            production_date=record.production_date.isoformat() if record.production_date else None,    query: str = Query(..., min_length=1, description="搜尋關鍵字"),

            created_at=record.created_at.isoformat(),    limit: int = Query(10, ge=1, le=50, description="建議數量限制"),

            display_name=record.display_name    db: AsyncSession = Depends(get_db)

        )) -> List[str]:

            """

        # 根據資料類型設置對應欄位    取得批號搜尋建議

        if record.data_type == DataType.P1:    

            query_record.product_name = record.product_name    Args:

            query_record.quantity = record.quantity        query: 搜尋關鍵字

            query_record.notes = record.notes        limit: 建議數量限制

        elif record.data_type == DataType.P2:        db: 資料庫會話

            query_record.sheet_width = record.sheet_width        

            query_record.thickness1 = record.thickness1    Returns:

            query_record.thickness2 = record.thickness2        List[str]: lot_no建議列表

            query_record.thickness3 = record.thickness3    """

            query_record.thickness4 = record.thickness4    try:

            query_record.thickness5 = record.thickness5        # 查詢符合條件的lot_no，按字母順序排序並去重

            query_record.thickness6 = record.thickness6        query_filter = f"%{query.strip()}%"

            query_record.thickness7 = record.thickness7        sql_query = (

            query_record.appearance = record.appearance            select(Record.lot_no)

            query_record.rough_edge = record.rough_edge            .where(Record.lot_no.ilike(query_filter))

            query_record.slitting_result = record.slitting_result            .distinct()

        elif record.data_type == DataType.P3:            .order_by(Record.lot_no)

            query_record.p3_no = record.p3_no            .limit(limit)

            query_record.product_name = record.product_name        )

            query_record.quantity = record.quantity        

            query_record.notes = record.notes        result = await db.execute(sql_query)

                suggestions = [row[0] for row in result.fetchall()]

        return query_record        

                return suggestions

    except HTTPException:        

        raise    except Exception as e:

    except Exception as e:        raise HTTPException(

        raise HTTPException(            status_code=500,

            status_code=500,            detail=f"取得建議時發生錯誤：{str(e)}"

            detail=f"取得記錄時發生錯誤：{str(e)}"        )

        )



@router.get(

@router.get(    "/records/{record_id}",

    "/records/stats",    response_model=QueryRecord,

    response_model=RecordStats,    summary="取得單筆記錄",

    summary="取得記錄統計資訊",    description="根據記錄ID取得詳細資訊"

    description="取得資料庫中記錄的統計資訊，包含總數、P1/P2/P3分類統計等")

)async def get_record(

async def get_record_stats(    record_id: UUID,

    db: AsyncSession = Depends(get_db)    db: AsyncSession = Depends(get_db)

) -> RecordStats:) -> QueryRecord:

    """    """

    取得記錄統計資訊    取得單筆記錄

        

    Args:    Args:

        db: 資料庫會話        record_id: 記錄ID

                db: 資料庫會話

    Returns:        

        RecordStats: 統計資訊    Returns:

    """        QueryRecord: 記錄詳情

    try:    """

        # 總記錄數    try:

        total_query = select(func.count(Record.id))        query = select(Record).where(Record.id == record_id)

        total_result = await db.execute(total_query)        result = await db.execute(query)

        total_records = total_result.scalar() or 0        record = result.scalar_one_or_none()

                

        if total_records == 0:        if not record:

            return RecordStats(            raise HTTPException(

                total_records=0,                status_code=404,

                unique_lots=0,                detail="找不到指定的記錄"

                p1_records=0,            )

                p2_records=0,        

                p3_records=0,        query_record = QueryRecord(

                latest_production_date=None,            id=str(record.id),

                earliest_production_date=None            lot_no=record.lot_no,

            )            data_type=record.data_type.value,

                    production_date=record.production_date.isoformat() if record.production_date else None,

        # 唯一批號數            created_at=record.created_at.isoformat(),

        unique_lots_query = select(func.count(func.distinct(Record.lot_no)))            display_name=record.display_name

        unique_lots_result = await db.execute(unique_lots_query)        )

        unique_lots = unique_lots_result.scalar() or 0        

                # 根據資料類型設置對應欄位

        # P1/P2/P3分類統計        if record.data_type == DataType.P1:

        type_stats_query = select(            query_record.product_name = record.product_name

            Record.data_type,            query_record.quantity = record.quantity

            func.count()            query_record.notes = record.notes

        ).group_by(Record.data_type)        elif record.data_type == DataType.P2:

        type_stats_result = await db.execute(type_stats_query)            query_record.sheet_width = record.sheet_width

        type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}            query_record.thickness1 = record.thickness1

                    query_record.thickness2 = record.thickness2

        p1_records = type_stats.get(DataType.P1, 0)            query_record.thickness3 = record.thickness3

        p2_records = type_stats.get(DataType.P2, 0)            query_record.thickness4 = record.thickness4

        p3_records = type_stats.get(DataType.P3, 0)            query_record.thickness5 = record.thickness5

                    query_record.thickness6 = record.thickness6

        # 最新和最早生產日期            query_record.thickness7 = record.thickness7

        date_query = select(func.max(Record.production_date), func.min(Record.production_date))            query_record.appearance = record.appearance

        date_result = await db.execute(date_query)            query_record.rough_edge = record.rough_edge

        date_row = date_result.first()            query_record.slitting_result = record.slitting_result

                elif record.data_type == DataType.P3:

        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None            query_record.p3_no = record.p3_no

        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None            query_record.product_name = record.product_name

                    query_record.quantity = record.quantity

        return RecordStats(            query_record.notes = record.notes

            total_records=total_records,        

            unique_lots=unique_lots,        return query_record

            p1_records=p1_records,        

            p2_records=p2_records,    except HTTPException:

            p3_records=p3_records,        raise

            latest_production_date=latest_date,    except Exception as e:

            earliest_production_date=earliest_date        raise HTTPException(

        )            status_code=500,

                    detail=f"取得記錄時發生錯誤：{str(e)}"

    except Exception as e:        )

        raise HTTPException(

            status_code=500,

            detail=f"取得統計資訊時發生錯誤：{str(e)}"@router.get(

        )    "/records/stats",

    response_model=RecordStats,

    summary="取得記錄統計資訊",

@router.post(    description="取得資料庫中記錄的統計資訊，包含總數、種類等"

    "/records/create-test-data",)

    summary="創建測試資料",async def get_record_stats(

    description="為演示目的創建一些測試記錄（僅開發環境使用）"    db: AsyncSession = Depends(get_db)

)) -> RecordStats:

async def create_test_data(    """

    db: AsyncSession = Depends(get_db)    取得記錄統計資訊

) -> dict:    

    """    Args:

    創建測試資料        db: 資料庫會話

            

    Args:    Returns:

        db: 資料庫會話        RecordStats: 統計資訊

            """

    Returns:    try:

        dict: 創建結果        # 總記錄數

    """        total_query = select(func.count(Record.id))

    try:        total_result = await db.execute(total_query)

        test_records = [        total_records = total_result.scalar() or 0

            # P1 測試資料        

            Record(        if total_records == 0:

                lot_no="2503033_01",            return RecordStats(

                data_type=DataType.P1,                total_records=0,

                product_name="產品A",                unique_lots=0,

                quantity=100,                unique_products=0,

                production_date=date(2024, 1, 15),                total_quantity=0,

                notes="測試產品"                latest_production_date=None,

            ),                earliest_production_date=None

            Record(            )

                lot_no="2503033_01",        

                data_type=DataType.P1,        # 唯一批號數

                product_name="產品B",        unique_lots_query = select(func.count(func.distinct(Record.lot_no)))

                quantity=200,        unique_lots_result = await db.execute(unique_lots_query)

                production_date=date(2024, 1, 16),        unique_lots = unique_lots_result.scalar() or 0

                notes="另一個測試產品"        

            ),        # 唯一產品數

            # P2 測試資料        unique_products_query = select(func.count(func.distinct(Record.product_name)))

            Record(        unique_products_result = await db.execute(unique_products_query)

                lot_no="2503033_01",        unique_products = unique_products_result.scalar() or 0

                data_type=DataType.P2,        

                sheet_width=7.985,        # 總數量

                thickness1=319.0,        total_quantity_query = select(func.sum(Record.quantity))

                thickness2=325.0,        total_quantity_result = await db.execute(total_quantity_query)

                thickness3=320.0,        total_quantity = total_quantity_result.scalar() or 0

                thickness4=319.0,        

                thickness5=319.0,        # 最新和最早生產日期

                thickness6=326.0,        date_query = select(func.max(Record.production_date), func.min(Record.production_date))

                thickness7=324.0,        date_result = await db.execute(date_query)

                appearance=0,        date_row = date_result.first()

                rough_edge=1,        

                slitting_result=1,        latest_date = date_row[0].isoformat() if date_row and date_row[0] else None

                production_date=date(2024, 1, 15)        earliest_date = date_row[1].isoformat() if date_row and date_row[1] else None

            ),        

            # P3 測試資料        return RecordStats(

            Record(            total_records=total_records,

                lot_no="2503033_01",            unique_lots=unique_lots,

                data_type=DataType.P3,            unique_products=unique_products,

                p3_no="2503033012345",            total_quantity=total_quantity,

                product_name="產品A",            latest_production_date=latest_date,

                quantity=100,            earliest_production_date=earliest_date

                production_date=date(2024, 1, 15),        )

                notes="測試產品"        

            )    except Exception as e:

        ]        raise HTTPException(

                    status_code=500,

        for record in test_records:            detail=f"取得統計資訊時發生錯誤：{str(e)}"

            db.add(record)        )

        

        await db.commit()

        @router.post(

        return {    "/records/create-test-data",

            "message": "測試資料創建成功",    summary="創建測試資料",

            "created_records": len(test_records)    description="為演示目的創建一些測試記錄（僅開發環境使用）"

        })

        async def create_test_data(

    except Exception as e:    db: AsyncSession = Depends(get_db)

        await db.rollback()) -> dict:

        raise HTTPException(    """

            status_code=500,    創建測試資料

            detail=f"創建測試資料時發生錯誤：{str(e)}"    

        )    Args:
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
            "message": "測試資料創建成功",
            "created_records": len(test_records)
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"創建測試資料時發生錯誤：{str(e)}"
        )