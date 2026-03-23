"""分析用 API 端點

提供追溯資料扁平化查詢（支援多 server 並發呼叫）

新規定：
1. 無全域狀態，每個請求獨立 session
2. 明確的 null/空陣列語義
3. Rate limiting 保護
"""

import logging
import math
import re
import time
from datetime import UTC, datetime
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.config.analytics_config import AnalyticsConfig
from app.core.database import get_db
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.services.traceability_flattener import TraceabilityFlattener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/analytics")

# ============ Rate Limiting（簡易實作）============
# 生產環境建議使用 Redis + slowapi
_rate_limit_store = {}  # {ip: [timestamp, ...]}


def check_rate_limit(request: Request, *, endpoint: str | None = None):
    """
    簡易 rate limiting 檢查

    限制：每 IP 每分鐘最多 RATE_LIMIT_REQUESTS_PER_MINUTE 次請求（支援多 server 並發）
    """
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - 60  # 60秒滾動窗口

    # 清理過期記錄並計算當前窗口內請求數
    if client_ip in _rate_limit_store:
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store[client_ip] if ts > window_start
        ]
        request_count = len(_rate_limit_store[client_ip])
    else:
        _rate_limit_store[client_ip] = []
        request_count = 0

    # 檢查是否超過限制
    if request_count >= AnalyticsConfig.RATE_LIMIT_REQUESTS_PER_MINUTE:
        oldest_ts = (
            min(_rate_limit_store.get(client_ip, []))
            if _rate_limit_store.get(client_ip)
            else current_time
        )
        retry_after_seconds = max(1, int(math.ceil((oldest_ts + 60) - current_time)))
        endpoint_tag = endpoint or request.url.path
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": (
                    f"Rate limit exceeded. Max {AnalyticsConfig.RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute."
                ),
                "endpoint": endpoint_tag,
                "retry_after_seconds": retry_after_seconds,
                "limit_per_minute": AnalyticsConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )

    # 記錄本次請求時間戳
    _rate_limit_store[client_ip].append(current_time)


# ============ API 端點 ============


@router.get("/flatten/monthly")
async def flatten_by_month(
    year: int = Query(..., ge=2010, le=2050, description="年份（2010-2050）"),
    month: int = Query(..., ge=1, le=12, description="月份（1-12）"),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
):
    """
    按月份查詢追溯資料（扁平化）

    **主要使用場景**：資料分析系統按月度批次拉取資料

    **新規定**：
    - 支援多 server 同時呼叫（無競態條件）
    - 資料庫內沒有的值填入 `null`
    - 空資料維持 `{"data": [], "count": 0}`

    **壓縮策略**：
    - ≥ 200 筆：自動 gzip 壓縮（Client 無感）
    - < 200 筆：不壓縮

    **效能**：
    - 典型查詢（800 筆）：約 2-3 秒
    - 壓縮後大小：約 300KB（原始 ~1MB）

    **範例**：
    ```bash
    curl "http://localhost:8000/api/v2/analytics/traceability/flatten/monthly?year=2025&month=9"
    ```

    **回應格式**：
    ```json
    {
      "data": [
        {
          "timestamp": "2025-09-01T08:00:00Z",
          "type": "P3",
          "location": "",
          "LOT NO.": "P3-20250901-001",
          "P1.Specification": "SPEC-001",
          "P1.Material": "PET",
          "Semi-finished Sheet Width(mm)": 1200.5,
          "Actual Temp_C1(°C)": 250.0,
          "Actual Temp_C2(°C)": null,
          ...
        }
      ],
      "count": 850,
      "has_data": true,
      "metadata": {
        "query_type": "monthly",
        "year": 2025,
        "month": 9,
        "compression": "gzip",
        "null_handling": "explicit"
      }
    }
    ```
    """
    # Rate limiting 檢查（支援並發）
    if request:
        check_rate_limit(request)

    # 初始化扁平化服務（每個請求獨立實例）
    flattener = TraceabilityFlattener(session)

    # 執行查詢（限制最大筆數）
    result = await flattener.flatten_by_month(
        year=year, month=month, limit=AnalyticsConfig.SINGLE_RESPONSE_MAX
    )

    # 檢查是否超過建議閥值
    if result["count"] > AnalyticsConfig.FORCE_PAGINATION_THRESHOLD:
        return JSONResponse(
            status_code=413,
            content={
                "error": "Payload too large",
                "message": f"Query returned {result['count']} records. "
                f"Maximum allowed: {AnalyticsConfig.FORCE_PAGINATION_THRESHOLD}. "
                f"Please use smaller date range or contact API administrator.",
                "suggestion": "Split into multiple months or use date range filters.",
            },
        )

    # 決定是否壓縮（Middleware 自動處理）
    if result["count"] >= AnalyticsConfig.AUTO_GZIP_THRESHOLD:
        result["metadata"]["compression"] = "gzip"

    return result


