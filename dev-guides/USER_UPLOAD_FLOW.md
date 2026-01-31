# 使用者上傳流程（Upload / Validate / Import）

> 注意：本文件以 **v2 import jobs** 為主流程（UploadPage 的 CSV 主流程已於 **2026-01-31** 切換）。
> - legacy import endpoints（例如 `/api/upload`、`/api/import`）屬 **Deprecated / 最低相容性**，僅保留在附錄供理解歷史現況。
> - **multi-tenant 模式會直接拒絕 legacy（410）**，避免 split-brain。
> - 推薦流程：`/api/v2/import/jobs` → poll → `/commit`。
>
> 參考：
> - dev-guides/LEGACY_DEPRECATION_PLAN.md
> - dev-guides/IMPORT_STRATEGY.md

本文件描述「使用者在前端上傳 CSV → 驗證 → 修正 → 匯入」的端到端流程，並補充系統內兩套狀態機：

- **V2 上傳/驗證/匯入（現況主流程；UploadPage 使用）**：`/api/v2/import/jobs`、`/api/v2/import/jobs/{id}/errors`、`/api/v2/import/jobs/{id}/commit`
- **Legacy 上傳/匯入（附錄/歷史流程）**：`/api/upload`、`/api/upload/{process_id}/content`、`/api/import`

> 文件目的：讓前後端在「狀態機變化」「UI 提示」「驗證與重試策略」有一致語言。

---

## 0) V2 推薦流程（最小示例）

> 這是「新的主流程」：`POST /api/v2/import/jobs` → poll `READY/FAILED` → `POST /commit` 或 `GET /errors`。

```bash
# 建立匯入 job（以 P1 為例）
curl -X POST "http://localhost:18002/api/v2/import/jobs" \
  -H "X-Tenant-Id: <TENANT_ID>" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -F "table_code=P1" \
  -F "allow_duplicate=false" \
  -F "files=@P1_2503033_01.csv;type=text/csv"

# poll 狀態直到 READY / FAILED
curl -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  "http://localhost:18002/api/v2/import/jobs/<JOB_ID>"

# READY 後提交 commit
curl -X POST -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  "http://localhost:18002/api/v2/import/jobs/<JOB_ID>/commit"
```

---

## 1) 使用者視角流程（現況：UploadPage CSV → v2 import jobs）

> 本章節描述目前 UploadPage（CSV）行為；PDF 流程仍走 `/api/upload/pdf*`。

1. 使用者在「上傳頁」選擇 CSV 檔案（可多檔）
2. 使用者按「驗證」：前端 `POST /api/v2/import/jobs`（multipart：`table_code` + `files[]`）
3. 後端背景 parse + validate；前端輪詢 `GET /api/v2/import/jobs/{id}` 直到 `READY` / `FAILED`
4. 若有錯誤：前端 `GET /api/v2/import/jobs/{id}/errors` 取得錯誤列並顯示
5. 使用者在表格修正後按「重新驗證」：前端會以**目前畫面 CSV 內容**重新建立檔案並重走步驟 2（建立新 job）
6. 驗證通過（READY 且錯誤數 0）後使用者按「匯入」或「批次匯入」：前端 `POST /api/v2/import/jobs/{id}/commit`

> 註：v2 的 commit 為主寫入路徑（v2-only write）。legacy `/api/import` 僅相容保留。

---

## 附錄 A) 使用者視角流程（歷史：舊版 UploadPage legacy）

> ⚠️ 注意：本章節是「歷史 legacy 流程」，不作為新開發/新腳本的教學範例。

### 1.1 流程概覽

1. 使用者在「上傳頁」選擇 CSV 檔案（可多檔）
2. 前端做基本檢查：副檔名、大小、重複檔名
3. 使用者按「驗證」：前端 `POST /api/upload`（multipart）
4. 後端完成驗證後回傳：`process_id` + 行數統計 + `sample_errors`
5. 前端顯示：驗證結果 toast、錯誤摘要、展開可編輯表格
6. 若有錯誤：使用者在表格修正後按「儲存修改」→ `PUT /api/upload/{process_id}/content`（後端會重新驗證）
7. 驗證通過後使用者按「匯入」或「批次匯入」→ `POST /api/import`

### 1.2 前端 UI 狀態機（UploadPage 的檔案狀態）

前端在每個檔案上維護狀態（`UploadedFile.status`）：

- `uploaded`：已加入列表（本地）
- `validating`：驗證中（進度條 10%→100%）
- `validated`：驗證完成（可看到 `sample_errors`、可編輯 CSV）
- `importing`：匯入中（進度條 10%→100%）
- `imported`：匯入完成（稍後會從列表移除）

### 1.3 後端狀態機（Legacy：upload_jobs.job_status_enum）

Legacy 上傳工作（`upload_jobs`）狀態（`JobStatus`）：

- `PENDING`：剛建立或驗證失敗（尚未能匯入）
- `VALIDATED`：驗證完成（可匯入）
- `IMPORTED`：已匯入（不可重複匯入同一工作）

狀態轉移（概念圖）：

```mermaid
stateDiagram-v2
  [*] --> PENDING: POST /api/upload 建立工作
  PENDING --> VALIDATED: 驗證成功
  PENDING --> PENDING: 驗證失敗(422)
  VALIDATED --> VALIDATED: PUT /api/upload/{id}/content 重新驗證
  VALIDATED --> IMPORTED: POST /api/import 匯入成功
```

