"""
Simple test server for Upload.tsx component
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
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

# Mock storage for uploaded files
uploaded_files = {}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and validate file"""
    
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
        "message": "檔案上傳成功",
        "file_id": file_id,
        "file_name": file.filename,
        "total_rows": total_rows,
        "has_errors": has_errors
    }

@app.get("/api/errors.csv")
async def get_errors(file_id: str):
    """Get validation errors CSV"""
    
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
    """Import validated data"""
    
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
        "message": f"資料匯入完成",
        "imported_rows": imported_rows,
        "failed_rows": failed_rows
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Test Upload API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)