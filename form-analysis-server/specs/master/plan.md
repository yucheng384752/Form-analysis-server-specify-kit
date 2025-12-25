# Implementation Plan: 表單上傳驗證系統 MVP

**Branch**: `master` | **Date**: 2025-11-08 | **Spec**: [spec.md](./spec.md)
**Input**: 檔案上傳 + 驗證 + 預覽 + 匯入系統規格

## Summary

建立最小可行的檔案處理系統，支援 CSV/Excel 上傳、即時驗證、資料預覽與批次匯入。採用前後端分離架構，後端 FastAPI + PostgreSQL，前端 React + TypeScript，透過 Docker Compose 統一部署。核心流程：上傳 → 驗證 → 預覽 → 確認匯入，每步驟提供清晰的使用者回饋與錯誤處理。

## Technical Context

**Language/Version**: Python 3.12, TypeScript 5.x, Node.js 20+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, React, Vite  
**Storage**: PostgreSQL 16 (containerized), file system (temporary upload storage)  
**Testing**: pytest + coverage (backend), vitest (frontend), pre-commit hooks  
**Target Platform**: Linux containers (Docker), modern browsers (Chrome 90+, Firefox 88+)  
**Project Type**: Web application (frontend + backend separation)  
**Performance Goals**: 3s 驗證回應, 30s 匯入完成 (10k 筆), 10MB 檔案支援, 10 並發使用者  
**Constraints**: 10MB 檔案上限, 中文友善錯誤, process_id 追蹤, 交易性匯入  
**Scale/Scope**: 內部工具 (~50 使用者), 單一功能模組, MVP 範圍 4-5 API 端點

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

 **SDD 流程**: 規格已完成 → 本計畫 → 任務分解 → 實作  
 **前後端分離**: FastAPI (後端) + React (前端) + Docker Compose  
 **程式碼品質**: ruff + black + mypy (Python), eslint + prettier (TS), pre-commit  
 **測試與 CI**: pytest + vitest, GitHub Actions 設定 lint → test → type-check  
 **可觀測性**: 中介層記錄 request_id, 處理時間, 錯誤追蹤, 結構化日誌  

