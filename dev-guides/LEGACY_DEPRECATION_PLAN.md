# Legacy API Deprecation Plan（P1/LEGACY）

本文件目標：把 legacy import 流程（`/api/upload`、`/api/import`、`/api/errors.csv` 等）從「可用但容易被誤用」收斂到「明確 deprecated、只有最低相容性」，並逐步移除，避免 split-brain。

> 既定原則（已落實）：
> - **v2 為唯一正規資料來源**（import jobs → commit → v2 tables）。
> - **multi-tenant 直接拒絕 legacy**（HTTP 410），避免跨租戶/資料一致性問題。

## 1) 範圍（本次要淘汰/降級的 legacy endpoints）

| 類別 | Endpoint | 狀態 | v2/替代方案 |
|---|---|---|---|
| Legacy Upload+Validate | `POST /api/upload` | Deprecated | `POST /api/v2/import/jobs`（multipart：`table_code`, `files[]`） |
| Legacy Validate Query | `GET /api/validate?process_id=...` | Deprecated | `GET /api/v2/import/jobs/{id}`（status/統計） |
| Legacy Errors Export | `GET /api/errors.csv?process_id=...` | Deprecated | `GET /api/v2/import/jobs/{id}/errors`（JSON；如需 CSV 另行提供轉換） |
| Legacy Import Commit | `POST /api/import` | Deprecated | `POST /api/v2/import/jobs/{id}/commit` |
| Legacy Query | `GET /api/records*` | Deprecated（對外示範不建議） | v2 query endpoints（`/api/v2/query/*`） |

備註：`/api/upload/pdf*` 與 PDF→CSV→v2 ingest 屬另一條支線（可另行規劃，但不在本文件主要淘汰範圍）。

## 2) Repo 現況（截至 2026-01-31）

- multi-tenant：legacy import 相關端點已被拒絕（410）。
- docs/scripts：已開始把「教學/驗證」全面改為 v2。

### 已完成的示範/工具切換（v2-only）

- form-analysis-server/test-api.sh
- form-analysis-server/test-api.ps1
- scripts/tests/test_p3_full_flow.py
- scripts/tests/test_p3_upload.py
- tools/comprehensive_verification_test.py（API 測試段落改用 v2 import jobs）
- tools/test_server.py（新增 v2 mock endpoints；legacy 仍保留但標註 deprecated）

### 仍需持續清理的高風險文件（會讓新使用者誤用 legacy）

- dev-guides/USER_UPLOAD_FLOW.md（已加上「歷史 legacy」警示與 v2 對應流程；後續可考慮把 legacy 章節移到附錄）
- dev-guides/USER_FLOW_DIAGRAMS.md（已標註 legacy 流程圖為歷史現況；後續可逐步補 v2 版本流程圖）
- form-analysis-server/README.md、form-analysis-server/backend/README.md（仍包含 legacy endpoints 的示範與 API 說明）
- getting-started/MANUAL_STARTUP_GUIDE.md、getting-started/QUICK_START.md（已局部更新，但需持續檢查其他段落）

## 3) 分階段移除策略（建議）

### Phase A：停止示範/文件引導（現在 → 近期）

- 所有「新手指南、測試腳本、驗證腳本、範例 curl」預設只走 v2。
- legacy endpoints 只保留在「Legacy/Compatibility」章節，且清楚標註：
  - 單租戶可用（最低相容性）
  - multi-tenant 一律 410

### Phase B：產品 UI 切換（下一步）

- 前端 UploadPage 從 legacy `/api/upload` + `/api/import` 切換為 v2 import jobs：
  - `POST /api/v2/import/jobs`（上傳/驗證）
  - `GET /api/v2/import/jobs/{id}`（poll/顯示狀態）
  - `GET /api/v2/import/jobs/{id}/errors`（顯示錯誤列）
  - `POST /api/v2/import/jobs/{id}/commit`（確認入庫）

> 狀態：已完成（2026-01-31）。
> - UploadPage 的 CSV 流程不再呼叫 legacy `/api/upload`、`/api/import`。
> - 回歸保護：新增 `frontend/src/pages/UploadPage.noLegacy.test.ts`。

### Phase C：限制 legacy 可用性（切換完成後）

- 單租戶模式下：
  - legacy endpoints 改成「僅 admin/dev」或「需 feature flag 才能啟用」。
  - 回應加上 deprecation 訊號（例如 response header `Deprecation: true`、log warning、audit event）。

### Phase D：移除 legacy endpoints（最後）

- 刪除 legacy routers 與其依賴的 legacy tables/資料寫入邏輯。
- 如仍需離線匯入：改成獨立工具（離線 migration script），避免保留對外 API。

## 4) 驗收/門檻（避免回歸）

- 所有 getting-started / README / tools / scripts：不再以 legacy 作為主要教學或預設路徑。
- multi-tenant 下：legacy import endpoints 仍維持 410（已落實）。
- 至少一條 v2 import 的端到端（e2e 或 integration）驗證：create job → READY → commit → v2 query 可查。

## 5) 參考文件

- dev-guides/IMPORT_STRATEGY.md
- dev-guides/LEGACY_INVENTORY.md
- dev-guides/LEGACY_API_INVENTORY.md
