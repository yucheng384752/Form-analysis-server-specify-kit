from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

logger = logging.getLogger(__name__)

StationCode = Literal["P2", "P3", "ALL"]

ArtifactKey = Literal[
    "serialized_events",
    "aggregated_diagnostics",
    "rag_results",
    "llm_reports",
    "weighted_contributions",
]

_ARTIFACT_FILE_MAP: dict[ArtifactKey, str] = {
    "serialized_events": "ut_serialized_results.json",
    "aggregated_diagnostics": "ut_aggregated_diagnostics.json",
    "rag_results": "ut_event_rag_results.json",
    "llm_reports": "ut_gemini_output_all.json",
    "weighted_contributions": "ut_weighted_contributions.json",
}


@dataclass(frozen=True)
class AnalyticsExternalPaths:
    analytical_four_root: Path
    september_v2_root: Path
    config_path: Path
    merged_csv_path: Path


@dataclass(frozen=True)
class AnalyticsArtifactInfo:
    key: ArtifactKey
    filename: str
    exists: bool
    size_bytes: int | None
    mtime_epoch: float | None


def _default_desktop() -> Path:
    # Works on Windows/macOS/Linux if the user has a Desktop folder.
    return Path.home() / "Desktop"


def resolve_external_paths() -> AnalyticsExternalPaths:
    """Resolve paths for Analytical-Four and september_v2.

    Priority:
    1) Explicit env vars
       - ANALYTICAL_FOUR_PATH
       - SEPTEMBER_V2_PATH
       - ANALYTICS_CONFIG_PATH
       - ANALYTICS_MERGED_CSV_PATH
    2) Conventional Desktop locations used in this workspace.
    """

    desktop = _default_desktop()

    analytical_four_root = Path(
        os.environ.get(
            "ANALYTICAL_FOUR_PATH",
            str(desktop / "Analytical" / "Analytical-Four"),
        )
    ).resolve()

    september_v2_root = Path(
        os.environ.get(
            "SEPTEMBER_V2_PATH",
            str(desktop / "september_v2"),
        )
    ).resolve()

    config_path = Path(
        os.environ.get(
            "ANALYTICS_CONFIG_PATH",
            str(september_v2_root / "config" / "ut_config_v3.json"),
        )
    ).resolve()

    merged_csv_path = Path(
        os.environ.get(
            "ANALYTICS_MERGED_CSV_PATH",
            str(september_v2_root / "merged_p1_p2_p3.csv"),
        )
    ).resolve()

    return AnalyticsExternalPaths(
        analytical_four_root=analytical_four_root,
        september_v2_root=september_v2_root,
        config_path=config_path,
        merged_csv_path=merged_csv_path,
    )


def resolve_artifacts_dir(*, paths: AnalyticsExternalPaths | None = None) -> Path:
    """Resolve where pre-generated Analytical-Four JSON artifacts live.

    Default: use september_v2 root (mounted into the backend container).
    Override with ANALYTICS_ARTIFACTS_DIR.

    Note: We only read files from this directory via allowlisted filenames.
    """

    if paths is None:
        paths = resolve_external_paths()

    raw = os.environ.get("ANALYTICS_ARTIFACTS_DIR")
    if raw and str(raw).strip():
        return Path(str(raw)).expanduser().resolve()
    return paths.september_v2_root


def list_analytics_artifacts(*, artifacts_dir: Path | None = None) -> list[AnalyticsArtifactInfo]:
    paths = resolve_external_paths()
    base = artifacts_dir or resolve_artifacts_dir(paths=paths)

    out: list[AnalyticsArtifactInfo] = []
    for key, filename in _ARTIFACT_FILE_MAP.items():
        p = (base / filename).resolve()
        # Safety: ensure file stays within base dir
        try:
            p.relative_to(base)
        except Exception:
            exists = False
            out.append(
                AnalyticsArtifactInfo(
                    key=key,
                    filename=filename,
                    exists=exists,
                    size_bytes=None,
                    mtime_epoch=None,
                )
            )
            continue

        if p.exists() and p.is_file():
            st = p.stat()
            out.append(
                AnalyticsArtifactInfo(
                    key=key,
                    filename=filename,
                    exists=True,
                    size_bytes=int(st.st_size),
                    mtime_epoch=float(st.st_mtime),
                )
            )
        else:
            out.append(
                AnalyticsArtifactInfo(
                    key=key,
                    filename=filename,
                    exists=False,
                    size_bytes=None,
                    mtime_epoch=None,
                )
            )
    return out


