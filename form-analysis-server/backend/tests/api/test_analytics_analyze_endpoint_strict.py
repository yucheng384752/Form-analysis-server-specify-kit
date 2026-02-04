import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
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
async def test_v2_analytics_analyze_success(client, db_session, monkeypatch):
    tenant = await _create_tenant(db_session)

    def fake_run_external_categorical_analysis(
        *, start_date, end_date, product_id, stations
    ):
        assert start_date == "2025-09-01"
        assert end_date == "2025-09-01"
        assert product_id == "20250901_P21_238-3_302"
        assert stations == ["P3"]
        return {
            "P3.operator": {
                "anna": {
                    "0": 0.111,
                    "1": 0.889,
                    "total_count": 9,
                    "count_0": 1,
                }
            }
        }

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "run_external_categorical_analysis",
        fake_run_external_categorical_analysis,
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/analyze",
        json={
            "start_date": "2025-09-01",
            "end_date": "2025-09-01",
            "product_id": "20250901_P21_238-3_302",
            "stations": ["P3"],
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["P3.operator"]["anna"]["count_0"] == 1


@pytest.mark.asyncio
async def test_v2_analytics_analyze_file_not_found_does_not_leak_paths(
    client, db_session, monkeypatch
):
    tenant = await _create_tenant(db_session)

    def fake_run_external_categorical_analysis(
        *, start_date, end_date, product_id, stations
    ):
        raise FileNotFoundError(
            "C:/Users/example/Desktop/september_v2/merged_p1_p2_p3.csv"
        )

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "run_external_categorical_analysis",
        fake_run_external_categorical_analysis,
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/analyze",
        json={"stations": ["P2"]},
        headers=headers,
    )

    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    # Should not leak internal absolute paths back to client.
    assert "C:/Users" not in str(body["detail"])


@pytest.mark.asyncio
async def test_v2_analytics_analyze_unexpected_error_is_generic(
    client, db_session, monkeypatch
):
    tenant = await _create_tenant(db_session)

    def fake_run_external_categorical_analysis(
        *, start_date, end_date, product_id, stations
    ):
        raise RuntimeError("boom")

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "run_external_categorical_analysis",
        fake_run_external_categorical_analysis,
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/analytics/analyze",
        json={"stations": ["P2"]},
        headers=headers,
    )

    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    assert "boom" not in str(body["detail"])