**通過條件**: 所有工具設定與 Docker 環境符合憲章要求

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
form-analysis-server/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 應用程式進入點
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes_upload.py       # POST /api/upload (檔案上傳+驗證)
│   │   │   ├── routes_validate.py     # GET /api/validate (取詳細驗證結果)
│   │   │   ├── routes_import.py       # POST /api/import (確認匯入)
│   │   │   ├── routes_export.py       # GET /api/export (下載錯誤CSV)
│   │   │   └── routes_health.py       # GET /healthz
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py              # 環境變數與設定
│   │   │   ├── database.py            # SQLAlchemy 連線設定
│   │   │   ├── logging.py             # 結構化日誌配置
│   │   │   └── middleware.py          # request_id, 時間記錄中介層
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── file_parser.py         # CSV/Excel 解析服務
│   │   │   ├── validator.py           # 資料驗證服務
│   │   │   └── importer.py            # 資料匯入服務
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── upload_jobs.py         # 上傳工作記錄
│   │   │   ├── upload_errors.py       # 驗證錯誤記錄
│   │   │   └── records.py             # 業務資料模型
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py              # 上傳相關 Pydantic models
│   │   │   ├── validation.py          # 驗證相關 Pydantic models
│   │   │   └── responses.py           # API 回應格式
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── file_utils.py          # 檔案處理工具函數
│   ├── alembic/
│   │   ├── versions/                  # migration 檔案
│   │   ├── env.py                     # Alembic 環境設定
│   │   └── script.py.mako             # migration 模板
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                # pytest 配置與 fixtures
│   │   ├── unit/                      # 單元測試
│   │   │   ├── test_validator.py
│   │   │   ├── test_file_parser.py
│   │   │   └── test_importer.py
│   │   ├── integration/               # 整合測試
│   │   │   ├── test_upload_flow.py
│   │   │   └── test_database.py
│   │   └── fixtures/                  # 測試檔案與資料
│   │       ├── valid_sample.csv
│   │       ├── invalid_sample.csv
│   │       └── sample.xlsx
│   ├── pyproject.toml                 # Python 專案配置
│   ├── requirements.txt               # 依賴套件清單
│   └── Dockerfile                     # 後端容器配置
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.tsx             # 主要上傳頁面
│   │   │   ├── Validation.tsx         # 驗證結果頁面
│   │   │   └── Import.tsx             # 匯入確認頁面
│   │   ├── components/
│   │   │   ├── FileUploader.tsx       # 檔案上傳元件
│   │   │   ├── PreviewTable.tsx       # 資料預覽表格
│   │   │   ├── ErrorList.tsx          # 錯誤列表顯示
│   │   │   └── ProgressBar.tsx        # 進度條元件
│   │   ├── lib/
│   │   │   ├── api.ts                 # API 呼叫封裝
│   │   │   └── validation.ts          # 前端驗證邏輯
│   │   ├── types/
│   │   │   ├── upload.ts              # 上傳相關 TypeScript 型別
│   │   │   └── api.ts                 # API 回應型別定義
│   │   ├── utils/
│   │   │   └── file.ts                # 檔案處理工具
│   │   ├── App.tsx                    # React 主應用
│   │   └── main.tsx                   # 應用程式進入點
│   ├── tests/
│   │   ├── components/                # 元件測試
│   │   ├── integration/               # 端到端測試
│   │   └── utils/                     # 工具函數測試
│   ├── package.json                   # Node.js 專案配置
│   ├── vite.config.ts                 # Vite 建置配置
│   ├── tsconfig.json                  # TypeScript 配置
│   ├── eslint.config.js               # ESLint 配置
│   ├── prettier.config.js             # Prettier 配置
│   └── Dockerfile                     # 前端容器配置
├── .env.example                       # 環境變數範例
├── .gitignore                         # Git 忽略檔案
├── .pre-commit-config.yaml            # pre-commit 配置
├── docker-compose.yml                 # 容器編排配置
├── pyproject.toml                     # 根目錄 Python 工具配置 (ruff, mypy)
└── README.md                          # 專案文件
```

**Structure Decision**: 採用 Web application 結構，前後端完全分離。後端專注 API 服務，前端專注使用者介面。透過 Docker Compose 統一管理服務依賴。每個模組有明確職責分工，便於測試與維護。

## Phase 0: Research & Setup

### Environment Setup & Dependencies

**Backend Dependencies (pyproject.toml)**:
```toml
[project]
name = "form-analysis-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "psycopg[binary]>=3.1.0",
    "python-multipart>=0.0.6",
    "pandas>=2.1.0",
    "openpyxl>=3.1.0",
    "python-json-logger>=2.0.7",
    "uuid-utils>=0.7.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.0",
    "ruff>=0.1.5",
    "black>=23.9.0",
    "mypy>=1.6.0",
    "pre-commit>=3.5.0"
]