def load_analytics_artifact(
    key: ArtifactKey,
    *,
    artifacts_dir: Path | None = None,
) -> Any:
    paths = resolve_external_paths()
    base = artifacts_dir or resolve_artifacts_dir(paths=paths)
    filename = _ARTIFACT_FILE_MAP[key]
    p = (base / filename).resolve()
    try:
        p.relative_to(base)
    except Exception:
        # Defensive: should not happen due to allowlist.
        raise FileNotFoundError("Analytics artifact not found")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError("Analytics artifact not found")
    return _load_json(p)


def parse_artifact_key(value: str) -> ArtifactKey:
    v = str(value or "").strip()
    if not v:
        raise KeyError("Unknown analytics artifact key")
    if v in _ARTIFACT_FILE_MAP:
        return v  # type: ignore[return-value]
    raise KeyError("Unknown analytics artifact key")


def _split_product_ids(value: str | None) -> list[str]:
    if not value:
        return []
    raw = re.split(r"[\s,，;；]+", str(value))
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        s = str(x).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= 50:
            break
    return out


def _matches_any_product_id(*haystacks: str, product_ids: list[str]) -> bool:
    if not product_ids:
        return True
    combined = " ".join([h for h in haystacks if h]).lower()
    needles = [p.lower() for p in product_ids]
    return any(pid in combined for pid in needles)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_number(value: Any) -> float:
    try:
        n = float(value)
        return n if pd.notna(n) else 0.0
    except Exception:
        return 0.0


