# 總經理跨 tenant 彙總（MVP）—待開發設計稿

> 目標：維持「一區 = 一個 tenant」的資料隔離前提下，讓總經理（GM）能在同一頁面彙總多個場區（多 tenant）的統計/查詢結果。

---

## 1) 背景與現況限制

目前的 auth 模型核心是：

- `X-API-Key` 會解析到 `tenant_api_keys`，並在 middleware 把 `request.state.auth_tenant_id` 綁死成單一 tenant。
- 因此「同一個 token」天然無法跨 tenant 查詢。

要達成 GM 彙總，需要引入「同一個 token 擁有多 tenant 讀取權限」的機制，且後端必須能展開 allowed tenants 並只查那些 tenant。

---

## 2) MVP 的需求定義

### In-scope（MVP）

- GM 可以登入後看到：
  - 自己允許的 tenant 清單（多個）
  - 可選擇「全部 / 部分」tenant
  - 在同一頁面看到彙總統計（例如：筆數、時間區間、常見批號、各 data_type 筆數等）

### Out-of-scope（先不做）

- GM 在同一個頁面做「跨 tenant 明細逐筆編輯」
- 既有業務端點（/api/query/*、/api/import/*）全面改寫成多 tenant
- 以 SSO/OAuth2 取代現有 API key（保留未來擴充空間）

---

## 3) 授權模型（最小可行）

### 3.1 角色

- `tenant_users.role`（既有）：
  - `user`：一般使用者，只能操作單 tenant
  - `admin`：場區管理者，可管理該 tenant 使用者

- **新增（MVP）**：`org_users`（或 `global_users`）
  - `gm`：總經理/區域總管，可跨多 tenant 查詢（read-only）

> 註：MVP 建議把 GM 與 tenant_users 分開，避免把 tenant-scoped 權限模型硬扭成 multi-tenant。

### 3.2 權限範圍（scope）

GM token 需要攜帶：

- `allowed_tenant_ids: UUID[]`
- `capabilities: { summary:read, tenants:list }`（MVP 先寫死也可）

### 3.3 Token 類型

- **既有**：`tenant_api_keys`（單 tenant）
- **新增（MVP）**：`org_api_keys`（多 tenant）

middleware 流程：

1. 先用 `X-API-Key` 嘗試查 `tenant_api_keys`
2. 查不到再查 `org_api_keys`
3. 若命中 `org_api_keys`：
   - 不設定 `request.state.auth_tenant_id`
   - 改設定：
     - `request.state.allowed_tenant_ids`
     - `request.state.actor_role = "gm"`

---

## 4) 資料模型（MVP）

### 4.1 新增表

1) `org_users`
- `id` UUID PK
- `username` unique
- `password_hash`
- `role`（固定 gm / 或預留）
- `is_active`

2) `org_user_tenants`
- `org_user_id` FK -> org_users.id
- `tenant_id` FK -> tenants.id
- unique(org_user_id, tenant_id)

3) `org_api_keys`
- `id` UUID PK
- `org_user_id` FK -> org_users.id
- `key_hash`（同 tenant_api_keys：HMAC-SHA256(secret_key, raw_key)）
- `label`
- `is_active`
- `created_at/last_used_at/revoked_at`

> 也可以設計 `orgs`（公司/區域）再掛 org_users，但 MVP 可先省略 orgs。

---

## 5) API 端點形狀（MVP）

### 5.1 登入

- `POST /api/auth/login`（既有）：tenant user 登入 -> 發 tenant_api_key

- **新增**：`POST /api/org-auth/login`
  - Request:
    ```json
    { "username": "gm1", "password": "..." }
    ```
  - Response:
    ```json
    {
      "api_key": "<raw>",
      "api_key_header": "X-API-Key",
      "role": "gm",
      "allowed_tenants": [
        {"tenant_id":"...","tenant_code":"t1","tenant_name":"..."}
      ]
    }
    ```

### 5.2 GM 可用的 tenant 清單

- `GET /api/gm/tenants`
  - Auth: org_api_key only
  - Response: tenant list（同上 allowed_tenants 形狀）

### 5.3 彙總統計（第一階段）

- `POST /api/gm/summary/records/stats`
  - Auth: org_api_key only
  - Request:
    ```json
    {
      "tenant_ids": ["..."],
      "production_date_from": "2025-01-01",
      "production_date_to": "2025-12-31",
      "data_types": ["P1","P2","P3"]
    }
    ```
  - Response（示意）:
    ```json
    {
      "tenants": [
        {"tenant_id":"...","tenant_code":"t1","count":123,"by_type":{"P1":1,"P2":2,"P3":120}},
        {"tenant_id":"...","tenant_code":"t2","count":456,"by_type":{"P1":10,"P2":20,"P3":426}}
      ],
      "total": {"count":579,"by_type":{"P1":11,"P2":22,"P3":546}}
    }
    ```

> MVP 注意：後端必須把 request.tenant_ids 與 `allowed_tenant_ids` 做交集，避免越權。

---

## 6) 前端操作方式（MVP）

### 6.1 UI 流程

- 新增「GM Dashboard」頁籤/路由
- 登入區塊：username/password -> `POST /api/org-auth/login`
- 成功後：保存 api key 到瀏覽器（沿用既有保存方式/同 header）

### 6.2 Tenant 選擇

- 顯示 `GET /api/gm/tenants` 回傳的 allowed tenants
- 提供：
  - 全選 / 取消全選
  - 多選列表

### 6.3 查詢

- 由 Dashboard 呼叫 `POST /api/gm/summary/records/stats`
- 畫面顯示：
  - 每個 tenant 的統計卡片
  - total summary

### 6.4 與既有頁面共存策略

- GM Dashboard 使用 org_api_key（多 tenant），**不要**強行套用到既有 tenant-scoped API。
- 若 GM 要進入「某個特定 tenant 的明細頁」，前端要先選定 tenant，並在該頁對既有 API 加上 `X-Tenant-Id`（且後端需要允許 org_api_key + X-Tenant-Id 進入 tenant-scoped API；這可列為 Phase 2）。

---

## 7) 安全與稽核（MVP）

- `org_api_keys` 也要 best-effort 更新 last_used_at。
- audit event 需要能記錄 actor：
  - 新增欄位或擴充 metadata：`actor_kind=org|tenant`、`actor_org_user_id`。

---

## 8) Phase 拆解（建議）

### Phase 1（MVP）

- 新增 org_users/org_user_tenants/org_api_keys + migration
- 新增 `/api/org-auth/login`、`/api/gm/tenants`、`/api/gm/summary/records/stats`
- 前端新增 GM Dashboard 頁

### Phase 2（可選）

- 允許 org_api_key + `X-Tenant-Id` 進入部分 tenant-scoped API（只讀）
- 加入更完整的彙總查詢（lot suggestions、top products、時間序列）

---

## 9) 風險與替代方案

- 風險：把 org key 直接塞進既有 `/api/*` tenant middleware，容易引入越權洞。
  - 緩解：MVP 只開 `/api/gm/*`，所有查詢都強制 intersect allowed tenants。

- 替代方案：做「GM 端以 server-side fan-out 呼叫每個 tenant 的單 tenant 查詢」
  - 缺點：複雜、效能差、容易在授權/tenant header 上踩坑。

---

## 10) 驗收標準（MVP）

- GM 可以登入成功拿到 API key
- GM 可以看到 allowed tenants
- GM 可以選多個 tenants 並得到彙總統計
- 後端拒絕任何不在 allowed tenants 的 tenant_id
