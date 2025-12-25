# 新功能需求分析與實作建議 (第二版)

**文檔日期**: 2025年12月10日  
**版本**: 2.0

---

## 新需求概述

1. **PDF 上傳對接外部 Server**
2. **P3 欄位搜尋排序功能**
3. **Product_ID 組合邏輯設計**

---

## 1️⃣ PDF 上傳對接外部 Server

### 場景分析

#### 對接方式選擇

根據不同的對接需求，有以下幾種架構方案：

###  架構方案

#### 方案 A：直接轉發模式（推薦）

**適用場景**: 
- 外部 Server 負責 PDF 處理（OCR、表格提取等）
- 本系統僅負責接收和驗證

**流程**:
```
使用者上傳 PDF
    ↓
本系統 Frontend
    ↓
本系統 Backend (接收、驗證檔案)
    ↓
外部 PDF Server (處理 PDF → 返回結構化資料)
    ↓
本系統 Backend (接收結構化資料 → 驗證 → 匯入資料庫)
    ↓
返回結果給使用者
```

**實作步驟**:

##### 步驟 1: 建立 PDF Server 客戶端服務

```python
# services/pdf_server_client.py

import httpx
import asyncio
from typing import Dict, Any, Optional, BinaryIO
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PDFServerClient:
    """PDF 處理伺服器客戶端"""
    
    def __init__(self):
        self.base_url = settings.pdf_server_url  # 外部 Server URL
        self.api_key = settings.pdf_server_api_key  # API 金鑰
        self.timeout = 300.0  # 5分鐘 timeout（PDF 處理較慢）
    
    async def upload_and_process_pdf(
        self, 
        file_content: bytes,
        filename: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上傳 PDF 到外部 Server 並處理
        
        Args:
            file_content: PDF 檔案內容
            filename: 檔案名稱
            options: 處理選項（如頁碼範圍、提取模式等）
            
        Returns:
            Dict: 處理結果，包含提取的表格資料
            
        Raises:
            PDFServerError: Server 處理失敗
        """
        try:
            logger.info("上傳 PDF 到外部 Server", filename=filename)
            
            # 準備請求
            files = {
                'file': (filename, file_content, 'application/pdf')
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'X-Request-Source': 'form-analysis-system'
            }
            
            data = options or {}
            
            # 發送請求
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/pdf/extract",
                    files=files,
                    data=data,
                    headers=headers
                )
                
                # 檢查回應
                if response.status_code != 200:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise PDFServerError(
                        f"PDF Server 處理失敗: {error_detail}",
                        status_code=response.status_code
                    )
                
                result = response.json()
                logger.info("PDF 處理成功", 
                           filename=filename,
                           rows_extracted=result.get('total_rows', 0))
                
                return result
                
        except httpx.TimeoutException:
            logger.error("PDF Server 請求超時", filename=filename)
            raise PDFServerError("PDF 處理超時，請稍後再試")
        
        except httpx.RequestError as e:
            logger.error("PDF Server 連接失敗", filename=filename, error=str(e))
            raise PDFServerError(f"無法連接到 PDF 處理伺服器: {str(e)}")
    
    async def check_server_health(self) -> bool:
        """檢查外部 Server 健康狀態"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False
    
    async def get_processing_status(self, job_id: str) -> Dict[str, Any]:
        """
        查詢 PDF 處理狀態（如果是非同步處理）
        
        Args:
            job_id: 處理任務 ID
            
        Returns:
            Dict: 任務狀態資訊
        """
        try:
            headers = {'Authorization': f'Bearer {self.api_key}'}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/pdf/status/{job_id}",
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise PDFServerError("無法查詢處理狀態")
                
                return response.json()
                
        except Exception as e:
            logger.error("查詢 PDF 處理狀態失敗", job_id=job_id, error=str(e))
            raise


class PDFServerError(Exception):
    """PDF Server 錯誤"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# 建立單例
pdf_server_client = PDFServerClient()
```

##### 步驟 2: 更新配置檔案

```python
# core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... 現有設定 ...
    
    # PDF Server 設定
    pdf_server_url: str = "http://pdf-server.example.com"
    pdf_server_api_key: str = "your-api-key-here"
    pdf_processing_timeout: int = 300  # 5分鐘
    pdf_async_mode: bool = False  # 是否使用非同步處理
    
    class Config:
        env_file = ".env"
```

