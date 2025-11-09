# Tasks: 表單上傳驗證系統 MVP - Sprint 1

**Feature**: 檔案上傳 + 驗證 + 預覽 + 匯入系統  
**Sprint Duration**: 1 週 (5 個工作天)  
**Team Size**: 1-2 開發者  
**Priority**: P1 (核心 MVP 功能)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Sprint 1 Tasks (Week 1)

### Phase 1: Project Setup & Infrastructure (Day 1)

#### T001 [Foundation] 專案初始化與 Git 設定
**Story**: Foundation  
**Description**: 建立專案根目錄結構，初始化 Git repository，設定 .gitignore
**Files**: 
- `/.gitignore`
- `/README.md` (skeleton)
- 建立 `backend/`, `frontend/` 目錄結構

**DoD (Definition of Done)**:
- [ ] Git repository 已初始化並設定適當的 .gitignore
- [ ] 專案根目錄結構完整 (backend/, frontend/, docs/)
- [ ] README.md 包含專案簡介與基本結構說明
- [ ] 建立基本的 LICENSE 檔案
- [ ] 初始 commit 已完成

#### T002 [Foundation] Docker Compose 環境設定
**Story**: Foundation  
**Description**: 建立完整的 Docker Compose 設定，包含 PostgreSQL、pgAdmin、API、Frontend 服務
**Files**:
- `/docker-compose.yml`
- `/docker-compose.override.yml` (development)
- `/.env.example`
- `/backend/Dockerfile`
- `/frontend/Dockerfile`

