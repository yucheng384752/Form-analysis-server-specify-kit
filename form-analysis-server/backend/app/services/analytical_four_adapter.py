"""
Analytical-Four Adapter

將 DB 資料轉換為 Analytical-Four 期望的格式，並呼叫分析函式。
提供即時分析功能，無需依賴預生成的 JSON 檔案。

設計原則：
- 不修改 Analytical-Four 原始碼
- 統一欄位映射邏輯
- 支援從 product_id 觸發的客訴分析流程
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pandas as pd

from app.services.analytics_external import (
    _ensure_analytical_four_importable,
    _load_json,
    resolve_external_paths,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ==============================================================================
# Config Loader
# ==============================================================================


def load_analytical_config(config_path: Path | None = None) -> dict[str, Any]:
    """載入 Analytical-Four 設定檔"""
    if config_path is None:
        paths = resolve_external_paths()
        config_path = paths.config_path
    
    if not config_path.exists():
        raise FileNotFoundError(f"Analytics config not found: {config_path}")
    
    return _load_json(config_path)


def get_station_config(
    config: dict[str, Any],
    station: str,
) -> tuple[str, list[str], list[str], str]:
    """
    從 config 提取站點設定
    
    Returns:
        tuple: (target_col, numerical_cols, categorical_cols, id_col)
    """
    station = station.upper()
    feature_cfg = config.get("feature", {}).get(station, {})
    
    target_col = str(feature_cfg.get("target") or "").strip()
    id_col = str(feature_cfg.get("id") or "").strip()
    
    numerical_cols = [str(x).strip() for x in feature_cfg.get("numerical", []) if str(x).strip()]
    
    categorical_cfg = feature_cfg.get("categorical", {})
    categorical_cols: list[str] = []
    for group_name, col_list in categorical_cfg.items():
        if isinstance(col_list, list):
            categorical_cols.extend([str(x).strip() for x in col_list if str(x).strip()])
    
    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_categorical: list[str] = []
    for c in categorical_cols:
        if c not in seen:
            seen.add(c)
            unique_categorical.append(c)
    
    return target_col, numerical_cols, unique_categorical, id_col


# ==============================================================================
# DataFrame Validation
# ==============================================================================


def validate_and_prepare_df(
    df: pd.DataFrame,
    required_cols: list[str],
    numerical_cols: list[str],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    驗證 DataFrame 並準備分析所需欄位
    
    Returns:
        tuple: (prepared_df, present_cols, missing_cols)
    """
    present_cols = [c for c in required_cols if c in df.columns]
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if missing_cols:
        logger.warning("Missing columns in DataFrame: %s", missing_cols)
    
    # Select only present columns
    if present_cols:
        prepared_df = df[present_cols].copy()
    else:
        prepared_df = df.copy()
    
    # Convert numerical columns to numeric
    for col in numerical_cols:
        if col in prepared_df.columns:
            prepared_df[col] = pd.to_numeric(prepared_df[col], errors='coerce')
    
    return prepared_df, present_cols, missing_cols


# ==============================================================================
# Basic Statistics (即時計算)
# ==============================================================================


