import shutil
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record

settings = get_settings()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Override tenant dependency to avoid header requirement if needed,
    # but our test setup creates a default tenant so it should work automatically.

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)

    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare file
    files = [
        ("files", ("test1.csv", b"content1", "text/csv")),
        ("files", ("test2.csv", b"content2", "text/csv")),
    ]
    data = {"table_code": "P1"}

    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )

    assert response.status_code == 201, response.text
    json_resp = response.json()
    assert json_resp["batch_id"] is not None
    assert json_resp["total_files"] == 2
    assert len(json_resp["files"]) == 2
    assert json_resp["files"][0]["filename"] in ["test1.csv", "test2.csv"]

    # Cleanup uploaded files
    job_id = json_resp["id"]
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)


@pytest.mark.asyncio
async def test_create_import_job_invalid_table(client, db_session):
    # Setup Tenant
    tenant = Tenant(
        name=f"Test Tenant 2 {uuid.uuid4()}",
        code=f"test_tenant_2_{uuid.uuid4()}",
        is_default=False,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    files = [("files", ("test.csv", b"content", "text/csv"))]
    data = {"table_code": "INVALID"}

    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )

    assert response.status_code == 400, response.text


from sqlalchemy import select

from app.models.import_job import ImportJobStatus, StagingRow
from app.services.import_v2 import ImportService