@router.get("/flatten")
async def flatten_by_product_ids(
    product_ids: list[str] = Query(
        ...,
        description="產品 ID 列表（逗號分隔）",
        max_items=AnalyticsConfig.MAX_PRODUCT_IDS_PER_REQUEST,
    ),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
):
    """
    按產品 ID 列表查詢追溯資料（扁平化）

    **使用場景**：針對特定產品進行追溯分析

    **新規定**：
    - 支援多 server 同時呼叫
    - 不存在的產品 ID 不會報錯，僅過濾結果
    - 空結果回傳 `{"data": [], "count": 0, "has_data": false}`

    **限制**：
    - 最多 500 個 product_id（防濫用）
    - 單次最多回傳 1500 筆

    **範例**：
    ```bash
    curl "http://localhost:8000/api/v2/analytics/traceability/flatten?product_ids=P3-20250901-001,P3-20250901-002"
    ```

    **回應格式**：同 `/flatten/monthly`
    """
    # Rate limiting
    if request:
        check_rate_limit(request)

    # 驗證 product_ids 數量
    if len(product_ids) > AnalyticsConfig.MAX_PRODUCT_IDS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many product IDs. Maximum: {AnalyticsConfig.MAX_PRODUCT_IDS_PER_REQUEST}",
        )

    # 初始化扁平化服務
    flattener = TraceabilityFlattener(session)

    # 執行查詢
    result = await flattener.flatten_by_product_ids(
        product_ids=product_ids, limit=AnalyticsConfig.SINGLE_RESPONSE_MAX
    )

    # 檢查閥值
    if result["count"] > AnalyticsConfig.FORCE_PAGINATION_THRESHOLD:
        return JSONResponse(
            status_code=413,
            content={
                "error": "Payload too large",
                "message": f"Query returned {result['count']} records. "
                f"Maximum allowed: {AnalyticsConfig.FORCE_PAGINATION_THRESHOLD}.",
                "suggestion": "Reduce number of product IDs or contact administrator.",
            },
        )

    # 決定壓縮策略
    if result["count"] >= AnalyticsConfig.AUTO_GZIP_THRESHOLD:
        result["metadata"]["compression"] = "gzip"

    return result


