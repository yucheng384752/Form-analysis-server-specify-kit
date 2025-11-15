# Form Analysis System - Log Management Tool (English Version)
# PowerShell script for advanced log management

param(
    [Parameter(Mandatory=$false)]
    [string]$Action = "menu",
    
    [Parameter(Mandatory=$false)]
    [string]$LogDir = "form-analysis-server\backend\logs",
    
    [Parameter(Mandatory=$false)]
    [int]$Lines = 50,
    
    [Parameter(Mandatory=$false)]
    [string]$SearchTerm = ""
)

# Set console encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Color configuration
$Colors = @{
    'Success' = 'Green'
    'Warning' = 'Yellow'
    'Error' = 'Red'
    'Info' = 'Cyan'
    'Header' = 'Magenta'
}

# Log level icons
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
    Show-Header "Log Statistics"
    
    if (-not (Test-LogDirectory)) { return }
    
    $logFiles = Get-LogFiles
    
    # File size statistics
    Write-ColoredOutput "File Information:" "Info"
    if ($logFiles.AppLogExists) {
        $size = (Get-Item $logFiles.AppLog).Length
        $sizeGB = [math]::Round($size / 1GB, 3)
        Write-Host "   app.log: " -NoNewline
        Write-Host "$($size.ToString('N0')) bytes ($sizeGB GB)" -ForegroundColor Green
    }
    
    if ($logFiles.ErrorLogExists) {
        $size = (Get-Item $logFiles.ErrorLog).Length
        $sizeGB = [math]::Round($size / 1GB, 3)
        Write-Host "   error.log: " -NoNewline
        Write-Host "$($size.ToString('N0')) bytes ($sizeGB GB)" -ForegroundColor Red
    }
    
    # Log level statistics
    if ($logFiles.AppLogExists) {
        Write-Host ""
        Write-ColoredOutput "Log Level Statistics:" "Info"
        
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
        
        Write-Host "   Total lines: " -NoNewline
        Write-Host $totalLines.ToString('N0') -ForegroundColor White
        
        foreach ($level in $stats.Keys) {
            $count = $stats[$level]
            $percentage = if ($totalLines -gt 0) { [math]::Round(($count / $totalLines) * 100, 1) } else { 0 }
            $icon = $LogIcons[$level]
            
            Write-Host "   $icon $level`: " -NoNewline
            Write-Host "$($count.ToString('N0')) ($percentage%)" -ForegroundColor $(if ($level -eq 'ERROR' -or $level -eq 'CRITICAL') { 'Red' } elseif ($level -eq 'WARNING') { 'Yellow' } else { 'Green' })
        }
    }
    
    # API usage statistics
    if ($logFiles.AppLogExists) {
        Write-Host ""
        Write-ColoredOutput "API Usage Statistics:" "Info"
        
        $content = Get-Content $logFiles.AppLog
        $apiStats = @{
            'File Upload' = ($content | Where-Object { $_ -match 'upload|Upload' }).Count
            'Data Query' = ($content | Where-Object { $_ -match 'query|Query' }).Count
            'Data Import' = ($content | Where-Object { $_ -match 'import|Import' }).Count
        }
        
        foreach ($api in $apiStats.Keys) {
            Write-Host "   $api`: " -NoNewline
            Write-Host $apiStats[$api].ToString('N0') -ForegroundColor Cyan
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
        Write-ColoredOutput "WARNING: Log file does not exist: $logFile" "Warning"
        return
    }
    
    Show-Header "$LogType Logs (Latest $LineCount lines)"
    
    $logs = Get-Content $logFile -Tail $LineCount
    
    foreach ($log in $logs) {
        # Try to parse JSON format logs
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
            # If not JSON format, display directly
            Write-Host $log -ForegroundColor Gray
        }
    }
    
    Write-Host ""
}