```env
# .env.example

# PDF Server 設定
PDF_SERVER_URL=http://pdf-server.example.com
PDF_SERVER_API_KEY=your-api-key-here
PDF_PROCESSING_TIMEOUT=300
PDF_ASYNC_MODE=false
```

##### 步驟 3: 整合到上傳路由

```python
# api/routes_upload.py

from app.services.pdf_server_client import pdf_server_client, PDFServerError

async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> FileUploadResponse:
    """處理檔案上傳"""
    
    # 判斷檔案類型
    file_type = file_validation_service._get_file_type(file.filename)
    
    if file_type == 'pdf':
        logger.info("處理 PDF 檔案（使用外部 Server）", filename=file.filename)
        
        try:
            # 讀取檔案內容
            file_content = await file.read()
            
            # 檢查檔案大小（PDF 可能較大）
            max_size = 20 * 1024 * 1024  # 20MB
            if len(file_content) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"PDF 檔案過大，最大支援 {max_size // 1024 // 1024}MB"
                )
            
            # 上傳到外部 Server 處理
            processing_options = {
                'extract_mode': 'table',  # 表格模式
                'output_format': 'json',  # JSON 格式
                'detect_headers': True    # 自動偵測標題
            }
            
            result = await pdf_server_client.upload_and_process_pdf(
                file_content=file_content,
                filename=file.filename,
                options=processing_options
            )
            
            # 將外部 Server 返回的資料轉換為 DataFrame
            df = pd.DataFrame(result.get('data', []))
            
            if df.empty:
                raise HTTPException(
                    status_code=422,
                    detail="PDF 中未找到有效的表格資料"
                )
            
            # 繼續使用現有的驗證流程
            validation_result = await file_validation_service.validate_data(
                df=df,
                filename=file.filename
            )
            
            # 記錄額外資訊
            logger.info("PDF 處理完成",
                       filename=file.filename,
                       pages_processed=result.get('pages_processed'),
                       tables_found=result.get('tables_found'))
            
        except PDFServerError as e:
            logger.error("PDF Server 處理失敗", 
                        filename=file.filename,
                        error=str(e))
            raise HTTPException(
                status_code=502,
                detail=f"PDF 處理失敗: {e.message}"
            )
        
        except Exception as e:
            logger.error("PDF 處理異常", 
                        filename=file.filename,
                        error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"PDF 處理時發生錯誤: {str(e)}"
            )
    
    else:
        # CSV/Excel 使用現有邏輯
        validation_result = await file_validation_service.validate_file(file=file)
    
    # ... 剩餘處理邏輯 ...
```

##### 步驟 4: 新增健康檢查端點

```python
# api/routes_health.py

from app.services.pdf_server_client import pdf_server_client

@router.get("/health/dependencies")
async def check_dependencies_health():
    """檢查外部依賴服務健康狀態"""
    
    pdf_server_status = await pdf_server_client.check_server_health()
    
    return {
        "status": "healthy" if pdf_server_status else "degraded",
        "dependencies": {
            "pdf_server": {
                "status": "up" if pdf_server_status else "down",
                "url": settings.pdf_server_url
            },
            "database": {
                "status": "up",  # 從現有檢查取得
            }
        }
    }
```

---

#### 方案 B：非同步處理模式

**適用場景**: PDF 處理時間很長（>1分鐘）

**流程**:
```
使用者上傳 PDF
    ↓
本系統接收 → 返回 job_id
    ↓
背景任務: 發送到外部 Server
    ↓
輪詢或 Webhook 取得結果
    ↓
處理完成後通知使用者
```

**核心程式碼**:

