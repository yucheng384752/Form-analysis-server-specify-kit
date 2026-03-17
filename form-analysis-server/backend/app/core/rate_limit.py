"""Shared in-memory rate limiter (sliding window).

Production environments should use Redis + slowapi instead.
"""

import math
import time
from typing import Optional

from fastapi import HTTPException, Request

_store: dict[str, list[float]] = {}


def check_rate_limit(
    request: Request,
    *,
    max_per_minute: int = 30,
    endpoint: Optional[str] = None,
) -> None:
    """Check per-IP rate limit using a 60-second sliding window.

    Args:
        request: The incoming FastAPI request.
        max_per_minute: Maximum allowed requests per minute per IP.
        endpoint: Optional endpoint tag for error messages.

    Raises:
        HTTPException: 429 if rate limit is exceeded.
    """
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - 60

    if client_ip in _store:
        _store[client_ip] = [ts for ts in _store[client_ip] if ts > window_start]
        request_count = len(_store[client_ip])
    else:
        _store[client_ip] = []
        request_count = 0

    if request_count >= max_per_minute:
        oldest_ts = min(_store[client_ip]) if _store[client_ip] else current_time
        retry_after_seconds = max(1, int(math.ceil((oldest_ts + 60) - current_time)))
        endpoint_tag = endpoint or request.url.path
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Max {max_per_minute} requests per minute.",
                "endpoint": endpoint_tag,
                "retry_after_seconds": retry_after_seconds,
                "limit_per_minute": max_per_minute,
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )

    _store[client_ip].append(current_time)