def get_analytics_artifact_list_view(
    key: ArtifactKey,
    *,
    product_ids: list[str] | None = None,
    artifacts_dir: Path | None = None,
) -> Any:
    """Return a compact list view suitable for tables.

    This intentionally avoids sending the entire raw artifact JSON to the frontend.
    """

    pids = product_ids or []
    raw = load_analytics_artifact(key, artifacts_dir=artifacts_dir)

    if key == "serialized_events":
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            event_id = _to_str(item.get("event_id")).strip() or _to_str(item.get("id")).strip()
            event_date = item.get("event_date")
            ctx = item.get("context") if isinstance(item.get("context"), dict) else {}
            produce_no = _to_str(ctx.get("Produce_No.") or ctx.get("produce_no") or ctx.get("LOT NO.") or ctx.get("lot_no")).strip()
            winder = _to_str(ctx.get("Winder number") or ctx.get("Winder") or "").strip()
            slitting = _to_str(ctx.get("Slitting machine") or ctx.get("Slitting") or "").strip()

            detected = item.get("detected_by_IQR") if isinstance(item.get("detected_by_IQR"), dict) else {}
            iqr_count = len(detected)
            ranked = item.get("ranked_features") if isinstance(item.get("ranked_features"), dict) else {}
            t2 = ranked.get("T2_feature") if isinstance(ranked.get("T2_feature"), list) else []
            spe = ranked.get("SPE_feature") if isinstance(ranked.get("SPE_feature"), list) else []

            if not event_id:
                continue
            if not _matches_any_product_id(event_id, produce_no, product_ids=pids):
                continue

            out.append(
                {
                    "event_id": event_id,
                    "event_date": event_date,
                    "produce_no": produce_no,
                    "winder": winder,
                    "slitting": slitting,
                    "iqr_count": int(iqr_count),
                    "t2_count": int(len(t2)),
                    "spe_count": int(len(spe)),
                }
            )
        return out

    if key == "aggregated_diagnostics":
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            summary_id = _to_str(item.get("summary_id") or item.get("id") or "").strip()
            analysis_dimension = _to_str(item.get("analysis_dimension") or "").strip()
            sample_count = int(_safe_number(item.get("sample_count")))
            ctx = item.get("context") if isinstance(item.get("context"), dict) else {}
            ctx_preview = " / ".join([f"{k}: {_to_str(v)}" for k, v in list(ctx.items())[:4]])
            core_features = item.get("core_features") if isinstance(item.get("core_features"), list) else []
            event_ids = item.get("event_ids") if isinstance(item.get("event_ids"), list) else []

            if not summary_id:
                continue
            if not _matches_any_product_id(summary_id, analysis_dimension, ctx_preview, product_ids=pids):
                continue

            out.append(
                {
                    "summary_id": summary_id,
                    "analysis_dimension": analysis_dimension,
                    "sample_count": sample_count,
                    "context_preview": ctx_preview,
                    "core_feature_count": int(len(core_features)),
                    "event_count": int(len(event_ids)),
                }
            )
        return out

    if key == "weighted_contributions":
        if not isinstance(raw, dict):
            return []
        out: list[dict[str, Any]] = []
        for k, v in raw.items():
            event_id = _to_str(k).strip()
            if not event_id:
                continue
            if not _matches_any_product_id(event_id, product_ids=pids):
                continue

            row = v if isinstance(v, dict) else {}
            x_t2 = float(_safe_number(row.get("x_T2")))
            x_spe = float(_safe_number(row.get("x_SPE")))
            t2 = row.get("T2_feature") if isinstance(row.get("T2_feature"), list) else []
            spe = row.get("SPE_feature") if isinstance(row.get("SPE_feature"), list) else []
            t2_top = _to_str(t2[0].get("feature")) if t2 and isinstance(t2[0], dict) else ""
            spe_top = _to_str(spe[0].get("feature")) if spe and isinstance(spe[0], dict) else ""
            out.append(
                {
                    "id": event_id,
                    "x_T2": x_t2,
                    "x_SPE": x_spe,
                    "t2_top": t2_top,
                    "spe_top": spe_top,
                }
            )
        out.sort(key=lambda r: max(float(r.get("x_T2") or 0), float(r.get("x_SPE") or 0)), reverse=True)
        return out

    if key == "rag_results":
        if not isinstance(raw, dict):
            return []
        out: list[dict[str, Any]] = []
        for event_id, value in raw.items():
            eid = _to_str(event_id).strip()
            if not eid:
                continue
            if not _matches_any_product_id(eid, product_ids=pids):
                continue
            feature_map = value if isinstance(value, dict) else {}
            feature_count = len(feature_map)
            sop_count = 0
            for vv in feature_map.values():
                if isinstance(vv, list):
                    sop_count += len(vv)
            out.append(
                {
                    "event_id": eid,
                    "feature_count": int(feature_count),
                    "sop_count": int(sop_count),
                }
            )
        out.sort(key=lambda r: (int(r.get("sop_count") or 0), int(r.get("feature_count") or 0)), reverse=True)
        return out

    if key == "llm_reports":
        # Accept either:
        # 1) a single report dict with event_id
        # 2) a list of report dicts
        # 3) a mapping event_id -> report dict
        def _summarize_report(report: dict[str, Any]) -> dict[str, Any] | None:
            event_id = _to_str(report.get("event_id") or report.get("id") or "").strip()
            if not event_id:
                return None
            event_time = report.get("event_time")
            main = report.get("main_anomalies") if isinstance(report.get("main_anomalies"), dict) else {}
            total = int(_safe_number(main.get("total_anomalies")))
            return {"event_id": event_id, "event_time": event_time, "total_anomalies": total}

        rows: list[dict[str, Any]] = []
        if isinstance(raw, list):
            for it in raw:
                if isinstance(it, dict):
                    s = _summarize_report(it)
                    if s:
                        rows.append(s)
        elif isinstance(raw, dict):
            if "event_id" in raw:
                s = _summarize_report(raw)
                if s:
                    rows.append(s)
            else:
                for _, it in raw.items():
                    if isinstance(it, dict):
                        s = _summarize_report(it)
                        if s:
                            rows.append(s)

        if pids:
            rows = [r for r in rows if _matches_any_product_id(_to_str(r.get("event_id")), product_ids=pids)]
        rows.sort(key=lambda r: int(r.get("total_anomalies") or 0), reverse=True)
        return rows

    return []


