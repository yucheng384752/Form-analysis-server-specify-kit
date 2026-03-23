# AI Agent 開發技巧（從本次聊天萃取）

最後更新：2026-01-18

這份文件把本次協作中反覆證明有效的「工程做法」整理成 AI agent 可直接套用的規範與操作手冊。

---

## 0) 任務導向原則（先對齊目標再動手）

- **先釐清契約（Contract）**：
  - 前端需要什麼欄位/形狀（例如 `additional_data.rows` 必須是 `list[dict]` 且扁平）
  - 後端保證什麼不變性（例如多租戶隔離、traceability 必定可顯示明細 rows）
- **先把「阻斷」與「提升」分開**：
  - P0：會造成錯租戶/資料外洩/功能壞掉/回歸風險
  - P1~P3：可排程改善
- **修根因，不做表面 patch**：
  - 例：P2 顯示不到 items，不是「前端加更多 if」，而是「後端輸出形狀保證」+「回歸測試」。

---

## 1) 多租戶安全（Tenant-safety）

### 1.1 一條鐵律：tenant-scoped 優先，legacy fallback 必須可證明安全

- **V2（tenant-scoped）為準**：所有查詢/追溯/匯入盡量走 v2 tables。
- **Legacy tables（不帶 tenant_id）是風險來源**：
  - 多租戶時禁止 fallback，否則會跨租戶讀到別人的資料。
- **允許 legacy fallback 的唯一合理條件**：
  - DB 只有 0/1 個 tenant（單租戶/開發環境），且行為有測試保障。

### 1.2 Tenant resolver 行為要一致、可預期

- **多租戶且無唯一 default**：不要用 422（表單語意），改用 400（請求不完整）更貼近「必填 header」。
- **錯誤訊息要可操作**：要清楚說「缺 `X-Tenant-Id`」以及何時需要。

### 1.3 前端：永遠不要靠「猜 tenant」

- 全域 fetch wrapper 可以**自動注入 `X-Tenant-Id`**（對 tenant-scoped 路由），但：
  - 不要在頁面載入時做會改狀態的「自動建立 tenant」行為（見 2.2）。

---

## 2) 權限設計（Auth/Admin）

### 2.1 一條鐵律：禁止隱性升權（No implicit privilege escalation）

- **全域 wrapper 不得自動帶 `X-Admin-API-Key`**。
- 管理者 header 只能在：
  - 使用者「明確啟用管理者模式」後
  - 由呼叫點（call site）顯式加上

這能避免「初始頁面自動帶入 admin 參數」這類問題。

### 2.2 Bootstrap 行為必須顯式授權

- 「資料庫沒有 tenant → 自動建立預設 tenant」這類動作屬於 admin 等級。
- 建議採用：
  - `ensureTenantIdWithOptions({ allowAdminBootstrap: true })`
  - 且必須已提供 admin key

### 2.3 Middleware 設計技巧：讓錯誤訊息幫助使用者

- 對 bootstrap endpoints（例如 `/api/tenants`, `/api/auth/*`）
  - 若缺 API key：可在 dev 模式回傳更可操作的提示（用 admin key 或設定 ADMIN_API_KEYS）

---

## 3) API 回應形狀（Shape）是產品的一部分

### 3.1 後端輸出要「穩定且可被前端消化」

- P2/P3 顯示明細時：
  - 前端最想要的是 `additional_data.rows: list[dict]`
- **避免巢狀形狀漂移**：例如 legacy 資料可能是 `{"rows": [{...}]}`，合併後要扁平化成單層 row dict。

### 3.2 Traceability 的最小保證

- 即使 `row_data` 缺失或 dataset 欄位散落在 columns：
  - 也要能組出 `rows`，並補上常用欄位（如 `winder_number`, `product_id`, `source_winder`）

---

## 4) 測試策略（Regression-first）

### 4.1 每修一個回歸，補一個最小測試

- 測試目標是「鎖住契約」，而不是覆蓋率。
- 優先補：
  - 多租戶禁止 legacy fallback
  - Query v2 的 P2 rows 必定存在且扁平
  - Traceability 回傳 rows 即使 row_data 缺失
  - Tenant resolver 在多租戶情境回 400

### 4.2 測試資料 seed 要對準真實資料形狀

- 特別注意 legacy/extras 的怪形狀：
  - `extras={"rows": [{...}]}`
  - items 只有 columns 沒有 row_data
- 這些都要 seed 成可重現的 fixture/helper。

---

## 5) 匯入/驗證策略（不要被資料欄位綁死）