[tool.ruff]
line-length = 88
select = ["E", "F", "W", "C901", "I", "N", "UP", "YTT", "ANN", "S", "BLE", "FBT", "B", "A", "COM", "C4", "DTZ", "T10", "ISC", "ICN", "G", "PIE", "T20", "PYI", "PT", "Q", "RSE", "RET", "SLF", "SIM", "TID", "TCH", "INT", "ARG", "PTH", "PL", "R", "TRY", "FLY", "NPY", "RUF"]
ignore = ["ANN101", "ANN102", "COM812", "ISC001"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

**Frontend Dependencies (package.json)**:
```json
{
  "name": "form-analysis-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "lint:fix": "eslint . --ext ts,tsx --fix",
    "format": "prettier --write .",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.17.0",
    "axios": "^1.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.33",
    "@types/react-dom": "^18.2.14",
    "@typescript-eslint/eslint-plugin": "^6.10.0",
    "@typescript-eslint/parser": "^6.10.0",
    "@vitejs/plugin-react": "^4.1.0",
    "eslint": "^8.53.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.4",
    "prettier": "^3.0.3",
    "typescript": "^5.2.2",
    "vite": "^4.5.0",
    "vitest": "^0.34.6",
    "@testing-library/react": "^13.4.0",
    "@testing-library/jest-dom": "^6.1.4"
  }
}
```

**Environment Variables (.env.example)**:
```bash
# Database Configuration
POSTGRES_USER=app
POSTGRES_PASSWORD=app_secure_password
POSTGRES_DB=form_analysis_db
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://app:app_secure_password@db:5432/form_analysis_db

# API Configuration  
API_PORT=8000
API_HOST=0.0.0.0
MAX_UPLOAD_SIZE_MB=10
UPLOAD_TEMP_DIR=/tmp/uploads
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Development
DEBUG=false
RELOAD=false
```

### Docker Configuration

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  db:
    image: postgres:16
    container_name: form_analysis_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-app_secure_password}
      POSTGRES_DB: ${POSTGRES_DB:-form_analysis_db}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: form_analysis_api
    depends_on:
      db:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-app}:${POSTGRES_PASSWORD:-app_secure_password}@db:5432/${POSTGRES_DB:-form_analysis_db}
      - API_PORT=${API_PORT:-8000}
      - MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-10}
      - CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:5173}
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - ./backend/uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: form_analysis_frontend
    depends_on:
      - backend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5173"]
      interval: 30s
      timeout: 10s
      retries: 3

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: form_analysis_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db
    profiles:
      - tools

volumes:
  postgres_data:
```

### Database Schema

**Alembic Migration (initial schema)**:
```sql
-- upload_jobs table
CREATE TABLE upload_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    total_rows INTEGER DEFAULT 0,
    valid_rows INTEGER DEFAULT 0,
    invalid_rows INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100), -- 未來使用者認證用
    source_ip INET,
    processing_time_ms INTEGER
);

