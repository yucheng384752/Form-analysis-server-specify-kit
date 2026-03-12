import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _create_tenant(db_session) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_list_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.services import analytics_external

    class FakeInfo:
        def __init__(self, key, filename, exists):
            self.key = key
            self.filename = filename
            self.exists = exists
            self.size_bytes = 123
            self.mtime_epoch = 456.0

    monkeypatch.setattr(
        analytics_external,
        "list_analytics_artifacts",
        lambda: [FakeInfo("serialized_events", "ut_serialized_results.json", True)],
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/analytics/artifacts", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert isinstance(payload, list)
    assert payload[0]["key"] == "serialized_events"
    assert payload[0]["exists"] is True


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_get_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "get_analytics_artifact_list_view",
        lambda key, **_: [
            {
                "event_id": "E-1",
                "event_date": "2025-01-01T00:00:00Z",
                "produce_no": "P",
                "winder": "W",
                "slitting": "S",
                "iqr_count": 1,
                "t2_count": 2,
                "spe_count": 3,
            }
        ],
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["event_id"] == "E-1"


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_snapshot_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "get_analytics_artifact_unified_snapshot",
        lambda key, **_: {
            "artifact_key": str(key),
            "sample_count": 3,
            "station_distribution": [{"name": "P2", "count": 2}],
            "machine_distribution": [{"name": "P24", "count": 2}],
            "top_features": [{"name": "IQR", "count": 5}],
            "metrics": {"total_anomalies": 5},
        },
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events/snapshot?product_ids=2507173_02_19",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["artifact_key"] == "serialized_events"
    assert body["sample_count"] == 3
    assert body["station_distribution"][0]["name"] == "P2"
    assert body["machine_distribution"][0]["name"] == "P24"
    assert body["top_features"][0]["name"] == "IQR"
    assert body["metrics"]["total_anomalies"] == 5


@pytest.mark.asyncio
async def test_v2_analytics_complaint_analysis_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.api import routes_analytics
    from app.api import traceability
    from app.services import analytics_external

    async def fake_resolve_artifact_input(**kwargs):
        _ = kwargs
        return routes_analytics.ArtifactInputResolveResponse(
            requested=["20250902_P24_238-2_301"],
            requested_count=1,
            normalized_inputs={"20250902_P24_238-2_301": ["20250902_P24_238-2_301"]},
            resolved=["2507173_02_19"],
            resolved_count=1,
            unmatched=[],
            unmatched_count=0,
            matches={"20250902_P24_238-2_301": ["2507173_02_19"]},
            match_diagnostics={
                "20250902_P24_238-2_301": {
                    "reason_code": "",
                    "reason_message": "",
                    "trace_source": "db_trace_lot",
                }
            },
            trace_tokens={"20250902_P24_238-2_301": ["2507173_02_19"]},
            trace_attempted_count=1,
            trace_resolved_count=1,
            unmatched_reason_counts={},
            elapsed_ms=12.3,
        )

    def fake_snapshot(key, **kwargs):
        _ = kwargs
        k = str(key)
        if k == "llm_reports":
            return {
                "artifact_key": k,
                "sample_count": 1,
                "station_distribution": [{"name": "P2", "count": 2}],
                "machine_distribution": [],
                "top_features": [{"name": "LLM:Burr", "count": 2}],
                "metrics": {"total_anomalies": 2},
            }
        if k == "rag_results":
            return {
                "artifact_key": k,
                "sample_count": 1,
                "station_distribution": [{"name": "P2", "count": 2}],
                "machine_distribution": [],
                "top_features": [{"name": "RAG:Burr", "count": 1}],
                "metrics": {"total_features": 1, "total_sop": 2},
            }
        return {
            "artifact_key": k,
            "sample_count": 1,
            "station_distribution": [{"name": "P2", "count": 2}],
            "machine_distribution": [{"name": "P24", "count": 2}],
            "top_features": [{"name": "IQR", "count": 2}],
            "metrics": {"total_events": 2},
        }

    monkeypatch.setattr(routes_analytics, "resolve_artifact_input", fake_resolve_artifact_input)
    monkeypatch.setattr(analytics_external, "get_analytics_artifact_unified_snapshot", fake_snapshot)
    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        _ = (db, current_tenant)
        assert product_id == "20250902_P24_238-2_301"
        return {
            "p1": {"lot_no": "2507173_02", "additional_data": {"rows": [{}]}},
            "p2": {"lot_no": "2507173_02", "additional_data": {"rows": [{}, {}]}},
            "p3": {"lot_no": "2507173_02", "additional_data": {"rows": [{}, {}, {}]}},
        }
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/complaint-analysis",
        headers=headers,
        json={
            "product_ids": ["20250902_P24_238-2_301"],
            "snapshot_artifact_key": "serialized_events",
            "include_report_views": ["llm_reports", "rag_results"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["artifact_key"] == "serialized_events"
    assert body["analysis_scope_id"] != "empty"
    assert body["scope_tokens_count"] == 1
    assert body["input_summary"]["resolved_count"] == 1
    assert body["source_scope"]["p1_count"] == 1
    assert body["source_scope"]["p2_count"] == 2
    assert body["source_scope"]["p3_count"] == 3
    assert body["report_input_scope"]["mode"] == "db_unified_p1p2p3"
    assert body["snapshot"]["machine_distribution"][0]["name"] == "P24"
    assert body["report_payload"]["llm_reports"]["metrics"]["total_anomalies"] == 2
    assert body["report_payload"]["rag_results"]["metrics"]["total_sop"] == 2
    assert body["mapping"]["20250902_P24_238-2_301"]["matched_stage"] == "matched_trace_lot"
    assert isinstance(body["report_composition"]["summary"], list)
    assert isinstance(body["report_composition"]["suggestions"], list)
    assert isinstance(body["report_composition"]["evidence_refs"], list)
    assert body["consistency"]["snapshot_scope_locked"] is True
    assert body["consistency"]["report_scope_locked"] is True
    assert body["consistency"]["scope_tokens_count"] == 1
    assert isinstance(body["timing"]["resolve_ms"], (int, float))
    assert isinstance(body["timing"]["snapshot_ms"], (int, float))
    assert isinstance(body["timing"]["report_ms"], (int, float))
    assert isinstance(body["timing"]["total_ms"], (int, float))


@pytest.mark.asyncio
async def test_v2_analytics_complaint_analysis_all_unmatched_returns_diagnostics_only(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.api import routes_analytics
    from app.api import traceability
    from app.services import analytics_external

    async def fake_resolve_artifact_input(**kwargs):
        _ = kwargs
        return routes_analytics.ArtifactInputResolveResponse(
            requested=["bad-id"],
            requested_count=1,
            normalized_inputs={"bad-id": ["bad-id"]},
            resolved=[],
            resolved_count=0,
            unmatched=["bad-id"],
            unmatched_count=1,
            matches={"bad-id": []},
            match_diagnostics={"bad-id": {"reason_code": "invalid_format", "reason_message": "bad format"}},
            trace_tokens={},
            trace_attempted_count=1,
            trace_resolved_count=0,
            unmatched_reason_counts={"invalid_format": 1},
            elapsed_ms=10.1,
        )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("unified snapshot should not be called when resolved is empty")

    monkeypatch.setattr(routes_analytics, "resolve_artifact_input", fake_resolve_artifact_input)
    monkeypatch.setattr(analytics_external, "get_analytics_artifact_unified_snapshot", fail_if_called)
    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        _ = (product_id, db, current_tenant)
        raise HTTPException(status_code=404, detail="not found")
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/complaint-analysis",
        headers=headers,
        json={
            "product_ids": ["bad-id"],
            "snapshot_artifact_key": "serialized_events",
            "include_report_views": ["llm_reports", "rag_results"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["analysis_scope_id"] == "empty"
    assert body["scope_tokens_count"] == 0
    assert body["input_summary"]["resolved_count"] == 0
    assert body["report_input_scope"]["mode"] == "db_unified_p1p2p3"
    assert body["source_scope"]["total_records"] == 0
    assert body["snapshot"]["sample_count"] == 0
    assert body["report_payload"] == {}
    assert isinstance(body["report_composition"]["summary"], list)
    assert isinstance(body["report_composition"]["suggestions"], list)
    assert isinstance(body["report_composition"]["evidence_refs"], list)
    assert body["consistency"]["scope_tokens_count"] == 0
    assert body["mapping"]["bad-id"]["matched_stage"] == "unmatched"
    assert isinstance(body["timing"]["resolve_ms"], (int, float))
    assert isinstance(body["timing"]["snapshot_ms"], (int, float))
    assert isinstance(body["timing"]["report_ms"], (int, float))
    assert isinstance(body["timing"]["total_ms"], (int, float))


@pytest.mark.asyncio
async def test_v2_analytics_complaint_analysis_partial_hit_keeps_analysis_and_diagnostics(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.api import routes_analytics
    from app.api import traceability
    from app.services import analytics_external

    async def fake_resolve_artifact_input(**kwargs):
        _ = kwargs
        return routes_analytics.ArtifactInputResolveResponse(
            requested=["hit-id", "miss-id"],
            requested_count=2,
            normalized_inputs={"hit-id": ["hit-id"], "miss-id": ["miss-id"]},
            resolved=["2507173_02_19"],
            resolved_count=1,
            unmatched=["miss-id"],
            unmatched_count=1,
            matches={"hit-id": ["2507173_02_19"], "miss-id": []},
            match_diagnostics={
                "hit-id": {"reason_code": "", "reason_message": "", "trace_source": "db_trace_lot"},
                "miss-id": {"reason_code": "no_trace", "reason_message": "No trace"},
            },
            trace_tokens={"hit-id": ["2507173_02_19"], "miss-id": []},
            trace_attempted_count=1,
            trace_resolved_count=0,
            unmatched_reason_counts={"no_trace": 1},
            elapsed_ms=8.8,
        )

    def fake_snapshot(key, **kwargs):
        _ = kwargs
        return {
            "artifact_key": str(key),
            "sample_count": 2,
            "station_distribution": [{"name": "P2", "count": 2}],
            "machine_distribution": [{"name": "P24", "count": 2}],
            "top_features": [{"name": "IQR", "count": 2}],
            "metrics": {"total_events": 2},
        }

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        _ = (db, current_tenant)
        if product_id == "hit-id":
            return {
                "p1": {"lot_no": "2507173_02", "additional_data": {"rows": [{}]}},
                "p2": {"lot_no": "2507173_02", "additional_data": {"rows": [{}]}},
                "p3": {"lot_no": "2507173_02", "additional_data": {"rows": [{}]}},
            }
        raise HTTPException(status_code=404, detail="not found")

    monkeypatch.setattr(routes_analytics, "resolve_artifact_input", fake_resolve_artifact_input)
    monkeypatch.setattr(analytics_external, "get_analytics_artifact_unified_snapshot", fake_snapshot)
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/complaint-analysis",
        headers=headers,
        json={
            "product_ids": ["hit-id", "miss-id"],
            "snapshot_artifact_key": "serialized_events",
            "include_report_views": ["llm_reports", "rag_results"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["input_summary"]["requested_count"] == 2
    assert body["input_summary"]["resolved_count"] == 1
    assert body["input_summary"]["unmatched_count"] == 1
    assert body["snapshot"]["sample_count"] == 2
    assert body["mapping"]["hit-id"]["matched_stage"] == "matched_trace_lot"
    assert body["mapping"]["miss-id"]["matched_stage"] == "unmatched"
    assert body["mapping"]["miss-id"]["reason_code"] == "no_trace"


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_unknown_key_404(client, db_session):
    tenant = await _create_tenant(db_session)
    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/analytics/artifacts/not_a_real_key", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "resolve_artifact_product_inputs",
        lambda key, **_: {
            "requested": ["2507173_02_19"],
            "resolved": ["2507173_02_19"],
            "unmatched": [],
            "matches": {"2507173_02_19": ["2507173_02_19"]},
        },
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids=2507173_02_19",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested"] == ["2507173_02_19"]
    assert body["requested_count"] == 1
    assert body["resolved"] == ["2507173_02_19"]
    assert body["resolved_count"] == 1
    assert body["unmatched"] == []
    assert body["unmatched_count"] == 0
    assert body["trace_attempted_count"] == 0
    assert body["trace_resolved_count"] == 0
    assert body["unmatched_reason_counts"] == {}


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_with_trace_tokens(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    def fake_resolve(_key, **kwargs):
        pids = kwargs.get("product_ids", [])
        # First pass: requested product_id has no direct hit.
        if pids == ["20250902_P24_238-2_301"]:
            return {
                "requested": pids,
                "resolved": [],
                "unmatched": ["20250902_P24_238-2_301"],
                "matches": {"20250902_P24_238-2_301": []},
            }
        # Second pass: trace token can hit artifacts.
        if pids == ["2507173_02_19"]:
            return {
                "requested": pids,
                "resolved": ["2507173_02_19"],
                "unmatched": [],
                "matches": {"2507173_02_19": ["2507173_02_19"]},
            }
        return {"requested": pids, "resolved": [], "unmatched": pids, "matches": {x: [] for x in pids}}

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        assert product_id == "20250902_P24_238-2_301"
        return {
            "p3": {
                "lot_no": "2507173_02",
                "source_winder": 19,
                "additional_data": {"rows": [{"Produce_No.": "2507173_02_19"}]},
            }
        }

    monkeypatch.setattr(analytics_external, "resolve_artifact_product_inputs", fake_resolve)
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids=20250902_P24_238-2_301",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested"] == ["20250902_P24_238-2_301"]
    assert body["requested_count"] == 1
    assert body["resolved"] == ["2507173_02_19"]
    assert body["resolved_count"] == 1
    assert body["unmatched"] == []
    assert body["unmatched_count"] == 0
    assert body["matches"]["20250902_P24_238-2_301"] == ["2507173_02_19"]
    assert body["trace_tokens"]["20250902_P24_238-2_301"] == ["2507173_02_19"]
    assert body["trace_attempted_count"] == 1
    assert body["trace_resolved_count"] == 1
    assert body["unmatched_reason_counts"] == {}


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_prefers_db_trace_lot_tokens(
    client, monkeypatch, db_session
):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    lot_raw = "2507173_02"
    lot_norm = normalize_lot_no(lot_raw)
    suffix = str((uuid.uuid4().int % 900) + 100)
    requested_pid = f"20250902_P24_238-2_{suffix}"
    trace_token = "2507173_02_19"

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_raw,
        lot_no_norm=lot_norm,
        production_date_yyyymmdd=20250902,
        machine_no="P24",
        mold_no="238-2",
        product_id=requested_pid,
        extras={"rows": [{}]},
        created_at=datetime(2025, 9, 2, tzinfo=timezone.utc),
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_raw,
            source_winder=19,
            product_id=requested_pid,
            specification="PE 32",
            row_data={},
        )
    ]

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_raw,
        lot_no_norm=lot_norm,
        winder_number=19,
        extras={"rows": [{}]},
        created_at=datetime(2025, 9, 2, tzinfo=timezone.utc),
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=19,
            trace_lot_no=trace_token,
            row_data={},
        )
    ]

    db_session.add_all([p3, p2])
    await db_session.commit()

    def fake_resolve(_key, **kwargs):
        pids = kwargs.get("product_ids", [])
        if pids == [requested_pid]:
            return {
                "requested": pids,
                "normalized_inputs": {requested_pid: [requested_pid]},
                "resolved": [],
                "unmatched": [requested_pid],
                "matches": {requested_pid: []},
                "artifact_row_count": 100,
            }
        if pids == [trace_token]:
            return {
                "requested": pids,
                "normalized_inputs": {trace_token: [trace_token]},
                "resolved": [trace_token],
                "unmatched": [],
                "matches": {trace_token: [trace_token]},
                "artifact_row_count": 100,
            }
        return {
            "requested": pids,
            "normalized_inputs": {x: [x] for x in pids},
            "resolved": [],
            "unmatched": pids,
            "matches": {x: [] for x in pids},
            "artifact_row_count": 100,
        }

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        _ = (product_id, db, current_tenant)
        raise HTTPException(status_code=404, detail="no trace")

    monkeypatch.setattr(analytics_external, "resolve_artifact_product_inputs", fake_resolve)
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        f"/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids={requested_pid}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matches"][requested_pid] == [trace_token]
    assert body["trace_tokens"][requested_pid] == [trace_token]
    assert body["trace_resolved_count"] == 1
    assert body["match_diagnostics"][requested_pid]["trace_source"] == "db_trace_lot"


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_rate_limit_returns_retry_after_header(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.api import routes_analytics
    from app.services import analytics_external

    class FakeInfo:
        def __init__(self, key, filename, exists):
            self.key = key
            self.filename = filename
            self.exists = exists
            self.size_bytes = 1
            self.mtime_epoch = 1.0

    monkeypatch.setattr(
        analytics_external,
        "list_analytics_artifacts",
        lambda: [FakeInfo("serialized_events", "ut_serialized_results.json", True)],
    )
    monkeypatch.setattr(routes_analytics.AnalyticsConfig, "RATE_LIMIT_REQUESTS_PER_MINUTE", 1)
    routes_analytics._rate_limit_store.clear()

    headers = {"X-Tenant-Id": str(tenant.id)}

    first = await client.get("/api/v2/analytics/artifacts", headers=headers)
    assert first.status_code == 200, first.text

    second = await client.get("/api/v2/analytics/artifacts", headers=headers)
    assert second.status_code == 429, second.text
    assert second.headers.get("Retry-After")
    body = second.json()
    assert isinstance(body, dict)
    assert isinstance(body.get("detail"), dict)
    assert body["detail"].get("code") == "RATE_LIMIT_EXCEEDED"
    assert body["detail"].get("endpoint") == "/api/v2/analytics/artifacts"


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_reason_invalid_format(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    monkeypatch.setattr(
        analytics_external,
        "resolve_artifact_product_inputs",
        lambda key, **_: {
            "requested": ["abc"],
            "artifact_row_count": 10,
            "normalized_inputs": {"abc": ["abc"]},
            "resolved": [],
            "unmatched": ["abc"],
            "matches": {"abc": []},
            "match_diagnostics": {"abc": {"candidate_count": 1, "matched_by": []}},
        },
    )

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        raise HTTPException(status_code=404, detail="not found")

    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids=abc",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested_count"] == 1
    assert body["resolved_count"] == 0
    assert body["unmatched_count"] == 1
    assert body["unmatched"] == ["abc"]
    assert body["match_diagnostics"]["abc"]["reason_code"] == "invalid_format"
    assert body["trace_attempted_count"] == 1
    assert body["trace_resolved_count"] == 0
    assert body["unmatched_reason_counts"] == {"invalid_format": 1}
    assert isinstance(body.get("elapsed_ms"), (int, float))


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_reason_no_trace(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    pid = "20250101_P99_999-9_999"
    monkeypatch.setattr(
        analytics_external,
        "resolve_artifact_product_inputs",
        lambda key, **_: {
            "requested": [pid],
            "artifact_row_count": 10,
            "normalized_inputs": {pid: [pid]},
            "resolved": [],
            "unmatched": [pid],
            "matches": {pid: []},
            "match_diagnostics": {pid: {"candidate_count": 1, "matched_by": []}},
        },
    )

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        raise HTTPException(status_code=404, detail="not found")

    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        f"/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids={pid}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested_count"] == 1
    assert body["resolved_count"] == 0
    assert body["unmatched_count"] == 1
    assert body["unmatched"] == [pid]
    assert body["match_diagnostics"][pid]["reason_code"] == "no_trace"
    assert body["trace_attempted_count"] == 1
    assert body["trace_resolved_count"] == 0
    assert body["unmatched_reason_counts"] == {"no_trace": 1}
    assert isinstance(body.get("elapsed_ms"), (int, float))


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_reason_artifact_no_data(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    pid = "20250909_P23_238-4_301"
    trace_token = "2507173_02_19"

    def fake_resolve(_key, **kwargs):
        pids = kwargs.get("product_ids", [])
        if pids == [pid]:
            return {
                "requested": [pid],
                "artifact_row_count": 10,
                "normalized_inputs": {pid: [pid, "20250909-P23-238-4-301"]},
                "resolved": [],
                "unmatched": [pid],
                "matches": {pid: []},
                "match_diagnostics": {pid: {"candidate_count": 2, "matched_by": []}},
            }
        if pids == [trace_token]:
            return {
                "requested": [trace_token],
                "artifact_row_count": 10,
                "normalized_inputs": {trace_token: [trace_token]},
                "resolved": [],
                "unmatched": [trace_token],
                "matches": {trace_token: []},
                "match_diagnostics": {trace_token: {"candidate_count": 1, "matched_by": []}},
            }
        return {
            "requested": pids,
            "artifact_row_count": 10,
            "normalized_inputs": {x: [x] for x in pids},
            "resolved": [],
            "unmatched": pids,
            "matches": {x: [] for x in pids},
            "match_diagnostics": {x: {"candidate_count": 1, "matched_by": []} for x in pids},
        }

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        assert product_id == pid
        return {
            "p3": {
                "lot_no": "2507173_02",
                "source_winder": 19,
                "additional_data": {"rows": [{"Produce_No.": trace_token}]},
            }
        }

    monkeypatch.setattr(analytics_external, "resolve_artifact_product_inputs", fake_resolve)
    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        f"/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids={pid}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested_count"] == 1
    assert body["resolved_count"] == 0
    assert body["unmatched_count"] == 1
    assert body["unmatched"] == [pid]
    assert body["trace_tokens"][pid] == [trace_token]
    assert body["match_diagnostics"][pid]["reason_code"] == "artifact_no_data"
    assert body["trace_attempted_count"] == 1
    assert body["trace_resolved_count"] == 0
    assert body["unmatched_reason_counts"] == {"artifact_no_data": 1}
    assert isinstance(body.get("elapsed_ms"), (int, float))


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_resolve_input_normalized_hit_fields(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)
    from app.services import analytics_external
    from app.api import traceability

    pid = "20250909-P23-238-4-301"
    normalized = "20250909_P23_238-4_301"

    monkeypatch.setattr(
        analytics_external,
        "resolve_artifact_product_inputs",
        lambda key, **_: {
            "requested": [pid],
            "artifact_row_count": 10,
            "normalized_inputs": {pid: [pid, normalized]},
            "resolved": ["2507173_02_19"],
            "unmatched": [],
            "matches": {pid: ["2507173_02_19"]},
            "match_diagnostics": {pid: {"candidate_count": 2, "matched_by": [normalized]}},
        },
    )

    async def fake_trace_by_product_id(*, product_id, db, current_tenant):
        raise HTTPException(status_code=404, detail="not needed")

    monkeypatch.setattr(traceability, "trace_by_product_id", fake_trace_by_product_id)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        f"/api/v2/analytics/artifacts/serialized_events/resolve-input?product_ids={pid}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested_count"] == 1
    assert body["resolved_count"] == 1
    assert body["unmatched_count"] == 0
    assert body["unmatched"] == []
    assert normalized in body["normalized_inputs"][pid]
    assert normalized in body["match_diagnostics"][pid]["matched_by"]
    assert body["trace_attempted_count"] == 0
    assert body["trace_resolved_count"] == 0
    assert body["unmatched_reason_counts"] == {}
    assert isinstance(body.get("elapsed_ms"), (int, float))