```python
# api/routes_upload.py

@router.post("/upload/async")
async def upload_file_async(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """非同步檔案上傳（適用於大型 PDF）"""
    
    if file.filename.lower().endswith('.pdf'):
        # 建立上傳任務
        upload_job = UploadJob(
            filename=file.filename,
            status=JobStatus.PROCESSING
        )
        db.add(upload_job)
        await db.commit()
        
        # 儲存檔案到臨時位置
        temp_path = f"/tmp/{upload_job.process_id}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        # 背景任務處理
        background_tasks.add_task(
            process_pdf_async,
            upload_job.process_id,
            temp_path,
            db
        )
        
        return {
            "process_id": str(upload_job.process_id),
            "status": "processing",
            "message": "PDF 正在處理中，請稍後查詢結果"
        }


async def process_pdf_async(process_id: uuid.UUID, file_path: str, db: AsyncSession):
    """背景處理 PDF"""
    try:
        # 上傳到外部 Server
        with open(file_path, 'rb') as f:
            result = await pdf_server_client.upload_and_process_pdf(
                file_content=f.read(),
                filename=os.path.basename(file_path)
            )
        
        # 處理結果
        df = pd.DataFrame(result['data'])
        validation_result = await file_validation_service.validate_data(df, filename)
        
        # 更新任務狀態
        upload_job = await db.get(UploadJob, process_id)
        upload_job.status = JobStatus.COMPLETED
        await db.commit()
        
    except Exception as e:
        logger.error(f"背景處理 PDF 失敗: {str(e)}")
        upload_job.status = JobStatus.FAILED
        await db.commit()
    finally:
        # 清理臨時檔案
        os.unlink(file_path)


@router.get("/upload/status/{process_id}")
async def get_upload_status(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """查詢上傳處理狀態"""
    upload_job = await db.get(UploadJob, process_id)
    if not upload_job:
        raise HTTPException(404, "找不到處理任務")
    
    return {
        "process_id": str(process_id),
        "status": upload_job.status,
        "progress": upload_job.progress,
        "total_rows": upload_job.total_rows,
        "error_message": upload_job.error_message
    }
```

---

#### 方案 C：Webhook 回調模式

**適用場景**: 外部 Server 主動推送結果

**流程**:
```python
# api/routes_webhook.py

@router.post("/webhook/pdf-processed")
async def pdf_processing_webhook(
    webhook_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """接收 PDF 處理完成的 Webhook"""
    
    # 驗證來源（檢查簽名）
    if not verify_webhook_signature(webhook_data):
        raise HTTPException(403, "無效的 Webhook 簽名")
    
    process_id = webhook_data.get('process_id')
    status = webhook_data.get('status')
    data = webhook_data.get('data')
    
    # 更新任務
    upload_job = await db.get(UploadJob, uuid.UUID(process_id))
    if not upload_job:
        raise HTTPException(404, "找不到處理任務")
    
    if status == 'success':
        # 處理成功，匯入資料
        df = pd.DataFrame(data)
        await import_service.import_records(df, upload_job.data_type, db)
        upload_job.status = JobStatus.COMPLETED
    else:
        # 處理失敗
        upload_job.status = JobStatus.FAILED
        upload_job.error_message = webhook_data.get('error')
    
    await db.commit()
    
    return {"status": "received"}


def verify_webhook_signature(data: Dict[str, Any]) -> bool:
    """驗證 Webhook 簽名"""
    signature = data.get('signature')
    # 實作簽名驗證邏輯
    # 例如: HMAC-SHA256
    return True  # 簡化示範
```

---

### 對接規範建議

#### API 契約範例

```json
// 請求格式
POST /api/pdf/extract
Headers:
  - Authorization: Bearer {api_key}
  - Content-Type: multipart/form-data

Body:
  - file: {PDF 檔案}
  - extract_mode: "table" | "text" | "mixed"
  - output_format: "json" | "csv"
  - detect_headers: true | false

// 回應格式（成功）
{
  "status": "success",
  "process_id": "uuid",
  "pages_processed": 5,
  "tables_found": 3,
  "data": [
    {
      "lot_no": "2503033_01",
      "product_name": "產品A",
      "quantity": 100,
      "...": "..."
    }
  ],
  "metadata": {
    "processing_time": 12.5,
    "confidence_score": 0.95
  }
}

// 回應格式（失敗）
{
  "status": "error",
  "error_code": "INVALID_PDF_FORMAT",
  "message": "PDF 格式無效或損壞",
  "details": "..."
}
```

#### 錯誤處理策略

```python
# 重試機制
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def upload_pdf_with_retry(file_content: bytes, filename: str):
    """帶重試的 PDF 上傳"""
    return await pdf_server_client.upload_and_process_pdf(
        file_content, filename
    )
```

---

## 2️⃣ P3 欄位搜尋排序功能

### 結論：完全可以實作！

### 實作方案

#### 方案 A：多欄位動態排序（推薦）

