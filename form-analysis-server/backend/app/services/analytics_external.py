from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

StationCode = Literal["P2", "P3", "ALL"]


@dataclass(frozen=True)
class AnalyticsExternalPaths:
    analytical_four_root: Path
    september_v2_root: Path
    config_path: Path
    merged_csv_path: Path


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

        # Only keep rows with meaningful target (avoid NaN -> "nan").
        station_df = station_df[station_df[target_col].notna()].copy()
        if station_df.empty:
            continue

        result = analyzer.analyze(
            data=station_df,
            target_col=target_col,
            categorical_cols=categorical_cols,
            normalize=True,
        )

        # Prefix keys if needed.
        if len(_station_codes_from_request(stations)) > 1:
            for feature_name, buckets in result.items():
                combined[f"{station}.{feature_name}"] = buckets
        else:
            combined.update(result)

    return combined
