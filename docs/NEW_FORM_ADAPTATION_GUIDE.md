# 新增/修改表單適配指南

## 概述
本文件說明需要新增新的表單類型（例如 P4、P5）或修改現有表單（P1/P2/P3）時，需要修改的所有程式碼位置。

---

##  快速檢查清單

### 新增表單類型（例如 P4）需要修改：
- [ ] 1. 後端：資料模型 - `record.py`
- [ ] 2. 後端：資料類型枚舉 - `record_schema.py`
- [ ] 3. 後端：CSV 欄位映射器 - `csv_field_mapper.py`
- [ ] 4. 後端：生產日期提取器 - `production_date_extractor.py`
- [ ] 5. 後端：驗證服務 - `validation.py`
- [ ] 6. 後端：匯入路由 - `routes_import.py`
- [ ] 7. 後端：查詢路由 - `routes_query.py`
- [ ] 8. 後端：常數配置 - `constants.py`
- [ ] 9. 前端：類型定義 - `QueryPage.tsx`
- [ ] 10. 前端：高級搜尋 - `AdvancedSearch.tsx`
- [ ] 11. 前端：UI 顯示邏輯 - `QueryPage.tsx`
- [ ] 12. 資料庫：遷移腳本（新增專屬欄位）

---

## 詳細修改步驟

### 1. 後端：資料模型 (`backend/app/models/record.py`)

**位置**：`form-analysis-server/backend/app/models/record.py`

**需要修改**：
1. 新增 `DataType` 枚舉值
2. 如果新表單有專屬欄位，新增 `Mapped` 欄位定義

```python
class DataType(str, Enum):
    """資料類型枚舉"""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"  # ← 新增
    
class Record(Base):
    # ... 現有欄位 ...
    
    # P4 專屬欄位（範例）
    p4_special_field: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="P4 專屬欄位說明"
    )
```

**索引建議**：
- 如果欄位會用於搜尋，加上 `index=True`
- 如果欄位必須唯一，使用 `unique=True`

---

### 2. 後端：資料類型枚舉 (`backend/app/schemas/record_schema.py`)

**位置**：`form-analysis-server/backend/app/schemas/record_schema.py`

**需要修改**：
1. 在 `DataType` 枚舉中新增類型
2. 在 `RecordSchema` 中新增專屬欄位（如有）

```python
class DataType(str, Enum):
    """資料類型枚舉"""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"  # ← 新增

class RecordSchema(BaseModel):
    # ... 現有欄位 ...
    
    # P4 專屬欄位
    p4_special_field: Optional[str] = Field(None, description="P4專屬欄位")
```

---

### 3. 後端：CSV 欄位映射器 (`backend/app/services/csv_field_mapper.py`)

**位置**：`form-analysis-server/backend/app/services/csv_field_mapper.py`

**需要修改**：
1. 新增 CSV 類型枚舉
2. 新增檔案名稱模式
3. 新增特徵欄位集合
4. 新增欄位別名清單
5. 更新 `detect_csv_type()` 方法
6. 更新 `extract_from_csv_row()` 方法

