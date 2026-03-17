"""Helper functions for analytics API endpoints."""

import re
from typing import Any

import pandas as pd
from fastapi import Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.analytics_config import AnalyticsConfig
from app.core.rate_limit import check_rate_limit as _shared_check_rate_limit
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record


def check_rate_limit(request: Request, *, endpoint: str | None = None):
    _shared_check_rate_limit(
        request,
        max_per_minute=AnalyticsConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
        endpoint=endpoint,
    )


def _extract_trace_tokens(trace_payload: Any) -> list[str]:
    if not isinstance(trace_payload, dict):
        return []
    p3 = trace_payload.get("p3")
    if not isinstance(p3, dict):
        return []

    out: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        s = str(value or "").strip()
        if not s:
            return
        k = s.lower()
        if k in seen:
            return
        seen.add(k)
        out.append(s)

    lot_no = p3.get("lot_no")
    source_winder = p3.get("source_winder")
    if lot_no and source_winder is not None:
        add(f"{lot_no}_{source_winder}")

    add(p3.get("product_id"))

    additional = p3.get("additional_data")
    rows = additional.get("rows") if isinstance(additional, dict) else None
    if isinstance(rows, list):
        for row in rows[:50]:
            if not isinstance(row, dict):
                continue
            add(row.get("Produce_No."))
            add(row.get("Produce_No"))
            add(row.get("produce_no"))
            add(row.get("P3_No."))
            add(row.get("lot no"))
            add(row.get("Lot No"))
            lot = str(row.get("lot") or "").strip()
            if lot and lot_no:
                add(f"{lot_no}_{lot}")

    return out[:50]


def _trace_rows_count(node: Any) -> int:
    if not isinstance(node, dict):
        return 0
    additional = node.get("additional_data")
    rows = additional.get("rows") if isinstance(additional, dict) else None
    if isinstance(rows, list):
        return len(rows)
    return 1


def _build_machine_distribution(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []

    candidates = [
        "Machine No.",
        "Machine NO",
        "Machine_No.",
        "Machine_No",
        "machine_no",
        "machine",
    ]
    machine_col = next((c for c in candidates if c in df.columns), None)
    if not machine_col:
        return []

    series = df[machine_col].dropna().astype(str).map(lambda x: x.strip())
    series = series[series != ""]
    if series.empty:
        return []

    counts = series.value_counts()
    return [
        {"name": str(name), "count": int(count)}
        for name, count in counts.items()
    ]


def _build_winder_distribution(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []

    p2_markers = [
        "Slitting date",
        "Slitting machine",
        "Striped Results",
        "Semi-finished No.",
    ]
    present_markers = [c for c in p2_markers if c in df.columns]
    if present_markers:
        df = df[df[present_markers].notna().any(axis=1)]
        if df.empty:
            return []

    candidates = [
        "Winder number",
        "Winder Number",
        "Winder No.",
        "Winder_No",
        "winder_number",
        "winder",
    ]
    winder_col = next((c for c in candidates if c in df.columns), None)
    if not winder_col:
        return []

    series = df[winder_col].dropna().astype(str).map(lambda x: x.strip())
    series = series[series != ""]
    if series.empty:
        return []

    counts = series.value_counts()
    return [
        {"name": str(name), "count": int(count)}
        for name, count in counts.items()
    ]


_LOT_WINDER_RE = re.compile(r"^\d{6,8}[-_]\d{2}[-_]\d+$")
_P3_PRODUCE_NO_RE = re.compile(r"^\d{8}[-_][A-Za-z0-9]+[-_].+[-_]\d+(?:[-_]dup\d+)?$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _looks_like_supported_product_id(pid: str) -> bool:
    s = str(pid or "").strip()
    if not s:
        return False
    if _LOT_WINDER_RE.fullmatch(s):
        return True
    if _P3_PRODUCE_NO_RE.fullmatch(s):
        return True
    if _UUID_RE.fullmatch(s):
        return True
    # minimal pragmatic fallback: contains separators and at least 3 segments
    segs = [x for x in re.split(r"[-_]", s) if x]
    return len(segs) >= 3


def _classify_unmatched_reason(
    *,
    requested_id: str,
    trace_candidates: list[str],
    artifact_row_count: int,
) -> tuple[str, str]:
    if not _looks_like_supported_product_id(requested_id):
        return ("invalid_format", "Input product_id format is not supported for artifact matching")
    if not trace_candidates:
        return ("no_trace", "No traceability tokens were found for this product_id")
    if artifact_row_count <= 0:
        return ("artifact_no_data", "Artifact has no rows for lookup")
    return ("artifact_no_data", "Artifact rows exist, but no matched token was found")


async def _resolve_trace_tokens_from_db(
    *,
    session: AsyncSession,
    tenant_id: Any,
    requested_ids: list[str],
    normalized_inputs: dict[str, list[str]],
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pid in requested_ids:
        candidates = [
            str(x).strip()
            for x in (normalized_inputs.get(pid, []) if isinstance(normalized_inputs, dict) else [])
            if str(x).strip()
        ]
        if not candidates:
            s = str(pid or "").strip()
            if s:
                candidates = [s]
        if not candidates:
            continue

        stmt = (
            select(P2ItemV2.trace_lot_no)
            .select_from(P3Record)
            .join(P3ItemV2, P3ItemV2.p3_record_id == P3Record.id)
            .join(
                P2Record,
                and_(
                    P2Record.tenant_id == P3Record.tenant_id,
                    P2Record.lot_no_norm == P3Record.lot_no_norm,
                    P2Record.winder_number == P3ItemV2.source_winder,
                ),
            )
            .join(
                P2ItemV2,
                and_(
                    P2ItemV2.p2_record_id == P2Record.id,
                    P2ItemV2.winder_number == P2Record.winder_number,
                ),
            )
            .where(
                P3Record.tenant_id == tenant_id,
                P3ItemV2.tenant_id == tenant_id,
                P2Record.tenant_id == tenant_id,
                P2ItemV2.tenant_id == tenant_id,
                P3ItemV2.source_winder.is_not(None),
                P2ItemV2.trace_lot_no.is_not(None),
                or_(
                    P3Record.product_id.in_(candidates),
                    P3ItemV2.product_id.in_(candidates),
                ),
            )
            .limit(50)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        seen: set[str] = set()
        tokens: list[str] = []
        for tok in rows:
            s = str(tok or "").strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            tokens.append(s)
        if tokens:
            out[pid] = tokens[:50]
    return out
