# Demo Setup

## Status
- Branch created: `demo/20260223`
- Step 2 completed: demo env template created at `form-analysis-server/.env.demo`
- Step 3 completed: smoke test document created at `SMOKE_TEST_DEMO.md`
- Step 3 extension completed: fixed dataset spec added at `dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md`
- Step 4 completed: one-command demo scripts added (`scripts/start-demo.bat`, `scripts/stop-demo.bat`)
- Startup flow fixed: account bootstrap + verification added (`scripts/ensure-demo-users.ps1`)
- Step 5 executed: smoke test result captured at `SMOKE_TEST_DEMO_RESULT_20260223.md`
- Step 6 completed: freeze + handoff docs added (`dev-guides/DEMO_FREEZE_20260223.md`, `RELEASE_NOTE_DEMO_20260223.md`, `dev-guides/PROD_PRECHECK_FOR_AGENT.md`)

## Step 2: Demo Env Baseline

### Actual changes
- Added `form-analysis-server/.env.demo` as demo-only environment template.
- Assigned dedicated demo ports to avoid collision with existing local runtime:
  - `POSTGRES_PORT=18101`
  - `HOST_API_PORT=18102`
  - `FRONTEND_PORT=18103`
  - `PGADMIN_PORT=5150`
- Added analytics host path placeholders used by docker bind mounts:
  - `SEPTEMBER_V2_HOST_PATH`
  - `ANALYTICAL_FOUR_HOST_PATH`
- Added fixed demo bootstrap keys/identities:
  - `ADMIN_API_KEYS`
  - `DEMO_TENANT_CODE` / `DEMO_TENANT_NAME`
  - `DEMO_MANAGER_USERNAME` / `DEMO_MANAGER_PASSWORD`
  - `DEMO_USER_USERNAME` / `DEMO_USER_PASSWORD`

### What to fill before running demo
- Confirm host paths in `form-analysis-server/.env.demo`:
  - `SEPTEMBER_V2_HOST_PATH`
  - `ANALYTICAL_FOUR_HOST_PATH`
- Replace weak secrets for demo deployment:
  - `POSTGRES_PASSWORD`
  - `SECRET_KEY`
  - `ADMIN_API_KEYS`

### Expected result
- Demo stack can run in isolation from current dev ports.
- Frontend points to demo API (`VITE_API_URL=http://localhost:18102`).
- Analytics bind mounts resolve to host assets without backend code changes.

## Step 3: Smoke Test Baseline

### Added documents
- `SMOKE_TEST_DEMO.md`
- `dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md`

### Included test cases
- `TC01` manager login success
- `TC02` login failure handling
- `TC03` upload flow basic check
- `TC04` analytical-four single product query
- `TC05` multi-product query and rate-limit behavior
- `TC06` query page dynamic filter
- `TC07` query table field mapping
- `TC08` manager permission workflow
- `TC09` date range query `2025-08-01` to `2025-09-30` (inclusive)

## Step 4: One-Command Demo Runtime

### Added scripts
- Start demo: `scripts/start-demo.bat`
- Stop demo: `scripts/stop-demo.bat`
- Ensure fixed users: `scripts/ensure-demo-users.ps1`

### Run commands
```bat
scripts\start-demo.bat
scripts\stop-demo.bat
```

### Expected result
- Start script launches compose using `--env-file .env.demo`
- Startup automatically ensures one manager + one user account in demo tenant
- Account verification is executed during startup and fails fast on mismatch
- Stop script cleanly shuts down demo containers

## Step 5: Smoke Test Execution

### Result file
- `SMOKE_TEST_DEMO_RESULT_20260223.md`

### Current outcome
- PASS: TC01, TC02, TC03, TC04, TC05, TC06, TC07, TC08, TC09
- Note: TC09 previously failed due to production_date between filtering logic in dynamic query flow; fixed and re-verified on 2026-02-23.

## Current verification snapshot
- Tenant `demo` exists
- User `demo_manager` exists with role `manager`
- User `demo_user` exists with role `user`

## Step 6: Demo Freeze and Handoff

### Entry criteria
- Smoke tests pass (TC01-TC09).
- Fixed demo accounts verified (demo_manager, demo_user).
- Demo env uses isolated ports via .env.demo and can start with one command.