```python
class CSVType(str, Enum):
    """CSV 檔案類型"""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"  # ← 新增
    UNKNOWN = "UNKNOWN"

class CSVFieldMapper:
    # 檔案名稱模式
    P4_FILENAME_PATTERN = re.compile(r'^P4_', re.IGNORECASE)  # ← 新增
    
    # P4 特徵欄位（用於自動偵測）
    P4_SIGNATURE_COLUMNS = {  # ← 新增
        'P4_Field_1',
        'P4_Field_2',
        'P4_Field_3'
    }
    
    # P4 可能的欄位別名
    P4_FIELD_NAMES = [  # ← 新增（根據需要）
        'P4 Field',
        'p4_field',
        'P4欄位'
    ]
    
    def detect_csv_type(self, filename: str, columns: List[str]) -> CSVType:
        # 優先根據檔案名稱判斷
        if self.P1_FILENAME_PATTERN.match(filename):
            return CSVType.P1
        elif self.P2_FILENAME_PATTERN.match(filename):
            return CSVType.P2
        elif self.P3_FILENAME_PATTERN.match(filename):
            return CSVType.P3
        elif self.P4_FILENAME_PATTERN.match(filename):  # ← 新增
            return CSVType.P4
        
        # 根據欄位特徵判斷
        column_set = set(columns)
        
        # 檢查 P4 特徵
        p4_matches = len(self.P4_SIGNATURE_COLUMNS & column_set)  # ← 新增
        if p4_matches >= 2:
            return CSVType.P4
        
        # ... 其他類型檢查 ...
    
    def extract_from_csv_row(self, row: pd.Series, csv_type: CSVType, filename: str) -> Dict[str, Any]:
        result = {}
        
        if csv_type == CSVType.P1:
            # P1 邏輯
            pass
        elif csv_type == CSVType.P2:
            # P2 邏輯
            pass
        elif csv_type == CSVType.P3:
            # P3 邏輯
            pass
        elif csv_type == CSVType.P4:  # ← 新增
            # P4: 提取專屬欄位
            result['p4_special_field'] = self._extract_field_value(
                row, 
                self.P4_FIELD_NAMES
            )
        
        return result
```

---

### 4. 後端：生產日期提取器 (`backend/app/services/production_date_extractor.py`)

**位置**：`form-analysis-server/backend/app/services/production_date_extractor.py`

**需要修改**：
1. 新增 P4 日期欄位名稱清單
2. 新增 `_extract_p4_date()` 方法
3. 更新 `extract_production_date()` 主方法

```python
class ProductionDateExtractor:
    # P4 可能的日期欄位名稱
    P4_DATE_FIELD_NAMES = [  # ← 新增
        'P4 Date',
        'p4_date',
        'P4日期'
    ]
    
    def extract_production_date(self, row_data: Dict[str, Any], data_type: str) -> Optional[date]:
        additional_data = row_data.get('additional_data', {})
        
        if data_type == 'P1':
            return self._extract_p1_date(additional_data)
        elif data_type == 'P2':
            return self._extract_p2_date(additional_data)
        elif data_type == 'P3':
            return self._extract_p3_date(additional_data)
        elif data_type == 'P4':  # ← 新增
            return self._extract_p4_date(additional_data)
        
        return None
    
    def _extract_p4_date(self, data: Dict[str, Any]) -> Optional[date]:  # ← 新增
        """
        從 P4 資料中提取日期
        
        P4 的日期格式說明...
        """
        date_value = self._find_field_value(data, self.P4_DATE_FIELD_NAMES)
        if not date_value:
            return None
        
        # 根據 P4 的日期格式進行解析
        return self._parse_date_string(str(date_value))
```

---

### 5. 後端：驗證服務 (`backend/app/services/validation.py`)

**位置**：`form-analysis-server/backend/app/services/validation.py`

**需要修改**（如果 P4 有特殊驗證邏輯）：
1. 新增 P4 檔案名稱模式
2. 新增 P4 特定驗證規則

```python
class FileValidationService:
    # P4 檔案名稱檢測模式
    P4_PATTERN = re.compile(r'P4_')  # ← 新增
    
    def validate_p4_specific_logic(self, df: pd.DataFrame) -> bool:  # ← 新增（如需要）
        """
        P4 特定驗證邏輯
        """
        # 實作 P4 的特殊驗證
        pass
```

---

### 6. 後端：匯入路由 (`backend/app/api/routes_import.py`)

**位置**：`form-analysis-server/backend/app/api/routes_import.py`

**需要修改**：
1. 檔案類型偵測邏輯
2. 批號提取邏輯
3. 資料處理邏輯

