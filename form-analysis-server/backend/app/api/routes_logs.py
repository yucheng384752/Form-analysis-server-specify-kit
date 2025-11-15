"""
日誌管理 API 路由
提供日誌查看、搜尋、統計等功能
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import re
from collections import defaultdict, Counter

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["logs"])

# 日誌目錄配置
LOGS_DIR = Path("logs")

class LogEntry:
    """日誌條目類"""
    def __init__(self, line: str, line_number: int):
        self.line_number = line_number
        self.raw_line = line
        
        try:
            # 嘗試解析 JSON 格式
            data = json.loads(line.strip())
            self.timestamp = data.get("timestamp", "")
            self.level = data.get("level", "INFO")
            self.message = data.get("message", "")
            self.extra_data = {k: v for k, v in data.items() 
                             if k not in ["timestamp", "level", "message"]}
            self.is_json = True
        except (json.JSONDecodeError, AttributeError):
            # 純文字格式
            self.timestamp = ""
            self.level = "INFO"
            self.message = line.strip()
            self.extra_data = {}
            self.is_json = False
    
    def to_dict(self) -> dict:
        return {
            "line_number": self.line_number,
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "extra_data": self.extra_data,
            "is_json": self.is_json,
            "raw_line": self.raw_line
        }

def get_log_files() -> Dict[str, Path]:
    """獲取可用的日誌檔案"""
    log_files = {}
    
    if LOGS_DIR.exists():
        # 主要日誌檔案
        app_log = LOGS_DIR / "app.log"
        error_log = LOGS_DIR / "error.log"
        
        if app_log.exists():
            log_files["app"] = app_log
        if error_log.exists():
            log_files["error"] = error_log
            
        # 備份日誌檔案
        for backup_file in LOGS_DIR.glob("*.log.*"):
            if backup_file.is_file():
                log_files[backup_file.name] = backup_file
    
    return log_files

def parse_time_filter(hours: Optional[int] = None, 
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> tuple:
    """解析時間過濾條件"""
    now = datetime.now()
    
    if hours:
        start_dt = now - timedelta(hours=hours)
        end_dt = now
    elif start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            start_dt = None
            end_dt = None
    else:
        start_dt = None
        end_dt = None
    
    return start_dt, end_dt

@router.get("/files")
async def list_log_files():
    """列出所有可用的日誌檔案"""
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
                "path": str(path)
            }
        
        logger.info("日誌檔案列表查詢", file_count=len(result))
        return {"files": result}
        
    except Exception as e:
        logger.error("獲取日誌檔案列表失敗", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get log files")

@router.get("/view/{log_type}")
async def view_logs(
    log_type: str,
    limit: int = Query(50, ge=1, le=1000, description="返回的日誌條數"),
    offset: int = Query(0, ge=0, description="跳過的日誌條數"),
    level: Optional[str] = Query(None, description="日誌級別過濾"),
    search: Optional[str] = Query(None, description="搜尋關鍵字"),
    hours: Optional[int] = Query(None, ge=1, description="最近N小時的日誌"),
    start_time: Optional[str] = Query(None, description="開始時間 (ISO format)"),
    end_time: Optional[str] = Query(None, description="結束時間 (ISO format)")
):
    """查看指定類型的日誌"""
    try:
        log_files = get_log_files()
        
        if log_type not in log_files:
            raise HTTPException(status_code=404, detail=f"Log file '{log_type}' not found")
        
        log_file = log_files[log_type]
        
        # 讀取日誌檔案
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 解析日誌條目
        entries = []
        for i, line in enumerate(lines, 1):
            if line.strip():
                entry = LogEntry(line, i)
                entries.append(entry)
        
        # 時間過濾
        start_dt, end_dt = parse_time_filter(hours, start_time, end_time)
        if start_dt and end_dt:
            filtered_entries = []
            for entry in entries:
                if entry.timestamp:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        if start_dt <= entry_time <= end_dt:
                            filtered_entries.append(entry)
                    except ValueError:
                        continue
            entries = filtered_entries
        
        # 級別過濾
        if level:
            entries = [e for e in entries if e.level.upper() == level.upper()]
        
        # 關鍵字搜尋
        if search:
            entries = [e for e in entries if search.lower() in e.message.lower()]
        
        # 分頁
        total = len(entries)
        entries = entries[offset:offset + limit]
        
        # 轉換為字典格式
        result_entries = [entry.to_dict() for entry in entries]
        
        logger.info("日誌查看請求", 
                   log_type=log_type, 
                   total=total, 
                   returned=len(result_entries),
                   filters={
                       "level": level,
                       "search": search,
                       "hours": hours
                   })
        
        return {
            "logs": result_entries,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            },
            "filters": {
                "log_type": log_type,
                "level": level,
                "search": search,
                "hours": hours,
                "start_time": start_time,
                "end_time": end_time
            }
        }
        
    except Exception as e:
        logger.error("查看日誌失敗", log_type=log_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to view logs: {str(e)}")

@router.get("/stats")
async def get_log_stats():
    """獲取日誌統計資訊"""
    try:
        log_files = get_log_files()
        
        stats = {
            "files": {},
            "total_size": 0,
            "level_distribution": defaultdict(int),
            "api_usage": defaultdict(int),
            "recent_activity": []
        }
        
        # 檔案統計
        for name, path in log_files.items():
            file_stat = path.stat()
            stats["files"][name] = {
                "size": file_stat.st_size,
                "size_mb": round(file_stat.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            }
            stats["total_size"] += file_stat.st_size
        
        # 分析主要日誌檔案
        if "app" in log_files:
            with open(log_files["app"], 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            recent_entries = []
            for line in lines[-100:]:  # 分析最近100條
                if line.strip():
                    entry = LogEntry(line, 0)
                    
                    # 級別統計
                    stats["level_distribution"][entry.level.upper()] += 1
                    
                    # API 使用統計
                    message_lower = entry.message.lower()
                    if "upload" in message_lower or "上傳" in message_lower:
                        stats["api_usage"]["upload"] += 1
                    elif "query" in message_lower or "查詢" in message_lower:
                        stats["api_usage"]["query"] += 1
                    elif "import" in message_lower or "匯入" in message_lower:
                        stats["api_usage"]["import"] += 1
                    
                    # 最近活動
                    if len(recent_entries) < 10:
                        recent_entries.append({
                            "timestamp": entry.timestamp,
                            "level": entry.level,
                            "message": entry.message[:100] + ("..." if len(entry.message) > 100 else "")
                        })
            
            stats["recent_activity"] = recent_entries
        
        # 轉換 defaultdict 為普通 dict
        stats["level_distribution"] = dict(stats["level_distribution"])
        stats["api_usage"] = dict(stats["api_usage"])
        stats["total_size_mb"] = round(stats["total_size"] / 1024 / 1024, 2)
        
        logger.info("日誌統計查詢完成", file_count=len(log_files))
        return stats
        
    except Exception as e:
        logger.error("獲取日誌統計失敗", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get log statistics")

@router.get("/search")
async def search_logs(
    query: str = Query(..., description="搜尋關鍵字"),
    log_type: str = Query("app", description="日誌類型"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回結果數"),
    case_sensitive: bool = Query(False, description="是否區分大小寫")
):
    """搜尋日誌內容"""
    try:
        log_files = get_log_files()
        
        if log_type not in log_files:
            raise HTTPException(status_code=404, detail=f"Log file '{log_type}' not found")
        
        log_file = log_files[log_type]
        
        results = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_content = line.strip()
                if not line_content:
                    continue
                
                # 搜尋匹配
                search_text = line_content if case_sensitive else line_content.lower()
                search_query = query if case_sensitive else query.lower()
                
                if search_query in search_text:
                    entry = LogEntry(line, line_num)
                    result = entry.to_dict()
                    
                    # 高亮顯示匹配的關鍵字
                    if not case_sensitive:
                        # 大小寫不敏感的高亮
                        pattern = re.compile(re.escape(query), re.IGNORECASE)
                        result["highlighted_message"] = pattern.sub(
                            f"<mark>{query}</mark>", 
                            entry.message
                        )
                    else:
                        result["highlighted_message"] = entry.message.replace(
                            query, f"<mark>{query}</mark>"
                        )
                    
                    results.append(result)
                    
                    if len(results) >= limit:
                        break
        
        logger.info("日誌搜尋完成", 
                   query=query, 
                   log_type=log_type, 
                   results_count=len(results))
        
        return {
            "results": results,
            "query": query,
            "log_type": log_type,
            "total_matches": len(results),
            "case_sensitive": case_sensitive,
            "truncated": len(results) >= limit
        }
        
    except Exception as e:
        logger.error("搜尋日誌失敗", query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.delete("/cleanup")
async def cleanup_old_logs():
    """清理舊的日誌備份檔案"""
    try:
        if not LOGS_DIR.exists():
            return {"message": "No log directory found", "cleaned_files": []}
        
        # 找出所有備份檔案 (*.log.*)
        backup_files = list(LOGS_DIR.glob("*.log.*"))
        
        cleaned_files = []
        for file_path in backup_files:
            if file_path.is_file():
                file_size = file_path.stat().st_size
                file_path.unlink()  # 刪除檔案
                cleaned_files.append({
                    "name": file_path.name,
                    "size": file_size,
                    "size_mb": round(file_size / 1024 / 1024, 2)
                })
        
        total_size = sum(f["size"] for f in cleaned_files)
        
        logger.info("日誌清理完成", 
                   cleaned_count=len(cleaned_files),
                   total_size_mb=round(total_size / 1024 / 1024, 2))
        
        return {
            "message": f"Successfully cleaned {len(cleaned_files)} backup files",
            "cleaned_files": cleaned_files,
            "total_size_freed": total_size,
            "total_size_freed_mb": round(total_size / 1024 / 1024, 2)
        }
        
    except Exception as e:
        logger.error("清理日誌失敗", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/download/{log_type}")
async def download_log_file(log_type: str):
    """下載日誌檔案"""
    try:
        log_files = get_log_files()
        
        if log_type not in log_files:
            raise HTTPException(status_code=404, detail=f"Log file '{log_type}' not found")
        
        from fastapi.responses import FileResponse
        
        log_file = log_files[log_type]
        
        logger.info("日誌檔案下載", log_type=log_type, file_size=log_file.stat().st_size)
        
        return FileResponse(
            path=str(log_file),
            filename=f"{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            media_type='text/plain'
        )
        
    except Exception as e:
        logger.error("下載日誌檔案失敗", log_type=log_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")