def get_analytics_artifact_detail_view(
    key: ArtifactKey,
    item_id: str,
    *,
    artifacts_dir: Path | None = None,
) -> Any:
    """Return a compact detail view suitable for tables/charts only."""

    raw = load_analytics_artifact(key, artifacts_dir=artifacts_dir)
    want_id = str(item_id or "").strip()
    if not want_id:
        raise KeyError("Missing artifact item id")

    if key == "serialized_events":
        if not isinstance(raw, list):
            raise KeyError("Event not found")
        found: dict[str, Any] | None = None
        for item in raw:
            if not isinstance(item, dict):
                continue
            eid = _to_str(item.get("event_id") or item.get("id") or "").strip()
            if eid == want_id:
                found = item
                break
        if not found:
            raise KeyError("Event not found")

        ctx = found.get("context") if isinstance(found.get("context"), dict) else {}
        produce_no = _to_str(ctx.get("Produce_No.") or ctx.get("produce_no") or ctx.get("LOT NO.") or ctx.get("lot_no")).strip()
        winder = _to_str(ctx.get("Winder number") or ctx.get("Winder") or "").strip()
        slitting = _to_str(ctx.get("Slitting machine") or ctx.get("Slitting") or "").strip()

        detected = found.get("detected_by_IQR") if isinstance(found.get("detected_by_IQR"), dict) else {}
        iqr_features = sorted([_to_str(k).strip() for k in detected.keys() if _to_str(k).strip()])

        ranked = found.get("ranked_features") if isinstance(found.get("ranked_features"), dict) else {}
        t2 = ranked.get("T2_feature") if isinstance(ranked.get("T2_feature"), list) else []
        spe = ranked.get("SPE_feature") if isinstance(ranked.get("SPE_feature"), list) else []

        def _top_features(items: list[Any]) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for it in items[:20]:
                if not isinstance(it, dict):
                    continue
                feat = _to_str(it.get("feature") or "").strip()
                if not feat:
                    continue
                out.append(
                    {
                        "feature": feat,
                        "final_score": float(_safe_number(it.get("final_score"))),
                        "final_rank": int(_safe_number(it.get("final_rank"))),
                    }
                )
            return out

        return {
            "event_id": want_id,
            "event_date": found.get("event_date"),
            "produce_no": produce_no,
            "winder": winder,
            "slitting": slitting,
            "iqr_features": iqr_features,
            "t2_features": _top_features(t2),
            "spe_features": _top_features(spe),
        }

    if key == "aggregated_diagnostics":
        if not isinstance(raw, list):
            raise KeyError("Summary not found")
        found: dict[str, Any] | None = None
        for item in raw:
            if not isinstance(item, dict):
                continue
            sid = _to_str(item.get("summary_id") or item.get("id") or "").strip()
            if sid == want_id:
                found = item
                break
        if not found:
            raise KeyError("Summary not found")

        core = found.get("core_features") if isinstance(found.get("core_features"), list) else []
        rows: list[dict[str, Any]] = []
        for it in core:
            if not isinstance(it, dict):
                continue
            feature = _to_str(it.get("feature") or "").strip()
            if not feature:
                continue
            evidence = it.get("evidence") if isinstance(it.get("evidence"), dict) else {}
            iqr = evidence.get("IQR") if isinstance(evidence.get("IQR"), (int, float, str, dict)) else evidence.get("iqr")

            def _freq(v: Any) -> int:
                if v is None:
                    return 0
                if isinstance(v, (int, float)):
                    return int(v) if pd.notna(v) else 0
                if isinstance(v, str):
                    try:
                        return int(float(v))
                    except Exception:
                        return 0
                if isinstance(v, dict):
                    if isinstance(v.get("frequency"), (int, float)):
                        return int(v.get("frequency"))
                    if isinstance(v.get("count"), (int, float)):
                        return int(v.get("count"))
                return 0

            iqr_f = _freq(iqr)
            ranked = evidence.get("ranked_features") if isinstance(evidence.get("ranked_features"), dict) else (
                evidence.get("rank") if isinstance(evidence.get("rank"), dict) else {}
            )
            t2_f = _freq(ranked.get("T2_feature") or ranked.get("t2_feature") or ranked.get("T2") or ranked.get("t2"))
            spe_f = _freq(ranked.get("SPE_feature") or ranked.get("spe_feature") or ranked.get("SPE") or ranked.get("spe"))
            total = iqr_f + t2_f + spe_f
            rows.append({"feature": feature, "iqr_freq": iqr_f, "t2_freq": t2_f, "spe_freq": spe_f, "total": total})

        rows.sort(key=lambda r: (int(r.get("total") or 0), int(r.get("iqr_freq") or 0), str(r.get("feature") or "")), reverse=True)

        ctx = found.get("context") if isinstance(found.get("context"), dict) else {}
        ctx_preview = " / ".join([f"{k}: {_to_str(v)}" for k, v in list(ctx.items())[:8]])
        event_ids = found.get("event_ids") if isinstance(found.get("event_ids"), list) else []

        return {
            "summary_id": want_id,
            "analysis_dimension": _to_str(found.get("analysis_dimension") or "").strip(),
            "sample_count": int(_safe_number(found.get("sample_count"))),
            "context_preview": ctx_preview,
            "event_count": int(len(event_ids)),
            "core_features": rows,
        }

    if key == "weighted_contributions":
        if not isinstance(raw, dict):
            raise KeyError("Item not found")
        row = raw.get(want_id)
        if not isinstance(row, dict):
            raise KeyError("Item not found")

        def _top(items: Any) -> list[dict[str, Any]]:
            if not isinstance(items, list):
                return []
            out: list[dict[str, Any]] = []
            for it in items[:20]:
                if not isinstance(it, dict):
                    continue
                feat = _to_str(it.get("feature") or "").strip()
                if not feat:
                    continue
                out.append(
                    {
                        "feature": feat,
                        "final_score": float(_safe_number(it.get("final_score"))),
                        "final_rank": int(_safe_number(it.get("final_rank"))),
                    }
                )
            return out

        return {
            "id": want_id,
            "x_T2": float(_safe_number(row.get("x_T2"))),
            "x_SPE": float(_safe_number(row.get("x_SPE"))),
            "t2_features": _top(row.get("T2_feature")),
            "spe_features": _top(row.get("SPE_feature")),
        }

    if key == "rag_results":
        import csv
        import io

        if not isinstance(raw, dict):
            raise KeyError("Item not found")
        feature_map = raw.get(want_id)
        if not isinstance(feature_map, dict):
            raise KeyError("Item not found")

        def _parse_line(line: str) -> dict[str, Any] | None:
            s = str(line or "").strip()
            if not s:
                return None
            try:
                parts = next(csv.reader(io.StringIO(s)))
            except Exception:
                parts = [p.strip() for p in s.split(",")]
            # Expected: code, station, feature, kind, problem, action, section
            code = parts[0] if len(parts) > 0 else ""
            station = parts[1] if len(parts) > 1 else ""
            kind = parts[3] if len(parts) > 3 else ""
            problem = parts[4] if len(parts) > 4 else ""
            action = parts[5] if len(parts) > 5 else ""
            section = parts[6] if len(parts) > 6 else ""
            return {
                "code": str(code or "").strip(),
                "station": str(station or "").strip(),
                "kind": str(kind or "").strip(),
                "problem": str(problem or "").strip(),
                "action": str(action or "").strip(),
                "section": str(section or "").strip(),
            }

        out_features: dict[str, list[dict[str, Any]]] = {}
        for feature, lines in feature_map.items():
            if not isinstance(lines, list):
                continue
            rows: list[dict[str, Any]] = []
            for raw_line in lines[:200]:
                parsed = _parse_line(_to_str(raw_line))
                if parsed:
                    rows.append(parsed)
            if rows:
                out_features[_to_str(feature)] = rows

        return {"event_id": want_id, "features": out_features}

    if key == "llm_reports":
        # Resolve report object by event_id from various shapes.
        report: dict[str, Any] | None = None
        if isinstance(raw, list):
            for it in raw:
                if isinstance(it, dict) and _to_str(it.get("event_id") or it.get("id") or "").strip() == want_id:
                    report = it
                    break
        elif isinstance(raw, dict):
            if "event_id" in raw:
                if _to_str(raw.get("event_id")).strip() == want_id:
                    report = raw
            elif want_id in raw and isinstance(raw.get(want_id), dict):
                report = raw.get(want_id)  # type: ignore[assignment]
            else:
                for _, it in raw.items():
                    if isinstance(it, dict) and _to_str(it.get("event_id") or it.get("id") or "").strip() == want_id:
                        report = it
                        break

        if not report:
            raise KeyError("Report not found")

        main = report.get("main_anomalies") if isinstance(report.get("main_anomalies"), dict) else {}
        total = int(_safe_number(main.get("total_anomalies")))
        by_station = main.get("by_station") if isinstance(main.get("by_station"), dict) else {}

        stations_out: list[dict[str, Any]] = []
        for station, payload in by_station.items():
            if not isinstance(payload, dict):
                continue
            anomalies = payload.get("anomalies") if isinstance(payload.get("anomalies"), list) else []
            rows: list[dict[str, Any]] = []
            for it in anomalies[:200]:
                if not isinstance(it, dict):
                    continue
                rows.append(
                    {
                        "feature_name": _to_str(it.get("feature_name") or "").strip(),
                        "detection_method": _to_str(it.get("detection_method") or "").strip(),
                        "problem_description": _to_str(it.get("problem_description") or "").strip(),
                    }
                )
            if rows:
                stations_out.append({"station": _to_str(station), "anomalies": rows})

        stations_out.sort(key=lambda r: len(r.get("anomalies") or []), reverse=True)
        return {
            "event_id": want_id,
            "event_time": report.get("event_time"),
            "total_anomalies": total,
            "by_station": stations_out,
        }

    raise KeyError("Unsupported artifact")