-- upload_errors table  
CREATE TABLE upload_errors (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES upload_jobs(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    field_name VARCHAR(100),
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    raw_value TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- records table (business data)
CREATE TABLE records (
    id SERIAL PRIMARY KEY,
    lot_no VARCHAR(20) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    production_date DATE NOT NULL,
    job_id UUID REFERENCES upload_jobs(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_upload_jobs_status ON upload_jobs(status);
CREATE INDEX idx_upload_jobs_created_at ON upload_jobs(created_at);
CREATE INDEX idx_upload_errors_job_id ON upload_errors(job_id);
CREATE INDEX idx_records_lot_no ON records(lot_no);
CREATE INDEX idx_records_production_date ON records(production_date);
```

## Phase 1: Core Backend Implementation

### API Endpoints Specification

**Core Upload API**:
```python
# POST /api/upload
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks
) -> UploadResponse:
    """
    上傳並驗證檔案
    
    Returns:
    {
        "process_id": "uuid-v4",
        "filename": "data.csv", 
        "total_rows": 1000,
        "valid_rows": 980,
        "invalid_rows": 20,
        "status": "validated",
        "sample_errors": [
            {
                "row_index": 5,
                "field": "quantity",
                "error_code": "INVALID_TYPE", 
                "message": "數量必須為非負整數，當前值：-5"
            }
        ]
    }
    """

# GET /api/validate
@router.get("/validate")
async def get_validation_result(process_id: UUID) -> ValidationDetailResponse:
    """
    取得詳細驗證結果
    
    Returns:
    {
        "process_id": "uuid-v4",
        "status": "validated|processing|failed",
        "errors": [...], # 完整錯誤列表
        "preview_data": [...], # 前10筆有效資料
        "summary": {
            "total_rows": 1000,
            "valid_rows": 980, 
            "invalid_rows": 20
        }
    }
    """

# POST /api/import  
@router.post("/import")
async def import_data(request: ImportRequest) -> ImportResponse:
    """
    確認匯入資料
    
    Body: {"process_id": "uuid-v4"}
    
    Returns:
    {
        "process_id": "uuid-v4",
        "imported_rows": 980,
        "skipped_rows": 20,
        "elapsed_ms": 1250,
        "status": "completed",
        "summary": "成功匯入 980 筆資料，跳過 20 筆錯誤資料"
    }
    """

# GET /api/export/errors/{process_id}
@router.get("/export/errors/{process_id}")
async def export_errors_csv(process_id: UUID) -> StreamingResponse:
    """下載錯誤列的 CSV 檔案"""

# GET /healthz
@router.get("/healthz")
async def health_check() -> HealthResponse:
    """健康檢查端點"""
```

### Validation Rules Implementation

**Validation Service**:
```python
# services/validator.py
class DataValidator:
    REQUIRED_FIELDS = ['lot_no', 'product_name', 'quantity', 'production_date']
    LOT_NO_PATTERN = re.compile(r'^\d{7}_\d{2}$')
    
    async def validate_structure(self, df: pd.DataFrame) -> List[ValidationError]:
        """驗證欄位結構"""
        errors = []
        
        # 檢查必需欄位
        missing_fields = set(self.REQUIRED_FIELDS) - set(df.columns)
        if missing_fields:
            errors.append(ValidationError(
                row_index=0,
                field=None,
                error_code="MISSING_REQUIRED_FIELDS",
                message=f"缺少必需欄位: {', '.join(missing_fields)}"
            ))
            
        # 檢查未知欄位
        unknown_fields = set(df.columns) - set(self.REQUIRED_FIELDS)
        if unknown_fields:
            errors.append(ValidationError(
                row_index=0,
                field=None, 
                error_code="UNKNOWN_FIELDS",
                message=f"未知欄位: {', '.join(unknown_fields)}"
            ))
            
        return errors
    
    async def validate_data(self, df: pd.DataFrame) -> List[ValidationError]:
        """驗證資料內容"""
        errors = []
        
        for idx, row in df.iterrows():
            # lot_no 格式驗證
            if not self.LOT_NO_PATTERN.match(str(row['lot_no'])):
                errors.append(ValidationError(
                    row_index=idx + 1,
                    field='lot_no',
                    error_code='INVALID_FORMAT',
                    message=f'lot_no 格式錯誤，應為 7位數字_2位數字，當前值: {row["lot_no"]}'
                ))
            
            # quantity 驗證
            try:
                qty = int(row['quantity'])
                if qty < 0:
                    errors.append(ValidationError(
                        row_index=idx + 1,
                        field='quantity',
                        error_code='INVALID_RANGE', 
                        message=f'數量不能為負數，當前值: {qty}'
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    row_index=idx + 1,
                    field='quantity',
                    error_code='INVALID_TYPE',
                    message=f'數量必須為整數，當前值: {row["quantity"]}'
                ))
            
            # production_date 驗證
            try:
                pd.to_datetime(row['production_date'], format='%Y-%m-%d')
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    row_index=idx + 1,
                    field='production_date',
                    error_code='INVALID_DATE_FORMAT',
                    message=f'日期格式錯誤，應為 YYYY-MM-DD，當前值: {row["production_date"]}'
                ))
                
        return errors
```

## Phase 2: Frontend Implementation  

### React Components Structure

**Main Upload Flow**:
```typescript
// pages/Upload.tsx
export const Upload: React.FC = () => {
  const [step, setStep] = useState<'upload' | 'validate' | 'import' | 'complete'>('upload');
  const [processId, setProcessId] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  const handleFileUpload = async (file: File) => {
    const response = await uploadFile(file);
    setProcessId(response.process_id);
    setStep('validate');
  };

  const handleImport = async () => {
    await importData(processId!);
    setStep('complete');
  };

  return (
    <div className="upload-container">
      {step === 'upload' && <FileUploader onUpload={handleFileUpload} />}
      {step === 'validate' && (
        <ValidationResults 
          processId={processId!} 
          onImport={handleImport}
          onBack={() => setStep('upload')}
        />
      )}
      {step === 'import' && <ImportProgress processId={processId!} />}
      {step === 'complete' && <CompletionSummary processId={processId!} />}
    </div>
  );
};

// components/FileUploader.tsx  
export const FileUploader: React.FC<FileUploaderProps> = ({ onUpload }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const handleDrop = async (event: React.DragEvent) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files);
    const file = files[0];
    
    if (!validateFileType(file)) {
      alert('僅支援 CSV 和 Excel (.xlsx) 檔案');
      return;
    }
    
    if (!validateFileSize(file)) {
      alert('檔案大小不能超過 10MB');
      return;
    }
    
    setIsUploading(true);
    try {
      await onUpload(file);
    } finally {
      setIsUploading(false);
    }
  };
  
  return (
    <div 
      className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
    >
      {isUploading ? (
        <ProgressBar message="上傳檔案中..." />
      ) : (
        <>
          <div className="upload-icon"></div>
          <p>拖拽檔案到此處或點擊選擇檔案</p>
          <p className="file-info">支援 CSV, Excel (.xlsx) 檔案，最大 10MB</p>
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
            style={{ display: 'none' }}
            id="file-input"
          />
          <label htmlFor="file-input" className="upload-button">
            選擇檔案
          </label>
        </>
      )}
    </div>
  );
};
```

## Phase 3: Testing & Quality Assurance

### Testing Strategy

**Backend Tests**:
```python
# tests/test_upload_flow.py
@pytest.mark.asyncio
async def test_complete_upload_flow():
    """測試完整上傳流程"""
    # 1. 上傳檔案
    with open("fixtures/valid_sample.csv", "rb") as f:
        response = await client.post("/api/upload", files={"file": f})
    
    assert response.status_code == 200
    data = response.json()
    process_id = data["process_id"]
    
    # 2. 驗證結果
    response = await client.get(f"/api/validate?process_id={process_id}")
    assert response.status_code == 200
    
    # 3. 匯入資料  
    response = await client.post("/api/import", json={"process_id": process_id})
    assert response.status_code == 200
    assert data["imported_rows"] > 0

