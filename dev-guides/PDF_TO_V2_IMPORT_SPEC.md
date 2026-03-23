# PDF→v2 Import 串接規格（先讓使用者看/修 CSV，再送 v2）

最後更新：2026-01-23

## 目標
- PDF 上傳後會啟動轉檔（PDF→CSV），但**轉檔完成不自動 validate**。
- 轉出的 CSV 先落在 **UploadJob（可檢視/編修）**；使用者修正後再手動送 **v2 import validate → commit**。
- 支援所有站別（P1/P2/P3）。
- PDF→CSV 轉換 server 輸出為 CSV 壓縮檔（zip）；一份 PDF 固定對應一份 CSV（轉換 server 已寫死）。

## 使用者流程（UI）
1) 上傳 PDF（上傳與轉檔同時進行）
2) 轉檔完成 → 顯示「可檢視/編修 CSV」卡片（UploadPage 延續卡片）
3) （可選）檢視/編修 CSV（UploadJob 編修能力）
4) 點「送出 v2 validate」→ 若失敗，仍回到 UploadPage 卡片顯示錯誤與可修正
5) validate 通過後 → 點「commit」

> 原因：轉檔 server 目前會產生多個錯誤內容，需要手動修正後再驗證。

## Table code 判斷規則
- 主要：靠 CSV 檔名判斷 `table_code`（P1/P2/P3）
- 若檔名與欄位特徵衝突：**以欄位特徵為主**（header fingerprint / 必要欄位集合）

## 去重與來源追溯
- 去重依據：PDF 原檔 `sha256`（同 tenant）
  - 若同一份 PDF 重複上傳，應回傳既有 `process_id`/conversion job（或建立新 job 但標記為 duplicate；以最小落地可採「直接回舊資料」）
- 來源追溯：
  - 需能由 v2 import job 追到：PDF 檔名、PDF sha256、PDF process_id、conversion job id、對應的 UploadJob process_id
  - 優先用既有機制落地：寫入 AuditEvent metadata（不強制新增 DB 欄位）

## 後端端點（兩步）

### Step 0：PDF 上傳/轉檔（既有）
- 上傳：既有 PDF upload endpoint（UploadPage 已提示需登入/使用者 API 才能使用）
- 查狀態：`GET /api/upload/pdf/{process_id}/convert/status`

### Step 1：產生 UploadJob（可編修）——轉檔完成後 ingest
- `POST /api/upload/pdf/{process_id}/convert/ingest?skip_validate=true&include_csv_text={bool}`
  - 目的：把轉出的 CSV 建成 UploadJob，**但不做 validate**（停在可編修階段）
  - 回傳：UploadJob 列表（含 process_id、filename、可選 csv_text），並回 `import_job_id`（對應 v2 ImportJob）
  - 冪等：同一個 conversion job 已 ingest 過，直接回傳既有 UploadJob

> 備註：目前 ingest 會同步建立 v2 ImportJob（以當下 UploadJob 的 bytes 做快照）。
> 若使用者後續編修 UploadJob 內容，需再次呼叫「from-upload-job」建立新的 v2 ImportJob 才會反映最新內容。

> 現況：此 endpoint 已存在 `skip_validate` 參數；PDF flow 需固定用 `skip_validate=true`。

### Step 2：UploadJob → v2 import validate（新增）
- `POST /api/v2/import/jobs/from-upload-job`
  - request（JSON）：
    - `upload_process_id`: UUID（必填）
    - `table_code`: string（可選；若不給，server 依「檔名→欄位特徵」自動判斷）
    - `allow_duplicate`: bool（可選；預設 false；但 PDF flow 常見會開啟 allow duplicate 以便反覆修正/重送）
  - server 行為：
    - 讀取 UploadJob.file_content（已包含使用者修正後內容）
    - 建立 import v2 job + import file（storage_path 可沿用既有 import v2 暫存策略）
    - 觸發 background parse + validate
    - 寫 audit event：包含來源追溯 metadata
  - response：既有 `ImportJobRead`（status 會進入 UPLOADED→PARSING→VALIDATING→READY/FAILED）

### Step 3：commit（既有）
- `POST /api/v2/import/jobs/{job_id}/commit`

## 驗收（Acceptance Criteria）
- 站別：全部（P1/P2/P3）
- 測試資料：新侑特資料 → PDF → UPLOAD from UT
- 允許 mock 外部轉檔 server
- 成功標準：
  - 上傳並轉檔通過（conversion job COMPLETED）
  - ingest 成功並停在 UploadJob（不自動 validate）
  - v2 validate 時 `lot no` 欄位驗證通過
  - 若 validate 失敗：可在 UI 修正內容後重新送 validate 並通過

## lot_no 驗證規則（補充）
- P1/P2：以內容欄位為主；若內容缺 lot_no，允許以檔名推論（如 `P1_2507173_02*.csv`）作為備援。
- P3：不從檔名推 lot_no；必須由內容欄位提供（`lot no` 或 `P3_No.`）。
