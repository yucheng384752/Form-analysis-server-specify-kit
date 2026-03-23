# LEGACY：存活路徑盤點（Inventory）

最後更新：2026-01-23

目的：
- 把仍存在的 legacy API/流程列成可 review 的清單
- 避免長期維持兩套行為分岔（尤其是 multi-tenant 風險）
- 明確列出替代方案與移除條件

## 定義

- **Legacy**：非 v2 方案的 import/query/read path，或資料表不具備完整 tenant-scoping 的歷史路徑。
- **v2**：以 `/api/v2/*`、`ImportJob`、tenant-scoped records/items 為核心的主路徑。

## Inventory（可移除清單）

| 類型 | 名稱/端點 | 目前用途 | 前端呼叫點 | 替代方案 | 建議狀態 | 移除條件 |
|---|---|---|---|---|---|---|
| Legacy Import | `POST /api/import` | 舊版 CSV 直接匯入（相容性保留） | （UI 已不再呼叫；仍需盤點 scripts/tools） | v2：`POST /api/v2/import/jobs/from-upload-job` → `POST /api/v2/import/jobs/{id}/commit` | **Deprecated（UI 已切換）** | 保留相容期限與移除日期；限制只在單 tenant / dev 環境允許；最後移除 endpoint |
| Legacy Query | `GET /api/query/*` | 舊版查詢（已移除） | （不應存在） | v2：`/api/v2/query/*` | **Removed** | 由測試保護，禁止重新掛載 |
| Legacy Traceability-by-lot | `GET /api/traceability/lot/{lot_no}` | 使用 legacy tables 查 lot 相關 |（目前前端不使用）| v2 query + product traceability（以 product_id 為主） | **Deprecated（建議移除）** | 決定是否保留；若保留需補 tenant 安全條款或移到 v2 表 |

備註：`GET /api/traceability/product/{product_id}` 不是 legacy endpoint，但內部包含「安全前提下」的 legacy fallback（僅在單一 tenant DB 允許）。

## 禁止擴散（工程落地）

- 後端路由保護：
  - 已有測試確保 OpenAPI 不再暴露 `/api/query/*`。
  - 檔案：`form-analysis-server/backend/tests/api/test_no_legacy_query_routes_present.py`

- 前端呼叫點保護（避免回歸）：
  - 新增 pytest 掃描前端 source，確保不會重新引入 `"/api/query"` 字串。
  - 檔案：`form-analysis-server/backend/tests/test_no_legacy_frontend_query_calls.py`

## 移除計畫（建議）

1) 先切 UI：UploadPage 的「匯入」改走 v2 ImportJob commit（v2-only write）。
2) 將 `/api/import` 加上 deprecation 訊號（log/audit/回應 header），並限制只在單 tenant 或特定環境允許。
3) 移除 `/api/import` 與其使用的 legacy tables（或封存為離線遷移工具）。

## 風險提示

- 多租戶環境下：任何非 tenant-scoped 的查詢/匯入都可能造成資料外洩。
- 因此 legacy fallback 需非常保守，且必須文件化其啟用條件。
