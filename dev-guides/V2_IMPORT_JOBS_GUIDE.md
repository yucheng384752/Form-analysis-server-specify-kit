# V2 Import Jobs 使用指南（推薦匯入流程）

最後更新：2026-01-31

本文件目標：提供「匯入 CSV 的正式主流程」最小可用指引。

- 主流程：`POST /api/v2/import/jobs` → poll 到 `READY/FAILED` → `POST /commit` 或 `GET /errors`
- multi-tenant：必帶 `X-Tenant-Id`；且 legacy import endpoints（`/api/upload`、`/api/import`、`/api/errors.csv`）在 multi-tenant 下會回 `410 Gone`

> 相關背景決策請參考：
> - `dev-guides/IMPORT_STRATEGY.md`
> - `dev-guides/IMPORT_WRITE_STRATEGY.md`
> - `dev-guides/LEGACY_DEPRECATION_PLAN.md`

---

## 1) 你需要準備什麼

### 1.1 必要 Header

- `X-Tenant-Id: <TENANT_ID>`：必帶
- `X-API-Key: <YOUR_API_KEY>`：若 `AUTH_MODE=api_key` 需要

### 1.2 端點摘要

- 建立匯入 job（含檔案上傳）：`POST /api/v2/import/jobs`
- 查詢 job 狀態：`GET /api/v2/import/jobs/{id}`
- 查詢錯誤：`GET /api/v2/import/jobs/{id}/errors`
- 提交（入庫）：`POST /api/v2/import/jobs/{id}/commit`

---

## 2) Job 狀態（重要）

常見狀態（以系統實作為準）：

- `QUEUED` / `UPLOADED`：已建立，等待背景處理
- `PARSING` / `VALIDATING`：背景解析/驗證中
- `READY`：可 commit
- `FAILED`：解析/驗證失敗（用 `/errors` 取得錯誤）
- `COMMITTING`：提交中
- `COMMITTED`：提交完成

> 建議：UI / 腳本要以 `READY | FAILED | COMMITTED` 這三個 terminal-ish 狀態做判斷。

---

## 3) Curl（Bash）最小示例

以下以 P1 為例；P2/P3 只需把 `table_code` 換成對應值。

```bash
# 0)（可選）確認後端可用
curl -sS "http://localhost:18002/healthz"

# 1) 建立匯入 job
JOB_JSON=$(curl -sS -X POST "http://localhost:18002/api/v2/import/jobs" \
  -H "X-Tenant-Id: <TENANT_ID>" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -F "table_code=P1" \
  -F "allow_duplicate=false" \
  -F "files=@P1_2503033_01.csv;type=text/csv")

echo "$JOB_JSON"
# 你會拿到 {"id": "...", "status": "QUEUED", ...}

# 2) poll 到 READY / FAILED
curl -sS -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  "http://localhost:18002/api/v2/import/jobs/<JOB_ID>"

# 3a) READY → commit
curl -sS -X POST -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  "http://localhost:18002/api/v2/import/jobs/<JOB_ID>/commit"

# 3b) FAILED → errors
curl -sS -H "X-Tenant-Id: <TENANT_ID>" -H "X-API-Key: <YOUR_API_KEY>" \
  "http://localhost:18002/api/v2/import/jobs/<JOB_ID>/errors"
```

---

## 4) PowerShell（Windows）最小示例

> 在 Windows 建議用 `curl.exe`，避免 PowerShell alias 行為差異。

```powershell
$BaseUrl = "http://localhost:18002"
$TenantId = "<TENANT_ID>"
$ApiKey = "<YOUR_API_KEY>"  # 若 AUTH_MODE=api_key
$CsvPath = "P1_2503033_01.csv"

# 1) 建立 job（multipart）
$job = curl.exe -sS -X POST "$BaseUrl/api/v2/import/jobs" `
  -H "X-Tenant-Id: $TenantId" `
  -H "X-API-Key: $ApiKey" `
  -F "table_code=P1" `
  -F "allow_duplicate=false" `
  -F "files=@$CsvPath;type=text/csv" | ConvertFrom-Json

$jobId = $job.id
Write-Host "job_id=$jobId status=$($job.status)"

# 2) poll 到 READY / FAILED
while ($true) {
  $j = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v2/import/jobs/$jobId" -Headers @{
    "X-Tenant-Id" = $TenantId
    "X-API-Key"   = $ApiKey
  }

  Write-Host "status=$($j.status)"
  if ($j.status -in @("READY","FAILED","COMMITTED")) { break }
  Start-Sleep -Seconds 1
}

# 3) commit / errors
if ($j.status -eq "READY") {
  Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v2/import/jobs/$jobId/commit" -Headers @{
    "X-Tenant-Id" = $TenantId
    "X-API-Key"   = $ApiKey
  }
} else {
  Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v2/import/jobs/$jobId/errors" -Headers @{
    "X-Tenant-Id" = $TenantId
    "X-API-Key"   = $ApiKey
  }
}
```

---

## 5) 常見行為（避免踩雷）

- **重新匯入（rerun）**：請「新建 job」而不是重跑同一個 job 的 commit。
- **commit 全成全敗（atomic）**：commit 期間若出錯，不應留下部分寫入。
- **重複資料**：
  - 同內容（同檔/同 SHA-256）會被拒絕（回應會提示已存在的 job/batch）。
  - 同 job 內：會做 row-level 去重與 business-key 合併（保守合併，避免覆蓋非空衝突值）。

---

## 6) 我該用哪個文件看更多？

- 想看「策略/決策」：`dev-guides/IMPORT_STRATEGY.md`
- 想看「只寫 v2 / 不 dual-write 的理由與切換計畫」：`dev-guides/IMPORT_WRITE_STRATEGY.md`
- 想看「legacy endpoints 移除節奏」：`dev-guides/LEGACY_DEPRECATION_PLAN.md`
