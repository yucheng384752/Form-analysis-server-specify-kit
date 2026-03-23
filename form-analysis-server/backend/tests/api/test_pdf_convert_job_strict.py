import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
from app.models.core.tenant import Tenant


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _pdf_filename() -> str:
    return "test.pdf"


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_convert_status_not_started(client, db_session_clean):
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    upload_resp = await client.post(
        "/api/upload/pdf", files=files, headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert upload_resp.status_code == 200, upload_resp.text
    process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    status_resp = await client.get(
        f"/api/upload/pdf/{process_id}/convert/status",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["status"] == "NOT_STARTED"


@pytest.mark.asyncio
async def test_pdf_convert_trigger_creates_job_and_status(
    client, db_session_clean, monkeypatch
):
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    # Mock pdf_server_url so endpoint doesn't return 503
    settings = get_settings()
    monkeypatch.setattr(settings, "pdf_server_url", "http://fake-pdf-server:8080")

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    upload_resp = await client.post(
        "/api/upload/pdf", files=files, headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert upload_resp.status_code == 200, upload_resp.text
    process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    trigger_resp = await client.post(
        f"/api/upload/pdf/{process_id}/convert",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert trigger_resp.status_code == 200, trigger_resp.text
    trigger_body = trigger_resp.json()
    assert trigger_body["status"] == "QUEUED"
    assert "job_id" in trigger_body

    status_resp = await client.get(
        f"/api/upload/pdf/{process_id}/convert/status",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["status"] == "QUEUED"
    assert body["job_id"] == trigger_body["job_id"]

    # Cleanup uploaded file to keep workspace tidy
    pdf_path = Path(settings.upload_temp_dir) / "pdf" / f"{process_id}.pdf"
    try:
        pdf_path.unlink(missing_ok=True)
    except TypeError:
        if pdf_path.exists():
            pdf_path.unlink()


@pytest.mark.asyncio
async def test_pdf_convert_is_tenant_scoped(client, db_session_clean, monkeypatch):
    t1 = Tenant(name="T1", code="t1", is_default=False, is_active=True)
    t2 = Tenant(name="T2", code="t2", is_default=True, is_active=True)
    db_session_clean.add_all([t1, t2])
    await db_session_clean.commit()

    # Mock pdf_server_url so endpoint doesn't return 503 before tenant check
    settings = get_settings()
    monkeypatch.setattr(settings, "pdf_server_url", "http://fake-pdf-server:8080")

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    upload_resp = await client.post(
        "/api/upload/pdf", files=files, headers={"X-Tenant-Id": str(t1.id)}
    )
    assert upload_resp.status_code == 200, upload_resp.text
    process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    other_tenant_trigger = await client.post(
        f"/api/upload/pdf/{process_id}/convert",
        headers={"X-Tenant-Id": str(t2.id)},
    )
    assert other_tenant_trigger.status_code == 404, other_tenant_trigger.text

    # Cleanup
    pdf_path = Path(settings.upload_temp_dir) / "pdf" / f"{process_id}.pdf"
    try:
        pdf_path.unlink(missing_ok=True)
    except TypeError:
        if pdf_path.exists():
            pdf_path.unlink()