### Actions
- Freeze demo dataset and record import job IDs used for validation.
- Freeze docs snapshot (README_DEMO.md, SMOKE_TEST_DEMO.md, SMOKE_TEST_DEMO_RESULT_20260223.md, dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md).
- Create release note for known limitations and operational boundaries (rate limit, supported query patterns).

### Expected result
- A reproducible demo package can be started and validated by another operator without backend code changes.

---

# For AI Agents & Developers

> 以下章節專為 AI 代理與開發者提供快速上手資訊（2026-03-09 新增）

## 快速啟動指令

### Demo 環境（給使用者/展示）
```powershell
cd scripts
.\start-demo.bat
```
- 前端：http://127.0.0.1:18103
- API：http://127.0.0.1:18102
- DB Port：18101

### Dev 環境（給開發者）
```powershell
cd scripts
.\start-dev.bat
```
- 前端：http://127.0.0.1:18003
- API：http://127.0.0.1:18002
- DB Port：18001

## 環境分離架構

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Desktop                            │
├─────────────────────────────┬───────────────────────────────┤
│     Demo Environment        │      Dev Environment          │
│     -p form-analysis-demo   │      -p form-analysis-dev     │
├─────────────────────────────┼───────────────────────────────┤
│  demo_form_analysis_db      │  form_analysis_db             │
│  (Port 18101)               │  (Port 18001)                 │
├─────────────────────────────┼───────────────────────────────┤
│  demo_form_analysis_api     │  form_analysis_api            │
│  (Port 18102)               │  (Port 18002)                 │
├─────────────────────────────┼───────────────────────────────┤
│  demo_form_analysis_frontend│  form_analysis_frontend       │
│  (Port 18103)               │  (Port 18003)                 │
├─────────────────────────────┼───────────────────────────────┤
│  Volume: postgres_demo_data │  Volume: postgres_data        │
└─────────────────────────────┴───────────────────────────────┘
```

## 重要檔案位置

| 類別 | 檔案路徑 |
|------|----------|
| Demo Compose | `form-analysis-server/docker-compose.demo.yml` |
| Dev Compose | `form-analysis-server/docker-compose.yml` |
| Demo 環境變數 | `form-analysis-server/.env.demo` |
| Dev 環境變數 | `form-analysis-server/.env.dev` |
| 啟動腳本 | `scripts/start-demo.bat`, `scripts/start-dev.bat` |
| 腳本清單 | `scripts/SCRIPTS_INVENTORY.md` |

## 預設帳號

### Demo 環境
| 角色 | 帳號 | 密碼 |
|------|------|------|
| Manager | demo_manager | demoMgr123 |
| User | demo_user | demoUsr123 |

### Dev 環境
| 角色 | 帳號 | 密碼 |
|------|------|------|
| Manager | dev_manager | devMgr123 |
| User | dev_user | devUsr123 |

## 常見操作

### 重建映像（強制）
```powershell
cd scripts
.\build-demo-images.bat   # Demo
# 或
docker-compose -f form-analysis-server/docker-compose.yml build --no-cache  # Dev
```

### 查看容器狀態
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 查看日誌
```powershell
docker logs demo_form_analysis_api -f   # Demo API
docker logs form_analysis_api -f        # Dev API
```

### 停止環境
```powershell
cd scripts
.\stop-demo.bat   # Demo
.\stop-system.bat # Dev
```

## AI Agent 開發注意事項

1. **IPv4 Only**: 所有 URL 使用 `127.0.0.1` 而非 `localhost`（避免 IPv6 問題）
2. **環境隔離**: Demo 和 Dev 使用不同的 Docker project name，互不影響
3. **資料庫分離**: 兩套環境使用獨立的 PostgreSQL volume
4. **Port 規則**: Demo 181xx, Dev 180xx
5. **PDF 服務**: 需設定 `PDF_SERVER_URL` 環境變數才能使用 PDF 轉檔功能

## 相關文件

- [環境分離操作指南](dev-guides/ENV_SEPARATION_OPERATIONS_GUIDE.md)
- [雙環境啟動檢查清單](dev-guides/DUAL_ENV_STARTUP_CHECKLIST.md)
- [腳本清單](scripts/SCRIPTS_INVENTORY.md)
- [Smoke Test 文件](SMOKE_TEST_DEMO.md)
