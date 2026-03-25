"""Station API — generic station/schema/validation-rule/analytics-mapping endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.models.core.tenant import Tenant
from app.services.generic_traceability import GenericTraceabilityService
from app.services.generic_validator import GenericValidator
from app.services.schema_service import SchemaService

router = APIRouter(prefix="/api/stations")


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
