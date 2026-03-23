# PDF 上傳功能（第一版）限制清單

本文件定義「PDF 上傳」第一版的功能邊界與限制，目標是：
- 先把「上傳與保存」打通（不破壞既有 CSV/v2 匯入鏈）
- 以最小風險方式保留擴充空間（未來再接 PDF→JSON/CSV 轉換服務）

## 目前範圍（v1）

- 僅提供「上傳 PDF 並保存」：不解析 PDF、不轉檔、不寫入業務資料表
- API：`POST /api/upload/pdf`
- 前端：UploadPage 支援選擇 `.pdf` 並上傳（按鈕顯示「上傳 PDF」）

## 檔案限制

- 允許副檔名：`.pdf`（大小寫不敏感）
- 內容檢查：必須包含 PDF magic header（`%PDF-`）
- 檔案大小：上限 10MB
- 空檔（0 bytes）：拒絕

## 行為限制

- 不支援批次匯入：PDF 不會出現「匯入檔案」按鈕
- 不支援 CSV 預覽/展開：PDF 不會顯示「展開 CSV 內容」
- 不支援編輯/儲存修改：PDF 不會顯示「儲存修改」

## Tenant 限制

- PDF 上傳端點屬於 tenant-scoped 路由集合（依專案既有規則）
- `X-Tenant-Id` 建議一律帶上（前端已在共用注入/確保 tenant 的流程補齊），避免依賴「單 tenant / default tenant」推導。
- 若未帶 `X-Tenant-Id`：
	- tenants 總數=1 → 允許（自動帶入該 tenant）
	- 多 tenants 且存在唯一 `is_default=true` → 允許（自動帶入 default tenant）
	- 多 tenants 且無唯一 default → 回 400（要求指定 `X-Tenant-Id`）
- 若 `X-Tenant-Id` 格式不是 UUID → 回 422（格式錯誤）

## 儲存策略（v1）

- 保存位置：`{settings.upload_temp_dir}/pdf/{process_id}.pdf`
- 檔名：以 `process_id` 命名，避免路徑穿越與特殊字元問題
- 回傳：沿用 `FileUploadResponse` schema，`process_id` 為保存後的識別；row 統計值固定為 0

## 風險與不支援項目（待後續版本）

以下項目目前不處理；需要第二階段規格與實作：

- 密碼保護 PDF / 權限限制 PDF（需要偵測與錯誤回報）
- 掃描影像 PDF（OCR）與表格抽取
- 嵌入檔案（attachments）與潛在惡意內容深度掃描
- 頁數上限（目前未做；若要限制需解析 PDF metadata）
- 自動轉換為 CSV/JSON、或直接匯入 v2 staging

## 後續建議（v2）

- 新增 `POST /api/upload/pdf/{process_id}/convert`：非同步轉換，回傳 job_id
- 設計轉換輸出格式（JSON schema）與 mapping 規則
- 支援與 v2 import job 串接（將轉換結果送入 `/api/v2/import/jobs`）

---

## 串接 PDF→CSV server 前要確認的細節（對接檢核清單）

這份清單的目標是：在開始接外部 PDF→CSV/JSON 轉換服務前，先把「介面契約」談清楚，避免後續出現
（1）回傳格式不穩、（2）狀態無法對齊、（3）tenant/安全問題、（4）匯入 mapping 無法落地。

### 1) 入口 API（Request）

- **URL/Method**：是否為 `POST`？路徑名稱（例：`/convert`、`/api/convert/pdf`）？
- **Content-Type**：
	- `multipart/form-data`：檔案欄位名稱是 `file` / `pdf`？是否需要同時送 `filename`？
	- 或 `application/octet-stream`：是否需額外 header 指定檔名？
- **必要參數**：是否需要 `table_code (P1/P2/P3)`、`tenant_id`、`language`、`timezone`、`ocr=true/false`、`page_range` 等。
- **檔案限制**：大小上限、頁數上限、是否支援加密 PDF、掃描影像 PDF、旋轉頁/橫向頁。
- **Idempotency**：是否支援 `Idempotency-Key`（同一份 PDF 重送不重跑/可回同 job_id）。