```python
async def import_data(request: ImportRequest, db: AsyncSession = Depends(get_db)):
    # ... 前面程式碼 ...
    
    # 檔案類型偵測
    if filename_lower.startswith('p1_'):
        data_type = DataType.P1
    elif filename_lower.startswith('p2_'):
        data_type = DataType.P2
    elif filename_lower.startswith('p3_'):
        data_type = DataType.P3
    elif filename_lower.startswith('p4_'):  # ← 新增
        data_type = DataType.P4
    else:
        data_type = DataType.P1  # 預設
    
    # 批號提取
    if data_type in [DataType.P1, DataType.P2, DataType.P4]:  # ← 修改：加入 P4
        # P1/P2/P4 檔案：從檔案名稱提取 lot_no
        lot_no_match = re.search(r'P[124]_(\d{7}_\d{2})', filename)  # ← 修改
        if lot_no_match:
            lot_no = lot_no_match.group(1)
        else:
            # fallback...
    elif data_type == DataType.P3:
        # P3 特殊處理
        pass
    
    # P4 資料處理邏輯
    if data_type == DataType.P4:  # ← 新增整個區塊
        # 決定 P4 的處理方式：
        # 方案 A: 像 P1 一樣，每列一筆 record
        # 方案 B: 像 P2/P3 一樣，合併為單筆 record
        
        # 範例：採用方案 A（每列一筆）
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            
            # 提取生產日期
            production_date = production_date_extractor.extract_production_date(
                row_data={'additional_data': row_dict},
                data_type='P4'
            ) or date.today()
            
            # 提取專屬欄位
            p4_field = row_dict.get('P4_Field')
            
            # 創建 Record
            record = Record(
                lot_no=lot_no,
                data_type=data_type,
                production_date=production_date,
                p4_special_field=p4_field,  # P4 專屬欄位
                additional_data=row_dict
            )
            db.add(record)
```

---

### 7. 後端：查詢路由 (`backend/app/api/routes_query.py`)

**位置**：`form-analysis-server/backend/app/api/routes_query.py`

**需要修改**：
1. `QueryRecord` 回傳模型（如有專屬欄位）
2. 高級搜尋邏輯（如需要按 P4 欄位搜尋）
3. 回傳資料組裝

```python
class QueryRecord(BaseModel):
    # ... 現有欄位 ...
    
    # P4 專屬欄位
    p4_special_field: Optional[str] = None  # ← 新增

async def advanced_search_records(
    lot_no: Optional[str] = Query(None),
    # ... 其他參數 ...
    p4_field: Optional[str] = Query(None, description="P4專屬欄位搜尋"),  # ← 新增
    data_type: Optional[DataType] = Query(None)
):
    # 搜尋條件
    if p4_field and p4_field.strip():  # ← 新增
        conditions.append(Record.p4_special_field.ilike(f"%{p4_field.strip()}%"))
    
    # ... 查詢邏輯 ...
    
    # 組裝回傳資料
    for record in records:
        query_record = QueryRecord(
            # ... 一般欄位 ...
        )
        
        if record.data_type == DataType.P4:  # ← 新增
            query_record.p4_special_field = record.p4_special_field
        
        query_records.append(query_record)
```

---

### 8. 後端：常數配置 (`backend/app/config/constants.py`)

**位置**：`form-analysis-server/backend/app/config/constants.py`

**需要修改**（如果 P4 有特定的驗證清單）：

```python
# P4 特定常數（範例）
VALID_P4_CATEGORIES = {  # ← 新增
    "CATEGORY_A",
    "CATEGORY_B",
    "CATEGORY_C"
}

def get_p4_category_list():  # ← 新增
    """取得 P4 分類清單"""
    return sorted(list(VALID_P4_CATEGORIES))
```

---

### 9. 前端：類型定義 (`frontend/src/pages/QueryPage.tsx`)

**位置**：`form-analysis-server/frontend/src/pages/QueryPage.tsx`

**需要修改**：
1. `DataType` 類型定義
2. `QueryRecord` 介面
3. UI 顯示邏輯

