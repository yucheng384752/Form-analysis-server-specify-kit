import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_no_legacy_query_paths_in_openapi():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")

    assert resp.status_code == 200, resp.text
    schema = resp.json()
    paths: dict = schema.get("paths") or {}

    # Legacy query router (v1) should not exist; query must go through /api/v2/query/*
    bad_prefixes = ("/api/query", "/api/query/")
    offenders = [p for p in paths.keys() if any(p.startswith(bp) for bp in bad_prefixes)]
    assert offenders == []