**DoD**:
- [ ] docker-compose.yml 包含所有必要服務 (db, backend, frontend, pgadmin)
- [ ] 所有服務都有適當的 healthcheck 設定
- [ ] .env.example 包含所有必要的環境變數及說明
- [ ] `docker-compose up -d` 可以成功啟動所有服務
- [ ] 資料庫可以透過 pgAdmin 連線 (http://localhost:5050)
- [ ] 各服務之間的網路通訊正常

#### T003 [P] [Foundation] 後端專案結構與依賴設定
**Story**: Foundation  
**Description**: 建立後端 FastAPI 專案骨架，設定 pyproject.toml 與依賴管理
**Files**:
- `/backend/pyproject.toml`
- `/backend/requirements.txt`
- `/backend/app/__init__.py`
- `/backend/app/main.py`
- `/backend/app/core/__init__.py`
- `/backend/app/core/config.py`

**DoD**:
- [ ] pyproject.toml 包含所有必要依賴 (FastAPI, SQLAlchemy, Alembic 等)
- [ ] app/main.py 包含基本的 FastAPI 應用程式設定
- [ ] config.py 包含環境變數讀取與設定管理
- [ ] `pip install -e .` 可以成功安裝專案
- [ ] FastAPI 應用程式可以啟動 (`uvicorn app.main:app`)
- [ ] 基本的 CORS 設定已配置

#### T004 [P] [Foundation] 前端專案結構與依賴設定
**Story**: Foundation  
**Description**: 建立前端 Vite + React + TypeScript 專案，設定基本依賴與建置工具
**Files**:
- `/frontend/package.json`
- `/frontend/vite.config.ts`
- `/frontend/tsconfig.json`
- `/frontend/src/main.tsx`
- `/frontend/src/App.tsx`
- `/frontend/index.html`

**DoD**:
- [ ] package.json 包含所有必要依賴 (React, TypeScript, Vite 等)
- [ ] vite.config.ts 包含適當的開發與建置設定
- [ ] tsconfig.json 設定嚴格的 TypeScript 檢查
- [ ] `npm install` 可以成功安裝依賴
- [ ] `npm run dev` 可以啟動開發伺服器 (http://localhost:5173)
- [ ] 基本的 React 應用程式可以正常顯示

### Phase 2: Backend Core Implementation (Day 2)

#### T005 [Backend] 健康檢查端點實作
**Story**: Infrastructure  
**Description**: 實作 /healthz 端點，包含資料庫連線檢查與系統狀態
**Files**:
- `/backend/app/api/__init__.py`
- `/backend/app/api/routes_health.py`
- `/backend/app/core/database.py`

**DoD**:
- [ ] /healthz 端點回傳系統健康狀態 (HTTP 200/503)
- [ ] 包含資料庫連線狀態檢查
- [ ] 包含應用程式版本與啟動時間資訊
- [ ] 回傳格式為標準 JSON ({"status": "healthy", "database": "connected", ...})
- [ ] Docker healthcheck 可以正常使用此端點
- [ ] 有適當的錯誤處理 (資料庫連線失敗時)

#### T006 [Backend] SQLAlchemy 模型與資料庫設定 ✅ **COMPLETED**
**Story**: Data Layer  
**Description**: 建立資料庫模型 (upload_jobs, upload_errors, records)，設定 SQLAlchemy 連線
**Files**:
- `/backend/app/models/__init__.py` ✅
- `/backend/app/models/upload_job.py` ✅ (renamed)
- `/backend/app/models/upload_error.py` ✅ (renamed) 
- `/backend/app/models/record.py` ✅ (renamed)
- `/backend/app/core/database.py` ✅

**DoD**:
- [x] 所有資料表模型符合 spec 中的 schema 定義
- [x] 適當的索引與約束條件已設定
- [x] SQLAlchemy session 管理正確實作
- [x] 模型間的關聯關係正確設定 (Foreign Keys)
- [x] 資料庫連線池設定適當
- [x] 所有模型都有適當的 __repr__ 方法

#### T007 [Backend] Alembic Migration 設定與初始 Schema ✅ **COMPLETED**
**Story**: Data Layer  
**Description**: 設定 Alembic migration 環境，建立初始資料庫 schema migration
**Files**:
- `/backend/alembic.ini` ✅
- `/backend/alembic/env.py` ✅
- `/backend/alembic/versions/2025_11_08_0122-ae889647f4f2_create_initial_tables_upload_jobs_.py` ✅
- `/backend/database_schema.sql` ✅ (SQL script generated)
- `/backend/DATABASE_SETUP.md` ✅ (setup guide)

**DoD**:
- [x] Alembic 環境正確設定並可連接資料庫
- [x] 初始 migration 包含所有必要的資料表
- [x] SQL 腳本已生成並驗證 (offline mode)
- [x] Migration 檔案包含適當的索引與約束條件  
- [x] 支援 async SQLAlchemy 設定
- [ ] `alembic upgrade head` 需要 PostgreSQL 連線 (待資料庫啟動)

#### T008 [Backend] Pydantic Schemas 定義 ✅ **COMPLETED**
**Story**: API Layer  
**Description**: 建立 API 請求/回應的 Pydantic models，包含驗證規則
**Files**:
- `/backend/app/schemas/__init__.py` ✅
- `/backend/app/schemas/upload_job_schema.py` ✅ (Create/Read/Update)
- `/backend/app/schemas/upload_error_schema.py` ✅ (Create/Read)
- `/backend/app/schemas/record_schema.py` ✅ (Create/Read with validation)

**DoD**:
- [x] 所有主要模型都有對應的 request/response schema
- [x] Schema 包含適當的驗證規則 (批號格式驗證等)
- [x] 錯誤回應格式標準化 
- [x] 支援 OpenAPI 文件自動生成 (examples included)
- [x] 所有 schema 都有適當的範例值 (examples)
- [x] 類型標註完整且正確 (Pydantic v2)

### Phase 3: Core Services Implementation (Day 3)

#### T009 [Backend] 檔案解析服務實作
**Story**: US1 (檔案上傳)  
**Description**: 實作 CSV/Excel 檔案解析服務，支援多種格式與編碼
**Files**:
- `/backend/app/services/__init__.py`
- `/backend/app/services/file_parser.py`
- `/backend/app/utils/file_utils.py`

**DoD**:
- [ ] 支援 CSV (UTF-8, 含/不含 BOM) 和 Excel (.xlsx) 格式
- [ ] 檔案大小檢查 (最大 10MB)
- [ ] 檔案類型驗證 (MIME type checking)
- [ ] 檔案編碼自動偵測與轉換
- [ ] 解析結果標準化為 pandas DataFrame
- [ ] 適當的錯誤處理 (檔案損壞、格式錯誤等)
- [ ] 支援檔案暫存與清理機制

#### T010 [Backend] 資料驗證服務實作
**Story**: US2 (即時驗證)  
**Description**: 實作資料驗證邏輯，包含欄位檢查、格式驗證、業務規則驗證
**Files**:
- `/backend/app/services/validator.py`
- `/backend/app/utils/validation_rules.py`

**DoD**:
- [ ] 必要欄位檢查 (lot_no, product_name, quantity, production_date)
- [ ] lot_no 格式驗證 (7位數字_2位數字 pattern)
- [ ] quantity 數值驗證 (非負整數)
- [ ] production_date 日期格式驗證 (YYYY-MM-DD)
- [ ] 錯誤訊息中文化且具體明確
- [ ] 錯誤分類 (阻擋性/列級/警告)
- [ ] 批次驗證效能最佳化
- [ ] 驗證規則可配置與擴展

#### T011 [Backend] 資料匯入服務實作
**Story**: US3 (確認匯入)  
**Description**: 實作交易性資料匯入服務，支援批次寫入與錯誤回滾
**Files**:
- `/backend/app/services/importer.py`
- `/backend/app/services/audit_logger.py`

**DoD**:
- [ ] 交易性批次匯入 (全部成功或全部回滾)
- [ ] 重複資料檢查與處理 (lot_no 唯一性)
- [ ] 匯入進度追蹤與統計
- [ ] 操作審計日誌記錄 (process_id, 使用者, IP, 時間)
- [ ] 效能最佳化 (批次 INSERT)
- [ ] 詳細的匯入結果報告
- [ ] 支援大量資料匯入 (分批處理)

### Phase 4: API Endpoints Implementation (Day 4)

#### T012 [Backend] 檔案上傳 API 端點
**Story**: US1 (檔案上傳)  
**Description**: 實作 POST /api/upload 端點，處理檔案上傳與初步驗證
**Files**:
- `/backend/app/api/routes_upload.py`
- `/backend/app/core/middleware.py`

**DoD**:
- [ ] 支援 multipart/form-data 檔案上傳
- [ ] 檔案大小與類型前置檢查
- [ ] 非同步檔案處理與暫存
- [ ] 產生唯一 process_id
- [ ] 回傳驗證概要 (總筆數、有效筆數、錯誤筆數)
- [ ] 適當的錯誤處理與狀態碼
- [ ] request_id 中介層記錄
- [ ] 處理時間監控

#### T013 [Backend] 驗證結果查詢 API 端點
**Story**: US2 (即時驗證)  
**Description**: 實作 GET /api/validate 端點，提供詳細驗證結果查詢
**Files**:
- `/backend/app/api/routes_validate.py`

**DoD**:
- [ ] 支援 process_id 參數查詢
- [ ] 回傳完整錯誤列表與詳細資訊
- [ ] 提供有效資料預覽 (前 10-20 筆)
- [ ] 支援錯誤分頁與篩選 (可選)
- [ ] 查詢效能最佳化 (適當索引)
- [ ] 處理查詢不存在的 process_id
- [ ] 回應格式符合 API 規格

#### T014 [Backend] 資料匯入 API 端點
**Story**: US3 (確認匯入)  
**Description**: 實作 POST /api/import 端點，執行資料匯入操作
**Files**:
- `/backend/app/api/routes_import.py`

**DoD**:
- [ ] 驗證 process_id 有效性與狀態
- [ ] 調用匯入服務執行交易性寫入
- [ ] 回傳詳細匯入結果 (成功/跳過/失敗筆數)
- [ ] 處理並發匯入請求 (防重複匯入)
- [ ] 匯入進度追蹤 (長時間操作)
- [ ] 完整的錯誤處理與復原機制
- [ ] 匯入完成後狀態更新

#### T015 [Backend] 錯誤 CSV 匯出端點
**Story**: US4 (錯誤處理)  
**Description**: 實作 GET /api/export/errors/{process_id} 端點，提供錯誤資料 CSV 下載
**Files**:
- `/backend/app/api/routes_export.py`
- `/backend/app/utils/csv_generator.py`

**DoD**:
- [ ] 動態生成錯誤資料 CSV 檔案
- [ ] 包含原始資料與錯誤訊息欄位
- [ ] 適當的 HTTP headers (Content-Disposition, MIME type)
- [ ] 支援 streaming response (大檔案)
- [ ] 檔案名稱包含 process_id 與時間戳
- [ ] 處理無錯誤資料的情況
- [ ] CSV 格式符合中文顯示需求 (UTF-8 BOM)

### Phase 5: Frontend Implementation (Day 4-5)

#### T016 [P] [Frontend] API 通訊層建立
**Story**: Frontend Infrastructure  
**Description**: 建立前端 API 呼叫封裝，包含錯誤處理與型別定義
**Files**:
- `/frontend/src/lib/api.ts`
- `/frontend/src/types/api.ts`
- `/frontend/src/types/upload.ts`

**DoD**:
- [ ] 封裝所有後端 API 端點呼叫
- [ ] 完整的 TypeScript 型別定義
- [ ] 統一的錯誤處理機制
- [ ] 請求/回應攔截器設定
- [ ] 支援 FormData 檔案上傳
- [ ] API base URL 可透過環境變數設定
- [ ] 適當的 timeout 與 retry 機制

#### T017 [P] [Frontend] 檔案上傳元件
**Story**: US1 (檔案上傳)  
**Description**: 實作檔案上傳元件，支援拖拽與點選上傳
**Files**:
- `/frontend/src/components/FileUploader.tsx`
- `/frontend/src/components/ProgressBar.tsx`
- `/frontend/src/utils/file.ts`

**DoD**:
- [ ] 支援拖拽上傳 (drag & drop)
- [ ] 支援點選選擇檔案
- [ ] 檔案類型與大小前端驗證
- [ ] 上傳進度顯示
- [ ] 友善的視覺回饋 (hover effects)
- [ ] 錯誤狀態顯示與重試機制
- [ ] 響應式設計 (桌面與平板)
- [ ] 可訪問性支援 (ARIA labels)

#### T018 [Frontend] 驗證結果頁面
**Story**: US2 (即時驗證)  
**Description**: 實作驗證結果顯示頁面，包含資料預覽與錯誤列表
**Files**:
- `/frontend/src/pages/Validation.tsx`
- `/frontend/src/components/PreviewTable.tsx`
- `/frontend/src/components/ErrorList.tsx`

**DoD**:
- [ ] 顯示驗證統計摘要 (總筆數、有效筆數、錯誤筆數)
- [ ] 有效資料預覽表格 (前 10-20 筆)
- [ ] 錯誤列表顯示 (列號、欄位、錯誤訊息)
- [ ] 錯誤可依類型篩選與排序
- [ ] 支援錯誤 CSV 下載
- [ ] 表格水平滾動支援
- [ ] 載入狀態與錯誤處理
- [ ] 確認匯入與返回按鈕

#### T019 [Frontend] 主要頁面流程整合
**Story**: Complete User Journey  
**Description**: 整合所有頁面元件，建立完整的使用者流程
**Files**:
- `/frontend/src/pages/Upload.tsx`
- `/frontend/src/pages/Import.tsx`
- `/frontend/src/App.tsx`
- `/frontend/src/components/Layout.tsx`

**DoD**:
- [ ] 完整的頁面流程 (上傳→驗證→匯入→完成)
- [ ] 頁面間狀態管理與資料傳遞
- [ ] 適當的導航與返回功能
- [ ] 載入狀態與進度指示
- [ ] 統一的錯誤處理與通知
- [ ] 響應式佈局設計
- [ ] 瀏覽器返回按鈕支援
- [ ] 使用者友善的介面設計

### Phase 6: Quality & Documentation (Day 5)

#### T020 [P] [Quality] 程式碼品質工具設定
**Story**: Code Quality  
**Description**: 設定 linting、formatting、type checking 與 pre-commit hooks
**Files**:
- `/pyproject.toml` (ruff, black, mypy 設定)
- `/frontend/eslint.config.js`
- `/frontend/prettier.config.js`
- `/.pre-commit-config.yaml`

**DoD**:
- [ ] Python: ruff + black + mypy 設定完成
- [ ] TypeScript: eslint + prettier + tsc 設定完成
- [ ] pre-commit hooks 涵蓋所有程式碼品質檢查
- [ ] 所有現有程式碼通過品質檢查
- [ ] IDE 整合設定檔案 (.vscode/settings.json)
- [ ] 團隊一致的程式碼風格
- [ ] CI/CD pipeline 品質檢查整合

#### T021 [P] [Testing] 基礎測試框架建立
**Story**: Testing Infrastructure  
**Description**: 建立 pytest 與 vitest 測試環境，撰寫核心功能測試
**Files**:
- `/backend/tests/conftest.py`
- `/backend/tests/test_health.py`
- `/backend/tests/test_file_parser.py`
- `/frontend/src/tests/setup.ts`
- `/frontend/src/tests/FileUploader.test.tsx`

**DoD**:
- [ ] pytest 環境設定與資料庫測試 fixtures
- [ ] vitest 環境設定與 React 測試工具
- [ ] 健康檢查端點測試
- [ ] 檔案解析服務單元測試
- [ ] 檔案上傳元件測試
- [ ] 測試覆蓋率基線建立 (>70%)
- [ ] CI 環境測試執行設定
- [ ] 測試資料與 fixtures 準備

#### T022 [Documentation] README 與 API 文件完善
**Story**: Documentation  
**Description**: 完善 README.md 快速開始指南與 API 文件
**Files**:
- `/README.md`
- `/docs/api.md`
- `/docs/development.md`

**DoD**:
- [ ] 完整的一鍵啟動指南 (Docker + 開發環境)
- [ ] API 端點文件與範例
- [ ] 常見問題與疑難排解
- [ ] 開發環境設定指南
- [ ] 專案架構與技術棧說明
- [ ] 貢獻指南與程式碼規範
- [ ] OpenAPI/Swagger 自動文件設定
- [ ] 部署相關文件

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Backend Core (Phase 2)**: Depends on T001, T002, T003 completion
- **Services (Phase 3)**: Depends on T005, T006, T007, T008 completion  
- **API Endpoints (Phase 4)**: Depends on T009, T010, T011 completion
- **Frontend (Phase 5)**: Depends on T004 completion, can parallel with Phase 4
- **Quality (Phase 6)**: Can run parallel with development, final integration needed

### Task Dependencies

**Critical Path**:
T001 → T002 → T003 → T006 → T007 → T009 → T010 → T011 → T012 → T013 → T014

**Parallel Tracks**:
- Frontend: T004 → T016 → T017 → T018 → T019 (can run parallel with backend)
- Quality: T020, T021, T022 (can run throughout the sprint)

### Daily Breakdown

**Day 1**: T001, T002, T003, T004 (Foundation & Setup)  
**Day 2**: T005, T006, T007, T008 (Backend Core)  
**Day 3**: T009, T010, T011 (Services Implementation)  
**Day 4**: T012, T013, T014, T015, T016, T017 (API & Frontend Start)  
**Day 5**: T018, T019, T020, T021, T022 (Integration & Quality)

## Sprint Success Criteria

### Functional Criteria
- [ ] 完整的檔案上傳→驗證→預覽→匯入流程可以執行
- [ ] 支援 CSV 與 Excel 檔案格式
- [ ] 錯誤驗證與友善訊息顯示
- [ ] 資料可以成功匯入資料庫
- [ ] 錯誤資料可以下載 CSV 檔案

### Technical Criteria  
- [ ] Docker Compose 一鍵啟動環境
- [ ] 所有 API 端點正常運作並有適當文件
- [ ] 前端可以與後端 API 正常通訊
- [ ] 基本測試覆蓋率達到 70%
- [ ] 程式碼品質工具全部通過

### Documentation Criteria
- [ ] README 包含完整的快速開始指南
- [ ] API 文件清晰且有範例
- [ ] 常見問題文件涵蓋主要使用情境

## Risk Mitigation

### Technical Risks
- **檔案解析相容性**: 準備多種格式的測試檔案
- **資料庫 Migration**: 測試 upgrade/downgrade 流程  
- **CORS 設定**: 確保前後端通訊正常
- **檔案大小限制**: 測試邊界條件

### Timeline Risks  
- **依賴阻塞**: 優先完成關鍵路徑任務
- **整合問題**: 每日進行整合測試
- **品質債務**: 並行執行品質檢查任務

---

**Total Tasks**: 22  
**Estimated Effort**: 40-50 小時  
**Sprint Goal**: 建立可運作的檔案上傳驗證 MVP，支援完整使用者流程