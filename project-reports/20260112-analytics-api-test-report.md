# Analytics API 測試報告
**測試日期**: 2026-01-12  
**API 版本**: v2.0  
**測試環境**: Docker (localhost:18002)

---

## 📊 測試執行摘要

| 項目 | 數量 | 比例 |
|------|------|------|
| **總測試數** | 8 | 100% |
| **通過** | 4 | 50% |
| **失敗** | 3 | 37.5% |
| **警告** | 1 | 12.5% |
| **總耗時** | 1.54秒 | - |

---

## 通過的測試 (4/8)

### 1. 健康檢查 (Health Check)
- **狀態**: PASS
- **結果**: `status: healthy`
- **配置資訊**:
  - Max Records: 1500/request
  - Rate Limit: 30/min
  - Auto Gzip: 200 筆閾值
  - Null Handling: explicit
  - Empty Array Handling: preserve

### 2. 邊界測試 - 無效年份 (Invalid Year)
- **狀態**: PASS
- **測試條件**: `year=1900`
- **預期行為**: 拒絕請求 (HTTP 422)
- **實際結果**: 正確拒絕，回傳 HTTP 422

### 3. 邊界測試 - 無效月份 (Invalid Month)
- **狀態**: PASS
- **測試條件**: `month=13`
- **預期行為**: 拒絕請求 (HTTP 422)
- **實際結果**: 正確拒絕，回傳 HTTP 422

### 4. 邊界測試 - 缺少參數 (Missing Parameter)
- **狀態**: PASS
- **測試條件**: 僅提供 `year` 參數，缺少 `month`
- **預期行為**: 拒絕請求 (HTTP 422)
- **實際結果**: 正確拒絕，回傳 HTTP 422

---

## ❌ 失敗的測試 (3/8)

### 1. 單 Server 呼叫單月內容 (2025年9月)
- **狀態**: ❌ FAIL
- **錯誤**: HTTP 500 Internal Server Error
- **根本原因**: 
  ```
  AttributeError: type object 'P3Record' has no attribute 'timestamp'
  ```
- **問題分析**:
  - 服務層程式碼使用 `P3Record.timestamp` 查詢
  - 實際 P3Record 模型使用 `production_date_yyyymmdd` (Integer YYYYMMDD 格式)
  - 需修正欄位映射與查詢邏輯

### 2. 模擬 3 Server 並發呼叫
- **狀態**: ❌ FAIL (0/3 成功)
- **原因**: 與測試 1 相同，API 端點回傳 500 錯誤
- **影響**: 無法測試並發處理能力

### 3. 空資料測試 (Future Date)
- **狀態**: ❌ FAIL
- **錯誤**: HTTP 422 Unprocessable Entity
- **原因**: 
  - 測試使用 `year=2099` (超出 API 限制 2020-2030)
  - 應修改測試條件為有效年份範圍內的無資料月份

---

## ⚠️ 警告的測試 (1/8)

### 1. Rate Limiting 測試
- **狀態**: ⚠️ WARNING
- **測試方式**: 快速發送 35 個連續請求至 `/health` 端點
- **預期行為**: 超過 30 次後應回傳 HTTP 429 (Too Many Requests)
- **實際結果**: 35 個請求全部成功 (HTTP 200)
- **可能原因**:
  1. Rate limiting 邏輯未啟用
  2. 請求間隔過長（健康檢查回應很快）
  3. Rate limit 計數器實作有誤

---

## 🐛 發現的問題

### 問題 1: 資料模型欄位不匹配 (Critical)

**影響範圍**: 所有追溯查詢 API

**錯誤位置**: `app/services/traceability_flattener.py:80`

**錯誤程式碼**:
```python
query = select(P3Record).where(
    and_(
        P3Record.timestamp >= start_date,  # ❌ 錯誤：P3Record 沒有 timestamp
        P3Record.timestamp < end_date
    )
)
```

**正確實作方式**:
```python
# P3Record 使用 production_date_yyyymmdd (Integer YYYYMMDD)
start_yyyymmdd = int(start_date.strftime('%Y%m%d'))
end_yyyymmdd = int(end_date.strftime('%Y%m%d'))

query = select(P3Record).where(
    and_(
        P3Record.production_date_yyyymmdd >= start_yyyymmdd,
        P3Record.production_date_yyyymmdd < end_yyyymmdd
    )
)
```

**修正步驟**:
1. 檢查所有 P1/P2/P3Record 的實際欄位定義
2. 修正 `analytics_field_mapping.py` 中的欄位映射
3. 修正 `traceability_flattener.py` 中的查詢邏輯
4. 處理 YYYYMMDD Integer 與 ISO 8601 datetime 的轉換

---

### 問題 2: Rate Limiting 未觸發

**影響**: 無法防止 API 濫用

**可能原因分析**:

1. **簡易實作的限制**:
   ```python
   # routes_analytics.py 中的 rate limiter 使用內存字典
   _rate_limit_store = {}  # 不支援 Docker 重啟後保留
   ```

