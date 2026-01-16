param(
  [string]$TenantId = "",
  [string]$TenantCode = "",
  [string]$Label = "default",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$argsList = @()
if ($TenantId) { $argsList += @("--tenant-id", $TenantId) }
if ($TenantCode) { $argsList += @("--tenant-code", $TenantCode) }
if ($Label) { $argsList += @("--label", $Label) }
if ($Force) { $argsList += "--force" }

python .\backend\scripts\bootstrap_tenant_api_key.py @argsList
