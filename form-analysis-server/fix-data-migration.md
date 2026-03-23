# 資料遷移問題修復 (2026-01-13)

## 問題說明

### 資料不一致狀態
- **Legacy 表** (records, p2_items): 有 3 筆測試資料
- **V2 表** (p1_records, p2_records, p3_records): 空的
- **前端**: 呼叫 `/api/v2/query` 查詢 V2 表 → 查無資料

### 根本原因
系統從 Legacy 架構遷移到 V2 架構，但：
1. 舊資料殘留在 Legacy 表
2. V2 表沒有資料
3. 前端已改用 V2 API
4. 查詢流程正確但資料在錯誤的表

## ✅ 解決方案: 使用 V2 匯入流程

### 步驟 1: 清理測試資料

```bash
# 清空 Legacy 表 (保留結構)
docker exec form_analysis_db psql -U app -d form_analysis_db -c "
  TRUNCATE TABLE records CASCADE;
"
```

### 步驟 2: 重新匯入到 V2 表

使用 V2 Import API 匯入原始檔案：

**檔案位置**:
- P1: `c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv`
- P2: `c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P2_2507173_02.csv`
- P3: 尚未找到對應檔案

**匯入順序** (重要):
1. P1 (必須先匯入，包含批號主記錄)
2. P2 (參照 P1 的批號)
3. P3 (參照 P1 的批號)

**API 端點**:
```
POST /api/v2/import/jobs
Content-Type: multipart/form-data

Body:
- table_code: P1 | P2 | P3
- files: <file>
```

### 步驟 3: 驗證資料

```bash
# 檢查 V2 表資料數量
docker exec form_analysis_db psql -U app -d form_analysis_db -c "
  SELECT 
    'p1_records' as table_name, COUNT(*) as count FROM p1_records
  UNION ALL
  SELECT 'p2_records', COUNT(*) FROM p2_records
  UNION ALL
  SELECT 'p3_records', COUNT(*) FROM p3_records;
"

# 測試 V2 API
curl "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02"
```

### 步驟 4: 前端驗證

開啟 http://localhost:18003 並查詢批號 `2507173_02`，確認：
- ✅ P1 資料顯示
- ✅ P2 資料顯示 (20個繞線頭)
- ✅ P3 資料顯示

## 📋 資料遷移檢查清單

- [ ] 清空 Legacy 表測試資料
- [ ] 匯入 P1 資料 (P1_2507173_02.csv)
- [ ] 驗證 P1 匯入成功
- [ ] 匯入 P2 資料 (P2_2507173_02.csv)
- [ ] 驗證 P2 匯入成功 (應有 20 筆 p2_records)
- [ ] 尋找並匯入 P3 資料
- [ ] API 測試通過
- [ ] 前端查詢測試通過

## 🔍 診斷指令

```bash
# 查看所有表記錄數
docker exec form_analysis_db psql -U app -d form_analysis_db -c "
  SELECT schemaname, tablename, n_live_tup as row_count 
  FROM pg_stat_user_tables 
  WHERE tablename IN ('records', 'p1_records', 'p2_records', 'p3_records', 'p2_items', 'p3_items')
  ORDER BY tablename;
"

# 查看匯入任務
docker exec form_analysis_db psql -U app -d form_analysis_db -c "
  SELECT id, table_code, status, total_rows, valid_rows, created_at 
  FROM import_jobs 
  ORDER BY created_at DESC 
  LIMIT 5;
"
```

## 📌 注意事項

1. **不要刪除 Legacy 表**: 保留結構以防回退需求
2. **Tenant 已配置**: Default Tenant (ee5e3236-3c60-4e49-ad7c-5b36a12e6d8c) 已建立
3. **V2 Import 自動關聯 Tenant**: 匯入時會自動使用 Default Tenant
4. **P2 結構已修正**: _merge_p2_records() 已改為 rows 格式

## 🚀 後續步驟

完成資料遷移後:
1. 測試 P2 顯示功能 (使用 test-p2-display.ps1)
2. 驗證前端表格顯示正確
3. 更新 TODO 清單標記 P2 問題已解決
