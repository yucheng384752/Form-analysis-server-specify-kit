"""Station API — generic station/schema/validation-rule/analytics-mapping endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.config import get_settings
from app.core.database import get_db
from app.models.core.tenant import Tenant
from app.services.generic_traceability import GenericTraceabilityService
from app.services.generic_validator import GenericValidator
from app.services.schema_service import SchemaService

router = APIRouter(prefix="/api/stations")


def _require_admin(request: Request) -> None:
    """Raise 403 unless the request carries a valid admin API key."""
    settings = get_settings()
    admin_header = getattr(settings, "admin_api_key_header", "X-Admin-API-Key")
    admin_keys = getattr(settings, "admin_api_keys", set())
    provided = request.headers.get(admin_header)
    if not (provided and provided.strip() in admin_keys):
        is_admin_state = bool(getattr(getattr(request, "state", None), "is_admin", False))
        if not is_admin_state:
            raise HTTPException(403, "Admin API key required")


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------


class StationOut(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    has_items: bool


class FieldDefOut(BaseModel):
    name: str
    type: str
    required: bool = False
    label: dict[str, str] = {}
    filterable: bool = False
    unit: str | None = None
    min: float | None = None
    max: float | None = None


class StationSchemaOut(BaseModel):
    station_code: str
    version: int
    record_fields: list[FieldDefOut]
    item_fields: list[FieldDefOut] | None = None
    unique_key_fields: list[str]


class ValidationRuleOut(BaseModel):
    id: str
    field_name: str
    rule_type: str
    rule_config: dict[str, Any]
    station_id: str | None = None


class AnalyticsMappingOut(BaseModel):
    id: str
    source_path: str
    output_column: str
    output_order: int
    data_type: str
    null_if_missing: bool


class StationLinkOut(BaseModel):
    id: str
    from_station_code: str
    to_station_code: str
    link_type: str
    link_config: dict[str, Any]


class TraceNodeOut(BaseModel):
    station_code: str
    station_name: str
    record: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=list[StationOut])
async def list_stations(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    stations = await svc.list_stations(tenant.id)
    return [
        StationOut(
            id=str(s.id),
            code=s.code,
            name=s.name,
            sort_order=s.sort_order,
            has_items=s.has_items,
        )
        for s in stations
    ]


@router.get("/{code}/schema", response_model=StationSchemaOut)
async def get_station_schema(
    code: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    schema = await svc.get_active_schema(tenant.id, code)
    if not schema:
        raise HTTPException(404, f"No active schema for station {code}")

    station = await svc.get_station(tenant.id, code)
    return StationSchemaOut(
        station_code=station.code if station else code,
        version=schema.version,
        record_fields=[FieldDefOut(**f) for f in schema.record_fields],
        item_fields=[FieldDefOut(**f) for f in schema.item_fields]
        if schema.item_fields
        else None,
        unique_key_fields=schema.unique_key_fields,
    )


@router.get("/{code}/schema/fields", response_model=list[FieldDefOut])
async def get_filterable_fields(
    code: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    fields = await svc.get_filterable_fields(tenant.id, code)
    return [FieldDefOut(**f) for f in fields]


@router.get("/{code}/validation-rules", response_model=list[ValidationRuleOut])
async def get_validation_rules(
    code: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    station = await svc.get_station(tenant.id, code)
    station_id = station.id if station else None
    rules = await svc.get_validation_rules(tenant.id, station_id)
    return [
        ValidationRuleOut(
            id=str(r.id),
            field_name=r.field_name,
            rule_type=r.rule_type,
            rule_config=r.rule_config,
            station_id=str(r.station_id) if r.station_id else None,
        )
        for r in rules
    ]


@router.get("/{code}/analytics-mapping", response_model=list[AnalyticsMappingOut])
async def get_analytics_mapping(
    code: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    station = await svc.get_station(tenant.id, code)
    if not station:
        raise HTTPException(404, f"Station {code} not found")
    mappings = await svc.get_analytics_mapping(tenant.id, station.id)
    return [
        AnalyticsMappingOut(
            id=str(m.id),
            source_path=m.source_path,
            output_column=m.output_column,
            output_order=m.output_order,
            data_type=m.data_type,
            null_if_missing=m.null_if_missing,
        )
        for m in mappings
    ]


@router.get("/links", response_model=list[StationLinkOut])
async def get_station_links(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = SchemaService(db)
    links = await svc.get_station_links(tenant.id)

    stations = await svc.list_stations(tenant.id)
    station_map = {s.id: s.code for s in stations}

    return [
        StationLinkOut(
            id=str(lnk.id),
            from_station_code=station_map.get(lnk.from_station_id, "?"),
            to_station_code=station_map.get(lnk.to_station_id, "?"),
            link_type=lnk.link_type,
            link_config=lnk.link_config,
        )
        for lnk in links
    ]


@router.get("/traceability/{lot_no_norm}", response_model=list[TraceNodeOut])
async def get_traceability_chain(
    lot_no_norm: int,
    start_station: str | None = Query(None),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = GenericTraceabilityService(db)
    chain = await svc.get_chain(tenant.id, lot_no_norm, start_station)
    return [TraceNodeOut(**node.to_dict()) for node in chain]


# ==================================================================
# Request schemas for CRUD (admin-only)
# ==================================================================


class StationCreateIn(BaseModel):
    code: str
    name: str
    sort_order: int = 0
    has_items: bool = False


class StationUpdateIn(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    has_items: bool | None = None


class SchemaUpsertIn(BaseModel):
    record_fields: list[dict[str, Any]]
    item_fields: list[dict[str, Any]] | None = None
    unique_key_fields: list[str] | None = None
    csv_signature_columns: list[str] | None = None
    csv_filename_pattern: str | None = None
    csv_field_mapping: dict[str, Any] | None = None


class ValidationRuleCreateIn(BaseModel):
    field_name: str
    rule_type: str
    rule_config: dict[str, Any]
    station_code: str | None = None


class ValidationRuleUpdateIn(BaseModel):
    field_name: str | None = None
    rule_type: str | None = None
    rule_config: dict[str, Any] | None = None
    is_active: bool | None = None


class AnalyticsMappingCreateIn(BaseModel):
    station_code: str
    source_path: str
    output_column: str
    output_order: int
    data_type: str = "string"
    null_if_missing: bool = True


class AnalyticsMappingUpdateIn(BaseModel):
    source_path: str | None = None
    output_column: str | None = None
    output_order: int | None = None
    data_type: str | None = None
    null_if_missing: bool | None = None


class StationLinkCreateIn(BaseModel):
    from_station_code: str
    to_station_code: str
    link_type: str
    link_config: dict[str, Any] | None = None
    sort_order: int = 0


class StationLinkUpdateIn(BaseModel):
    link_type: str | None = None
    link_config: dict[str, Any] | None = None
    sort_order: int | None = None


# ==================================================================
# CRUD endpoints (admin-only)
# ==================================================================


@router.post("", response_model=StationOut, status_code=201)
async def create_station(
    body: StationCreateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    existing = await svc.get_station(tenant.id, body.code)
    if existing:
        raise HTTPException(409, f"Station {body.code} already exists")
    station = await svc.create_station(
        tenant.id, body.code, body.name, body.sort_order, body.has_items
    )
    await db.commit()
    return StationOut(
        id=str(station.id), code=station.code, name=station.name,
        sort_order=station.sort_order, has_items=station.has_items,
    )


@router.put("/{code}", response_model=StationOut)
async def update_station(
    code: str,
    body: StationUpdateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    patch = body.model_dump(exclude_none=True)
    station = await svc.update_station(tenant.id, code, patch)
    if not station:
        raise HTTPException(404, f"Station {code} not found")
    await db.commit()
    return StationOut(
        id=str(station.id), code=station.code, name=station.name,
        sort_order=station.sort_order, has_items=station.has_items,
    )


@router.delete("/{code}", status_code=204)
async def delete_station(
    code: str,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    deleted = await svc.delete_station(tenant.id, code)
    if not deleted:
        raise HTTPException(404, f"Station {code} not found")
    await db.commit()


# -- Schema CRUD ------------------------------------------------------


@router.put("/{code}/schema", response_model=StationSchemaOut)
async def upsert_station_schema(
    code: str,
    body: SchemaUpsertIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    schema = await svc.upsert_schema(
        tenant.id, code,
        record_fields=body.record_fields,
        item_fields=body.item_fields,
        unique_key_fields=body.unique_key_fields,
        csv_signature_columns=body.csv_signature_columns,
        csv_filename_pattern=body.csv_filename_pattern,
        csv_field_mapping=body.csv_field_mapping,
    )
    if not schema:
        raise HTTPException(404, f"Station {code} not found")
    await db.commit()
    station = await svc.get_station(tenant.id, code)
    return StationSchemaOut(
        station_code=station.code if station else code,
        version=schema.version,
        record_fields=[FieldDefOut(**f) for f in schema.record_fields],
        item_fields=[FieldDefOut(**f) for f in schema.item_fields] if schema.item_fields else None,
        unique_key_fields=schema.unique_key_fields,
    )


# -- Validation Rule CRUD ---------------------------------------------


@router.post("/validation-rules", response_model=ValidationRuleOut, status_code=201)
async def create_validation_rule(
    body: ValidationRuleCreateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    station_id = None
    if body.station_code:
        station = await svc.get_station(tenant.id, body.station_code)
        if not station:
            raise HTTPException(404, f"Station {body.station_code} not found")
        station_id = station.id
    rule = await svc.create_validation_rule(
        tenant.id, station_id, body.field_name, body.rule_type, body.rule_config,
    )
    await db.commit()
    return ValidationRuleOut(
        id=str(rule.id), field_name=rule.field_name, rule_type=rule.rule_type,
        rule_config=rule.rule_config, station_id=str(rule.station_id) if rule.station_id else None,
    )


@router.put("/validation-rules/{rule_id}", response_model=ValidationRuleOut)
async def update_validation_rule(
    rule_id: str,
    body: ValidationRuleUpdateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    patch = body.model_dump(exclude_none=True)
    rule = await svc.update_validation_rule(UUID(rule_id), patch)
    if not rule:
        raise HTTPException(404, "Validation rule not found")
    await db.commit()
    return ValidationRuleOut(
        id=str(rule.id), field_name=rule.field_name, rule_type=rule.rule_type,
        rule_config=rule.rule_config, station_id=str(rule.station_id) if rule.station_id else None,
    )


@router.delete("/validation-rules/{rule_id}", status_code=204)
async def delete_validation_rule(
    rule_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    deleted = await svc.delete_validation_rule(UUID(rule_id))
    if not deleted:
        raise HTTPException(404, "Validation rule not found")
    await db.commit()


# -- Analytics Mapping CRUD -------------------------------------------


@router.post("/analytics-mappings", response_model=AnalyticsMappingOut, status_code=201)
async def create_analytics_mapping(
    body: AnalyticsMappingCreateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    station = await svc.get_station(tenant.id, body.station_code)
    if not station:
        raise HTTPException(404, f"Station {body.station_code} not found")
    mapping = await svc.create_analytics_mapping(
        tenant.id, station.id, body.source_path, body.output_column,
        body.output_order, body.data_type, body.null_if_missing,
    )
    await db.commit()
    return AnalyticsMappingOut(
        id=str(mapping.id), source_path=mapping.source_path,
        output_column=mapping.output_column, output_order=mapping.output_order,
        data_type=mapping.data_type, null_if_missing=mapping.null_if_missing,
    )


@router.put("/analytics-mappings/{mapping_id}", response_model=AnalyticsMappingOut)
async def update_analytics_mapping(
    mapping_id: str,
    body: AnalyticsMappingUpdateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    patch = body.model_dump(exclude_none=True)
    mapping = await svc.update_analytics_mapping(UUID(mapping_id), patch)
    if not mapping:
        raise HTTPException(404, "Analytics mapping not found")
    await db.commit()
    return AnalyticsMappingOut(
        id=str(mapping.id), source_path=mapping.source_path,
        output_column=mapping.output_column, output_order=mapping.output_order,
        data_type=mapping.data_type, null_if_missing=mapping.null_if_missing,
    )


@router.delete("/analytics-mappings/{mapping_id}", status_code=204)
async def delete_analytics_mapping(
    mapping_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    deleted = await svc.delete_analytics_mapping(UUID(mapping_id))
    if not deleted:
        raise HTTPException(404, "Analytics mapping not found")
    await db.commit()


# -- Station Link CRUD ------------------------------------------------


@router.post("/links", response_model=StationLinkOut, status_code=201)
async def create_station_link(
    body: StationLinkCreateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    from_st = await svc.get_station(tenant.id, body.from_station_code)
    to_st = await svc.get_station(tenant.id, body.to_station_code)
    if not from_st:
        raise HTTPException(404, f"Station {body.from_station_code} not found")
    if not to_st:
        raise HTTPException(404, f"Station {body.to_station_code} not found")
    link = await svc.create_station_link(
        tenant.id, from_st.id, to_st.id, body.link_type, body.link_config, body.sort_order,
    )
    await db.commit()
    return StationLinkOut(
        id=str(link.id), from_station_code=body.from_station_code,
        to_station_code=body.to_station_code, link_type=link.link_type,
        link_config=link.link_config,
    )


@router.put("/links/{link_id}", response_model=StationLinkOut)
async def update_station_link(
    link_id: str,
    body: StationLinkUpdateIn,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    patch = body.model_dump(exclude_none=True)
    link = await svc.update_station_link(UUID(link_id), patch)
    if not link:
        raise HTTPException(404, "Station link not found")
    await db.commit()
    stations = await svc.list_stations(tenant.id)
    station_map = {s.id: s.code for s in stations}
    return StationLinkOut(
        id=str(link.id),
        from_station_code=station_map.get(link.from_station_id, "?"),
        to_station_code=station_map.get(link.to_station_id, "?"),
        link_type=link.link_type, link_config=link.link_config,
    )


@router.delete("/links/{link_id}", status_code=204)
async def delete_station_link(
    link_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(request)
    svc = SchemaService(db)
    deleted = await svc.delete_station_link(UUID(link_id))
    if not deleted:
        raise HTTPException(404, "Station link not found")
    await db.commit()