```python
# api/routes_query.py

from enum import Enum
from typing import List

class SortField(str, Enum):
    """可排序的欄位"""
    LOT_NO = "lot_no"
    P3_NO = "p3_no"
    PRODUCT_NAME = "product_name"
    QUANTITY = "quantity"
    PRODUCTION_DATE = "production_date"
    CREATED_AT = "created_at"


class SortOrder(str, Enum):
    """排序方向"""
    ASC = "asc"   # 升序
    DESC = "desc"  # 降序


@router.get(
    "/p3/search",
    response_model=QueryResponse,
    summary="P3 資料搜尋（支援排序）",
    description="支援多欄位搜尋和靈活排序"
)
async def search_p3_records(
    # 搜尋條件
    p3_no: Optional[str] = Query(None, description="P3追蹤編號"),
    product_name: Optional[str] = Query(None, description="產品名稱"),
    lot_no: Optional[str] = Query(None, description="批號"),
    quantity_min: Optional[int] = Query(None, description="數量最小值"),
    quantity_max: Optional[int] = Query(None, description="數量最大值"),
    production_date_start: Optional[date] = Query(None, description="生產日期起始"),
    production_date_end: Optional[date] = Query(None, description="生產日期結束"),
    
    # 排序參數
    sort_by: Optional[List[SortField]] = Query(
        default=[SortField.CREATED_AT],
        description="排序欄位（可多個），例如: ?sort_by=production_date&sort_by=lot_no"
    ),
    sort_order: Optional[List[SortOrder]] = Query(
        default=[SortOrder.DESC],
        description="排序方向（對應 sort_by），例如: ?sort_order=desc&sort_order=asc"
    ),
    
    # 分頁
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(20, ge=1, le=100, description="每頁記錄數"),
    
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """P3 資料進階搜尋（支援多欄位排序）"""
    
    try:
        logger.info("P3 搜尋開始", 
                   p3_no=p3_no, 
                   product_name=product_name,
                   sort_by=sort_by,
                   sort_order=sort_order)
        
        # 建構查詢條件
        conditions = [Record.data_type == DataType.P3]
        
        # P3 編號模糊搜尋
        if p3_no:
            conditions.append(Record.p3_no.ilike(f"%{p3_no}%"))
        
        # 產品名稱模糊搜尋
        if product_name:
            conditions.append(Record.product_name.ilike(f"%{product_name}%"))
        
        # 批號模糊搜尋
        if lot_no:
            conditions.append(Record.lot_no.ilike(f"%{lot_no}%"))
        
        # 數量範圍
        if quantity_min is not None:
            conditions.append(Record.quantity >= quantity_min)
        if quantity_max is not None:
            conditions.append(Record.quantity <= quantity_max)
        
        # 日期範圍
        if production_date_start:
            conditions.append(Record.production_date >= production_date_start)
        if production_date_end:
            conditions.append(Record.production_date <= production_date_end)
        
        # 建構查詢
        query_stmt = select(Record).where(and_(*conditions))
        
        # 動態排序
        order_clauses = []
        for i, field in enumerate(sort_by):
            # 取得對應的排序方向
            order = sort_order[i] if i < len(sort_order) else SortOrder.ASC
            
            # 根據欄位建構排序子句
            if field == SortField.LOT_NO:
                order_clause = Record.lot_no
            elif field == SortField.P3_NO:
                order_clause = Record.p3_no
            elif field == SortField.PRODUCT_NAME:
                order_clause = Record.product_name
            elif field == SortField.QUANTITY:
                order_clause = Record.quantity
            elif field == SortField.PRODUCTION_DATE:
                order_clause = Record.production_date
            elif field == SortField.CREATED_AT:
                order_clause = Record.created_at
            else:
                continue
            
            # 套用排序方向
            if order == SortOrder.DESC:
                order_clause = order_clause.desc()
            else:
                order_clause = order_clause.asc()
            
            # 處理 NULL 值（放在最後）
            if field in [SortField.PRODUCTION_DATE, SortField.P3_NO, 
                        SortField.PRODUCT_NAME, SortField.QUANTITY]:
                order_clause = order_clause.nullslast()
            
            order_clauses.append(order_clause)
        
        # 計算總數
        count_query = select(func.count(Record.id)).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # 套用排序和分頁
        offset = (page - 1) * page_size
        query_stmt = query_stmt.order_by(*order_clauses).offset(offset).limit(page_size)
        
        # 執行查詢
        result = await db.execute(query_stmt)
        records = result.scalars().all()
        
        # 轉換為回應格式
        query_records = []
        for record in records:
            query_record = QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                data_type=record.data_type.value,
                production_date=record.production_date.isoformat() if record.production_date else None,
                created_at=record.created_at.isoformat(),
                display_name=record.display_name,
                p3_no=record.p3_no,
                product_name=record.product_name,
                quantity=record.quantity,
                notes=record.notes,
                additional_data=record.additional_data
            )
            query_records.append(query_record)
        
        logger.info("P3 搜尋完成", 
                   total_count=total_count,
                   returned_count=len(query_records),
                   sort_by=sort_by)
        
        return QueryResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            records=query_records,
            sort_info={  # 額外返回排序資訊
                "sort_by": [s.value for s in sort_by],
                "sort_order": [o.value for o in sort_order]
            }
        )
        
    except Exception as e:
        logger.error("P3 搜尋失敗", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"搜尋時發生錯誤: {str(e)}"
        )
```