def _ensure_analytical_four_importable(root: Path) -> None:
    # The repo is not installed as a wheel in this backend; add to sys.path.
    if not root.exists():
        raise FileNotFoundError(f"Analytical-Four not found: {root}")

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _station_codes_from_request(
    stations: list[StationCode],
) -> list[Literal["P2", "P3"]]:
    if not stations:
        return ["P2"]
    if "ALL" in stations:
        return ["P2", "P3"]
    out: list[Literal["P2", "P3"]] = []
    if "P2" in stations:
        out.append("P2")
    if "P3" in stations:
        out.append("P3")
    return out


_LOT_WINDER_PRODUCT_ID_RE = re.compile(r"^\d+_\d+_\d+$")

# P3 Produce_No. values in merged CSV look like:
#   20250902_P21_238-3_302
#   20250902_P21_238-3_302_dup9
_P3_PRODUCE_NO_PRODUCT_ID_RE = re.compile(r"^\d{8}_[A-Za-z0-9]+_.+_\d+(?:_dup\d+)?$")


def _is_lot_winder_product_id(product_id: str | None) -> bool:
    """Return True when product_id looks like lot_no + winder number.

    Examples: "2507173_02_1", "2507173_01_1".

    Business rule: these IDs are only meaningful for P2 analysis.
    """

    if not product_id:
        return False
    pid = str(product_id).strip()
    if not pid:
        return False
    return _LOT_WINDER_PRODUCT_ID_RE.fullmatch(pid) is not None


