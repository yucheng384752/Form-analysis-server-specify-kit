# ============================================================
# P3 Items 資料庫遷移執行腳本
# ============================================================
# 版本: 1.0
# 日期: 2025-01-22
# 說明: 自動化執行 P3 Items 資料庫遷移
# ============================================================

param(
    [switch]$Backfill,      # 是否執行資料回填
    [switch]$DryRun,        # 僅顯示將要執行的命令，不實際執行
    [switch]$SkipBackup     # 跳過備份步驟
)

# 設定錯誤處理
$ErrorActionPreference = "Stop"

# 顏色輸出函數
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# ============================================================
# Step 1: 載入環境變數
# ============================================================

Write-ColorOutput "`n============================================================" "Cyan"
Write-ColorOutput "P3 Items 資料庫遷移腳本" "Cyan"
Write-ColorOutput "============================================================`n" "Cyan"

# 從 .env 檔案讀取配置
$envFile = "form-analysis-server\.env"
if (Test-Path $envFile) {
    Write-ColorOutput "✓ 載入環境變數: $envFile" "Green"
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} else {
    Write-ColorOutput "✗ 找不到 .env 檔案，使用預設值" "Yellow"
}

# 設定資料庫連接資訊
$PGHOST = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "localhost" }
$PGPORT = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "18001" }
$PGDATABASE = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "form_analysis_db" }
$PGUSER = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "app" }
$PGPASSWORD = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "app_secure_password_2024" }

# 設定環境變數供 psql 使用
$env:PGHOST = $PGHOST
$env:PGPORT = $PGPORT
$env:PGDATABASE = $PGDATABASE
$env:PGUSER = $PGUSER
$env:PGPASSWORD = $PGPASSWORD

Write-ColorOutput "`n資料庫連接資訊:" "Cyan"
Write-ColorOutput "  主機: $PGHOST" "White"
Write-ColorOutput "  端口: $PGPORT" "White"
Write-ColorOutput "  資料庫: $PGDATABASE" "White"
Write-ColorOutput "  使用者: $PGUSER" "White"
Write-ColorOutput "  密碼: ********" "White"

# ============================================================
# Step 2: 檢查 psql 是否可用
# ============================================================

Write-ColorOutput "`n檢查 PostgreSQL 客戶端工具..." "Cyan"

try {
    $psqlVersion = psql --version 2>&1
    Write-ColorOutput "✓ psql 已安裝: $psqlVersion" "Green"
} catch {
    Write-ColorOutput "✗ 找不到 psql 命令" "Red"
    Write-ColorOutput "`n請安裝 PostgreSQL 客戶端或使用 Docker:" "Yellow"
    Write-ColorOutput "  方法 1: 下載 PostgreSQL - https://www.postgresql.org/download/" "Yellow"
    Write-ColorOutput "  方法 2: 使用 Docker - docker exec -it <container> psql ..." "Yellow"
    exit 1
}

# ============================================================
# Step 3: 測試資料庫連接
# ============================================================

Write-ColorOutput "`n測試資料庫連接..." "Cyan"

if (-not $DryRun) {
    try {
        $testQuery = "SELECT version();"
        $result = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c $testQuery 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ 資料庫連接成功" "Green"
        } else {
            throw "連接失敗"
        }
    } catch {
        Write-ColorOutput "✗ 無法連接到資料庫" "Red"
        Write-ColorOutput "錯誤: $_" "Red"
        exit 1
    }
} else {
    Write-ColorOutput "[DRY RUN] 跳過連接測試" "Yellow"
}

# ============================================================
# Step 4: 備份現有資料（如果表已存在）
# ============================================================

if (-not $SkipBackup -and -not $DryRun) {
    Write-ColorOutput "`n檢查是否需要備份..." "Cyan"
    
    $checkTable = "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'p3_items');"
    $tableExists = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkTable
    
    if ($tableExists -match "t") {
        Write-ColorOutput "⚠ p3_items 表已存在，創建備份..." "Yellow"
        
        $backupFile = "migrations\backup_p3_items_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
        
        try {
            pg_dump -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t p3_items -f $backupFile
            Write-ColorOutput "✓ 備份已創建: $backupFile" "Green"
        } catch {
            Write-ColorOutput "✗ 備份失敗: $_" "Red"
            $continue = Read-Host "是否繼續執行遷移？(y/N)"
            if ($continue -ne "y") {
                exit 1
            }
        }
    } else {
        Write-ColorOutput "✓ 無需備份（表不存在）" "Green"
    }
}

