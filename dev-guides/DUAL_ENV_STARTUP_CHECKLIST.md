# 雙環境啟動檢查清單（Demo + Dev）

日期：2026-02-23  
目標：同一台主機上可控地執行「展示環境（demo）」與「開發測試環境（dev）」

## Step 1. 前置檢查
- [ ] Docker / Docker Compose 可用
- [ ] `form-analysis-server/.env.demo` 存在且可讀
- [ ] `form-analysis-server/.env`（作為 dev env）存在且可讀
- [ ] demo/dev ports 不衝突（DB/API/Frontend/pgAdmin）
- [ ] compose 設定允許雙環境併行（特別是 `container_name`）

## Step 2. 啟動 Demo（展示）
- [ ] 執行 `scripts/start-demo.bat`
- [ ] `docker compose --env-file .env.demo ps` 顯示服務正常
- [ ] `GET /healthz` 成功
- [ ] demo 帳號檢查（manager/user）

## Step 3. 啟動 Dev（開發）
- [ ] 用 `.env` 啟動開發環境（不覆蓋 demo）
- [ ] 若需要同機併行，使用獨立 compose project + 不衝突 container 名稱
- [ ] `docker compose ps` 顯示 dev 服務正常
- [ ] `GET /healthz`（dev API）成功

## Step 4. 併行驗證
- [ ] demo 前端/API 可同時存活
- [ ] dev 前端/API 可同時存活
- [ ] demo 不受 dev 改碼影響
- [ ] 服務停止與回復流程可用

## Step 5. 結論
- [ ] 可雙環境併行
- [ ] 僅可單環境運行（需改 compose 後再併行）

---

## 本次執行紀錄（由 Agent 填）
- Step 1:
- Step 2:
- Step 3:
- Step 4:
- Final:

## 本次執行結果（2026-02-23）
- Step 1（前置檢查）：PASS
  - Docker/Compose 可用
  - `.env.demo` 與 `.env` 均存在
  - ports 不衝突（demo: 18101/18102/18103, dev: 18001/18002/18003）
  - 發現阻擋：`docker-compose.yml` 使用固定 `container_name`，不支援同機同時啟兩套
- Step 2（啟動 Demo）：PASS
  - `docker compose --env-file .env.demo up -d --build` 成功
  - demo API `GET /healthz` = 200
  - demo frontend `GET /index.html` = 200
  - `ensure-demo-users.ps1` 驗證通過
- Step 3（啟動 Dev）：FAIL（符合預期阻擋）
  - `docker compose --env-file .env up -d --build` 會重建同名容器，非並行啟動
  - backend 啟動失敗：`password authentication failed for user "app"`
- Step 4（併行驗證）：FAIL
  - 現行 compose 不可雙環境併行
- 最終結論：目前僅可單環境運行；要雙環境併行需先調整 compose（移除/參數化 `container_name`）與資料卷策略。
