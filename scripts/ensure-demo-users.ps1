param(
    [string]$EnvFile = "form-analysis-server/.env.demo"
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Default = ""
    )
    if (-not (Test-Path $Path)) { return $Default }
    $line = Get-Content -Encoding UTF8 -Path $Path |
        Where-Object { $_ -match "^\s*$Key\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $Default }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function Get-StatusCode {
    param($Exception)
    try { return [int]$Exception.Response.StatusCode.value__ } catch { return -1 }
}

function Wait-Backend {
    param([string]$HealthUrl)
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -Method Get -TimeoutSec 4
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $projectRoot $EnvFile }

$apiPort = Get-EnvValue -Path $envPath -Key "HOST_API_PORT" -Default "18102"
$adminHeader = Get-EnvValue -Path $envPath -Key "ADMIN_API_KEY_HEADER" -Default "X-Admin-API-Key"
$adminKeysRaw = Get-EnvValue -Path $envPath -Key "ADMIN_API_KEYS" -Default ""
$tenantCode = Get-EnvValue -Path $envPath -Key "DEMO_TENANT_CODE" -Default "demo"
$tenantName = Get-EnvValue -Path $envPath -Key "DEMO_TENANT_NAME" -Default "Demo Tenant"
$managerUsername = Get-EnvValue -Path $envPath -Key "DEMO_MANAGER_USERNAME" -Default "demo_manager"
$managerPassword = Get-EnvValue -Path $envPath -Key "DEMO_MANAGER_PASSWORD" -Default "DemoManager123!"
$userUsername = Get-EnvValue -Path $envPath -Key "DEMO_USER_USERNAME" -Default "demo_user"
$userPassword = Get-EnvValue -Path $envPath -Key "DEMO_USER_PASSWORD" -Default "DemoUser123!"

$adminKey = ($adminKeysRaw -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" } | Select-Object -First 1)
if (-not $adminKey) {
    throw "ADMIN_API_KEYS is not configured in $envPath"
}

$baseUrl = "http://127.0.0.1:$apiPort"
$headers = @{}
$headers[$adminHeader] = $adminKey

Write-Host "[ensure-demo-users] Waiting backend health..." -ForegroundColor Cyan
if (-not (Wait-Backend -HealthUrl "$baseUrl/healthz")) {
    throw "Backend health check timed out: $baseUrl/healthz"
}

Write-Host "[ensure-demo-users] Resolving tenant..." -ForegroundColor Cyan
$tenants = @()
try {
    $tenantsResp = Invoke-RestMethod -Uri "$baseUrl/api/tenants?include_inactive=true" -Method Get -Headers $headers -TimeoutSec 10
    if ($tenantsResp -is [System.Array]) { $tenants = @($tenantsResp) }
    elseif ($null -ne $tenantsResp) { $tenants = @($tenantsResp) }
} catch {
    throw "Failed to list tenants: $($_.Exception.Message)"
}

$targetTenant = $tenants | Where-Object { $_.code -eq $tenantCode -and $_.is_active -eq $true } | Select-Object -First 1

if (-not $targetTenant) {
    if ($tenants.Count -eq 0) {
        Write-Host "[ensure-demo-users] Creating initial tenant '$tenantCode'..." -ForegroundColor Yellow
        $createBody = @{ name = $tenantName; code = $tenantCode; is_default = $true; is_active = $true } | ConvertTo-Json
        try {
            $targetTenant = Invoke-RestMethod -Uri "$baseUrl/api/tenants" -Method Post -Headers $headers -ContentType "application/json" -Body $createBody -TimeoutSec 15
        } catch {
            $statusCode = Get-StatusCode -Exception $_.Exception
            if ($statusCode -ne 409) { throw "Create tenant failed: $($_.Exception.Message)" }
        }
    } else {
        Write-Host "[ensure-demo-users] Creating additional tenant '$tenantCode'..." -ForegroundColor Yellow
        $createAdminBody = @{ name = $tenantName; code = $tenantCode; is_default = $false; is_active = $true } | ConvertTo-Json
        try {
            $targetTenant = Invoke-RestMethod -Uri "$baseUrl/api/tenants/admin" -Method Post -Headers $headers -ContentType "application/json" -Body $createAdminBody -TimeoutSec 15
        } catch {
            $statusCode = Get-StatusCode -Exception $_.Exception
            if ($statusCode -ne 409) { throw "Create tenant(admin) failed: $($_.Exception.Message)" }
        }
    }

    $tenantsResp2 = Invoke-RestMethod -Uri "$baseUrl/api/tenants?include_inactive=true" -Method Get -Headers $headers -TimeoutSec 10
    $tenants2 = if ($tenantsResp2 -is [System.Array]) { @($tenantsResp2) } elseif ($null -ne $tenantsResp2) { @($tenantsResp2) } else { @() }
    $targetTenant = $tenants2 | Where-Object { $_.code -eq $tenantCode -and $_.is_active -eq $true } | Select-Object -First 1
}

if (-not $targetTenant) {
    throw "Unable to resolve target tenant code '$tenantCode'"
}

function Ensure-User {
    param(
        [string]$BaseUrl,
        [hashtable]$Headers,
        [string]$TenantCode,
        [string]$Username,
        [string]$Password,
        [string]$Role
    )
    $body = @{ tenant_code = $TenantCode; username = $Username; password = $Password; role = $Role } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/users" -Method Post -Headers $Headers -ContentType "application/json" -Body $body -TimeoutSec 15
        Write-Host "[ensure-demo-users] Created $Role user: $Username" -ForegroundColor Green
    } catch {
        $statusCode = Get-StatusCode -Exception $_.Exception
        if ($statusCode -eq 409) {
            Write-Host "[ensure-demo-users] User already exists: $Username" -ForegroundColor DarkYellow
            return
        }
        throw "Create user '$Username' failed: $($_.Exception.Message)"
    }
}

Ensure-User -BaseUrl $baseUrl -Headers $headers -TenantCode $tenantCode -Username $managerUsername -Password $managerPassword -Role "manager"
Ensure-User -BaseUrl $baseUrl -Headers $headers -TenantCode $tenantCode -Username $userUsername -Password $userPassword -Role "user"

Write-Host "[ensure-demo-users] Verifying manager/user existence..." -ForegroundColor Cyan
$usersResp = Invoke-RestMethod -Uri "$baseUrl/api/auth/users?tenant_code=$tenantCode" -Method Get -Headers $headers -TimeoutSec 10
$users = if ($usersResp -is [System.Array]) { @($usersResp) } elseif ($null -ne $usersResp) { @($usersResp) } else { @() }

$managerCount = @($users | Where-Object { $_.username -eq $managerUsername -and $_.role -eq "manager" -and $_.is_active -eq $true }).Count
$userCount = @($users | Where-Object { $_.username -eq $userUsername -and $_.role -eq "user" -and $_.is_active -eq $true }).Count

if ($managerCount -lt 1 -or $userCount -lt 1) {
    throw "Verification failed. manager=$managerCount user=$userCount"
}

Write-Host "[ensure-demo-users] OK tenant=$tenantCode manager=$managerUsername user=$userUsername" -ForegroundColor Green
exit 0
