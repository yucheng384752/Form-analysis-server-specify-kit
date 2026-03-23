# test-edit-api.ps1
# 測試 L3-3 Inline Edit & Audit

$baseUrl = "http://localhost:18002"

# 1. Get Tenant
Write-Host "1. Getting Tenants..."
try {
    $tenants = Invoke-RestMethod -Uri "$baseUrl/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        Write-Host "[FAIL] No tenants found. Cannot proceed."
        exit 1
    }
    $tenantId = $tenants[0].id
    Write-Host "   Using Tenant ID: $tenantId"
} catch {
    Write-Host "[FAIL] Failed to get tenants: $($_.Exception.Message)"
    exit 1
}

# 2. Init Reasons
Write-Host "`n2. Initializing Edit Reasons..."
try {
    $initResp = Invoke-RestMethod -Uri "$baseUrl/api/edit/reasons/init" -Method Post -Headers @{ "X-Tenant-Id" = $tenantId } -ContentType "application/json" -Body (@{ tenant_id = $tenantId } | ConvertTo-Json)
} catch {
    Write-Host "[FAIL] Failed to init edit reasons: $($_.Exception.Message)"
    exit 1
}

# 3. List Reasons
Write-Host "`n3. Listing Edit Reasons..."
try {
    $reasons = Invoke-RestMethod -Uri "$baseUrl/api/edit/reasons?tenant_id=$tenantId" -Method Get -Headers @{ "X-Tenant-Id" = $tenantId }
    $reasons = @($reasons)
} catch {
    Write-Host "[FAIL] Failed to list edit reasons: $($_.Exception.Message)"
    exit 1
}

Write-Host "   Found $($reasons.Count) reasons."
if (-not $reasons -or $reasons.Count -eq 0) {
    Write-Host "[FAIL] No edit reasons found after init. Cannot proceed." 
    exit 1
}

$reasonId = $reasons[0].id
Write-Host "   Using Reason ID: $reasonId ($($reasons[0].reason_code))"

# 4. Find a P1 Record
Write-Host "`n4. Finding a P1 Record..."
try {
    $searchResult = Invoke-RestMethod -Uri "$baseUrl/api/v2/query/advanced" -Method Post -Headers @{ "X-Tenant-Id" = $tenantId } -ContentType "application/json" -Body (@{ page = 1; page_size = 1 } | ConvertTo-Json)
} catch {
    Write-Host "[FAIL] Advanced search failed: $($_.Exception.Message)"
    exit 1
}

if ($searchResult.results.Count -eq 0) {
    Write-Host "[FAIL] No records found."
    exit 1
}

$traceKey = $searchResult.results[0].trace_key
# Get detail to find P1 ID
try {
    $detail = Invoke-RestMethod -Uri "$baseUrl/api/v2/query/trace/$traceKey" -Method Get -Headers @{ "X-Tenant-Id" = $tenantId }
} catch {
    Write-Host "[FAIL] Trace detail failed: $($_.Exception.Message)"
    exit 1
}

if (-not $detail.p1) {
    Write-Host "[FAIL] No P1 record in this trace."
    exit 1
}

$p1Id = $detail.p1.id
$oldMarker = $null
try { $oldMarker = $detail.p1.extras.test_marker } catch { $oldMarker = $null }
Write-Host "   Target P1 ID: $p1Id"
Write-Host "   Current test_marker: $oldMarker"

# 5. Update Record
Write-Host "`n5. Updating Record..."
$ts = Get-Date -Format "yyyyMMddHHmmss"
$newMarker = "edit-test-$ts"
$updateUrl = "$baseUrl/api/edit/records/P1/$p1Id"
try {
    $updateBody = @{
        request   = @{
            updates     = @{ test_marker = $newMarker }
            reason_id   = $reasonId
            reason_text = "Automated Test Update"
        }
        tenant_id = $tenantId
    } | ConvertTo-Json -Depth 6

    $updatedRecord = Invoke-RestMethod -Uri $updateUrl -Method Patch -Headers @{ "X-Tenant-Id" = $tenantId } -ContentType "application/json" -Body $updateBody
    $updatedMarker = $null
    try { $updatedMarker = $updatedRecord.extras.test_marker } catch { $updatedMarker = $null }
    if ($updatedMarker -eq $newMarker) {
        Write-Host "   [OK] test_marker updated to $newMarker"
    } else {
        Write-Host "   [FAIL] test_marker mismatch: $updatedMarker"
        exit 1
    }
} catch {
    Write-Host "   [FAIL] Update request failed: $($_.Exception.Message)"
    exit 1
}

# 6. Verify Persistence (Get Detail Again)
Write-Host "`n6. Verifying Persistence..."
try {
    $detail2 = Invoke-RestMethod -Uri "$baseUrl/api/v2/query/trace/$traceKey" -Method Get -Headers @{ "X-Tenant-Id" = $tenantId }
} catch {
    Write-Host "   [FAIL] Persistence check request failed: $($_.Exception.Message)"
    exit 1
}
$persistedMarker = $null
try { $persistedMarker = $detail2.p1.extras.test_marker } catch { $persistedMarker = $null }

if ($persistedMarker -eq $newMarker) {
    Write-Host "   [OK] Persistence verified."
} else {
    Write-Host "   [FAIL] Persistence check failed. Got $persistedMarker"
    exit 1
}

Write-Host "`n[PASS] Edit API test completed." -ForegroundColor Green
exit 0
