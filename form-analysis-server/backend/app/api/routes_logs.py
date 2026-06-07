import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["logs"])

LOGS_DIR = Path("logs")


def _normalize_log_level(level: str) -> str:
    normalized = str(level or "").upper()
    if normalized == "WARN":
        return "WARNING"
    return normalized


def _require_log_admin(request: Request) -> None:
    state = getattr(request, "state", None)
    if bool(getattr(state, "is_admin", False)):
        return
    if getattr(state, "actor_role", None) == "manager":
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Manager privileges required",
    )


class LogEntry:
    def __init__(self, line: str, line_number: int):
        self.line_number = line_number
        self.raw_line = line

        try:
            data = json.loads(line.strip())
            self.timestamp = data.get("timestamp", "")
            self.level = data.get("level", "INFO")
            self.message = data.get("message", "")
            self.extra_data = {
                k: v
                for k, v in data.items()
                if k not in ["timestamp", "level", "message"]
            }
            self.is_json = True
        except (json.JSONDecodeError, AttributeError):
            self.timestamp = ""
            self.level = "INFO"
            self.message = line.strip()
            self.extra_data = {}
            self.is_json = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "extra_data": self.extra_data,
            "is_json": self.is_json,
            "raw_line": self.raw_line,
        }


def get_log_files() -> dict[str, Path]:
    log_files: dict[str, Path] = {}

    if LOGS_DIR.exists():
        app_log = LOGS_DIR / "app.log"
        error_log = LOGS_DIR / "error.log"

        if app_log.exists():
            log_files["app"] = app_log
        if error_log.exists():
            log_files["error"] = error_log

        for backup_file in LOGS_DIR.glob("*.log.*"):
            if backup_file.is_file():
                log_files[backup_file.name] = backup_file

    return log_files


