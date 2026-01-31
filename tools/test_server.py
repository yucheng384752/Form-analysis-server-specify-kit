"""Simple test server for frontend development.

This mock server supports both:
- Legacy upload/import endpoints (deprecated)
- v2 import jobs endpoints (recommended)
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uuid
import time
import io
import csv

app = FastAPI(title="Test Upload API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mock storage
tenants = [{"tenant_id": "demo", "id": "demo", "name": "Demo Tenant"}]
uploaded_files = {}
import_jobs = {}


def _require_tenant(x_tenant_id: str | None):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id")
    return x_tenant_id


def _compute_job_status(job: dict) -> str:
    if job.get("status") in {"FAILED", "READY", "COMPLETED", "CANCELLED"}:
        return job["status"]
    # Simulate background processing
    elapsed = time.time() - job["created_at"]
    if elapsed < 0.5:
        return "QUEUED"
    if job.get("has_errors"):
        return "FAILED"
    return "READY"


@app.get("/api/tenants")
async def list_tenants():
    return tenants

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """(DEPRECATED) Upload and validate file"""
    
    # Check file type
    allowed_types = ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']
    if file.content_type not in allowed_types:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "不支援的檔案格式。請上傳 CSV 或 Excel 檔案。"
            }
        )
    
    # Check file size (10MB limit)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "檔案大小超過 10MB 限制。"
            }
        )
    
    # Generate file ID
    file_id = str(uuid.uuid4())
    
    # Simulate processing
    total_rows = 150  # Mock row count
    has_errors = len(content) % 3 == 0  # Randomly assign errors
    
    # Store file info
    uploaded_files[file_id] = {
        "filename": file.filename,
        "content": content,
        "total_rows": total_rows,
        "has_errors": has_errors,
        "upload_time": time.time()
    }
    
    return {
        "success": True,
        "message": "檔案上傳成功（deprecated: 請改用 /api/v2/import/jobs）",
        "file_id": file_id,
        "file_name": file.filename,
        "total_rows": total_rows,
        "has_errors": has_errors
    }

@app.get("/api/errors.csv")
async def get_errors(file_id: str):
    """(DEPRECATED) Get validation errors CSV"""
    
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="檔案未找到")
    
    file_info = uploaded_files[file_id]
    
    if not file_info["has_errors"]:
        # Return empty CSV if no errors
        csv_content = "row,column,value,error\n"
    else:
        # Mock error data
        csv_content = """row,column,value,error
2,lot_no,123456,"格式錯誤：應為 7digits_2digits 格式"
5,quantity,-10,"數量不能為負數"
8,production_date,2023-13-45,"日期格式錯誤：應為 YYYY-MM-DD"
12,product_name,"","產品名稱不能為空"
"""
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=validation_errors.csv"}
    )

@app.post("/api/import")
async def import_data(request: dict):
    """(DEPRECATED) Import validated data"""
    
    file_id = request.get("file_id")
    if not file_id or file_id not in uploaded_files:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "無效的檔案 ID"
            }
        )
    
    file_info = uploaded_files[file_id]
    
    # Simulate import process
    imported_rows = file_info["total_rows"] - (4 if file_info["has_errors"] else 0)
    failed_rows = 4 if file_info["has_errors"] else 0
    
    return {
        "success": True,
        "message": "資料匯入完成（deprecated: 請改用 v2 commit）",
        "imported_rows": imported_rows,
        "failed_rows": failed_rows
    }


@app.post("/api/v2/import/jobs")
async def create_import_job(
    table_code: str = Form(...),
    allow_duplicate: str = Form("false"),
    files: list[UploadFile] = File(...),
    x_tenant_id: str | None = Header(default=None),
):
    """Create v2 import job (mock)."""
    _require_tenant(x_tenant_id)

    if not files:
        raise HTTPException(status_code=400, detail="No files")

    first = files[0]
    content = await first.read()
    has_errors = len(content) % 3 == 0
    job_id = str(uuid.uuid4())

    import_jobs[job_id] = {
        "id": job_id,
        "tenant_id": x_tenant_id,
        "table_code": table_code,
        "allow_duplicate": allow_duplicate.lower() == "true",
        "filename": first.filename,
        "created_at": time.time(),
        "has_errors": has_errors,
        "status": "PROCESSING",
    }

    return {
        "id": job_id,
        "status": _compute_job_status(import_jobs[job_id]),
        "table_code": table_code,
        "files": [{"filename": first.filename}],
    }


@app.get("/api/v2/import/jobs/{job_id}")
async def get_import_job(job_id: str, x_tenant_id: str | None = Header(default=None)):
    _require_tenant(x_tenant_id)
    job = import_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["tenant_id"] != x_tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    status = _compute_job_status(job)
    job["status"] = status
    return {
        "id": job_id,
        "status": status,
        "table_code": job.get("table_code"),
        "filename": job.get("filename"),
    }


@app.post("/api/v2/import/jobs/{job_id}/commit")
async def commit_import_job(job_id: str, x_tenant_id: str | None = Header(default=None)):
    _require_tenant(x_tenant_id)
    job = import_jobs.get(job_id)
    if not job or job["tenant_id"] != x_tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    status = _compute_job_status(job)
    if status != "READY":
        raise HTTPException(status_code=409, detail=f"Job not READY (status={status})")

    job["status"] = "COMPLETED"
    return {"id": job_id, "status": "COMPLETED"}


@app.get("/api/v2/import/jobs/{job_id}/errors")
async def get_import_job_errors(job_id: str, x_tenant_id: str | None = Header(default=None)):
    _require_tenant(x_tenant_id)
    job = import_jobs.get(job_id)
    if not job or job["tenant_id"] != x_tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.get("has_errors"):
        return {"items": [], "total": 0}

    # Mock error rows
    return {
        "items": [
            {"row": 2, "field": "lot_no", "message": "格式錯誤：應為 7digits_2digits"},
            {"row": 5, "field": "quantity", "message": "數量不能為負數"},
        ],
        "total": 2,
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Test Upload API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)