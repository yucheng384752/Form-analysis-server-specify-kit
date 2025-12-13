# Form Analysis System - 進階日誌管理工具
# PowerShell 版本，提供更豐富的日誌分析功能

param(
    [Parameter(Mandatory=$false)]
    [string]$Action = "menu",
    
    [Parameter(Mandatory=$false)]
    [string]$LogDir = "form-analysis-server\backend\logs",
    
    [Parameter(Mandatory=$false)]
    [int]$Lines = 50,
    
    [Parameter(Mandatory=$false)]
    [string]$SearchTerm = "",
    
    [Parameter(Mandatory=$false)]
    [int]$Hours = 24,
    
    [Parameter(Mandatory=$false)]
    [switch]$ExportJson,
    
    [Parameter(Mandatory=$false)]
    [switch]$Watch
)

# 設定控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 顏色配置
$Colors = @{
    'Success' = 'Green'
    'Warning' = 'Yellow'
    'Error' = 'Red'
    'Info' = 'Cyan'
    'Header' = 'Magenta'
    'Separator' = 'DarkGray'
}

# 日誌級別對應的圖示
$LogIcons = @{
    'INFO' = '[INFO]'
    'WARNING' = '[WARN]'
    'ERROR' = '[ERROR]'
    'DEBUG' = '[DEBUG]'
    'CRITICAL' = '[CRIT]'
}

function Write-ColoredOutput {
    param(
        [string]$Message,
        [string]$Color = 'White'
    )
    Write-Host $Message -ForegroundColor $Colors[$Color]
}

function Show-Header {
    param([string]$Title)
    
    Write-Host ""
    Write-ColoredOutput "================================================================" "Header"
    Write-ColoredOutput "                    $Title" "Header"
    Write-ColoredOutput "================================================================" "Header"
    Write-Host ""
}

function Test-LogDirectory {
    if (-not (Test-Path $LogDir)) {
        Write-ColoredOutput "ERROR: Log directory does not exist: $LogDir" "Error"
        Write-ColoredOutput "Please start the system first to create log files" "Warning"
        return $false
    }
    return $true
}

function Get-LogFiles {
    $appLog = Join-Path $LogDir "app.log"
    $errorLog = Join-Path $LogDir "error.log"
    
    return @{
        'AppLog' = $appLog
        'ErrorLog' = $errorLog
        'AppLogExists' = (Test-Path $appLog)
        'ErrorLogExists' = (Test-Path $errorLog)
    }
}

