# Smoke Test Demo Result (Step 5)

Date: 2026-02-23
Branch: `demo/20260223`
Environment: `form-analysis-server/.env.demo`
Executor: Codex

## 1. Runtime Health Snapshot
- `backend`: healthy (`http://localhost:18102`)
- `frontend`: healthy (`http://localhost:18103`)
- `db`: healthy (`localhost:18101`)

## 2. Account Baseline Verification
- Tenant exists: `demo` (`Demo Tenant`)
- Manager exists: `demo_manager` (role=`manager`, active=true)
- User exists: `demo_user` (role=`user`, active=true)

## 3. Test Data Used (User Provided + Normalized)
Original user files:
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv`
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P2_2507173_02.csv`
- `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv`

Normalized copies used for re-import:
- `test-data/demo-normalized/P1_2507173_02_norm.csv`
- `test-data/demo-normalized/P2_2507173_02_norm.csv`

Re-import jobs (normalized run):
- P1: `0dc464b6-13f1-4def-99e4-697de1898bf6` (`COMPLETED`, `error_count=0`, `total_rows=1`)
- P2: `cf1a135a-53fb-445a-90aa-a6d4886ec85f` (`COMPLETED`, `error_count=0`, `total_rows=20`)
- P3: `c0a2b377-14a9-4574-bdef-37ddff7207b6` (`COMPLETED`, `error_count=0`, `total_rows=4`)

## 4. Test Case Results

| TC | Result | Evidence Summary |
|---|---|---|
| TC01 Manager login success | PASS | `POST /api/auth/login` with `demo_manager / DemoManager123!` returned 200 + api_key | **need enter tenant code**
| TC02 Login failure handling | PASS | same endpoint with wrong password returned 401 |
| TC03 Upload flow basic check | PASS | `POST /api/v2/import/jobs` works; re-import jobs completed |
| TC04 Analytical-Four single product query | PASS | endpoint reachable and returns stable JSON |
| TC05 Multi-product query + rate limit behavior | PASS | multi-id call returned normal response / no crash |
| TC06 Query page dynamic filter | PASS | `POST /api/v2/query/records/dynamic` works in demo env |
| TC07 Query table field mapping | PASS | `lot_no=2507173_02` query returns P1/P2/P3 records for table rendering verification |
| TC08 Manager permission workflow | PASS | manager key can list users; `demo_user` key gets 403 on manager-only endpoint |
| TC09 Date range query (Aug-Sep) | PASS | `between 2025-08-01~2025-09-30` now excludes out-of-range/null-date rows (P1=0, P2=0, P3=1) |
| TC10 Resolve-input unmatched classification: invalid format | PASS | `serialized_events + product_id=abc` => `reason_code=invalid_format` |
| TC11 Resolve-input unmatched classification: no trace | PASS | `serialized_events + product_id=20250101_P99_999-9_999` => `reason_code=no_trace` |
| TC12 Resolve-input unmatched classification: artifact no data | PASS | `llm_reports + product_id=20250909_P23_238-4_301` => `reason_code=artifact_no_data` |
| TC13 Complaint-analysis all-unmatched fallback | PASS | `POST /api/v2/analytics/complaint-analysis` with unmatched ids returns diagnostics-only (`analysis_scope_id=empty`, `snapshot.sample_count=0`, `report_payload={}`); frontend shows diagnostics-only notice |

## 5. Post-Fix Verification
- Backend regression tests:
  - `test_query_dynamic_allowlist.py`: PASS
  - `test_query_dynamic_date_range_strict.py` (new): PASS
- Demo API spot-check:
  - P1 date-range query: `total_count=0`
  - P2 date-range query: `total_count=0`
  - P3 date-range query: `total_count=1`, `production_date=2025-09-02`

## 6. Conclusion
- Date-range logic defect has been fixed.
- Step 5 smoke tests are now fully passable with the current demo dataset.

## 7. Regression Rerun (2026-02-25)
- Scope: dynamic query blocking fixes (`data_type` optional + incompatible field combo returns 400)
- Executor: Codex

### API Regression
- `POST /api/v2/query/records/dynamic` without `data_type`: PASS (`200`)
- `POST /api/v2/query/records/dynamic` with `data_type=P1` + `winder_number`: PASS (`400`, unsupported field)

### Smoke Query TC Rerun
- TC04 (`POST /api/v2/analytics/analyze`, single product id): PASS (`200`)
- TC06 (dynamic filter, `data_type=P3`, `machine_no contains P24`): PASS (`200`, `total_count=1`)
- TC07 (lot mapping, `lot_no eq 2507173_02`): PASS (`200`, returned `P1/P2/P3`)
- TC09 (date range `2025-08-01` ~ `2025-09-30`): PASS (`200`, `total_count=1`, P3 dated `2025-09-02`)