# tests/test_validator.py  
@pytest.mark.asyncio
async def test_lot_no_validation():
    """測試 lot_no 格式驗證"""
    validator = DataValidator()
    
    # 有效格式
    df_valid = pd.DataFrame({'lot_no': ['1234567_01'], 'product_name': ['test'], 'quantity': [10], 'production_date': ['2025-01-01']})
    errors = await validator.validate_data(df_valid)
    assert len(errors) == 0
    
    # 無效格式
    df_invalid = pd.DataFrame({'lot_no': ['123456_1'], 'product_name': ['test'], 'quantity': [10], 'production_date': ['2025-01-01']})
    errors = await validator.validate_data(df_invalid) 
    assert len(errors) == 1
    assert errors[0].error_code == 'INVALID_FORMAT'
```

**Frontend Tests**:
```typescript
// tests/components/FileUploader.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { FileUploader } from '../components/FileUploader';

test('should accept valid CSV file', async () => {
  const mockOnUpload = jest.fn();
  render(<FileUploader onUpload={mockOnUpload} />);
  
  const file = new File(['col1,col2\nval1,val2'], 'test.csv', { type: 'text/csv' });
  const input = screen.getByLabelText(/選擇檔案/);
  
  fireEvent.change(input, { target: { files: [file] } });
  
  expect(mockOnUpload).toHaveBeenCalledWith(file);
});

