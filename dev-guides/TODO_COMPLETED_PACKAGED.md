# TODO 已完成項目打包（以 Issue 為單位）

- 對應來源：`dev-guides/TODO_IN_20251229.md`
- 打包日期：2026-01-29
- 打包目標：把「已完成」的 TODO 以 issue 為單位整理，並附上問題描述／解決方法／修改檔案（含 commit 證據）。

> 註：部分 issue 在 TODO 完成紀錄中只有「做了什麼」但未列出完整檔案清單；本文件以「完成紀錄提到的 commit」為主來源，必要時補上目前工作樹（未回填到 TODO 的最新改動）作為補充。

---

## ISSUE: 後端 Import / Query（v2 與 Legacy 相容性）

### 1) ISSUE: 匯入 legacy P3 items 需同步到 v2 items

**問題描述**
- legacy import 流程只寫入 legacy 結構，導致 v2 查詢／統計缺少 P3 items 資料或行為不一致。

**解決方法**
- 新增/補強測試，明確驗證 legacy import 時，P3 items 能同步至 v2 結構。

**修改檔案（commit: `3d87af4`）**
- `form-analysis-server/backend/tests/api/test_import_legacy_sync_p3_items_v2.py`

---

### 2) ISSUE: v2 進階查詢（material）過濾邏輯回歸/不正確

**問題描述**
- 進階查詢的 material 過濾在某些條件下產生錯誤結果（例如只比對部分欄位、或未正規化導致比對失準）。

**解決方法**
- 修正 v2 query 的 material 過濾比對與正規化策略，並補上回歸測試。

**修改檔案（commit: `de3d21e`）**
- `form-analysis-server/backend/app/api/routes_query_v2.py`
- `form-analysis-server/backend/tests/api/test_query_advanced_material.py`

---

### 3) ISSUE: legacy query 入口與 v2 fallback / stats 行為一致化

**問題描述**
- legacy query/stats 端點在多租戶或特定條件下，需要能正確 fallback 到 v2；同時需明確測到「多租戶必須指定 tenant」等保護。

**解決方法**
- 補上多組 strict 測試，覆蓋：
  - legacy stats 會 fallback 到 v2
  - traceability v2 record 回傳包含 items
  - 多租戶情境下 v2 stats 需要 tenant

**修改檔案（commit: `80e2365`）**
- `form-analysis-server/backend/tests/api/test_legacy_query_stats_falls_back_to_v2.py`
- `form-analysis-server/backend/tests/api/test_traceability_product_v2_record_includes_items.py`
- `form-analysis-server/backend/tests/api/test_v2_query_stats_requires_tenant_in_multitenant.py`

---

### 4) ISSUE: Import route 調整（對應 2026-01-23 完成紀錄）

**問題描述**
- import 路由需配合新的匯入策略/行為調整（完成紀錄中以 commit 方式標記）。

**解決方法**
- 針對 import route 進行修正。

**修改檔案（commit: `231fc32`）**
- `form-analysis-server/backend/app/api/routes_import.py`

---

### 5) ISSUE: Query route 調整（對應 2026-01-23 完成紀錄）

**問題描述**
- query 路由需配合新的查詢策略/行為調整（完成紀錄中以 commit 方式標記）。

**解決方法**
- 針對 query route 進行修正。

**修改檔案（commit: `043a936`）**
- `form-analysis-server/backend/app/api/routes_query.py`

---

## ISSUE: Windows 本機腳本 / Quick Start 穩定性

### 6) ISSUE: local PowerShell 匯入/測試腳本資料路徑參數化（UT_DATA_DIR）

**問題描述**
- 本機測試/匯入腳本在不同環境下資料目錄不一致，使用者需要能用參數或環境變數指定資料路徑。

**解決方法**
- local ps1 腳本支援 `-DataDir`，並可用環境變數 `UT_DATA_DIR` 作為預設；若缺少則給出清楚錯誤。

**修改檔案（commit: `0987f81`）**
- `form-analysis-server/scripts/local-ps1/import-p1.ps1`
- `form-analysis-server/scripts/local-ps1/test-import-production-data.ps1`
- `form-analysis-server/scripts/local-ps1/test-import-v2-commit-3files.ps1`
- `form-analysis-server/scripts/local-ps1/test-prod-data.ps1`
- `form-analysis-server/scripts/local-ps1/test-prod-data2.ps1`
- `form-analysis-server/scripts/local-ps1/test-prod-final.ps1`