### 2) 回應模式（同步 / 非同步）

- **同步模式**：`POST` 直接回結果（CSV/JSON）？最大處理時間？逾時策略？
- **非同步模式**：`POST` 回 `job_id`，再 `GET /jobs/{job_id}` 查狀態。
- **狀態對齊**：外部 server 的 status 枚舉有哪些？如何 mapping 到系統內狀態：
	- `NOT_STARTED/QUEUED/UPLOADING/PROCESSING/COMPLETED/FAILED`
- **取消/重試**：是否支援取消（`DELETE`/`POST cancel`）？哪些錯誤可重試？是否有 `Retry-After`？

### 3) 輸出格式（CSV / JSON / ZIP）

- **回傳形式**：
	- 直接回「純 CSV」檔案？
	- 回 JSON（內含 CSV 字串/欄位結構/下載 URL）？
	- 若一個 PDF 產生多份 CSV：用 zip 還是 JSON array？
- **編碼與換行**：UTF-8/UTF-8-SIG/Big5？換行 `\n`/`\r\n`？全形半形保留策略？
- **欄位命名**：header 是否固定？是否能輸出「標準欄位」以利後端 mapping/驗證？

### 4) 欄位對應與資料品質（最容易踩坑）

- **類型判斷**：如何分辨 PDF 對應 P1/P2/P3？要你提供 `table_code` 還是它可自動判斷？
- **欄位對齊**：是否能對齊本系統 v2 import/validation 需要的欄位（例如 lot_no、specification、machine、production_date、quantity 等）？
- **正規化規則**：日期格式、數字千分位、空白字元、全形半形、單位（kg/g）等是否一致？
- **缺失/不確定值**：用空字串、`null`、`N/A`？是否會輸出註解行或混入非資料列？

### 5) 錯誤回傳（Failure contract）

- **HTTP code 定義**：400/401/403/413/422/429/500 各代表什麼？
- **錯誤內容 schema**：是否回 `{error_code, message, details}`？details 是否包含頁碼/表格位置/欄位？
- **可重試性**：哪些錯誤可 retry？是否有節流/排隊資訊？

### 6) 結果取得方式與保存策略

- **結果取得**：
	- 直接回檔：`Content-Disposition` 檔名規則？
	- 回 URL：是否為 pre-signed URL？有效期限多久？是否需要 token？
- **保存/清理**：轉換結果在外部 server 保留多久？是否可設定「處理後立即刪除」？

### 7) 身分驗證、tenant 與安全

- **Auth**：API Key / Bearer token / mTLS？token 放 header 還是 query？
- **租戶隔離**：若外部 server 多租戶，如何確保 job/results 不跨 tenant？
- **敏感資料**：PDF/結果是否落地存檔？會不會記錄原文到 log？是否可關閉敏感 log？

### 8) 效能、容量與 timeout

- **效能指標**：平均/最慢處理時間（P95/P99）、併發上限、Rate limit（QPS）。
- **timeout 建議值**：connect/read timeout（本系統已有設定欄位可配置）。
- **大檔策略**：是否支援 chunk 上傳或必須整檔一次傳。

### 9) 版本與相容性

- **版本控管**：是否有 API versioning（路徑 v1/v2 或 header）？
- **schema 相容性**：欄位新增/更名是否會破壞相容？如何公告變更？

### 10) 與本系統串接時要定義的落地策略

- **轉換完成後的走法**：
	- 直接把結果送入 `/api/v2/import/jobs`？
	- 或先落地保存（CSV/JSON）再由使用者觸發匯入？
- **關聯鍵**：建議至少保存 `process_id`、`pdf_conversion_job_id`、後續 `import_job_id` 的關聯（用於追蹤與除錯）。
- **UI 呈現**：錯誤訊息/失敗原因要能被前端 polling 顯示（需外部 server 提供可讀錯誤）。