test('should reject oversized file', () => {
  const mockOnUpload = jest.fn();
  render(<FileUploader onUpload={mockOnUpload} />);
  
  // Create 15MB file (over 10MB limit)
  const largeContent = 'x'.repeat(15 * 1024 * 1024);
  const file = new File([largeContent], 'large.csv', { type: 'text/csv' });
  const input = screen.getByLabelText(/選擇檔案/);
  
  fireEvent.change(input, { target: { files: [file] } });
  
  expect(mockOnUpload).not.toHaveBeenCalled();
  expect(screen.getByText(/檔案大小不能超過 10MB/)).toBeInTheDocument();
});
```

### CI/CD Pipeline (.github/workflows/ci.yml)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_USER: test_user
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
          
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: 3.12
        
    - name: Install dependencies
      run: |
        cd backend
        pip install -e .[dev]
        
    - name: Run linting
      run: |
        cd backend
        ruff check .
        black --check .
        mypy .
        
    - name: Run tests
      run: |
        cd backend  
        pytest --cov=app --cov-report=xml
        
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
        
  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
        cache-dependency-path: frontend/package-lock.json
        
    - name: Install dependencies  
      run: |
        cd frontend
        npm ci
        
    - name: Run linting
      run: |
        cd frontend
        npm run lint
        npm run type-check
        
    - name: Run tests
      run: |
        cd frontend
        npm run test
        
    - name: Build
      run: |
        cd frontend
        npm run build
        
  docker-build:
    needs: [backend-tests, frontend-tests]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Build and test Docker images
      run: |
        docker-compose -f docker-compose.yml build
        docker-compose -f docker-compose.yml up -d
        
        # Health check
        timeout 60 bash -c 'until curl -f http://localhost:8000/healthz; do sleep 2; done'
        timeout 60 bash -c 'until curl -f http://localhost:5173; do sleep 2; done'
        
        docker-compose down
```

## Phase 4: Documentation & Deployment

### README.md Quick Start Guide

```markdown
# 表單上傳驗證系統 MVP

最小可行的檔案處理系統，支援 CSV/Excel 上傳、即時驗證、資料預覽與批次匯入。

##  快速開始

### 前置需求
- Docker & Docker Compose
- Node.js 20+ (開發環境)
- Python 3.12+ (開發環境)

### 一鍵啟動 (推薦)

```bash
# 1. 複製環境變數
cp .env.example .env

# 2. 啟動所有服務 (資料庫 + API + 前端)
docker-compose up -d

# 3. 初始化資料庫
docker-compose exec backend alembic upgrade head

# 4. 開啟瀏覽器
# 前端: http://localhost:5173
# API 文件: http://localhost:8000/docs  
# pgAdmin: http://localhost:5050 (admin@example.com / admin)
```

### 開發環境啟動

```bash
# 後端開發
cd backend
pip install -e .[dev]
pre-commit install
uvicorn app.main:app --reload --port 8000

# 前端開發  
cd frontend
npm install
npm run dev  # http://localhost:5173

# 資料庫 (Docker)
docker-compose up -d db
```

##  主要功能

### 檔案上傳與驗證
- 支援 CSV (UTF-8) 和 Excel (.xlsx) 格式
- 檔案大小限制 10MB
- 即時格式與內容驗證
- 友善的中文錯誤訊息

### 資料預覽與匯入
- 可匯入資料的即時預覽
- 詳細錯誤列表顯示
- 錯誤資料 CSV 下載
- 交易性批次匯入

### 追蹤與日誌
- 每次操作產生唯一 process_id
- 完整的操作審計日誌
- 處理時間與效能監控

##  API 規格

### 核心端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/api/upload` | 檔案上傳與驗證 |
| GET | `/api/validate?process_id=...` | 獲取詳細驗證結果 |
| POST | `/api/import` | 確認匯入資料 |
| GET | `/api/export/errors/{process_id}` | 下載錯誤 CSV |
| GET | `/healthz` | 健康檢查 |

### 範例請求

**上傳檔案**:
```bash
curl -X POST "http://localhost:8000/api/upload" \
     -F "file=@sample.csv" \
     -H "Content-Type: multipart/form-data"
```