@router.get("/health")
async def health_check():
    """
    健康檢查端點（用於負載均衡器）

    **用途**：
    - 負載均衡器健康檢查
    - 監控系統確認 API 可用性

    **回應**：
    ```json
    {
      "status": "healthy",
      "timestamp": "2025-09-01T12:00:00Z",
      "config": {
        "max_records_per_request": 1500,
        "rate_limit_per_minute": 90,
        "auto_gzip_threshold": 200
      }
    }
    ```
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config": {
            "max_records_per_request": AnalyticsConfig.SINGLE_RESPONSE_MAX,
            "rate_limit_per_minute": AnalyticsConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "auto_gzip_threshold": AnalyticsConfig.AUTO_GZIP_THRESHOLD,
            "null_handling": "explicit",
            "empty_array_handling": "preserve",
        },
    }


class AnalyzeRequest(BaseModel):
    """Request payload for returning analysis JSON produced by an external analytics package."""

    start_date: str | None = Field(default=None, description="YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="YYYY-MM-DD")
    product_id: str | None = Field(default=None, description="客戶退貨產品編號")
    product_ids: list[str] = Field(default_factory=list, description="客訴 product_id 清單")
    stations: list[Literal["P2", "P3", "ALL"]] = Field(
        default_factory=list,
        description="站點篩選（作為 query 參數傳給分析 package）",
    )


class ArtifactListItem(BaseModel):
    key: str
    filename: str
    exists: bool
    size_bytes: int | None = None
    mtime_epoch: float | None = None


class ArtifactInputResolveResponse(BaseModel):
    requested: list[str]
    requested_count: int | None = None
    normalized_inputs: dict[str, list[str]] = Field(default_factory=dict)
    resolved: list[str]
    resolved_count: int | None = None
    unmatched: list[str]
    unmatched_count: int | None = None
    matches: dict[str, list[str]]
    match_diagnostics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    trace_tokens: dict[str, list[str]] = Field(default_factory=dict)
    trace_attempted_count: int | None = None
    trace_resolved_count: int | None = None
    unmatched_reason_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: float | None = None


class ArtifactSnapshotBucket(BaseModel):
    name: str
    count: int


class ArtifactUnifiedSnapshotResponse(BaseModel):
    artifact_key: str
    sample_count: int
    station_distribution: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    machine_distribution: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    top_features: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)


class ComplaintAnalysisRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, description="客訴 product_id 清單")
    include_basic_stats: bool = Field(
        default=True,
        description="是否包含基本統計",
    )
    include_outliers: bool = Field(
        default=True,
        description="是否包含異常檢測",
    )
    include_contribution: bool = Field(
        default=False,
        description="是否包含 PCA 貢獻度分析（較耗時）",
    )


class ComplaintAnalysisResponse(BaseModel):
    requested_ids: list[str] = Field(default_factory=list)
    mapping: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source_scope: dict[str, int] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    machine_distribution: list[dict[str, Any]] = Field(default_factory=list)
    winder_distribution: list[dict[str, Any]] = Field(default_factory=list)
    timing: dict[str, float] = Field(default_factory=dict)
    elapsed_ms: float | None = None


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


@router.post("/analyze")
async def analyze(
    payload: AnalyzeRequest,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    依照前端提供的篩選條件（含站點 P2/P3/ALL）準備 query 後內容，交由外部分析 package 產生分析結果 JSON。

    此端點從資料庫撈取資料，確保直方圖顯示的資料與 NG drill-down 查詢的資料來源一致。
    """

    # Rate limiting（支援並發）
    if request:
        check_rate_limit(request)

    # Use DB-based analysis to ensure data consistency with NG drill-down
    try:
        from app.services.analytics_external import (
            run_external_categorical_analysis_from_db,
        )

        product_ids = [str(pid).strip() for pid in (payload.product_ids or []) if str(pid or "").strip()]
        product_id = payload.product_id

        data = await run_external_categorical_analysis_from_db(
            db=session,
            tenant_id=current_tenant.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            product_id=product_id,
            product_ids=product_ids,
            stations=payload.stations,
        )
        return data
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=(
                "Analytics inputs not found. Please configure ANALYTICAL_FOUR_PATH / SEPTEMBER_V2_PATH "
                "(or provide ANALYTICS_CONFIG_PATH / ANALYTICS_MERGED_CSV_PATH)."
            ),
        )
    except Exception:
        logger.exception(
            "Analytics package execution failed (stations=%s, start_date=%s, end_date=%s, product_id=%s)",
            payload.stations,
            payload.start_date,
            payload.end_date,
            (payload.product_id[:32] + "...") if payload.product_id and len(payload.product_id) > 32 else payload.product_id,
        )
        raise HTTPException(
            status_code=500, detail="Analytics package execution failed"
        )


@router.get("/artifacts", response_model=list[ArtifactListItem])
async def list_artifacts(request: Request = None):
    """List available pre-generated analytics artifacts (JSON files).

    These artifacts are generated by the Analytical-Four pipeline and mounted into the backend container.
    The backend only serves allowlisted filenames to avoid path traversal/leaks.
    """

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts")

    from app.services.analytics_external import list_analytics_artifacts

    items = list_analytics_artifacts()
    return [
        ArtifactListItem(
            key=i.key,
            filename=i.filename,
            exists=i.exists,
            size_bytes=i.size_bytes,
            mtime_epoch=i.mtime_epoch,
        )
        for i in items
    ]


