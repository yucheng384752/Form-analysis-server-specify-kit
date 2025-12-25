# 前端日期顯示格式化指南

**版本**: 1.0  
**日期**: 2025-01-22  
**狀態**:  可實施

---

## 📋 背景說明

### 資料庫現狀

**production_date 欄位**:
- 類型: `DATE`
- 格式: `YYYY-MM-DD` (PostgreSQL 標準格式)
- 覆蓋率: **100%** (所有資料都有值)
  - P1: 8/8 (100%)
  - P2: 6/6 (100%)
  - P3: 5/5 (100%)

**API 輸出範例**:
```json
{
  "id": "uuid-here",
  "lot_no": "2411012_04",
  "data_type": "P1",
  "production_date": "2024-11-01",  // YYYY-MM-DD 格式
  "created_at": "2025-01-22T10:30:00Z"
}
```

### 需求總結

1.  **Data Date**: 直接使用現有的 `production_date` 欄位
2.  **P1 Product Date YYYYMMDD 格式**: 前端顯示時格式化

---

## 🎨 前端實作方案

### 方案 1: JavaScript 格式化（推薦）

#### 格式化函數

```javascript
/**
 * 將 YYYY-MM-DD 格式轉換為 YYYYMMDD
 * @param {string} dateStr - YYYY-MM-DD 格式的日期字串
 * @returns {string} YYYYMMDD 格式的日期字串
 */
function formatDateToYYYYMMDD(dateStr) {
  if (!dateStr) return '';
  // 移除所有連字符
  return dateStr.replace(/-/g, '');
}

// 使用範例
const apiDate = "2024-11-01";
const displayDate = formatDateToYYYYMMDD(apiDate);
console.log(displayDate); // 輸出: "20241101"
```

#### React 組件範例

```jsx
// 函數組件
function ProductionDateDisplay({ productionDate }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return dateStr.replace(/-/g, '');
  };

  return (
    <div className="production-date">
      <label>生產日期:</label>
      <span>{formatDate(productionDate)}</span>
    </div>
  );
}

// 使用
<ProductionDateDisplay productionDate={record.production_date} />
```

#### Vue 組件範例

```vue
<template>
  <div class="production-date">
    <label>生產日期:</label>
    <span>{{ formattedDate }}</span>
  </div>
</template>

<script>
export default {
  props: {
    productionDate: {
      type: String,
      default: ''
    }
  },
  computed: {
    formattedDate() {
      if (!this.productionDate) return '-';
      return this.productionDate.replace(/-/g, '');
    }
  }
}
</script>
```

### 方案 2: 使用日期庫（可選）

如果需要更複雜的日期處理，可以使用日期庫：

#### Day.js

```javascript
import dayjs from 'dayjs';

function formatDateToYYYYMMDD(dateStr) {
  if (!dateStr) return '';
  return dayjs(dateStr).format('YYYYMMDD');
}

// 使用
const displayDate = formatDateToYYYYMMDD("2024-11-01");
console.log(displayDate); // "20241101"
```

#### date-fns

```javascript
import { format, parseISO } from 'date-fns';

function formatDateToYYYYMMDD(dateStr) {
  if (!dateStr) return '';
  return format(parseISO(dateStr), 'yyyyMMdd');
}

// 使用
const displayDate = formatDateToYYYYMMDD("2024-11-01");
console.log(displayDate); // "20241101"
```

---

## 📱 各場景應用

### 1. 資料查詢頁面

**P1 基本資料顯示**:

```javascript
// 原始資料
const record = {
  lot_no: "2411012_04",
  production_date: "2024-11-01",
  data_type: "P1"
};

// 顯示邏輯
const displayFields = {
  "批號": record.lot_no,
  "生產日期": record.production_date.replace(/-/g, ''), // 20241101
  "類型": record.data_type
};
```

**渲染結果**:
```
批號: 2411012_04
生產日期: 20241101
類型: P1
```

### 2. 表格顯示

```javascript
// 表格欄位定義
const columns = [
  { field: 'lot_no', headerName: '批號', width: 150 },
  { 
    field: 'production_date', 
    headerName: '生產日期', 
    width: 120,
    valueFormatter: (params) => {
      return params.value ? params.value.replace(/-/g, '') : '-';
    }
  },
  { field: 'data_type', headerName: '類型', width: 80 }
];
```

### 3. 搜尋條件輸入

**日期範圍選擇器**:

```jsx
function DateRangeFilter({ onFilterChange }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const handleSubmit = () => {
    // 保持 YYYY-MM-DD 格式傳給後端
    onFilterChange({
      start_date: startDate,  // "2024-01-01"
      end_date: endDate       // "2024-12-31"
    });
  };

  return (
    <div className="date-range-filter">
      <input 
        type="date" 
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
      />
      <span>至</span>
      <input 
        type="date" 
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
      />
      <button onClick={handleSubmit}>搜尋</button>
    </div>
  );
}
```

**重要**: 
- 前端顯示用 YYYYMMDD
- 後端 API 傳遞保持 YYYY-MM-DD

### 4. CSV 匯出

```javascript
function exportToCSV(records) {
  const csvData = records.map(record => ({
    '批號': record.lot_no,
    '生產日期': record.production_date.replace(/-/g, ''), // YYYYMMDD
    '產品編號': record.product_id,
    '數量': record.quantity
  }));
  
  // 匯出邏輯...
}
```

---

## 🔄 Data Date (資料日期) 使用方式

### 概念說明

- **created_at**: 記錄進入系統的時間（系統時間戳）
- **production_date**: 資料實際產生的日期（業務日期 = Data Date）

### 前端顯示

**方法 1: 直接使用 production_date**

```javascript
// 不需要額外處理，production_date 就是 data_date
function RecordCard({ record }) {
  return (
    <div className="record-card">
      <div>資料日期: {formatDate(record.production_date)}</div>
      <div>建立時間: {formatDateTime(record.created_at)}</div>
    </div>
  );
}
```

**方法 2: 添加別名顯示**

```javascript
// API 回應處理
function processRecord(record) {
  return {
    ...record,
    data_date: record.production_date  // 添加別名方便理解
  };
}

// 使用
const processedRecord = processRecord(apiRecord);
console.log(processedRecord.data_date);  // "2024-11-01"
```

### 各類型對應關係

| 資料類型 | 來源欄位 | production_date 提取自 |
|---------|---------|----------------------|
| P1 | Production Date | CSV 中的 "Production Date" |
| P2 | 分條時間 | CSV 中的 "分條時間"（民國年轉西元） |
| P3 | year-month-day | CSV 中的 "year-month-day" |

**已完成**: 
-  所有提取邏輯已在 `production_date_extractor.py` 實作
-  已整合到 `routes_import.py`
-  100% 資料覆蓋率

---

## 📊 實際資料驗證

### 資料庫查詢

```sql
-- 檢視各類型的 production_date
SELECT 
  data_type,
  COUNT(*) as total_records,
  COUNT(production_date) as records_with_date,
  MIN(production_date) as earliest_date,
  MAX(production_date) as latest_date
FROM records
GROUP BY data_type;
```

**當前結果**:
```
data_type | total_records | records_with_date | earliest_date | latest_date
----------|---------------|-------------------|---------------|-------------
P1        |            8  |                8  | 2024-xx-xx    | 2025-xx-xx
P2        |            6  |                6  | 2024-xx-xx    | 2025-xx-xx
P3        |            5  |                5  | 2025-xx-xx    | 2025-xx-xx
```

### API 測試

```bash
# 取得記錄
curl http://localhost:18002/api/records/search?lot_no=2411012_04

# 回應
{
  "id": "...",
  "lot_no": "2411012_04",
  "production_date": "2024-11-01",  // 可直接使用
  "data_type": "P1",
  "created_at": "2025-01-22T..."
}
```

---

## 🎯 實作檢查清單

### 前端開發者任務

- [ ] **實作日期格式化函數**
  - [ ] 創建 `formatDateToYYYYMMDD()` 函數
  - [ ] 添加到 utils/dateFormatter.js

- [ ] **更新顯示組件**
  - [ ] P1 生產日期顯示（YYYYMMDD 格式）
  - [ ] P2 分條時間顯示
  - [ ] P3 生產日期顯示

- [ ] **表格欄位格式化**
  - [ ] 查詢結果表格
  - [ ] 高級搜尋結果表格

- [ ] **CSV 匯出**
  - [ ] 確保匯出的日期格式為 YYYYMMDD

- [ ] **測試**
  - [ ] 測試 P1 日期顯示
  - [ ] 測試 P2 日期顯示
  - [ ] 測試 P3 日期顯示
  - [ ] 測試空值處理

### 驗證步驟

1. **顯示驗證**
   - 檢查 P1 記錄的生產日期顯示為 YYYYMMDD
   - 確認無連字符顯示

2. **搜尋驗證**
   - 日期範圍搜尋功能正常
   - 後端仍接收 YYYY-MM-DD 格式

