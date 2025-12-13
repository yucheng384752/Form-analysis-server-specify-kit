# 開發與維護文件

本資料夾包含系統開發過程中的各種技術文件、錯誤修復報告、功能實作分析等。

## 資料夾結構

```
dev-docs/
├── 2025-11/          # 2025年11月文件
│   ├── LOG_AND_DATABASE_FIX_SUMMARY.md
│   ├── LOG_MANAGEMENT_IMPLEMENTATION_SUMMARY.md
│   └── UPLOAD_FUNCTION_TEST_REPORT.md
│
└── 2025-12/          # 2025年12月文件
    ├── API_PREFIX_FIX_REPORT.md
    ├── BATCH_IMPORT_ERROR_FIX_REPORT.md
    ├── DATA_LOSS_BUG_FIX.md
    ├── DATABASE_FIELD_FIX_REPORT.md
    ├── DATABASE_MIGRATION_ERROR_FIX_REPORT.md
    ├── DEPLOYMENT_GUIDE.md
    ├── FEATURE_REQUIREMENTS_ANALYSIS.md
    ├── FEATURE_REQUIREMENTS_V2.md
    ├── FILE_ORGANIZATION.md
    ├── FINAL_PORT_TEST_REPORT.md
    ├── FRONTEND_CONNECTION_FIX_REPORT.md
    ├── PORT_CONFLICT_FIX_REPORT.md
    ├── PORT_CONFLICT_RESOLUTION_REPORT.md
    ├── PRODUCT_ID_SEARCH_IMPLEMENTATION.md
    ├── README_PORT_FIX_REPORT.md
    ├── SCRIPT_COMPARISON_ANALYSIS.md
    ├── SYSTEM_REQUIREMENTS.md
    └── SYSTEM_STARTUP_SUCCESS_REPORT.md
```

## 文件分類

### 錯誤修復報告
- API_PREFIX_FIX_REPORT.md - API 前綴修正
- BATCH_IMPORT_ERROR_FIX_REPORT.md - 批次匯入錯誤修復
- DATA_LOSS_BUG_FIX.md - 資料遺失問題修復
- DATABASE_FIELD_FIX_REPORT.md - 資料庫欄位修正
- DATABASE_MIGRATION_ERROR_FIX_REPORT.md - 資料庫遷移錯誤修復
- FRONTEND_CONNECTION_FIX_REPORT.md - 前端連線問題修復
- PORT_CONFLICT_FIX_REPORT.md - 端口衝突修復
- README_PORT_FIX_REPORT.md - README 端口配置修正

### 系統配置與部署
- DEPLOYMENT_GUIDE.md - 部署指南
- SYSTEM_REQUIREMENTS.md - 系統需求說明
- SYSTEM_STARTUP_SUCCESS_REPORT.md - 系統啟動成功報告
- PORT_CONFLICT_RESOLUTION_REPORT.md - 端口衝突解決方案

### 功能需求與實作分析
- FEATURE_REQUIREMENTS_ANALYSIS.md - 功能需求分析
- FEATURE_REQUIREMENTS_V2.md - 功能需求分析 v2
- PRODUCT_ID_SEARCH_IMPLEMENTATION.md - Product ID 搜尋功能實作

### 測試報告
- UPLOAD_FUNCTION_TEST_REPORT.md - 上傳功能測試
- FINAL_PORT_TEST_REPORT.md - 最終端口測試

### 其他技術文件
- FILE_ORGANIZATION.md - 檔案組織結構
- LOG_AND_DATABASE_FIX_SUMMARY.md - 日誌與資料庫修復總結
- LOG_MANAGEMENT_IMPLEMENTATION_SUMMARY.md - 日誌管理實作總結
- SCRIPT_COMPARISON_ANALYSIS.md - 腳本比較分析

## 快速查找

### 需要修復錯誤？
查看 `*_FIX_REPORT.md` 和 `*_BUG_FIX.md` 檔案

### 需要部署系統？
查看 `DEPLOYMENT_GUIDE.md` 和 `SYSTEM_REQUIREMENTS.md`

### 需要實作新功能？
查看 `FEATURE_REQUIREMENTS_*.md` 和 `*_IMPLEMENTATION.md` 檔案

### 需要測試系統？
查看 `*_TEST_REPORT.md` 檔案

---

**文件整理日期**: 2025年12月13日  
**整理說明**: 根據修改日期將開發/維護文件歸檔至對應月份資料夾