- 若需求是「P1 只需要 LOT NO」：
  - 驗證應以檔名擷取的 lot_no 為準
  - 不要強制要求特定資料欄位（例如 Screw Pressure/Line Speed）
- 把「資料正規化」集中在單一處理層：
  - 例如 lot_no pattern、P1/P2 檔名解析、`2507173_02_10 → 2507173_02`

---

## 6) 變更管理與文件同步（Docs/Script/Config）

### 6.1 部署預設值要寫在「部署層」

- 例：Docker Compose 預設 `AUTH_MODE=api_key`，但程式預設仍可保留 `AUTH_MODE=off` 以降低開發/測試踩雷。

### 6.2 文件跟著契約走

- README/getting-started 要同步：
  - tenant 初始化流程
  - auth 模式與 header
  - curl 範例要能直接複製執行

### 6.3 腳本不可硬編絕對路徑

- `.bat/.ps1` 應使用 `%~dp0` 或相對路徑，避免換資料夾即壞。

---

## 7) AI agent 工作流程（可直接照做）

### 7.1 推薦流程

1. **找契約**：前端期待的 payload shape / 後端保證
2. **定位來源**：搜尋路由/serializer/merge 函數
3. **做最小修正**：集中在「輸出契約層」或「安全邏輯層」
4. **加回歸測試**：先寫 failing case，再修到 pass
5. **跑測試**：先局部，再全套
6. **更新文件/TODO**：把決策與不變條款寫下來

### 7.2 快速檢查清單

- [ ] 多租戶時是否可能讀到 legacy tables？
- [ ] 是否有任何地方「自動帶 admin header」或「自動做 admin 動作」？
- [ ] Query/Traceability 的 `additional_data.rows` 是否永遠可用且扁平？
- [ ] 錯誤碼是否語意合理（400 vs 422）？
- [ ] 是否新增了對應回歸測試？

---

## 8) 具體 Do / Don’t（給 agent 的硬規範）

### Do

- 明確把「安全不變性」寫成程式碼與測試。
- 任何前後端不一致，優先修「後端輸出契約」。
- 新增 option flag（例如 `allowAdminBootstrap`）把危險行為變成顯式行為。

### Don’t

- 不要用全域 wrapper 偷偷加 admin header。
- 不要在多租戶環境 fallback 到不帶 tenant 的 legacy tables。
- 不要為了過一個 UI case 在前端加一堆特殊分支，而不修後端輸出形狀。

---

## 9) 本次聊天的高價值「不變條款」（建議納入 PRD/Architecture）

- Admin 權限必須顯式啟用、顯式附加 header；不得隱性帶入。
- 多租戶下禁止 legacy fallback；僅允許單租戶情境 fallback。
- P2/P3 明細表格依賴 `additional_data.rows`；後端必須保證存在且為扁平 rows。
- 匯入驗證規則要以產品需求為準（例如 P1 最小 LOT NO），不要綁死特定欄位。

### 9.1（新增）QueryPage「資料查詢」渲染契約（前端長期不變）

目標：使用者用 `lot_no` 查詢時，**P2 的 UI 只顯示 1 張卡片**（預設收合），展開後顯示 **items 細項表格**。

- **聚合邏輯**（lot_no 查詢情境）：
  - 後端 Query V2 可能回傳「同一個 lot_no 多筆 records（每個 winder 一筆）」
  - 前端在 lot_no 查詢情境下需要把這些 records 聚合成「單筆 record + `additional_data.rows` 20 筆」以供 UI 呈現
- **呈現邏輯**：
  - 當「lot_no 查詢且沒有指定 winder_number」時：結果區只渲染 1 張可展開卡片（預設收合）
  - 卡片展開內容：直接顯示 P2 明細（依賴 `additional_data.rows`）
  - 當使用進階查詢指定 `winder_number` 時：維持單筆/多筆 record 的一般列表模式（不可合併，避免 traceability/精確查詢被破壞）

對應實作位置（供維護）：
- 前端 UI：form-analysis-server/frontend/src/pages/QueryPage.tsx
- 前端樣式：form-analysis-server/frontend/src/styles/query-page.css

### 9.2（新增）Admin key 的儲存與啟動行為（前端長期不變）

- **Admin key 不可被全域自動帶入**：全域 fetch wrapper 不得自動注入 `X-Admin-API-Key`。
- **Admin key 儲存位置**：前端以瀏覽器的 localStorage 儲存（不是 cookie）。
  - 若使用者未在 UI 啟用管理者模式，localStorage 不會自動出現 admin key。
  - 重啟後端/前端伺服器不會清除瀏覽器 localStorage（除非使用者手動清除站點資料、或使用無痕視窗）。
