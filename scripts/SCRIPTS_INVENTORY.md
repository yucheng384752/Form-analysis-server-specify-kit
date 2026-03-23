# 腳本清單與用途

> 更新日期：2026-03-09
> 用途：記錄 scripts/ 目錄下各腳本的狀態與功能

## 🟢 現行使用中腳本

### 環境啟動/停止
| 腳本 | 用途 | 備註 |
|------|------|------|
| `start-demo.bat` | 啟動 Demo 環境 | Port 181xx, `-p form-analysis-demo` |
| `start-dev.bat` | 啟動 Dev 環境 | Port 180xx, `-p form-analysis-dev` |
| `stop-demo.bat` | 停止 Demo 環境 | |
| `stop-system.bat` | 停止 Docker 系統 | 通用停止腳本 |
| `build-demo-images.bat` | 重建 Demo 映像 | 用於強制重建 |

### 診斷/監控
| 腳本 | 用途 | 備註 |
|------|------|------|
| `diagnose-system.bat` | 系統診斷 | 檢查 Docker、Port、資料庫狀態 |
| `diagnose-connection.bat` | 連線診斷 | |
| `diagnose-frontend.ps1` | 前端診斷 | PowerShell |
| `monitor-logs.bat` | 監控日誌 | |
| `LogManager.ps1` | 日誌管理 | 中文版 |
| `LogManager-EN.ps1` | 日誌管理 | 英文版 |

### 使用者/資料管理
| 腳本 | 用途 | 備註 |
|------|------|------|
| `ensure-demo-users.ps1` | 確保 Demo 使用者存在 | Demo 環境初始化 |
| `check-pdf-server.ps1` | 檢查 PDF 服務狀態 | |

### 資料處理
| 腳本 | 用途 | 備註 |
|------|------|------|
| `analyze_p3_files.py` | 分析 P3 檔案 | Python |
| `check_p2_data.py` | 檢查 P2 資料 | Python |
| `cleanup_duplicates.py` | 清理重複資料 | Python |
| `delete_p2_record.py` | 刪除 P2 紀錄 | Python |
| `migrate_v1_to_v2.py` | v1 到 v2 遷移 | Python |
| `fix_product_id_format_to_underscore.py` | 修正 product_id 格式 | Python |

## 🟡 保留但不常用腳本

### 傳統啟動腳本
| 腳本 | 用途 | 備註 |
|------|------|------|
| `start-system.bat` | 傳統 Docker 啟動 | 被 start-demo/dev 取代，但仍可用 |
| `start-backend.bat` | 單獨啟動後端 | 特殊情況使用 |
| `start-frontend.bat` | 單獨啟動前端 | 特殊情況使用 |

### 測試/驗證
| 腳本 | 用途 | 備註 |
|------|------|------|
| `test-system.ps1` | 系統測試 | |
| `test-encoding.ps1` | 編碼測試 | |
| `encoding-test.ps1` | 編碼測試 | |
| `verify-database-fix.ps1` | 驗證資料庫修復 | |
| `verify-database-migration-fix.ps1` | 驗證遷移修復 | |

### GitHub Issues
| 腳本 | 用途 | 備註 |
|------|------|------|
| `create-github-issues.ps1` | 建立 GitHub Issues | 批次建立 |

## 🔴 已棄用腳本（建議歸檔或刪除）

| 腳本 | 原用途 | 棄用原因 |
|------|--------|----------|
| `start-system.ps1.backup2` | PowerShell 啟動備份 | 備份檔，已有正式版 |
| `start-system-simple.bat` | 簡化啟動 | 已被 start-demo/dev 取代 |
| `start-system-v2.bat` | v2 啟動腳本 | 已被 start-demo/dev 取代 |
| `start_services.bat` | 服務啟動 | 可能為舊版 |
| `start_services.ps1` | 服務啟動 | 可能為舊版 |
| `fix-frontend-connection.ps1` | 修復前端連線 | 一次性修復腳本 |
| `fix-frontend-connection-v2.ps1` | 修復前端連線 v2 | 一次性修復腳本 |

## 📁 子目錄

### utilities/
| 腳本 | 用途 |
|------|------|
| `prepare-for-packaging.bat` | 打包準備 |
| `verify-deployment.bat` | 部署驗證 |
| `test-api-connection.js` | API 連線測試 |

### tests/
測試用腳本，依測試需求使用。

### logs/
日誌輸出目錄。

### uploads/
上傳檔案暫存目錄。
