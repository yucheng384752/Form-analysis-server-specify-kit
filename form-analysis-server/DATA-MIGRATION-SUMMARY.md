# 資料遷移問題修復總結 (2026-01-13)

## 根本問題

**資料架構不一致**: 系統存在兩套資料表結構但資料未同步

| 項目 | Legacy 模式 | V2 模式 | 狀態 |
|------|------------|---------|------|
| 資料表 | `records`, `p2_items`, `p3_items` | `p1_records`, `p2_records`, `p3_records` | ⚠️ 不同步 |
| Tenant 支援 | 無 `tenant_id` 欄位 | ✅ 有 `tenant_id` 欄位 | - |
| 資料數量 | 3 筆測試資料 (已清除) | 0 筆 | ⚠️ 空的 |
| API 端點 | `/api/query` | `/api/v2/query` | Legacy 已移除 |
| 前端使用 | 未使用 | ✅ **正在使用** | ⚠️ **導致查無資料** |

### 診斷過程

1. **API 返回 0 筆**: `/api/v2/query/records/advanced?lot_no=2507173_02` → `total_count: 0`
2. **資料庫檢查**: V2 表 (`p1_records`, `p2_records`, `p3_records`) 完全空的
3. **發現舊資料**: Legacy 表 (`records`) 有 3 筆測試資料
4. **前端路由**: 前端呼叫 `/api/v2/query/records` (V2 API)

**結論**: 前端改用 V2 API，但資料還在 Legacy 表，兩者未同步。

## ✅ 解決方案

### 已完成

- [x] 清空 Legacy 表測試資料 (`TRUNCATE TABLE records CASCADE`)
- [x] 確認 V2 表結構正確
- [x] 確認 Tenant 已配置 (Default Tenant: ee5e3236-3c60-4e49-ad7c-5b36a12e6d8c)
- [x] 定位原始 CSV 檔案:
  - P1: `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv`
  - P2: `C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P2_2507173_02.csv`

### 待執行 (建議使用前端 UI)

#### 方案 A: 使用前端上傳 UI (推薦)

1. 開啟 http://localhost:18003
2. 進入「資料匯入」頁面
3. 依序上傳:
   - **P1_2507173_02.csv** (table_code: P1)
   - **P2_2507173_02.csv** (table_code: P2)
4. 等待處理完成
5. 返回查詢頁面驗證

#### 方案 B: 使用 API 匯入 (開發用)

```powershell
# 使用 curl (Windows)
curl -X POST "http://localhost:18002/api/v2/import/jobs" `
  -F "table_code=P1" `
  -F "files=@C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv"

# 檢查任務狀態
curl "http://localhost:18002/api/v2/import/jobs/{job_id}"
```

## 🔍 驗證步驟

### 1. 檢查資料表記錄數

```bash
docker exec form_analysis_db psql -U app -d form_analysis_db -c "
SELECT 
  'p1_records' as table, COUNT(*) as count FROM p1_records
UNION ALL
SELECT 'p2_records', COUNT(*) FROM p2_records
UNION ALL
SELECT 'p3_records', COUNT(*) FROM p3_records;
"
```

**預期結果**:
- p1_records: 1 筆 (批號 2507173_02)
- p2_records: 20 筆 (winder 1-20)
- p3_records: 0 筆 (尚未匯入)

### 2. 測試 V2 API

```powershell
Invoke-RestMethod -Uri "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02"
```

**預期結果**:
```json
{
  "total_count": 2,  // P1 + P2 (merged)
  "records": [
    {"data_type": "P1", "lot_no": "2507173_02", ...},
    {"data_type": "P2", "lot_no": "2507173_02", "additional_data": {"rows": [...]}}
  ]
}
```

### 3. 前端驗證

開啟 http://localhost:18003 → 查詢批號 `2507173_02`

**檢查清單**:
- [ ] P1 資料顯示正確
- [ ] P2 資料顯示為表格 (20 rows)
- [ ] P2 表格可排序
- [ ] 欄位名稱正確顯示

## 📋 資料匯入狀態

| 批號 | P1 | P2 | P3 | 狀態 |
|------|----|----|----| -----|
| 2507173_02 | ⏳ 待匯入 | ⏳ 待匯入 | 無檔案 | 待處理 |

## 🔧 相關檔案

### 文件
- [fix-data-migration.md](./fix-data-migration.md) - 完整修復文件
- [0113-tenant-solution.md](../dev-docs/2025-01/0113-tenant-solution.md) - Tenant 配置解決方案
- [0113-p2-display-fix.md](../dev-docs/2025-01/0113-p2-display-fix.md) - P2 顯示修正技術文件

### 腳本
- [reimport-data.ps1](./reimport-data.ps1) - 自動化匯入腳本 (編碼問題待修正)
- [import-p1.ps1](./import-p1.ps1) - P1 單獨匯入 (路徑問題待修正)
- [test-p2-display.ps1](./test-p2-display.ps1) - P2 顯示測試

### API 端點
- `POST /api/v2/import/jobs` - 建立匯入任務
- `GET /api/v2/import/jobs/{id}` - 查詢任務狀態
- `POST /api/v2/import/jobs/{id}/commit` - 提交批次資料
- `GET /api/v2/query/records/advanced` - 查詢記錄 (V2)

## 🚀 後續步驟

1. **立即執行**: 使用前端 UI 匯入 P1 和 P2 資料
2. **驗證**: 確認 API 和前端都能正確顯示
3. **測試 P2 顯示**: 執行 `test-p2-display.ps1` 確認結構正確
4. **更新 TODO**: 標記 P2 顯示問題已解決
5. **文檔更新**: 完成 0113-work-summary.md

## ⚠️ 重要提醒

1. **不要使用 Legacy API**: `/api/query` 已移除，請使用 `/api/v2/*`
2. **Tenant 已配置**: 無需手動指定 tenant_id，系統自動使用 Default Tenant
3. **匯入順序**: 必須先匯入 P1，再匯入 P2/P3 (因有外鍵關聯)
4. **P2 結構已修正**: 後端會自動將 20 個 winders 合併為 rows 陣列