---

### 7) ISSUE: Quick Start / compose 啟動流程整體修正（Windows）

**問題描述**
- Windows 下 `quick-start.ps1`、其他啟動腳本與 `start-system.bat` 行為不一致：工作目錄錯誤、compose 指令/環境不一致、node_modules volume 覆蓋等，導致只有其中一個腳本能啟動成功。

**解決方法**
- 統一 compose 啟動方式、修正 working directory、修正 node_modules 初始化策略、補上相關說明文件。

**修改檔案（commit: `de3d21e`）**
- `form-analysis-server/docker-compose.yml`
- `form-analysis-server/quick-start.bat`
- `form-analysis-server/quick-start.ps1`
- `form-analysis-server/quick-start.sh`
- `form-analysis-server/scripts/bootstrap-api-key.ps1`
- `form-analysis-server/backend/start_server.bat`
- `getting-started/QUICK_START.md`

（同 commit 也同步更新 README/.env.example 等，詳見下方「共用文件變更」與 commit 清單）

---

### 8) ISSUE: 監控腳本（monitor_backend.bat / monitor_frontend.bat）生成/清除

**問題描述**
- Windows 啟動後需要一鍵追 log 的監控腳本；停止系統時需清理。

**解決方法**
- `start-system.bat` 會生成監控腳本並啟動；`stop-system.bat` 清理生成檔。

**修改檔案（commit: `de3d21e` + 目前 repo 既有腳本）**
- `monitor_backend.bat`
- `monitor_frontend.bat`
- `scripts/start-system.bat`
- `scripts/stop-system.bat`
- `scripts/start-backend.bat`
- `scripts/start-frontend.bat`

---

## ISSUE: Auth / Tenant / Audit / Registration

### 9) ISSUE: 嚴格化登入／API key／審計（audit）與多租戶保護

**問題描述**
- 需要更嚴格的 API key/tenant 作用域與稽核事件（audit event）記錄，避免跨租戶誤用，並讓行為可測。

**解決方法**
- 引入/擴充 audit event、tenant scoped 行為、並以 strict 測試鎖定行為。

**修改檔案（commit: `de3d21e`）**
- `form-analysis-server/backend/app/core/auth.py`
- `form-analysis-server/backend/app/core/middleware.py`
- `form-analysis-server/backend/app/models/core/audit_event.py`
- `form-analysis-server/backend/app/schemas/audit.py`
- `form-analysis-server/backend/tests/api/test_audit_events_enabled_strict.py`
- `form-analysis-server/backend/tests/api/test_auth_api_key_strict.py`
- `form-analysis-server/backend/tests/api/test_tenants_api_strict.py`
- `form-analysis-server/frontend/src/services/adminAuth.ts`
- `form-analysis-server/frontend/src/services/auth.ts`

---

### 10) ISSUE: Registration / Tenant user 與 API key 綁定（含 migration）

**問題描述**
- 需要讓使用者登入能取得可追溯到 `TenantUser` 的 API key（例如 `TenantApiKey.user_id`），並支援後續角色/權限判斷與稽核。

**解決方法**
- 增加 tenant_users / tenant_api_keys 的 schema 與 migration；更新 auth routes；補上後端 strict 測試與前端註冊流程測試。

**修改檔案（commit: `04d06d1`）**
- `form-analysis-server/backend/alembic/versions/2026_01_17_0001-tenant_api_keys_v1.py`
- `form-analysis-server/backend/alembic/versions/2026_01_17_0002-merge_traceability_heads_v1.py`
- `form-analysis-server/backend/alembic/versions/2026_01_17_0003-tenant_users_v1.py`
- `form-analysis-server/backend/alembic/versions/2026_01_17_0004-tenant_api_keys_add_user_id_v1.py`
- `form-analysis-server/backend/app/api/routes_auth.py`
- `form-analysis-server/backend/app/core/config.py`
- `form-analysis-server/backend/app/core/password.py`
- `form-analysis-server/backend/app/main.py`
- `form-analysis-server/backend/app/models/core/tenant_api_key.py`
- `form-analysis-server/backend/app/models/core/tenant_user.py`
- `form-analysis-server/backend/tests/api/test_auth_login_strict.py`
- `form-analysis-server/backend/tests/conftest.py`
- `form-analysis-server/frontend/src/pages/RegisterPage.test.tsx`
- `form-analysis-server/frontend/src/pages/RegisterPage.tsx`
- `form-analysis-server/frontend/src/services/fetchWrapper.ts`
- `form-analysis-server/frontend/src/styles/register-page.css`
- `getting-started/REGISTRATION_FLOW.md`

