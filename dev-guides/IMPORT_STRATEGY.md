# IMPORT：匯入策略（收斂版）

最後更新：2026-01-18

## 結論（先求穩）

- **主流程一律以 v2 為準**：匯入請使用 `POST /api/v2/import/jobs` → 等待 `READY` → `POST /api/v2/import/jobs/{id}/commit`。
- `/api/upload`、`/api/errors.csv`、`/api/import` 視為**舊流程/相容性保留**：
  - **單租戶**：可用於最低限度相容性（舊腳本/舊流程）。
  - **多租戶**：直接拒絕（避免資料只落在 legacy tables，造成查詢/追溯不一致）。

### 多租戶下拒絕 legacy（已採用）

- 以 env `MULTI_TENANT_ENABLED=true` 啟用多租戶模式。
- 啟用後，以下 legacy 端點會回 `410 Gone`：
  - `POST /api/upload`
  - `GET /api/errors.csv`
  - `POST /api/import`

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

## 重複資料策略（你已確認）

- **同檔案、同內容**（相同 SHA-256）：v2 會回 400，提示「內容重複」並附上既有的 `job_id/batch_id`，避免誤匯入。
- **不同檔案但大部分內容相同**：採用「business-key 合併 + row-level 去重」，避免同一批次多檔案造成重複 rows，同時能容忍少量欄位差異（以保守策略合併）。

### row-level dedupe / business-key 合併（具體實作內容）

目前採用「business-key 合併（保守）+ 精確去重（輕量正規化）」的方案（不做昂貴的模糊比對）：

1) **row signature（精確去重）定義**
- 對每一列 `Dict[str, Any]`：
  - key 做 `strip()`
  - value 轉字串並 `strip()`（`None` 保留）
  - 用 JSON canonicalization（`sort_keys=True`）生成穩定字串，作為 signature。

2) **business-key 合併（大部分相同內容）**
- 針對「同一個 business key」底下的多列資料：
  - 先挑「欄位最完整」的 row 當 base
  - 其他 row 只用來補 base 裡空值/缺欄位
  - 若遇到同欄位兩邊都有值但不同：保留 base、不覆蓋（只記錄衝突數量到 log）

3) **範圍（目前只在同一個 v2 job 內）**
- 先以「同一個 v2 job 內」為範圍：
  - P1：以 `(tenant_id, lot_no_norm)`（同一 lot）合併多檔案 rows → 去重 → 合併成 1 row。
  - P2：以 `(tenant_id, lot_no_norm, winder_number)`（同一 lot + 同一 winder）合併多檔案 rows → 去重 → 合併成 1 row。
- 不跨 job 做全域 dedupe（避免自動吞掉修正後資料；若要跨 job，需要額外的 business key 設計與稽核流程）。

4) **可預期行為**
- 多檔案 split/重覆匯入：合併後不重複計算；欄位互補時會被補齊。
- 若使用者想「覆蓋」而不是「合併」：建議上層 UI/流程用「新建 job + 單一檔案」來明確覆蓋。

## 最小一致性測試（已補齊）

- `form-analysis-server/backend/tests/integration/test_import_write_strategy_min_consistency.py`
  - 驗證：v2-only 匯入後，`/api/v2/query/records` 能查到 P1/P2/P3，且 `/api/traceability/product/{product_id}` 可用。

## commit（交易性）建議（你已確認）

- **commit 需全成全敗（atomic）**：commit 過程任何錯誤都不應留下部分寫入。
- 失敗後：**新建 job** 重新匯入（不提供原 job retry commit）。

## 腳本與文件

- `form-analysis-server/quick-start.ps1` 已改為以 v2 import jobs 做 smoke 匯入測試。
- `form-analysis-server/test-api.ps1` 的匯入段落已改為 v2 import jobs。

## 後續（若要更硬）

若你希望徹底避免誤用 legacy：
- 在 `/api/import` 回應加上 deprecation 提示（或在多租戶模式直接關閉舊端點）。
- 補齊「legacy → v2 全類型雙寫」或提供官方回填腳本，確保 v2 查詢來源永遠完整。
