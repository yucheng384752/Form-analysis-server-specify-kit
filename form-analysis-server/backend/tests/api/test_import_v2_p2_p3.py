import pytest
import uuid
import shutil
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.core.schema_registry import TableRegistry
from app.core.config import get_settings
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.services.import_v2 import ImportService
from app.models.import_job import ImportJobStatus
from sqlalchemy import select

settings = get_settings()

@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_import_p2_job(client, db_session):
    # Setup Tenant
    stmt = select(Tenant).where(Tenant.code == "test_tenant_p2")
    result = await db_session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name="Test Tenant P2", code="test_tenant_p2", is_default=True)
        db_session.add(tenant)
    
    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P2")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P2", display_name="P2 Records")
        db_session.add(table)
    
    await db_session.commit()
    
    # Prepare CSV content
    csv_content = "col1,col2\nval1,val2"
    filename = "P2_Lot123_05.csv"
    
    files = [('files', (filename, csv_content.encode('utf-8'), 'text/csv'))]
    data = {'table_code': 'P2'}
    headers = {"X-Tenant-Id": str(tenant.id)}
    
    # 1. Create Job
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
    assert response.status_code == 201
    job_id = response.json()["id"]
    
    # 2. Parse Job
    service = ImportService(db_session)
    job = await service.parse_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.VALIDATING
    
    # 3. Validate Job
    job = await service.validate_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.READY
    
    # 4. Commit Job
    job = await service.commit_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.COMPLETED
    
    # 5. Verify P2Record
    # Lot123_05 -> 12305
    stmt = select(P2Record).where(P2Record.lot_no_norm == 12305)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    
    assert record is not None
    assert record.winder_number == 5
    assert record.extras["rows"][0]["col1"] == "val1"
    
    # Cleanup
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

@pytest.mark.asyncio
async def test_import_p3_job(client, db_session):
    # Setup Tenant
    stmt = select(Tenant).where(Tenant.code == "test_tenant_p3")
    result = await db_session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name="Test Tenant P3", code="test_tenant_p3", is_default=True)
        db_session.add(tenant)
    
    # Setup TableRegistry
    stmt = select(TableRegistry).where(TableRegistry.table_code == "P3")
    result = await db_session.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        table = TableRegistry(table_code="P3", display_name="P3 Records")
        db_session.add(table)
    
    await db_session.commit()
    
    # Prepare CSV content
    # Include Mold NO in content as it's required and not in filename
    csv_content = "Mold NO,col2\nMold123,val2"
    filename = "P3_2507173_02_17.csv"
    
    files = [('files', (filename, csv_content.encode('utf-8'), 'text/csv'))]
    data = {'table_code': 'P3'}
    headers = {"X-Tenant-Id": str(tenant.id)}
    
    # 1. Create Job
    response = await client.post("/api/v2/import/jobs", files=files, data=data, headers=headers)
    assert response.status_code == 201
    job_id = response.json()["id"]
    
    # 2. Parse Job
    service = ImportService(db_session)
    job = await service.parse_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.VALIDATING
    
    # 3. Validate Job
    job = await service.validate_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.READY
    
    # 4. Commit Job
    job = await service.commit_job(uuid.UUID(job_id))
    assert job.status == ImportJobStatus.COMPLETED
    
    # 5. Verify P3Record
    # 2507173 -> 2025-07-17
    stmt = select(P3Record).where(P3Record.production_date_yyyymmdd == 20250717)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    
    assert record is not None
    assert record.machine_no == "02"
    assert record.mold_no == "Mold123"
    
    # Verify product_id
    # P3_2507173_02_17.csv -> digits: 25071730217
    # Date: 20250717
    # Machine: 02
    # Mold: Mold123
    # Lot: 25071730217
    expected_product_id = "20250717-02-Mold123-25071730217"
    assert record.product_id == expected_product_id
    
    # Cleanup
    upload_dir = Path(settings.upload_temp_dir) / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