# ============================================================
# Step 5: 執行主要遷移
# ============================================================

Write-ColorOutput "`n執行主要遷移腳本..." "Cyan"

$migrationFile = "migrations\001_create_p3_items.sql"

if (-not (Test-Path $migrationFile)) {
    Write-ColorOutput "✗ 找不到遷移檔案: $migrationFile" "Red"
    exit 1
}

if ($DryRun) {
    Write-ColorOutput "[DRY RUN] 將執行: psql -f $migrationFile" "Yellow"
} else {
    try {
        Write-ColorOutput "執行: $migrationFile" "White"
        psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f $migrationFile
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ 主要遷移完成" "Green"
        } else {
            throw "遷移執行失敗"
        }
    } catch {
        Write-ColorOutput "✗ 遷移執行失敗: $_" "Red"
        exit 1
    }
}

# ============================================================
# Step 6: 執行資料回填（可選）
# ============================================================

if ($Backfill) {
    Write-ColorOutput "`n執行資料回填腳本..." "Cyan"
    
    $backfillFile = "migrations\002_backfill_p3_items.sql"
    
    if (-not (Test-Path $backfillFile)) {
        Write-ColorOutput "✗ 找不到回填檔案: $backfillFile" "Red"
    } elseif ($DryRun) {
        Write-ColorOutput "[DRY RUN] 將執行: psql -f $backfillFile" "Yellow"
    } else {
        # 先檢查是否有 P3 資料
        $checkP3 = "SELECT COUNT(*) FROM records WHERE data_type = 'P3';"
        $p3Count = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkP3
        
        Write-ColorOutput "找到 $p3Count 筆 P3 記錄" "White"
        
        if ([int]$p3Count -gt 0) {
            try {
                Write-ColorOutput "執行: $backfillFile" "White"
                psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f $backfillFile
                
                if ($LASTEXITCODE -eq 0) {
                    Write-ColorOutput "✓ 資料回填完成" "Green"
                } else {
                    Write-ColorOutput "⚠ 資料回填失敗，但主要遷移已完成" "Yellow"
                }
            } catch {
                Write-ColorOutput "⚠ 資料回填失敗: $_" "Yellow"
            }
        } else {
            Write-ColorOutput "✓ 無 P3 資料，跳過回填" "Green"
        }
    }
}

# ============================================================
# Step 7: 驗證遷移結果
# ============================================================

if (-not $DryRun) {
    Write-ColorOutput "`n驗證遷移結果..." "Cyan"
    
    # 檢查表是否存在
    $checkTable = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = 'p3_items';"
    $tableResult = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkTable
    
    if ($tableResult -match "p3_items") {
        Write-ColorOutput "✓ p3_items 表已創建" "Green"
    } else {
        Write-ColorOutput "✗ p3_items 表創建失敗" "Red"
        exit 1
    }
    
    # 檢查欄位數量
    $checkColumns = "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'p3_items';"
    $columnCount = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkColumns
    Write-ColorOutput "✓ 欄位數量: $columnCount" "Green"
    
    # 檢查索引數量
    $checkIndexes = "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'p3_items';"
    $indexCount = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkIndexes
    Write-ColorOutput "✓ 索引數量: $indexCount" "Green"
    
    # 檢查外鍵約束
    $checkFk = "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_name = 'p3_items' AND constraint_type = 'FOREIGN KEY';"
    $fkCount = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c $checkFk
    Write-ColorOutput "✓ 外鍵約束: $fkCount" "Green"
}

# ============================================================
# 完成
# ============================================================

Write-ColorOutput "`n============================================================" "Cyan"
Write-ColorOutput " 遷移執行完成！" "Green"
Write-ColorOutput "============================================================" "Cyan"

Write-ColorOutput "`n下一步:" "Cyan"
Write-ColorOutput "  1. 重啟應用服務" "White"
Write-ColorOutput "  2. 測試 P3 檔案匯入功能" "White"
Write-ColorOutput "  3. 檢查應用程式日誌" "White"
Write-ColorOutput "  4. 執行功能測試" "White"

if ($DryRun) {
    Write-ColorOutput "`n[DRY RUN] 這是模擬執行，實際資料庫未被修改" "Yellow"
    Write-ColorOutput "移除 -DryRun 參數以實際執行遷移" "Yellow"
}

Write-ColorOutput "" "White"
