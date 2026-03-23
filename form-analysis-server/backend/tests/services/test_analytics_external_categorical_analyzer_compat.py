import json
import sys
from pathlib import Path

import pandas as pd

from app.services.analytics_external import run_external_categorical_analysis


def _install_fake_categorical_analyzer_module(*, tmp_path: Path, mode: str):
    """Inject a fake Analytical-Four module into sys.modules.

    mode:
      - "new": provides analyze_target_distribution_by_category
      - "old": provides analyze
    """

    # Ensure namespace packages exist.
    sys.modules.setdefault("analysis", type(sys)("analysis"))
    sys.modules.setdefault("analysis.descriptive", type(sys)("analysis.descriptive"))

    mod = type(sys)("analysis.descriptive.categorical_analyzer")

    calls = {"called": None, "categorical_cols": None}

    class CategoricalAnalyzer:  # noqa: N801 (external API)
        def __init__(self):
            pass

        def analyze_target_distribution_by_category(
            self, *, data, target_col, categorical_cols, normalize=True
        ):
            calls["called"] = "new"
            calls["categorical_cols"] = list(categorical_cols)
            # Return minimal shape expected by the endpoint.
            return {
                "feature_a": {"x": {"0": 0.5, "1": 0.5, "total_count": 2, "count_0": 1}}
            }

        def analyze(self, *, data, target_col, categorical_cols, normalize=True):
            calls["called"] = "old"
            calls["categorical_cols"] = list(categorical_cols)
            return {
                "feature_a": {"x": {"0": 1.0, "1": 0.0, "total_count": 1, "count_0": 1}}
            }

    if mode == "new":
        # Remove old method to ensure we pick the new method.
        delattr(CategoricalAnalyzer, "analyze")
    elif mode == "old":
        # Remove new method to ensure we fall back to old method.
        delattr(CategoricalAnalyzer, "analyze_target_distribution_by_category")
    else:
        raise ValueError("mode must be 'new' or 'old'")

    mod.CategoricalAnalyzer = CategoricalAnalyzer

    sys.modules["analysis.descriptive.categorical_analyzer"] = mod
    return calls


def _write_inputs(tmp_path: Path):
    config = {
        "feature": {
            "P2": {
                "target": "result",
                "categorical": {
                    "group1": ["feature_a", "missing_feature"],
                },
            }
        }
    }

    config_path = tmp_path / "ut_config_v3.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    df = pd.DataFrame(
        [
            {"result": "0", "feature_a": "x"},
            {"result": "1", "feature_a": "x"},
        ]
    )
    csv_path = tmp_path / "merged.csv"
    df.to_csv(csv_path, index=False)

    return config_path, csv_path


def test_run_external_categorical_analysis_uses_new_api_when_available(
    monkeypatch, tmp_path
):
    calls = _install_fake_categorical_analyzer_module(tmp_path=tmp_path, mode="new")
    config_path, csv_path = _write_inputs(tmp_path)

    analytical_root = tmp_path / "Analytical-Four"
    analytical_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ANALYTICAL_FOUR_PATH", str(analytical_root))
    monkeypatch.setenv("ANALYTICS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ANALYTICS_MERGED_CSV_PATH", str(csv_path))

    out = run_external_categorical_analysis(
        start_date=None,
        end_date=None,
        product_id=None,
        stations=["P2"],
    )

    assert calls["called"] == "new"
    # Should silently drop missing categorical columns.
    assert calls["categorical_cols"] == ["feature_a"]
    assert "feature_a" in out


def test_run_external_categorical_analysis_falls_back_to_old_api(monkeypatch, tmp_path):
    calls = _install_fake_categorical_analyzer_module(tmp_path=tmp_path, mode="old")
    config_path, csv_path = _write_inputs(tmp_path)

    analytical_root = tmp_path / "Analytical-Four"
    analytical_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ANALYTICAL_FOUR_PATH", str(analytical_root))
    monkeypatch.setenv("ANALYTICS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ANALYTICS_MERGED_CSV_PATH", str(csv_path))

    out = run_external_categorical_analysis(
        start_date=None,
        end_date=None,
        product_id=None,
        stations=["P2"],
    )

    assert calls["called"] == "old"
    assert calls["categorical_cols"] == ["feature_a"]
    assert "feature_a" in out