**匯入資料**:
```bash
curl -X POST "http://localhost:8000/api/import" \
     -H "Content-Type: application/json" \
     -d '{"process_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

## 測試

### 執行測試

```bash
# 後端測試
cd backend
pytest --cov=app

# 前端測試  
cd frontend
npm run test

# 整合測試
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### 測試檔案

專案提供測試用的範例檔案：
- `backend/tests/fixtures/valid_sample.csv` - 有效資料範例
- `backend/tests/fixtures/invalid_sample.csv` - 包含錯誤的資料
- `backend/tests/fixtures/sample.xlsx` - Excel 格式範例

##  驗證規則

### 必需欄位
- `lot_no`: 批號 (格式: 7位數字_2位數字，如 1234567_01)
- `product_name`: 產品名稱 (1-100 字元)
- `quantity`: 數量 (非負整數)
- `production_date`: 生產日期 (YYYY-MM-DD 格式)

### 錯誤分級
- **阻擋性錯誤**: 欄位結構問題，無法進行匯入
- **列級錯誤**: 資料格式或內容錯誤，該列會被跳過
- **警告**: 資料品質問題，不影響匯入但建議檢查

##  開發指南

### 程式碼品質
```bash
# Python (後端)
ruff check . && black . && mypy .

# TypeScript (前端)  
npm run lint && npm run type-check
```

### 資料庫 Migration
```bash
# 建立新的 migration
alembic revision --autogenerate -m "add new table"

# 執行 migration  
alembic upgrade head

# 回滾 migration
alembic downgrade -1
```

### 除錯模式
```bash
# 開啟詳細日誌
export LOG_LEVEL=DEBUG
export DEBUG=true

# 關閉 CORS (僅開發環境)
export CORS_ORIGINS=*
```

## 常見問題

### Windows PowerShell 權限問題
```powershell
# 設定執行政策 (管理員權限)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine

# 或僅針對當前 process
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

### 上傳檔案大小限制
預設限制 10MB，可透過環境變數調整：
```bash
MAX_UPLOAD_SIZE_MB=20  # 調整為 20MB
```

### CORS 錯誤
如果前後端在不同 port 開發遇到 CORS 問題：
```bash
# 在 .env 中設定
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080
```

### 資料庫連線問題
```bash
# 檢查資料庫是否啟動
docker-compose ps

# 查看資料庫日誌
docker-compose logs db

# 重啟資料庫服務
docker-compose restart db
```

### 檔案編碼問題
- 上傳 CSV 建議使用 UTF-8 編碼 (支援 BOM)
- Excel 檔案請確保為 .xlsx 格式 (不支援舊版 .xls)

### 效能問題
- 建議單次上傳檔案 ≤ 50,000 列
- 大檔案處理時間較長，請耐心等待驗證完成
- 可透過 `/healthz` 端點檢查系統狀態

## 監控與維運

### 健康檢查
- API: `GET /healthz`
- 前端: `GET http://localhost:5173`  
- 資料庫: `docker-compose exec db pg_isready`

### 日誌查看
```bash
# API 日誌
docker-compose logs -f backend

# 前端日誌  
docker-compose logs -f frontend

# 資料庫日誌
docker-compose logs -f db
```

### 備份與還原
```bash
# 備份資料庫
docker-compose exec db pg_dump -U app form_analysis_db > backup.sql

# 還原資料庫
docker-compose exec -T db psql -U app form_analysis_db < backup.sql
```

##  部署

### Production 環境
```bash
# 1. 複製並調整 production 環境變數
cp .env.example .env.prod

# 2. 使用 production compose 檔案
docker-compose -f docker-compose.prod.yml up -d

# 3. 執行 migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 環境變數檢查清單
- [ ] `POSTGRES_PASSWORD` 使用強密碼
- [ ] `DEBUG=false` 關閉除錯模式
- [ ] `CORS_ORIGINS` 設定正確的前端網域
- [ ] `LOG_LEVEL=INFO` 適當的日誌級別

## 支援
None
---

**版本**: v1.0.0 | **更新日期**: 2025-11-08
```

