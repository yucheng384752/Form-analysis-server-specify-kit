# 專案重構與功能實作清單 (v2.1)

> v2.1 修正重點（相較 v2.0）
> - 補齊 Import Job API：`/errors`、`/cancel`、`/commit`
> - 明確化 ImportJob 狀態機（移除「PENDING」模糊狀態），支援「進庫前可取消」
> - 補上批次混上傳規則：同批次 **tenant/format/header_fingerprint** 必須一致
> - Tenant Resolver 固定使用 Header `X-Tenant-Id`，並明確「單 tenant / default tenant」判定
> - P3 欄位統一為 `production_date_yyyymmdd:int`（利於 unique/index/查詢交集）
> - Traceability Search 改為「優先走 Trace Index，缺索引才 fallback join」
> - Inline Edit API 修正為 `PATCH /api/records/{table_code}/{id}`，並加入 edit_reasons / row_edits 流程
> - 前端整合補齊：Axios interceptor 注入 tenant、Job Error Table、Cancel、PDF 轉檔下載/套用、Trace Modal 等元件拆分

---

## Level 0: 基礎設施與環境準備 (Infrastructure)
**目標：建立支援非同步任務與快取的執行環境。**

### L0-01 Docker Compose 更新
*   **實作內容**：
    *   修改 `docker-compose.yml`，新增 `redis` 服務（作為 Celery Broker & Backend）。
    *   新增 `worker` 服務（基於 backend image，執行 `celery -A app.celery_app worker`）。
    *   設定環境變數 `CELERY_BROKER_URL` 與 `CELERY_RESULT_BACKEND`。
*   **測試策略**：
    *   `docker-compose up -d` 後，檢查所有 container status 為 healthy。
    *   進入 backend container 執行簡單的 Celery task（如 `add(1, 1)`），確認 worker 有收到並執行。

### L0-02 專案結構調整
*   **實作內容**：
    *   建立 `app/celery_app.py` 初始化 Celery 實例。
    *   建立 `app/tasks/` 目錄，預先規劃 `import_tasks.py`, `pdf_tasks.py`。
    *   （建議）建立 `app/core/tenant_resolver.py`、`app/core/validation/` 等「核心層」模組，避免業務邏輯散落在 router。

---

## Level 1: 核心架構重構 (Core Infrastructure)
**目標：建立正確的資料庫結構與多租戶機制。**

### L1-1 Database Refactoring (拆表 + Mixin)
*   **實作內容**：
    *   **BaseRecordMixin** (`app/models/base_record.py`): 定義共用欄位  
        `id`, `tenant_id`, `lot_no_raw`, `lot_no_norm`, `schema_version_id`, `created_at`, `updated_at`, `extras(JSONB)`。
    *   **P1Record** (`app/models/p1_record.py`): 繼承 Mixin（P1: one lot -> one row）。
    *   **P2Record** (`app/models/p2_record.py`): 繼承 Mixin，新增 `winder_number`（必填）。
    *   **P3Record** (`app/models/p3_record.py`): 繼承 Mixin，新增：
        * `production_date_yyyymmdd:int`（由 csv `year-month-day` 正規化而來）
        * `machine_no`, `mold_no`
        * `product_id`（衍生欄位，可索引但不作真相）
    *   **Unique Constraints（DB 最終防線）**：
        * P1: `unique(tenant_id, lot_no_norm)`
        * P2: `unique(tenant_id, lot_no_norm, winder_number)`
        * P3: `unique(tenant_id, production_date_yyyymmdd, machine_no, mold_no, lot_no_norm)`
    *   **Index（查詢/交集加速）**：
        * `index(tenant_id, lot_no_norm)`（P1/P2/P3）
        * `index(tenant_id, production_date_yyyymmdd, machine_no, mold_no)`（P3 建議）
*   **測試策略 (重點)**：
    *   **Unit Test (`tests/models/test_records.py`)**:
        *   測試 Mixin 是否正確被繼承。
        *   測試 Unique Constraint：嘗試插入重複資料，斷言拋出 `IntegrityError`。
        *   測試 Relationship：確認 P1/P2/P3 與 Tenant 的關聯。

