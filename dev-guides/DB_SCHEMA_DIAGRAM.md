# DB 架構圖（ERD）與資料流

> 目標：用一張圖快速理解「多租戶 tenant」如何貫穿整個 DB，以及各 API 主要讀寫哪些資料表。

## 1) ER Diagram（Mermaid）

```mermaid
erDiagram
  TENANTS {
    uuid id PK
    string name
    string code
    boolean is_active
    boolean is_default
  }

  TENANT_USERS {
    uuid id PK
    uuid tenant_id FK
    string username
    string password_hash
    string role
    boolean is_active
    datetime created_at
    datetime last_login_at
  }

  TENANT_API_KEYS {
    uuid id PK
    uuid tenant_id FK
    uuid user_id FK
    string key_hash
    string label
    boolean is_active
    datetime created_at
    datetime last_used_at
    datetime revoked_at
  }

  AUDIT_EVENTS {
    uuid id PK
    uuid tenant_id FK
    uuid actor_api_key_id FK
    string method
    string path
    int status_code
    string action
  }

  UPLOAD_JOBS {
    uuid id PK
    uuid process_id
    uuid tenant_id FK
    uuid actor_api_key_id FK
    string filename
    string status
    int total_rows
    int valid_rows
    int invalid_rows
    datetime created_at
  }

  UPLOAD_ERRORS {
    uuid id PK
    uuid job_id FK
    int row_index
    string field
    string error_code
    string message
    datetime created_at
  }

  PDF_UPLOADS {
    uuid process_id PK
    uuid tenant_id FK
    uuid actor_api_key_id FK
    string filename
    int file_size
    string storage_path
    datetime created_at
  }

  PDF_CONVERSION_JOBS {
    uuid id PK
    uuid process_id FK
    uuid tenant_id FK
    uuid actor_api_key_id FK
    string status
    int progress
    string external_job_id
    string output_path
    datetime created_at
  }

  TABLE_REGISTRY {
    uuid id PK
    string table_code
    string display_name
    datetime created_at
  }

  SCHEMA_VERSIONS {
    uuid id PK
    uuid table_id FK
    string schema_hash
    string header_fingerprint
    json schema_json
    datetime created_at
  }

  IMPORT_JOBS {
    uuid id PK
    uuid tenant_id FK
    uuid table_id FK
    uuid schema_version_id FK
    uuid actor_api_key_id FK
    string batch_id
    string status
    int progress
    int total_files
    int total_rows
    int error_count
    json error_summary
    datetime created_at
    datetime updated_at
  }

  IMPORT_FILES {
    uuid id PK
    uuid job_id FK
    uuid tenant_id FK
    uuid table_id FK
    string filename
    string file_hash
    string storage_path
    int file_size
    int row_count
    datetime created_at
  }

  STAGING_ROWS {
    uuid id PK
    uuid job_id FK
    uuid file_id FK
    int row_index
    json parsed_json
    json errors_json
    boolean is_valid
  }

  P1_RECORDS {
    uuid id PK
    uuid tenant_id FK
    string lot_no_raw
    bigint lot_no_norm
    uuid schema_version_id
    json extras
    datetime created_at
    datetime updated_at
  }

  P2_RECORDS {
    uuid id PK
    uuid tenant_id FK
    string lot_no_raw
    bigint lot_no_norm
    int winder_number
    uuid schema_version_id
    json extras
    datetime created_at
    datetime updated_at
  }

  P2_ITEMS_V2 {
    uuid id PK
    uuid tenant_id FK
    uuid p2_record_id FK
    int winder_number
    float sheet_width
    float thickness1
    float thickness2
    float thickness3
    float thickness4
    float thickness5
    float thickness6
    float thickness7
    int appearance
    int rough_edge
    int slitting_result
    json row_data
    datetime created_at
    datetime updated_at
  }

  P3_RECORDS {
    uuid id PK
    uuid tenant_id FK
    string lot_no_raw
    bigint lot_no_norm
    int production_date_yyyymmdd
    string machine_no
    string mold_no
    string product_id
    uuid schema_version_id
    json extras
    datetime created_at
    datetime updated_at
  }

  P3_ITEMS_V2 {
    uuid id PK
    uuid tenant_id FK
    uuid p3_record_id FK
    int row_no
    string product_id
    string lot_no
    date production_date
    string machine_no
    string mold_no
    int production_lot
    int source_winder
    string specification
    string bottom_tape_lot
    json row_data
    datetime created_at
    datetime updated_at
  }

  TENANTS ||--o{ TENANT_USERS : has
  TENANTS ||--o{ TENANT_API_KEYS : has
  TENANT_USERS ||--o{ TENANT_API_KEYS : owns

  TENANTS ||--o{ AUDIT_EVENTS : scopes
  TENANT_API_KEYS ||--o{ AUDIT_EVENTS : actor

  TENANTS ||--o{ UPLOAD_JOBS : scopes
  UPLOAD_JOBS ||--o{ UPLOAD_ERRORS : has
  TENANT_API_KEYS ||--o{ UPLOAD_JOBS : actor

  TENANTS ||--o{ PDF_UPLOADS : scopes
  TENANTS ||--o{ PDF_CONVERSION_JOBS : scopes
  PDF_UPLOADS ||--o{ PDF_CONVERSION_JOBS : spawns
  TENANT_API_KEYS ||--o{ PDF_UPLOADS : actor
  TENANT_API_KEYS ||--o{ PDF_CONVERSION_JOBS : actor

  TABLE_REGISTRY ||--o{ SCHEMA_VERSIONS : has

  TENANTS ||--o{ IMPORT_JOBS : scopes
  TABLE_REGISTRY ||--o{ IMPORT_JOBS : target
  SCHEMA_VERSIONS ||--o{ IMPORT_JOBS : schema
  IMPORT_JOBS ||--o{ IMPORT_FILES : has
  IMPORT_JOBS ||--o{ STAGING_ROWS : has
  IMPORT_FILES ||--o{ STAGING_ROWS : has

  TENANTS ||--o{ P1_RECORDS : owns
  TENANTS ||--o{ P2_RECORDS : owns
  TENANTS ||--o{ P3_RECORDS : owns

  P2_RECORDS ||--o{ P2_ITEMS_V2 : has
  P3_RECORDS ||--o{ P3_ITEMS_V2 : has
```

