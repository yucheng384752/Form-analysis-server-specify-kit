# Fixed Demo Test Data List (Aug-Sep)

Last updated: 2026-02-23
Purpose: lock a stable dataset for demo smoke tests, especially TC04/TC05/TC09.

## 1) Dataset Scope
- Tenant: `demo-tenant` (or your fixed demo tenant)
- Data period:
  - In-range: `2025-08-01` to `2025-09-30`
  - Out-of-range control samples: `2025-07` and `2025-10`
- Record levels: include P1, P2, P3 mapping for query page validation

## 2) Fixed Product IDs
Use two-track ID strategy in demo docs/UI:
- Internal product ID (`product_id_internal`): system normalized key
- Customer product ID (`product_id_customer`): raw ID from customer data

Fixed list for demo:
- `AFD-202508-A01`
- `AFD-202508-A02`
- `AFD-202509-B01`
- `AFD-202509-B02`
- `AFD-202507-Z01` (out-of-range control)
- `AFD-202510-Z02` (out-of-range control)

## 3) Canonical Records (for smoke)

| Row | product_id_customer | product_id_internal | level | record_date | Expected in TC09 |
|---|---|---|---|---|---|
| 1 | CUS-AUG-001 | AFD-202508-A01 | P1 | 2025-08-03 | Yes |
| 2 | CUS-AUG-001 | AFD-202508-A01 | P2 | 2025-08-03 | Yes |
| 3 | CUS-AUG-001 | AFD-202508-A01 | P3 | 2025-08-04 | Yes |
| 4 | CUS-AUG-002 | AFD-202508-A02 | P1 | 2025-08-18 | Yes |
| 5 | CUS-AUG-002 | AFD-202508-A02 | P2 | 2025-08-19 | Yes |
| 6 | CUS-SEP-001 | AFD-202509-B01 | P1 | 2025-09-02 | Yes |
| 7 | CUS-SEP-001 | AFD-202509-B01 | P3 | 2025-09-02 | Yes |
| 8 | CUS-SEP-002 | AFD-202509-B02 | P2 | 2025-09-21 | Yes |
| 9 | CUS-SEP-002 | AFD-202509-B02 | P3 | 2025-09-30 | Yes (boundary) |
| 10 | CUS-JUL-001 | AFD-202507-Z01 | P1 | 2025-07-29 | No |
| 11 | CUS-JUL-001 | AFD-202507-Z01 | P2 | 2025-07-31 | No |
| 12 | CUS-OCT-001 | AFD-202510-Z02 | P3 | 2025-10-01 | No |

## 4) Expected Result Baseline
- TC09 query range: `2025-08-01` ~ `2025-09-30` (inclusive)
- Expected included rows: 9
- Expected excluded rows: 3
- Boundary check:
  - `2025-09-30` must be included
  - `2025-10-01` must be excluded

## 5) How to Use in Smoke Test
- TC04: use `AFD-202508-A01` for single product query
- TC05: use `AFD-202508-A01,AFD-202508-A02,AFD-202509-B01,AFD-202509-B02` for multi-product query
- TC06/TC07: verify P1/P2/P3 cross-level rendering by `AFD-202508-A01`
- TC09: validate date-range count and boundary rows

## 6) Data Freeze Rules
- Do not rename fixed IDs after demo freeze.
- If customer changes raw product ID format, only update `product_id_customer`; keep `product_id_internal` stable.
- Any data change must bump version in this file (`v1`, `v2`, ...).

## 7) Version
- Current version: `v1`
- Owner: Demo QA / PM
- Change log:
  - `v1` (2026-02-23): Initial Aug-Sep fixed list for smoke tests
