from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_frontend_sources_do_not_call_legacy_query_api():
    """Guardrail: legacy `/api/query/*` routes were removed.

    This test prevents accidentally reintroducing frontend calls to them.
    """

    repo_root = Path(__file__).resolve().parents[2]  # .../form-analysis-server
    src_root = repo_root / "frontend" / "src"

    assert src_root.exists(), f"Missing frontend source dir: {src_root}"

    needle = "/api/query"
    offenders: list[str] = []

    for path in src_root.rglob("*.ts*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            offenders.append(str(path.relative_to(repo_root)).replace("\\", "/"))

    assert offenders == [], f"Found legacy query API usages: {offenders}"