```typescript
// 資料類型枚舉
type DataType = 'P1' | 'P2' | 'P3' | 'P4';  // ← 修改：加入 P4

interface QueryRecord {
  id: string;
  lot_no: string;
  data_type: DataType;
  production_date?: string;
  created_at: string;
  display_name: string;
  
  // P1專用欄位
  // ...
  
  // P2專用欄位
  // ...
  
  // P3專用欄位
  // ...
  
  // P4專用欄位  // ← 新增
  p4_special_field?: string;
  
  additional_data?: { [key: string]: any };
}

// UI 顯示邏輯
const renderRecordDetails = (record: QueryRecord) => {
  if (record.data_type === 'P1') {
    // P1 顯示邏輯
  } else if (record.data_type === 'P2') {
    // P2 顯示邏輯
  } else if (record.data_type === 'P3') {
    // P3 顯示邏輯
  } else if (record.data_type === 'P4') {  // ← 新增
    return (
      <div>
        <h3>P4 資料</h3>
        <div className="detail-row">
          <strong>P4專屬欄位：</strong>
          <span>{record.p4_special_field || '-'}</span>
        </div>
        {/* 其他 P4 欄位 */}
      </div>
    );
  }
};
```

---

### 10. 前端：高級搜尋 (`frontend/src/components/AdvancedSearch.tsx`)

**位置**：`form-analysis-server/frontend/src/components/AdvancedSearch.tsx`

**需要修改**：
1. `AdvancedSearchParams` 介面
2. 搜尋欄位狀態
3. UI 表單

```typescript
export interface AdvancedSearchParams {
  lot_no?: string;
  production_date_from?: string;
  production_date_to?: string;
  machine_no?: string;
  mold_no?: string;
  product_id?: string;
  p3_specification?: string;
  p4_field?: string;  // ← 新增
  data_type?: string;
}

export const AdvancedSearch: React.FC<AdvancedSearchProps> = ({...}) => {
  // ... 現有狀態 ...
  const [p4Field, setP4Field] = useState('');  // ← 新增
  
  const handleSearch = () => {
    // ... 其他參數 ...
    if (p4Field.trim()) params.p4_field = p4Field.trim();  // ← 新增
    
    onSearch(params);
  };
  
  const handleReset = () => {
    // ... 重置其他欄位 ...
    setP4Field('');  // ← 新增
    onReset();
  };
  
  return (
    <div className="advanced-search">
      {/* ... 現有欄位 ... */}
      
      {/* P4 專屬搜尋欄位 */}
      <div className="search-field">  {/* ← 新增 */}
        <label htmlFor="adv-p4-field">P4 專屬欄位</label>
        <input
          id="adv-p4-field"
          type="text"
          value={p4Field}
          onChange={(e) => setP4Field(e.target.value)}
          placeholder="輸入 P4 欄位 (模糊搜尋)"
        />
      </div>
      
      {/* 資料類型 */}
      <div className="search-field">
        <label htmlFor="adv-data-type">資料類型</label>
        <select id="adv-data-type" value={dataType} onChange={(e) => setDataType(e.target.value)}>
          <option value="">全部</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
          <option value="P4">P4</option>  {/* ← 新增 */}
        </select>
      </div>
    </div>
  );
};
```

---

### 11. 資料庫遷移

**需要執行**：
1. 在 DBeaver 或 pgAdmin 執行 SQL 新增欄位
2. 建立索引
3. 回填資料（如需要）

```sql
-- 新增 P4 專屬欄位
ALTER TABLE records 
ADD COLUMN IF NOT EXISTS p4_special_field VARCHAR(100);

-- 新增索引（如需要搜尋）
CREATE INDEX IF NOT EXISTS ix_records_p4_special_field 
ON records(p4_special_field);

-- 回填資料（如有舊資料需要遷移）
UPDATE records 
SET p4_special_field = additional_data->'rows'->0->>'P4_Field'
WHERE data_type = 'P4' 
  AND additional_data->'rows'->0->>'P4_Field' IS NOT NULL;
```

---

## 修改現有表單（P1/P2/P3）

如果只是修改現有表單的欄位處理（例如新增 P3 的某個欄位），主要修改：

