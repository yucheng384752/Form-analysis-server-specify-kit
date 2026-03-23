# IMPORT：未來匯入寫入策略（Write Strategy）

最後更新：2026-01-23

## TL;DR（決策）

- **最終策略：v2-only write（只寫 v2）**
  - 所有「正式匯入（commit）」都應透過 **v2 ImportJob（parse → validate → commit）** 寫入租戶隔離的 v2 資料表（P1Record/P2Record/P3Record + items_v2 等）。
  - `UploadJob` 的角色定位為 **可檢視/可編修的暫存（staging）**，不應被視為長期寫入策略的一部分。
- **legacy import（/api/import）僅保留做相容/臨時用途**
  - 主要原因：legacy 資料表多為 **非 tenant-scoped**，在多租戶下存在交叉污染與資訊外洩風險。
  - 不採用 dual-write（同時寫 legacy + v2），避免長期兩套行為分岔。

## 現況背景

### 現有兩條路徑

1) **UploadJob path（可編修）**
- 來源：`/api/upload`（legacy；僅作 staging/可編修暫存。multi-tenant 下 legacy import 端點會回 410）
- 內容：`UploadJob.file_content` 保存檔案 bytes，可供前端檢視/修正。

2) **v2 ImportJob path（可驗證/可 commit）**
- 來源：
  - `POST /api/v2/import/jobs/from-upload-job`
  - `POST /api/upload/pdf/{process_id}/convert/ingest`（會為每個 UploadJob 同步建立對應 ImportJob）
- 流程：parse → validate → commit
- 寫入：tenant-scoped v2 tables（作為後續查詢/追溯的主要資料來源）

### 為什麼不能長期 dual-write

- **資料一致性成本高**：一份 CSV 的規格/欄位 mapping/normalize/修正紀錄若要同步到兩套表，長期維護成本與回歸風險大。
- **多租戶安全性**：legacy 資料表不完整 tenant-scoping，dual-write 會讓非隔離資料更難收斂。
- **產品 ID / lot_no 正規化已收斂**：v2 路徑已具備一致的 normalize 與 traceability 需求；再維持 legacy 同步會拖慢收斂。

## 策略選項（文件化）

### 選項 A：v2-only write（採用）

- **寫入**：僅 v2（ImportJob commit）
- **讀取**：v2 優先；legacy 只做「安全前提下」的 fallback（例如資料庫只有單一 tenant 時）
- **優點**：
  - 行為一致、測試面小、收斂快
  - 多租戶風險最低
- **缺點/代價**：
  - 若既有環境有 legacy 資料，可能需要補一條回填/遷移腳本

### 選項 B：dual-write（不採用）

- **寫入**：同時寫 legacy + v2
- **風險**：一致性/回歸成本倍增；多租戶下 legacy 表的使用會變得更危險。

### 選項 C：transitional（短期可能存在，但不作為最終目標）

- 過渡期 UI 可能仍會呼叫 legacy import（例如舊版 UploadPage 曾用 legacy commit），但需有明確切換計畫與移除期限。

> 更新（2026-01-31）：UploadPage 的 CSV 匯入主流程已完成切換為 v2 import jobs commit（不再呼叫 legacy `/api/import`）。

## 切換計畫（建議）

### Phase 0：維持現況但不擴散
- 禁止新增 legacy query routes；已移除 `/api/query/*`。
- 新功能一律走 `/api/v2/*`。

### Phase 1：UI 匯入動作全面切到 v2
- UploadPage：
  - 對 CSV：以 `from-upload-job` 建立 ImportJob
  - parse/validate 顯示結果後，commit 透過 `/api/v2/import/jobs/{job_id}/commit`
- PDF：已決策「轉檔後不自動 validate」，先停在 UploadJob 供使用者修 CSV，再用 v2 匯入。

### Phase 2：標記 legacy import deprecated
- `/api/import` 進入「僅相容/僅 admin/dev」狀態（可加 warning log / audit event）。

### Phase 3：移除或封存 legacy import
- 依照 `dev-guides/LEGACY_INVENTORY.md` 的清單逐項移除。

## 最小一致性測試（必備）

- 目標：確保「v2-only write」後，至少以下兩個核心能力可用：
  1) `/api/v2/query/*` 查得到匯入結果
  2) `/api/traceability/product/{product_id}` 可形成可用追溯鏈（P3→P2→P1）

對應測試：`form-analysis-server/backend/tests/integration/test_import_write_strategy_min_consistency.py`

## 回填/遷移責任邊界

- **資料回填不是 import job 的責任**。
- 若需把舊資料補到 v2：
  - 由 migrations/scripts 負責
  - 必須定義 tenant 對應規則（避免 legacy 非 tenant 資料污染）
  - 回填策略要可重跑（idempotent）