### L1-2 Tenant 機制（後端預設 tenant 支援單場域隱藏 UI）
*   **實作內容**：
    *   **Tenant Model**: `id`, `code`, `name`, `is_default`。
    *   **Dependency (`app/api/deps.py`)**: 實作 `get_current_tenant`（API 層強制依賴）。
        *   固定使用 Header：`X-Tenant-Id`
        *   邏輯：
            1) 若 Header 提供 → 查 DB（不存在回 404/422）
            2) 若未提供：
               - 若 tenants 總數=1 → 自動帶入該 tenant
               - 否則若 `is_default=true` 且唯一 → 自動帶入 default tenant
               - 否則 → Raise 422（要求指定 tenant）
*   **測試策略**：
    *   **Integration Test (`tests/api/test_tenant_dependency.py`)**:
        *   Case 1: 單 Tenant 環境，不帶 Header -> 預期成功。
        *   Case 2: 多 Tenant 環境，不帶 Header -> 預期失敗 (422)。
        *   Case 3: 帶錯誤的 Tenant ID -> 預期失敗 (404/422)。

### L1-3 Schema Registry & Normalization
*   **實作內容**：
    *   **Models**: `TableRegistry`, `SchemaVersions`
        * `SchemaVersions` 必含：`schema_hash`, `header_fingerprint`, `schema_json`
    *   **Utils**:
        *   `normalize_lot_no(val) -> int`: Regex 移除符號，轉 BIGINT；非法回 `E_LOT_FORMAT`
        *   `normalize_date(val) -> date|int`:
            - 支援 `1120101`（民國 YYYMMDD）→ `2023-01-01` / `20230101`
            - 支援 `20230101`、`2023-01-01`
            - 無法判斷回 `E_DATE_FORMAT`
*   **測試策略**：
    *   **Unit Test (`tests/utils/test_normalization.py`)**:
        *   Lot No: `123-45`, `123_45`, `12345` → `12345`；`abc` 報錯。
        *   Date: `1120101`, `20230101`, `2023-01-01` 皆輸出一致結果。

### L1-4 Alembic Migration
*   **實作內容**：
    *   設定 `alembic.ini` 與 `env.py` 支援 Async Engine。
    *   產生 `001_initial_schema.py`（初版可 autogenerate，後續維持手寫 migration）
    *   （必做）確認 migration 內含所有 unique/index（避免 race condition）
*   **測試策略**：
    *   **Migration Test**：空 Test DB 執行 `alembic upgrade head`，確認無錯誤並檢查 Table/Constraint 存在。

---

## Level 2: 資料寫入與驗證 (Ingestion & Validation)
**目標：實作可靠的批次匯入流程（整批成功才進庫；失敗可列出錯誤列）。**

### L2-1 Import Job Pipeline (狀態機 + API)
*   **實作內容**：
    *   [x] **Models**: `ImportJob`, `ImportFile`, `StagingRow`（存 JSONB）。
    *   [x] **Status Enum（固定）**：
        * `UPLOADED` → `PARSING` → `VALIDATING` → (`FAILED` | `READY`) → `COMMITTING` → (`COMPLETED` | `FAILED`)
        * 任何 `COMMITTING` 之前都允許 `CANCELLED`
    *   **API（補齊）**：
        * [x] `POST /api/import/jobs`：建立 Job（多檔）
        * [x] `GET /api/import/jobs/{id}`：查狀態/進度/統計
        * [x] `GET /api/import/jobs/{id}/errors`：錯誤列分頁（只回 error rows）
        * `POST /api/import/jobs/{id}/cancel`：進庫前取消
        * [x] `POST /api/import/jobs/{id}/commit`：手動觸發 commit（若採自動 commit，則標示為 internal/可保留）
    *   **Progress**：至少提供 `progress 0-100` 與 `error_count`
*   **測試策略**：
    *   建 job → 狀態正確更新、progress 變化合理。
    *   取消 job → 狀態=cancelled、正式表無資料、staging 清理符合規範。