2. **計數邏輯問題**:
   - 可能未正確累計請求數
   - 清理過期記錄的邏輯可能過於激進

3. **健康檢查端點可能豁免** (需確認)

**建議修正**:
- 使用 Redis 實作分散式 rate limiting
- 或使用 FastAPI 插件如 `slowapi`
- 添加測試端點專門用於測試 rate limiting

---

### 問題 3: 空資料測試年份超限

**影響**: 測試案例設計不當

**修正**: 使用 `year=2025&month=12` (假設 12 月無資料)

---

## 📋 需要補充的測試

### 未執行的測試項目

1. **Product ID 查詢測試**
   - 狀態: SKIP (因月度查詢失敗，無可用資料)
   - 需修正後重新測試

2. **超過限制筆數測試**
   - 無法完整測試 (需大量測試資料)
   - 建議: 建立測試資料生成腳本

3. **壓縮效果驗證**
   - 未測試實際壓縮率
   - 需檢查 `Content-Encoding: gzip` header
   - 需比較壓縮前後大小

4. **Null 語義驗證**
   - 未驗證缺失欄位是否正確回傳 `null`
   - 需檢查空陣列是否正確保留 `[]`

5. **並發安全性測試**
   - 需驗證 Connection Pool 是否正常運作
   - 需測試資料競爭 (race condition)

---

## 🔧 修正建議

### 優先級 P0 (Critical - 必須立即修正)

1. **修正 P3Record 查詢邏輯**
   - 檔案: `app/services/traceability_flattener.py`
   - 使用 `production_date_yyyymmdd` 取代 `timestamp`
   - 修正 P1Record, P2Record 的時間欄位引用

2. **修正欄位映射表**
   - 檔案: `app/config/analytics_field_mapping.py`
   - 確認所有欄位路徑與實際模型一致
   - 特別注意 `timestamp` vs `created_at` vs `production_date_yyyymmdd`

### 優先級 P1 (High - 影響功能)

3. **修正 Rate Limiting**
   - 選項 A: 使用 `slowapi` 套件
   - 選項 B: 使用 Redis 實作分散式限流
   - 選項 C: 修正現有內存實作的邏輯

4. **補充單元測試**
   - 檔案: `tests/test_analytics_flattener.py` (新建)
   - 測試欄位映射
   - 測試 Null 處理
   - 測試空陣列語義

### 優先級 P2 (Medium - 完善性)

5. **測試資料生成**
   - 建立 2025年9月測試資料（100-200 筆）
   - 確保涵蓋各種情境：
     - 完整資料 (P3→P2→P1 全有)
     - 部分缺失 (P2 或 P1 不存在)
     - 空 extras.rows[]
     - Null 欄位

6. **壓縮效果驗證**
   - 測試 200 筆以上資料的壓縮率
   - 驗證 `Content-Encoding` header
   - 測量實際大小減少比例

---

## 📝 測試環境資訊

```json
{
  "TestDate": "2026-01-12T13:46:52+08:00",
  "Environment": {
    "BaseUrl": "http://localhost:18002",
    "PowerShellVersion": "5.1.22621.4391",
    "Docker": "Running",
    "Containers": {
      "backend": "form_analysis_api (unhealthy → restarted)",
      "database": "form_analysis_db (healthy)",
      "frontend": "form_analysis_frontend (healthy)"
    }
  },
  "API": {
    "Version": "v2.0",
    "Endpoints": [
      "/api/v2/analytics/traceability/health",
      "/api/v2/analytics/traceability/flatten/monthly",
      "/api/v2/analytics/traceability/flatten"
    ]
  }
}
```

---

## 🎯 下一步行動

### 立即行動 (今天完成)

1. 修正 `P3Record.timestamp` → `production_date_yyyymmdd`
2. 修正 P1/P2 時間欄位引用
3. 重新執行測試 1, 2

### 短期行動 (本週完成)

4. 🔄 修正 Rate Limiting 實作
5. 🔄 建立測試資料 (2025年9月)
6. 🔄 補充單元測試

### 長期優化 (下週完成)

7. 📅 壓縮效果驗證與調優
8. 📅 效能基準測試 (Performance Benchmark)
9. 📅 文件完善 (API 使用範例、故障排查指南)

---

## 附錄: 原始測試日誌

測試日誌已儲存至: `./test-results/20260112-analytics-api-test-report.json`

### 測試命令
```powershell
.\test-analytics-api-simple.ps1 -BaseUrl "http://localhost:18002"
```

### 測試輸出摘要
```
=== Analytics API Test Suite ===
Total: 8, Passed: 4, Failed: 3, Warnings: 1
Duration: 1.54 seconds
```

---

**報告產生時間**: 2026-01-12 13:48:00 UTC+8  
**報告版本**: 1.0  
**測試人員**: AI Assistant (GitHub Copilot)
