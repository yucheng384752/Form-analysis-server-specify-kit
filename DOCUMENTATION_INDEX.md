# 文件索引（依存放/使用優先級排序）

本文件用來快速找到專案內的 Markdown 文件，並依「最常用/最應該先看」→「次要/歷史紀錄」排序。

## P0：入口（先看）

- [README.md](README.md)（專案總覽/快速入口）
- [getting-started/QUICK_START.md](getting-started/QUICK_START.md)（最快啟動）
- [getting-started/MANUAL_STARTUP_GUIDE.md](getting-started/MANUAL_STARTUP_GUIDE.md)（手動啟動流程）
- [getting-started/POSTGRESQL_SETUP.md](getting-started/POSTGRESQL_SETUP.md)（資料庫安裝/設定）
- [getting-started/DBEAVER_CONNECTION_GUIDE.md](getting-started/DBEAVER_CONNECTION_GUIDE.md)（DB GUI 連線）

## P1：開發指南（規格/設計/待辦）

- [dev-guides/PROJECT_OVERVIEW.md](dev-guides/PROJECT_OVERVIEW.md)
- [dev-guides/PRD.md](dev-guides/PRD.md)
- [dev-guides/PRD2.md](dev-guides/PRD2.md)
- [dev-guides/API_DESIGN_EXPLANATION.md](dev-guides/API_DESIGN_EXPLANATION.md)
- [dev-guides/USER_UPLOAD_FLOW.md](dev-guides/USER_UPLOAD_FLOW.md)（使用者上傳流程：狀態機/UI 提示/驗證）
- [dev-guides/USER_QUERY_FLOW.md](dev-guides/USER_QUERY_FLOW.md)（使用者查詢流程：UI 提示/驗證/追溯）
- [dev-guides/NEW_FORM_ADAPTATION_GUIDE.md](dev-guides/NEW_FORM_ADAPTATION_GUIDE.md)
- [dev-guides/LOGGING_GUIDE.md](dev-guides/LOGGING_GUIDE.md)
- [dev-guides/FRONTEND_DATE_DISPLAY_GUIDE.md](dev-guides/FRONTEND_DATE_DISPLAY_GUIDE.md)
- [dev-guides/IMPLEMENTATION_PLAN_V2.md](dev-guides/IMPLEMENTATION_PLAN_V2.md)
- [dev-guides/IMPLEMENTATION_PLAN_V2_1.md](dev-guides/IMPLEMENTATION_PLAN_V2_1.md)
- [dev-guides/STARTUP_SCRIPT_FEATURES.md](dev-guides/STARTUP_SCRIPT_FEATURES.md)
- [dev-guides/RESTRUCTURE_PLAN.md](dev-guides/RESTRUCTURE_PLAN.md)
- [dev-guides/TODO_IN_20251229.md](dev-guides/TODO_IN_20251229.md)

## P1：服務內文件（form-analysis-server 子專案）

- [form-analysis-server/README.md](form-analysis-server/README.md)
- [form-analysis-server/backend/README.md](form-analysis-server/backend/README.md)
- [form-analysis-server/backend/DATABASE_SETUP.md](form-analysis-server/backend/DATABASE_SETUP.md)
- [form-analysis-server/backend/tests/README.md](form-analysis-server/backend/tests/README.md)

## P1：資料遷移

- [migrations/MIGRATION_GUIDE.md](migrations/MIGRATION_GUIDE.md)

## P2：內部開發紀錄（可參考，但通常不是入口）

- [dev-docs/README.md](dev-docs/README.md)

### dev-docs/2025-01
- [dev-docs/2025-01/0113-test-report.md](dev-docs/2025-01/0113-test-report.md)（Product_ID 解析與 P2 查詢優化測試報告）

### dev-docs/2025-11
- [dev-docs/2025-11/LOG_AND_DATABASE_FIX_SUMMARY.md](dev-docs/2025-11/LOG_AND_DATABASE_FIX_SUMMARY.md)
- [dev-docs/2025-11/LOG_MANAGEMENT_IMPLEMENTATION_SUMMARY.md](dev-docs/2025-11/LOG_MANAGEMENT_IMPLEMENTATION_SUMMARY.md)
- [dev-docs/2025-11/UPLOAD_FUNCTION_TEST_REPORT.md](dev-docs/2025-11/UPLOAD_FUNCTION_TEST_REPORT.md)