### 簡化流程：
1. **欄位映射器** (`csv_field_mapper.py`)：新增欄位別名清單
2. **資料模型** (`record.py`)：如需獨立欄位，新增 `Mapped` 定義
3. **匯入路由** (`routes_import.py`)：更新欄位提取邏輯
4. **查詢路由** (`routes_query.py`)：更新回傳與搜尋邏輯
5. **前端** (`QueryPage.tsx`, `AdvancedSearch.tsx`)：更新顯示與搜尋

---

## 範例：新增 P3 的「檢驗員」欄位

### 1. 後端模型
```python
# record.py
inspector: Mapped[Optional[str]] = mapped_column(
    String(50),
    nullable=True,
    index=True,
    comment="檢驗員姓名"
)
```

### 2. 欄位映射
```python
# csv_field_mapper.py
INSPECTOR_FIELD_NAMES = [
    'Inspector',
    'inspector',
    '檢驗員',
    '檢查員'
]

# 在 P3 區塊加入
result['inspector'] = self._extract_field_value(row, self.INSPECTOR_FIELD_NAMES)
```

### 3. 匯入邏輯
```python
# routes_import.py - P3 區塊
inspector_val = (
    first_row.get('Inspector')
    or first_row.get('inspector')
    or first_row.get('檢驗員')
)
if inspector_val:
    record_kwargs['inspector'] = str(inspector_val).strip()
```

### 4. 查詢 API
```python
# routes_query.py
class QueryRecord(BaseModel):
    inspector: Optional[str] = None  # 新增

# 在 P3 填值區塊
query_record.inspector = record.inspector
```

### 5. 前端
```typescript
// QueryPage.tsx
interface QueryRecord {
  inspector?: string;  // 新增
}

// P3 詳情顯示
<div className="detail-row">
  <strong>檢驗員：</strong>
  <span>{record.inspector || '-'}</span>
</div>
```

---

## 測試檢查清單

完成修改後，請進行以下測試：

### 後端測試
- [ ] API 文件正常顯示新欄位（訪問 `/docs`）
- [ ] 上傳新類型 CSV 檔案成功
- [ ] 資料正確寫入資料庫（含新欄位）
- [ ] 高級搜尋可使用新欄位篩選
- [ ] 查詢 API 正確回傳新欄位

### 前端測試
- [ ] 資料類型下拉選單顯示新類型
- [ ] 查詢結果正確顯示新欄位
- [ ] 高級搜尋表單包含新欄位輸入
- [ ] 搜尋結果正確篩選
- [ ] UI 佈局正常，無錯位

### 整合測試
- [ ] 上傳 → 匯入 → 查詢 → 顯示 完整流程
- [ ] 舊資料（P1/P2/P3）不受影響
- [ ] 錯誤處理正常（檔案格式錯誤、欄位缺失等）

---

## 常見問題

### Q1: 新增表單後，舊的 P1/P2/P3 資料會受影響嗎？
**A**: 不會。只要正確設定 `nullable=True`，新欄位對舊資料不會造成問題。

### Q2: 如何決定欄位應該獨立還是放在 JSONB？
**A**: 
- **獨立欄位**：需要頻繁搜尋、排序、索引的欄位
- **JSONB**：很少查詢、僅供顯示的欄位

### Q3: 如何處理相同欄位名但不同表單的情況？
**A**: 使用表單前綴區分，例如：
- P1: `p1_status`
- P4: `p4_status`

### Q4: 忘記加索引會怎樣？
**A**: 系統仍能運作，但查詢效能會下降。建議在 `record.py` 設定 `index=True`。

---

## 相關文件

- [資料庫 Schema 說明](./DBEAVER_CONNECTION_GUIDE.md)
- [API 使用指南](./README.md)
- [PRD 需求文件](./PRD2.md)
- [測試報告](./reports/)

---

## 最佳實踐

1. **先規劃再實作**：確認新表單的欄位結構與資料流
2. **保持一致性**：欄位命名、驗證規則與現有表單一致
3. **完整測試**：每個修改點都要測試
4. **文件更新**：修改後更新 PRD 與 README
5. **版本控制**：每次修改都要 commit，並寫清楚 commit message

---

**最後更新**：2025-12-22  
**維護者**：GitHub Copilot
