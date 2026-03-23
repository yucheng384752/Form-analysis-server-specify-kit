# 驗證機制盤點（Upload / Import v2 / PDF→CSV）

最後更新：2026-01-23

本文件整理「從上傳到寫入資料庫」各階段的驗證機制，並列出目前系統對 lot_no 的統一規則。

## 核心結論（目前系統行為）

- lot_no 驗證一律以「檔案內容欄位」為準，不再以檔名擷取作為驗證依據。
- P3 的 lot_no 允許帶尾碼（例如 `2507173_02_18`），但不可空白；空白視為錯誤。
- PDF→CSV 轉檔後自動建立的 UploadJob 會套用相同的 CSV 驗證機制（同一個 `FileValidationService.validate_file`）。

## CSV/Excel Upload（UploadJob）

主要路徑：
- 驗證器：[form-analysis-server/backend/app/services/validation.py](../form-analysis-server/backend/app/services/validation.py)
- 相關 API：[form-analysis-server/backend/app/api/routes_upload.py](../form-analysis-server/backend/app/api/routes_upload.py)

驗證內容：
- 檔案格式：僅支援 `.csv/.xlsx/.xls`
- 解析：CSV 使用 `utf-8-sig`（處理 BOM）；Excel 依副檔名選 engine
- 空列：整行空白會在 DataFrame 層級被 drop
- lot_no：
  - P1/P2：從內容欄位（`CSVFieldMapper.LOT_NO_FIELD_NAMES`）取值；必須符合 `^\d{7}_\d{2}$`（允許有後綴但會正規化成 7+2 再比對）
  - P3：優先取 `lot no` 欄位，否則回退 `P3_No.` 擷取；允許 `7+2+後綴`，但不可空白
- 產出：
  - 統計 total/valid/invalid
  - row-level errors（寫入 `UploadError`）

## Import v2（ImportJob：parse → validate → commit）

主要路徑：
- Import service：[form-analysis-server/backend/app/services/import_v2.py](../form-analysis-server/backend/app/services/import_v2.py)
- v2 routes：[form-analysis-server/backend/app/api/routes_import_v2.py](../form-analysis-server/backend/app/api/routes_import_v2.py)

### 上傳建立 ImportJob（routes_import_v2）
- table_code 必須存在
- 同一批檔案不可混用副檔名
- SHA256 去重（可用 allow_duplicate 放行）

### parse_job（讀檔入 staging_rows）
- 目前 parse 只負責：讀 CSV→Dict→寫入 `StagingRow.parsed_json`
- 編碼：先 `utf-8-sig`，失敗 fallback `cp950`

### validate_job（staging row 驗證）
- 逐列從內容欄位抓 `lot_no`：
  - 缺值：該列 invalid，寫入 errors_json
  - 格式：
    - P1/P2：要求 7+2 格式（允許後綴但會 canonicalize）
    - P3：允許 7+2+後綴，但不可空白

### commit_job（寫入 v2 表）
- P1：要求單檔只有 1 個 lot_no；寫入/更新 `p1_records`（extras.rows）
- P2：要求單檔只有 1 個 lot_no；依 winder 分組寫入/更新 `p2_records` 與 `p2_items_v2`
- P3：以每列的 lot_no 分組寫入/更新 `p3_records` 與 `p3_items_v2`；不再沿用上一列 lot_no（空白列會在 validate 階段變 invalid）

## PDF Upload / PDF→CSV

主要路徑：
- PDF 上傳：[form-analysis-server/backend/app/api/routes_upload.py](../form-analysis-server/backend/app/api/routes_upload.py)
- PDF 轉檔與自動 ingest：[form-analysis-server/backend/app/services/pdf_conversion.py](../form-analysis-server/backend/app/services/pdf_conversion.py)

- `POST /api/upload/pdf`：只做基本檔案檢查（副檔名/大小/%PDF- header），保存 PDF 與建立 `PdfUpload` 記錄；不解析、不匯入。
- PDF 轉 CSV 後 auto-ingest：
  - 將轉出的 CSV 建立 `UploadJob`
  - 呼叫 `file_validation_service.validate_file(...)` 進行同一套 CSV 驗證

## 欄位來源（lot_no 欄位集合）

- 欄位定義集中在：[form-analysis-server/backend/app/services/csv_field_mapper.py](../form-analysis-server/backend/app/services/csv_field_mapper.py)
  - `CSVFieldMapper.LOT_NO_FIELD_NAMES`
