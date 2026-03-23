# PostgreSQL 本地開發環境啟動腳本
# 此腳本啟動PostgreSQL Docker容器並初始化資料庫

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Form Analysis PostgreSQL 設置" -ForegroundColor Cyan  
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Resolve-Compose {
	try {
		docker compose version | Out-Null
		if ($LASTEXITCODE -eq 0) {
			return @{ Cmd = 'docker'; BaseArgs = @('compose') }
		}
	} catch {
		# ignore
	}

	if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
		return @{ Cmd = 'docker-compose'; BaseArgs = @() }
	}

	throw '找不到 Docker Compose。請確認 Docker Desktop 已安裝 compose plugin 或已安裝 docker-compose。'
}

function Get-DotEnvValue {
	param(
		[Parameter(Mandatory = $true)][string]$Path,
		[Parameter(Mandatory = $true)][string]$Key,
		[Parameter(Mandatory = $true)][string]$Default
	)
	if (-not (Test-Path $Path)) { return $Default }
	try {
		$line = Get-Content $Path -ErrorAction Stop | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } | Select-Object -First 1
		if (-not $line) { return $Default }
		$value = ($line -split "=", 2)[1]
		if (-not $value) { return $Default }
		return $value.Trim().Trim('"')
	} catch {
		return $Default
	}
}

$compose = Resolve-Compose
$composeCmd = $compose.Cmd
$composeBaseArgs = $compose.BaseArgs

$composeDisplay = if ($composeCmd -eq 'docker') { 'docker compose' } else { 'docker-compose' }

$envFile = Join-Path $PSScriptRoot '.env'
$dbPort = Get-DotEnvValue -Path $envFile -Key 'POSTGRES_PORT' -Default '18001'

Write-Host " 正在啟動PostgreSQL Docker容器..." -ForegroundColor Yellow
& $composeCmd @($composeBaseArgs + @('up', '-d', 'db'))

Write-Host ""
Write-Host " 等待PostgreSQL準備就緒..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host " 檢查PostgreSQL容器狀態..." -ForegroundColor Yellow
& $composeCmd @($composeBaseArgs + @('ps', 'db'))

Write-Host ""
Write-Host " PostgreSQL連接資訊:" -ForegroundColor Green
Write-Host "   主機: localhost" -ForegroundColor White
Write-Host "   端口: $dbPort" -ForegroundColor White
Write-Host "   資料庫: form_analysis_db" -ForegroundColor White
Write-Host "   用戶: app" -ForegroundColor White
Write-Host "   密碼: 請見 .env 的 POSTGRES_PASSWORD" -ForegroundColor White

Write-Host ""
Write-Host " 正在初始化資料庫表格..." -ForegroundColor Yellow
Push-Location backend
python setup_postgresql.py
Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " PostgreSQL設置完成！" -ForegroundColor Green
Write-Host ""
Write-Host "提示:" -ForegroundColor Yellow
Write-Host "   - 使用 $composeDisplay logs db 查看資料庫日誌" -ForegroundColor White
Write-Host "   - 使用 $composeDisplay down 停止服務" -ForegroundColor White  
Write-Host "   - 使用 $composeDisplay up -d pgadmin --profile tools 啟動pgAdmin" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan

Read-Host "按Enter鍵繼續"