def _is_p3_produce_no_product_id(product_id: str | None) -> bool:
    if not product_id:
        return False
    pid = str(product_id).strip()
    if not pid:
        return False
    return _P3_PRODUCE_NO_PRODUCT_ID_RE.fullmatch(pid) is not None


def _normalize_station_selection_for_product_id(
    stations: list[StationCode],
    product_id: str | None,
) -> list[StationCode]:
    """Apply business routing rules between product_id and station selection."""

    if _is_lot_winder_product_id(product_id):
        # When product_id is lot+winder style, only P2 is valid.
        return ["P2"]

    if _is_p3_produce_no_product_id(product_id):
        # When product_id matches P3 Produce_No. style, only P3 is meaningful.
        return ["P3"]
    return stations


def _parse_date_to_yyyymmdd(value: Any) -> int | None:
    if value is None:
        return None

    # Pandas NaN
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    s = str(value).strip()
    if not s:
        return None

    # Handle float-like strings that come from CSV dtype inference.
    # Example: "20250901.0" should be treated as "20250901".
    if "." in s:
        left, right = s.split(".", 1)
        if left.strip().isdigit() and (not right or set(right.strip()) <= {"0"}):
            s = left.strip()

    # Examples in merged CSV:
    # - "250717" (YYMMDD)
    # - "20250807_16_00" (YYYYMMDD_..)
    # - "20250901" (YYYYMMDD)
    if "_" in s:
        s = s.split("_", 1)[0]

    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8:
        try:
            return int(digits)
        except ValueError:
            return None

    if len(digits) == 6:
        # Assume 20YYMMDD (matches this dataset naming)
        try:
            yy = int(digits[:2])
            mm = int(digits[2:4])
            dd = int(digits[4:6])
            return (2000 + yy) * 10000 + mm * 100 + dd
        except ValueError:
            return None

    return None


