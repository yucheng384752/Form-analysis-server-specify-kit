# LEGACY API 盤點（非 /api/v2）

> 注意：本文件是「盤點/移除規劃」用途，不是 API 教學。
> 新匯入主流程請一律以 v2 import jobs（`/api/v2/import/jobs`）為準；multi-tenant 下 legacy import 端點會回 410。
> 參考：`dev-guides/IMPORT_STRATEGY.md`、`dev-guides/LEGACY_DEPRECATION_PLAN.md`。

目標：
- 列出目前仍「存活」的非 `/api/v2/*` 端點（含 router/檔案位置/用途/前端呼叫點）。
- 產出 migration / 移除清單，避免長期維持兩套行為分岔。
- 加上最小保護測試，避免 legacy query 類端點回歸、避免前端硬編碼 backend base URL。

## 定義

- **V2**：`/api/v2/*`。
- **Non‑V2（現役）**：不是 `/api/v2/*`，但仍被前端/管理功能依賴（例如 `/api/auth`, `/api/tenants`）。
- **Legacy（待收斂）**：歷史 v1 風格，長期應移轉或封存到 `/api/v2/*`，或改成純內部用途。

> 註：此文件以 [form-analysis-server/backend/app/main.py](../form-analysis-server/backend/app/main.py) 的 `include_router()` 為準。

---

## Backend Router / 端點清單

### A) Non‑V2（現役，短期不建議移除）

1) **Auth**
- Router：`routes_auth`
- 掛載：`/api/auth/*`
- 檔案：`form-analysis-server/backend/app/api/routes_auth.py`
- 前端呼叫：`frontend/src/pages/AdminPage.tsx`, `frontend/src/services/fetchWrapper.ts`
- 備註：這是多租戶 / API Key bootstrap 管理核心。

2) **Tenants**
- Router：`routes_tenants`
- 端點：`/api/tenants`, `/api/tenants/admin`, `/api/tenants/{tenant_id}`...
- 檔案：`form-analysis-server/backend/app/api/routes_tenants.py`
- 前端呼叫：`frontend/src/services/tenant.ts`, `frontend/src/pages/AdminPage.tsx`, `frontend/src/pages/AnalyticsPage.tsx`

3) **Logs**
- Router：`routes_logs`
- 掛載：`/api/logs/*`
- 檔案：`form-analysis-server/backend/app/api/routes_logs.py`
- 前端呼叫：`frontend/src/services/logService.ts`
- Migration 建議：長期可移至 `/api/v2/logs/*`（不急）。

4) **Constants**
- Router：`routes_constants`（router prefix 內建 `/api/constants`）
- 掛載：`/api/constants/*`
- 檔案：`form-analysis-server/backend/app/api/constants.py`
- 前端呼叫：待補（目前未看到明確直接呼叫點；可能由 UI 表單選項使用）
- Migration 建議：長期可移至 `/api/v2/constants/*`（不急）。

5) **Traceability**
- Router：`routes_traceability`（router prefix 內建 `/api/traceability`）
- 掛載：`/api/traceability/*`
- 檔案：`form-analysis-server/backend/app/api/traceability.py`
- 前端呼叫：`frontend/src/pages/QueryPage.tsx`
- Migration 建議：長期可移至 `/api/v2/traceability/*`（不急，先確保行為穩定）。

6) **Inline Edit**
- Router：`routes_edit`
- 掛載：`/api/edit/*`
- 檔案：`form-analysis-server/backend/app/api/routes_edit.py`
- 前端呼叫：`frontend/src/components/EditRecordModal.tsx`
- Migration 建議：長期可移至 `/api/v2/edit/*`（不急）。

7) **Audit Events**
- Router：`routes_audit_events`
- 端點：`/api/audit-events`, `/api/admin/audit-events`
- 檔案：`form-analysis-server/backend/app/api/routes_audit_events.py`
- 前端呼叫：待補（目前未看到直接 UI 呼叫點，可能僅做觀測/管理）

---

### B) Legacy（待收斂 / 建議規劃移除）

