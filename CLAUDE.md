# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Environments

Two isolated Docker environments run concurrently. **Never mix their ports.**

| | Demo | Dev |
|---|---|---|
| Ports | 181xx | 180xx |
| Docker project | `form-analysis-demo` | `form-analysis-dev` |
| Compose file | `docker-compose.demo.yml` | `docker-compose.yml` |
| Env file | `.env.demo` | `.env.dev` |
| Frontend | http://127.0.0.1:18103 | http://127.0.0.1:18003 |
| API | http://127.0.0.1:18102 | http://127.0.0.1:18002 |
| DB | 18101 | 18001 |

All URLs must use `127.0.0.1`, not `localhost` (IPv6 issue on Windows).

### Start / Stop

```powershell
# Dev (auto-creates .env.dev on first run, checks ports, smart build)
cd scripts && .\start-dev.bat
cd scripts && .\stop-dev.bat

# Dev with options
cd scripts && .\start-dev.bat --build       # Force rebuild images
cd scripts && .\start-dev.bat --reset-db    # Remove DB volume and start fresh
cd scripts && .\stop-dev.bat --reset-db     # Stop and remove DB volume

# Demo
cd scripts && .\start-demo.bat
cd scripts && .\stop-demo.bat

# Stop all environments at once
cd scripts && .\stop-system.bat
```

### Promote Dev code → Demo image

Run this whenever backend or frontend code changes and needs to appear in Demo:

```powershell
cd scripts && .\build-demo-images.bat
# then
.\start-demo.bat
```

`build-demo-images.bat` builds `form-analysis-backend:demo` and `form-analysis-frontend:demo` using the `production` Dockerfile target (code baked in, no hot reload). Dev uses the `development` target with source-code volume mounts.

---

## Common Commands

All commands below run from within the respective service directory.

### Backend (`form-analysis-server/backend/`)

```bash
# Run tests
pytest

# Run a single test file
pytest tests/path/to/test_file.py

# Run a single test
pytest tests/path/to/test_file.py::test_function_name

# Lint
ruff check app/

# Format
ruff format app/

# Type check
mypy app/

# Run dev server locally (outside Docker)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (`form-analysis-server/frontend/`)

```bash
npm run dev          # Vite dev server
npm run build        # Production build (tsc + vite)
npm run lint         # ESLint (0 warnings allowed)
npm run lint:fix     # Auto-fix lint issues
npm run type-check   # tsc --noEmit
npm run test         # Vitest
npm run format       # Prettier
```

### Docker (from repo root)

```bash
# Check running containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Tail API logs
docker logs demo_form_analysis_api -f
docker logs form_analysis_api -f

# Verify demo images exist
docker images | grep "form-analysis"
```

---

## Architecture

### Backend — FastAPI (Python 3.12, SQLAlchemy 2.0 async)

`form-analysis-server/backend/app/`

**Request lifecycle:**
1. `main.py` — registers all routers, CORS, auth middleware, and audit middleware
2. `core/middleware.py` — attaches `request.state.is_admin`, `auth_tenant_id`, `actor_user_id`, `actor_role` for every request
3. `api/deps.py` — `get_current_tenant()` resolves the active tenant from `request.state` (set by middleware) or falls back to the single/default tenant
4. Route handlers inject `Depends(get_current_tenant)` and `Depends(get_db)` for scoped DB sessions

**Auth model:**
- `X-API-Key` header → tenant-scoped user session (role: `user` or `manager`)
- `X-Admin-API-Key` header → admin break-glass access (bypasses tenant scoping)
- Login via `POST /api/auth/login` returns an `api_key` to use as `X-API-Key`
- `tenant_code` is required at login when multiple tenants exist; optional when only one exists

**Key API prefixes:**

| Prefix | Module |
|---|---|
| `/api/auth` | `routes_auth.py` |
| `/api/v2/import` | `routes_import_v2.py` |
| `/api/v2/query` | `routes_query_v2.py` |
| `/api/analytics` | `routes_analytics.py` |
| `/api/tenants` | `routes_tenants.py` |
| `/healthz` | `routes_health.py` |

**V2 Import Job flow** (non-blocking):
```
POST /api/v2/import/jobs          → creates job (PENDING)
  background task: parse + validate CSV/Excel
GET  /api/v2/import/jobs/{id}    → poll status (PARSING → READY | FAILED)
GET  /api/v2/import/jobs/{id}/errors → paginated validation errors
POST /api/v2/import/jobs/{id}/commit → write P1/P2/P3 records to DB
```

**Data model — production chain:**
- `p1_records` → Extrusion/forming
- `p2_records` + `p2_items` → Slitting
- `p3_records` + `p3_items` → Punch/separation
- Traceability queries join across all three via lot codes

**Multi-tenancy:** Every data table is scoped by `tenant_id`. The `tenant_users` table stores users per tenant with roles (`manager`, `user`). Admin key bypasses tenant scoping entirely.

### Frontend — React 18 + TypeScript + Vite

`form-analysis-server/frontend/src/`

**Pages → API mapping:**

| Page | Primary API |
|---|---|
| `RegisterPage.tsx` | `/api/auth/login`, tenant bootstrap |
| `UploadPage.tsx` | `/api/v2/import/jobs` (create → poll → commit) |
| `QueryPage.tsx` | `/api/v2/query` |
| `AnalyticsPage.tsx` | `/api/analytics`, Pareto chart |
| `AdminPage.tsx` | `/api/tenants`, `/api/auth` (user management) |
| `ManagerPage.tsx` | `/api/auth` (manager-scoped user ops) |

**Auth state** is stored in `localStorage` via `services/auth.ts` (API key) and `services/tenant.ts` (tenant ID). The `fetchWrapper.ts` automatically injects `X-API-Key` and `X-Tenant-Id` on every request.

**UI stack:** Radix UI headless components + shadcn/ui + Tailwind CSS. Component library lives in `components/ui/`.

**i18n:** `react-i18next`, locale files at `src/locales/zh-TW/` and `src/locales/en/`.

---

## Demo Accounts

Login via frontend requires filling the **「區域代碼」** field — it cannot be left blank when multiple tenants exist.

| Env | 區域代碼 | 帳號 | 密碼 |
|---|---|---|---|
| Demo | `demo` | `demo_manager` | `DemoManager123!` |
| Demo | `demo` | `demo_user` | `DemoUser123!` |

Demo accounts are bootstrapped by `scripts/ensure-demo-users.ps1`, which is called automatically by `start-demo.bat`.

---

## Key File Locations

| Purpose | Path |
|---|---|
| Backend entry point | `form-analysis-server/backend/app/main.py` |
| Settings (env vars) | `form-analysis-server/backend/app/core/config.py` |
| Auth middleware | `form-analysis-server/backend/app/core/middleware.py` |
| Route deps (tenant/db) | `form-analysis-server/backend/app/api/deps.py` |
| Analytics field mapping | `form-analysis-server/backend/app/config/analytics_field_mapping.py` |
| Frontend API client | `form-analysis-server/frontend/src/services/api.ts` |
| Fetch wrapper (auth inject) | `form-analysis-server/frontend/src/services/fetchWrapper.ts` |
| Demo env vars | `form-analysis-server/.env.demo` |
| Dev env vars | `form-analysis-server/.env.dev` |
| Scripts inventory | `scripts/SCRIPTS_INVENTORY.md` |