### dev-docs/2025-12
- [dev-docs/2025-12/API_PREFIX_FIX_REPORT.md](dev-docs/2025-12/API_PREFIX_FIX_REPORT.md)
- [dev-docs/2025-12/BATCH_IMPORT_ERROR_FIX_REPORT.md](dev-docs/2025-12/BATCH_IMPORT_ERROR_FIX_REPORT.md)
- [dev-docs/2025-12/DATA_LOSS_BUG_FIX.md](dev-docs/2025-12/DATA_LOSS_BUG_FIX.md)
- [dev-docs/2025-12/DATABASE_FIELD_FIX_REPORT.md](dev-docs/2025-12/DATABASE_FIELD_FIX_REPORT.md)
- [dev-docs/2025-12/DATABASE_MIGRATION_ERROR_FIX_REPORT.md](dev-docs/2025-12/DATABASE_MIGRATION_ERROR_FIX_REPORT.md)
- [dev-docs/2025-12/DEPLOYMENT_GUIDE.md](dev-docs/2025-12/DEPLOYMENT_GUIDE.md)
- [dev-docs/2025-12/FEATURE_REQUIREMENTS_ANALYSIS.md](dev-docs/2025-12/FEATURE_REQUIREMENTS_ANALYSIS.md)
- [dev-docs/2025-12/FEATURE_REQUIREMENTS_V2.md](dev-docs/2025-12/FEATURE_REQUIREMENTS_V2.md)
- [dev-docs/2025-12/FILE_ORGANIZATION.md](dev-docs/2025-12/FILE_ORGANIZATION.md)
- [dev-docs/2025-12/FINAL_PORT_TEST_REPORT.md](dev-docs/2025-12/FINAL_PORT_TEST_REPORT.md)
- [dev-docs/2025-12/FRONTEND_CONNECTION_FIX_REPORT.md](dev-docs/2025-12/FRONTEND_CONNECTION_FIX_REPORT.md)
- [dev-docs/2025-12/PORT_CONFLICT_FIX_REPORT.md](dev-docs/2025-12/PORT_CONFLICT_FIX_REPORT.md)
- [dev-docs/2025-12/PORT_CONFLICT_RESOLUTION_REPORT.md](dev-docs/2025-12/PORT_CONFLICT_RESOLUTION_REPORT.md)
- [dev-docs/2025-12/PRODUCT_ID_SEARCH_IMPLEMENTATION.md](dev-docs/2025-12/PRODUCT_ID_SEARCH_IMPLEMENTATION.md)
- [dev-docs/2025-12/README_PORT_FIX_REPORT.md](dev-docs/2025-12/README_PORT_FIX_REPORT.md)
- [dev-docs/2025-12/SCRIPT_COMPARISON_ANALYSIS.md](dev-docs/2025-12/SCRIPT_COMPARISON_ANALYSIS.md)
- [dev-docs/2025-12/SYSTEM_REQUIREMENTS.md](dev-docs/2025-12/SYSTEM_REQUIREMENTS.md)
- [dev-docs/2025-12/SYSTEM_STARTUP_SUCCESS_REPORT.md](dev-docs/2025-12/SYSTEM_STARTUP_SUCCESS_REPORT.md)

## P3：Spec 工具/提示文件（通常不用改）

- [form-analysis-server/specs/master/spec.md](form-analysis-server/specs/master/spec.md)
- [form-analysis-server/specs/master/plan.md](form-analysis-server/specs/master/plan.md)
- [form-analysis-server/specs/master/tasks.md](form-analysis-server/specs/master/tasks.md)
- [form-analysis-server/.specify/memory/constitution.md](form-analysis-server/.specify/memory/constitution.md)

## P3：project-reports（歷史報告/驗證紀錄）

- [project-reports/ASYNC_TESTS_COMPLETION_REPORT.md](project-reports/ASYNC_TESTS_COMPLETION_REPORT.md)
- [project-reports/BACKEND_COMPLETION_REPORT.md](project-reports/BACKEND_COMPLETION_REPORT.md)
- [project-reports/COMBINED_VALIDATION_REPORT.md](project-reports/COMBINED_VALIDATION_REPORT.md)
- [project-reports/CONFIG_FIX_REPORT.md](project-reports/CONFIG_FIX_REPORT.md)
- [project-reports/CSV_FOLDER_VALIDATION_REPORT.md](project-reports/CSV_FOLDER_VALIDATION_REPORT.md)
- [project-reports/DOCKER_REBUILD_TEST_REPORT.md](project-reports/DOCKER_REBUILD_TEST_REPORT.md)
- [project-reports/FINAL_SYSTEM_VERIFICATION_REPORT.md](project-reports/FINAL_SYSTEM_VERIFICATION_REPORT.md)
- [project-reports/FRONTEND_AND_DATE_FIX_REPORT.md](project-reports/FRONTEND_AND_DATE_FIX_REPORT.md)
- [project-reports/FRONTEND_FIXES_IMPLEMENTATION_REPORT.md](project-reports/FRONTEND_FIXES_IMPLEMENTATION_REPORT.md)
- [project-reports/INTEGRATION_TEST_REPORT.md](project-reports/INTEGRATION_TEST_REPORT.md)
- [project-reports/LOGGING_IMPLEMENTATION_REPORT.md](project-reports/LOGGING_IMPLEMENTATION_REPORT.md)
- [project-reports/LOT_NO_VALIDATION_FIX_REPORT.md](project-reports/LOT_NO_VALIDATION_FIX_REPORT.md)
- [project-reports/P3_CHECK_09_ANALYSIS.md](project-reports/P3_CHECK_09_ANALYSIS.md)
- [project-reports/P3_ITEMS_ERROR_REPORT.md](project-reports/P3_ITEMS_ERROR_REPORT.md)
- [project-reports/P3_ITEMS_IMPLEMENTATION_SUMMARY.md](project-reports/P3_ITEMS_IMPLEMENTATION_SUMMARY.md)
- [project-reports/P3_ITEMS_MIGRATION_COMPLETION_REPORT.md](project-reports/P3_ITEMS_MIGRATION_COMPLETION_REPORT.md)
- [project-reports/P3_ITEMS_TEST_REPORT.md](project-reports/P3_ITEMS_TEST_REPORT.md)
- [project-reports/P3_ITEMS_TEST_SUMMARY.md](project-reports/P3_ITEMS_TEST_SUMMARY.md)
- [project-reports/P3_LOT_NO_FIX_TEST_REPORT.md](project-reports/P3_LOT_NO_FIX_TEST_REPORT.md)
- [project-reports/P3_LOT_NO_FLEXIBLE_HANDLING_REPORT.md](project-reports/P3_LOT_NO_FLEXIBLE_HANDLING_REPORT.md)
- [project-reports/STARTUP_FIX_REPORT.md](project-reports/STARTUP_FIX_REPORT.md)
- [project-reports/TODO_ANALYSIS_REPORT.md](project-reports/TODO_ANALYSIS_REPORT.md)
