# Step 6 Freeze Snapshot (2026-02-23)

目的：固定 demo 可重現版本，供交接與展示使用。

## 1) Freeze Date / Scope
- Freeze date: 2026-02-23
- Scope: Demo environment + smoke test baseline + fixed dataset spec

## 2) Runtime Baseline
- Env file: `form-analysis-server/.env.demo`
- Start script: `scripts/start-demo.bat`
- Stop script: `scripts/stop-demo.bat`
- Account bootstrap: `scripts/ensure-demo-users.ps1`

## 3) Fixed Accounts
- Tenant: `demo`
- Manager: `demo_manager`
- User: `demo_user`

## 4) Frozen Dataset / Import Jobs
Data source (user provided):
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv`
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P2_2507173_02.csv`
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv`

Normalized files used:
- `test-data/demo-normalized/P1_2507173_02_norm.csv`
- `test-data/demo-normalized/P2_2507173_02_norm.csv`

Import jobs:
- P1: `0dc464b6-13f1-4def-99e4-697de1898bf6`
- P2: `cf1a135a-53fb-445a-90aa-a6d4886ec85f`
- P3: `c0a2b377-14a9-4574-bdef-37ddff7207b6`

## 5) Frozen Documents
- `README_DEMO.md`
- `SMOKE_TEST_DEMO.md`
- `SMOKE_TEST_DEMO_RESULT_20260223.md`
- `dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md`
- `dev-guides/PROD_PRECHECK_FOR_AGENT.md`

## 6) Smoke Baseline
- PASS: `TC01~TC09`
- Key fix included: date-range strict filtering for dynamic query flow (`production_date between`)

## 7) Change Control
- Any dataset/schema/query behavior change after this point must:
  1. update this freeze file version/date,
  2. re-run smoke tests,
  3. update smoke result report.
