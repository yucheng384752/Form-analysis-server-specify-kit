import uuid
from datetime import date

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_legacy_advanced_query_winder_does_not_include_p1(client, db_session):
    # Arrange
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    lot_no = "2507173_02"

    p1 = Record(
        lot_no=lot_no,
        data_type=DataType.P1,
        production_date=date(2025, 1, 1),
        product_name="P1",
        quantity=1,
        additional_data={"rows": [{"Specification": "P1-SPEC"}]},
    )

    p2 = Record(
        lot_no=lot_no,
        data_type=DataType.P2,
        production_date=date(2025, 1, 1),
        additional_data={"rows": [{"format": "P2-FORMAT"}]},
    )
    p2.p2_items = [
        P2Item(
            winder_number=5,
            row_data={"winder_number": 5},
        )
    ]

    p3 = Record(
        lot_no=lot_no,
        data_type=DataType.P3,
        production_date=date(2025, 1, 1),
        additional_data={"rows": [{"specification": "P3-SPEC"}]},
    )
    p3.p3_items = [
        P3Item(
            row_no=1,
            lot_no=lot_no,
            source_winder=5,
            specification="P3-SPEC",
            row_data={"source_winder": 5},
        )
    ]

    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    # Act
    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/query/records/advanced",
        params={"lot_no": lot_no, "winder_number": "5"},
        headers=headers,
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    types = {r["data_type"] for r in payload["records"]}

    assert "P1" not in types
    assert "P2" in types
    assert "P3" in types