@pytest.mark.asyncio
async def test_parse_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant 3", code="test_tenant_3", is_default=True)
    db_session.add(tenant)

    # Setup TableRegistry
    # Check if exists first to avoid unique constraint error if fixture didn't clean up
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare CSV content
    csv_content = "col1,col2\nval1,val2\nval3,val4"

    files = [("files", ("data.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    if response.status_code != 201:
        print(response.json())
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Run Parse Service
    service = ImportService(db_session)
    job = await service.parse_job(uuid.UUID(job_id))

    assert job.status == ImportJobStatus.VALIDATING
    assert job.total_rows == 2

    # 3. Verify Staging Rows
    stmt = (
        select(StagingRow)
        .where(StagingRow.job_id == job.id)
        .order_by(StagingRow.row_index)
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 2
    assert rows[0].parsed_json == {"col1": "val1", "col2": "val2"}
    assert rows[1].parsed_json == {"col1": "val3", "col2": "val4"}

    # Cleanup
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)


@pytest.mark.asyncio
async def test_validate_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant 4", code="test_tenant_4", is_default=True)
    db_session.add(tenant)

    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare CSV content (P1 validation should verify LOT NO from row content)
    csv_content = (
        "lot_no,Any,Other\n2503033_01,10.5,abc\n2503033_01,Invalid,def\n2503033_01,,ghi"
    )

    files = [("files", ("P1_2503033_01.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Run Parse Service
    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))

    # 3. Run Validate Service
    job = await service.validate_job(uuid.UUID(job_id))

    assert job.status == ImportJobStatus.READY

    # 4. Verify Staging Rows
    stmt = (
        select(StagingRow)
        .where(StagingRow.job_id == job.id)
        .order_by(StagingRow.row_index)
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 3

    # All rows valid as long as LOT NO is present in row content
    assert rows[0].is_valid is True
    assert rows[0].errors_json == []
    assert rows[1].is_valid is True
    assert rows[1].errors_json == []
    assert rows[2].is_valid is True
    assert rows[2].errors_json == []

    # Cleanup
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)


@pytest.mark.asyncio
async def test_validate_import_job_ignores_leading_blank_rows(client, db_session):
    tenant = Tenant(
        name="Test Tenant Blank Rows",
        code=f"test_tenant_blank_rows_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)

    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Include multiple blank rows before the first valid row.
    csv_content = (
        "lot_no,Any,Other\n"
        ",,\n"
        " , , \n"
        ",,\n"
        "2503033_01,10.5,abc\n"
    )
    files = [("files", ("P1_2503033_01.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]

    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))
    job = await service.validate_job(uuid.UUID(job_id))

    assert job.status == ImportJobStatus.READY
    assert int(job.error_count or 0) == 0
    assert int(job.total_rows or 0) == 1

    stmt = (
        select(StagingRow)
        .where(StagingRow.job_id == uuid.UUID(job_id))
        .order_by(StagingRow.row_index)
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].is_valid is True
    assert rows[0].errors_json == []
    assert rows[0].parsed_json.get("lot_no") == "2503033_01"

    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)


@pytest.mark.asyncio
async def test_commit_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant 5", code="test_tenant_5", is_default=True)
    db_session.add(tenant)

    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare CSV content
    # lot_no is extracted from row content
    csv_content = "lot_no,Line Speed(M/min),Screw Pressure(psi)\n2503033_01,10.5,100.2"

    files = [("files", ("P1_2503033_01.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    # 1. Create Job
    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Parse Job
    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))

    # 3. Validate Job
    await service.validate_job(uuid.UUID(job_id))

    # 4. Commit Job
    response = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit", headers=headers
    )
    assert response.status_code == 200
    job_data = response.json()
    assert job_data["status"] == "COMPLETED"

    # 5. Verify P1Record
    stmt = select(P1Record).where(P1Record.lot_no_norm == 250303301)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()

    assert record is not None


@pytest.mark.asyncio
async def test_commit_import_job_p1_business_key_merge(client, db_session):
    tenant = Tenant(
        name="Test Tenant P1 Merge",
        code=f"test_tenant_p1_merge_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)

    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    csv_1 = "lot_no,product_name\n2503033_01,ProdA"
    csv_2 = "lot_no,material_code\n2503033_01,MatX"

    files = [
        ("files", ("P1_2503033_01_part1.csv", csv_1.encode("utf-8"), "text/csv")),
        ("files", ("P1_2503033_01_part2.csv", csv_2.encode("utf-8"), "text/csv")),
    ]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]

    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))
    await service.validate_job(uuid.UUID(job_id))

    response = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"

    stmt = select(P1Record).where(
        P1Record.tenant_id == tenant.id, P1Record.lot_no_norm == 250303301
    )
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()

    assert record is not None
    assert record.extras is not None
    assert "rows" in record.extras
    assert len(record.extras["rows"]) == 1
    row = record.extras["rows"][0]
    assert row.get("product_name") == "ProdA"
    assert row.get("material_code") == "MatX"


@pytest.mark.asyncio
async def test_commit_import_job_p2_business_key_merge(client, db_session):
    suffix = uuid.uuid4()
    tenant = Tenant(
        name=f"Test Tenant P2 Merge {suffix}",
        code=f"test_tenant_p2_merge_{suffix}",
        is_default=True,
    )
    db_session.add(tenant)

    stmt = select(TableRegistry).where(TableRegistry.table_code == "P2")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P2", display_name="P2 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    csv_1 = "lot_no,winder_number,sheet_width\n2503033_01,5,100"
    csv_2 = "lot_no,winder_number,appearance\n2503033_01,5,OK"

    files = [
        ("files", ("P2_2503033_01_part1.csv", csv_1.encode("utf-8"), "text/csv")),
        ("files", ("P2_2503033_01_part2.csv", csv_2.encode("utf-8"), "text/csv")),
    ]
    data = {"table_code": "P2"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]

    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))
    await service.validate_job(uuid.UUID(job_id))

    response = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"

    stmt = select(P2Record).where(
        P2Record.tenant_id == tenant.id,
        P2Record.lot_no_norm == 250303301,
        P2Record.winder_number == 5,
    )
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()

    assert record is not None
    assert record.extras is not None
    assert "rows" in record.extras
    assert len(record.extras["rows"]) == 1
    row = record.extras["rows"][0]
    assert row.get("sheet_width") == "100"
    assert row.get("appearance") == "OK"

    item_stmt = select(P2ItemV2).where(P2ItemV2.p2_record_id == record.id)
    item_result = await db_session.execute(item_stmt)
    item = item_result.scalar_one_or_none()
    assert item is not None
    assert item.trace_lot_no == "2503033_01_05"


@pytest.mark.asyncio
async def test_get_import_job_errors(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant 6", code="test_tenant_6", is_default=True)
    db_session.add(tenant)

    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare CSV content; trigger errors by missing lot_no in content
    csv_content = "lot_no,Any,Other\n,1,100.2"

    files = [("files", ("P1_anyname.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    # 1. Create Job
    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Parse Job
    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))

    # 3. Validate Job
    await service.validate_job(uuid.UUID(job_id))

    # 4. Get Errors
    response = await client.get(f"/api/v2/import/jobs/{job_id}/errors", headers=headers)
    assert response.status_code == 200
    errors = response.json()

    assert len(errors) > 0
    assert errors[0]["row_index"] == 1
    # Check if errors list is not empty
    assert len(errors[0]["errors"]) > 0


@pytest.mark.asyncio
async def test_cancel_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant 7", code="test_tenant_7", is_default=True)
    db_session.add(tenant)

    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P1")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session.add(table)

    await db_session.commit()
    await db_session.refresh(tenant)

    # Prepare CSV content
    csv_content = "Line Speed(M/min),Screw Pressure(psi)\n10.5,100.2"

    files = [("files", ("P1_cancel.csv", csv_content.encode("utf-8"), "text/csv"))]
    data = {"table_code": "P1"}
    headers = {"X-Tenant-Id": str(tenant.id)}

    # 1. Create Job
    response = await client.post(
        "/api/v2/import/jobs", files=files, data=data, headers=headers
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Cancel Job
    response = await client.post(
        f"/api/v2/import/jobs/{job_id}/cancel", headers=headers
    )
    assert response.status_code == 200
    job_data = response.json()
    assert job_data["status"] == "CANCELLED"

    # 3. Verify Status via GET
    response = await client.get(f"/api/v2/import/jobs/{job_id}", headers=headers)
    assert response.json()["status"] == "CANCELLED"

    # Cleanup
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