def parse_time_filter(
    hours: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> tuple[datetime | None, datetime | None]:
    now = datetime.now(UTC)

    if hours:
        return now - timedelta(hours=hours), now

    if start_time and end_time:
        try:
            return (
                datetime.fromisoformat(start_time.replace("Z", "+00:00")),
                datetime.fromisoformat(end_time.replace("Z", "+00:00")),
            )
        except ValueError:
            return None, None

    return None, None


@router.get("/files")
async def list_log_files(request: Request):
    _require_log_admin(request)
    try:
        log_files = get_log_files()
        result = {}
        for name, path in log_files.items():
            stat = path.stat()
            result[name] = {
                "name": name,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(path),
            }

        logger.info("Log files listed", file_count=len(result))
        return {"files": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list log files", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get log files")


@router.get("/view/{log_type}")
async def view_logs(
    request: Request,
    log_type: str,
    limit: int = Query(50, ge=1, le=1000, description="Number of entries"),
    offset: int = Query(0, ge=0, description="Offset"),
    level: str | None = Query(None, description="Log level filter"),
    search: str | None = Query(None, description="Message search filter"),
    hours: int | None = Query(None, ge=1, description="Recent hours filter"),
    start_time: str | None = Query(None, description="Start time (ISO format)"),
    end_time: str | None = Query(None, description="End time (ISO format)"),
):
    _require_log_admin(request)
    try:
        log_files = get_log_files()
        if log_type not in log_files:
            raise HTTPException(
                status_code=404, detail=f"Log file '{log_type}' not found"
            )

        entries: list[LogEntry] = []
        with open(log_files[log_type], encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    entries.append(LogEntry(line, i))

        start_dt, end_dt = parse_time_filter(hours, start_time, end_time)
        if start_dt and end_dt:
            filtered_entries = []
            for entry in entries:
                if not entry.timestamp:
                    continue
                try:
                    entry_time = datetime.fromisoformat(
                        entry.timestamp.replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
                if start_dt <= entry_time <= end_dt:
                    filtered_entries.append(entry)
            entries = filtered_entries

        if level:
            requested_level = _normalize_log_level(level)
            entries = [
                e for e in entries if _normalize_log_level(e.level) == requested_level
            ]

        if search:
            entries = [e for e in entries if search.lower() in e.message.lower()]

        total = len(entries)
        result_entries = [
            entry.to_dict() for entry in entries[offset : offset + limit]
        ]

        logger.info(
            "Logs viewed",
            log_type=log_type,
            total=total,
            returned=len(result_entries),
        )

        return {
            "logs": result_entries,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            },
            "filters": {
                "log_type": log_type,
                "level": level,
                "search": search,
                "hours": hours,
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to view logs", log_type=log_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to view logs: {str(e)}")


@router.get("/stats")
async def get_log_stats(request: Request):
    _require_log_admin(request)
    try:
        log_files = get_log_files()
        stats: dict[str, Any] = {
            "files": {},
            "total_size": 0,
            "level_distribution": defaultdict(int),
            "api_usage": defaultdict(int),
            "recent_activity": [],
        }

        for name, path in log_files.items():
            stat = path.stat()
            stats["files"][name] = {
                "size": stat.st_size,
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "lines": 0,
            }
            stats["total_size"] += stat.st_size

            recent_entries = []
            with open(path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    stats["files"][name]["lines"] = line_num
                    if not line.strip():
                        continue
                    entry = LogEntry(line, line_num)
                    stats["level_distribution"][entry.level] += 1
                    message = entry.message.lower()
                    if "api" in message or "request" in message:
                        stats["api_usage"][entry.level] += 1
                    if len(recent_entries) < 10:
                        recent_entries.append(entry.to_dict())

            stats["recent_activity"] = recent_entries

        stats["level_distribution"] = dict(stats["level_distribution"])
        stats["api_usage"] = dict(stats["api_usage"])
        stats["total_size_mb"] = round(stats["total_size"] / 1024 / 1024, 2)

        logger.info("Log stats calculated", file_count=len(log_files))
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get log statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get log statistics")


@router.get("/search")
async def search_logs(
    request: Request,
    query: str = Query(..., description="Search query"),
    log_type: str = Query("app", description="Log type"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    case_sensitive: bool = Query(False, description="Case-sensitive search"),
):
    _require_log_admin(request)
    try:
        log_files = get_log_files()
        if log_type not in log_files:
            raise HTTPException(
                status_code=404, detail=f"Log file '{log_type}' not found"
            )

        results = []
        search_query = query if case_sensitive else query.lower()
        with open(log_files[log_type], encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line_content = line.strip()
                if not line_content:
                    continue

                search_text = line_content if case_sensitive else line_content.lower()
                if search_query not in search_text:
                    continue

                results.append(LogEntry(line, line_num).to_dict())
                if len(results) >= limit:
                    break

        logger.info(
            "Log search completed",
            query=query,
            log_type=log_type,
            results_count=len(results),
        )
        return {
            "results": results,
            "query": query,
            "log_type": log_type,
            "total_matches": len(results),
            "case_sensitive": case_sensitive,
            "truncated": len(results) >= limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to search logs", query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.delete("/cleanup")
async def cleanup_old_logs(request: Request):
    _require_log_admin(request)
    try:
        if not LOGS_DIR.exists():
            return {"message": "No log directory found", "cleaned_files": []}

        backup_files = list(LOGS_DIR.glob("*.log.*"))
        cleaned_files = []
        total_size = 0

        cutoff_time = datetime.now().timestamp() - (30 * 24 * 60 * 60)
        for file_path in backup_files:
            if file_path.stat().st_mtime < cutoff_time:
                size = file_path.stat().st_size
                file_path.unlink()
                cleaned_files.append(
                    {
                        "filename": file_path.name,
                        "size": size,
                        "size_mb": round(size / 1024 / 1024, 2),
                    }
                )
                total_size += size

        logger.info(
            "Old logs cleaned",
            cleaned_count=len(cleaned_files),
            total_size_mb=round(total_size / 1024 / 1024, 2),
        )
        return {
            "message": f"Successfully cleaned {len(cleaned_files)} backup files",
            "cleaned_files": cleaned_files,
            "total_size_freed": total_size,
            "total_size_freed_mb": round(total_size / 1024 / 1024, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clean logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/download/{log_type}")
async def download_log_file(request: Request, log_type: str):
    _require_log_admin(request)
    try:
        log_files = get_log_files()
        if log_type not in log_files:
            raise HTTPException(
                status_code=404, detail=f"Log file '{log_type}' not found"
            )

        log_file = log_files[log_type]
        logger.info("Log file downloaded", log_type=log_type)
        return FileResponse(
            path=str(log_file),
            filename=f"{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            media_type="text/plain",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download log file", log_type=log_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