---

### 11) ISSUE: 「必須改密碼」與「管理者/主管重設密碼」流程（含 UI/測試）

**問題描述**
- 需要兩條密碼流程：
  1) 使用者自助改密碼
  2) admin/manager 可重設他人密碼，並強制對方下次登入必須改密碼（must_change_password）
- 同時需要稽核事件（不記敏感資訊）。

**解決方法**
- 引入 `must_change_password` 欄位與中介層強制規則；新增/調整 auth endpoints；前端加上提醒/自助改密碼 UI；補測試。

**修改檔案（對應近期完成；部分已在 `04d06d1` / 後續未回填 TODO 的改動）**
- `form-analysis-server/backend/app/api/routes_auth.py`
- `form-analysis-server/backend/app/core/config.py`
- `form-analysis-server/backend/app/core/password.py`
- `form-analysis-server/backend/app/main.py`
- `form-analysis-server/backend/app/models/core/tenant_user.py`
- `form-analysis-server/backend/alembic/versions/2026_01_29_0001-tenant_users_add_must_change_password_v1.py`

---

## ISSUE: 前端 A11Y（字體大小切換）

### 12) ISSUE: 字體縮放（font-scale）可切換且持久化（MVP）

**問題描述**
- 使用者需要在 UI 內切換字體大小（可讀性/可及性），並且刷新後仍保留設定。

**解決方法**
- 以前端 CSS 變數 `--font-scale` 實作；使用 localStorage 記錄；App UI 提供選單。

**修改檔案（依現況掃描）**
- `form-analysis-server/frontend/src/services/a11y.ts`
- `form-analysis-server/frontend/src/App.tsx`
- `form-analysis-server/frontend/src/main.tsx`
- `form-analysis-server/frontend/src/index.css`
- `form-analysis-server/frontend/src/styles/app.css`
- `form-analysis-server/frontend/src/locales/zh-TW/common.json`
- `form-analysis-server/frontend/src/locales/en/common.json`

---

## 共用文件 / 追蹤文件變更

### 13) ISSUE: TODO 與文件更新（完成紀錄、ignore）

**問題描述**
- 完成事項需要在 TODO 與文件中留下可追溯紀錄。

**解決方法**
- 更新 TODO 與 .gitignore。

**修改檔案**
- （commit: `06fc6e8`）
  - `.gitignore`
  - `dev-guides/TODO_IN_20251229.md`
- （commit: `cb3861b`）
  - `dev-guides/TODO_IN_20251229.md`

---

## 補充：啟動時自動建立 manager（Startup Bootstrap）

> 這一段是依你後續新需求完成，但「不一定已回寫到 TODO 完成紀錄」；因此在此作補充整理。

**問題描述**
- 需要在系統啟動時（lifespan/bootstrap）可選擇性自動建立一個 `manager` 使用者，並能用 admin key 查詢狀態以便驗證。

**解決方法**
- 新增 startup bootstrap：讀 env 設定，best-effort 建立 manager user（含 password/must_change 的安全條件）。
- 新增 admin-only 的狀態檢查 endpoint。
- 新增 pytest 覆蓋 bootstrap 行為。

**修改檔案（依目前工作樹）**
- `form-analysis-server/backend/app/core/bootstrap.py`（新增）
- `form-analysis-server/backend/app/core/config.py`（新增 BOOTSTRAP_MANAGER_* 設定）
- `form-analysis-server/backend/app/main.py`（lifespan 呼叫 bootstrap + admin-only 白名單）
- `form-analysis-server/backend/app/api/routes_auth.py`（新增 `/api/auth/bootstrap/manager-status` 等）
- `form-analysis-server/backend/tests/api/test_bootstrap_manager_seed.py`（新增）
- `form-analysis-server/.env.example`（補 env 說明）

---

## 附錄：如何用 commit 查完整檔案清單

- `git show --name-only --pretty=format: <commit>`
  - 例：`git show --name-only --pretty=format: de3d21e`
