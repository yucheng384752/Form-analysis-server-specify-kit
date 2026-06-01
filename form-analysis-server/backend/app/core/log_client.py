"""
LogCollectClient — sends heartbeats and structured user logs to a remote monitor server.

Ported from the standalone client package; uses httpx (already in project deps)
instead of requests so no extra dependency is needed.
"""

import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

_TZ_TAIPEI = timezone(timedelta(hours=8))


class LogCollectClient:
    def __init__(
        self,
        server_url: str,
        source: str,
        host: str | None = None,
        timeout: int = 5,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.source = source
        self.host = host or socket.gethostname()
        self.timeout = timeout
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def send_log(
        self,
        action: str,
        state: str,
        describe: str,
        timestemp: datetime | None = None,
        level: str = "INFO",
    ) -> dict[str, Any]:
        payload = {
            "Action": action,
            "State": state,
            "Timestemp": self._format_time(timestemp or datetime.now(_TZ_TAIPEI)),
            "Describe": describe,
            "source": self.source,
            "host": self.host,
            "level": level,
        }
        return self._post("/api/logs", payload)

    def send_heartbeat(
        self,
        state: str = "alive",
        timestemp: datetime | None = None,
    ) -> dict[str, Any]:
        payload = {
            "source": self.source,
            "host": self.host,
            "State": state,
            "Timestemp": self._format_time(timestemp or datetime.now(_TZ_TAIPEI)),
        }
        return self._post("/api/heartbeat", payload)

    def start_heartbeat(self, interval_seconds: int = 60) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)

    def _heartbeat_loop(self, interval_seconds: int) -> None:
        while not self._heartbeat_stop.is_set():
            try:
                self.send_heartbeat()
            except Exception:
                # Never block the main system on monitor failure.
                pass
            self._heartbeat_stop.wait(interval_seconds)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.server_url}{path}",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _format_time(value: datetime) -> str:
        # Convert aware datetimes to UTC+8; treat naive as UTC+8 directly.
        if value.tzinfo is not None:
            value = value.astimezone(_TZ_TAIPEI)
        return value.strftime("%Y-%m-%d %H:%M:%S+08:00")