## 執行清單與待辦任務

### Phase 1: 專案初始化 (1-2 天)
- [ ] **T1.1**: 建立專案結構與目錄
- [ ] **T1.2**: 設定 pyproject.toml 與 package.json
- [ ] **T1.3**: 建立 Docker 與 docker-compose 設定
- [ ] **T1.4**: 設定 pre-commit hooks 與程式碼品質工具
- [ ] **T1.5**: 建立 .env.example 與環境變數文件
- [ ] **T1.6**: 初始化 Git repository 與 .gitignore

### Phase 2: 後端核心實作 (3-4 天)  
- [ ] **T2.1**: 建立 FastAPI 應用程式骨架 (main.py, config.py)
- [ ] **T2.2**: 設定 SQLAlchemy 與資料庫連線
- [ ] **T2.3**: 建立 Alembic 設定與初始 migration
- [ ] **T2.4**: 實作資料模型 (upload_jobs, upload_errors, records)
- [ ] **T2.5**: 建立 Pydantic schemas 與 API 回應格式
- [ ] **T2.6**: 實作檔案解析服務 (CSV/Excel)
- [ ] **T2.7**: 實作資料驗證服務 (格式與內容驗證)
- [ ] **T2.8**: 實作資料匯入服務 (交易性寫入)

### Phase 3: API 端點實作 (2-3 天)
- [ ] **T3.1**: 實作 `/api/upload` 端點 (檔案上傳與驗證)
- [ ] **T3.2**: 實作 `/api/validate` 端點 (詳細驗證結果)
- [ ] **T3.3**: 實作 `/api/import` 端點 (確認匯入)
- [ ] **T3.4**: 實作 `/api/export/errors` 端點 (錯誤 CSV 下載)
- [ ] **T3.5**: 實作 `/healthz` 健康檢查端點
- [ ] **T3.6**: 建立中介層 (request_id, 耗時記錄, CORS)
- [ ] **T3.7**: 設定 OpenAPI 文件與 Swagger UI

### Phase 4: 前端實作 (3-4 天)
- [ ] **T4.1**: 建立 Vite + React + TypeScript 專案骨架
- [ ] **T4.2**: 建立 API 呼叫封裝 (axios client)
- [ ] **T4.3**: 實作檔案上傳元件 (拖拽 + 選擇檔案)
- [ ] **T4.4**: 實作驗證結果顯示 (預覽表格 + 錯誤列表)
- [ ] **T4.5**: 實作匯入確認與進度顯示
- [ ] **T4.6**: 實作完成結果摘要頁面
- [ ] **T4.7**: 建立 TypeScript 型別定義
- [ ] **T4.8**: 設定前端 linting 與 formatting

### Phase 5: 測試與品質保證 (2-3 天)
- [ ] **T5.1**: 建立後端單元測試 (服務層測試)  
- [ ] **T5.2**: 建立後端整合測試 (API 端點測試)
- [ ] **T5.3**: 建立前端元件測試
- [ ] **T5.4**: 建立端到端測試 (完整上傳流程)
- [ ] **T5.5**: 準備測試檔案與測試資料
- [ ] **T5.6**: 設定 CI/CD pipeline (GitHub Actions)
- [ ] **T5.7**: 效能測試與大檔案處理測試

### Phase 6: 部署與文件 (1-2 天)
- [ ] **T6.1**: 完善 README.md 文件
- [ ] **T6.2**: 建立 production Docker 設定
- [ ] **T6.3**: 設定健康檢查與監控
- [ ] **T6.4**: 建立部署指南與維運手冊
- [ ] **T6.5**: 使用者驗收測試
- [ ] **T6.6**: 效能調優與最終測試

### 總預估時程: 12-18 天 (2-3 週)

每個任務都有明確的交付成果，可獨立驗收，便於追蹤進度與品質控制。
