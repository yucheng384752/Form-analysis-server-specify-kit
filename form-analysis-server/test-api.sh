#!/usr/bin/env bash

# v2-only smoke test (import jobs)
# - create job (valid P1)
# - poll until READY/FAILED
# - commit if READY
# - create job (invalid P1) and fetch errors

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:18002}"
TENANT_ID="${TENANT_ID:-}"

NC="\033[0m"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"

print_test() { echo -e "${YELLOW}[TEST]${NC} $*"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
print_err() { echo -e "${RED}[ERR]${NC} $*"; }

json_pretty() {
    if command -v jq >/dev/null 2>&1; then
        jq .
    else
        cat
    fi
}

resolve_tenant_id() {
    if [ -n "${TENANT_ID}" ]; then
        echo "${TENANT_ID}"
        return 0
    fi
    # Take the first tenant from /api/tenants
    curl -s "${API_BASE}/api/tenants" | grep -o '"tenant_id"\s*:\s*"[^"]*"' | head -n 1 | cut -d'"' -f4
}

poll_job_status() {
    local id="$1"
    local max_tries="${2:-60}"
    local i=0
    while [ $i -lt $max_tries ]; do
        local resp
        resp=$(curl -s -H "X-Tenant-Id: ${TENANT_ID}" "${API_BASE}/api/v2/import/jobs/${id}" || true)
        local status
        status=$(echo "$resp" | grep -o '"status"\s*:\s*"[^"]*"' | head -n 1 | cut -d'"' -f4)
        if [ -n "${status}" ]; then
            if [ "${status}" = "READY" ] || [ "${status}" = "FAILED" ] || [ "${status}" = "COMPLETED" ] || [ "${status}" = "CANCELLED" ]; then
                echo "${status}"
                return 0
            fi
        fi
        sleep 1
        i=$((i+1))
    done
    echo "TIMEOUT"
    return 0
}

create_job_p1() {
    local csv_path="$1"
    local filename="$2"
    curl -s -X POST \
        -H "X-Tenant-Id: ${TENANT_ID}" \
        -F "table_code=P1" \
        -F "allow_duplicate=false" \
        -F "files=@${csv_path};type=text/csv;filename=${filename}" \
        "${API_BASE}/api/v2/import/jobs"
}

TENANT_ID="$(resolve_tenant_id)"
if [ -z "${TENANT_ID}" ]; then
    print_err "TENANT_ID is empty; set TENANT_ID env or create tenant first"
    exit 1
fi

echo "API_BASE=${API_BASE}"
echo "TENANT_ID=${TENANT_ID}"

print_test "1. prepare temp csv"
VALID_CSV=$(mktemp --suffix=.csv)
cat << 'EOF' > "${VALID_CSV}"
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
1234567_01,測試產品B,50,2024-01-16
EOF

ERROR_CSV=$(mktemp --suffix=.csv)
cat << 'EOF' > "${ERROR_CSV}"
lot_no,product_name,quantity,production_date
1234567_01,,50,2024-01-16
1234567_01,測試產品C,-75,2024-01-17
EOF
print_ok "temp csv ready"

print_test "2. create job (valid)"
CREATE_JOB_RESP=$(create_job_p1 "${VALID_CSV}" "P1_1234567_01.csv")
echo "${CREATE_JOB_RESP}" | json_pretty

JOB_ID=$(echo "${CREATE_JOB_RESP}" | grep -o '"id"\s*:\s*"[^"]*"' | head -n 1 | cut -d'"' -f4)
if [ -z "${JOB_ID}" ]; then
    print_err "cannot parse job id"
    rm -f "${VALID_CSV}" "${ERROR_CSV}"
    exit 1
fi

print_test "3. poll job"
JOB_STATUS=$(poll_job_status "${JOB_ID}" 90)
echo "job status: ${JOB_STATUS}"

if [ "${JOB_STATUS}" = "READY" ]; then
    print_test "4. commit job"
    COMMIT_RESP=$(curl -s -X POST -H "X-Tenant-Id: ${TENANT_ID}" "${API_BASE}/api/v2/import/jobs/${JOB_ID}/commit")
    echo "${COMMIT_RESP}" | json_pretty
    print_ok "commit request sent"
else
    echo -e "${YELLOW}[SKIP]${NC} job not READY; skip commit"
fi

print_test "5. create job (invalid) and fetch errors"
ERR_JOB_RESP=$(create_job_p1 "${ERROR_CSV}" "P1_1234567_01_error.csv")
echo "${ERR_JOB_RESP}" | json_pretty
ERR_JOB_ID=$(echo "${ERR_JOB_RESP}" | grep -o '"id"\s*:\s*"[^"]*"' | head -n 1 | cut -d'"' -f4)

if [ -n "${ERR_JOB_ID}" ]; then
    ERR_STATUS=$(poll_job_status "${ERR_JOB_ID}" 90)
    echo "error job status: ${ERR_STATUS}"
    curl -s -H "X-Tenant-Id: ${TENANT_ID}" "${API_BASE}/api/v2/import/jobs/${ERR_JOB_ID}/errors" | json_pretty || true
else
    echo -e "${YELLOW}[SKIP]${NC} cannot parse error job id"
fi

rm -f "${VALID_CSV}" "${ERROR_CSV}"
print_ok "done"