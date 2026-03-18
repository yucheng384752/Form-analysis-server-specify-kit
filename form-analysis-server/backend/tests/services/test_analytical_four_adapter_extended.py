"""
Extended tests for analytical_four_adapter — covers validate_and_prepare_df edge cases,
get_station_config edge cases, and the extraction-analysis pipeline logic.
"""

import pytest
import pandas as pd
import numpy as np

pytestmark = pytest.mark.anyio


# ==========================================================================
# validate_and_prepare_df — unit tests
# ==========================================================================


class TestValidateAndPrepareDF:
    """validate_and_prepare_df 的單元測試"""

    @staticmethod
    def _import():
        from app.services.analytical_four_adapter import validate_and_prepare_df
        return validate_and_prepare_df

    async def test_basic_numeric_conversion(self):
        """字串數字欄位應被轉為 numeric"""
        fn = self._import()
        df = pd.DataFrame({
            "a": ["1.1", "2.2", "3.3"],
            "b": [10, 20, 30],
        })
        prepared, present, missing = fn(df, ["a", "b"], ["a", "b"])
        assert set(present) == {"a", "b"}
        assert missing == []
        assert prepared["a"].dtype in (np.float64, np.int64)
        assert prepared["b"].dtype in (np.float64, np.int64)

    async def test_missing_columns_reported(self):
        """缺少的欄位應出現在 missing 列表"""
        fn = self._import()
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        _, present, missing = fn(df, ["x", "y", "z", "w"], ["x"])
        assert "x" in present
        assert "y" in present
        assert set(missing) == {"z", "w"}

    async def test_coerce_non_numeric_to_nan(self):
        """無法轉為數字的值應被 coerce 為 NaN"""
        fn = self._import()
        df = pd.DataFrame({"val": ["1.0", "abc", "3.0", None]})
        prepared, _, _ = fn(df, ["val"], ["val"])
        assert prepared["val"].isna().sum() == 2  # "abc" and None

    async def test_empty_required_cols(self):
        """required_cols 為空 → 回傳完整 df 複本"""
        fn = self._import()
        df = pd.DataFrame({"a": [1], "b": [2]})
        prepared, present, missing = fn(df, [], [])
        assert present == []
        assert missing == []
        assert list(prepared.columns) == ["a", "b"]

    async def test_all_columns_missing(self):
        """全部 required 欄位都不在 df → present=[], missing=全部"""
        fn = self._import()
        df = pd.DataFrame({"x": [1]})
        prepared, present, missing = fn(df, ["a", "b"], ["a", "b"])
        assert present == []
        assert set(missing) == {"a", "b"}
        # prepared should be full copy of df
        assert "x" in prepared.columns

    async def test_numerical_cols_not_in_df_ignored(self):
        """numerical_cols 中不存在於 df 的欄位不會引發例外"""
        fn = self._import()
        df = pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]})
        prepared, _, _ = fn(df, ["a"], ["a", "not_exist"])
        assert prepared["a"].dtype in (np.float64, np.int64)

    async def test_preserves_index(self):
        """原始 index 應被保留"""
        fn = self._import()
        df = pd.DataFrame({"v": [10, 20]}, index=[5, 9])
        prepared, _, _ = fn(df, ["v"], ["v"])
        assert list(prepared.index) == [5, 9]


# ==========================================================================
# get_station_config — unit tests
# ==========================================================================


