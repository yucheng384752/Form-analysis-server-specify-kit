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
- 必須帶 `X-Tenant-Id` 才能成功呼叫（前端已在共用注入/確保 tenant 的流程補齊）

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