#### 前端使用範例

```typescript
// frontend/src/api/queries.ts

interface P3SearchParams {
  p3_no?: string;
  product_name?: string;
  lot_no?: string;
  quantity_min?: number;
  quantity_max?: number;
  production_date_start?: string;
  production_date_end?: string;
  sort_by?: string[];  // ['production_date', 'lot_no']
  sort_order?: string[]; // ['desc', 'asc']
  page?: number;
  page_size?: number;
}

export const searchP3Records = async (params: P3SearchParams) => {
  const queryParams = new URLSearchParams();
  
  // 基本搜尋參數
  if (params.p3_no) queryParams.append('p3_no', params.p3_no);
  if (params.product_name) queryParams.append('product_name', params.product_name);
  // ... 其他參數
  
  // 排序參數（可多個）
  params.sort_by?.forEach(field => queryParams.append('sort_by', field));
  params.sort_order?.forEach(order => queryParams.append('sort_order', order));
  
  // 分頁
  queryParams.append('page', String(params.page || 1));
  queryParams.append('page_size', String(params.page_size || 20));
  
  const response = await fetch(
    `${API_BASE_URL}/api/p3/search?${queryParams.toString()}`
  );
  
  return response.json();
};

// 使用範例
const results = await searchP3Records({
  product_name: '產品A',
  sort_by: ['production_date', 'lot_no'],
  sort_order: ['desc', 'asc'],  // 日期降序，批號升序
  page: 1,
  page_size: 20
});
```

#### UI 組件範例

```typescript
// frontend/src/components/P3SearchWithSort.tsx

import React, { useState } from 'react';
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/outline';

interface SortConfig {
  field: string;
  order: 'asc' | 'desc';
}

function P3SearchWithSort() {
  const [sortConfig, setSortConfig] = useState<SortConfig[]>([
    { field: 'production_date', order: 'desc' }
  ]);
  
  const handleSort = (field: string) => {
    setSortConfig(prev => {
      const existing = prev.find(s => s.field === field);
      
      if (existing) {
        // 切換排序方向
        return prev.map(s => 
          s.field === field 
            ? { ...s, order: s.order === 'asc' ? 'desc' : 'asc' }
            : s
        );
      } else {
        // 新增排序欄位
        return [...prev, { field, order: 'asc' }];
      }
    });
  };
  
  const getSortIcon = (field: string) => {
    const config = sortConfig.find(s => s.field === field);
    if (!config) return null;
    
    return config.order === 'asc' 
      ? <ArrowUpIcon className="w-4 h-4" />
      : <ArrowDownIcon className="w-4 h-4" />;
  };
  
  return (
    <div>
      {/* 搜尋表單 */}
      <div className="mb-4">
        <input 
          type="text" 
          placeholder="P3 編號"
          className="border p-2 rounded"
        />
        {/* 其他搜尋欄位 */}
      </div>
      
      {/* 排序選項 */}
      <div className="mb-4">
        <label className="font-bold">排序:</label>
        <div className="flex gap-2 mt-2">
          {['production_date', 'lot_no', 'p3_no', 'quantity'].map(field => (
            <button
              key={field}
              onClick={() => handleSort(field)}
              className={`px-3 py-1 rounded border flex items-center gap-1 ${
                sortConfig.some(s => s.field === field) 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100'
              }`}
            >
              {field === 'production_date' && '生產日期'}
              {field === 'lot_no' && '批號'}
              {field === 'p3_no' && 'P3編號'}
              {field === 'quantity' && '數量'}
              {getSortIcon(field)}
            </button>
          ))}
        </div>
      </div>
      
      {/* 結果表格 */}
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-100">
            <th 
              className="border p-2 cursor-pointer hover:bg-gray-200"
              onClick={() => handleSort('lot_no')}
            >
              批號 {getSortIcon('lot_no')}
            </th>
            <th 
              className="border p-2 cursor-pointer hover:bg-gray-200"
              onClick={() => handleSort('production_date')}
            >
              生產日期 {getSortIcon('production_date')}
            </th>
            <th className="border p-2">產品名稱</th>
            <th 
              className="border p-2 cursor-pointer hover:bg-gray-200"
              onClick={() => handleSort('quantity')}
            >
              數量 {getSortIcon('quantity')}
            </th>
          </tr>
        </thead>
        <tbody>
          {/* 渲染資料 */}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 3️⃣ Product_ID 組合邏輯設計

### 需求分析

**Product_ID 組成**:
```
日期 + 機台號碼 + 模具號碼 + 生產序號
例如: 20250310-M01-D05-S123
```

### 建議：**後端組合並回傳（強烈推薦）**

###  原因分析

| 考量因素 | 後端組合 | 前端組合 |
|---------|---------|---------|
| **資料一致性** | 統一邏輯 | 可能不一致 |
| **維護性** | 單一來源 | 多處修改 |
| **效能** | 計算一次 | 每次渲染計算 |
| **儲存** | 可儲存到DB | 無法儲存 |
| **搜尋** | 可直接搜尋 | 無法搜尋 |
| **API 回傳** | 直接使用 | 需要原始欄位 |
| **測試** | 容易測試 | 需要模擬資料 |

### 實作方案

#### 步驟 1: 修改資料庫模型

```python
# models/record.py

