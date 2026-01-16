import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
from app.models.core.tenant import Tenant


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


def _pdf_bytes() -> bytes:
    # Minimal PDF content with correct header.
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _pdf_filename() -> str:
    return "test.pdf"


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_no_tenants_returns_404(client):
    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post("/api/upload/pdf", files=files)

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert "detail" in body
    assert "No tenants exist" in body["detail"]


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_single_tenant_allows_missing_header(client, db_session_clean):
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post("/api/upload/pdf", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert set(data.keys()) >= {"process_id", "total_rows", "valid_rows", "invalid_rows", "sample_errors"}
    assert data["total_rows"] == 0
    assert data["valid_rows"] == 0
    assert data["invalid_rows"] == 0
    assert isinstance(data["sample_errors"], list)

    # Verify file saved to disk
    process_id = uuid.UUID(str(data["process_id"]))
    settings = get_settings()
    target_path = Path(settings.upload_temp_dir) / "pdf" / f"{process_id}.pdf"
    assert target_path.exists()

    # Cleanup to keep repo workspace tidy
    try:
        target_path.unlink(missing_ok=True)
    except TypeError:
        # Python <3.8 compatibility (unlikely here), keep safe
        if target_path.exists():
            target_path.unlink()


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_multiple_tenants_no_default_requires_header(client, db_session_clean):
    t1 = Tenant(name="T1", code="t1", is_default=False, is_active=True)
    t2 = Tenant(name="T2", code="t2", is_default=False, is_active=True)
    db_session_clean.add_all([t1, t2])
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post("/api/upload/pdf", files=files)

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" in body
    assert "X-Tenant-Id header is required" in body["detail"]


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_unique_default_allows_missing_header(client, db_session_clean):
    t1 = Tenant(name="T1", code="t1", is_default=False, is_active=True)
    t2 = Tenant(name="T2", code="t2", is_default=True, is_active=True)
    db_session_clean.add_all([t1, t2])
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post("/api/upload/pdf", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    process_id = uuid.UUID(str(data["process_id"]))
    settings = get_settings()
    target_path = Path(settings.upload_temp_dir) / "pdf" / f"{process_id}.pdf"
    assert target_path.exists()

    # Cleanup
    try:
        target_path.unlink(missing_ok=True)
    except TypeError:
        if target_path.exists():
            target_path.unlink()


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_invalid_header_returns_422(client, db_session_clean):
    # Even if tenants exist, invalid header should 422.
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post("/api/upload/pdf", files=files, headers={"X-Tenant-Id": "not-a-uuid"})

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body.get("detail") == "Invalid X-Tenant-Id format"


@pytest.mark.asyncio
async def test_tenant_scoped_pdf_upload_missing_tenant_returns_404(client, db_session_clean):
    # tenant in DB exists, but header points to a different tenant id.
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    files = {"file": (_pdf_filename(), _pdf_bytes(), "application/pdf")}
    resp = await client.post(
        "/api/upload/pdf",
        files=files,
        headers={"X-Tenant-Id": str(uuid.uuid4())},
    )

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body.get("detail") == "Tenant not found"
