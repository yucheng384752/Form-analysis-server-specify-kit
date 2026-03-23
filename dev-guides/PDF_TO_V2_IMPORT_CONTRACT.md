# PDF → v2 import 串接（契約與規則）

最後更新：2026-01-21

## 目標

- PDF 轉出的 CSV **不再走** legacy upload_job + `/api/import`。
- 前端可先預覽/編修 CSV，再用 `/api/v2/import/jobs` 走一致的 parse/validate/commit 流程。

## Converter 輸出命名規則（Mapping 規則）

前端會用檔名自動判斷表別（table_code）：

- `P1_*.csv` → `table_code = P1`
- `P2_*.csv` → `table_code = P2`
- 其他 `.csv`（含 `P3_*.csv`）→ `table_code = P3`

建議 converter 輸出檔名固定使用 `P1_` / `P2_` / `P3_` 前綴，避免誤判。

## 後端 API 契約

### 1) 取得 PDF 轉檔輸出（不建立任何 job）

`GET /api/upload/pdf/{process_id}/convert/outputs?include_csv_text=1`

- 說明：回傳該次 PDF conversion job 的輸出 CSV 檔案清單。
- 不會建立 UploadJob / ImportJob。
- `include_csv_text=1` 時會回傳 `csv_text` 方便前端立即顯示表格。

回應：

```json
{
  "outputs": [
    {
      "filename": "P1_2503033_01.csv",
      "csv_text": "lot_no,quantity\n2503033_01,1\n"
    }
  ]
}
```

錯誤：
- 404：找不到 PDF 上傳紀錄/轉檔工作
- 409：轉檔尚未完成
- 422：沒有可用的 CSV（只輸出空檔或 `error_list.csv`）

### 2) 前端建立 v2 import job（沿用既有）

`POST /api/v2/import/jobs`

- form-data：
  - `table_code`: `P1`/`P2`/`P3`
  - `files`: CSV 檔案（前端可用 `csv_text` 建立 File/Blob，上傳目前使用者編修後的內容）

後續：
- 前端輪詢 `GET /api/v2/import/jobs/{job_id}` 直到 `READY`/`FAILED`
- `READY` 後可呼叫 `POST /api/v2/import/jobs/{job_id}/commit`

## 現況限制（先不做）

- v2 import job 尚未提供「直接覆寫已上傳檔案內容」的編輯 API。
- 因此本方案是：**使用者編修後再建立新的 v2 job**（或重新驗證同一檔案會建立新 job）。
