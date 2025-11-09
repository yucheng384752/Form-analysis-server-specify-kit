# Form Analysis Server PRD

版本：v0.2（草稿）
最後更新：2025-11-04

## 1. Summary
讓工廠把紙本表單（P1 擠出、P2 分條、P3 沖孔自檢/QC）轉為 CSV，上傳→驗證→預覽修正→確認入庫，並能查詢單一 lot 的完整生產鏈（P1→P2→P3）。

工程補充（內部工具定位）：
- Logger 分析頁是「工程師用」的觀測與診斷工具（非客戶 Facing）。
- 在生產環境以「功能旗標/環境變數」控制是否啟用並在 UI 隱藏入口。

## 2. Audience（讀者與用途）
- 對 PM：掌握交付邊界、驗收標準、風險與里程碑。
- 對工程師：具體規格、資料模型、流程行為、觀測面向。
- 非客戶文件：本 PRD 的 Logger 分析為內部用途，不做對外訓練與展示。

## 3. Goals / Non-goals
- Goals
  - CSV 上傳、驗證、暫存預覽、可編修、確認入庫（冪等）。
  - 生產鏈完整性（P3 需有 P2，P2 需有 P1）。
  - P3 資料表使用複合唯一鍵 UNIQUE(lot_no, p3_no)（允許一個 lot 有多張 P3）。
  - 內部 Logger 分析：支援統計、搜尋、錯誤追蹤、效能觀測；可選 7 天 / 1 個月。

## 4. Scope（功能與行為）
### 4.1 上傳與驗證（Upload & Validate）
- 檔案：CSV（UTF-8，含/不含 BOM 均可）
- 分類：p1/p2/p3/qc（優先序：檔名前綴 → 預設值 → 表頭偵測）
- Lot 規則：正規化為 7位_2位（如 2503033-03 → 2503033_03）
- P3 特例：
  - 行資料若無 lot_no 但其他資料有效，允許暫存（預覽時標示警示），但 confirm 時仍須通過父鏈檢查。
- 錯誤彙整：檔案 meta.errors、預覽前 10 筆、coerced rows 記錄

驗收（工程）：
- 同批 CSV 混相上傳可被正確分類與預檢。
- P3 缺 lot_no 的行可見於暫存與預覽；confirm 時若缺父 P2，跳過並回報。

### 4.2 暫存與確認（Stage & Confirm）
- 暫存：`uploaded_files` / `uploaded_rows` + `upload_audit`
- Confirm：
  - P1：若無對應 lot 即建立最小記錄。
  - P2：`slitting_records` 主表；`slitting_checks` 以 (slitting_record_id, winder_no) upsert。
  - P3：`punching_self_check_records.extra.rows` 合併去重（基於 JSON hash）。

驗收：
- P2 相同 winder_no 不重覆；P3 重送內容不重覆。

### 4.3 Schema（重點）
- P1：`extrusion_records.lot_no` UNIQUE
- P2：`slitting_records.lot_no` UNIQUE 並 FK → P1（1:1）
- P3：`punching_self_check_records.lot_no` FK → P2（1:N）
- P3 複合唯一：
  ```sql
  ALTER TABLE punching_self_check_records
    DROP CONSTRAINT IF EXISTS punching_self_check_records_lot_no_key;
  ALTER TABLE punching_self_check_records
    ADD CONSTRAINT unique_lot_p3 UNIQUE (lot_no, p3_no);
  ```

### 4.4 工程可觀測性：Logger 分析（Internal Only）
- 目的：工程診斷與效能監控；非客戶 Facing。
- 前端頁（內部工具）
  - 統計：by_level、by_hour、by_logger、錯誤/警告數
  - 搜尋：關鍵字 + 等級 + 時間窗
  - 錯誤追蹤：Top 20
  - 效能：Top 慢 API（avg/min/max/P50/P95/P99）
  - CSV 匯出、30 秒自動刷新、容器寬 2400px、三圖 1/3 寬
- 後端 API（標示 Internal）
  - GET `/api/logs/analyze?hours&level&limit`
  - GET `/api/logs/search?q&level&hours&limit`
  - 時間窗限制：建議上限 744 小時（1 個月）；現狀 analyze=72（需調整）、search=168（建議 744）
- 可見性/發佈策略
  - 生產環境預設隱藏導覽入口（不在 UI 菜單出現）
  - 以環境變數/功能旗標啟用（例：VITE_ENABLE_LOGGER_DASHBOARD=true）
  - 無權限系統前，僅向工程人員提供 URL；或限制到特定網段/VPN

驗收：
- 選「最近 7 天/最近 1 個月」不出現 422；統計、搜尋與匯出可用
- 生產環境預設不顯示入口；設置旗標後可使用

## 5. Non-functional
- 效能：1 個月時間窗在限制 limit=1000 下，分析 API 2~5 秒返回（機房/資料量視情調整）
- 可靠性：confirm 冪等；每次 confirm 記錄 `upload_audit`
- 可維護：上傳模組化（FileValidator/LotExtractor/RowProcessor/FileStager）
- 資安/隱私：Logger 不輸出敏感資訊（密鑰、密碼、Cookie、PII）；必要時脫敏

## 6. Data Model（重點表）
- uploaded_files, uploaded_rows, upload_audit
- extrusion_records（P1）、slitting_records + slitting_checks（P2）
- punching_self_check_records（P3, UNIQUE(lot_no, p3_no)）
- Lookup：materials、slitting_machines、measurement_points、buckets、bottom_tapes

## 7. APIs（摘要）
- Upload
  - POST /api/upload/files（多檔驗證 & 暫存）
  - POST /api/upload/confirm?process_id=xxx
- View
  - GET /api/view/lots, /api/phase{1,2,3}/{lot}
- Logs（Internal）
  - GET /api/logs/analyze
  - GET /api/logs/search

## 8. Risks & Mitigations
- 大時間窗查詢壓力 → 限制 limit、預先彙總、必要時分頁或快取
- P3 lot 抽取混亂 → 檔名規範、上傳前置校正、預覽高亮提示
- CSV 欄位多樣 → HEADER_ALIASES 維護、未知欄位預警

## 9. Milestones
- M1（1 週，Internal）：Logger 分析上線（後端 hours 上限放寬、UI 入口隱藏、CSV 匯出）
- M2（2~3 週）：上傳/驗證/確認穩定（含 P3 複合唯一遷移）、查單 lot 檢視
- M3（可選）：Logger 分頁/快取、查詢效能優化、更多儀表板

## 10. Acceptance（整體）
- 上傳 p1/p2/p3 CSV → 預覽與錯誤可見 → 可修正 → confirm 後資料鏈完整
- P2 checks upsert 正常；P3 rows 合併去重
- Logger（Internal）支援 7 天/1 個月；生產環境預設不顯示入口

## 11. Change Log
- 2025-11-04：將 Logger 分析標記為 Internal Only，新增可見性策略；保留既有上傳/Schema 目標。