class Record(Base):
    """資料記錄模型"""
    __tablename__ = "records"
    
    # ... 現有欄位 ...
    
    # P3 專用欄位
    p3_no: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="P3追蹤編號 (P3使用)"
    )
    
    # 新增: Product ID（P3 使用）
    product_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="產品ID: 日期+機台+模具+序號 (P3使用)",
        index=True  # 建立索引以支援搜尋
    )
    
    # P3 組成欄位（從 CSV 讀取）
    machine_no: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="機台號碼 (P3使用)"
    )
    
    mold_no: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="模具號碼 (P3使用)"
    )
    
    production_sequence: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="生產序號 (P3使用)"
    )
```

#### 步驟 2: 建立資料庫遷移

```bash
cd form-analysis-server/backend
alembic revision -m "add_product_id_and_p3_fields"
```

```python
# migrations/versions/xxxx_add_product_id_and_p3_fields.py

def upgrade():
    # 新增欄位
    op.add_column('records', sa.Column('product_id', sa.String(100), nullable=True))
    op.add_column('records', sa.Column('machine_no', sa.String(20), nullable=True))
    op.add_column('records', sa.Column('mold_no', sa.String(20), nullable=True))
    op.add_column('records', sa.Column('production_sequence', sa.String(20), nullable=True))
    
    # 建立索引
    op.create_index('ix_records_product_id', 'records', ['product_id'])

def downgrade():
    op.drop_index('ix_records_product_id')
    op.drop_column('records', 'production_sequence')
    op.drop_column('records', 'mold_no')
    op.drop_column('records', 'machine_no')
    op.drop_column('records', 'product_id')
```

#### 步驟 3: 建立 Product ID 生成器

```python
# services/product_id_generator.py

