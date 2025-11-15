"""
Form Analysis Backend API

A FastAPI-based service for file upload, validation, and data import operations.
Supports CSV and Excel file formats with comprehensive validation rules.

Main application entry point.
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 添加專案根目錄到 Python 路徑，以便直接執行時能找到模組
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import init_db, Base
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware, add_process_time_header
from app.api import routes_health, routes_upload, routes_validate, routes_import, routes_export, routes_query, routes_logs

# Import all models to ensure they're registered with Base
from app.models import UploadJob, UploadError, Record

# Initialize application settings
settings = get_settings()

# Setup structured logging
setup_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Database initialization
    - Connection pool setup
    - Resource cleanup
    """
    # Startup - 驗證PostgreSQL配置
    if not settings.database_url.startswith('postgresql'):
        raise ValueError(f" 系統只支援PostgreSQL資料庫！當前配置: {settings.database_url[:30]}...")
    
    # Initialize database connection
    await init_db()
    
    # Import engine after initialization
    from app.core.database import engine
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("📋 Database tables created/verified")
    
    print(f"🚀 Form Analysis API starting on {settings.api_host}:{settings.api_port}")
    print(f" Database: PostgreSQL - {settings.database_url.split('@')[-1]}")  # Hide credentials
    print(f" Upload limit: {settings.max_upload_size_mb}MB")
    print(f"🔒 CORS origins: {settings.cors_origins}")
    print(f"🛡️  Database Type: PostgreSQL Only (固定使用PostgreSQL)")
    
    yield
    
    # Shutdown
    print("🛑 Form Analysis API shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Form Analysis API",
    description="""
    ## File Upload Validation System
    
    A comprehensive API for uploading, validating, and importing CSV/Excel files.
    
    ### Key Features:
    - **File Upload**: Support for CSV (UTF-8) and Excel (.xlsx) formats
    - **Real-time Validation**: Immediate format and content validation
    - **Data Preview**: Preview of importable data with error highlighting  
    - **Batch Import**: Transaction-safe bulk data import
    - **Error Export**: Download error data as CSV for correction
    - **Audit Tracking**: Complete operation tracking with process_id
    
    ### Supported File Formats:
    - CSV files (UTF-8 encoding, with or without BOM)
    - Excel files (.xlsx format only)
    - Maximum file size: 10MB
    
    ### Validation Rules:
    - **lot_no**: 7digits_2digits format (e.g., 1234567_01)
    - **product_name**: 1-100 characters, non-empty
    - **quantity**: Non-negative integer
    - **production_date**: YYYY-MM-DD format
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"],
)

# Custom middleware for request logging and timing
app.add_middleware(RequestLoggingMiddleware)
app.middleware("http")(add_process_time_header)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, "request_id", "unknown"),
        }
    )


# Include API routers
app.include_router(
    routes_health.router,
    prefix="/healthz",
    tags=["Health Check"]
)

# 檔案上傳路由
app.include_router(
    routes_upload.router,
    prefix="/api",
    tags=["檔案上傳"]
)

# 驗證結果查詢路由
app.include_router(
    routes_validate.router,
    prefix="/api",
    tags=["驗證結果查詢"]
)

# 資料匯入路由
app.include_router(
    routes_import.router,
    prefix="/api",
    tags=["資料匯入"]
)

# 資料匯出路由
app.include_router(
    routes_export.router,
    prefix="/api",
    tags=["資料匯出"]
)

# 資料查詢路由
app.include_router(
    routes_query.router,
    prefix="/api/query",
    tags=["資料查詢"]
)

# 日誌管理路由
app.include_router(
    routes_logs.router,
    prefix="/api/logs",
    tags=["日誌管理"]
)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with basic API information."""
    return {
        "message": "Form Analysis API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/healthz"
    }


if __name__ == "__main__":
    # Run the application directly (for development)
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        access_log=True,
    )