@router.get("/artifacts/{artifact_key}")
async def get_artifact(artifact_key: str, request: Request = None) -> Any:
    """Fetch one allowlisted analytics artifact.

    NOTE: This endpoint is kept for backwards compatibility.
    The frontend should prefer the list/detail endpoints which only return table/chart data.
    """

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts/{artifact_key}")

    try:
        from app.services.analytics_external import (
            get_analytics_artifact_list_view,
            parse_artifact_key,
        )

        key = parse_artifact_key(artifact_key)
        return get_analytics_artifact_list_view(key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analytics artifact not found. "
                "Please generate it with Analytical-Four and place it under SEPTEMBER_V2_PATH (or set ANALYTICS_ARTIFACTS_DIR)."
            ),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown analytics artifact key")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load analytics artifact")


@router.get("/artifacts/{artifact_key}/list")
async def get_artifact_list(
    artifact_key: str,
    product_ids: str | None = None,
    request: Request = None,
) -> Any:
    """Get compact list view for an artifact.

    Returns only the fields needed to render tables/charts.
    """

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts/{artifact_key}/list")

    try:
        from app.services.analytics_external import (
            _split_product_ids,
            get_analytics_artifact_list_view,
            parse_artifact_key,
        )

        key = parse_artifact_key(artifact_key)
        pids = _split_product_ids(product_ids)
        return get_analytics_artifact_list_view(key, product_ids=pids)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analytics artifact not found. "
                "Please generate it with Analytical-Four and place it under SEPTEMBER_V2_PATH (or set ANALYTICS_ARTIFACTS_DIR)."
            ),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown analytics artifact key")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load analytics artifact")