def _parse_ymd_to_yyyymmdd(ymd: str) -> int | None:
    s = str(ymd).strip()
    if not s:
        return None
    try:
        parts = s.split("-")
        if len(parts) != 3:
            return None
        y = int(parts[0])
        m = int(parts[1])
        d = int(parts[2])
        return y * 10000 + m * 100 + d
    except ValueError:
        return None


def _pick_date_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Production Date",
        "Slitting date",
        "Production Date_x",
        "Production Date_y",
    ]

    best_col: str | None = None
    best_count = 0
    for c in candidates:
        if c not in df.columns:
            continue
        parsed = df[c].map(_parse_date_to_yyyymmdd)
        count = int(parsed.notna().sum())
        if count > best_count:
            best_col = c
            best_count = count

    # If nothing is parsable, skip date filtering entirely.
    return best_col if best_count > 0 else None


def _pick_date_column_for_station(
    df: pd.DataFrame, station: Literal["P2", "P3"]
) -> str | None:
    """Pick the most appropriate date column for a station.

    Business rule:
    - P3 should prefer production-date-like columns when present and parsable.
    - P2 should prefer slitting-date-like columns when present and parsable.
    """

    def _best_from_candidates(candidates: list[str]) -> tuple[str | None, int]:
        best_col: str | None = None
        best_count = 0
        for c in candidates:
            if c not in df.columns:
                continue
            parsed = df[c].map(_parse_date_to_yyyymmdd)
            count = int(parsed.notna().sum())
            if count > best_count:
                best_col = c
                best_count = count
        return best_col, best_count

    production_like = [
        "Production Date",
        "Production Date_x",
        "Production Date_y",
    ]
    slitting_like = [
        "Slitting date",
    ]

    if station == "P3":
        prod_col, prod_count = _best_from_candidates(production_like)
        if prod_col and prod_count > 0:
            return prod_col
        slit_col, slit_count = _best_from_candidates(slitting_like)
        return slit_col if slit_col and slit_count > 0 else None

    # P2
    slit_col, slit_count = _best_from_candidates(slitting_like)
    if slit_col and slit_count > 0:
        return slit_col
    prod_col, prod_count = _best_from_candidates(production_like)
    return prod_col if prod_col and prod_count > 0 else None


def _normalize_binary_target(value: Any) -> str:
    """Normalize common binary target representations to string "0"/"1"."""

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        if value == 0 or value == 0.0:
            return "0"
        if value == 1 or value == 1.0:
            return "1"

    s = str(value).strip()
    if not s:
        return s

    upper = s.upper()
    if upper in {"OK", "PASS", "TRUE", "Y", "YES", "1"}:
        return "1"
    if upper in {"NG", "FAIL", "FALSE", "N", "NO", "0"}:
        return "0"

    # Handle float-ish strings like "1.0" or "0.0".
    try:
        f = float(s)
    except ValueError:
        return s
    if f == 0.0:
        return "0"
    if f == 1.0:
        return "1"
    return s


def _filter_df(
    df: pd.DataFrame,
    *,
    start_date: str | None,
    end_date: str | None,
    product_id: str | None,
    station: Literal["P2", "P3"] | None = None,
) -> pd.DataFrame:
    out = df

    date_col = (
        _pick_date_column_for_station(out, station)
        if station
        else _pick_date_column(out)
    )
    start_i = _parse_ymd_to_yyyymmdd(start_date) if start_date else None
    end_i = _parse_ymd_to_yyyymmdd(end_date) if end_date else None

    if date_col and (start_i or end_i):
        date_series = out[date_col].map(_parse_date_to_yyyymmdd)
        mask = pd.Series(True, index=out.index)
        if start_i:
            mask &= date_series.ge(start_i)
        if end_i:
            mask &= date_series.le(end_i)
        out = out.loc[mask]

    if product_id:
        pid = str(product_id).strip()
        if pid:
            candidates = [
                "Semi_produce No.",
                "Produce_No.",
                "LOT NO.",
                "Semi-finished No.",
                "Lot_No.",
            ]
            present = [c for c in candidates if c in out.columns]
            if present:
                mask_pid = pd.Series(False, index=out.index)
                for c in present:
                    s = out[c].astype(str).str.strip()
                    mask_pid |= s.eq(pid)
                    # Some P3 Produce_No. values in merged CSV include a "_dupN" suffix.
                    # If the user provides the base product id (without _dup), include those rows too.
                    if _is_p3_produce_no_product_id(pid):
                        mask_pid |= s.str.startswith(pid + "_dup")
                out = out.loc[mask_pid]

    return out


