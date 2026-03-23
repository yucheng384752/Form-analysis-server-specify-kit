import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.services.import_v2 import ImportService


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _upload_and_commit_v2(
    client: AsyncClient,
    db_session,
    tenant_id: str,
    table_code: str,
    filename: str,
    content: bytes,
) -> uuid.UUID:
    upload_resp = await client.post(
        "/api/upload",
        headers={"X-Tenant-Id": tenant_id},
        files={"file": (filename, content, "text/csv")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    upload_process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    create_resp = await client.post(
        "/api/v2/import/jobs/from-upload-job",
        headers={"X-Tenant-Id": tenant_id},
        json={"upload_process_id": str(upload_process_id), "table_code": table_code},
    )
    assert create_resp.status_code == 201, create_resp.text
    job_id = uuid.UUID(str(create_resp.json()["id"]))

    # Parse + validate synchronously (tests don't run background tasks)
    service = ImportService(db_session)
    await service.parse_job(job_id, actor_kind="user")
    await service.validate_job(job_id, actor_kind="user")

    commit_resp = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit",
        headers={"X-Tenant-Id": tenant_id},
    )
    assert commit_resp.status_code == 200, commit_resp.text

    return job_id


@pytest.mark.asyncio
async def test_import_v2_only_write_min_consistency_query_and_traceability(
    client, db_session_clean
):
    tenant = Tenant(
        name="T1", code=f"t1_{uuid.uuid4()}", is_default=True, is_active=True
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    # Ensure registry exists for table_code inference during v2 parse
    db_session_clean.add_all(
        [
            TableRegistry(table_code="P1", display_name="P1"),
            TableRegistry(table_code="P2", display_name="P2"),
            TableRegistry(table_code="P3", display_name="P3"),
        ]
    )
    await db_session_clean.commit()

    # Use minimal CSVs that are known to pass the current v2 validator.
    # Keep the lot consistent so v2 query and traceability can link P3 -> P2 -> P1.
    p1_csv = "lot_no,quantity\n2507173_02,1\n"
    p2_csv = "lot_no,col1\n2507173_02,val1\n"
    p3_csv = "year-month-day,Machine NO,Mold NO,lot no,lot,Source Winder\n114年09月02日,P24,238-2,2507173_02_17,301,17\n"

    # Import P1/P2/P3 through v2 jobs created from UploadJob (no legacy write assumptions)
    await _upload_and_commit_v2(
        client,
        db_session_clean,
        str(tenant.id),
        "P1",
        "P1_2507173_02.csv",
        p1_csv.encode("utf-8"),
    )
    # winder inferred from filename when absent in rows
    await _upload_and_commit_v2(
        client,
        db_session_clean,
        str(tenant.id),
        "P2",
        "P2_2507173_02_17.csv",
        p2_csv.encode("utf-8"),
    )
    await _upload_and_commit_v2(
        client,
        db_session_clean,
        str(tenant.id),
        "P3",
        "P3_0902_P24_copy.csv",
        p3_csv.encode("utf-8"),
    )

    # 1) v2 query should return records for this lot
    lot_search = "2507173_02"
    query_resp = await client.get(
        "/api/v2/query/records",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"lot_no": lot_search, "page": 1, "page_size": 100},
    )
    assert query_resp.status_code == 200, query_resp.text
    body = query_resp.json()

    records = body.get("records") or []
    assert isinstance(records, list) and records, body

    data_types = {r.get("data_type") for r in records if isinstance(r, dict)}
    assert "P1" in data_types, data_types
    assert "P2" in data_types, data_types
    assert "P3" in data_types, data_types

    # 2) traceability should be usable for an imported product_id
    # From P3 test CSV: 114年09月02日 + P24 + 238-2 + lot=301
    product_id = "20250902_P24_238-2_301"
    trace_resp = await client.get(
        f"/api/traceability/product/{product_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert trace_resp.status_code == 200, trace_resp.text
    trace = trace_resp.json()

    assert trace.get("product_id") == product_id
    assert trace.get("p3") is not None
    assert trace.get("p2") is not None
    assert trace.get("p1") is not None
    assert trace.get("trace_complete") is True