from datetime import date
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProductIDGenerator:
    """Product ID 生成器"""
    
    @staticmethod
    def generate_product_id(
        production_date: Optional[date],
        machine_no: Optional[str],
        mold_no: Optional[str],
        production_sequence: Optional[str],
        separator: str = "-"
    ) -> Optional[str]:
        """
        生成 Product ID
        
        格式: YYYYMMDD-{機台}-{模具}-{序號}
        例如: 20250310-M01-D05-S123
        
        Args:
            production_date: 生產日期
            machine_no: 機台號碼
            mold_no: 模具號碼
            production_sequence: 生產序號
            separator: 分隔符（預設: -）
            
        Returns:
            str: Product ID，如果任何必要欄位缺失則返回 None
        """
        try:
            # 檢查必要欄位
            if not all([production_date, machine_no, mold_no, production_sequence]):
                logger.warning("Product ID 生成失敗: 缺少必要欄位",
                              has_date=bool(production_date),
                              has_machine=bool(machine_no),
                              has_mold=bool(mold_no),
                              has_sequence=bool(production_sequence))
                return None
            
            # 格式化日期
            date_str = production_date.strftime("%Y%m%d")
            
            # 清理並格式化各個部分
            machine_str = str(machine_no).strip().upper()
            mold_str = str(mold_no).strip().upper()
            sequence_str = str(production_sequence).strip()
            
            # 組合 Product ID
            product_id = separator.join([
                date_str,
                machine_str,
                mold_str,
                sequence_str
            ])
            
            logger.debug("Product ID 生成成功", product_id=product_id)
            return product_id
            
        except Exception as e:
            logger.error("Product ID 生成異常", error=str(e))
            return None
    
    @staticmethod
    def parse_product_id(product_id: str, separator: str = "-") -> dict:
        """
        解析 Product ID
        
        Args:
            product_id: Product ID 字串
            separator: 分隔符
            
        Returns:
            dict: 包含各個組成部分的字典
        """
        try:
            parts = product_id.split(separator)
            if len(parts) != 4:
                return {}
            
            date_str, machine, mold, sequence = parts
            
            return {
                'production_date': date_str,
                'machine_no': machine,
                'mold_no': mold,
                'production_sequence': sequence
            }
        except:
            return {}
    
    @staticmethod
    def validate_product_id(product_id: str, separator: str = "-") -> bool:
        """驗證 Product ID 格式"""
        try:
            parts = product_id.split(separator)
            if len(parts) != 4:
                return False
            
            date_str = parts[0]
            # 驗證日期格式 (YYYYMMDD)
            if len(date_str) != 8 or not date_str.isdigit():
                return False
            
            return True
        except:
            return False


# 建立單例
product_id_generator = ProductIDGenerator()
```

#### 步驟 4: 修改匯入服務

```python
# services/import_service.py

from app.services.product_id_generator import product_id_generator

class DataImportService:
    
    async def import_records(
        self, 
        df: pd.DataFrame, 
        data_type: DataType,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """匯入資料記錄（自動生成 Product ID）"""
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # 提取基本欄位
                lot_no = row.get('lot_no')
                production_date = row.get('production_date')
                
                # P3 特殊處理
                if data_type == DataType.P3:
                    # 提取 P3 組成欄位
                    machine_no = row.get('機台號碼') or row.get('machine_no')
                    mold_no = row.get('模具號碼') or row.get('mold_no')
                    production_sequence = row.get('生產序號') or row.get('production_sequence')
                    
                    # 自動生成 Product ID
                    product_id = product_id_generator.generate_product_id(
                        production_date=production_date,
                        machine_no=machine_no,
                        mold_no=mold_no,
                        production_sequence=production_sequence
                    )
                    
                    if product_id:
                        logger.info("生成 Product ID", 
                                   lot_no=lot_no, 
                                   product_id=product_id)
                    else:
                        logger.warning("Product ID 生成失敗", 
                                      lot_no=lot_no,
                                      row_index=idx)
                    
                    # 建立記錄
                    record = Record(
                        lot_no=lot_no,
                        data_type=data_type,
                        production_date=production_date,
                        p3_no=row.get('P3_No.'),
                        product_name=row.get('product_name'),
                        quantity=row.get('quantity'),
                        notes=row.get('notes'),
                        # P3 專用欄位
                        machine_no=machine_no,
                        mold_no=mold_no,
                        production_sequence=production_sequence,
                        product_id=product_id,  # 儲存生成的 Product ID
                        additional_data=row.to_dict()
                    )
                else:
                    # P1/P2 處理
                    record = Record(
                        lot_no=lot_no,
                        data_type=data_type,
                        production_date=production_date,
                        # ... 其他欄位
                    )
                
                db.add(record)
                imported_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append({
                    'row_index': idx,
                    'error': str(e)
                })
                logger.error("匯入記錄失敗", 
                            row_index=idx, 
                            error=str(e))
        
        await db.commit()
        
        return {
            'imported_count': imported_count,
            'failed_count': failed_count,
            'errors': errors
        }
```

#### 步驟 5: 更新查詢回應

```python
# api/routes_query.py

class QueryRecord(BaseModel):
    """查詢記錄回應模型"""
    id: str
    lot_no: str
    data_type: str
    production_date: Optional[str]
    created_at: str
    display_name: str
    
    # P3 專用欄位
    p3_no: Optional[str] = None
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    notes: Optional[str] = None
    
    # P3 Product ID 相關欄位
    product_id: Optional[str] = None  # 後端生成並回傳
    machine_no: Optional[str] = None
    mold_no: Optional[str] = None
    production_sequence: Optional[str] = None
    
    # ... 其他欄位


@router.get("/p3/search")
async def search_p3_records(...) -> QueryResponse:
    """P3 搜尋（包含 Product ID）"""
    
    # ... 查詢邏輯 ...
    
    for record in records:
        query_record = QueryRecord(
            id=str(record.id),
            lot_no=record.lot_no,
            data_type=record.data_type.value,
            production_date=record.production_date.isoformat() if record.production_date else None,
            created_at=record.created_at.isoformat(),
            display_name=record.display_name,
            p3_no=record.p3_no,
            product_name=record.product_name,
            quantity=record.quantity,
            notes=record.notes,
            # Product ID 相關欄位（後端組合好的）
            product_id=record.product_id,  # 直接返回
            machine_no=record.machine_no,
            mold_no=record.mold_no,
            production_sequence=record.production_sequence
        )
        query_records.append(query_record)
    
    return QueryResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        records=query_records
    )
