import uuid
from typing import Any, Optional

from app.core.config import get_settings
from app.core import database
from app.models.core.audit_event import AuditEvent


def _is_enabled() -> bool:
    settings = get_settings()
    return bool(getattr(settings, "audit_events_enabled", False))


async def write_audit_event_best_effort(
    *,
    tenant_id: Optional[uuid.UUID],
    actor_api_key_id: Optional[uuid.UUID] = None,
    actor_label_snapshot: Optional[str] = None,
    request_id: Optional[str] = None,
    method: str,
    path: str,
    status_code: int,
    action: str,
    metadata: Optional[dict[str, Any]] = None,
    client_host: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Persist an AuditEvent if enabled.

    Best-effort / non-blocking:
    - Never raises
    - Never stores raw API keys or request bodies

    Notes:
    - Uses global `database.async_session_factory` so call-sites don't need to
      reuse their request/session transaction.
    """

    if not _is_enabled():
        return

    if database.async_session_factory is None:
        return

    try:
        async with database.async_session_factory() as db:
            db.add(
                AuditEvent(
                    tenant_id=tenant_id,
                    actor_api_key_id=actor_api_key_id,
                    actor_label_snapshot=actor_label_snapshot,
                    request_id=str(request_id) if request_id else None,
                    method=(method or "").upper() or "INTERNAL",
                    path=str(path or "/internal"),
                    status_code=int(status_code or 0),
                    client_host=client_host,
                    user_agent=user_agent,
                    action=str(action or "http.request"),
                    metadata_json=metadata or {},
                )
            )
            await db.commit()
    except Exception:
        # Best-effort: never block user requests due to audit logging.
        return