---

## 附錄 B) 後端 API 與資料流（Legacy UI 對應）

### 2.1 檔案上傳與驗證：`POST /api/upload`

- Request：`multipart/form-data`，欄位 `file`
- 後端行為（摘要）：
  - 建立 `upload_jobs`（狀態 `PENDING`）並保存 `file_content`
  - 執行檔案驗證（含 lot_no 格式、尾端空白列忽略等）
  - 成功：更新工作狀態為 `VALIDATED`、寫入 `upload_errors`、回傳統計與 `sample_errors`
  - 失敗：回 422，工作維持/回到 `PENDING`

前端對應的 UI 提示（節選）：
- 不支援檔案類型：`僅支援 csv 檔案類型`
- 檔案太大：`檔案大小超過 10MB 限制`
- 驗證成功：`${檔名} 驗證完成：共 N 行全部有效`
- 驗證含錯誤：
  - info：`${檔名} 驗證完成：共 N 行，有效 A 行，無效 B 行`
  - error：列出前 3 筆錯誤摘要 + 引導「展開檔案查看完整錯誤列表並修正後按『儲存修改』（會重新驗證）」

### 2.2 使用者修正後重驗證：`PUT /api/upload/{process_id}/content`

- 目的：讓前端表格修改「真的生效」，避免重新上傳原始檔覆蓋使用者修改
- Request：JSON `{ "csv_text": "..." }`
- 後端行為（摘要）：
  - 寫回 `upload_jobs.file_content`
  - 清除舊 `upload_errors`
  - 重新跑驗證
  - 回傳最新統計與 `sample_errors`

前端對應的 UI 提示：
- 未驗證就儲存：`缺少 process_id，請先驗證檔案後再儲存修改`
- 儲存後仍有錯誤：`修改已儲存，但仍有 X 行無效，請繼續修正`
- 儲存且通過：`修改已儲存，且驗證通過`

### 2.3 匯入：`POST /api/import`

- Request：JSON `{ "process_id": "..." }`
- 前置條件：對應的 `upload_jobs.status` 必須是 `VALIDATED`
- 後端行為（摘要）：
  - 重新讀取 `upload_jobs.file_content`
  - 解析 CSV → 寫入 `records`（與相關明細表，例如 P3 items）
  - 更新 `upload_jobs.status = IMPORTED`

前端「批次匯入」行為（摘要）：
- 多檔時：會**跳過**仍有驗證錯誤的檔案，只匯入「已驗證且 `sample_errors` 為空」的檔案
- 若有檔案未驗證/仍有錯誤：會用 toast 阻止匯入並提示原因

---

## 2) V2 批次匯入狀態機（ImportJobStatus，供 scripts / UI 使用）

V2 匯入工作（`import_jobs`）狀態（`ImportJobStatus`）：

- `UPLOADED`：建立 Job、檔案已上傳到暫存資料夾
- `PARSING`：背景解析 CSV，寫入 `staging_rows`
- `VALIDATING`：背景驗證 staging rows
- `READY`：驗證完成，可提交 commit
- `COMMITTING`：提交中（寫入正式表，例如 records + P2/P3 items）
- `COMPLETED`：提交成功
- `FAILED`：背景流程或提交失敗
- `CANCELLED`：取消（若有實作）

狀態轉移（概念圖）：

```mermaid
stateDiagram-v2
  [*] --> UPLOADED: POST /api/v2/import/jobs
  UPLOADED --> PARSING: background parse_job
  PARSING --> VALIDATING: parse 完成
  VALIDATING --> READY: validate 完成
  READY --> COMMITTING: POST /api/v2/import/jobs/{id}/commit
  COMMITTING --> COMPLETED: commit 完成
  UPLOADED --> FAILED
  PARSING --> FAILED
  VALIDATING --> FAILED
  READY --> FAILED
  COMMITTING --> FAILED
```

> 註：V2 在背景任務發生例外時會把 job 標記為 `FAILED`（避免 UI/監控顯示卡住）。

---

## 3) 驗證過程（建議驗證清單）

### 3.1 UI 驗證（建議操作）

1. 進入 Upload 頁，選擇 1~3 個 CSV
2. 應看到 toast：`已加入 N 個檔案`
3. 點「驗證」
   - 成功：看到 success/info toast + 可展開表格
   - 失敗：看到 error toast（例如 lot_no 格式錯誤）
4. 若有錯誤：在表格修正後點「儲存修改」
   - 仍有錯誤：toast 會提示仍有 `invalid_rows`
   - 通過：toast 顯示 `修改已儲存，且驗證通過`
5. 點「匯入」或「批次匯入」
   - 成功：toast 顯示匯入筆數，已匯入檔案會從列表移除

### 3.2 API 驗證（不用開 UI）

- 建立 job：`POST /api/v2/import/jobs`（multipart）
- 查狀態：`GET /api/v2/import/jobs/{id}`
- 查錯誤：`GET /api/v2/import/jobs/{id}/errors`
- commit：`POST /api/v2/import/jobs/{id}/commit`

若要回歸測試，可參考 form-analysis-server 內的 PowerShell 測試腳本（例如 `test-api.ps1` 系列）。
