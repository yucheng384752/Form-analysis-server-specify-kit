# 多租戶 / 初始化 / 管理者（Tenant & Users）實作摘要

這份文件整理「登入 / 初始化 / 管理者」拆頁後的責任邊界、Header 規則、以及 Tenant / Tenant users 的 CRUD 端點。

> 目標：
> - 避免跨租戶資料外洩（永遠要 tenant-scope）
> - 避免前端隱性帶入管理者權限（永遠要 explicit admin key）
> - 刪除一律採用安全刪除（soft delete）

---

## 前端頁籤責任

### 1) 「登入」

用途：一般使用者日常入口。

- 選擇 Tenant（保存 tenant_id 到 localStorage）
- 帳密登入取得 API key（若後端啟用 `AUTH_MODE=api_key`）
- 查 whoami（判斷自己是否為 tenant admin）

對應程式：

- `frontend/src/pages/RegisterPage.tsx`

### 2) 「初始化」

用途：只給內部維運或首次上線/緊急復原。

- 先貼上 admin key（保存於 localStorage）
- 空資料庫時建立 Tenant（bootstrap）
- 建立第一個 tenant admin（role=admin）

對應程式：

- `frontend/src/pages/InitPage.tsx`

### 3) 「管理者」

用途：日常 CRUD（Tenant / Users）。

- Tenant：新增 / 改名 / 設預設 / 啟用停用 / 安全刪除
- Users：新增 / 改 username / 改 role / 啟用停用 / 安全刪除

對應程式：

- `frontend/src/pages/AdminPage.tsx`

---

## Header 規則（安全不變條款）

### Tenant scope（一定要有）

- tenant-scoped API（大多數 `/api/*`）需要 `X-Tenant-Id`
- 前端用 global fetch wrapper 自動補上 tenant header，避免漏帶。

對應程式：

- `frontend/src/services/fetchWrapper.ts`

### Admin key（一定要 explicit）

- admin-only API 需要 `X-Admin-API-Key`
- 前端**不允許**在 global fetch wrapper 裡自動注入 admin header
- 只有在 Init/Admin 頁面，使用者主動貼 key 後，該頁面呼叫 API 時才會明確帶 `X-Admin-API-Key`

---

## 後端端點摘要

### Tenant

- `GET /api/tenants`
  - 預設只回傳 `is_active=true`
  - admin key 才能用 `include_inactive=true` 看停用 tenant

- `POST /api/tenants`
  - bootstrap-only（用於「第一次」建立 default tenant）

- `POST /api/tenants/admin`
  - 日常新增 tenant（建議 UI 一律走這個）

- `PATCH /api/tenants/{tenant_id}`
  - 可更新 `name` / `is_active` / `is_default`
  - 設 `is_default=true` 時，後端會自動清掉其他 tenant 的 default，確保「只會有一個 default」

- `DELETE /api/tenants/{tenant_id}`
  - 安全刪除（soft delete）：`is_active=false`，並清掉 `is_default`

### Tenant users（包含 tenant admin）

- `GET /api/auth/users`
  - tenant admin 只會拿到自己 tenant 的 users
  - admin key 可用 `tenant_code=` 切換查看/管理不同 tenant

- `POST /api/auth/users`
  - 建立使用者（`role=user|admin`）

- `PATCH /api/auth/users/{user_id}`
  - 更新 `username` / `role` / `is_active`
  - tenant admin 只能修改自己 tenant 的 user

- `DELETE /api/auth/users/{user_id}`
  - 安全刪除（soft delete）：`is_active=false`

---

## 建議操作順序（外部上線版）

1. 內部維運：到「初始化」貼上 admin key
2. 建立/選擇 Tenant（必要時 bootstrap）
3. 建立第一個 tenant admin（role=admin）
4. 外部使用者：到「登入」選 Tenant + 帳密登入取得 API key
5. 日常管理：到「管理者」進行 tenant/users CRUD（仍需 admin key 或 tenant admin 身分）
