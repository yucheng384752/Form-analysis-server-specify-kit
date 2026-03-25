# 通用化更新指南（Agent / Developer）

> 目標：將現行專案從「製造業 P1/P2/P3 專用系統」重構為「85% 通用 + 15% 客製」的可配置平台。
> 本文件為 Claude Code Agent 與開發者提供完整的重構路線圖。

---

## 目錄

1. [現況評估](#1-現況評估)
2. [目標架構](#2-目標架構)
3. [Phase 1：資料庫通用化](#3-phase-1資料庫通用化)
4. [Phase 2：後端服務通用化](#4-phase-2後端服務通用化)
5. [Phase 3：前端通用化](#5-phase-3前端通用化)
6. [Phase 4：配置與管理介面](#6-phase-4配置與管理介面)
7. [遷移策略](#7-遷移策略)
8. [Agent 操作守則](#8-agent-操作守則)
9. [驗收標準](#9-驗收標準)

---

## 1. 現況評估

### 1.1 通用 vs 客製比例（現狀）

| 層級 | 通用 | 客製 | 說明 |
|------|------|------|------|
| Backend 基礎設施 | ✅ 95% | 5% | Multi-tenancy、Auth、Audit、Middleware |
| Backend 業務邏輯 | 20% | ❌ 80% | Model、Service、Config 深度耦合 P1/P2/P3 |
| Frontend UI 元件 | ✅ 95% | 5% | shadcn/ui 元件庫已通用 |
| Frontend 頁面邏輯 | 30% | ❌ 70% | Upload/Query/Analytics 頁面綁定製造業流程 |
| **整體** | **~40%** | **~60%** | 距離 85/15 目標尚有差距 |

### 1.2 主要耦合點

以下為需要通用化的「硬編碼熱點」：

| 耦合點 | 涉及檔案 | 問題描述 |
|--------|----------|----------|
| P1/P2/P3 獨立表 | `models/p1_record.py`, `p2_record.py`, `p3_record.py` | 每個工站各一張表，新增工站需加表+改程式 |
| P2/P3 Item 表 | `models/p2_item_v2.py`, `p3_item_v2.py` | 明細欄位硬編碼（thickness1-7, appearance 等） |
| 70+ 欄位映射 | `config/analytics_field_mapping.py` | 分析輸出欄位完全綁定製造業 |
| UT 欄位映射 | `config/ut_field_mapping.py` | 查詢欄位綁定 P2/P3 特定欄位名 |
| CSV 偵測邏輯 | `services/csv_field_mapper.py`（586 行） | 用 `P1_`/`P2_`/`P3_` 前綴 + 簽章欄位判斷 |
| 驗證常數 | `config/constants.py` | `VALID_MATERIALS`, `VALID_SLITTING_MACHINES` 硬編碼 |
| Lot No 格式 | `utils/normalization.py`, `services/validation.py` | 7碼+2碼格式、民國年轉換 |
| 追溯鏈 | `services/traceability_flattener.py` | P3→P2→P1 三層 JOIN 寫死 |
| 前端型別 | `frontend/src/types/api.ts` | `ExtrusionRecord`, `SlittingRecord`, `PunchingRecord` |
| 前端頁面 | `UploadPage.tsx`, `QueryPage.tsx`, `AnalyticsPage.tsx` | P1/P2/P3 邏輯散布在 3000+ 行頁面中 |
| 前端篩選器 | `components/AdvancedSearch.tsx` | machine_no, mold_no, winder 等欄位硬編碼 |
| 追溯視覺化 | `components/TraceabilityFlow.tsx` | 固定三層 P1→P2→P3 |
| i18n 術語表 | `locales/zh-TW/common.json`, `locales/en/common.json` | 專有名詞對照表綁定製造業術語 |

---

## 2. 目標架構

### 2.1 核心理念

```
┌─────────────────────────────────────────────────────────┐
│                    通用平台（85%）                        │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │
│  │Multi-Tenant│ │Auth/Audit │ │ Generic   │ │ Dynamic │ │
│  │ Framework  │ │ Framework │ │ Import/   │ │ Schema  │ │
│  │           │ │           │ │ Export    │ │ Engine  │ │
│  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │
│  │ Dynamic   │ │ Config-   │ │ Generic   │ │ Generic │ │
│  │ Form      │ │ Driven    │ │ Trace-    │ │ Analyt- │ │
│  │ Renderer  │ │ Query     │ │ ability   │ │ ics     │ │
│  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────┤
│                    客製層（15%）                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Station Definitions (P1/P2/P3) ← JSON config      │ │
│  │  Field Mappings ← DB / JSON                         │ │
│  │  Validation Rules ← DB / JSON                       │ │
│  │  Glossary Terms ← per-tenant i18n config            │ │
│  │  Traceability Links ← station_links table           │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 2.2 原則

1. **配置優於程式碼** — 新增工站/欄位/驗證規則不需要改程式碼
2. **Schema 驅動** — 前後端都從同一份 schema 定義產生行為
3. **向後相容** — 現有 P1/P2/P3 資料可無損遷移
4. **漸進式重構** — 分 Phase 執行，每個 Phase 可獨立部署驗證

---

## 3. Phase 1：資料庫通用化

> 目標：用通用表取代 `p1_records`, `p2_records`, `p3_records`, `p2_items_v2`, `p3_items_v2`。

### 3.1 新表結構

#### `stations`（工站定義）

```sql
CREATE TABLE stations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,          -- e.g. 'P1', 'P2', 'P3'
    name        VARCHAR(100) NOT NULL,         -- e.g. '押出', '分條', '沖切'
    sort_order  INTEGER NOT NULL DEFAULT 0,
    has_items   BOOLEAN NOT NULL DEFAULT FALSE, -- 是否有明細子表
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, code)
);
```

#### `station_schemas`（工站欄位定義）

```sql
CREATE TABLE station_schemas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id  UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL DEFAULT 1,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    -- 主記錄欄位定義
    record_fields JSONB NOT NULL,
    -- 明細欄位定義（僅 has_items=true 時使用）
    item_fields   JSONB,
    -- 唯一鍵定義（用於 dedup）
    unique_key_fields TEXT[] NOT NULL,         -- e.g. ['lot_no_norm'] or ['lot_no_norm','winder_number']
    -- CSV 匯入對應
    csv_signature_columns TEXT[],              -- 用於自動偵測檔案類型
    csv_filename_pattern  VARCHAR(100),        -- e.g. 'P1_*'
    csv_field_mapping     JSONB,              -- CSV header → DB field 對應
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (station_id, version)
);
```

**`record_fields` / `item_fields` JSONB 結構範例：**

```json
[
  {
    "name": "winder_number",
    "type": "integer",
    "required": true,
    "label": { "zh-TW": "捲收機號", "en": "Winder Number" },
    "indexed": true,
    "filterable": true,
    "min": 1,
    "max": 20
  },
  {
    "name": "sheet_width",
    "type": "float",
    "required": false,
    "label": { "zh-TW": "半成品寬度(mm)", "en": "Sheet Width(mm)" },
    "unit": "mm"
  }
]
```

#### `records`（通用記錄表）

```sql
CREATE TABLE records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    station_id      UUID NOT NULL REFERENCES stations(id),
    schema_version_id UUID REFERENCES station_schemas(id),
    lot_no_raw      VARCHAR(50) NOT NULL,
    lot_no_norm     BIGINT NOT NULL,
    data            JSONB NOT NULL DEFAULT '{}',  -- 工站特定欄位
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 核心索引
CREATE INDEX idx_records_tenant_station ON records(tenant_id, station_id);
CREATE INDEX idx_records_lot_norm ON records(tenant_id, lot_no_norm);
CREATE INDEX idx_records_data ON records USING GIN (data);

-- Generated columns（對常查欄位加速）
ALTER TABLE records ADD COLUMN production_date DATE
    GENERATED ALWAYS AS (
        CASE WHEN data->>'production_date' IS NOT NULL
             THEN (data->>'production_date')::DATE
             ELSE NULL
        END
    ) STORED;
CREATE INDEX idx_records_prod_date ON records(tenant_id, production_date);
```

#### `record_items`（通用明細表）

```sql
CREATE TABLE record_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id   UUID NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    row_no      INTEGER NOT NULL,
    data        JSONB NOT NULL DEFAULT '{}',  -- 明細特定欄位
    row_data    JSONB,                         -- 原始 CSV 行（審計用）
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (record_id, row_no)
);

CREATE INDEX idx_record_items_record ON record_items(record_id);
CREATE INDEX idx_record_items_data ON record_items USING GIN (data);
```

#### `station_links`（工站追溯關係）

```sql
CREATE TABLE station_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    from_station_id UUID NOT NULL REFERENCES stations(id),
    to_station_id   UUID NOT NULL REFERENCES stations(id),
    link_type       VARCHAR(20) NOT NULL,      -- 'lot_no', 'winder', 'custom'
    link_config     JSONB NOT NULL DEFAULT '{}',
    sort_order      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, from_station_id, to_station_id)
);
```

**`link_config` 範例（P3→P2 透過 lot_no + winder）：**

```json
{
  "from_field": "data.source_winder",
  "to_field": "data.winder_number",
  "shared_key": "lot_no_norm",
  "description": "P3 成品追溯到 P2 分條捲收機"
}
```

#### `validation_rules`（驗證規則，取代 constants.py）

```sql
CREATE TABLE validation_rules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    station_id  UUID REFERENCES stations(id),  -- NULL = 全工站適用
    field_name  VARCHAR(100) NOT NULL,
    rule_type   VARCHAR(30) NOT NULL,           -- 'enum', 'range', 'regex', 'required'
    rule_config JSONB NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (tenant_id, station_id, field_name, rule_type)
);
```

**範例：**

```json
-- 取代 VALID_MATERIALS = ["H2", "H5", "H8"]
{ "rule_type": "enum", "field_name": "material", "rule_config": { "values": ["H2", "H5", "H8"] } }

-- 取代 VALID_SLITTING_MACHINES = [1, 2]
{ "rule_type": "enum", "field_name": "slitting_machine", "rule_config": { "values": [1, 2], "labels": {"1": "分條1", "2": "分條2"} } }

-- Lot No 格式
{ "rule_type": "regex", "field_name": "lot_no_raw", "rule_config": { "pattern": "^\\d{7}_\\d{1,2}$" } }
```

#### `analytics_mappings`（分析欄位映射，取代 analytics_field_mapping.py）

```sql
CREATE TABLE analytics_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    station_id      UUID NOT NULL REFERENCES stations(id),
    source_path     VARCHAR(200) NOT NULL,     -- e.g. 'data.temperature.actual.C1'
    output_column   VARCHAR(100) NOT NULL,     -- e.g. 'Actual Temp_C1(℃)'
    output_order    INTEGER NOT NULL,
    data_type       VARCHAR(20) DEFAULT 'string',
    null_if_missing BOOLEAN DEFAULT TRUE,
    UNIQUE (tenant_id, station_id, output_column)
);
```

### 3.2 資料遷移 SQL

```sql
-- Step 1: 建立工站定義
INSERT INTO stations (tenant_id, code, name, sort_order, has_items) VALUES
  ('<tenant_id>', 'P1', '押出/成型', 1, FALSE),
  ('<tenant_id>', 'P2', '分條',      2, TRUE),
  ('<tenant_id>', 'P3', '沖切/分離', 3, TRUE);

-- Step 2: 遷移 P1 records
INSERT INTO records (tenant_id, station_id, lot_no_raw, lot_no_norm, data, created_at)
SELECT p1.tenant_id, s.id, p1.lot_no_raw, p1.lot_no_norm, p1.extras, p1.created_at
FROM p1_records p1
JOIN stations s ON s.tenant_id = p1.tenant_id AND s.code = 'P1';

-- Step 3: 遷移 P2 records（winder_number 移入 data）
INSERT INTO records (tenant_id, station_id, lot_no_raw, lot_no_norm, data, created_at)
SELECT p2.tenant_id, s.id, p2.lot_no_raw, p2.lot_no_norm,
       jsonb_build_object('winder_number', p2.winder_number) || COALESCE(p2.extras, '{}'),
       p2.created_at
FROM p2_records p2
JOIN stations s ON s.tenant_id = p2.tenant_id AND s.code = 'P2';

-- Step 4: 遷移 P2 items
INSERT INTO record_items (record_id, tenant_id, row_no, data, row_data)
SELECT r.id, i.tenant_id, i.winder_number,
       jsonb_build_object(
           'winder_number', i.winder_number,
           'sheet_width', i.sheet_width,
           'thickness1', i.thickness1, 'thickness2', i.thickness2,
           'thickness3', i.thickness3, 'thickness4', i.thickness4,
           'thickness5', i.thickness5, 'thickness6', i.thickness6,
           'thickness7', i.thickness7,
           'appearance', i.appearance,
           'rough_edge', i.rough_edge,
           'slitting_result', i.slitting_result
       ),
       i.row_data
FROM p2_items_v2 i
JOIN records r ON r.lot_no_norm = (
    SELECT p2.lot_no_norm FROM p2_records p2 WHERE p2.id = i.p2_record_id
) AND r.station_id = (SELECT id FROM stations WHERE code = 'P2' AND tenant_id = i.tenant_id);

-- Step 5: 遷移 P3 records
INSERT INTO records (tenant_id, station_id, lot_no_raw, lot_no_norm, data, created_at)
SELECT p3.tenant_id, s.id, p3.lot_no_raw, p3.lot_no_norm,
       jsonb_build_object(
           'production_date_yyyymmdd', p3.production_date_yyyymmdd,
           'machine_no', p3.machine_no,
           'mold_no', p3.mold_no,
           'product_id', p3.product_id
       ) || COALESCE(p3.extras, '{}'),
       p3.created_at
FROM p3_records p3
JOIN stations s ON s.tenant_id = p3.tenant_id AND s.code = 'P3';

-- Step 6: 遷移 P3 items
INSERT INTO record_items (record_id, tenant_id, row_no, data, row_data)
SELECT r.id, i.tenant_id, i.row_no,
       jsonb_build_object(
           'product_id', i.product_id,
           'lot_no', i.lot_no,
           'production_date', i.production_date,
           'machine_no', i.machine_no,
           'mold_no', i.mold_no,
           'production_lot', i.production_lot,
           'source_winder', i.source_winder,
           'specification', i.specification,
           'bottom_tape_lot', i.bottom_tape_lot
       ),
       i.row_data
FROM p3_items_v2 i
JOIN records r ON r.lot_no_norm = (
    SELECT p3.lot_no_norm FROM p3_records p3 WHERE p3.id = i.p3_record_id
) AND r.station_id = (SELECT id FROM stations WHERE code = 'P3' AND tenant_id = i.tenant_id);
```

---

## 4. Phase 2：後端服務通用化

### 4.1 新增 / 修改的模組

#### A. 通用 Model（取代 p1/p2/p3_record.py）

**新檔案：** `backend/app/models/record.py`（重寫）

```python
# 取代 p1_record.py, p2_record.py, p3_record.py, p2_item_v2.py, p3_item_v2.py
# 單一 Record model + RecordItem model 搭配 station_id 區分

class Record(Base):
    __tablename__ = "records"
    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    station_id = Column(UUID, ForeignKey("stations.id"), nullable=False)
    lot_no_raw = Column(String(50), nullable=False)
    lot_no_norm = Column(BigInteger, nullable=False, index=True)
    data = Column(JSONB, nullable=False, default={})
    items = relationship("RecordItem", back_populates="record", cascade="all, delete-orphan")

class RecordItem(Base):
    __tablename__ = "record_items"
    id = Column(UUID, primary_key=True)
    record_id = Column(UUID, ForeignKey("records.id"), nullable=False)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    row_no = Column(Integer, nullable=False)
    data = Column(JSONB, nullable=False, default={})
    row_data = Column(JSONB)
```

#### B. Schema 服務（新增）

**新檔案：** `backend/app/services/schema_service.py`

職責：
- 從 `station_schemas` 讀取欄位定義
- 提供欄位驗證（取代 `validation.py` 中的硬編碼規則）
- 產生動態查詢條件
- 提供前端需要的 schema JSON

```python
class SchemaService:
    async def get_station_schema(self, tenant_id: UUID, station_code: str) -> StationSchema:
        """取得工站的 active schema 定義"""

    async def validate_record_data(self, schema: StationSchema, data: dict) -> list[ValidationError]:
        """根據 schema 驗證 record.data"""

    async def get_filterable_fields(self, tenant_id: UUID, station_code: str) -> list[FieldDef]:
        """取得可篩選欄位（供前端 AdvancedSearch 使用）"""

    async def get_analytics_mapping(self, tenant_id: UUID) -> list[AnalyticsColumn]:
        """取得分析輸出欄位映射（取代 analytics_field_mapping.py）"""
```

#### C. 通用 CSV Mapper（重寫 csv_field_mapper.py）

**修改檔案：** `backend/app/services/csv_field_mapper.py`

```python
class GenericCSVFieldMapper:
    async def detect_station(self, filename: str, headers: list[str], tenant_id: UUID) -> Station:
        """
        根據 station_schemas 中的 csv_filename_pattern 和 csv_signature_columns 偵測工站
        取代硬編碼的 P1_/P2_/P3_ 前綴判斷
        """

    async def map_fields(self, station_code: str, headers: list[str], tenant_id: UUID) -> dict:
        """
        根據 station_schemas.csv_field_mapping 映射 CSV header → record.data key
        取代硬編碼的 field alias 列表
        """
```

#### D. 通用追溯服務（重寫 traceability_flattener.py）

**修改檔案：** `backend/app/services/traceability_flattener.py`

```python
class GenericTraceabilityService:
    async def get_chain(self, tenant_id: UUID, product_id: str) -> list[TraceNode]:
        """
        根據 station_links 表動態建構追溯鏈
        取代硬編碼的 P3→P2→P1 JOIN
        """

    async def flatten_for_analytics(self, tenant_id: UUID, filters: dict) -> list[dict]:
        """
        根據 analytics_mappings 表動態扁平化
        取代 70+ 欄位的硬編碼映射
        """
```

#### E. 通用驗證服務（重寫 validation.py）

```python
class GenericValidator:
    async def validate(self, tenant_id: UUID, station_code: str, data: dict) -> list[Error]:
        """
        從 validation_rules 表載入規則，動態驗證
        取代 VALID_MATERIALS, VALID_SLITTING_MACHINES 硬編碼
        """
```

### 4.2 新增 API 端點

| 端點 | 方法 | 用途 |
|------|------|------|
| `/api/stations` | GET | 列出租戶的所有工站 |
| `/api/stations/{code}/schema` | GET | 取得工站 schema（欄位定義） |
| `/api/stations/{code}/schema/fields` | GET | 取得可篩選/可排序欄位 |
| `/api/stations/{code}/validation-rules` | GET | 取得驗證規則 |
| `/api/stations/{code}/analytics-mapping` | GET | 取得分析映射 |
| `/api/records` | GET/POST | 通用記錄 CRUD（帶 `station` query param） |
| `/api/traceability/{product_id}` | GET | 動態追溯（根據 station_links） |

### 4.3 需保留的檔案（已通用，不需修改）

| 檔案 | 原因 |
|------|------|
| `core/config.py` | 環境變數配置 |
| `core/database.py` | SQLAlchemy 設定 |
| `core/auth.py`, `core/password.py` | 密碼/API key 雜湊 |
| `core/middleware.py` | 請求日誌 |
| `core/tenant_resolver.py` | 租戶解析 |
| `api/deps.py` | 依賴注入 |
| `api/routes_auth.py` | 認證路由 |
| `api/routes_tenants.py` | 租戶管理 |
| `api/routes_health.py` | 健康檢查 |
| `models/core/*` | 租戶、使用者、API key、審計 |
| `models/import_job.py` | 匯入工作流 |
| `services/audit_events.py` | 審計寫入 |

### 4.4 需刪除 / 合併的檔案（完成遷移後）

| 刪除 | 合併至 |
|------|--------|
| `models/p1_record.py` | `models/record.py`（通用） |
| `models/p2_record.py` | `models/record.py` |
| `models/p3_record.py` | `models/record.py` |
| `models/p2_item_v2.py` | `models/record.py`（RecordItem） |
| `models/p3_item_v2.py` | `models/record.py` |
| `config/analytics_field_mapping.py` | `analytics_mappings` 表 |
| `config/ut_field_mapping.py` | `analytics_mappings` 表 |
| `config/constants.py` | `validation_rules` 表 |

---

## 5. Phase 3：前端通用化

### 5.1 Schema-Driven 動態渲染

核心改動：前端不再硬編碼 P1/P2/P3 型別，改為從 API 取得 schema 後動態渲染。

#### A. 新增 Schema Hook

**新檔案：** `frontend/src/hooks/useStationSchema.ts`

```typescript
interface FieldDef {
  name: string;
  type: 'string' | 'integer' | 'float' | 'date' | 'boolean' | 'enum';
  label: Record<string, string>;  // { 'zh-TW': '...', 'en': '...' }
  required?: boolean;
  filterable?: boolean;
  unit?: string;
  enum_values?: Array<{ value: any; label: Record<string, string> }>;
}

interface StationSchema {
  station_code: string;
  station_name: Record<string, string>;
  record_fields: FieldDef[];
  item_fields?: FieldDef[];
}

function useStationSchema(stationCode: string): {
  schema: StationSchema | null;
  loading: boolean;
}
```

#### B. 動態表單元件（取代硬編碼欄位）

**新檔案：** `frontend/src/components/DynamicForm.tsx`

根據 `FieldDef[]` 動態產生表單欄位：
- `string` → `<Input />`
- `integer` / `float` → `<Input type="number" />`
- `date` → `<DatePicker />`
- `enum` → `<Select />` 或 `<RadioGroup />`
- `boolean` → `<Checkbox />`

#### C. 動態篩選器（取代 AdvancedSearch.tsx）

**修改檔案：** `frontend/src/components/AdvancedSearch.tsx`

```typescript
// Before: 硬編碼 machine_no, mold_no, winder_number 等
// After:
function AdvancedSearch({ stationCode }: Props) {
  const { schema } = useStationSchema(stationCode);
  const filterableFields = schema?.record_fields.filter(f => f.filterable) ?? [];

  return filterableFields.map(field => (
    <DynamicFilterField key={field.name} field={field} />
  ));
}
```

#### D. 動態追溯鏈（取代 TraceabilityFlow.tsx）

**修改檔案：** `frontend/src/components/TraceabilityFlow.tsx`

```typescript
// Before: 固定三層 P1→P2→P3 卡片
// After: 從 API 取得 station_links，動態渲染 N 層
function TraceabilityFlow({ productId }: Props) {
  const { chain } = useTraceabilityChain(productId);
  // chain = [{ station: 'P3', data: {...} }, { station: 'P2', data: {...} }, { station: 'P1', data: {...} }]
  return chain.map(node => <StationCard key={node.station} schema={node.schema} data={node.data} />);
}
```

#### E. 型別重構

**修改檔案：** `frontend/src/types/api.ts`

```typescript
// Before:
// interface ExtrusionRecord { ... }
// interface SlittingRecord { ... }
// interface PunchingRecord { ... }

// After: 通用型別
interface GenericRecord {
  id: string;
  station_code: string;
  lot_no_raw: string;
  lot_no_norm: number;
  data: Record<string, any>;
  items?: GenericRecordItem[];
  created_at: string;
}

interface GenericRecordItem {
  id: string;
  row_no: number;
  data: Record<string, any>;
}
```

### 5.2 i18n 術語表外部化

**修改方式：**

```typescript
// Before: 硬編碼在 locales/zh-TW/common.json 的「專有名詞對照表」
// After: 從 station_schemas 的 field.label 動態載入

// 保留 common.json 中的 UI 通用翻譯（按鈕、標題、錯誤訊息等）
// 移除 common.json 中的製造業術語（分條機台、捲收機號等）
// 改由 useStationSchema 提供的 label 欄位取代
```

### 5.3 不需修改的檔案

| 檔案 | 原因 |
|------|------|
| `components/ui/*` | shadcn/ui 通用元件，完全不動 |
| `components/common/*` | Toast、Modal、ProgressBar 已通用 |
| `services/fetchWrapper.ts` | 已通用 |
| `services/auth.ts`, `adminAuth.ts` | 已通用 |
| `services/tenant.ts` | 已通用 |
| `services/a11y.ts` | 已通用 |
| `pages/AdminPage.tsx` | 已通用 |
| `pages/ManagerPage.tsx` | 已通用 |
| `pages/RegisterPage.tsx` | 幾乎已通用 |

---

## 6. Phase 4：配置與管理介面

### 6.1 新增管理頁面

在 `AdminPage.tsx` 中新增以下 Tab：

| Tab | 功能 |
|-----|------|
| 工站管理 | CRUD stations，編輯 schema、CSV mapping |
| 驗證規則 | 管理 validation_rules（enum 值、regex、range） |
| 分析映射 | 管理 analytics_mappings（輸出欄位順序與來源） |
| 追溯關係 | 管理 station_links |
| 術語表 | 管理每工站的多語言 label |

### 6.2 Seed Data 腳本

為現有製造業客戶提供 seed 腳本，將現行硬編碼的配置寫入新表：

```bash
# 新增腳本
scripts/seed-manufacturing-config.py
```

此腳本讀取現行 `constants.py`、`analytics_field_mapping.py` 等，轉換為 `stations`、`station_schemas`、`validation_rules`、`analytics_mappings` 的 INSERT 語句。

---

## 7. 遷移策略

### 7.1 執行順序

```
Phase 1 (DB)    ─── 2-3 週 ───→ Phase 2 (Backend) ─── 2-3 週 ───→
Phase 3 (Frontend) ─── 2-3 週 ───→ Phase 4 (Admin UI) ─── 1-2 週
```

### 7.2 雙寫過渡期

在 Phase 1→2 過渡期間，建議採用「雙寫」策略：

1. 新資料同時寫入新表（`records`）和舊表（`p1/p2/p3_records`）
2. 讀取優先使用新表，fallback 舊表
3. 驗證新舊表資料一致後，移除舊表寫入
4. 最終移除舊表

### 7.3 回滾計畫

每個 Phase 獨立分支，配合 feature flag：

```python
# backend/app/core/config.py
USE_GENERIC_SCHEMA: bool = Field(default=False, env="USE_GENERIC_SCHEMA")
```

- `False`：使用現行 P1/P2/P3 邏輯
- `True`：使用新的通用 schema 邏輯

---

## 8. Agent 操作守則

> 以下為 Claude Code Agent 在執行本指南時應遵循的規則。

### 8.1 修改前必做

- [ ] 讀取本文件確認當前 Phase
- [ ] 確認 `USE_GENERIC_SCHEMA` feature flag 狀態
- [ ] 檢查目標檔案是否已被其他 Phase 修改

### 8.2 禁止事項

| 規則 | 原因 |
|------|------|
| 不得刪除舊 Model 檔案，除非雙寫驗證完成 | 防止資料遺失 |
| 不得修改 `core/` 目錄下的通用模組 | 已通用，無需改動 |
| 不得在通用層引入領域術語 | 例如不得在 `records` model 中出現 `winder_number` 欄位 |
| 不得硬編碼新的工站代碼 | 所有工站定義必須來自 `stations` 表 |
| 不得在前端硬編碼欄位名稱 | 所有欄位名稱必須來自 schema API |

### 8.3 命名規範

| 類型 | 規範 | 範例 |
|------|------|------|
| 通用 Model | 單數名詞 | `Record`, `RecordItem`, `Station` |
| 通用 Service | `Generic` 前綴 | `GenericCSVFieldMapper`, `GenericTraceabilityService` |
| Schema API | `/api/stations/{code}/...` | `/api/stations/P2/schema` |
| Feature Flag | `USE_GENERIC_*` | `USE_GENERIC_SCHEMA` |
| 遷移腳本 | `migrate_*` | `migrate_p1_to_records.sql` |

### 8.4 測試要求

每個 Phase 完成後必須通過：

1. **單元測試**：新 service 的邏輯正確性
2. **遷移測試**：舊資料遷移到新表後，查詢結果一致
3. **API 相容性測試**：現有前端不受影響（雙寫期間）
4. **效能測試**：JSONB 查詢 vs 舊欄位查詢的 latency 對比

---

## 9. 驗收標準

### 9.1 通用化比例目標

| 層級 | 目標 | 驗證方式 |
|------|------|----------|
| Backend Model | 100% 通用 | 無任何 P1/P2/P3 專用表或欄位 |
| Backend Service | 90% 通用 | 僅 seed data 腳本包含領域知識 |
| Backend Config | 100% 通用 | `config/` 目錄無領域硬編碼 |
| Frontend 元件 | 95% 通用 | 無硬編碼工站/欄位名 |
| Frontend 頁面 | 85% 通用 | 僅 seed config 和 i18n 包含領域知識 |
| **整體** | **≥ 85% 通用** | |

### 9.2 功能驗收

- [ ] 可透過管理介面新增工站（如 P4），無需改程式碼
- [ ] 可透過管理介面新增欄位到現有工站，無需改程式碼
- [ ] 可透過管理介面修改驗證規則（如新增材料代碼），無需改程式碼
- [ ] 可透過管理介面配置追溯關係，前端自動渲染追溯鏈
- [ ] 現有 P1/P2/P3 資料完整遷移，查詢結果不變
- [ ] 分析報表輸出欄位與遷移前一致

### 9.3 效能驗收

- [ ] 通用查詢（JSONB）的 P95 latency ≤ 舊查詢的 1.5 倍
- [ ] 分析 API 的回應時間在 `QUERY_TIMEOUT_SECONDS`（45s）內
- [ ] Generated column 索引命中率 ≥ 90%

---

## 附錄：現行檔案與目標狀態對照

| 現行檔案 | 目標狀態 | Phase |
|---------|---------|-------|
| `models/p1_record.py` | 刪除，合併至 `models/record.py` | Phase 1 |
| `models/p2_record.py` | 刪除，合併至 `models/record.py` | Phase 1 |
| `models/p3_record.py` | 刪除，合併至 `models/record.py` | Phase 1 |
| `models/p2_item_v2.py` | 刪除，合併至 `models/record.py` | Phase 1 |
| `models/p3_item_v2.py` | 刪除，合併至 `models/record.py` | Phase 1 |
| `models/base_record.py` | 刪除，BaseRecordMixin 不再需要 | Phase 1 |
| `config/constants.py` | 刪除，遷移至 `validation_rules` 表 | Phase 2 |
| `config/analytics_field_mapping.py` | 刪除，遷移至 `analytics_mappings` 表 | Phase 2 |
| `config/ut_field_mapping.py` | 刪除，遷移至 `analytics_mappings` 表 | Phase 2 |
| `services/csv_field_mapper.py` | 重寫為 `GenericCSVFieldMapper` | Phase 2 |
| `services/validation.py` | 重寫為 `GenericValidator` | Phase 2 |
| `services/traceability_flattener.py` | 重寫為 `GenericTraceabilityService` | Phase 2 |
| `services/analytics_data_fetcher.py` | 重寫，讀取 `analytics_mappings` | Phase 2 |
| `services/import_v2.py` | 重寫，使用通用 Record model | Phase 2 |
| `frontend/src/types/api.ts` | 重寫為 `GenericRecord` 型別 | Phase 3 |
| `frontend/src/pages/UploadPage.tsx` | 重構，使用 schema-driven 邏輯 | Phase 3 |
| `frontend/src/pages/QueryPage.tsx` | 重構，使用動態欄位 | Phase 3 |
| `frontend/src/pages/AnalyticsPage.tsx` | 重構，使用動態映射 | Phase 3 |
| `frontend/src/components/AdvancedSearch.tsx` | 重構為 schema-driven | Phase 3 |
| `frontend/src/components/TraceabilityFlow.tsx` | 重構為動態 N 層 | Phase 3 |
| `frontend/src/locales/*/common.json` | 移除術語表，改由 schema label 提供 | Phase 3 |
| `config/analytics_config.py` | **保留**（效能設定，已通用） | — |
| `core/*` | **保留**（已通用） | — |
| `models/core/*` | **保留**（已通用） | — |
| `models/import_job.py` | **保留**（已通用） | — |
| `api/routes_auth.py` | **保留**（已通用） | — |
| `api/routes_tenants.py` | **保留**（已通用） | — |
| `api/deps.py` | **保留**（已通用） | — |
| `frontend/src/components/ui/*` | **保留**（已通用） | — |
| `frontend/src/services/fetchWrapper.ts` | **保留**（已通用） | — |
