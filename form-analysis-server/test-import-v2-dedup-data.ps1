# test-import-v2-dedup-data.ps1
# 測試 L2-3 資料重複檢查 (E_UNIQUE_IN_FILE, E_UNIQUE_IN_DB)

$baseUrl = "http://localhost:18002/api/v2/import"

# 1. 準備測試檔案 (P1)
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
# 使用相同的檔名以確保 Lot No 相同 (P1 Lot No 來自檔名)
$fileName = "P1_Dedup_$timestamp.csv"
$lotNo = "Dedup_$timestamp"

# 第一份檔案內容：單行資料
$content1 = @"
Lot No.,Winder,Date,Time,Length,Weight,Diameter,M/min,Kg/min,Denier,Draw Ratio,D/R 2,D/R 3,Temp 1,Temp 2,Temp 3,Temp 4,Temp 5,Temp 6,Temp 7,Temp 8,Temp 9,Temp 10,Temp 11,Temp 12,Temp 13,Temp 14,Temp 15,Temp 16,Temp 17,Temp 18,Temp 19,Temp 20,Temp 21,Temp 22,Temp 23,Temp 24,Temp 25,Temp 26,Temp 27,Temp 28,Temp 29,Temp 30,Temp 31,Temp 32,Temp 33,Temp 34,Temp 35,Temp 36,Temp 37,Temp 38,Temp 39,Temp 40,Temp 41,Temp 42,Temp 43,Temp 44,Temp 45,Temp 46,Temp 47,Temp 48,Temp 49,Temp 50,Temp 51,Temp 52,Temp 53,Temp 54,Temp 55,Temp 56,Temp 57,Temp 58,Temp 59,Temp 60,Temp 61,Temp 62,Temp 63,Temp 64,Temp 65,Temp 66,Temp 67,Temp 68,Temp 69,Temp 70,Temp 71,Temp 72,Temp 73,Temp 74,Temp 75,Temp 76,Temp 77,Temp 78,Temp 79,Temp 80,Temp 81,Temp 82,Temp 83,Temp 84,Temp 85,Temp 86,Temp 87,Temp 88,Temp 89,Temp 90,Temp 91,Temp 92,Temp 93,Temp 94,Temp 95,Temp 96,Temp 97,Temp 98,Temp 99,Temp 100
$lotNo,1,2023/10/27,10:00:00,1000,5.5,120,500,0.5,150,1.5,1.2,1.1,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200
"@
Set-Content -Path $fileName -Value $content1 -Encoding UTF8

Write-Host "1. Uploading Initial File (to be committed)..."
$response1Json = curl.exe -s -X POST "$baseUrl/jobs" -F "table_code=P1" -F "files=@$fileName"
Write-Host "Raw Response 1: $response1Json"
try {
    $response1 = $response1Json | ConvertFrom-Json
    $jobId1 = $response1.id
    Write-Host "   Job ID: $jobId1"
} catch {
    Write-Host "Failed to parse JSON response"
}

# Commit Job 1
if ($jobId1) {
    Write-Host "   Committing Job 1..."
    # Wait for validation to complete
    Start-Sleep -Seconds 2
    
    # Check Job 1 status and errors BEFORE commit
    $job1StatusJson = curl.exe -s -X GET "$baseUrl/jobs/$jobId1"
    $job1Status = $job1StatusJson | ConvertFrom-Json
    Write-Host "   Job 1 Status (Pre-Commit): $($job1Status.status)"
    if ($job1Status.files[0].errors) {
        Write-Host "   Job 1 Errors (Pre-Commit):"
        Write-Host ($job1Status.files[0].errors | ConvertTo-Json -Depth 2)
    }

    curl.exe -s -X POST "$baseUrl/jobs/$jobId1/commit"
    Write-Host "   Job 1 Committed."
} else {
    Write-Host "Skipping commit because Job ID is missing"
}