class TestGetStationConfig:
    """get_station_config 的單元測試"""

    @staticmethod
    def _import():
        from app.services.analytical_four_adapter import get_station_config
        return get_station_config

    async def test_normal_config(self):
        """標準配置提取"""
        fn = self._import()
        config = {
            "feature": {
                "P2": {
                    "numerical": ["col_a", "col_b"],
                    "categorical": {
                        "Machine": ["machine_1", "machine_2"],
                        "Man": ["operator"],
                    },
                    "target": "result",
                    "id": "lot_no",
                }
            }
        }
        target, num, cat, id_col = fn(config, "P2")
        assert target == "result"
        assert num == ["col_a", "col_b"]
        assert set(cat) == {"machine_1", "machine_2", "operator"}
        assert id_col == "lot_no"

    async def test_case_insensitive_station(self):
        """站點代碼應不區分大小寫"""
        fn = self._import()
        config = {"feature": {"P2": {"target": "T", "id": "I", "numerical": ["n1"]}}}
        target, num, cat, id_col = fn(config, "p2")
        assert target == "T"
        assert num == ["n1"]

    async def test_missing_station(self):
        """缺少站點設定時應回傳空值"""
        fn = self._import()
        config = {"feature": {"P2": {"target": "T"}}}
        target, num, cat, id_col = fn(config, "P3")
        assert target == ""
        assert num == []
        assert cat == []
        assert id_col == ""

    async def test_empty_feature_config(self):
        """空的 feature 設定不應報錯"""
        fn = self._import()
        config = {"feature": {}}
        target, num, cat, id_col = fn(config, "P2")
        assert target == ""
        assert num == []

    async def test_categorical_dedup(self):
        """重複的 categorical 欄位應被去重"""
        fn = self._import()
        config = {
            "feature": {
                "P2": {
                    "numerical": [],
                    "categorical": {
                        "A": ["dup_col", "unique_a"],
                        "B": ["dup_col", "unique_b"],
                    },
                    "target": "t",
                    "id": "i",
                }
            }
        }
        _, _, cat, _ = fn(config, "P2")
        assert cat.count("dup_col") == 1
        assert len(cat) == 3

    async def test_whitespace_stripped(self):
        """欄位名稱的空白應被清除"""
        fn = self._import()
        config = {
            "feature": {
                "P2": {
                    "numerical": ["  col_a  ", " col_b"],
                    "target": " target ",
                    "id": " id_col ",
                }
            }
        }
        target, num, _, id_col = fn(config, "P2")
        assert target == "target"
        assert num == ["col_a", "col_b"]
        assert id_col == "id_col"


# ==========================================================================
# load_analytical_config — unit tests
# ==========================================================================