## 8. Unmatched Classification Rerun (2026-03-05)
- Scope: `resolve-input` unmatched reason coverage (`invalid_format` / `no_trace` / `artifact_no_data`)
- Executor: Codex

### API Verification
- TC10 (`serialized_events`, `product_id=abc`): PASS
  - `unmatched=true`
  - `match_diagnostics["abc"].reason_code = invalid_format`
- TC11 (`serialized_events`, `product_id=20250101_P99_999-9_999`): PASS
  - `unmatched=true`
  - `match_diagnostics["20250101_P99_999-9_999"].reason_code = no_trace`
- TC12 (`llm_reports`, `product_id=20250909_P23_238-4_301`): PASS
  - `unmatched=true`
  - `match_diagnostics["20250909_P23_238-4_301"].reason_code = artifact_no_data`
- TC13 (`complaint-analysis`, all unmatched IDs): PASS
  - `analysis_scope_id = empty`
  - `scope_tokens_count = 0`
  - `snapshot.sample_count = 0`
  - `report_payload = {}`

## 9. Complaint-Mode Smoke Pack Result (P2-10)
- Scope: complaint-first flow (`product_id` input + `開始客訴分析`)
- Executor: Codex
- Date: 2026-03-08

| TC | Result | Evidence Summary |
|---|---|---|
| TC-P2-12-01 Complaint full-hit run | PASS | `test_v2_analytics_complaint_analysis_ok` passed (`resolved_count=1`, snapshot/report payload returned) |
| TC-P2-12-02 Complaint partial-hit run | PASS | `test_v2_analytics_complaint_analysis_partial_hit_keeps_analysis_and_diagnostics` passed (`requested=2`, `resolved=1`, `unmatched=1`, analysis still returned) |
| TC-P2-12-03 Complaint all-unmatched run | PASS | `test_v2_analytics_complaint_analysis_all_unmatched_returns_diagnostics_only` passed (`analysis_scope_id=empty`, `snapshot.sample_count=0`, `report_payload={}`) |
| TC-P2-12-04 Mixed format normalization | PASS | `test_v2_analytics_artifacts_resolve_input_normalized_hit_fields` passed (`normalized_inputs` and `matched_by` contain normalized token) |
| TC-P2-12-05 Cross-artifact consistency | PASS | `test_v2_analytics_complaint_analysis_ok` passed (`consistency.snapshot_scope_locked=true`, `report_scope_locked=true`) |
| TC-P2-13-01 Summary field validation | PASS | complaint-analysis tests assert `requested/resolved/unmatched` counts and scope counts |
| TC-P2-13-02 Diagnostics schema validation | PASS | complaint-analysis tests assert `mapping.*.matched_stage`, `reason_code`, `reason_message` (including `matched_trace_lot` stage) |
| TC-P2-13-03 Timing field validation | PASS | complaint-analysis tests assert `timing.resolve_ms/snapshot_ms/report_ms/total_ms` are numeric |

### Complaint-Mode Validation Checklist
- [x] `requested/resolved/unmatched` counts are coherent
- [x] `matched_stage` values include expected categories (`matched_direct/matched_trace/matched_trace_lot/unmatched`)
- [x] all-unmatched flow shows diagnostics-only mode
- [x] timing fields are present and numeric
- [x] no blocking 500/blank-page behavior

### Execution Evidence
- Backend API suite: `python -m pytest -q form-analysis-server/backend/tests/api/test_analytics_artifacts_endpoint.py` => `14 passed`
- Frontend regression suite: `npm run test -- --run` => `26 passed, 1 skipped`

## 10. P1-6 Backfill Audit Rerun (2026-03-08)
- Scope: `trace_lot_no` backfill status on demo DB (`localhost:18101`)
- Executor: Codex

### DB Audit / Backfill Evidence
- Command:
  - `python -m scripts.manual.audit_p2_trace_lot_no_backfill`
  - Result: `scanned=280 already_filled=280 fillable=0 missing_lot_no_raw=0 invalid_lot_no_raw_format=0 missing_winder_number=0 invalid_winder_number=0`
- Command:
  - `python -m scripts.manual.backfill_p2_trace_lot_no`
  - Result: `scanned=280 updated=0 skipped=0`
- Conclusion:
  - Demo DB historical P2 items are already fully backfilled for `trace_lot_no`; no pending fillable rows.

### API Regression Evidence
- `python -m pytest -q form-analysis-server/backend/tests/api/test_analytics_artifacts_endpoint.py -k "resolve_input_prefers_db_trace_lot_tokens or complaint_analysis_partial_hit_keeps_analysis_and_diagnostics"` => `2 passed`

