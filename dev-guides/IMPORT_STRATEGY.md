# IMPORT：匯入策略（收斂版）

最後更新：2026-01-18

## 結論（先求穩）

- **主流程一律以 v2 為準**：匯入請使用 `POST /api/v2/import/jobs` → 等待 `READY` → `POST /api/v2/import/jobs/{id}/commit`。
- `/api/upload`、`/api/errors.csv`、`/api/import` 視為**舊流程/相容性保留**，不建議在新環境或多租戶情境作為主要匯入路徑。

這樣做的目的：避免資料只落在 legacy tables，導致「匯入成功但 v2 查不到 / 追溯不到」的操作阻斷。

## 為什麼要收斂

系統同時存在兩條匯入路徑：

1) **Legacy 匯入**
- 上傳：`POST /api/upload`
- 錯誤報告：`GET /api/errors.csv?process_id=...`
- 確認匯入：`POST /api/import`

2) **V2 匯入（建議）**
- 建立任務並上傳檔案：`POST /api/v2/import/jobs`（multipart/form-data）
- 查狀態：`GET /api/v2/import/jobs/{id}`
- 查錯誤：`GET /api/v2/import/jobs/{id}/errors`
- 提交：`POST /api/v2/import/jobs/{id}/commit`

前端 UploadPage 已經以 v2 import jobs 為主；若腳本/文件仍使用 legacy，就會出現「同一份資料在不同查詢路徑看起來不一致」的風險。

## v2 匯入 API（最小可用範例）

- 必帶：`X-Tenant-Id: <TENANT_ID>`
- 若 `AUTH_MODE=api_key`：還要帶 `X-API-Key: <YOUR_API_KEY>`

```bash
# 1) 建立匯入 job（以 P1 為例）
curl -X POST \
  -H "X-Tenant-Id: <TENANT_ID>" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -F "table_code=P1" \
  -F "allow_duplicate=false" \
  -F "files=@P1_2503033_01.csv" \
  http://localhost:18002/api/v2/import/jobs

# 2) poll 狀態直到 READY / FAILED
curl -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  http://localhost:18002/api/v2/import/jobs/<JOB_ID>

# 3) commit
curl -X POST -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  http://localhost:18002/api/v2/import/jobs/<JOB_ID>/commit
```

## 資料落點（責任邊界）

- **v2 匯入（commit）**：寫入 v2 正規化資料表（以及對應的主表/明細表）。
- **legacy 匯入**：主要寫入 legacy tables；為了 v2 查詢/追溯一致性，部分資料會做同步（例如 P3 已有 `p3_records` / `p3_items_v2` 的同步邏輯）。

### 建議的責任邊界

- 新資料匯入：一律走 v2。
- 舊資料或歷史資料：若仍在 legacy tables，需要**一次性回填/migration**到 v2 tables（用 migrations 或專用回填腳本），不要依賴查詢時的 fallback。

## 腳本與文件

- `form-analysis-server/quick-start.ps1` 已改為以 v2 import jobs 做 smoke 匯入測試。
- `form-analysis-server/test-api.ps1` 的匯入段落已改為 v2 import jobs。

## 後續（若要更硬）

若你希望徹底避免誤用 legacy：
- 在 `/api/import` 回應加上 deprecation 提示（或在多租戶模式直接關閉舊端點）。
- 補齊「legacy → v2 全類型雙寫」或提供官方回填腳本，確保 v2 查詢來源永遠完整。
