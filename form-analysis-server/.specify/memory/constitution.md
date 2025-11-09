# Form Analysis Server Constitution

## Core Principles

### I. Spec-Driven Development (SDD) 流程
規格→計畫→任務→實作的開發流程。每個 PR 必須對應明確的任務 ID。不允許跳過規格直接開發。所有功能變更都要先更新 spec.md，經確認後才進入實作階段。

### II. 前後端分離架構 (NON-NEGOTIABLE)
後端：FastAPI + PostgreSQL + Alembic migrations。前端：TypeScript + 現代前端框架。通過 Docker Compose 統一啟動。後端只提供 API，不處理前端路由或靜態檔案。

### III. 程式碼品質標準
Python：ruff + black + mypy，pre-commit 強制執行。TypeScript：eslint + prettier，同樣設 pre-commit。所有程式碼必須通過 lint 檢查才能合併。設定檔統一放在專案根目錄。

### IV. 測試與 CI/CD
pytest + coverage (後端)，vitest (前端)。主分支必跑 CI：lint → type-check → test。覆蓋率低於 80% 不可合併。所有 API 端點需有集成測試。

### V. 可觀測性與記錄
FastAPI 中介層記錄：request_id、API 路徑、回應時間、錯誤堆疊。DB 查詢時間監控。Log 級別：DEBUG (開發)、INFO (一般操作)、WARN (潛在問題)、ERROR (系統錯誤)。

## 技術規範與安全

### 版本管理
語義化版本號 (MAJOR.MINOR.PATCH)。每個 PR 必須包含 CHANGELOG 條目。Breaking changes 只能在 MAJOR 版本。向後相容：API 調整以別名方式提供舊介面，舊行為保留至下一 minor 版才移除。

### 安全與設定管理
環境變數使用 .env (不入庫) 和 .env.local。密碼、Token、API Key 統一走 Secret Manager 或 .env.local。永不在程式碼中硬編碼敏感資訊。生產環境變數通過 CI/CD pipeline 注入。

### Docker 與部署
docker-compose.yml 提供完整開發環境 (DB + Backend + Frontend)。Dockerfile 多階段構建。healthcheck 端點必須實作。container 啟動順序：DB → migrate → backend → frontend。

## 開發工作流程

### PR 與 Code Review
每個 PR 對應一個任務，包含：任務 ID、變更說明、測試結果、DoD 檢查表。至少一人 approve 才可合併。CI 全數通過是合併的必要條件。

### 文件與 DoD
README.md 必須包含：一鍵啟動指令、系統架構圖、API 規格連結、常見問題。每個任務都要有明確的完成定義 (Definition of Done)。API 變更需同步更新 OpenAPI 文件。

### 資料庫變更
所有 schema 變更必須通過 Alembic migration。Migration 檔案需包含 upgrade 和 downgrade。測試環境先驗證 migration，確認無誤後才部署到生產環境。

## Governance

### 憲章執行
本憲章優先於所有其他開發慣例。所有 PR review 必須驗證憲章合規性。違反憲章的程式碼不得合併，除非有技術負責人書面核准並記錄例外原因。

### 憲章修訂
修訂憲章需要：(1) 技術影響分析 (2) 團隊討論與共識 (3) 遷移計畫 (4) 更新相關工具設定。修訂後需通知全體開發者並更新相關文件。

### 工具與自動化
pre-commit hooks、CI pipelines、linting rules 都必須與憲章保持一致。工具設定變更需同步更新憲章。推薦使用 GitHub Actions 或類似 CI/CD 工具強制執行品質門檻。

**Version**: 1.0.0 | **Ratified**: 2025-11-08 | **Last Amended**: 2025-11-08
