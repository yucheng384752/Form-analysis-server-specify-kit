# Demo Smoke Test Plan

Last updated: 2026-02-23
Scope: demo branch `demo/20260223`
Reference dataset: `dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md` (version v1)

## 1. Test Objective
- Verify end-to-end core flow is usable in demo environment.
- Focus on availability and correctness of main workflow, not performance tuning.

## 2. Preconditions
- Use env file: `form-analysis-server/.env.demo`
- Services are started successfully (DB / backend / frontend)
- Demo tenant and users are available (at least one manager account)
- Test data exists (>= 5 rows, including different `product_id` and date distribution)
- If `AUTH_MODE=api_key`, valid `X-API-Key` is configured

## 3. Smoke Test Cases

| TC ID | Name | Steps | Expected Result |
|---|---|---|---|
| TC01 | Manager login success | Login with valid manager credentials | Redirect to app successfully, no auth error |
| TC02 | Login failure handling | Login with wrong password | Error message shown, user stays on login page |
| TC03 | Upload flow basic check | Upload one valid CSV/XLSX file | Upload accepted and record can be queried |
| TC04 | Analytical-Four single product query | Input one `product_id` in analytics page and run | Result cards/table render correctly |
| TC05 | Analytical-Four multi-product query + rate limit behavior | Input multiple `product_id` values and run continuous query | System returns data or controlled warning; no page crash |
| TC06 | Query page dynamic filter | Select p1/p2/p3 parameters and submit | Returned rows match selected parameters |
| TC07 | Query table field mapping | Check returned columns for p1/p2/p3 sections | Column labels and values are consistent with DB |
| TC08 | Manager permission workflow | Open manager page and execute allowed operations | Allowed actions succeed; unauthorized actions are blocked |
| TC09 | Date range query (Aug-Sep) | Query with date range `2025-08-01` to `2025-09-30` | Only records within range are returned (inclusive bounds) |
| TC10 | Resolve-input unmatched classification: invalid format | Call `/api/v2/analytics/artifacts/{key}/resolve-input` with malformed id (e.g. `abc`) | `match_diagnostics[pid].reason_code = invalid_format` |
| TC11 | Resolve-input unmatched classification: no trace | Call resolve-input with format-valid but non-traceable id | `match_diagnostics[pid].reason_code = no_trace` |
| TC12 | Resolve-input unmatched classification: artifact no data | Call resolve-input where trace exists but selected artifact has no hit | `match_diagnostics[pid].reason_code = artifact_no_data` |
| TC13 | Complaint-analysis all-unmatched fallback | Call `POST /api/v2/analytics/complaint-analysis` with all-unmatched product_ids | Return 200 with diagnostics-only payload (`analysis_scope_id=empty`, `snapshot.sample_count=0`, `report_payload={}`) and UI shows diagnostics-only notice |

## 3.1 Complaint-Mode Smoke Pack (P2-10)

| TC ID | Name | Steps | Expected Result |
|---|---|---|---|
| TC-P2-12-01 | Complaint full-hit run | In analytics page input only hit-able complaint `product_id` list, click `開始客訴分析` | UI shows summary/snapshot/report blocks; `resolved_count > 0`; no blocking error |
| TC-P2-12-02 | Complaint partial-hit run | Input mixed hit + unmatched ids, click `開始客訴分析` | Analysis still renders for matched scope; unmatched summary toast and diagnostics panel are visible |
| TC-P2-12-03 | Complaint all-unmatched run | Input only unmatched ids, click `開始客訴分析` | Diagnostics-only mode is shown; snapshot/report core values are empty/zero |
| TC-P2-12-04 | Mixed format normalization | Input same logical ids with `_` and `-` variants | Mapping/resolve result converges to same effective tokens where data exists |
| TC-P2-12-05 | Cross-artifact consistency | Repeat complaint run across views (`events/llm/rag/weighted`) | `scope_lock` remains yes and complaint scope is consistent |
| TC-P2-13-01 | Summary field validation | Verify `requested/resolved/unmatched`, trace counts, reason counts | Fields are present and internally consistent |
| TC-P2-13-02 | Diagnostics schema validation | Verify unmatched reason and mapping stage output | `reason_code/reason_message/matched_stage` are available per row |
| TC-P2-13-03 | Timing field validation | Verify `timing.resolve_ms/snapshot_ms/report_ms/total_ms` | All timing fields exist and are numeric |

## 4. Execution Record Template

Use this template for each test case:

```md
### TCxx - <test name>
- Preconditions:
- Steps:
  1.
  2.
  3.
- Expected:
- Actual:
- Result: Pass / Fail
- Evidence: screenshot path or log snippet
- Notes:
```

## 5. Go / No-Go Criteria
- Must pass: TC01, TC03, TC04, TC06, TC09
- No blocking error: 500 responses, blank page, broken auth flow
- Known issue is acceptable only with workaround documented in release note

## 6. Known Risk Notes
- Multi-product analytics can hit backend rate limit (`30 req/min`) if frontend sends too many requests in a short window.
- If this occurs, mark TC05 as conditional pass only when retry/backoff UX is understandable and system recovers.

## 7. Test Summary
- Test date:
- Tester:
- Version/commit:
- Total: Pass / Fail / Blocked
- Final decision: Go / No-Go
