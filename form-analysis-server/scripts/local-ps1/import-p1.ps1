param(
    [string]$ApiBase = "http://localhost:18002",
    [string]$P1File = "C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv"
)

Write-Host "Importing P1 data..." -ForegroundColor Yellow

$uri = "$ApiBase/api/v2/import/jobs"

# Get Tenant (required for /api/* endpoints)
Write-Host "Getting Tenant..." -ForegroundColor Yellow
try {
    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        throw "No tenants found"
    }
    $tenantId = $tenants[0].id
    $headers = @{ "X-Tenant-Id" = "$tenantId" }
    Write-Host "Using Tenant ID: $tenantId" -ForegroundColor Gray
} catch {
    Write-Host "Error: Failed to get tenant: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Create multipart form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"table_code`"$LF",
    "P1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"files`"; filename=`"P1_2507173_02.csv`"",
    "Content-Type: text/csv$LF",
    [System.IO.File]::ReadAllText($P1File),
    "--$boundary--$LF"
)

$body = $bodyLines -join $LF

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body -ContentType "multipart/form-data; boundary=$boundary"
    Write-Host "Job created: $($response.id)" -ForegroundColor Green
    Write-Host $($response | ConvertTo-Json)
    
    # Wait for processing
    $jobId = $response.id
    Write-Host "Waiting for processing..." -NoNewline
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
        $job = Invoke-RestMethod -Uri "http://localhost:18002/api/v2/import/jobs/$jobId" -Headers $headers
        $status = ($job.status | ForEach-Object { "$_" }).ToUpperInvariant()
        if ($status -eq "COMPLETED" -or $status -eq "FAILED") {
            Write-Host ""
            Write-Host "Status: $($job.status)" -ForegroundColor $(if ($status -eq "COMPLETED") { "Green" } else { "Red" })
            Write-Host "Total rows: $($job.total_rows)"
            Write-Host "Valid rows: $($job.valid_rows)"
            Write-Host "Error rows: $($job.error_rows)"
            break
        }
    }
}
catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.Exception.Response
}
