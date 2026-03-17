from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class AdvancedSearchRequest(BaseModel):
    lot_no: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    machine_no: str | None = None
    mold_no: str | None = None
    winder_number: int | None = None

    page: int = 1
    page_size: int = 20


class TraceResult(BaseModel):
    trace_key: str  # Usually lot_no_norm
    p1_found: bool
    p2_count: int
    p3_count: int


class AdvancedSearchResponse(BaseModel):
    total: int
    results: list[TraceResult]


class TraceDetailResponse(BaseModel):
    trace_key: str
    p1: dict[str, Any] | None
    p2: list[dict[str, Any]]
    p3: list[dict[str, Any]]


class DynamicFilter(BaseModel):
    """A safe, allowlisted dynamic filter that can be translated to v2 advanced query params."""

    field: str = Field(..., description="Allowlisted field key")
    op: str = Field(..., description="Allowlisted operator")
    value: Any = Field(
        None, description="Operator value; may be scalar or list depending on op"
    )


class DynamicQueryRequest(BaseModel):
    """Dynamic query request.

    This endpoint intentionally supports only a constrained subset of fields/operators
    and translates them to the existing strict v2 advanced query implementation.
    """

    data_type: str | None = Field(None, description="P1|P2|P3")
    filters: list[DynamicFilter] = Field(default_factory=list)
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


# --- Legacy-compatible schemas (for frontend QueryPage) ---


class QueryRecordV2Compat(BaseModel):
    id: str
    lot_no: str
    data_type: str  # 'P1' | 'P2' | 'P3'
    production_date: str | None = None
    created_at: str
    display_name: str

    # Optional known fields used by frontend (kept for compatibility)
    winder_number: int | None = None
    # For merged P2 cards: list of winders that match advanced filters.
    winder_numbers: list[int] | None = None
    product_id: str | None = None
    machine_no: str | None = None
    mold_no: str | None = None
    source_winder: int | None = None
    specification: str | None = None
    additional_data: dict[str, Any] | None = None


class QueryResponseV2Compat(BaseModel):
    total_count: int
    page: int
    page_size: int
    records: list[QueryRecordV2Compat]


class LotGroupV2Compat(BaseModel):
    lot_no: str
    p1_count: int
    p2_count: int
    p3_count: int
    total_count: int
    latest_production_date: str | None = None
    created_at: str


class LotGroupListV2Compat(BaseModel):
    total_count: int
    page: int
    page_size: int
    groups: list[LotGroupV2Compat]


class RecordStatsV2Compat(BaseModel):
    total_records: int
    unique_lots: int
    p1_records: int
    p2_records: int
    p3_records: int
    latest_production_date: str | None
    earliest_production_date: str | None
