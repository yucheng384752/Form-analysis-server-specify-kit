"""Analysis routes for analytics API (analyze, realtime-analysis, complaint-analysis, extraction-analysis)."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.models.core.tenant import Tenant

from .helpers import (
    _build_machine_distribution,
    _build_winder_distribution,
    check_rate_limit,
)
from .schemas import (
    AnalyzeRequest,
    ComplaintAnalysisRequest,
    ComplaintAnalysisResponse,
    ExtractionAnalysisRequest,
    ExtractionAnalysisResponse,
    RealtimeAnalysisRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
        from app.services.analytics_external import run_external_categorical_analysis_from_db

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
        from app.services.analytics_data_fetcher import fetch_merged_by_product_ids, _normalize_product_id
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
