from typing import List, Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

from app.core.database import get_db
from app.models import EditReason, RowEdit, P1Record, P2Record, P3Record
from app.schemas.audit import EditReasonResponse, EditRecordRequest, RowEditResponse

router = APIRouter()

def get_model_by_table_code(table_code: str):
    code = table_code.upper()
    if code == "P1":
        return P1Record
    elif code == "P2":
        return P2Record
    elif code == "P3":
        return P3Record
    else:
        raise HTTPException(status_code=400, detail=f"Invalid table code: {table_code}")

@router.get("/reasons", response_model=List[EditReasonResponse])
async def get_edit_reasons(
    tenant_id: Optional[UUID] = None,
    http_request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of active edit reasons for a tenant.
    """
    resolved_tenant_id = tenant_id
    if resolved_tenant_id is None and http_request is not None:
        resolved_tenant_id = getattr(getattr(http_request, "state", None), "tenant_id", None) or getattr(
            getattr(http_request, "state", None), "auth_tenant_id", None
        )

    if resolved_tenant_id is None:
        raise HTTPException(status_code=422, detail="tenant_id is required (provide X-Tenant-Id header or tenant_id)")

    query = select(EditReason).where(
        EditReason.tenant_id == resolved_tenant_id,
        EditReason.is_active == True
    ).order_by(EditReason.display_order)
    
    result = await db.execute(query)
    reasons = result.scalars().all()
    return reasons

@router.patch("/records/{table_code}/{record_id}", response_model=Dict[str, Any])
async def update_record(
    table_code: str = Path(..., description="Table code (P1, P2, P3)"),
    record_id: UUID = Path(..., description="Record ID"),
    http_request: Request = None,
    payload: EditRecordRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a record with audit logging.
    """
    ModelClass = get_model_by_table_code(table_code)
    
    # 1. Fetch existing record
    query = select(ModelClass).where(ModelClass.id == record_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    resolved_tenant_id = payload.tenant_id
    if resolved_tenant_id is None and http_request is not None:
        resolved_tenant_id = getattr(getattr(http_request, "state", None), "tenant_id", None) or getattr(
            getattr(http_request, "state", None), "auth_tenant_id", None
        )

    if resolved_tenant_id is None:
        raise HTTPException(status_code=422, detail="tenant_id is required (provide X-Tenant-Id header or tenant_id)")

    # Prevent cross-tenant edits.
    if getattr(record, "tenant_id", None) is not None and str(getattr(record, "tenant_id")) != str(resolved_tenant_id):
        raise HTTPException(status_code=404, detail="Record not found")
    
    # 2. Capture state before update
    # Convert record to dict (excluding internal fields if necessary)
    before_json = {c.name: getattr(record, c.name) for c in record.__table__.columns}
    # Serialize UUIDs and Datetimes if needed, but JSON column usually handles basic types or we use a custom encoder.
    # SQLAlchemy models to dict usually needs care with dates/UUIDs for JSON storage.
    # For simplicity, we'll rely on Pydantic's jsonable_encoder or similar if we were returning it, 
    # but for storage in JSON column, we need to ensure it's JSON serializable.
    # Let's do a simple conversion helper.
    
    def json_friendly(d):
        new_d = {}
        for k, v in d.items():
            if isinstance(v, UUID):
                new_d[k] = str(v)
            elif hasattr(v, 'isoformat'):
                new_d[k] = v.isoformat()
            else:
                new_d[k] = v
        return new_d

    before_json_safe = json_friendly(before_json)

    # 3. Apply updates
    # Validate that fields exist in model or put in extras
    valid_columns = {c.name for c in record.__table__.columns}
    
    # Prepare extras update if needed
    current_extras = dict(getattr(record, "extras", {}))
    extras_changed = False

    for key, value in payload.updates.items():
        if key == 'id':
            continue # Prevent ID update
            
        if key in valid_columns:
            setattr(record, key, value)
        else:
            # If not a column, assume it's an extra field
            # Only if the model has 'extras' column
            if "extras" in valid_columns:
                current_extras[key] = value
                extras_changed = True
            else:
                raise HTTPException(status_code=400, detail=f"Invalid field: {key}")
    
    if extras_changed:
        record.extras = current_extras
    
    # 4. Capture state after update
    # We need to flush to get any DB-side defaults if we were creating, but here we are updating.
    # However, the object is updated in memory.
    after_json = {c.name: getattr(record, c.name) for c in record.__table__.columns}
    after_json_safe = json_friendly(after_json)
    
    # 5. Create Audit Log
    actor_label = getattr(getattr(http_request, "state", None), "auth_api_key_label", None) if http_request else None
    actor_id = getattr(getattr(http_request, "state", None), "auth_api_key_id", None) if http_request else None
    created_by = actor_label or (str(actor_id) if actor_id else None) or "system"

    row_edit = RowEdit(
        tenant_id=resolved_tenant_id,
        table_code=table_code.upper(),
        record_id=record_id,
        reason_id=payload.reason_id,
        reason_text=payload.reason_text,
        before_json=before_json_safe,
        after_json=after_json_safe,
        created_by=created_by,
    )
    
    db.add(row_edit)
    
    # 6. Commit
    await db.commit()
    await db.refresh(record)
    
    return json_friendly({c.name: getattr(record, c.name) for c in record.__table__.columns})

@router.post("/reasons/init", response_model=List[EditReasonResponse])
async def init_default_reasons(
    tenant_id: Optional[UUID] = Body(None, embed=True),
    http_request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize default edit reasons for a tenant.
    """
    resolved_tenant_id = tenant_id
    if resolved_tenant_id is None and http_request is not None:
        resolved_tenant_id = getattr(getattr(http_request, "state", None), "tenant_id", None) or getattr(
            getattr(http_request, "state", None), "auth_tenant_id", None
        )

    if resolved_tenant_id is None:
        raise HTTPException(status_code=422, detail="tenant_id is required (provide X-Tenant-Id header or tenant_id)")

    defaults = [
        {"code": "TYPO", "desc": "Typo / Spelling Error", "order": 1},
        {"code": "WRONG_DATA", "desc": "Incorrect Data Entry", "order": 2},
        {"code": "MISSING_INFO", "desc": "Missing Information", "order": 3},
        {"code": "SYSTEM_ERROR", "desc": "System Import Error", "order": 4},
        {"code": "OTHER", "desc": "Other (Please Specify)", "order": 99},
    ]
    
    created = []
    for d in defaults:
        # Check if exists
        query = select(EditReason).where(
            EditReason.tenant_id == resolved_tenant_id,
            EditReason.reason_code == d["code"]
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if not existing:
            reason = EditReason(
                tenant_id=resolved_tenant_id,
                reason_code=d["code"],
                description=d["desc"],
                display_order=d["order"]
            )
            db.add(reason)
            created.append(reason)
    
    if created:
        await db.commit()
        for r in created:
            await db.refresh(r)
            
    # Return all
    query = select(EditReason).where(EditReason.tenant_id == resolved_tenant_id).order_by(EditReason.display_order)
    result = await db.execute(query)
    return result.scalars().all()