```

#### 步驟 6: 支援 Product ID 搜尋

```python
# api/routes_query.py

@router.get("/p3/search")
async def search_p3_records(
    # ... 其他參數 ...
    
    product_id: Optional[str] = Query(None, description="Product ID（支援模糊搜尋）"),
    machine_no: Optional[str] = Query(None, description="機台號碼"),
    mold_no: Optional[str] = Query(None, description="模具號碼"),
    production_sequence: Optional[str] = Query(None, description="生產序號"),
    
    # ...
) -> QueryResponse:
    """P3 搜尋（支援 Product ID）"""
    
    conditions = [Record.data_type == DataType.P3]
    
    # Product ID 搜尋
    if product_id:
        conditions.append(Record.product_id.ilike(f"%{product_id}%"))
    
    # 機台號碼搜尋
    if machine_no:
        conditions.append(Record.machine_no.ilike(f"%{machine_no}%"))
    
    # 模具號碼搜尋
    if mold_no:
        conditions.append(Record.mold_no.ilike(f"%{mold_no}%"))
    
    # 生產序號搜尋
    if production_sequence:
        conditions.append(Record.production_sequence.ilike(f"%{production_sequence}%"))
    
    # ... 其他查詢邏輯 ...
```

#### 前端使用範例

```typescript
// frontend/src/types/record.ts

interface P3Record {
  id: string;
  lot_no: string;
  data_type: 'P3';
  production_date?: string;
  p3_no?: string;
  product_name?: string;
  quantity?: number;
  
  // Product ID 相關（後端生成並回傳）
  product_id: string;  // 直接使用
  machine_no?: string;
  mold_no?: string;
  production_sequence?: string;
}

// 直接顯示
function P3RecordRow({ record }: { record: P3Record }) {
  return (
    <tr>
      <td>{record.lot_no}</td>
      <td>{record.product_id}</td>  {/* 直接顯示 */}
      <td>{record.machine_no}</td>
      <td>{record.mold_no}</td>
      <td>{record.production_sequence}</td>
    </tr>
  );
}
```

---

## 總結

| 需求 | 建議方案 | 複雜度 | 優先級 |
|------|---------|--------|--------|
| PDF Server 對接 | 直接轉發模式 | 中 | 高 |
| P3 排序功能 | 多欄位動態排序 | 低 | 高 |
| Product ID 組合 | **後端組合** | 低 | 高 |

###  實作順序

1. **第一階段** (1-2天): Product ID 生成
   - 修改資料庫模型
   - 實作生成器
   - 更新匯入邏輯

2. **第二階段** (1天): P3 排序功能
   - 修改查詢 API
   - 新增排序參數
   - 更新前端 UI

3. **第三階段** (2-3天): PDF Server 對接
   - 建立客戶端服務
   - 整合上傳流程
   - 測試對接

---

**文檔版本**: 2.0  
**最後更新**: 2025年12月10日