## 11. TC-P1-12 Rerun (2026-03-08, demo DB)
- Scope: re-import `新侑特資料/P2` 7 files (140 rows) then verify `resolve-input` `resolved_count` uplift for complaint product_id set.
- Note: requested path `新侑特資料/P2/all` not found; executed with 7 files under `新侑特資料/P2`:
  - `P2_2507173_01.csv`
  - `P2_2507173_02.csv`
  - `P2_2507243_01.csv`
  - `P2_2507313_01.csv`
  - `P2_2507313_02.csv`
  - `P2_2508073_01.csv`
  - `P2_2508073_02.csv`

### Import Job Evidence (allow_duplicate=true)
- `26761b02-60c0-429f-803a-5bf3fc10f878` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `8b171133-5be6-4c32-bf7e-d6d5c900d867` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `bd2cd933-38e5-4eec-9c7e-fa87e1e90ce5` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `ef5850c5-a151-4bc9-9638-d24a523ac852` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `0fd56039-1e7a-46a9-a988-bad31ad4fac1` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `73553d27-7668-4dd8-a027-5eeecda617cf` (`COMPLETED`, `total_rows=20`, `error_count=0`)
- `4d15c9a0-e20f-406d-8e99-fc4c8c33a86f` (`COMPLETED`, `total_rows=20`, `error_count=0`)

### Resolve-Input Before/After
- Endpoint: `GET /api/v2/analytics/artifacts/serialized_events/resolve-input`
- Input: 20 complaint product_ids (same list as previous diagnostics run)
- Before import:
  - `requested_count=20`
  - `resolved_count=2`
  - `unmatched_count=19`
  - `trace_attempted_count=20`
  - `trace_resolved_count=1`
- After import:
  - `requested_count=20`
  - `resolved_count=2`
  - `unmatched_count=19`
  - `trace_attempted_count=20`
  - `trace_resolved_count=1`
  - `unmatched_reason_counts={"artifact_no_data":12,"no_trace":7}`

### Result
- `TC-P1-12`: **NO UPLIFT (still open)**
- Interpretation:
  - P2 re-import succeeded, but this complaint product_id set still does not produce additional artifact hits.
  - Likely cause is data-scope mismatch between complaint IDs / trace tokens and current `serialized_events` artifact content.

### Artifact-Token Audit + Guaranteed Set Rerun
- Script added:
  - `form-analysis-server/backend/scripts/manual/audit_artifact_token_intersection.py`
- Output snapshot:
  - `dev-guides/tc_p1_12_audit_result_20260308.json`
- Audit result (same 20 complaint IDs):
  - `recommended_product_ids_by_trace_intersection = []` (trace-token intersection is empty)
  - `guaranteed_product_ids_by_matches = ["20250909_P23_238-4_301"]`
- Rerun with guaranteed set (`20250909_P23_238-4_301`):
  - `requested_count=1`
  - `resolved_count=2`
  - `unmatched_count=0`
  - `trace_resolved_count=1`
- Conclusion:
  - A guaranteed hit subset exists for current artifact, but uplift for the original 20-ID complaint set remains not achieved.

## 12. Demo UI/API Smoke Rerun (2026-03-09)
- Scope: verify NG drill-down flow follows new rule:
  - click winder bar (example `winder_number=20`)
  - query via `POST /api/v2/query/records/dynamic`
  - NG definition fixed to `row_data.Striped Results == 0`
- Runtime:
  - `form_analysis_frontend`: healthy (`18103`)
  - `form_analysis_api`: healthy (`18102`)
  - `form_analysis_db`: healthy (`18101`)

### UI Reachability
- `GET http://localhost:18103/@vite/client` => `200` (frontend dev server active)

### API Smoke Evidence
- Login:
  - `POST /api/auth/login` (`demo_manager`) => `200`, tenant resolved.
- Dynamic query payload A (numeric zero):
  - `data_type=P2`
  - `filters=[{winder_number eq 20}, {row_data.Striped Results eq 0}]`
  - Result: `total_count=8`
- Dynamic query payload B (string zero):
  - same as A but `row_data.Striped Results eq "0"`
  - Result: `total_count=8` (same as numeric zero)
- Dynamic query payload C (non-NG control):
  - `data_type=P2`
  - `filters=[{winder_number eq 20}, {row_data.Striped Results eq 1}]`
  - Result: `total_count=6`

### Conclusion
- New NG rule works in demo API path:
  - `Striped Results = 0` is the active NG selector.
  - Numeric/string `0` behave consistently.
  - `winder_number` filter and NG filter can be combined deterministically.