function Search-Logs {
    param([string]$Term)
    
    if (-not (Test-LogDirectory)) { return }
    
    if ([string]::IsNullOrEmpty($Term)) {
        $Term = Read-Host "Enter search term"
    }
    
    if ([string]::IsNullOrEmpty($Term)) { return }
    
    Show-Header "Search Results: '$Term'"
    
    $logFiles = Get-LogFiles
    
    if ($logFiles.AppLogExists) {
        $results = Get-Content $logFiles.AppLog | Select-String $Term -AllMatches
        
        Write-ColoredOutput "Found $($results.Count) matches in app.log:" "Info"
        
        foreach ($result in $results | Select-Object -First 20) {
            $lineNumber = $result.LineNumber
            $line = $result.Line
            
            Write-Host "[$lineNumber] " -NoNewline -ForegroundColor Yellow
            Write-Host $line -ForegroundColor White
        }
        
        if ($results.Count -gt 20) {
            Write-ColoredOutput "... $($results.Count - 20) more results not shown" "Warning"
        }
    }
    
    Write-Host ""
}

function Cleanup-OldLogs {
    if (-not (Test-LogDirectory)) { return }
    
    Show-Header "Log Cleanup"
    
    $backupFiles = Get-ChildItem $LogDir -Filter "*.log.*"
    
    if ($backupFiles.Count -eq 0) {
        Write-ColoredOutput "No backup files to clean up" "Info"
        return
    }
    
    Write-ColoredOutput "Found $($backupFiles.Count) backup files:" "Warning"
    foreach ($file in $backupFiles) {
        $size = [math]::Round($file.Length / 1MB, 2)
        Write-Host "   $($file.Name) ($size MB)" -ForegroundColor DarkGray
    }
    
    Write-Host ""
    $confirm = Read-Host "Are you sure you want to delete these backup files? (y/N)"
    
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        $backupFiles | Remove-Item -Force
        Write-ColoredOutput "Cleaned up $($backupFiles.Count) backup files" "Success"
    } else {
        Write-ColoredOutput "Cleanup cancelled" "Warning"
    }
    
    Write-Host ""
}

function Show-Menu {
    do {
        Clear-Host
        Show-Header "Form Analysis System - Log Management Tool"
        
        Write-ColoredOutput "Available Operations:" "Info"
        Write-Host "   [1] View Application Logs (Latest 50 lines)"
        Write-Host "   [2] View Error Logs (Latest 50 lines)"
        Write-Host "   [3] Show Statistics"
        Write-Host "   [4] Search Logs"
        Write-Host "   [5] Clean Old Logs"
        Write-Host "   [6] Custom View"
        Write-Host "   [0] Exit"
        Write-Host ""
        
        $choice = Read-Host "Select operation (0-6)"
        
        switch ($choice) {
            "1" { Show-RecentLogs -LogType "app" -LineCount 50; Read-Host "Press Enter to continue" }
            "2" { Show-RecentLogs -LogType "error" -LineCount 50; Read-Host "Press Enter to continue" }
            "3" { Show-LogStats; Read-Host "Press Enter to continue" }
            "4" { Search-Logs; Read-Host "Press Enter to continue" }
            "5" { Cleanup-OldLogs; Read-Host "Press Enter to continue" }
            "6" { 
                $lines = Read-Host "Enter number of lines to display (default 50)"
                if ([string]::IsNullOrEmpty($lines)) { $lines = 50 }
                Show-RecentLogs -LogType "app" -LineCount $lines
                Read-Host "Press Enter to continue"
            }
            "0" { Write-ColoredOutput "Goodbye!" "Success"; break }
            default { Write-ColoredOutput "Invalid selection, please try again" "Error"; Start-Sleep 1 }
        }
    } while ($true)
}

# Main program logic
switch ($Action.ToLower()) {
    "menu" { Show-Menu }
    "stats" { Show-LogStats }
    "view" { Show-RecentLogs -LogType "app" -LineCount $Lines }
    "errors" { Show-RecentLogs -LogType "error" -LineCount $Lines }
    "search" { Search-Logs -Term $SearchTerm }
    "cleanup" { Cleanup-OldLogs }
    default { 
        Write-ColoredOutput "Unknown action: $Action" "Error"
        Write-ColoredOutput "Available actions: menu, stats, view, errors, search, cleanup" "Info"
    }
}