## 2) 資料流（API → DB）

- 認證/租戶
  - `/api/auth/login`：讀 `tenants`、`tenant_users`；寫 `tenant_api_keys`（並更新 `tenant_users.last_login_at`）
  - `/api/auth/users*`：CRUD `tenant_users`（本次新增：可改綁定 tenant，並撤銷 `tenant_api_keys`）
  - `/api/tenants*`：CRUD `tenants`

- 上傳/驗證
  - `/api/*upload*`：寫 `upload_jobs`、`upload_errors`；成功後會進入匯入流程（依版本可能寫入 `p1_records/p2_records/p3_records` 與 items）

- V2 匯入管線
  - `/api/v2/import/*`：
    - 控制面：`import_jobs / import_files / staging_rows`
    - schema 管理：`table_registry / schema_versions`
    - commit 後：寫入 `p1_records / p2_records / p2_items_v2 / p3_records / p3_items_v2`

- 查詢/追溯
  - `/api/v2/query/*`：主要讀 `p1_records / p2_records / p2_items_v2 / p3_records / p3_items_v2`（以及部分 legacy 表，若路由仍保留）

- 分析（資料分析頁）
  - `/api/v2/analytics/analyze`：目前回傳範例 JSON；未來預期會讀取上列查詢表，組合查詢結果後交給外部分析套件產生 JSON。

## 3) Multi-tenant 規則（重要）

- 大多數業務 API 都是 tenant-scoped：以 `X-Tenant-Id` 決定資料範圍。
- 若啟用 `AUTH_MODE=api_key`：一般情況 tenant 會綁定在 `X-API-Key`。
- 本次新增：當同時提供有效 `X-Admin-API-Key`（最高級 admin）時，可用 `X-Tenant-Id` 明確指定要查哪個 tenant（跨租戶切換）。