def _extract_station_config(
    config: dict[str, Any], station: Literal["P2", "P3"]
) -> tuple[str, list[str]]:
    # config schema: { feature: { P2: { target, categorical: {..} } } }
    feature = config.get("feature") or {}
    station_cfg = feature.get(station) or {}
    target_col = str(station_cfg.get("target") or "").strip()
    if not target_col:
        raise ValueError(f"Missing target column for {station} in config")

    categorical: dict[str, Any] = station_cfg.get("categorical") or {}
    cols: list[str] = []
    for _, col_list in categorical.items():
        if isinstance(col_list, list):
            cols.extend([str(x) for x in col_list if str(x).strip()])

    # Some configs use the same field multiple times across groups.
    cols = _flatten_unique(cols)
    if not cols:
        raise ValueError(f"Missing categorical columns for {station} in config")

    return target_col, cols


def run_external_categorical_analysis(
    *,
    start_date: str | None,
    end_date: str | None,
    product_id: str | None,
    stations: list[StationCode],
) -> dict[str, Any]:
    """Run Analytical-Four categorical analysis and return JSON-ready dict.

    Output matches the frontend's expected structure:
    {"FeatureName": {"Value": {"0": ratio0, "1": ratio1, "total_count": ..., "count_0": ...}}, ...}

    When both P2/P3 are requested, feature keys are prefixed with station code to avoid collisions.
    """

    stations = _normalize_station_selection_for_product_id(stations, product_id)

    paths = resolve_external_paths()

    if not paths.config_path.exists():
        raise FileNotFoundError(f"Analytics config not found: {paths.config_path}")
    if not paths.merged_csv_path.exists():
        raise FileNotFoundError(f"Merged CSV not found: {paths.merged_csv_path}")

    _ensure_analytical_four_importable(paths.analytical_four_root)

    # Import only the lightweight analyzer (pandas-based) to avoid pulling heavy deps.
    from analysis.descriptive.categorical_analyzer import (
        CategoricalAnalyzer,  # type: ignore
    )

    config = _load_json(paths.config_path)

    df = pd.read_csv(paths.merged_csv_path)

    analyzer = CategoricalAnalyzer()
    combined: dict[str, Any] = {}

    for station in _station_codes_from_request(stations):
        target_col, categorical_cols = _extract_station_config(config, station)

        station_df = _filter_df(
            df,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            station=station,
        )

        if target_col not in station_df.columns:
            # If the merged CSV doesn't include this station's target, just skip.
            continue

        present_categorical_cols = [c for c in categorical_cols if c in station_df.columns]
        missing_categorical_cols = [c for c in categorical_cols if c not in station_df.columns]
        if missing_categorical_cols:
            logger.warning(
                "Analytics categorical columns missing in merged CSV for %s: %s",
                station,
                missing_categorical_cols,
            )
        if not present_categorical_cols:
            # Nothing to analyze for this station.
            continue

        # Only keep rows with meaningful target (avoid NaN -> "nan").
        station_df = station_df[station_df[target_col].notna()].copy()
        if station_df.empty:
            continue

        # Analytical-Four has had API variations across versions.
        # Prefer the newer explicit method name if present.
        if hasattr(analyzer, "analyze_target_distribution_by_category"):
            result = analyzer.analyze_target_distribution_by_category(
                data=station_df,
                target_col=target_col,
                categorical_cols=present_categorical_cols,
                normalize=True,
            )
        else:
            # Backward compatibility with older Analytical-Four versions.
            result = analyzer.analyze(  # type: ignore[attr-defined]
                data=station_df,
                target_col=target_col,
                categorical_cols=present_categorical_cols,
                normalize=True,
            )

        # Prefix keys if needed.
        if len(_station_codes_from_request(stations)) > 1:
            for feature_name, buckets in result.items():
                combined[f"{station}.{feature_name}"] = buckets
        else:
            combined.update(result)

    return combined
