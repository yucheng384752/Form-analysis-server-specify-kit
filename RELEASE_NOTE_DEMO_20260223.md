# Demo Release Note (Pilot Production)

Date: 2026-02-23
Target: internal demo / controlled enterprise pilot

## 1. Release Summary
- Demo environment is reproducible with one-command startup.
- Smoke test baseline `TC01~TC09` is passable on frozen dataset.
- Date-range filtering defect in dynamic query flow has been fixed and verified.

## 2. Included Fixes
- Dynamic query now enforces strict date-range filtering for `production_date between`.
- Out-of-range / null / unparseable production dates are excluded when date filter is active.

## 3. Operational Boundaries
- API rate limit exists: `Max 30 requests per minute`.
- Recommended usage for demo: batch product_id input and avoid burst requests.
- This release is a controlled pilot, not an unrestricted public production rollout.

## 4. Known Limitations
- Multi-product high-frequency querying can hit rate limit.
- Advanced query selectable fields are not yet fully dynamic for all table parameters.

## 5. Validation Reference
- Smoke cases: `SMOKE_TEST_DEMO.md`
- Smoke result: `SMOKE_TEST_DEMO_RESULT_20260223.md`
- Fixed dataset: `dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md`
- Freeze snapshot: `dev-guides/DEMO_FREEZE_20260223.md`
- Pre-prod checklist: `dev-guides/PROD_PRECHECK_FOR_AGENT.md`

## 6. Rollback Guideline (Minimal)
- Stop demo stack: `scripts/stop-demo.bat`
- Restore previous frozen env/data snapshot.
- Restart and re-run smoke baseline before reopening access.
