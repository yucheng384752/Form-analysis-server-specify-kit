# test-edit-api.ps1
# 測試 L3-3 Inline Edit & Audit

$baseUrl = "http://localhost:18002"

# 1. Get Tenant
Write-Host "1. Getting Tenants..."
$tenantsJson = curl.exe -s -X GET "$baseUrl/api/tenants"
try {
    $tenants = $tenantsJson | ConvertFrom-Json
    if ($tenants.Count -eq 0) {
        Write-Host "No tenants found. Cannot proceed."
        exit
    }
    $tenantId = $tenants[0].id
    Write-Host "   Using Tenant ID: $tenantId"
} catch {
    Write-Host "Failed to get tenants: $tenantsJson"
    exit
}

# 2. Init Reasons
Write-Host "`n2. Initializing Edit Reasons..."
$initBody = "{`"tenant_id`": `"$tenantId`"}"
$reasonsJson = curl.exe -s -X POST "$baseUrl/api/edit/reasons/init" -H "Content-Type: application/json" -d $initBody
# Write-Host "Raw Reasons: $reasonsJson"

# 3. List Reasons
Write-Host "`n3. Listing Edit Reasons..."
$reasonsListJson = curl.exe -s -X GET "$baseUrl/api/edit/reasons?tenant_id=$tenantId"
$reasons = $reasonsListJson | ConvertFrom-Json
Write-Host "   Found $($reasons.Count) reasons."
$reasonId = $reasons[0].id
Write-Host "   Using Reason ID: $reasonId ($($reasons[0].reason_code))"

# 4. Find a P1 Record
Write-Host "`n4. Finding a P1 Record..."
$searchBody = '{\"page\": 1, \"page_size\": 1}'
$searchJson = curl.exe -s -X POST "$baseUrl/api/v2/query/advanced" -H "Content-Type: application/json" -d $searchBody
$searchResult = $searchJson | ConvertFrom-Json

if ($searchResult.results.Count -eq 0) {
    Write-Host "No records found."
    exit
}

$traceKey = $searchResult.results[0].trace_key
# Get detail to find P1 ID
$detailJson = curl.exe -s -X GET "$baseUrl/api/v2/query/trace/$traceKey"
$detail = $detailJson | ConvertFrom-Json

if (-not $detail.p1) {
    Write-Host "No P1 record in this trace."
    exit
}

$p1Id = $detail.p1.id
$oldQty = $detail.p1.quantity
Write-Host "   Target P1 ID: $p1Id"
Write-Host "   Current Quantity: $oldQty"

# 5. Update Record
Write-Host "`n5. Updating Record..."
$newQty = 9999
$updateBody = "{
    `"tenant_id`": `"$tenantId`",
    `"updates`": { `"quantity`": $newQty },
    `"reason_id`": `"$reasonId`",
    `"reason_text`": `"Automated Test Update`"
}"
# Remove newlines for curl
$updateBody = $updateBody -replace "`r`n", "" -replace "`n", ""

$updateUrl = "$baseUrl/api/edit/records/P1/$p1Id"
$updateJson = curl.exe -s -X PATCH $updateUrl -H "Content-Type: application/json" -d $updateBody

try {
    $updatedRecord = $updateJson | ConvertFrom-Json
    if ($updatedRecord.quantity -eq $newQty) {
        Write-Host "   [OK] Quantity updated to $newQty"
    } else {
        Write-Host "   [FAIL] Quantity mismatch: $($updatedRecord.quantity)"
        Write-Host "   Response: $updateJson"
    }
} catch {
    Write-Host "Failed to parse update response: $updateJson"
}

# 6. Verify Persistence (Get Detail Again)
Write-Host "`n6. Verifying Persistence..."
$detailJson2 = curl.exe -s -X GET "$baseUrl/api/v2/query/trace/$traceKey"
$detail2 = $detailJson2 | ConvertFrom-Json
if ($detail2.p1.quantity -eq $newQty) {
    Write-Host "   [OK] Persistence verified."
} else {
    Write-Host "   [FAIL] Persistence check failed. Got $($detail2.p1.quantity)"
}