function Show-LogStats {
    Show-Header "日誌統計資訊"
    
    if (-not (Test-LogDirectory)) { return }
    
    $logFiles = Get-LogFiles
    
    # 檔案大小統計
    Write-ColoredOutput " 檔案資訊:" "Info"
    if ($logFiles.AppLogExists) {
        $size = (Get-Item $logFiles.AppLog).Length
        $sizeGB = [math]::Round($size / 1GB, 3)
        Write-Host "    app.log: " -NoNewline
        Write-Host "$($size.ToString('N0')) bytes ($sizeGB GB)" -ForegroundColor Green
    }
    
    if ($logFiles.ErrorLogExists) {
        $size = (Get-Item $logFiles.ErrorLog).Length
        $sizeGB = [math]::Round($size / 1GB, 3)
        Write-Host "    error.log: " -NoNewline
        Write-Host "$($size.ToString('N0')) bytes ($sizeGB GB)" -ForegroundColor Red
    }
    
    # 日誌級別統計
    if ($logFiles.AppLogExists) {
        Write-Host ""
        Write-ColoredOutput " 日誌級別統計:" "Info"
        
        $content = Get-Content $logFiles.AppLog
        $totalLines = $content.Count
        
        $stats = @{
            'INFO' = 0
            'WARNING' = 0
            'ERROR' = 0
            'DEBUG' = 0
            'CRITICAL' = 0
        }
        
        foreach ($line in $content) {
            foreach ($level in $stats.Keys) {
                if ($line -match $level) {
                    $stats[$level]++
                    break
                }
            }
        }
        
        Write-Host "   總行數: " -NoNewline
        Write-Host $totalLines.ToString('N0') -ForegroundColor White
        
        foreach ($level in $stats.Keys) {
            $count = $stats[$level]
            $percentage = if ($totalLines -gt 0) { [math]::Round(($count / $totalLines) * 100, 1) } else { 0 }
            $icon = $LogIcons[$level]
            
            Write-Host "   $icon $level`: " -NoNewline
            Write-Host "$($count.ToString('N0')) ($percentage%)" -ForegroundColor $(if ($level -eq 'ERROR' -or $level -eq 'CRITICAL') { 'Red' } elseif ($level -eq 'WARNING') { 'Yellow' } else { 'Green' })
        }
    }
    
    # API 使用統計
    if ($logFiles.AppLogExists) {
        Write-Host ""
        Write-ColoredOutput " API 使用統計:" "Info"
        
        $content = Get-Content $logFiles.AppLog
        $apiStats = @{
            '檔案上傳' = ($content | Where-Object { $_ -match '檔案上傳|upload' }).Count
            '資料查詢' = ($content | Where-Object { $_ -match '查詢|query' }).Count
            '資料匯入' = ($content | Where-Object { $_ -match '匯入|import' }).Count
        }
        
        foreach ($api in $apiStats.Keys) {
            Write-Host "    $api`: " -NoNewline
            Write-Host $apiStats[$api].ToString('N0') -ForegroundColor Cyan
        }
    }
    
    # 最近活動
    Write-Host ""
    Write-ColoredOutput "🕐 最近活動 (最新5條):" "Info"
    if ($logFiles.AppLogExists) {
        $recentLogs = Get-Content $logFiles.AppLog -Tail 5
        foreach ($log in $recentLogs) {
            $truncated = if ($log.Length -gt 100) { $log.Substring(0, 100) + "..." } else { $log }
            Write-Host "   $truncated" -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
}

function Show-RecentLogs {
    param(
        [string]$LogType = "app",
        [int]$LineCount = $Lines
    )
    
    if (-not (Test-LogDirectory)) { return }
    
    $logFiles = Get-LogFiles
    
    $logFile = if ($LogType -eq "error") { $logFiles.ErrorLog } else { $logFiles.AppLog }
    $logExists = if ($LogType -eq "error") { $logFiles.ErrorLogExists } else { $logFiles.AppLogExists }
    
    if (-not $logExists) {
        Write-ColoredOutput "  日誌檔案不存在: $logFile" "Warning"
        return
    }
    
    Show-Header "$LogType 日誌 (最新 $LineCount 行)"
    
    $logs = Get-Content $logFile -Tail $LineCount
    
    foreach ($log in $logs) {
        # 嘗試解析 JSON 格式的日誌
        try {
            $jsonLog = $log | ConvertFrom-Json -ErrorAction Stop
            $timestamp = $jsonLog.timestamp -replace 'T', ' ' -replace 'Z', ''
            $level = $jsonLog.level.ToUpper()
            $message = $jsonLog.message
            
            $icon = $LogIcons[$level]
            $color = switch ($level) {
                'ERROR' { 'Red' }
                'WARNING' { 'Yellow' }
                'INFO' { 'Green' }
                'DEBUG' { 'Cyan' }
                default { 'White' }
            }
            
            Write-Host "[$timestamp] " -NoNewline -ForegroundColor DarkGray
            Write-Host "$icon $level" -NoNewline -ForegroundColor $Colors[$color]
            Write-Host ": $message"
        }
        catch {
            # 如果不是 JSON 格式，直接顯示
            Write-Host $log -ForegroundColor Gray
        }
    }
    
    Write-Host ""
}

function Watch-Logs {
    if (-not (Test-LogDirectory)) { return }
    
    Show-Header "即時日誌監控 (Ctrl+C 停止)"
    
    $logFiles = Get-LogFiles
    
    if (-not $logFiles.AppLogExists) {
        Write-ColoredOutput "  日誌檔案不存在" "Warning"
        return
    }
    
    Write-ColoredOutput "開始監控 $($logFiles.AppLog)..." "Info"
    Write-Host ""
    
    Get-Content $logFiles.AppLog -Wait -Tail 10 | ForEach-Object {
        $timestamp = Get-Date -Format "HH:mm:ss"
        
        try {
            $jsonLog = $_ | ConvertFrom-Json -ErrorAction Stop
            $level = $jsonLog.level.ToUpper()
            $message = $jsonLog.message
            
            $icon = $LogIcons[$level]
            $color = switch ($level) {
                'ERROR' { 'Red' }
                'WARNING' { 'Yellow' }
                'INFO' { 'Green' }
                'DEBUG' { 'Cyan' }
                default { 'White' }
            }
            
            Write-Host "[$timestamp] " -NoNewline -ForegroundColor DarkGray
            Write-Host "$icon $level" -NoNewline -ForegroundColor $Colors[$color]
            Write-Host ": $message"
        }
        catch {
            Write-Host "[$timestamp] $_" -ForegroundColor Gray
        }
    }
}

function Search-Logs {
    param([string]$Term)
    
    if (-not (Test-LogDirectory)) { return }
    
    if ([string]::IsNullOrEmpty($Term)) {
        $Term = Read-Host "請輸入搜尋關鍵字"
    }
    
    if ([string]::IsNullOrEmpty($Term)) { return }
    
    Show-Header "搜尋結果: '$Term'"
    
    $logFiles = Get-LogFiles
    
    if ($logFiles.AppLogExists) {
        $results = Get-Content $logFiles.AppLog | Select-String $Term -AllMatches
        
        Write-ColoredOutput " 在 app.log 中找到 $($results.Count) 個匹配項:" "Info"
        
        foreach ($result in $results | Select-Object -First 20) {
            $lineNumber = $result.LineNumber
            $line = $result.Line
            
            # 高亮搜尋關鍵字
            $highlighted = $line -replace "($Term)", "***$1***"
            
            Write-Host "[$lineNumber] " -NoNewline -ForegroundColor Yellow
            Write-Host $highlighted -ForegroundColor White
        }
        
        if ($results.Count -gt 20) {
            Write-ColoredOutput "... 還有 $($results.Count - 20) 個結果未顯示" "Warning"
        }
    }
    
    Write-Host ""
}

function Export-LogsToJson {
    if (-not (Test-LogDirectory)) { return }
    
    Show-Header "匯出日誌為 JSON 格式"
    
    $logFiles = Get-LogFiles
    
    if (-not $logFiles.AppLogExists) {
        Write-ColoredOutput "  日誌檔案不存在" "Warning"
        return
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $outputFile = "log_export_$timestamp.json"
    
    Write-ColoredOutput "📤 正在匯出日誌..." "Info"
    
    $logs = @()
    $content = Get-Content $logFiles.AppLog
    
    foreach ($line in $content) {
        try {
            $jsonLog = $line | ConvertFrom-Json -ErrorAction Stop
            $logs += $jsonLog
        }
        catch {
            # 如果不是 JSON 格式，包裝成 JSON
            $logs += @{
                'timestamp' = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
                'level' = 'INFO'
                'message' = $line
            }
        }
    }
    
    $logs | ConvertTo-Json -Depth 10 | Out-File $outputFile -Encoding UTF8
    
    Write-ColoredOutput " 日誌已匯出到: $outputFile" "Success"
    Write-ColoredOutput " 匯出了 $($logs.Count) 條日誌記錄" "Info"
    Write-Host ""
}

function Cleanup-OldLogs {
    if (-not (Test-LogDirectory)) { return }
    
    Show-Header "清理舊日誌"
    
    $backupFiles = Get-ChildItem $LogDir -Filter "*.log.*"
    
    if ($backupFiles.Count -eq 0) {
        Write-ColoredOutput "  沒有備份檔案需要清理" "Info"
        return
    }
    
    Write-ColoredOutput "🗂️  找到 $($backupFiles.Count) 個備份檔案:" "Warning"
    foreach ($file in $backupFiles) {
        $size = [math]::Round($file.Length / 1MB, 2)
        Write-Host "    $($file.Name) ($size MB)" -ForegroundColor DarkGray
    }
    
    Write-Host ""
    $confirm = Read-Host "確定要刪除這些備份檔案嗎？(y/N)"
    
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        $backupFiles | Remove-Item -Force
        Write-ColoredOutput " 已清理 $($backupFiles.Count) 個備份檔案" "Success"
    } else {
        Write-ColoredOutput " 已取消清理操作" "Warning"
    }
    
    Write-Host ""
}

function Show-Menu {
    do {
        Clear-Host
        Show-Header "Form Analysis System - 日誌管理工具"
        
        Write-ColoredOutput " 可用操作：" "Info"
        Write-Host "   [1]  查看應用程式日誌 (最新50行)"
        Write-Host "   [2]  查看錯誤日誌 (最新50行)"
        Write-Host "   [3]  統計資訊"
        Write-Host "   [4] 即時監控"
        Write-Host "   [5]  搜尋日誌"
        Write-Host "   [6] 📤 匯出 JSON"
        Write-Host "   [7]  清理舊日誌"
        Write-Host "   [8] ⚙️  自定義查看"
        Write-Host "   [0]  退出"
        Write-Host ""
        
        $choice = Read-Host "請選擇操作 (0-8)"
        
        switch ($choice) {
            "1" { Show-RecentLogs -LogType "app" -LineCount 50; Read-Host "按 Enter 繼續" }
            "2" { Show-RecentLogs -LogType "error" -LineCount 50; Read-Host "按 Enter 繼續" }
            "3" { Show-LogStats; Read-Host "按 Enter 繼續" }
            "4" { Watch-Logs }
            "5" { Search-Logs; Read-Host "按 Enter 繼續" }
            "6" { Export-LogsToJson; Read-Host "按 Enter 繼續" }
            "7" { Cleanup-OldLogs; Read-Host "按 Enter 繼續" }
            "8" { 
                $lines = Read-Host "請輸入要顯示的行數 (預設 50)"
                if ([string]::IsNullOrEmpty($lines)) { $lines = 50 }
                Show-RecentLogs -LogType "app" -LineCount $lines
                Read-Host "按 Enter 繼續"
            }
            "0" { Write-ColoredOutput "👋 再見！" "Success"; break }
            default { Write-ColoredOutput " 無效選擇，請重新輸入" "Error"; Start-Sleep 1 }
        }
    } while ($true)
}

# 主程式邏輯
switch ($Action.ToLower()) {
    "menu" { Show-Menu }
    "stats" { Show-LogStats }
    "view" { Show-RecentLogs -LogType "app" -LineCount $Lines }
    "errors" { Show-RecentLogs -LogType "error" -LineCount $Lines }
    "search" { Search-Logs -Term $SearchTerm }
    "export" { Export-LogsToJson }
    "cleanup" { Cleanup-OldLogs }
    "watch" { Watch-Logs }
    default { 
        Write-ColoredOutput " 未知操作: $Action" "Error"
        Write-ColoredOutput "可用操作: menu, stats, view, errors, search, export, cleanup, watch" "Info"
    }
}