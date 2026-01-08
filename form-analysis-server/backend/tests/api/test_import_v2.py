import pytest
import uuid
import shutil
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_db, get_current_tenant
from app.models.core.tenant import Tenant
from app.models.core.schema_registry import TableRegistry
from app.core.config import get_settings
from app.models.p1_record import P1Record

settings = get_settings()

@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Override tenant dependency to avoid header requirement if needed, 
    # but our test setup creates a default tenant so it should work automatically.
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_import_job(client, db_session):
    # Setup Tenant
    tenant = Tenant(name="Test Tenant", code="test_tenant", is_default=True)
    db_session.add(tenant)
    
    # Setup TableRegistry
    table = TableRegistry(table_code="P1", display_name="P1 Records")
    db_session.add(table)
    
    await db_session.commit()
    
    # Prepare file
    files = [
        ('files', ('test1.csv', b'content1', 'text/csv')),
        ('files', ('test2.csv', b'content2', 'text/csv'))
    ]
    data = {'table_code': 'P1'}
    
    response = await client.post("/api/v2/import/jobs", files=files, data=data)
    
    assert response.status_code == 201
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
    tenant = Tenant(name="Test Tenant 2", code="test_tenant_2", is_default=False)
    db_session.add(tenant)
    await db_session.commit()
    
    files = [('files', ('test.csv', b'content', 'text/csv'))]
    data = {'table_code': 'INVALID'}
    
    response = await client.post("/api/v2/import/jobs", files=files, data=data)
    
    assert response.status_code == 400

from app.services.import_v2 import ImportService
from app.models.import_job import ImportJobStatus, StagingRow
from sqlalchemy import select

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
    
    files = [
        ('files', ('data.csv', csv_content.encode('utf-8'), 'text/csv'))
    ]
    data = {'table_code': 'P1'}
    headers = {'X-Tenant-Id': str(tenant.id)}
    
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
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
    stmt = select(StagingRow).where(StagingRow.job_id == job.id).order_by(StagingRow.row_index)
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
    
    # Prepare CSV content with P1 headers
    # Required: Line Speed(M/min), Screw Pressure(psi)
    csv_content = "Line Speed(M/min),Screw Pressure(psi),Other\n10.5,100,abc\nInvalid,200,def\n,300,ghi"
    
    files = [
        ('files', ('data_val.csv', csv_content.encode('utf-8'), 'text/csv'))
    ]
    data = {'table_code': 'P1'}
    headers = {'X-Tenant-Id': str(tenant.id)}
    
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
    assert response.status_code == 201
    job_id = response.json()["id"]
    
    # 2. Run Parse Service
    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))
    
    # 3. Run Validate Service
    job = await service.validate_job(uuid.UUID(job_id))
    
    assert job.status == ImportJobStatus.READY
    
    # 4. Verify Staging Rows
    stmt = select(StagingRow).where(StagingRow.job_id == job.id).order_by(StagingRow.row_index)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    
    assert len(rows) == 3
    
    # Row 1: Valid
    assert rows[0].is_valid == True
    assert rows[0].errors_json == []
    
    # Row 2: Invalid (Line Speed is "Invalid")
    assert rows[1].is_valid == False
    assert len(rows[1].errors_json) > 0
    assert rows[1].errors_json[0]["field"] == "Line Speed(M/min)"
    
    # Row 3: Invalid (Line Speed is empty)
    assert rows[2].is_valid == False
    assert len(rows[2].errors_json) > 0
    
    # Cleanup
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
    # P1_2503033_01.csv -> Lot No: 250303301
    csv_content = "Line Speed(M/min),Screw Pressure(psi)\n10.5,100.2"
    
    files = [('files', ('P1_2503033_01.csv', csv_content.encode('utf-8'), 'text/csv'))]
    data = {'table_code': 'P1'}
    headers = {'X-Tenant-Id': str(tenant.id)}
    
    # 1. Create Job
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
    assert response.status_code == 201
    job_id = response.json()["id"]
    
    # 2. Parse Job
    service = ImportService(db_session)
    await service.parse_job(uuid.UUID(job_id))
    
    # 3. Validate Job
    await service.validate_job(uuid.UUID(job_id))
    
    # 4. Commit Job
    response = await client.post(f"/api/v2/import/jobs/{job_id}/commit", headers=headers)
    assert response.status_code == 200
    job_data = response.json()
    assert job_data["status"] == "COMPLETED"

    
    # 5. Verify P1Record
    stmt = select(P1Record).where(P1Record.lot_no_norm == 250303301)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    
    assert record is not None

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
    
    # Prepare CSV content with errors
    # Missing required field
    csv_content = "Line Speed(M/min),Screw Pressure(psi)\n,100.2"
    
    files = [('files', ('P1_error.csv', csv_content.encode('utf-8'), 'text/csv'))]
    data = {'table_code': 'P1'}
    headers = {'X-Tenant-Id': str(tenant.id)}
    
    # 1. Create Job
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
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
    
    files = [('files', ('P1_cancel.csv', csv_content.encode('utf-8'), 'text/csv'))]
    data = {'table_code': 'P1'}
    headers = {'X-Tenant-Id': str(tenant.id)}
    
    # 1. Create Job
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
    assert response.status_code == 201
    job_id = response.json()["id"]
    
    # 2. Cancel Job
    response = await client.post(f"/api/v2/import/jobs/{job_id}/cancel", headers=headers)
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
