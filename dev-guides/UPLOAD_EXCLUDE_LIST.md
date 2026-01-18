# 不建議上傳/交付的檔案清單（建議排除）

這份清單用來協助你在「部署交付 / 上傳壓縮檔 / 提供給外部」時，避免把不必要、或可能包含環境資訊的檔案一起帶出去。

> 原則：**交付只包含可重建的原始碼 + 必要設定範本**。其餘能靠 build/test 產生的、或屬於本機環境/資料/紀錄的，一律排除。

## 1) 開發文件 / TODO / 變更紀錄（非執行必要）

- `dev-docs/`
- `dev-guides/`
- `DOCUMENTATION_INDEX.md`
- `README.md`（通常可保留；若交付對象不需要也可排除）
- `**/TODO*.md`、`**/*PLAN*.md`、`**/*SUMMARY*.md`、`**/*REPORT*.md`
- `project-reports/`

## 2) 測試資料 / 範例資料 / 匯入用 CSV（避免誤上傳客戶資料）

- `test-data/`
- `uploads/`（本機上傳暫存/測試檔）
- `logs/`
- `form-analysis-server/_import_test_*.csv`
- 任何客戶/生產資料（例如 workspace 內的 `侑特資料/`）

## 3) 本機環境/產物（可由 build 產生）

- Python：`.venv/`, `**/__pycache__/`, `**/*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- Node：`**/node_modules/`, `**/dist/`, `**/build/`, `**/.vite/`, `**/.next/`
- 通用：`**/*.log`, `**/*.tmp`, `**/*.bak`

## 4) IDE/工具設定（每人不同）

- `.vscode/`（除非你有特別要交付 tasks/launch 設定）
- `**/*.code-workspace`

## 5) 機密/環境設定（避免洩漏）

- `.env`, `.env.*`（建議只交付 `.env.example`）
- 任何 `*_key*`, `*secret*`, `*token*` 類檔案（含測試用也不建議對外）

## 6) 什麼應該保留？（最小可執行集合）

- 後端原始碼：`form-analysis-server/backend/`
- 前端原始碼：`form-analysis-server/frontend/`
- DB init：`form-analysis-server/backend/init.sql`
- Docker / Compose：`form-analysis-server/docker-compose.yml`、`form-analysis-server/backend/Dockerfile`、`form-analysis-server/frontend/Dockerfile`
- 需要的 scripts（例如啟動/監控、資料匯入工具）：`form-analysis-server/scripts/`（但仍建議排除任何含客戶資料的輸入檔）

---

如果你的「上傳」指的是 Docker build context，建議搭配 `.dockerignore` 進一步排除以上項目；如果是交付 zip 給外部，建議用壓縮腳本明確列白名單（allow-list）。