### L2-2 Batch Upload API（多檔 + 混批規則）
*   **實作內容**：
    *   `POST /api/import/jobs` 接受 `files: List[UploadFile]`。
    *   **混批規則（同一 job 必須一致）**：
        1) 同 `tenant_id`（由 tenant resolver 或 UI 選擇）
        2) 同 `format`（csv/xlsx/pdf 不混）
        3) 同 `header_fingerprint`（禁止 schema 混上傳）
    *   若違反任一條：整批 fail，回傳 `E_BATCH_MIXED_*`
*   **測試策略**：
    *   上傳 csv+xlsx 混合 → fail
    *   上傳兩個 header 不同的 csv → fail（E_HEADER_MISMATCH）

### L2-3 Deduplication（檔案級 + 資料級）
*   **實作內容**：
    *   [x] **檔案級去重**：
        * SHA-256 串流計算（避免大檔吃光記憶體）
        * DB unique：`unique(tenant_id, table_id, file_hash)` 為最終保護
        * 命中回 `E_FILE_DUPLICATE`
    *   [x] **資料級去重**：
        * 檔案內 unique key 重複 → `E_UNIQUE_IN_FILE`
        * DB 既有 unique key 重複 → `E_UNIQUE_IN_DB`
*   **測試策略**：
    *   同檔案重複 unique → errors API 可看到重複列
    *   DB 已有資料再匯入 → errors API 可看到重複列

### L2-4 Parser + Staging（可定位 row_index）
*   **實作內容**：
    *   CSV/Excel 解析器：
        * 保留 `row_index`（原檔列號）
        * 依 schema header mapping 產出 `parsed_json`
    *   寫入 `StagingRow(parsed_json)`（即便後續整批 fail 也保留，用於前端顯示錯誤列）
    *   計算 `header_fingerprint`（同 job 需一致）
*   **測試策略**：
    *   任一列欄位缺失/型別錯 → 可回報該 row_index + field + code

### L2-5 Validation Service（全量收斂錯誤）
*   **實作內容**：
    *   [x] 驗證層採「schema-driven」為主（Pydantic 可作基本型別輔助，但避免寫死只支援 P1/P2/P3）
    *   [x] 規則：
        * required/type/range（欄位級）
        * cross-field（同列邏輯）
        * cross-row（unique）
        * cross-table（由 tenant_table_settings 開關控制：P3 是否必須對應 P2/P1）
    *   [x] 將錯誤寫回 `StagingRow.errors_json`，並提供 `/errors` API 分頁讀取
*   **測試策略**：
    *   整批含多種錯誤 → errors API 能完整列出，不只第一個錯

### L2-6 Commit（整批交易 + DB 競態回填）
*   **實作內容**：
    *   [x] `commit_job_task`：
        * Transaction：staging → 正式表 bulk insert
        * 成功：job=COMPLETED
        * 失敗：rollback，job=FAILED
    *   **DB unique violation 競態處理**：
        * 若 commit 遇到 `IntegrityError`（unique）：
            - 將對應錯誤回填為 `E_UNIQUE_DB`
            - job=FAILED，正式表不得有任何新增
*   **測試策略**：
    *   競態測試（兩 job 同時寫入同 unique）→ 一個成功、一個失敗且 errors 可查

---

## Level 3: 進階功能 (Advanced Features)

### L3-1 PDF Conversion（外部轉檔為主）
*   **實作內容**：
    *   **[Skipped]** User requested to skip this feature.
    *   **Celery Task**: `convert_pdf_task`
    *   **主流程**：呼叫內網/外部轉檔服務（timeout=2min）
    *   **Retry**：每 5 分鐘重送，最多 5 次；超過標記 `CONVERSION_FAILED`
    *   **前端行為**：轉檔成功後提供「下載 CSV / 套用」；套用走 Level 2 同一套匯入流程
    *   （Optional Fallback）本地 pdfplumber/tabula 僅作 fallback，不列入主里程碑
*   **測試策略**：
    *   Mock 外部 API（成功/逾時/失敗）驗證 retry 次數與狀態更新
    *   轉檔成功後套用 → 必須能產生 job 並驗證/commit

