# Form Analysis Server

## Introduction
工廠使用這個系統管理輸入的csv檔案，並進行資料的即時搜尋

## Objectives 
### 上傳頁面
針對每個動作都顯示toast提示
- 區塊一
  1. 可以使用拖曳上傳與選擇檔案上傳 -> 支援多檔案上傳
  2. 僅支援csv上傳，檔案大小限制10MB
  3. 具有hover提示功能，在上傳區域點擊**開啟檔案選擇**
- 區塊二
  1. 可以看到上傳進度
  2. 顯示**確認驗證**按鈕
  3. 在驗證時顯示進度條(區塊3.1)
  4. 在上傳完成時，按下**確認**進行必要表格驗證
  5. 在驗證時，要鎖定驗證按鈕
  6. 在顯示檔案的區塊要有**取消(X)**按鈕可以刪除上傳檔案
- 區塊三
  1. 顯示csv內容編輯(固定標題欄、右側滑桿、下方滑桿)
  2. 儲存格會**根據最長的欄位**動態同步所有表格的寬度
  3. 提供 **儲存修改**、**確認匯入** 按鈕
  4. 根據上傳的資料提供提示訊息: 共 X 行資料，Y 個欄位；提示：點擊任意儲存格即可直接編輯內容
  5. 在儲存修改前，無法按下確認匯入按鈕
  6. 按下**確認匯入**按鈕時，顯示彈窗:  是否確認上傳；此操作將會把 CSV 檔案匯入資料庫中，請確認是否要繼續？
  7. 匯入資料庫時顯示進度條
  8. 可以先搜尋資料庫是否有相同lot_no以及Phase的資料，有的話要提示User
  9. 匯入完畢後，更新頁面，回到最初的畫面

### 查詢頁面
- 區塊一
  1. 輸入lot_no(支援模糊搜尋)
  2. 根據搜尋到的結果，顯示P1、P2、P3分頁(不論是否有資料)
- 區塊二
  1. 根據**自定義**的表格顯示規則分成數個區塊(根據客戶需要)(區塊2.1, 2.2, 2.3 ...)

# 實作方案

### 生產日期提取邏輯 已完成
已建立 production_date_extractor.py 服務並整合到 routes_import.py：
- P1: 從 "Production Date" 提取，支援 YYYY-MM-DD、YYMMDD、YY-MM-DD
- P2: 從 "分條時間" 提取，支援民國年格式 YYY/MM/DD、YYY-MM-DD、YYYMMDD
- P3: 從 "year-month-day" 提取，支援 "114年09月02日"、YYY/MM/DD
- 所有格式統一轉換為 date 物件儲存到 production_date 欄位

### 部署步驟

#### 1. 重建 Docker 映像（如使用 Docker）
```bash
cd form-analysis-server
docker-compose down
docker-compose build
docker-compose up -d
```

#### 2. 或直接重啟後端服務（本地開發）
```bash
cd form-analysis-server/backend
# 停止現有服務
# 重新啟動
python -m uvicorn app.main:app --reload --port 18002
```

#### 3. 測試新功能
上傳一個 P2 或 P3 檔案，確認：
- production_date 欄位正確填入
- 民國年正確轉換為西元年
- P1 的日期正確解析

### 使用範例
```python
# P1 範例
production_date = production_date_extractor.extract_production_date(
    row_data={'additional_data': {'Production Date': '2024-01-15'}},
    data_type='P1'
)  # 結果: date(2024, 1, 15)

# P2 範例（民國年）
production_date = production_date_extractor.extract_production_date(
    row_data={'additional_data': {'分條時間': '114/09/02'}},
    data_type='P2'
)  # 結果: date(2025, 9, 2)

# P3 範例（中文格式）
production_date = production_date_extractor.extract_production_date(
    row_data={'additional_data': {'year-month-day': '114年09月02日'}},
    data_type='P3'
)  # 結果: date(2025, 9, 2)
```

## 技術分析備註
### #1 P1/P2 Material 關聯
-  兩者都使用 material_code 欄位
-  有效材料：H2, H5, H8
-  可透過 lot_no + material_code 追溯關聯

### #2 Quality Inspection/Control
-  P2 欄位，品檢品管人員輸入
-  儲存在 additional_data JSONB
-  無需建立從表

### #3 Slitting Machine 轉換
-  後端對應表: {1: "分1Points 1", 2: "分2Points 2"}
-  前端已實作 formatFieldValue 轉換

### #5 Product_ID 組合邏輯
- 格式: YYYY-MM-DD_機台_模具號碼_LOT
- 範例: 2025-09-02_P24_238-2_301
-  後端產生器已實作
-  進階搜尋已支援
- 前端顯示位置需確認

### 進階搜尋策略
- 建議：除批號外，其他搜尋以P3為主
- 實作：P3 → lot_no/winder → P2 → P1 追溯鏈