class TestLoadAnalyticalConfig:
    """load_analytical_config 的單元測試"""

    async def test_loads_valid_json(self, tmp_path):
        """應成功載入合法 JSON"""
        import json
        from app.services.analytical_four_adapter import load_analytical_config

        cfg = {"method": "IQR Thresholds", "feature": {"P2": {}}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")

        result = load_analytical_config(p)
        assert result["method"] == "IQR Thresholds"

    async def test_raises_on_missing_file(self, tmp_path):
        """設定檔不存在應拋出 FileNotFoundError"""
        from app.services.analytical_four_adapter import load_analytical_config

        with pytest.raises(FileNotFoundError):
            load_analytical_config(tmp_path / "not_exist.json")


# ==========================================================================
# Extraction analysis endpoint — API integration test
# ==========================================================================


class TestExtractionAnalysisEndpoint:
    """POST /api/v2/analytics/extraction-analysis 的 API 測試"""

    @pytest.fixture
    async def client(self, db_session):
        from httpx import ASGITransport, AsyncClient
        from app.api.deps import get_db
        from app.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest.fixture
    async def tenant(self, db_session):
        import uuid
        from app.models.core.tenant import Tenant

        t = Tenant(
            name=f"Test Tenant {uuid.uuid4()}",
            code=f"test_{uuid.uuid4().hex[:8]}",
            is_default=True,
        )
        db_session.add(t)
        await db_session.commit()
        await db_session.refresh(t)
        return t

    async def test_extraction_analysis_returns_final_raw_score(
        self, client, tenant, monkeypatch
    ):
        """成功時回應應包含 final_raw_score 結構"""

        async def fake_run(*, db, tenant_id, start_date, end_date, station, product_ids):
            return {
                "boundary_count": {"col_a": 5, "col_b": 2},
                "spe_score": {"col_a": 0.62, "col_b": 0.38},
                "t2_score": {"col_a": 0.55, "col_b": 0.45},
                "final_raw_score": {"col_a": 1.17, "col_b": 0.83},
                "features_used": ["col_a", "col_b"],
                "sample_counts": {"total": 100, "baseline": 80, "analysis": 20},
            }

        from app.services import analytical_four_adapter
        monkeypatch.setattr(
            analytical_four_adapter,
            "run_extraction_analysis_from_db",
            fake_run,
        )

        resp = await client.post(
            "/api/v2/analytics/extraction-analysis",
            json={"start_date": "2025-09-01", "end_date": "2025-09-01", "station": "P2"},
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "final_raw_score" in body
        assert body["final_raw_score"]["col_a"] == 1.17
        assert body["features_used"] == ["col_a", "col_b"]
        assert body["sample_counts"]["total"] == 100

    async def test_extraction_analysis_empty_result(
        self, client, tenant, monkeypatch
    ):
        """無資料時應回傳空 final_raw_score"""

        async def fake_run(*, db, tenant_id, start_date, end_date, station, product_ids):
            return {}

        from app.services import analytical_four_adapter
        monkeypatch.setattr(
            analytical_four_adapter,
            "run_extraction_analysis_from_db",
            fake_run,
        )

        resp = await client.post(
            "/api/v2/analytics/extraction-analysis",
            json={"station": "P2"},
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["final_raw_score"] == {}
        assert body["features_used"] == []

    async def test_extraction_analysis_error_returns_empty(
        self, client, tenant, monkeypatch
    ):
        """adapter 回傳 error 時，API 應回傳空結構而非 500"""

        async def fake_run(*, db, tenant_id, start_date, end_date, station, product_ids):
            return {"error": "PCA failed"}

        from app.services import analytical_four_adapter
        monkeypatch.setattr(
            analytical_four_adapter,
            "run_extraction_analysis_from_db",
            fake_run,
        )

        resp = await client.post(
            "/api/v2/analytics/extraction-analysis",
            json={"station": "P2"},
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["final_raw_score"] == {}

    async def test_extraction_analysis_exception_returns_500(
        self, client, tenant, monkeypatch
    ):
        """adapter 拋出例外時應回傳 500"""

        async def fake_run(*, db, tenant_id, start_date, end_date, station, product_ids):
            raise RuntimeError("unexpected failure")

        from app.services import analytical_four_adapter
        monkeypatch.setattr(
            analytical_four_adapter,
            "run_extraction_analysis_from_db",
            fake_run,
        )

        resp = await client.post(
            "/api/v2/analytics/extraction-analysis",
            json={"station": "P2"},
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 500


# ==========================================================================
# Analyze endpoint — NG count_0 data (used by Pareto)
# ==========================================================================


class TestAnalyzeEndpointNgPareto:
    """POST /api/v2/analytics/analyze — 驗證 count_0 資料 (Pareto 需要)"""

    @pytest.fixture
    async def client(self, db_session):
        from httpx import ASGITransport, AsyncClient
        from app.api.deps import get_db
        from app.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest.fixture
    async def tenant(self, db_session):
        import uuid
        from app.models.core.tenant import Tenant

        t = Tenant(
            name=f"Test Tenant {uuid.uuid4()}",
            code=f"test_{uuid.uuid4().hex[:8]}",
            is_default=True,
        )
        db_session.add(t)
        await db_session.commit()
        await db_session.refresh(t)
        return t

    async def test_analyze_returns_count_0_for_pareto(
        self, client, tenant, monkeypatch
    ):
        """analyze 回應應包含 count_0 供前端 NG Pareto 使用"""

        async def fake_analysis(
            *, db, tenant_id, start_date, end_date, product_id, product_ids, stations
        ):
            return {
                "P2.NG_code": {
                    "short_circuit": {
                        "0": 0.15,
                        "1": 0.85,
                        "total_count": 200,
                        "count_0": 30,
                    },
                    "open_circuit": {
                        "0": 0.10,
                        "1": 0.90,
                        "total_count": 200,
                        "count_0": 20,
                    },
                    "impedance_out_of_spec": {
                        "0": 0.05,
                        "1": 0.95,
                        "total_count": 200,
                        "count_0": 10,
                    },
                },
            }

        from app.services import analytics_external
        monkeypatch.setattr(
            analytics_external,
            "run_external_categorical_analysis_from_db",
            fake_analysis,
        )

        resp = await client.post(
            "/api/v2/analytics/analyze",
            json={
                "start_date": "2025-09-01",
                "end_date": "2025-09-01",
                "stations": ["P2"],
            },
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 200
        body = resp.json()

        # Verify the count_0 structure that frontend buildParetoSeries() consumes
        ng_code = body["P2.NG_code"]
        assert "short_circuit" in ng_code
        assert ng_code["short_circuit"]["count_0"] == 30
        assert ng_code["open_circuit"]["count_0"] == 20
        assert ng_code["impedance_out_of_spec"]["count_0"] == 10

        # Verify sorted order for Pareto: short_circuit(30) > open_circuit(20) > impedance(10)
        count_0_values = [v["count_0"] for v in ng_code.values()]
        assert count_0_values == sorted(count_0_values, reverse=True)

    async def test_analyze_no_data_returns_empty(
        self, client, tenant, monkeypatch
    ):
        """無分析資料時應回傳空 dict"""

        async def fake_analysis(
            *, db, tenant_id, start_date, end_date, product_id, product_ids, stations
        ):
            return {}

        from app.services import analytics_external
        monkeypatch.setattr(
            analytics_external,
            "run_external_categorical_analysis_from_db",
            fake_analysis,
        )

        resp = await client.post(
            "/api/v2/analytics/analyze",
            json={"stations": ["P2"]},
            headers={"X-Tenant-Id": str(tenant.id)},
        )

        assert resp.status_code == 200
        assert resp.json() == {}


# ==========================================================================
# ExtractionAnalysisResponse schema — unit tests
# ==========================================================================


class TestExtractionAnalysisSchemas:
    """ExtractionAnalysisRequest / Response schema 驗證"""

    async def test_request_default_station_is_p2(self):
        from app.api.analytics.schemas import ExtractionAnalysisRequest

        req = ExtractionAnalysisRequest()
        assert req.station == "P2"

    async def test_request_accepts_product_ids(self):
        from app.api.analytics.schemas import ExtractionAnalysisRequest

        req = ExtractionAnalysisRequest(
            product_ids=["pid1", "pid2"],
            station="P3",
        )
        assert req.product_ids == ["pid1", "pid2"]
        assert req.station == "P3"

    async def test_response_defaults_empty(self):
        from app.api.analytics.schemas import ExtractionAnalysisResponse

        resp = ExtractionAnalysisResponse(station="P2")
        assert resp.final_raw_score == {}
        assert resp.features_used == []
        assert resp.sample_counts == {}
        assert resp.boundary_count == {}

    async def test_response_with_data(self):
        from app.api.analytics.schemas import ExtractionAnalysisResponse

        resp = ExtractionAnalysisResponse(
            station="P2",
            final_raw_score={"col_a": 1.5, "col_b": 0.8},
            features_used=["col_a", "col_b"],
            sample_counts={"total": 100, "baseline": 80, "analysis": 20},
            boundary_count={"col_a": 3, "col_b": 1},
            spe_score={"col_a": 0.6, "col_b": 0.4},
            t2_score={"col_a": 0.5, "col_b": 0.3},
            elapsed_ms=125.5,
        )
        assert resp.final_raw_score["col_a"] == 1.5
        assert resp.elapsed_ms == 125.5


# ==========================================================================
# AnalyzeRequest schema — unit tests
# ==========================================================================


class TestAnalyzeRequestSchema:
    """AnalyzeRequest schema 驗證"""

    async def test_defaults(self):
        from app.api.analytics.schemas import AnalyzeRequest

        req = AnalyzeRequest()
        assert req.start_date is None
        assert req.end_date is None
        assert req.product_id is None
        assert req.product_ids == []
        assert req.stations == []

    async def test_with_all_fields(self):
        from app.api.analytics.schemas import AnalyzeRequest

        req = AnalyzeRequest(
            start_date="2025-09-01",
            end_date="2025-09-30",
            product_id="prod_001",
            product_ids=["prod_001", "prod_002"],
            stations=["P2", "P3"],
        )
        assert req.start_date == "2025-09-01"
        assert len(req.product_ids) == 2
        assert "P2" in req.stations