@router.get(
    "/artifacts/{artifact_key}/resolve-input",
    response_model=ArtifactInputResolveResponse,
)
async def resolve_artifact_input(
    artifact_key: str,
    product_ids: str | None = None,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> ArtifactInputResolveResponse:
    """Resolve user inputs into artifact-effective filter tokens."""
    t0 = time.perf_counter()

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts/{artifact_key}/resolve-input")

    try:
        from app.services.analytics_external import (
            _split_product_ids,
            parse_artifact_key,
            resolve_artifact_product_inputs,
        )

        key = parse_artifact_key(artifact_key)
        pids = _split_product_ids(product_ids)
        base = resolve_artifact_product_inputs(key, product_ids=pids)
        base_normalized = (
            base.get("normalized_inputs", {})
            if isinstance(base.get("normalized_inputs", {}), dict)
            else {}
        )

        trace_tokens: dict[str, list[str]] = {}
        trace_token_source: dict[str, str] = {}
        unresolved = [x for x in base.get("unmatched", []) if isinstance(x, str)]
        trace_attempted_count = len(unresolved)
        db_trace_tokens = await _resolve_trace_tokens_from_db(
            session=session,
            tenant_id=current_tenant.id,
            requested_ids=unresolved,
            normalized_inputs=base_normalized,
        )
        if unresolved:
            from app.api.traceability import trace_by_product_id

            for pid in unresolved:
                if db_trace_tokens.get(pid):
                    trace_tokens[pid] = list(db_trace_tokens.get(pid, []))
                    trace_token_source[pid] = "db_trace_lot"
                    continue
                try:
                    trace_payload = await trace_by_product_id(
                        product_id=pid,
                        db=session,
                        current_tenant=current_tenant,
                    )
                    tokens = _extract_trace_tokens(trace_payload)
                    if tokens:
                        trace_tokens[pid] = tokens
                        trace_token_source[pid] = "traceability"
                except HTTPException:
                    trace_tokens[pid] = []
                except Exception:
                    trace_tokens[pid] = []

        if not trace_tokens:
            artifact_row_count = int(base.get("artifact_row_count") or 0)
            base_normalized = (
                base_normalized
            )
            base_diag = (
                base.get("match_diagnostics", {})
                if isinstance(base.get("match_diagnostics", {}), dict)
                else {}
            )
            base_unmatched = (
                base.get("unmatched", [])
                if isinstance(base.get("unmatched", []), list)
                else []
            )
            enriched_diag: dict[str, dict[str, Any]] = {}
            for pid in pids:
                pid_base_diag = base_diag.get(pid) if isinstance(base_diag.get(pid), dict) else {}
                reason_code = ""
                reason_message = ""
                if pid in base_unmatched:
                    reason_code, reason_message = _classify_unmatched_reason(
                        requested_id=pid,
                        trace_candidates=[],
                        artifact_row_count=artifact_row_count,
                    )
                enriched_diag[pid] = {
                    "candidate_count": int(pid_base_diag.get("candidate_count") or len(base_normalized.get(pid, []))),
                    "matched_by": pid_base_diag.get("matched_by", []) if isinstance(pid_base_diag.get("matched_by", []), list) else [],
                    "reason_code": reason_code,
                    "reason_message": reason_message,
                    "trace_source": trace_token_source.get(pid, ""),
                }

            resolved_list = [
                str(x).strip()
                for x in (
                    base.get("resolved", [])
                    if isinstance(base.get("resolved", []), list)
                    else []
                )
                if str(x).strip()
            ]
            unmatched_list = [str(x).strip() for x in base_unmatched if str(x).strip()]
            reason_counts: dict[str, int] = {}
            for pid in unmatched_list:
                code = str((enriched_diag.get(pid) or {}).get("reason_code") or "").strip()
                if not code:
                    continue
                reason_counts[code] = int(reason_counts.get(code, 0)) + 1

            return ArtifactInputResolveResponse(
                requested=pids,
                requested_count=len(pids),
                normalized_inputs={pid: list(base_normalized.get(pid, [])) for pid in pids},
                resolved=resolved_list,
                resolved_count=len(resolved_list),
                unmatched=unmatched_list,
                unmatched_count=len(unmatched_list),
                matches={
                    pid: [str(x).strip() for x in ((base.get("matches", {}) or {}).get(pid, []) if isinstance((base.get("matches", {}) or {}).get(pid, []), list) else []) if str(x).strip()][:20]
                    for pid in pids
                },
                match_diagnostics=enriched_diag,
                trace_tokens={},
                trace_attempted_count=trace_attempted_count,
                trace_resolved_count=0,
                unmatched_reason_counts=reason_counts,
                elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
            )

        # Re-run matching by using trace-derived candidates and map hits back to requested IDs.
        token_order: list[str] = []
        token_seen: set[str] = set()
        for pid in unresolved:
            for tok in trace_tokens.get(pid, []):
                tk = tok.lower()
                if tk in token_seen:
                    continue
                token_seen.add(tk)
                token_order.append(tok)

        token_result = (
            resolve_artifact_product_inputs(key, product_ids=token_order)
            if token_order
            else {"matches": {}, "resolved": []}
        )
        token_matches = token_result.get("matches", {}) if isinstance(token_result, dict) else {}
        artifact_row_count = int(base.get("artifact_row_count") or 0)
        base_normalized = (
            base_normalized
        )
        base_diag = (
            base.get("match_diagnostics", {})
            if isinstance(base.get("match_diagnostics", {}), dict)
            else {}
        )

        merged_matches: dict[str, list[str]] = {}
        merged_resolved: list[str] = []
        merged_resolved_seen: set[str] = set()
        for x in base.get("resolved", []):
            s = str(x).strip()
            if not s:
                continue
            k = s.lower()
            if k in merged_resolved_seen:
                continue
            merged_resolved_seen.add(k)
            merged_resolved.append(s)

        base_matches = base.get("matches", {}) if isinstance(base.get("matches", {}), dict) else {}
        for pid in pids:
            direct = base_matches.get(pid, []) if isinstance(base_matches, dict) else []
            hits: list[str] = []
            hit_seen: set[str] = set()
            for h in direct:
                hs = str(h).strip()
                if not hs:
                    continue
                hk = hs.lower()
                if hk in hit_seen:
                    continue
                hit_seen.add(hk)
                hits.append(hs)
            if not hits:
                for tok in trace_tokens.get(pid, []):
                    for h in token_matches.get(tok, []):
                        hs = str(h).strip()
                        if not hs:
                            continue
                        hk = hs.lower()
                        if hk in hit_seen:
                            continue
                        hit_seen.add(hk)
                        hits.append(hs)
            for h in hits:
                hk = h.lower()
                if hk not in merged_resolved_seen:
                    merged_resolved_seen.add(hk)
                    merged_resolved.append(h)
            merged_matches[pid] = hits[:20]

        merged_unmatched = [pid for pid in pids if not merged_matches.get(pid)]
        merged_diag: dict[str, dict[str, Any]] = {}
        for pid in pids:
            pid_base_diag = base_diag.get(pid) if isinstance(base_diag.get(pid), dict) else {}
            matched_by_raw = pid_base_diag.get("matched_by", [])
            matched_by = [str(x).strip() for x in matched_by_raw if str(x).strip()] if isinstance(matched_by_raw, list) else []
            if not matched_by and merged_matches.get(pid):
                # Fallback path: direct match was empty, but trace token mapping resolved hits.
                matched_by = trace_tokens.get(pid, [])[:20]
            reason_code = ""
            reason_message = ""
            if pid in merged_unmatched:
                reason_code, reason_message = _classify_unmatched_reason(
                    requested_id=pid,
                    trace_candidates=trace_tokens.get(pid, []),
                    artifact_row_count=artifact_row_count,
                )
            merged_diag[pid] = {
                "candidate_count": int(pid_base_diag.get("candidate_count") or len(base_normalized.get(pid, []))),
                "matched_by": matched_by[:20],
                "reason_code": reason_code,
                "reason_message": reason_message,
                "trace_source": trace_token_source.get(pid, ""),
            }

        trace_resolved_count = 0
        for pid in unresolved:
            if merged_matches.get(pid):
                trace_resolved_count += 1

        reason_counts: dict[str, int] = {}
        for pid in merged_unmatched:
            code = str((merged_diag.get(pid) or {}).get("reason_code") or "").strip()
            if not code:
                continue
            reason_counts[code] = int(reason_counts.get(code, 0)) + 1

        return ArtifactInputResolveResponse(
            requested=pids,
            requested_count=len(pids),
            normalized_inputs={pid: list(base_normalized.get(pid, [])) for pid in pids},
            resolved=merged_resolved[:100],
            resolved_count=len(merged_resolved[:100]),
            unmatched=merged_unmatched,
            unmatched_count=len(merged_unmatched),
            matches=merged_matches,
            match_diagnostics=merged_diag,
            trace_tokens=trace_tokens,
            trace_attempted_count=trace_attempted_count,
            trace_resolved_count=trace_resolved_count,
            unmatched_reason_counts=reason_counts,
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analytics artifact not found. "
                "Please generate it with Analytical-Four and place it under SEPTEMBER_V2_PATH (or set ANALYTICS_ARTIFACTS_DIR)."
            ),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown analytics artifact key")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to resolve analytics artifact input")