async def run_basic_statistics_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    從 DB 撈取資料並執行 Analytical-Four basic_statistics
    
    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        station: 站點代碼 (P1/P2/P3)
        product_ids: 客訴 product_id 列表（優先使用，若提供則忽略日期範圍）
        
    Returns:
        dict: 基本統計結果，格式為 {column_name: StatisticsSummary}
    """
    from app.services.analytics_data_fetcher import (
        fetch_merged_by_product_ids,
        fetch_merged_p1p2p3_from_db,
    )
    
    paths = resolve_external_paths()
    _ensure_analytical_four_importable(paths.analytical_four_root)
    
    # Import Analytical-Four components
    from analysis.descriptive.statistical_calculator import BasicStatistics
    
    # Load config
    config = load_analytical_config()
    target_col, numerical_cols, categorical_cols, id_col = get_station_config(config, station)
    
    # Fetch data from DB (product_ids 優先於日期範圍)
    if product_ids:
        df = await fetch_merged_by_product_ids(
            db=db,
            tenant_id=tenant_id,
            product_ids=product_ids,
        )
    else:
        df = await fetch_merged_p1p2p3_from_db(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            stations=[station],
        )
    
    if df.empty:
        logger.warning("No data found for basic statistics: tenant=%s, station=%s", tenant_id, station)
        return {}
    
    # Validate and prepare DataFrame
    prepared_df, present_cols, missing_cols = validate_and_prepare_df(
        df,
        numerical_cols,
        numerical_cols,
    )
    
    present_numerical = [c for c in numerical_cols if c in present_cols]
    if not present_numerical:
        logger.warning("No numerical columns available for basic statistics")
        return {}
    
    # Calculate basic statistics
    stats = BasicStatistics()
    results: dict[str, Any] = {}
    
    for col in present_numerical:
        col_data = prepared_df[col].dropna().tolist()
        if not col_data:
            continue
        
        try:
            stats_result = stats.calculate_summary(col_data)
            if is_dataclass(stats_result):
                results[col] = asdict(stats_result)
            else:
                results[col] = stats_result
        except Exception as e:
            logger.warning("Failed to calculate statistics for column %s: %s", col, e)
            continue
    
    logger.info(
        "Basic statistics calculated: tenant=%s, station=%s, columns=%d",
        tenant_id,
        station,
        len(results),
    )
    
    return results


# ==============================================================================
# Compare Outliers (即時異常檢測)
# ==============================================================================


async def run_compare_outliers_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    method: str | None = None,
    baseline: dict[str, Any] | None = None,
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    從 DB 撈取資料並執行 Analytical-Four compare_outliers
    
    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        station: 站點代碼 (P1/P2/P3)
        method: 異常檢測方法 (IQR Thresholds / 3sigma / minmax)
        baseline: 基準線設定 (可選，若無則使用 config 中的 diagnostic baseline)
        product_ids: 客訴 product_id 列表（優先使用）
        
    Returns:
        dict: 異常檢測結果
    """
    from app.services.analytics_data_fetcher import (
        fetch_merged_by_product_ids,
        fetch_merged_p1p2p3_from_db,
    )
    
    paths = resolve_external_paths()
    _ensure_analytical_four_importable(paths.analytical_four_root)
    
    # Import Analytical-Four components
    from analysis.diagnostic.comparator import Comparator
    
    # Load config
    config = load_analytical_config()
    target_col, numerical_cols, categorical_cols, id_col = get_station_config(config, station)
    
    # Use method from config if not specified
    if method is None:
        method = config.get("method", "IQR Thresholds")
    
    # Load baseline if not provided
    if baseline is None:
        diagnostic_paths = config.get("data_source", {}).get("diagnostic", [])
        if diagnostic_paths:
            baseline_path = paths.september_v2_root.parent / diagnostic_paths[0]
            if baseline_path.exists():
                baseline = _load_json(baseline_path)
            else:
                logger.warning("Baseline file not found: %s", baseline_path)
    
    # Fetch data from DB (product_ids 優先於日期範圍)
    if product_ids:
        df = await fetch_merged_by_product_ids(
            db=db,
            tenant_id=tenant_id,
            product_ids=product_ids,
        )
    else:
        df = await fetch_merged_p1p2p3_from_db(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            stations=[station],
        )
    
    if df.empty:
        logger.warning("No data found for compare outliers: tenant=%s, station=%s", tenant_id, station)
        return {}
    
    # Validate and prepare DataFrame
    prepared_df, present_cols, missing_cols = validate_and_prepare_df(
        df,
        numerical_cols + [id_col] if id_col else numerical_cols,
        numerical_cols,
    )
    
    present_numerical = [c for c in numerical_cols if c in present_cols]
    if not present_numerical:
        logger.warning("No numerical columns available for compare outliers")
        return {}
    
    # First calculate basic statistics
    stats_results = await run_basic_statistics_from_db(
        db=db,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        station=station,
        product_ids=product_ids,
    )
    
    if not stats_results:
        logger.warning("No statistics available for compare outliers")
        return {}
    
    # Run compare outliers
    comparator = Comparator()
    
    try:
        result = comparator.check_outlier(
            data=prepared_df,
            stats=stats_results,
            base_line=baseline,
            method=method,
            id_feature=id_col,
            numerical_features=present_numerical,
        )
        
        logger.info(
            "Compare outliers completed: tenant=%s, station=%s, method=%s, outliers=%d",
            tenant_id,
            station,
            method,
            len(result) if isinstance(result, (list, dict)) else 0,
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to run compare outliers: %s", e)
        return {"error": str(e)}


# ==============================================================================
# Contribution Analysis (PCA 貢獻度分析)
# ==============================================================================


async def run_contribution_analysis_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    從 DB 撈取資料並執行 Analytical-Four contribution_analysis (PCA 貢獻度分析)
    
    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        station: 站點代碼 (P1/P2/P3)
        product_ids: 客訴 product_id 列表（優先使用）
        
    Returns:
        dict: PCA 貢獻度分析結果，包含：
            - explained_variance: 各主成分解釋的變異數
            - loadings: 特徵負荷量
            - sample_diagnostics: 樣本 T²/SPE 診斷統計量
    """
    from app.services.analytics_data_fetcher import (
        fetch_merged_by_product_ids,
        fetch_merged_p1p2p3_from_db,
    )
    
    paths = resolve_external_paths()
    _ensure_analytical_four_importable(paths.analytical_four_root)
    
    # Import Analytical-Four components
    from analysis.diagnostic.contribution import ContributionAnalyzer
    
    # Load config
    config = load_analytical_config()
    target_col, numerical_cols, categorical_cols, id_col = get_station_config(config, station)
    
    # Fetch data from DB (product_ids 優先於日期範圍)
    if product_ids:
        df = await fetch_merged_by_product_ids(
            db=db,
            tenant_id=tenant_id,
            product_ids=product_ids,
        )
    else:
        df = await fetch_merged_p1p2p3_from_db(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            stations=[station],
        )
    
    if df.empty:
        logger.warning("No data found for contribution analysis: tenant=%s, station=%s", tenant_id, station)
        return {}
    
    # Validate and prepare DataFrame
    all_required = numerical_cols + ([id_col] if id_col else [])
    prepared_df, present_cols, missing_cols = validate_and_prepare_df(
        df,
        all_required,
        numerical_cols,
    )
    
    present_numerical = [c for c in numerical_cols if c in present_cols]
    if len(present_numerical) < 2:
        logger.warning("Need at least 2 numerical columns for PCA, got %d", len(present_numerical))
        return {}
    
    # Prepare sample ID list
    if id_col and id_col in present_cols:
        sample_id_list = prepared_df[id_col].astype(str).tolist()
    else:
        sample_id_list = [f"row_{i}" for i in prepared_df.index]
    
    # Prepare numerical-only DataFrame
    num_df = prepared_df[present_numerical].dropna()
    
    if len(num_df) < 10:
        logger.warning("Insufficient samples for PCA: %d (need at least 10)", len(num_df))
        return {}
    
    # Use first 80% as baseline, last 20% as analysis target
    # (In production, baseline should come from a separate dataset)
    split_idx = int(len(num_df) * 0.8)
    baseline_df = num_df.iloc[:split_idx]
    analysis_df = num_df.iloc[split_idx:]
    analysis_ids = sample_id_list[split_idx:] if len(sample_id_list) > split_idx else sample_id_list[-len(analysis_df):]
    
    if len(baseline_df) < 5 or len(analysis_df) < 1:
        logger.warning("Insufficient data for PCA split: baseline=%d, analysis=%d", len(baseline_df), len(analysis_df))
        return {}
    
    # Run contribution analysis
    analyzer = ContributionAnalyzer()
    alpha = 0.05
    
    try:
        # 1. Fit scaler on baseline
        scaler = analyzer.fit_scaler(baseline_df)
        std_baseline_df = analyzer.transform_with_scaler(baseline_df, scaler)
        std_analysis_df = analyzer.transform_with_scaler(analysis_df, scaler)
        
        # 2. PCA on baseline
        pca, transformed, cum_var, sel_var = analyzer.PCA(std_baseline_df)
        
        # 3. Calculate loadings
        loadings_dict_list = analyzer.loadings(std_baseline_df, pca)
        
        # 4. Calculate control limits
        t2_ucl = analyzer.calculate_t2_limit(std_baseline_df, pca, alpha=alpha)
        spe_ucl = analyzer.calculate_spe_limit(std_baseline_df, pca, alpha=alpha)
        
        # 5. Calculate T² and SPE for analysis samples
        t2, t2_feature, t2_feature_score, t2_feature_rank = analyzer.hotelling_t2(std_analysis_df, pca)
        spe, spe_feature, spe_feature_score, spe_feature_rank = analyzer.SPE(std_analysis_df, pca)
        
        # 6. Build sample diagnostics
        sample_diagnostics = analyzer.construct_sample_diagnostics(
            analysis_ids,
            std_analysis_df,
            t2,
            t2_ucl,
            t2_feature,
            t2_feature_score,
            t2_feature_rank,
            spe,
            spe_ucl,
            spe_feature,
            spe_feature_score,
            spe_feature_rank,
        )
        
        result = {
            "explained_variance": sel_var.tolist() if hasattr(sel_var, 'tolist') else list(sel_var),
            "cumulative_variance": cum_var.tolist() if hasattr(cum_var, 'tolist') else list(cum_var),
            "n_components": int(pca.n_components_),
            "loadings": loadings_dict_list,
            "sample_diagnostics": sample_diagnostics,
            "features_used": present_numerical,
            "control_limits": {
                "t2_ucl": float(t2_ucl),
                "spe_ucl": float(spe_ucl),
                "alpha": alpha,
            },
            "sample_counts": {
                "baseline": len(baseline_df),
                "analysis": len(analysis_df),
            },
        }
        
        logger.info(
            "Contribution analysis completed: tenant=%s, station=%s, n_components=%d, samples=%d",
            tenant_id,
            station,
            pca.n_components_,
            len(sample_diagnostics),
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to run contribution analysis: %s", e)
        return {"error": str(e)}


# ==============================================================================
# Serialization (序列化診斷事件)
# ==============================================================================


async def run_serialization_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    product_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    從 DB 撈取資料並執行 Analytical-Four serialization
    
    這個函式整合多個分析結果，產生序列化的診斷事件列表。
    
    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        station: 站點代碼 (P1/P2/P3)
        product_ids: 客訴 product_id 列表（優先使用）
        
    Returns:
        list[dict]: 序列化的診斷事件列表
    """
    from app.services.analytics_data_fetcher import (
        fetch_merged_by_product_ids,
        fetch_merged_p1p2p3_from_db,
    )
    
    paths = resolve_external_paths()
    _ensure_analytical_four_importable(paths.analytical_four_root)
    
    # Import Analytical-Four components
    from serializer import SerializerFactory
    
    # Load config
    config = load_analytical_config()
    target_col, numerical_cols, categorical_cols, id_col = get_station_config(config, station)
    serializer_type = config.get("serializer", "UT")
    
    # Fetch data (product_ids 優先於日期範圍)
    if product_ids:
        df = await fetch_merged_by_product_ids(
            db=db,
            tenant_id=tenant_id,
            product_ids=product_ids,
        )
    else:
        df = await fetch_merged_p1p2p3_from_db(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            stations=[station],
        )
    
    if df.empty:
        logger.warning("No data found for serialization: tenant=%s, station=%s", tenant_id, station)
        return []
    
    # Run prerequisite analyses
    compare_result = await run_compare_outliers_from_db(
        db=db,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        station=station,
        product_ids=product_ids,
    )
    
    contribution_result = await run_contribution_analysis_from_db(
        db=db,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        station=station,
        product_ids=product_ids,
    )
    
    if not compare_result or not contribution_result:
        logger.warning("Prerequisite analyses failed for serialization")
        return []
    
    # Prepare inputs
    sample_diagnostics = contribution_result.get("sample_diagnostics", {})
    
    try:
        serializer_instance = SerializerFactory.create_serializer(serializer_type)
        
        serialized_results = serializer_instance.serialization_file(
            csv_data=df,
            iqr_data=compare_result,
            spe_t2_data=sample_diagnostics,
            id_col=id_col,
        )
        
        logger.info(
            "Serialization completed: tenant=%s, station=%s, events=%d",
            tenant_id,
            station,
            len(serialized_results),
        )
        
        return serialized_results
        
    except Exception as e:
        logger.exception("Failed to run serialization: %s", e)
        return []


# ==============================================================================
# Unified Analysis Entry Point
# ==============================================================================


async def run_unified_analysis_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    product_ids: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    include_basic_stats: bool = True,
    include_outliers: bool = True,
    include_contribution: bool = False,
) -> dict[str, Any]:
    """
    統一分析入口點：從 DB 即時執行多種分析
    
    這是給客訴分析流程使用的主要函式，整合多個 Analytical-Four 分析。
    
    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        product_ids: 要分析的 product_id 列表（用於過濾）
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        station: 站點代碼 (P1/P2/P3)
        include_basic_stats: 是否包含基本統計
        include_outliers: 是否包含異常檢測
        include_contribution: 是否包含 PCA 貢獻度分析
        
    Returns:
        dict: 整合分析結果
    """
    result: dict[str, Any] = {
        "station": station,
        "product_ids": product_ids or [],
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
    }
    
    # Basic statistics
    if include_basic_stats:
        try:
            stats = await run_basic_statistics_from_db(
                db=db,
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                station=station,
                product_ids=product_ids,
            )
            result["basic_statistics"] = stats
        except Exception as e:
            logger.exception("Failed to run basic statistics: %s", e)
            result["basic_statistics"] = {"error": str(e)}
    
    # Outlier detection
    if include_outliers:
        try:
            outliers = await run_compare_outliers_from_db(
                db=db,
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                station=station,
                product_ids=product_ids,
            )
            result["outliers"] = outliers
        except Exception as e:
            logger.exception("Failed to run outlier detection: %s", e)
            result["outliers"] = {"error": str(e)}
    
    # PCA contribution analysis
    if include_contribution:
        try:
            contribution = await run_contribution_analysis_from_db(
                db=db,
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                station=station,
                product_ids=product_ids,
            )
            result["contribution"] = contribution
        except Exception as e:
            logger.exception("Failed to run contribution analysis: %s", e)
            result["contribution"] = {"error": str(e)}

    return result


