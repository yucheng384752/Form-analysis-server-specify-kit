"""
資料查詢路由

提供查詢已匯入資料的API端點。
支援P1/P2/P3三種不同類型的資料查詢。
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy import select, func, or_, and_, String, exists
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, date, timezone

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no

from app.api.deps import get_current_tenant
from app.models.core.tenant import Tenant

# 獲取日誌記錄器
logger = get_logger(__name__)

# 建立路由器
router = APIRouter(
    tags=["資料查詢"]
)


async def _legacy_fallback_enabled(db: AsyncSession) -> bool:
    """Legacy tables are not tenant-scoped.

    To prevent cross-tenant leakage, only allow legacy fallback when the DB has
    a single tenant.
    """
    try:
        tenants_count = await db.scalar(select(func.count()).select_from(Tenant))
        return (tenants_count or 0) <= 1
    except Exception:
        return False


async def _resolve_current_tenant(db: AsyncSession, x_tenant_id: Optional[str]) -> Optional[Tenant]:
    if x_tenant_id is not None:
        # If client explicitly provided tenant id, let errors surface.
        return await get_current_tenant(x_tenant_id=x_tenant_id, db=db)

    # If not provided, try best-effort (works for single-tenant DBs).
    try:
        return await get_current_tenant(x_tenant_id=None, db=db)
    except Exception:
        return None


def _map_v2_record_to_legacy(r: Any) -> "QueryRecord":
    return QueryRecord(
        id=r.id,
        lot_no=r.lot_no,
        data_type=r.data_type,
        production_date=r.production_date,
        created_at=r.created_at,
        display_name=r.display_name,
        additional_data=r.additional_data,
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
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> LotGroupListResponse:
    """查詢批號分組"""
    try:
        logger.info("開始查詢批號分組", search=search, page=page, page_size=page_size)

        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 (tenant-scoped).
        # If a tenant is resolved, treat v2 as the source of truth and do not
        # fall back to legacy just because v2 is empty.
        if current_tenant is not None:
            try:
                from app.api.routes_query_v2 import query_lot_groups_v2

                v2_resp = await query_lot_groups_v2(
                    search=search,
                    page=page,
                    page_size=page_size,
                    db=db,
                    current_tenant=current_tenant,
                )

                mapped_groups = [
                    LotGroupResponse(
                        lot_no=g.lot_no,
                        p1_count=g.p1_count,
                        p2_count=g.p2_count,
                        p3_count=g.p3_count,
                        total_count=g.total_count,
                        latest_production_date=g.latest_production_date,
                        created_at=g.created_at,
                    )
                    for g in v2_resp.groups
                ]

                return LotGroupListResponse(
                    total_count=v2_resp.total_count,
                    page=v2_resp.page,
                    page_size=v2_resp.page_size,
                    groups=mapped_groups,
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("批號分組 v2 查詢失敗，嘗試 legacy fallback", error=str(e))
        
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

        if not await _legacy_fallback_enabled(db):
            return LotGroupListResponse(total_count=0, page=page, page_size=page_size, groups=[])
        
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
    summary="進階搜尋資料記錄",
    description="""
    使用多個條件進行進階搜尋
    
    **查詢參數（所有參數均為選填，支援模糊搜尋）：**
    - lot_no: 批號（模糊搜尋）
    - production_date_from: 生產日期起始（YYYY-MM-DD）
    - production_date_to: 生產日期結束（YYYY-MM-DD）
    - machine_no: 機台號碼（模糊搜尋，如: P24, P21）
    - mold_no: 下膠編號 (Bottom Tape)（模糊搜尋，如: M250523-06-0159）
    - product_id: 產品編號（模糊搜尋）
    - p3_specification: P3規格（模糊搜尋）
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
    mold_no: Optional[str] = Query(None, description="下膠編號 (Bottom Tape)（模糊搜尋）"),
    product_id: Optional[str] = Query(None, description="產品編號（模糊搜尋）"),
    p3_specification: Optional[str] = Query(None, description="P3規格（模糊搜尋）"),
    winder_number: Optional[int] = Query(None, description="卷收機號碼（精確搜尋，用於 P2）"),
    material: Optional[str] = Query(None, description="材料代號（P1/P2）"),
    data_type: Optional[DataType] = Query(None, description="資料類型 (P1/P2/P3)"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> QueryResponse:
    """進階搜尋資料記錄 - 支援多條件模糊搜尋"""
    try:
        logger.info("開始進階搜尋", 
                   lot_no=lot_no,
                   production_date_from=production_date_from,
                   production_date_to=production_date_to,
                   machine_no=machine_no,
                   mold_no=mold_no,
                   product_id=product_id,
                   p3_specification=p3_specification,
                   winder_number=winder_number,
                   material=material,
                   data_type=data_type,
                   page=page,
                   page_size=page_size)

        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        tenant_header_provided = x_tenant_id is not None and x_tenant_id.strip() != ""
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 (tenant-scoped).
        # - If tenant is explicitly provided via header, treat v2 as the source of truth
        #   and do not fall back to legacy just because v2 is empty.
        # - If tenant is inferred (single-tenant convenience, header missing), keep
        #   backward-compat: allow legacy fallback when v2 is empty.
        if current_tenant is not None and tenant_header_provided:
            try:
                from app.api.routes_query_v2 import query_records_advanced_v2

                v2_resp = await query_records_advanced_v2(
                    lot_no=lot_no,
                    production_date_from=production_date_from.isoformat() if production_date_from else None,
                    production_date_to=production_date_to.isoformat() if production_date_to else None,
                    machine_no=machine_no,
                    mold_no=mold_no,
                    product_id=product_id,
                    material=material,
                    specification=p3_specification,
                    winder_number=str(winder_number) if winder_number is not None else None,
                    data_type=data_type.value if data_type else None,
                    page=page,
                    page_size=page_size,
                    db=db,
                    current_tenant=current_tenant,
                )

                return QueryResponse(
                    total_count=v2_resp.total_count,
                    page=v2_resp.page,
                    page_size=v2_resp.page_size,
                    records=[_map_v2_record_to_legacy(r) for r in v2_resp.records],
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records/advanced v2 查詢失敗，嘗試 legacy fallback", error=str(e))

        if current_tenant is not None and not tenant_header_provided:
            try:
                from app.api.routes_query_v2 import query_records_advanced_v2

                v2_resp = await query_records_advanced_v2(
                    lot_no=lot_no,
                    production_date_from=production_date_from.isoformat() if production_date_from else None,
                    production_date_to=production_date_to.isoformat() if production_date_to else None,
                    machine_no=machine_no,
                    mold_no=mold_no,
                    product_id=product_id,
                    material=material,
                    specification=p3_specification,
                    winder_number=str(winder_number) if winder_number is not None else None,
                    data_type=data_type.value if data_type else None,
                    page=page,
                    page_size=page_size,
                    db=db,
                    current_tenant=current_tenant,
                )

                if v2_resp.total_count > 0 or not await _legacy_fallback_enabled(db):
                    return QueryResponse(
                        total_count=v2_resp.total_count,
                        page=v2_resp.page,
                        page_size=v2_resp.page_size,
                        records=[_map_v2_record_to_legacy(r) for r in v2_resp.records],
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records/advanced v2 查詢失敗，嘗試 legacy fallback", error=str(e))
        
        # 建構查詢條件列表
        conditions = []
        
        # 批號模糊搜尋
        if lot_no and lot_no.strip():
            conditions.append(Record.lot_no.ilike(f"%{lot_no.strip()}%"))
        
        # 卷收機號碼精確搜尋（P2/P3）
        # 使用 EXISTS 避免不必要 JOIN 造成 row 重複/意外匹配
        if winder_number is not None:
            conditions.append(
                or_(
                    and_(
                        Record.data_type == DataType.P2,
                        exists(
                            select(1)
                            .select_from(P2Item)
                            .where(
                                P2Item.record_id == Record.id,
                                P2Item.winder_number == winder_number,
                            )
                        ),
                    ),
                    and_(
                        Record.data_type == DataType.P3,
                        exists(
                            select(1)
                            .select_from(P3Item)
                            .where(
                                P3Item.record_id == Record.id,
                                P3Item.source_winder == winder_number,
                            )
                        ),
                    ),
                )
            )

        # 材料代號搜尋（P1/P2）
        if material and material.strip():
            m = material.strip()
            conditions.append(
                and_(
                    Record.data_type.in_([DataType.P1, DataType.P2]),
                    Record.material_code.isnot(None),
                    Record.material_code.ilike(f"%{m}%"),
                )
            )
        
        # 生產日期範圍搜尋
        if production_date_from:
            conditions.append(Record.production_date >= production_date_from)
        if production_date_to:
            conditions.append(Record.production_date <= production_date_to)
        
        # 機台號碼模糊搜尋（P3專用）
        if machine_no and machine_no.strip():
            conditions.append(P3Item.machine_no.ilike(f"%{machine_no.strip()}%"))
        
        # 下膠編號模糊搜尋（P3專用，使用獨立欄位搜尋）
        if mold_no and mold_no.strip():
            conditions.append(P3Item.bottom_tape_lot.ilike(f"%{mold_no.strip()}%"))
        
        # 產品編號模糊搜尋
        if product_id and product_id.strip():
            conditions.append(P3Item.product_id.ilike(f"%{product_id.strip()}%"))
        
        # P3 規格搜尋（使用獨立欄位搜尋）
        if p3_specification and p3_specification.strip():
            conditions.append(P3Item.specification.ilike(f"%{p3_specification.strip()}%"))
        
        # 資料類型過濾
        if data_type:
            conditions.append(Record.data_type == data_type)
        
        # 如果沒有任何條件，返回空結果
        if not conditions:
            logger.warning("進階搜尋沒有提供任何搜尋條件")
            return QueryResponse(
                total_count=0,
                page=page,
                page_size=page_size,
                records=[]
            )
        
        # 組合查詢
        query_stmt = select(Record).distinct()
        
        # 檢查是否需要 join P3Item
        need_p3_join = (
            (machine_no and machine_no.strip()) or
            (mold_no and mold_no.strip()) or
            (product_id and product_id.strip()) or
            (p3_specification and p3_specification.strip())
        )
        
        if need_p3_join:
            query_stmt = query_stmt.join(Record.p3_items)
        
        query_stmt = query_stmt.where(and_(*conditions))
        
        # 計算總數
        count_query = select(func.count(func.distinct(Record.id))).select_from(Record)
        if need_p3_join:
            count_query = count_query.join(Record.p3_items)
        count_query = count_query.where(and_(*conditions))
        
        result = await db.execute(count_query)
        total_count = result.scalar() or 0
        
        # 分頁查詢
        offset = (page - 1) * page_size
        # 預加載 p2_items 和 p3_items
        query_stmt = query_stmt.options(
            selectinload(Record.p2_items),
            selectinload(Record.p3_items)
        )
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
                # [FIX] 強制使用 p2_items 表格資料，不使用 JSONB 中的 rows
                # P2 改為從 p2_items 獲取資料並放入 additional_data['rows']
                rows = []
                if record.p2_items:
                    # 排序 p2_items (按 winder_number)
                    sorted_items = sorted(record.p2_items, key=lambda x: x.winder_number)
                    for item in sorted_items:
                        # 如果有指定 winder_number，只返回該 winder 的資料
                        if winder_number is not None and item.winder_number != winder_number:
                            continue
                            
                        if item.row_data:
                            rows.append(item.row_data)
                
                if not query_record.additional_data:
                    query_record.additional_data = {}
                query_record.additional_data['rows'] = rows
                
            elif record.data_type == DataType.P3:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
                
                # [FIX] 強制使用 p3_items 表格資料，不使用 JSONB 中的 rows
                # P3: 從 p3_items 獲取資料並放入 additional_data['rows']
                rows = []
                if record.p3_items:
                    # 排序 p3_items (按 row_no)
                    sorted_items = sorted(record.p3_items, key=lambda x: x.row_no)
                    for item in sorted_items:
                        if winder_number is not None and item.source_winder != winder_number:
                            continue
                        row = item.row_data.copy() if item.row_data else {}
                        # 注入 product_id 到 row data 中，供前端顯示
                        row['product_id'] = item.product_id
                        rows.append(row)
                
                if not query_record.additional_data:
                    query_record.additional_data = {}
                query_record.additional_data['rows'] = rows
            
            query_records.append(query_record)
        
        logger.info("進階搜尋完成", 
                   total_count=total_count,
                   returned_count=len(query_records),
                   conditions_count=len(conditions))

        if not await _legacy_fallback_enabled(db):
            return QueryResponse(total_count=0, page=page, page_size=page_size, records=[])
        
        return QueryResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            records=query_records
        )
        
    except Exception as e:
        logger.error("進階搜尋失敗", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"進階搜尋時發生錯誤：{str(e)}"
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
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> QueryResponse:
    """查詢指定批號的資料記錄"""
    try:
        logger.info("開始查詢資料記錄", lot_no=lot_no, data_type=data_type, page=page, page_size=page_size)

        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        tenant_header_provided = x_tenant_id is not None and x_tenant_id.strip() != ""
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 (tenant-scoped).
        # - If tenant is explicitly provided via header, treat v2 as the source of truth
        #   and do not fall back to legacy just because v2 is empty.
        # - If tenant is inferred (single-tenant convenience, header missing), keep
        #   backward-compat: allow legacy fallback when v2 is empty.
        if current_tenant is not None and tenant_header_provided:
            try:
                from app.api.routes_query_v2 import query_records_v2

                v2_resp = await query_records_v2(
                    lot_no=lot_no,
                    data_type=data_type.value if data_type else None,
                    page=page,
                    page_size=page_size,
                    db=db,
                    current_tenant=current_tenant,
                )

                return QueryResponse(
                    total_count=v2_resp.total_count,
                    page=v2_resp.page,
                    page_size=v2_resp.page_size,
                    records=[_map_v2_record_to_legacy(r) for r in v2_resp.records],
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records v2 查詢失敗，嘗試 legacy fallback", error=str(e))

        if current_tenant is not None and not tenant_header_provided:
            try:
                from app.api.routes_query_v2 import query_records_v2

                v2_resp = await query_records_v2(
                    lot_no=lot_no,
                    data_type=data_type.value if data_type else None,
                    page=page,
                    page_size=page_size,
                    db=db,
                    current_tenant=current_tenant,
                )

                if v2_resp.total_count > 0 or not await _legacy_fallback_enabled(db):
                    return QueryResponse(
                        total_count=v2_resp.total_count,
                        page=v2_resp.page,
                        page_size=v2_resp.page_size,
                        records=[_map_v2_record_to_legacy(r) for r in v2_resp.records],
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records v2 查詢失敗，嘗試 legacy fallback", error=str(e))
        
        # 建構查詢條件
        conditions = [Record.lot_no == lot_no]
        if data_type:
            conditions.append(Record.data_type == data_type)
        
        query_stmt = select(Record).where(and_(*conditions))
        
        # 計算總數
        count_query = select(func.count(Record.id)).select_from(Record).where(and_(*conditions))
        result = await db.execute(count_query)
        total_count = result.scalar() or 0
        
        # 分頁查詢
        offset = (page - 1) * page_size
        # 預加載 p2_items 和 p3_items
        query_stmt = query_stmt.options(
            selectinload(Record.p2_items),
            selectinload(Record.p3_items)
        )
        query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)
        
        result = await db.execute(query_stmt)
        records = result.scalars().all()
        
        # 轉換為回應格式
        query_records = []
        for record in records:
            # 確保 additional_data 是字典
            additional_data = record.additional_data if isinstance(record.additional_data, dict) else {}
            
            query_record = QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                data_type=record.data_type.value,
                production_date=record.production_date.isoformat() if record.production_date else None,
                created_at=record.created_at.isoformat(),
                display_name=record.display_name,
                additional_data=additional_data  # 包含所有額外欄位
            )
            
            # 根據資料類型設置對應欄位
            if record.data_type == DataType.P1:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            elif record.data_type == DataType.P2:
                # [FIX] 強制使用 p2_items 表格資料，不使用 JSONB 中的 rows
                # P2 改為從 p2_items 獲取資料並放入 additional_data['rows']
                rows = []
                if record.p2_items:
                    # 排序 p2_items (按 winder_number)
                    sorted_items = sorted(record.p2_items, key=lambda x: x.winder_number)
                    for item in sorted_items:
                        if item.row_data:
                            rows.append(item.row_data)
                
                if not query_record.additional_data:
                    query_record.additional_data = {}
                query_record.additional_data['rows'] = rows
            elif record.data_type == DataType.P3:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
                
                # [FIX] 強制使用 p3_items 表格資料，不使用 JSONB 中的 rows
                # P3: 從 p3_items 獲取資料並放入 additional_data['rows']
                rows = []
                if record.p3_items:
                    # 排序 p3_items (按 row_no)
                    sorted_items = sorted(record.p3_items, key=lambda x: x.row_no)
                    for item in sorted_items:
                        row = item.row_data.copy() if item.row_data else {}
                        # 注入 product_id 到 row data 中，供前端顯示
                        row['product_id'] = item.product_id
                        rows.append(row)
                
                if not query_record.additional_data:
                    query_record.additional_data = {}
                query_record.additional_data['rows'] = rows
            
            query_records.append(query_record)
        
        logger.info("查詢完成", lot_no=lot_no, data_type=data_type, total_count=total_count, returned_count=len(query_records))

        if not await _legacy_fallback_enabled(db):
            return QueryResponse(total_count=0, page=page, page_size=page_size, records=[])

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
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
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
        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 suggestions.
        # If a tenant is resolved, treat v2 as the source of truth and do not
        # fall back to legacy just because v2 is empty.
        if current_tenant is not None:
            try:
                from app.api.routes_query_v2 import suggest_lots

                return await suggest_lots(term=query, limit=limit, db=db, current_tenant=current_tenant)
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("批號建議 v2 查詢失敗，嘗試 legacy fallback", error=str(e))

        if not await _legacy_fallback_enabled(db):
            return []

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
    "/options/{field_name}",
    response_model=List[str],
    summary="取得欄位選項",
    description="取得指定欄位的所有不重複值，用於前端下拉選單"
)
async def get_field_options(
    field_name: str,
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> List[str]:
    """
    取得指定欄位的所有不重複值
    
    Args:
        field_name: 欄位名稱 (specification, machine_no, bottom_tape_lot, material_code)
        db: 資料庫會話
    
    Returns:
        List[str]: 選項列表
    """
    try:
        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 options when supported.
        v2_field = None
        if field_name in {"machine_no", "mold_no", "specification", "winder_number", "material"}:
            v2_field = field_name
        elif field_name == "bottom_tape_lot":
            # legacy bottom_tape_lot maps to v2 mold_no
            v2_field = "mold_no"
        elif field_name == "material_code":
            # legacy material_code maps to v2 material options list
            v2_field = "material"
        elif field_name == "p3_specification":
            v2_field = "specification"
        elif field_name == "product_id":
            v2_field = "product_id"

        if v2_field and current_tenant is not None:
            try:
                from app.api.routes_query_v2 import get_field_options_v2
                v2_options = await get_field_options_v2(
                    field_name=v2_field,
                    limit=200,
                    db=db,
                    current_tenant=current_tenant,
                )
                # If tenant context is available, treat v2 as the source of truth
                # and do not fall back to legacy just because v2 is empty.
                return v2_options
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("欄位選項 v2 查詢失敗，嘗試 legacy fallback", field_name=field_name, error=str(e))

        if not await _legacy_fallback_enabled(db):
            return []

        # 映射前端欄位名稱到資料庫模型欄位
        field_map = {
            "specification": P3Item.specification,
            "p3_specification": P3Item.specification,
            "machine_no": P3Item.machine_no,
            "bottom_tape_lot": P3Item.bottom_tape_lot,
            "mold_no": P3Item.bottom_tape_lot, # 前端 mold_no 對應 DB bottom_tape_lot
            "material_code": Record.material_code,
            "product_id": P3Item.product_id
        }
        
        if field_name not in field_map:
            raise HTTPException(status_code=400, detail=f"不支援的欄位名稱: {field_name}")
            
        target_column = field_map[field_name]
        
        # 查詢不重複值，排除空值
        stmt = (
            select(target_column)
            .where(target_column.isnot(None))
            .where(target_column != "")
            .distinct()
            .order_by(target_column)
        )
        
        result = await db.execute(stmt)
        options = [str(row[0]) for row in result.fetchall() if row[0]]

        return options
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得欄位選項失敗: {field_name}", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"取得欄位選項時發生錯誤：{str(e)}"
        )


# NOTE: This must be declared before `/records/{record_id}`.
# Otherwise FastAPI can match `/records/{record_id}` first and reject
# `/records/stats` with a 422 UUID parsing error.
@router.get(
    "/records/stats",
    response_model=RecordStats,
    summary="取得記錄統計資訊",
    description="取得資料庫中記錄的統計資訊，包含總數、P1/P2/P3分類統計等"
)
async def get_record_stats(
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> RecordStats:
    """
    取得記錄統計資訊
    
    Args:
        db: 資料庫會話
    
    Returns:
        RecordStats: 統計資訊
    """
    try:
        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        tenant_header_provided = x_tenant_id is not None and x_tenant_id.strip() != ""
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 (tenant-scoped).
        # - If tenant is explicitly provided via header, treat v2 as the source of truth
        #   and do not fall back to legacy just because v2 is empty.
        # - If tenant is inferred (single-tenant convenience, header missing), keep
        #   backward-compat: allow legacy fallback when v2 is empty.
        if current_tenant is not None and tenant_header_provided:
            try:
                from app.api.routes_query_v2 import get_record_stats_v2

                v2_stats = await get_record_stats_v2(db=db, current_tenant=current_tenant)
                return RecordStats(
                    total_records=v2_stats.total_records,
                    unique_lots=v2_stats.unique_lots,
                    p1_records=v2_stats.p1_records,
                    p2_records=v2_stats.p2_records,
                    p3_records=v2_stats.p3_records,
                    latest_production_date=v2_stats.latest_production_date,
                    earliest_production_date=v2_stats.earliest_production_date,
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records/stats v2 查詢失敗，嘗試 legacy fallback", error=str(e))

        if current_tenant is not None and not tenant_header_provided:
            try:
                from app.api.routes_query_v2 import get_record_stats_v2

                v2_stats = await get_record_stats_v2(db=db, current_tenant=current_tenant)
                if v2_stats.total_records > 0 or not await _legacy_fallback_enabled(db):
                    return RecordStats(
                        total_records=v2_stats.total_records,
                        unique_lots=v2_stats.unique_lots,
                        p1_records=v2_stats.p1_records,
                        p2_records=v2_stats.p2_records,
                        p3_records=v2_stats.p3_records,
                        latest_production_date=v2_stats.latest_production_date,
                        earliest_production_date=v2_stats.earliest_production_date,
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("records/stats v2 查詢失敗，嘗試 legacy fallback", error=str(e))

        if not await _legacy_fallback_enabled(db):
            return RecordStats(
                total_records=0,
                unique_lots=0,
                p1_records=0,
                p2_records=0,
                p3_records=0,
                latest_production_date=None,
                earliest_production_date=None,
            )

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


@router.get(
    "/records/{record_id}",
    response_model=QueryRecord,
    summary="取得單筆記錄",
    description="根據記錄ID取得詳細資訊"
)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
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
        current_tenant = await _resolve_current_tenant(db=db, x_tenant_id=x_tenant_id)
        if current_tenant is None and not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=400, detail="需要提供 X-Tenant-Id")

        # Prefer v2 lookup.
        if current_tenant is not None:
            from app.api.routes_query_v2 import get_record_v2

            try:
                v2_record = await get_record_v2(record_id=record_id, db=db, current_tenant=current_tenant)
                return _map_v2_record_to_legacy(v2_record)
            except HTTPException as e:
                if e.status_code != 404:
                    raise

        if not await _legacy_fallback_enabled(db):
            raise HTTPException(status_code=404, detail="找不到指定的記錄")

        query = select(Record).where(Record.id == record_id).options(selectinload(Record.p2_items))
        result = await db.execute(query)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="找不到指定的記錄")
        
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
            # P2 改為從 p2_items 獲取資料並放入 additional_data['rows']
            if record.p2_items:
                rows = []
                # 排序 p2_items (按 winder_number)
                sorted_items = sorted(record.p2_items, key=lambda x: x.winder_number)
                for item in sorted_items:
                    if item.row_data:
                        rows.append(item.row_data)
                
                if not query_record.additional_data:
                    query_record.additional_data = {}
                query_record.additional_data['rows'] = rows
        elif record.data_type == DataType.P3:
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


@router.post(
    "/records/create-test-data",
    summary="創建測試資料",
    description="為演示目的創建一些測試記錄（僅開發環境使用）"
)
async def create_test_data(
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> dict:
    """
    創建測試資料
    
    Args:
        db: 資料庫會話
    
    Returns:
        dict: 創建結果
    """
    try:
        # Seed v2 tenant-scoped tables so legacy query wrappers (which prefer v2)
        # can immediately show demo data without relying on legacy tables.
        lot_no = "2503033_01"
        lot_no_norm = normalize_lot_no(lot_no)

        now = datetime.now(timezone.utc)
        test_records = [
            P1Record(
                tenant_id=current_tenant.id,
                lot_no_raw=lot_no,
                lot_no_norm=lot_no_norm,
                extras={"product_name": "產品A", "quantity": 100, "notes": "測試產品"},
                created_at=now,
            ),
            P2Record(
                tenant_id=current_tenant.id,
                lot_no_raw=lot_no,
                lot_no_norm=lot_no_norm,
                winder_number=1,
                extras={
                    "sheet_width": 7.985,
                    "thickness": [319.0, 325.0, 320.0, 319.0, 319.0, 326.0, 324.0],
                    "appearance": 0,
                    "rough_edge": 1,
                    "slitting_result": 1,
                },
                created_at=now,
            ),
            P3Record(
                tenant_id=current_tenant.id,
                lot_no_raw=lot_no,
                lot_no_norm=lot_no_norm,
                production_date_yyyymmdd=20240115,
                machine_no="P24",
                mold_no="M1",
                product_id=f"2024-01-15-P24-M1-{lot_no}",
                extras={"rows": [{"specification": "P3-SPEC", "notes": "測試產品"}]},
                created_at=now,
            ),
        ]

        for r in test_records:
            db.add(r)
        
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