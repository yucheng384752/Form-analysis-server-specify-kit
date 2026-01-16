# 註冊 / 初始化流程（tenant + API key）

這份文件描述「第一次啟動後」要怎麼把系統設定到可用狀態。

本專案的「註冊」不是傳統帳號密碼註冊，而是：

- 建立（或選擇）tenant（租戶）
- （可選）啟用 API key 驗證，並建立第一把 tenant-bound API key
- 讓前端/呼叫端在每次 API request 都帶上正確 header

---

## 名詞與規則

- **Tenant**：資料隔離單位。後端用 `X-Tenant-Id` header（或 API key 綁定 tenant）決定你在操作哪一個租戶。
- **API key（tenant-bound）**：簡易防護用。啟用後，所有受保護的 API 都需要 `X-API-Key`。
  - key 會綁定 tenant：啟用後，server 會以 key 推導 tenant，並忽略 client 提供的 `X-Tenant-Id`（避免繞過）。

---

## 0) 啟動系統

你可以用 docker compose 或腳本啟動。

- 後端 Swagger：`http://localhost:18002/docs`
- 前端：`http://localhost:18003`

（詳細啟動方式請看：getting-started/QUICK_START.md）

---

## 1) 建立 / 選擇 tenant（第一次必做）

### 方法 A（推薦）：用前端自動 bootstrap

前端啟動時會呼叫 `/api/tenants`：

- 若後端回傳 **0 個 tenants**：前端會自動呼叫 `POST /api/tenants` 建立預設 tenant（名稱 `UT`、code `ut`），並把 tenant id 存到瀏覽器 localStorage。
- 若後端回傳 **1 個 tenant**：前端會自動選擇該 tenant。
- 若後端回傳 **多個 tenants**：你需要明確指定要用哪個 tenant（目前做法是把 tenant id 放在 localStorage，或後續做 UI 選擇器）。

#### 補充：用「註冊 / 初始化」頁（UI）手動完成

前端提供一個專門的 onboarding 頁面，適合初次建置/切換環境時使用：

1. 開啟前端：`http://localhost:18003`
2. 點選頁面中的「註冊 / 初始化（tenant + API key）」tab
3. 你可以在頁面上：
  - 按「自動初始化 Tenant」：在空資料庫下建立預設 tenant（UT / ut）並保存 tenant id
  - 按「刷新 tenants 列表」並選擇要使用的 tenant
  - 在啟用 `AUTH_MODE=api_key` 後，貼上 raw API key 並按「保存 API key」（保存到 localStorage）

### 方法 B：用 API 手動建立

1) 列出 tenants

`GET /api/tenants`

2) 若為空，建立 tenant

`POST /api/tenants`

Body 範例：

```json
{
  "name": "UT",
  "code": "ut",
  "is_default": true,
  "is_active": true
}
```

---

## 2) （可選）啟用 API key 驗證（簡易身份驗證）

目標：阻擋公網掃描/濫用，不做完整 RBAC。

注意：**第一次建立 tenant 時，建議先不要開 `AUTH_MODE=api_key`**。

推薦順序：

1. `AUTH_MODE=off` 啟動 → 建立 tenant
2. 用腳本建立第一把 API key（需要 tenant 已存在）
3. 再把 `AUTH_MODE=api_key` 打開並重啟

### 2.1 建立第一把 API key（bootstrap）

PowerShell：

```powershell
# 在 form-analysis-server 目錄下
python .\backend\scripts\bootstrap_tenant_api_key.py --tenant-code ut --label local-dev
```

會輸出 raw key（只顯示一次，請保存）。

安全閘門：預設只允許在 DB 還沒有任何 key 時建立；若真的要再加 key，才用 `--force`。

### 2.2 啟用 API key middleware

後端環境變數（示例）：

```env
AUTH_MODE=api_key
AUTH_API_KEY_HEADER=X-API-Key
AUTH_PROTECT_PREFIXES=/api
```

如果你要保護所有路徑（包含 docs），請看後端 README 的 profiles 說明。

---

## 3) 前端/呼叫端 header 要怎麼帶

### 3.1 Tenant header（前端已自動處理）

- 前端會自動對所有 `/api*` request 注入 `X-Tenant-Id`（除了 `/api/tenants`）。
- 若 DB 重建導致 tenant id 失效，前端會嘗試自癒（重新選擇/重建預設 tenant）。

### 3.2 API key header（若啟用 AUTH_MODE=api_key）

前端支援兩種來源（二選一）：

1) **環境變數**（建議 dev 使用）：

- `VITE_API_KEY=<你的 raw key>`
- （可選）`VITE_API_KEY_HEADER=X-API-Key`

2) **瀏覽器 localStorage**（方便手動切換）：

- key：`form_analysis_api_key`
- value：你的 raw key

你可以在 DevTools Console 設定：

```js
localStorage.setItem('form_analysis_api_key', '<your-raw-key>')
```

---

## 常見問題

### Q: 我開了 `AUTH_MODE=api_key`，前端進不去 / 變 401？

A: 代表前端沒有送 `X-API-Key`。請用本文件「3.2」設定 `VITE_API_KEY` 或 localStorage。

### Q: 我想用 API key 綁 tenant，那還需要 `X-Tenant-Id` 嗎？

A: 不需要。啟用後 server 會忽略 `X-Tenant-Id`，以 API key 綁定 tenant 為準。
