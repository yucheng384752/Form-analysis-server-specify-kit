param(
  [Parameter(Mandatory = $true)]
  [string]$Owner,

  [Parameter(Mandatory = $true)]
  [string]$Repo,

  [string]$Token = "",

  [string]$SeedFile = "$PSScriptRoot\..\dev-guides\issue-seeds\2026-01-16.json",

  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SeedFile)) {
  throw "Seed file not found: $SeedFile"
}

if (-not $Token) {
  $Token = $env:GITHUB_TOKEN
}

if (-not $Token) {
  $Token = $env:GH_TOKEN
}

if (-not $Token) {
  throw "Missing GitHub token. Provide -Token or set env GITHUB_TOKEN/GH_TOKEN."
}

$issues = Get-Content -Raw -Encoding UTF8 $SeedFile | ConvertFrom-Json
if (-not $issues -or $issues.Count -eq 0) {
  throw "No issues found in seed file: $SeedFile"
}

$apiBase = "https://api.github.com"
$uri = "$apiBase/repos/$Owner/$Repo/issues"

$headers = @{
  Authorization = "Bearer $Token"
  Accept        = "application/vnd.github+json"
  "X-GitHub-Api-Version" = "2022-11-28"
  "User-Agent"  = "Form-analysis-server-specify-kit-issue-seeder"
}

$created = @()

foreach ($item in $issues) {
  $title = [string]$item.title
  $body = [string]$item.body

  if (-not $title.Trim()) { continue }

  $payload = @{ title = $title; body = $body } | ConvertTo-Json -Depth 10

  if ($DryRun) {
    Write-Host "[DRYRUN] would create: $title"
    continue
  }

  Write-Host "Creating issue: $title"
  $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $payload -ContentType "application/json; charset=utf-8"
  $created += $resp.html_url
}

Write-Host ""
Write-Host "Created issues:"
$created | ForEach-Object { Write-Host "- $_" }