### L3-2 Traceability Search（優先 Trace Index，fallback join）
*   **實作內容**：
    *   [x] **API**：
        * `POST /api/query/advanced`：多條件交集（lot/date_range/machine/mold/winder）
        * `GET /api/query/trace/{trace_key}`：展開回完整追溯鏈（P1+P2[]+P3[]，缺漏也回）
    *   **索引策略**：
        1) 若已建置 Trace Index（`trace_lots/trace_p2_index/trace_p3_index`）→ 查詢優先走索引表
        2) 若尚未建置 → fallback 使用 join（MVP），但需標註後續切換成本
*   **測試策略**：
    *   [x] 插入一組 P1->P2->P3 資料：多條件交集能正確回傳
    *   [x] 展開 trace：缺 P1 或缺 P2/P3 也能回（空陣列 + 缺漏標記）

### L3-3 Inline Edit & Audit（原因必填 + 全量驗證）
*   **實作內容**：
    *   [x] **API**：
        * `GET /api/edit-reasons`（per-tenant，允許 Other）
        * `PATCH /api/records/{table_code}/{id}`（原因必填）
    *   [x] **流程**：
        1) PATCH 提交前：載入 record（依 table_code）
        2) 執行同一套 Validation（required/type/range/cross-field/cross-table）
        3) 寫入 record
        4) 同 transaction 寫入 `row_edits(before_json, after_json, reason_id/other_text)`
*   **測試策略**：
    *   [x] 未帶 reason → 422
    *   [x] patch 後 row_edits 必有一筆且 before/after 正確

---

## 前端整合 (Frontend Integration)
**目標：配合後端 API 調整 UI，且完整對應「單 tenant 隱藏 / 多 tenant 選擇 / 匯入進度 / 錯誤列顯示 / 可取消 / PDF 轉檔下載&套用 / 追溯彈窗」。**

### FE-1 Tenant（單 tenant 隱藏；多 tenant 顯示）
* `TenantProvider`：App 啟動時 `GET /api/tenants`
* `TenantSelector`：若 tenants>1 顯示 Modal/Dropdown；若=1 隱藏
* Axios Interceptor：對除 `GET /api/tenants` 以外的請求自動注入 Header `X-Tenant-Id`

### FE-2 匯入/任務（Upload + Progress + Cancel + Errors）
* `UploadPage`：選 table_code + format（同批次限制）
* `UploadDropzone`（react-dropzone）：多檔上傳
* `JobList` / `JobCard`：顯示 status/progress/error_count
* `CancelJobButton`：呼叫 `POST /api/import/jobs/{id}/cancel`
* `JobErrorTable`：呼叫 `GET /api/import/jobs/{id}/errors`，只顯示錯誤列（可展開顯示 field/code/message）

### FE-3 PDF 轉檔（下載 / 套用）
* `PdfUploadToggle`：切換上傳 CSV vs PDF
* `PdfConversionStatus`：顯示轉檔狀態與 retry 次數
* `DownloadConvertedCsvButton` / `ApplyConvertedCsvButton`

### FE-4 查詢/追溯（卡片 + 展開彈窗）
* `AdvancedSearchForm`：lot/date_range/machine/mold/winder 任意組合
* `SearchResultCards`：回 trace_key
* `TraceModal`：呼叫 `GET /api/query/trace/{trace_key}` 展開顯示 P1/P2/P3（缺漏也顯示）

### FE-5 線上編輯（inline edit + reason）
* `RecordTable`（PrimeReact DataTable + virtual scroll）
* `InlineEditCell`
* `EditReasonDropdown`：`GET /api/edit-reasons`
* `PatchSubmitBar`：提交 PATCH 並顯示全量驗證錯誤

---

## 總體測試執行方式
1. **Unit Tests**：`pytest tests/unit`（快速、頻繁）
2. **Integration Tests**：`pytest tests/integration`（需 Test DB，Commit 前必跑）
3. **E2E Tests（建議）**：Playwright 模擬：
   - 單 tenant：不選 tenant → 上傳 → 顯示進度 → errors table → 修正流程
   - 多 tenant：必選 tenant → 上傳 → 取消 → 追溯查詢展開
