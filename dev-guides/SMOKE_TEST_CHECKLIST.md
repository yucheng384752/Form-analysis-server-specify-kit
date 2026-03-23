# Smoke Test Checklist（Docker 起來後可照做）

最後更新：2026-01-18

目的：用最小成本確認「服務有起來、多租戶 header 沒漏、v2 匯入/查詢/追溯/修正」主流程可用。

## 0) 前置條件（一次性）

- 已安裝：Docker Desktop、Node.js（npm）、Python（含 venv）
- 預期埠號：
  - Backend：`http://localhost:18002`
  - Frontend：`http://localhost:18003`
- 多租戶：所有 `/api/*` 呼叫建議都帶 `X-Tenant-Id`。
- 若 `AUTH_MODE=api_key`：所有 `/api/*` 也需要 `X-API-Key`（Tenant API key）。

## 1) 啟動（Docker）

用途：啟動後端/前端與 DB，確保基本可連線。

1. 啟動 docker compose

```powershell
cd form-analysis-server
# 如果你有專用的啟動方式也可以用 monitor_backend.bat / monitor_frontend.bat
# 這裡先用最常見方式示意

docker compose up -d
```

2. 打開 API 文件
- 輸入：瀏覽器開 `http://localhost:18002/docs`
- 預期：Swagger UI 正常顯示、可載入 OpenAPI

## 2) Frontend 測試（最快速回歸）

用途：確認前端基本邏輯（tenant/header guard、auth wrapper）沒壞。

```powershell
cd form-analysis-server/frontend
npm test -- --run
```

預期：
- `Test Files ... passed`（允許有 1 個 deprecated/skipped 測試）

## 3) Backend 測試（最小集合）

用途：確認多租戶安全、v2 query/traceability、import_v2 的主要 contract。

```powershell
cd form-analysis-server/backend
# 建議先跑 API 層的最小集合
python -m pytest -q tests/api
```

預期：
- 測試全部通過（或僅有你已知的非阻斷項目失敗）

> 若只想先驗證匯入/追溯最小集合，可先跑：
>
> ```powershell
> python -m pytest -q \
>   tests/api/test_import_v2.py \
>   tests/api/test_query_basic_and_advanced_strict.py \
>   tests/api/test_traceability_product_v2_record_includes_items.py
> ```

## 4) PowerShell Smoke（依使用者操作流程）

### 4.1 最小 API 流程（health + tenant + upload + v2 import commit）

用途：用一支腳本串起最小流程，驗證「tenant header + v2 匯入 commit」。

輸入：無（預設使用本機 `http://localhost:18002`）

```powershell
cd form-analysis-server
./test-api.ps1
```

預期：
- 能取得 tenant（若沒有 tenant，請先在 UI 登入頁輸入管理者金鑰解鎖管理者功能並建立 tenant）
- 上傳成功（回 `process_id`）
- v2 import job 建立成功（回 `job_id`），狀態能到 `READY` 並 commit

### 4.2 v2 匯入 commit（較完整：P3 範例）

用途：驗證 `POST /api/v2/import/jobs` → poll READY → commit → poll COMPLETED。

輸入：需要可用的 P3 CSV 測資（腳本會從多個候選路徑找檔案）。

```powershell
cd form-analysis-server
./test-import-v2-commit.ps1
```

預期：
- 顯示 `Job is READY!`
- commit 後狀態到 `COMPLETED`（或至少 commit 有回應；背景 commit 時可能需要再 poll）

### 4.3 v2 查詢 + 追溯（Traceability）

用途：驗證 `advanced search` + `trace detail`（最核心查詢流程）。

```powershell
cd form-analysis-server
./test-query-v2-trace.ps1
```

預期：
- advanced search 回傳 `trace_key`
- trace detail 回傳 `trace_key` 相符，並列出 P2/P3 數量

### 4.4 Inline Edit + Audit（若你要驗證修正流程）

用途：驗證 edit reasons init、修改 P1 extras、再查詢確認持久化。

```powershell
cd form-analysis-server
./test-edit-api.ps1
```

預期：
- init reasons 成功
- patch 後 `test_marker` 成功更新且二次查詢仍存在

### 4.5 Analytics（若有資料才有意義）

用途：驗證 analytics flatten/monthly 等端點基本可用與效能邊界。

```powershell
cd form-analysis-server
./test-analytics-api.ps1
```

預期：
- health OK
- monthly 查詢可回資料/空資料語義正確

## 5) 常見卡關（排除指南）

- 取得 tenant 失敗 / tenants 為空：
  - 到前端「登入」頁，輸入管理者金鑰驗證成功後解鎖「管理者」頁籤，建立第一個 tenant。
- 400/401（需要 API key）：
  - 若 `AUTH_MODE=api_key`，確認你有帶 `X-API-Key`，且是該 tenant 的 key。
- v2 import job 一直不是 READY：
  - 查 `GET /api/v2/import/jobs/{id}` 的 `status`/`error_summary`
  - 查 `GET /api/v2/import/jobs/{id}/errors` 看驗證錯誤

---

建議：把這份 checklist 當作「上線前 10 分鐘驗證」的固定流程；若有新增/變更端點，請同步更新本文件。
