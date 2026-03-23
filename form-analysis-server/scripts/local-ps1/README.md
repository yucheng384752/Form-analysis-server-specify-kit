# local-ps1

這個資料夾放的是「本機/開發用途」的 PowerShell 輔助腳本（通常用來跑一段特定流程、重現問題或匯入特定測資）。

## 注意事項

- 這些腳本多半需要本機已有資料檔（例如侑特資料夾），因此預設路徑可能不適用所有人。
- 大部分腳本已改為可用參數覆寫（例如 `-BaseUrl` / `-ApiBase` / `-DataDir` / `-TenantId`）。
- 若未提供 `TenantId`，腳本會嘗試呼叫 `GET /api/tenants` 自動取第一個 tenant。

## 範例

- 匯入 P1（指定檔案路徑）：
  - `powershell -ExecutionPolicy Bypass -File .\import-p1.ps1 -ApiBase http://localhost:18002 -P1File C:\path\to\P1.csv`

- 匯入 production 資料（只取前 2 個檔案）：
  - `powershell -ExecutionPolicy Bypass -File .\test-import-production-data.ps1 -DataDir C:\path\to\data -Take 2`