@router.get(
    "/artifacts/{artifact_key}/snapshot",
    response_model=ArtifactUnifiedSnapshotResponse,
)
async def get_artifact_unified_snapshot(
    artifact_key: str,
    product_ids: str | None = None,
    request: Request = None,
) -> ArtifactUnifiedSnapshotResponse:
    """Get a unified aggregate snapshot for cross-view rendering."""

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts/{artifact_key}/snapshot")

    try:
        from app.services.analytics_external import (
            _split_product_ids,
            get_analytics_artifact_unified_snapshot,
            parse_artifact_key,
        )

        key = parse_artifact_key(artifact_key)
        pids = _split_product_ids(product_ids)
        data = get_analytics_artifact_unified_snapshot(key, product_ids=pids)
        return ArtifactUnifiedSnapshotResponse(**data)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analytics artifact not found. "
                "Please generate it with Analytical-Four and place it under SEPTEMBER_V2_PATH (or set ANALYTICS_ARTIFACTS_DIR)."
            ),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown analytics artifact key")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build analytics unified snapshot")


class RealtimeAnalysisRequest(BaseModel):
    """即時 Analytical-Four 分析請求"""
    station: str = Field(default="P2", description="分析站點 (P1/P2/P3)")
    start_date: str | None = Field(default=None, description="開始日期 (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="結束日期 (YYYY-MM-DD)")
    include_basic_stats: bool = Field(default=True, description="包含基本統計")
    include_outliers: bool = Field(default=True, description="包含異常檢測")
    include_contribution: bool = Field(default=False, description="包含 PCA 貢獻度分析（較耗時）")


@router.post(
    "/realtime-analysis",
    response_model=dict[str, Any],
    summary="即時 Analytical-Four 分析",
)
async def run_realtime_analysis(
    payload: RealtimeAnalysisRequest,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """
    即時執行 Analytical-Four 分析
    
    從 DB 撈取資料，直接呼叫 Analytical-Four 函式進行分析。
    這個端點不依賴預生成的 JSON 檔案，可即時取得分析結果。
    
    支援的分析：
    - basic_statistics: 基本統計（mean, std, min, max, Q1, Q2, Q3）
    - outliers: 異常檢測（IQR / 3sigma）
    - contribution: PCA 貢獻度分析（T²/SPE）
    """
    import time
    t0 = time.perf_counter()
    
    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/realtime-analysis")
    
    try:
        from app.services.analytical_four_adapter import run_unified_analysis_from_db
        
        result = await run_unified_analysis_from_db(
            db=session,
            tenant_id=current_tenant.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            station=payload.station,
            include_basic_stats=payload.include_basic_stats,
            include_outliers=payload.include_outliers,
            include_contribution=payload.include_contribution,
        )
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["elapsed_ms"] = round(elapsed_ms, 2)
        
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Realtime analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Realtime analysis failed: {e}")


@router.post(
    "/complaint-analysis",
    response_model=ComplaintAnalysisResponse,
)
async def analyze_complaint_products(
    payload: ComplaintAnalysisRequest,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> ComplaintAnalysisResponse:
    """One-shot complaint analysis: trace by product_id -> DB unified analysis -> results."""

    t0 = time.perf_counter()
    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/complaint-analysis")

    try:
        from app.api.traceability import trace_by_product_id
        from app.services.analytical_four_adapter import run_unified_analysis_from_db
        from app.services.analytics_data_fetcher import (
            _normalize_product_id,
            fetch_merged_by_product_ids,
        )
        from app.services.analytics_external import write_complain_csv_from_df

        requested_ids: list[str] = []
        seen: set[str] = set()
        for raw in payload.product_ids:
            s = str(raw or "").strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            requested_ids.append(s)

        normalized_lookup: dict[str, str] = {}
        for pid in requested_ids:
            normalized = _normalize_product_id(pid) or pid
            normalized_lookup[pid] = normalized

        t_trace = time.perf_counter()
        mapping: dict[str, dict[str, Any]] = {}
        resolved_count = 0
        for pid in requested_ids:
            normalized_pid = normalized_lookup.get(pid, pid)
            try:
                trace_payload = await trace_by_product_id(
                    product_id=normalized_pid,
                    db=session,
                    current_tenant=current_tenant,
                )
            except Exception:
                mapping[pid] = {
                    "matched_stage": "trace_error",
                    "missing_stages": ["P3", "P2", "P1"],
                    "trace_status": {"p3": False, "p2": False, "p1": False},
                }
                continue

            p1 = trace_payload.get("p1") if isinstance(trace_payload, dict) else None
            p2 = trace_payload.get("p2") if isinstance(trace_payload, dict) else None
            p3 = trace_payload.get("p3") if isinstance(trace_payload, dict) else None

            status = {
                "p1": isinstance(p1, dict),
                "p2": isinstance(p2, dict),
                "p3": isinstance(p3, dict),
            }
            if any(status.values()):
                resolved_count += 1

            missing_stages: list[str] = []
            if not status["p3"]:
                missing_stages.append("P3")
            if not status["p2"]:
                missing_stages.append("P2")
            if not status["p1"]:
                missing_stages.append("P1")

            mapping[pid] = {
                "matched_stage": "trace_ok" if any(status.values()) else "trace_missing",
                "missing_stages": missing_stages,
                "trace_status": status,
            }

        trace_ms = (time.perf_counter() - t_trace) * 1000

        t_scope = time.perf_counter()
        df = await fetch_merged_by_product_ids(
            db=session,
            tenant_id=current_tenant.id,
            product_ids=requested_ids,
        )
        scope_ms = (time.perf_counter() - t_scope) * 1000

        try:
            if df is not None and not df.empty:
                write_complain_csv_from_df(df)
        except Exception:
            logger.exception("Failed to write complaint CSV")

        machine_distribution = _build_machine_distribution(df)
        winder_distribution = _build_winder_distribution(df)

        source_scope = {
            "requested_count": len(requested_ids),
            "resolved_count": resolved_count,
            "merged_rows": int(len(df.index)) if df is not None else 0,
        }

        t_analysis = time.perf_counter()
        analysis: dict[str, Any] = {}
        for station in ("P1", "P2", "P3"):
            analysis[station] = await run_unified_analysis_from_db(
                db=session,
                tenant_id=current_tenant.id,
                product_ids=requested_ids,
                start_date=None,
                end_date=None,
                station=station,
                include_basic_stats=payload.include_basic_stats,
                include_outliers=payload.include_outliers,
                include_contribution=payload.include_contribution,
            )
        analysis_ms = (time.perf_counter() - t_analysis) * 1000

        total_ms = (time.perf_counter() - t0) * 1000

        return ComplaintAnalysisResponse(
            requested_ids=requested_ids,
            mapping=mapping,
            source_scope=source_scope,
            analysis=analysis,
            machine_distribution=machine_distribution,
            winder_distribution=winder_distribution,
            timing={
                "trace_ms": round(trace_ms, 2),
                "scope_ms": round(scope_ms, 2),
                "analysis_ms": round(analysis_ms, 2),
                "total_ms": round(total_ms, 2),
            },
            elapsed_ms=round(total_ms, 2),
        )
    except Exception:
        logger.exception("complaint-analysis failed")
        raise HTTPException(status_code=500, detail="Failed to build complaint analysis payload")


class ExtractionAnalysisRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, description="product_id 清單")
    start_date: str | None = Field(default=None, description="開始日期 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="結束日期 YYYY-MM-DD")
    station: str = Field(default="P2", description="站點代碼 (P1/P2/P3)")


class ExtractionAnalysisResponse(BaseModel):
    station: str
    boundary_count: dict[str, int] = Field(default_factory=dict)
    spe_score: dict[str, float] = Field(default_factory=dict)
    t2_score: dict[str, float] = Field(default_factory=dict)
    final_raw_score: dict[str, float] = Field(default_factory=dict)
    features_used: list[str] = Field(default_factory=list)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: float | None = None


@router.post(
    "/extraction-analysis",
    response_model=ExtractionAnalysisResponse,
)
async def run_extraction_analysis(
    payload: ExtractionAnalysisRequest,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> ExtractionAnalysisResponse:
    """
    Extraction analysis: IQR boundary + PCA T²/SPE → final_raw_score per feature.
    用於識別最影響品質的特徵。
    """
    t0 = time.perf_counter()
    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/extraction-analysis")

    try:
        from app.services.analytical_four_adapter import run_extraction_analysis_from_db

        result = await run_extraction_analysis_from_db(
            db=session,
            tenant_id=current_tenant.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            station=payload.station.upper(),
            product_ids=payload.product_ids if payload.product_ids else None,
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not result or "error" in result:
            return ExtractionAnalysisResponse(
                station=payload.station.upper(),
                elapsed_ms=elapsed_ms,
            )

        return ExtractionAnalysisResponse(
            station=result.get("station", payload.station.upper()),
            boundary_count=result.get("boundary_count", {}),
            spe_score=result.get("spe_score", {}),
            t2_score=result.get("t2_score", {}),
            final_raw_score=result.get("final_raw_score", {}),
            features_used=result.get("features_used", []),
            sample_counts=result.get("sample_counts", {}),
            elapsed_ms=elapsed_ms,
        )

    except Exception:
        logger.exception("extraction-analysis failed")
        raise HTTPException(status_code=500, detail="Failed to run extraction analysis")


@router.get("/artifacts/{artifact_key}/detail/{item_id}")
async def get_artifact_detail(
    artifact_key: str,
    item_id: str,
    request: Request = None,
) -> Any:
    """Get compact detail view for a single item.

    Returns only the fields needed to render tables/charts.
    """

    if request:
        check_rate_limit(request, endpoint="/api/v2/analytics/artifacts/{artifact_key}/detail/{item_id}")

    try:
        from app.services.analytics_external import (
            get_analytics_artifact_detail_view,
            parse_artifact_key,
        )

        key = parse_artifact_key(artifact_key)
        return get_analytics_artifact_detail_view(key, item_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analytics artifact not found. "
                "Please generate it with Analytical-Four and place it under SEPTEMBER_V2_PATH (or set ANALYTICS_ARTIFACTS_DIR)."
            ),
        )
    except KeyError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail="Artifact item not found")
        raise HTTPException(status_code=404, detail="Unknown analytics artifact key")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load analytics artifact")
