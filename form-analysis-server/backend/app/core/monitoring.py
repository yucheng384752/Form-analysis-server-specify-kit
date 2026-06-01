"""
Remote monitoring service — heartbeat + user/system log forwarding.

Integrates with the project's structlog pipeline and provides a simple
fire-and-forget API for sending user-action logs to the central monitor.

Lifecycle (called from main.py lifespan):
    init_monitoring(server_url, source)
    start_heartbeat(interval_seconds)
    ...
    stop_heartbeat()

Usage from any route handler:
    from app.core.monitoring import report_user_action
    report_user_action("login", "success", f"user {username} from {client_ip}")
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.log_client import LogCollectClient

_logger = logging.getLogger(__name__)

_client: LogCollectClient | None = None
# 2 workers: one for heartbeat overflow, one for user logs — keeps queue shallow
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="monitor")


def init_monitoring(server_url: str, source: str, host: str | None = None) -> None:
    """Initialise the client. Must be called before start_heartbeat / report."""
    global _client
    _client = LogCollectClient(server_url=server_url, source=source, host=host)
    _logger.info("Monitoring initialised → %s (source=%s)", server_url, source)


def start_heartbeat(interval_seconds: int = 60) -> None:
    """Start the background heartbeat thread. No-op if monitoring is disabled."""
    if _client is None:
        return
    _client.start_heartbeat(interval_seconds)
    _logger.info("Heartbeat started (interval=%ds)", interval_seconds)


def stop_heartbeat() -> None:
    """Stop the heartbeat thread gracefully. No-op if monitoring is disabled."""
    if _client is None:
        return
    _client.stop_heartbeat()
    _logger.info("Heartbeat stopped")


def report_user_action(
    action: str,
    state: str,
    describe: str,
    level: str = "INFO",
) -> None:
    """
    Fire-and-forget: send a structured user-action log to the monitor.

    Never raises; never blocks the caller.  Safe to call from any context.

    Args:
        action:   What the user did, e.g. "login", "upload_p1", "query".
        state:    Outcome or page context, e.g. "success", "failed", "upload_page".
        describe: Human-readable detail, e.g. "user demo_manager from 10.0.0.1".
        level:    Log severity — "INFO" | "WARNING" | "ERROR".
    """
    if _client is None:
        return
    _executor.submit(_safe_send, action, state, describe, level)


def report_system_event(
    action: str,
    state: str,
    describe: str,
    level: str = "WARNING",
) -> None:
    """
    Same as report_user_action but signals a system/infrastructure event.
    Defaults to WARNING so it surfaces in monitor dashboards.
    """
    report_user_action(action, state, describe, level)


def make_structlog_processor(min_level: str = "WARNING"):
    """
    Returns a structlog processor that forwards logs at or above `min_level`
    to the remote monitor (fire-and-forget).

    Insert this into the structlog processor chain *before* the final renderer
    so the event_dict is still a plain dict.

    Example:
        processors = [
            ...
            monitoring.make_structlog_processor("WARNING"),
            structlog.processors.JSONRenderer(),
        ]
    """
    _forward_levels = {"WARNING", "WARN", "ERROR", "CRITICAL"}
    if min_level.upper() not in _forward_levels:
        _forward_levels = {"WARNING", "WARN", "ERROR", "CRITICAL"}

    def _processor(logger_obj, method: str, event_dict: dict) -> dict:
        level = (event_dict.get("level") or "").upper()
        if level not in _forward_levels:
            return event_dict
        if _client is None:
            return event_dict
        try:
            _executor.submit(
                _safe_send,
                method,                                      # action = log method
                level,                                       # state  = log level
                str(event_dict.get("event", ""))[:500],     # describe = message
                level,
            )
        except Exception:
            pass  # monitoring must never break logging
        return event_dict

    return _processor


def _safe_send(action: str, state: str, describe: str, level: str) -> None:
    """Internal: actual HTTP call, runs inside the executor thread."""
    try:
        assert _client is not None
        _client.send_log(action=action, state=state, describe=describe, level=level)
    except Exception as exc:
        # Log locally at DEBUG so it doesn't re-trigger the processor loop.
        _logger.debug("Monitor send_log failed: %s", exc)