# ==============================================================================
# Extraction Analysis (IQR + PCA → final_raw_score)
# ==============================================================================


async def run_extraction_analysis_from_db(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    start_date: str | None = None,
    end_date: str | None = None,
    station: str = "P2",
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    從 DB 撈取資料並執行 Extraction Analysis:
    IQR boundary + PCA T²/SPE → merge_boundary_spe_with_t2 → final_raw_score

    Returns:
        dict: {boundary_count, spe_score, t2_score, final_raw_score, features_used}
    """
    from app.services.analytics_data_fetcher import (
        fetch_merged_by_product_ids,
        fetch_merged_p1p2p3_from_db,
    )

    paths = resolve_external_paths()
    _ensure_analytical_four_importable(paths.analytical_four_root)

    from analysis.diagnostic.comparator import Comparator
    from analysis.diagnostic.contribution import ContributionAnalyzer
    from analysis.diagnostic.extraction import Extractor
    from analysis.models import (
        CompareOutliersResults,
        DataFrameSummary,
        StatisticsSummary,
    )

    config = load_analytical_config()
    target_col, numerical_cols, categorical_cols, id_col = get_station_config(config, station)

    try:
        # ── Fetch and prepare data ──
        if product_ids:
            df = await fetch_merged_by_product_ids(
                db=db, tenant_id=tenant_id, product_ids=product_ids,
            )
        else:
            df = await fetch_merged_p1p2p3_from_db(
                db=db, tenant_id=tenant_id,
                start_date=start_date, end_date=end_date,
                stations=[station],
            )

        if df.empty:
            logger.warning("No data for extraction analysis: tenant=%s, station=%s", tenant_id, station)
            return {}

        all_required = numerical_cols + ([id_col] if id_col else [])
        prepared_df, present_cols, missing_cols = validate_and_prepare_df(
            df, all_required, numerical_cols,
        )
        present_numerical = [c for c in numerical_cols if c in present_cols]
        if len(present_numerical) < 2:
            logger.warning("Need at least 2 numerical columns for extraction, got %d", len(present_numerical))
            return {}

        num_df = prepared_df[present_numerical].dropna()
        if len(num_df) < 10:
            logger.warning("Insufficient samples for extraction: %d", len(num_df))
            return {}

        if id_col and id_col in present_cols:
            sample_id_list = prepared_df.loc[num_df.index, id_col].astype(str).tolist()
        else:
            sample_id_list = [f"row_{i}" for i in num_df.index]

        # ── Step 1: IQR boundary detection ──
        stats_results = await run_basic_statistics_from_db(
            db=db, tenant_id=tenant_id,
            start_date=start_date, end_date=end_date,
            station=station, product_ids=product_ids,
        )
        if not stats_results:
            return {}

        # Wrap plain dict → DataFrameSummary (check_outlier expects .results attribute)
        stats_obj = DataFrameSummary(results={
            col: StatisticsSummary(**vals) if isinstance(vals, dict) else vals
            for col, vals in stats_results.items()
        })

        method = config.get("method", "IQR Thresholds")
        baseline = None
        diagnostic_paths = config.get("data_source", {}).get("diagnostic", [])
        if diagnostic_paths:
            baseline_path = paths.september_v2_root.parent / diagnostic_paths[0]
            if baseline_path.exists():
                baseline = _load_json(baseline_path)

        comparator = Comparator()
        boundary_result = comparator.check_outlier(
            data=prepared_df,
            stats=stats_obj,
            base_line=baseline,
            method=method,
            id_feature=id_col,
            numerical_features=present_numerical,
        )
        # Wrap as CompareOutliersResults
        boundary_obj = CompareOutliersResults(results=boundary_result if isinstance(boundary_result, dict) else {})

        # ── Step 2: PCA T²/SPE contribution ──
        split_idx = int(len(num_df) * 0.8)
        baseline_df = num_df.iloc[:split_idx]
        analysis_df = num_df.iloc[split_idx:]
        analysis_ids = sample_id_list[split_idx:] if len(sample_id_list) > split_idx else sample_id_list[-len(analysis_df):]

        if len(baseline_df) < 5 or len(analysis_df) < 1:
            logger.warning("Insufficient data for PCA split: baseline=%d, analysis=%d", len(baseline_df), len(analysis_df))
            return {}

        analyzer = ContributionAnalyzer()
        alpha = 0.05

        scaler = analyzer.fit_scaler(baseline_df)
        std_baseline_df = analyzer.transform_with_scaler(baseline_df, scaler)
        std_analysis_df = analyzer.transform_with_scaler(analysis_df, scaler)

        pca, transformed, cum_var, sel_var = analyzer.PCA(std_baseline_df)

        t2_ucl = analyzer.calculate_t2_limit(std_baseline_df, pca, alpha=alpha)
        spe_ucl = analyzer.calculate_spe_limit(std_baseline_df, pca, alpha=alpha)

        t2, t2_feature, t2_feature_score, t2_feature_rank = analyzer.hotelling_t2(std_analysis_df, pca)
        spe, spe_feature, spe_feature_score, spe_feature_rank = analyzer.SPE(std_analysis_df, pca)

        sample_diagnostics = analyzer.construct_sample_diagnostics(
            analysis_ids, std_analysis_df,
            t2, t2_ucl, t2_feature, t2_feature_score, t2_feature_rank,
            spe, spe_ucl, spe_feature, spe_feature_score, spe_feature_rank,
        )

        # ── Step 3: Merge boundary + SPE + T² → final_raw_score ──
        # Fix: construct_sample_diagnostics stores is_T2/SPE_Outlier as strings ("True"/"False"),
        # but merge_boundary_spe_with_t2 uses them in boolean context — convert to real bools
        for _sid, diag in sample_diagnostics.items():
            for key in ("is_T2_Outlier", "is_SPE_Outlier"):
                val = diag.get(key)
                if isinstance(val, str):
                    diag[key] = val == "True"

        extractor = Extractor()
        merged = extractor.merge_boundary_spe_with_t2(
            boundary=boundary_obj,
            spe_with_t2=sample_diagnostics,
        )

        # Sort by final_raw_score descending
        sorted_features = sorted(merged.final_raw_score.items(), key=lambda x: x[1], reverse=True)

        result = {
            "boundary_count": {f: merged.boundary_count.get(f, 0) for f, _ in sorted_features},
            "spe_score": {f: merged.spe_score.get(f, 0.0) for f, _ in sorted_features},
            "t2_score": {f: merged.t2_score.get(f, 0.0) for f, _ in sorted_features},
            "final_raw_score": dict(sorted_features),
            "features_used": present_numerical,
            "sample_counts": {
                "total": len(num_df),
                "baseline": len(baseline_df),
                "analysis": len(analysis_df),
            },
        }

        logger.info(
            "Extraction analysis completed: tenant=%s, station=%s, features=%d",
            tenant_id, station, len(sorted_features),
        )
        return result

    except Exception as e:
        logger.exception("Failed to run extraction analysis: %s", e)
        return {"error": str(e)}