# 2. 準備第二份檔案 (測試重複)
# 使用相同的檔名 (Lot No 相同)，但內容不同 (File Hash 不同)
# - 第一行：與 Job 1 資料重複 (E_UNIQUE_IN_DB)
# - 第二行：新資料 (但 Lot No 相同 -> E_UNIQUE_IN_DB, 且與第一行 Lot No 相同 -> E_UNIQUE_IN_FILE)
# - 第三行：與第二行重複 (E_UNIQUE_IN_DB, E_UNIQUE_IN_FILE)
$content2 = @"
Lot No.,Winder,Date,Time,Length,Weight,Diameter,M/min,Kg/min,Denier,Draw Ratio,D/R 2,D/R 3,Temp 1,Temp 2,Temp 3,Temp 4,Temp 5,Temp 6,Temp 7,Temp 8,Temp 9,Temp 10,Temp 11,Temp 12,Temp 13,Temp 14,Temp 15,Temp 16,Temp 17,Temp 18,Temp 19,Temp 20,Temp 21,Temp 22,Temp 23,Temp 24,Temp 25,Temp 26,Temp 27,Temp 28,Temp 29,Temp 30,Temp 31,Temp 32,Temp 33,Temp 34,Temp 35,Temp 36,Temp 37,Temp 38,Temp 39,Temp 40,Temp 41,Temp 42,Temp 43,Temp 44,Temp 45,Temp 46,Temp 47,Temp 48,Temp 49,Temp 50,Temp 51,Temp 52,Temp 53,Temp 54,Temp 55,Temp 56,Temp 57,Temp 58,Temp 59,Temp 60,Temp 61,Temp 62,Temp 63,Temp 64,Temp 65,Temp 66,Temp 67,Temp 68,Temp 69,Temp 70,Temp 71,Temp 72,Temp 73,Temp 74,Temp 75,Temp 76,Temp 77,Temp 78,Temp 79,Temp 80,Temp 81,Temp 82,Temp 83,Temp 84,Temp 85,Temp 86,Temp 87,Temp 88,Temp 89,Temp 90,Temp 91,Temp 92,Temp 93,Temp 94,Temp 95,Temp 96,Temp 97,Temp 98,Temp 99,Temp 100
$lotNo,1,2023/10/27,10:00:00,1000,5.5,120,500,0.5,150,1.5,1.2,1.1,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200
$lotNo,2,2023/10/27,10:00:00,1000,5.5,120,500,0.5,150,1.5,1.2,1.1,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200
$lotNo,2,2023/10/27,10:00:00,1000,5.5,120,500,0.5,150,1.5,1.2,1.1,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200
"@
Set-Content -Path $fileName -Value $content2 -Encoding UTF8

Write-Host "2. Uploading Test File (expecting errors)..."
$response2Json = curl.exe -s -X POST "$baseUrl/jobs" -F "table_code=P1" -F "files=@$fileName"
Write-Host "Raw Response 2: $response2Json"
try {
    $response2 = $response2Json | ConvertFrom-Json
    $jobId2 = $response2.id
    Write-Host "   Job ID: $jobId2"
} catch {
    Write-Host "Failed to parse JSON response"
}

# 3. 檢查 Job 狀態
if ($jobId2) {
    Start-Sleep -Seconds 2
    $jobStatusJson = curl.exe -s -X GET "$baseUrl/jobs/$jobId2"
    $jobStatus = $jobStatusJson | ConvertFrom-Json
    Write-Host "   Job Status: $($jobStatus.status)"

    # 4. 檢查 Errors
    Write-Host "   Checking Errors..."
    
    # Check error_count first
    if ($jobStatus.error_count -eq 0) {
        Write-Host "FAILURE: error_count is 0. Expected errors."
        exit 1
    }
    Write-Host "   [OK] error_count is $($jobStatus.error_count)"

    # Fetch detailed errors
    $errorsJson = curl.exe -s -X GET "$baseUrl/jobs/$jobId2/errors"
    try {
        $errors = $errorsJson | ConvertFrom-Json
    } catch {
        Write-Host "Failed to parse errors JSON"
        exit 1
    }

    $foundUniqueInFile = $false
    $foundUniqueInDB = $false

    foreach ($row in $errors) {
        foreach ($err in $row.errors) {
            if ($err.message -eq "E_UNIQUE_IN_FILE") {
                Write-Host "   [OK] Found E_UNIQUE_IN_FILE at row $($row.row_index)"
                $foundUniqueInFile = $true
            }
            if ($err.message -eq "E_UNIQUE_IN_DB") {
                Write-Host "   [OK] Found E_UNIQUE_IN_DB at row $($row.row_index)"
                $foundUniqueInDB = $true
            }
        }
    }

    if ($foundUniqueInFile -and $foundUniqueInDB) {
        Write-Host "SUCCESS: Both deduplication checks passed."
    } else {
        Write-Host "FAILURE: Missing expected errors."
        Write-Host "Errors found: " ($errors | ConvertTo-Json -Depth 4)
    }
} else {
    Write-Host "Skipping checks because Job ID 2 is missing"
}

# Cleanup
Remove-Item $fileName