1) **Upload v1**
- Router：`routes_upload`
- 掛載：`/api/upload*`（因 main.py prefix=`/api`，router path 以 `/upload...` 開頭）
- 檔案：`form-analysis-server/backend/app/api/routes_upload.py`
- 主要端點（摘要）：
  - `POST /api/upload`（CSV/Excel 上傳+驗證）
  - `POST /api/upload/pdf`（PDF 上傳）
  - `POST /api/upload/pdf/{process_id}/convert`（觸發 PDF→CSV）
  - `POST /api/upload/pdf/{process_id}/convert/ingest`（轉檔結果 ingest 成 UploadJob）
  - `PUT /api/upload/{process_id}/content`（前端修正後回寫+重驗）
  - `POST /api/upload/{process_id}/validate`（重驗）
- 前端呼叫：
  - UploadPage 的 PDF 流程仍使用 `/api/upload/pdf*`；CSV 匯入主流程已改走 v2 import jobs
- Migration 建議：
  - **中期**：把「上傳→驗證→入庫」主流程統一成 `/api/v2/import/*` 的 job 模型；Upload v1 僅保留為「上傳暫存/轉檔」或逐步併入 v2。

2) **Validate v1**
- Router：`routes_validate`
- 端點：`GET /api/validate`
- 檔案：`form-analysis-server/backend/app/api/routes_validate.py`
- 前端呼叫：待補（可能已被新版流程取代，需再確認）
- Migration 建議：
  - 若 v2 import job 能完整取代「驗證錯誤查詢」，則此端點可規劃 deprecated。

3) **Import v1（最重要的 legacy 風險點）**
- Router：`routes_import`
- 端點：`POST /api/import`
- 檔案：`form-analysis-server/backend/app/api/routes_import.py`
- 說明：典型 v1「一鍵匯入」，可能有 legacy 寫入策略（同時維護 records/p3_items 與 v2 正規化表的同步）。
- 前端呼叫：目前主線 UI 看起來不依賴；但仍應視為高風險 legacy surface。
- Migration 建議：
  - **優先**：把所有 UI 流程改走 `/api/v2/import/jobs + commit`；
  - `/api/import` 轉為 internal-only（或加上明確 deprecated warning），最後移除。

4) **Export v1**
- Router：`routes_export`
- 端點：`GET /api/errors.csv`
- 檔案：`form-analysis-server/backend/app/api/routes_export.py`
- 前端呼叫：待補（若前端有「下載錯誤 CSV」功能）
- Migration 建議：
  - 若 v2 import job 有 `/errors`，可改成 v2 下載端點後移除。

---

## Frontend 呼叫點（摘要）

- Upload：CSV 主流程走 `/api/v2/import/jobs*`；PDF 流程走 `/api/upload/pdf*`
- Edit：`frontend/src/components/EditRecordModal.tsx` → `/api/edit/*`
- Logs：`frontend/src/services/logService.ts` → `/api/logs/*`
- Tenants/Auth：`frontend/src/services/tenant.ts`, `frontend/src/pages/AdminPage.tsx`
- Query/Traceability：`frontend/src/pages/QueryPage.tsx` → `/api/v2/query/*` + `/api/traceability/*`

---

## Dead / Backup 候選（建議封存或刪除）

- `form-analysis-server/backend/app/api/routes_query_backup.py`：目前未掛載於 app，但檔案內容疑似損壞/重複，建議移除或移到 `dev-docs/` 當作歷史備份。
- `form-analysis-server/frontend/src/pages/QueryPage_backup.tsx`：疑似備份檔；建議封存或移除，避免後續誤用。
- `form-analysis-server/frontend/src/components/FileUpload.tsx`：目前未被引用；已改為停用 placeholder（避免誤用 legacy 流程）；仍可考慮封存或刪除。

---

## Migration / 移除清單（建議節奏）

### Phase 0（立即，防止回歸）
- 禁止前端硬編碼 backend base URL（例如 `http://localhost:8000/api/...`）。
- 測試保護：確保 `/api/query*` 這類 legacy query 端點不會被重新掛回來。

### Phase 1（主線收斂）
- UI 主流程全面改走 `/api/v2/import/*`（包含建立 job、錯誤查詢、commit/cancel）。
- `/api/import` 轉成 deprecated（或 internal-only），並列出哪些外部/內部腳本仍依賴它。

### Phase 2（版本化一致性）
- 視需求把 constants / logs / traceability / edit 規劃成 `/api/v2/*`。
- 移除或封存所有 backup/legacy router 檔案，降低維護成本。