3. **匯出驗證**
   - CSV 匯出的日期格式正確
   - Excel 可正確識別

---

## 💡 最佳實踐

### 1. 保持後端格式統一

** 推薦**:
- 後端始終使用標準 DATE 格式（YYYY-MM-DD）
- 資料庫儲存標準格式
- API 傳輸標準格式

**❌ 不推薦**:
- 在後端添加多種日期格式欄位
- 資料庫儲存字串格式日期

### 2. 前端靈活格式化

** 推薦**:
- 根據不同場景前端格式化
- 使用 computed properties 或 valueFormatter
- 集中管理格式化邏輯

```javascript
// 集中管理
const dateFormatters = {
  display: (date) => date.replace(/-/g, ''),      // YYYYMMDD
  api: (date) => date,                            // YYYY-MM-DD
  readable: (date) => date.replace(/-/g, '/'),   // YYYY/MM/DD
  chinese: (date) => {
    const [y, m, d] = date.split('-');
    return `${y}年${m}月${d}日`;
  }
};
```

### 3. 保持可維護性

```javascript
//  好的做法
const DISPLAY_FORMAT = 'YYYYMMDD';
const formatProductionDate = (date) => date.replace(/-/g, '');

// ❌ 避免硬編碼
const displayDate = record.production_date.replace(/-/g, '');
```

### 4. 處理邊界情況

```javascript
function formatDateToYYYYMMDD(dateStr) {
  // 處理 null/undefined
  if (!dateStr) return '-';
  
  // 驗證格式
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    console.warn('Invalid date format:', dateStr);
    return dateStr;  // 返回原值
  }
  
  return dateStr.replace(/-/g, '');
}
```

---

## 🔧 故障排查

### 問題 1: 日期顯示為 undefined

**原因**: API 回應中沒有 production_date

**檢查**:
```javascript
console.log('API Response:', record);
console.log('Production Date:', record.production_date);
```

**解決**:
```javascript
const displayDate = record.production_date 
  ? formatDateToYYYYMMDD(record.production_date)
  : '-';
```

### 問題 2: 格式化後仍有連字符

**原因**: replace() 只替換第一個匹配

**錯誤**:
```javascript
dateStr.replace('-', '')  // 只移除第一個 -
```

**正確**:
```javascript
dateStr.replace(/-/g, '')  // 使用 g 標誌移除所有 -
```

### 問題 3: 日期範圍搜尋失敗

**原因**: 前端傳送了 YYYYMMDD 格式給後端

**檢查後端日誌**:
```
Invalid date format: 20241101
```

**解決**: 保持後端 API 使用 YYYY-MM-DD
```javascript
// 前端發送前不要格式化
const searchParams = {
  start_date: startDate,  // 保持 "2024-01-01"
  end_date: endDate
};
```

---

## 📚 參考資料

### 相關檔案

- `form-analysis-server/backend/app/services/production_date_extractor.py`
- `form-analysis-server/backend/app/api/routes_import.py`
- `form-analysis-server/backend/app/models/record.py`

### 相關文件

- [P3_ITEMS_IMPLEMENTATION_SUMMARY.md](./P3_ITEMS_IMPLEMENTATION_SUMMARY.md)
- [PRD2.md](./docs/PRD2.md)

---

##  總結

### 問題解答

**1. data date 是否可以使用已有的資料進行提取？**

 **是的！直接使用現有的 `production_date` 欄位即可**

- production_date 已經從正確的來源提取
- 覆蓋率 100%（所有記錄都有值）
- 不需要新增 data_date 欄位
- 前端使用 `record.production_date` 顯示資料日期

**2. 用於前端顯示**

 **P1 的 YYYYMMDD 格式在前端處理**

- 後端保持 YYYY-MM-DD 標準格式
- 前端顯示時格式化為 YYYYMMDD
- 簡單實作：`dateStr.replace(/-/g, '')`
- 推薦集中管理格式化函數

### 實作優勢

| 方面 | 優勢 |
|------|------|
| 🗄️ **資料庫** | 標準 DATE 格式，支援日期運算 |
| 🔧 **後端** | 統一格式，易於維護 |
| 🎨 **前端** | 靈活格式化，適應不同場景 |
| **查詢** | 原生日期查詢，效能最佳 |
| 📊 **匯出** | 支援多種格式輸出 |

### 無需額外開發

-  資料庫欄位已存在
-  提取邏輯已完成
-  資料已正確填入
-  只需前端格式化

---

**文件版本**: 1.0  
**最後更新**: 2025-01-22  
**狀態**:  可直接使用
