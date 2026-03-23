# Manual / one-off scripts

這個資料夾用來收納 backend 根目錄過去累積的「手動執行、一次性、維運/遷移/分析」腳本。

- 目標：讓 `backend/` 根目錄保持乾淨，避免被 pytest 或 IDE 誤當成正式測試/模組。
- 相容性：原本 `backend/<script>.py` 仍保留 shim，可繼續用 `python <script>.py` 執行。

## 分類（約略）

- analyze_*：分析/統計用
- check_*：資料一致性/重複檢查
- fix_* / repair_*：資料修復
- migrate_* / verify_*：資料或 schema 遷移/驗證
- seed_* / setup_*：初始化/種子資料/環境設定
- simple_* / *_integration_* / manual_test：手動驗證流程
