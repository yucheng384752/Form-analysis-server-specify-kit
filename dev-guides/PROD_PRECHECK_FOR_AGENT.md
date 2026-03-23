# 正式版上線前檢查表（for Agent）

版本：v1  
更新日期：2026-02-23  
適用範圍：Form-analysis-server demo 轉正式版（受控上線）

## A. 上線門檻（Go / No-Go）
- [ ] `SMOKE_TEST_DEMO.md` 全數測項執行完成，且 `TC01~TC09` 全 PASS。
- [ ] 日期區間查詢回歸測試 PASS（`test_query_dynamic_date_range_strict.py`）。
- [ ] 角色權限驗證完成（manager 可用、user 無管理權限）。
- [ ] demo 專用環境可一鍵啟停（`scripts/start-demo.bat` / `scripts/stop-demo.bat`）。
- [ ] 若任一項未達標，結論必須是 `No-Go`。

## B. 環境與設定檢查
- [ ] 使用 `form-analysis-server/.env.demo`，且與開發環境 port 不衝突。
- [ ] 必填路徑有效：`SEPTEMBER_V2_HOST_PATH`、`ANALYTICAL_FOUR_HOST_PATH`。
- [ ] 高風險密鑰已替換：`POSTGRES_PASSWORD`、`SECRET_KEY`、`ADMIN_API_KEYS`。
- [ ] `VITE_API_URL` 指向 demo API（例：`http://localhost:18102`）。

## C. 資料與凍結檢查
- [ ] demo 測資文件已凍結：`dev-guides/DEMO_FIXED_TEST_DATA_AUG_SEP.md`。
- [ ] 匯入工作 ID 已記錄且可追溯（P1/P2/P3）。
- [ ] 測資版本號已標記（例：`v1`），未經變更審核不得直接覆寫。

## D. 帳號與權限檢查
- [ ] tenant `demo` 存在。
- [ ] `demo_manager` 存在且角色為 `manager`。
- [ ] `demo_user` 存在且角色為 `user`。
- [ ] manager/user 帳號可登入，錯誤密碼可被正確拒絕（401）。

## E. 查詢與功能檢查
- [ ] Analytical-Four 單筆 product_id 查詢正常。
- [ ] 多筆 product_id 查詢在可接受頻率下可回應。
- [ ] 進階查詢可回傳 P1/P2/P3 對應欄位。
- [ ] 日期區間 `2025-08-01 ~ 2025-09-30` 僅回傳區間內資料。

## F. 風險與限制（需明確告知）
- [ ] 已對外說明 rate limit：`Max 30 requests per minute`。
- [ ] 已告知示範版本為「受控正式版（Pilot）」範圍與邊界。
- [ ] 已定義發生查詢異常時的回滾方案（回滾資料/回滾版本）。

## G. 交付物檢查
- [ ] `README_DEMO.md` 已更新到最新測試結果與 Step 6 狀態。
- [ ] `SMOKE_TEST_DEMO_RESULT_20260223.md` 與實測結果一致。
- [ ] 已產出 Step 6 凍結文件與 release note。

## H. Agent 執行指令（最小集合）
```bat
scripts\start-demo.bat
```

```bat
scripts\stop-demo.bat
```

```powershell
python -m pytest -q form-analysis-server/backend/tests/api/test_query_dynamic_allowlist.py form-analysis-server/backend/tests/api/test_query_dynamic_date_range_strict.py
```

## I. 最終判定
- [ ] Go
- [ ] No-Go
- 判定者：`<name>`
- 判定時間：`<YYYY-MM-DD HH:mm>`
- 備註：`<risk / rollback / exception>`
