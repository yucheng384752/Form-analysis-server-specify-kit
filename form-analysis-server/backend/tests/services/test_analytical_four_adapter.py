"""
Tests for Analytical-Four Adapter

測試即時分析功能
"""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_analytical_four(monkeypatch, tmp_path):
    """Mock Analytical-Four 模組"""
    # Create fake config
    config = {
        "method": "IQR Thresholds",
        "serializer": "UT",
        "feature": {
            "P2": {
                "numerical": ["Semi-finished impedance", "Heat gun temperature", "Slitting speed"],
                "categorical": {
                    "Machine": ["Slitting machine", "Winder number"],
                    "Man": ["Qaulity inspecrion"],
                },
                "target": "Striped Results",
                "id": "Semi_produce No.",
            }
        },
    }
    
    config_path = tmp_path / "config" / "ut_config_v3.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    
    # Mock external paths
    from app.services import analytics_external
    
    class FakePaths:
        analytical_four_root = tmp_path / "Analytical-Four"
        september_v2_root = tmp_path
        merged_csv_path = tmp_path / "merged_p1_p2_p3.csv"
    
    # Assign config_path after class definition
    FakePaths.config_path = config_path
    
    monkeypatch.setattr(analytics_external, "resolve_external_paths", lambda: FakePaths())
    
    return FakePaths()


@pytest.fixture
def mock_db_data(monkeypatch):
    """Mock DB fetcher to return test data"""
    import pandas as pd
    
    async def fake_fetch(*args, **kwargs):
        return pd.DataFrame({
            "Semi_produce No.": ["LOT001", "LOT002", "LOT003"],
            "Striped Results": [1, 0, 1],
            "Semi-finished impedance": [45.2, 46.1, 44.8],
            "Heat gun temperature": [120, 125, 118],
            "Slitting speed": [50, 52, 48],
            "Slitting machine": ["M1", "M1", "M2"],
            "Winder number": [1, 2, 1],
        })
    
    from app.services import analytics_data_fetcher
    monkeypatch.setattr(analytics_data_fetcher, "fetch_merged_p1p2p3_from_db", fake_fetch)


async def test_load_analytical_config(mock_analytical_four):
    """測試載入 Analytical-Four 設定檔"""
    from app.services.analytical_four_adapter import load_analytical_config
    
    config = load_analytical_config(mock_analytical_four.config_path)
    
    assert "feature" in config
    assert "P2" in config["feature"]
    assert config["method"] == "IQR Thresholds"


async def test_get_station_config(mock_analytical_four):
    """測試提取站點設定"""
    from app.services.analytical_four_adapter import (
        get_station_config,
        load_analytical_config,
    )
    
    config = load_analytical_config(mock_analytical_four.config_path)
    target, numerical, categorical, id_col = get_station_config(config, "P2")
    
    assert target == "Striped Results"
    assert "Semi-finished impedance" in numerical
    assert id_col == "Semi_produce No."


async def test_validate_and_prepare_df():
    """測試 DataFrame 驗證和準備"""
    import pandas as pd

    from app.services.analytical_four_adapter import validate_and_prepare_df
    
    df = pd.DataFrame({
        "col1": ["1", "2", "3"],
        "col2": [4.0, 5.0, 6.0],
        "col3": ["a", "b", "c"],
    })
    
    prepared, present, missing = validate_and_prepare_df(
        df,
        required_cols=["col1", "col2", "col4"],
        numerical_cols=["col1", "col2"],
    )
    
    assert "col1" in present
    assert "col2" in present
    assert "col4" in missing
    assert prepared["col1"].dtype in ["int64", "float64"]


async def test_adapter_functions_exist():
    """測試 Adapter 模組包含所需函式"""
    from app.services import analytical_four_adapter
    
    assert hasattr(analytical_four_adapter, "run_basic_statistics_from_db")
    assert hasattr(analytical_four_adapter, "run_compare_outliers_from_db")
    assert hasattr(analytical_four_adapter, "run_contribution_analysis_from_db")
    assert hasattr(analytical_four_adapter, "run_serialization_from_db")
    assert hasattr(analytical_four_adapter, "run_unified_analysis_from_db")


async def test_realtime_analysis_endpoint_exists():
    """測試即時分析端點存在（檢查 router 定義）"""
    from app.api.routes_analytics import router
    
    # Check that the router has the endpoint defined
    route_paths = [route.path for route in router.routes]
    assert "/api/v2/analytics/realtime-analysis" in route_paths


async def test_complaint_analysis_request_model():
    """測試 ComplaintAnalysisRequest 包含必要欄位"""
    from app.api.routes_analytics import ComplaintAnalysisRequest

    model_fields = ComplaintAnalysisRequest.model_fields

    assert "product_ids" in model_fields
    assert "include_basic_stats" in model_fields
    assert "include_outliers" in model_fields
    assert "include_contribution" in model_fields


async def test_complaint_analysis_response_model():
    """測試 ComplaintAnalysisResponse 包含必要欄位"""
    from app.api.routes_analytics import ComplaintAnalysisResponse

    model_fields = ComplaintAnalysisResponse.model_fields
    assert "requested_ids" in model_fields
    assert "mapping" in model_fields
    assert "source_scope" in model_fields
    assert "analysis" in model_fields

