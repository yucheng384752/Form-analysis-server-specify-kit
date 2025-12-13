# Product_ID 搜尋功能實作建議

**文檔日期**: 2025年12月10日  
**版本**: 1.0  
**需求**: 根據 product_id 搜尋對應的 P1、P2 表格資料

---

## 需求分析

### 核心需求
- 使用者輸入 `product_id`（從 P3 表格）
- 系統自動搜尋並返回對應的 P1（產品基本資料）和 P2（尺寸檢測資料）
- 關聯邏輯：通過 `lot_no` 欄位進行關聯

### 資料關聯邏輯

```
P3 表格 (追蹤編號)
  ├─ product_id: "20250310-M01-D05-S001"  
  ├─ lot_no: "2503033_01"  ← 關聯鍵
  └─ 其他 P3 資料...

        ↓ (透過 lot_no 關聯)

P1 表格 (產品基本資料)
  ├─ lot_no: "2503033_01"  ← 相同 lot_no
  ├─ product_name: "產品A"
  ├─ quantity: 100
  └─ production_date: 2025-03-03

P2 表格 (尺寸檢測資料)
  ├─ lot_no: "2503033_01"  ← 相同 lot_no
  ├─ sheet_width: 1250.5
  ├─ thickness1-7: ...
  └─ 檢測結果...
```

---

## 🗄️ 資料庫架構修改

### 1. 新增 Product_ID 欄位到 Record 模型

**檔案**: `form-analysis-server/backend/app/models/record.py`

```python
# 在 Record 類別中新增以下欄位（約在 line 100 之後）

    # P3 專用欄位 - Product ID 相關
    product_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,  # 建立索引加速搜尋
        comment="產品ID (P3使用)，格式：YYYYMMDD-M##-D##-S###"
    )
    
    machine_no: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="機台號碼 (P3使用)"
    )
    
    mold_no: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="模具號碼 (P3使用)"
    )
    
    production_sequence: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="生產序號 (P3使用)"
    )
```

### 2. 建立資料庫遷移腳本

**檔案**: `form-analysis-server/backend/alembic/versions/YYYYMMDD_HHMM_add_product_id_fields.py`

```python
"""add product_id fields to records

Revision ID: <自動生成>
Revises: <上一個 revision>
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '<自動生成>'
down_revision = '<上一個 revision>'
branch_labels = None
depends_on = None


def upgrade():
    """新增 product_id 相關欄位"""
    # 新增欄位
    op.add_column('records', sa.Column('product_id', sa.String(50), nullable=True, comment='產品ID (P3使用)'))
    op.add_column('records', sa.Column('machine_no', sa.String(10), nullable=True, comment='機台號碼 (P3使用)'))
    op.add_column('records', sa.Column('mold_no', sa.String(10), nullable=True, comment='模具號碼 (P3使用)'))
    op.add_column('records', sa.Column('production_sequence', sa.Integer, nullable=True, comment='生產序號 (P3使用)'))
    
    # 建立索引加速搜尋
    op.create_index('ix_records_product_id', 'records', ['product_id'])
    op.create_index('ix_records_machine_mold', 'records', ['machine_no', 'mold_no'])


def downgrade():
    """移除 product_id 相關欄位"""
    op.drop_index('ix_records_machine_mold')
    op.drop_index('ix_records_product_id')
    op.drop_column('records', 'production_sequence')
    op.drop_column('records', 'mold_no')
    op.drop_column('records', 'machine_no')
    op.drop_column('records', 'product_id')
```

**執行遷移**:
```bash
cd form-analysis-server/backend
alembic revision --autogenerate -m "add product_id fields to records"
alembic upgrade head
```

---

##  後端實作

### 1. Product ID 生成服務

**檔案**: `form-analysis-server/backend/app/services/product_id_generator.py`

```python
"""
Product ID 生成服務

負責根據 P3 資料生成唯一的 Product ID
格式: YYYYMMDD-M##-D##-S###
"""

from datetime import date
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProductIDGenerator:
    """Product ID 生成器"""
    
    @staticmethod
    def generate_product_id(
        production_date: date,
        machine_no: str,
        mold_no: str,
        production_sequence: int
    ) -> str:
        """
        生成 Product ID
        
        Args:
            production_date: 生產日期
            machine_no: 機台號碼 (如: "01", "02")
            mold_no: 模具號碼 (如: "05", "10")
            production_sequence: 生產序號 (如: 1, 2, 3...)
            
        Returns:
            str: Product ID (格式: "20250310-M01-D05-S001")
        """
        # 格式化日期為 YYYYMMDD
        date_str = production_date.strftime("%Y%m%d")
        
        # 格式化機台號碼為 M## (兩位數，不足補0)
        machine_str = f"M{int(machine_no):02d}"
        
        # 格式化模具號碼為 D## (兩位數，不足補0)
        mold_str = f"D{int(mold_no):02d}"
        
        # 格式化生產序號為 S### (三位數，不足補0)
        sequence_str = f"S{production_sequence:03d}"
        
        # 組合 Product ID
        product_id = f"{date_str}-{machine_str}-{mold_str}-{sequence_str}"
        
        logger.debug(
            "生成 Product ID",
            product_id=product_id,
            production_date=production_date,
            machine_no=machine_no,
            mold_no=mold_no,
            sequence=production_sequence
        )
        
        return product_id
    
    @staticmethod
    def parse_product_id(product_id: str) -> Optional[dict]:
        """
        解析 Product ID
        
        Args:
            product_id: Product ID 字串
            
        Returns:
            dict: 包含日期、機台、模具、序號的字典，失敗返回 None
        """
        try:
            # 分割字串: "20250310-M01-D05-S001"
            parts = product_id.split("-")
            if len(parts) != 4:
                return None
            
            date_str, machine_str, mold_str, sequence_str = parts
            
            # 提取數字
            date_value = date_str  # YYYYMMDD
            machine_no = machine_str[1:]  # 移除 "M"
            mold_no = mold_str[1:]  # 移除 "D"
            production_sequence = int(sequence_str[1:])  # 移除 "S" 並轉整數
            
            return {
                "date": date_value,
                "machine_no": machine_no,
                "mold_no": mold_no,
                "production_sequence": production_sequence
            }
        except Exception as e:
            logger.warning("解析 Product ID 失敗", product_id=product_id, error=str(e))
            return None
```

### 2. 搜尋 API 端點

**檔案**: `form-analysis-server/backend/app/api/routes_query.py`

在文件末尾新增以下 API 端點：

```python
# ==================== Product ID 搜尋功能 ====================

class ProductIDSearchResponse(BaseModel):
    """Product ID 搜尋回應模型"""
    product_id: str
    lot_no: str
    
    # P3 資料
    p3_data: Optional[QueryRecord] = None
    
    # P1 資料列表（可能有多筆）
    p1_data: List[QueryRecord] = []
    
    # P2 資料列表（可能有多筆）
    p2_data: List[QueryRecord] = []
    
    # 統計資訊
    p1_count: int = 0
    p2_count: int = 0


@router.get(
    "/search/product-id",
    response_model=ProductIDSearchResponse,
    summary="根據 Product ID 搜尋關聯資料",
    description="""
    根據 Product ID 搜尋對應的 P1、P2、P3 資料
    
    **搜尋邏輯：**
    1. 透過 product_id 找到 P3 記錄
    2. 取得 P3 記錄的 lot_no
    3. 使用 lot_no 搜尋所有對應的 P1 和 P2 記錄
    
    **回傳內容：**
    - product_id: 查詢的 Product ID
    - lot_no: 關聯的批號
    - p3_data: P3 記錄（追蹤編號）
    - p1_data: P1 記錄列表（產品基本資料）
    - p2_data: P2 記錄列表（尺寸檢測資料）
    - p1_count: P1 記錄數量
    - p2_count: P2 記錄數量
    """
)
async def search_by_product_id(
    product_id: str = Query(..., description="Product ID（格式：YYYYMMDD-M##-D##-S###）"),
    db: AsyncSession = Depends(get_db)
) -> ProductIDSearchResponse:
    """根據 Product ID 搜尋關聯資料"""
    try:
        logger.info("開始搜尋 Product ID", product_id=product_id)
        
        # 步驟 1: 搜尋 P3 記錄
        p3_query = select(Record).where(
            and_(
                Record.product_id == product_id,
                Record.data_type == DataType.P3
            )
        )
        result = await db.execute(p3_query)
        p3_record = result.scalar_one_or_none()
        
        if not p3_record:
            logger.warning("找不到對應的 P3 記錄", product_id=product_id)
            raise HTTPException(
                status_code=404,
                detail=f"找不到 Product ID: {product_id} 的記錄"
            )
        
        lot_no = p3_record.lot_no
        logger.info("找到 P3 記錄", product_id=product_id, lot_no=lot_no)
        
        # 步驟 2: 搜尋對應的 P1 記錄
        p1_query = select(Record).where(
            and_(
                Record.lot_no == lot_no,
                Record.data_type == DataType.P1
            )
        ).order_by(Record.created_at.desc())
        
        p1_result = await db.execute(p1_query)
        p1_records = p1_result.scalars().all()
        
        # 步驟 3: 搜尋對應的 P2 記錄
        p2_query = select(Record).where(
            and_(
                Record.lot_no == lot_no,
                Record.data_type == DataType.P2
            )
        ).order_by(Record.created_at.desc())
        
        p2_result = await db.execute(p2_query)
        p2_records = p2_result.scalars().all()
        
        # 轉換為回應格式
        def convert_to_query_record(record: Record) -> QueryRecord:
            """將 Record 轉換為 QueryRecord"""
            query_record = QueryRecord(
                id=str(record.id),
                lot_no=record.lot_no,
                data_type=record.data_type.value,
                production_date=record.production_date.isoformat() if record.production_date else None,
                created_at=record.created_at.isoformat(),
                display_name=record.display_name,
                additional_data=record.additional_data
            )
            
            if record.data_type == DataType.P1:
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            elif record.data_type == DataType.P2:
                query_record.sheet_width = record.sheet_width
                query_record.thickness1 = record.thickness1
                query_record.thickness2 = record.thickness2
                query_record.thickness3 = record.thickness3
                query_record.thickness4 = record.thickness4
                query_record.thickness5 = record.thickness5
                query_record.thickness6 = record.thickness6
                query_record.thickness7 = record.thickness7
                query_record.appearance = record.appearance
                query_record.rough_edge = record.rough_edge
                query_record.slitting_result = record.slitting_result
            elif record.data_type == DataType.P3:
                query_record.p3_no = record.p3_no
                query_record.product_name = record.product_name
                query_record.quantity = record.quantity
                query_record.notes = record.notes
            
            return query_record
        
        # 組合回應
        response = ProductIDSearchResponse(
            product_id=product_id,
            lot_no=lot_no,
            p3_data=convert_to_query_record(p3_record),
            p1_data=[convert_to_query_record(r) for r in p1_records],
            p2_data=[convert_to_query_record(r) for r in p2_records],
            p1_count=len(p1_records),
            p2_count=len(p2_records)
        )
        
        logger.info(
            "搜尋完成",
            product_id=product_id,
            lot_no=lot_no,
            p1_count=len(p1_records),
            p2_count=len(p2_records)
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("搜尋 Product ID 時發生錯誤", product_id=product_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"搜尋時發生錯誤：{str(e)}"
        )


@router.get(
    "/search/product-id/suggestions",
    response_model=List[str],
    summary="Product ID 自動完成建議",
    description="根據輸入關鍵字提供 Product ID 的自動完成建議"
)
async def get_product_id_suggestions(
    query: str = Query(..., min_length=1, description="搜尋關鍵字"),
    limit: int = Query(10, ge=1, le=50, description="建議數量限制"),
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """
    取得 Product ID 搜尋建議
    
    Args:
        query: 搜尋關鍵字
        limit: 建議數量限制
        db: 資料庫會話
    
    Returns:
        List[str]: Product ID 建議列表
    """
    try:
        # 查詢符合條件的 product_id，按字母順序排序並去重
        query_filter = f"%{query.strip()}%"
        sql_query = (
            select(Record.product_id)
            .where(
                and_(
                    Record.product_id.isnot(None),
                    Record.product_id.ilike(query_filter),
                    Record.data_type == DataType.P3
                )
            )
            .distinct()
            .order_by(Record.product_id.desc())  # 最新的在前面
            .limit(limit)
        )
        
        result = await db.execute(sql_query)
        suggestions = [row[0] for row in result.fetchall()]
        
        logger.info("Product ID 建議查詢完成", query=query, count=len(suggestions))
        return suggestions
        
    except Exception as e:
        logger.error("查詢 Product ID 建議時發生錯誤", query=query, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"查詢建議時發生錯誤：{str(e)}"
        )
```

### 3. 更新匯入服務自動生成 Product ID

**檔案**: `form-analysis-server/backend/app/services/import_service.py`

在 P3 資料匯入時自動生成 Product ID：

```python
# 在 import_service.py 中的 P3 資料處理部分

from app.services.product_id_generator import ProductIDGenerator

# 在建立 P3 Record 時，自動生成 product_id
# 假設 CSV 包含 machine_no, mold_no, production_sequence 欄位

async def import_p3_records(self, df: pd.DataFrame, lot_no: str, upload_job_id: uuid.UUID):
    """匯入 P3 資料並自動生成 Product ID"""
    
    for index, row in df.iterrows():
        try:
            # 從 lot_no 解析生產日期（格式：YYYYMMDD_##）
            production_date = self._parse_production_date_from_lot_no(lot_no)
            
            # 讀取必要欄位
            machine_no = str(row.get('machine_no', '01'))  # 機台號碼
            mold_no = str(row.get('mold_no', '01'))  # 模具號碼
            production_sequence = int(row.get('production_sequence', index + 1))  # 生產序號
            
            # 生成 Product ID
            product_id = ProductIDGenerator.generate_product_id(
                production_date=production_date,
                machine_no=machine_no,
                mold_no=mold_no,
                production_sequence=production_sequence
            )
            
            # 建立 P3 記錄
            record = Record(
                lot_no=lot_no,
                data_type=DataType.P3,
                production_date=production_date,
                product_id=product_id,  # ← 新增
                machine_no=machine_no,  # ← 新增
                mold_no=mold_no,  # ← 新增
                production_sequence=production_sequence,  # ← 新增
                p3_no=row.get('p3_no'),
                product_name=row.get('product_name'),
                quantity=row.get('quantity'),
                notes=row.get('notes'),
                additional_data={...}  # 其他欄位
            )
            
            db.add(record)
            
        except Exception as e:
            logger.error(f"匯入 P3 記錄失敗", row_index=index, error=str(e))
            continue
    
    await db.commit()
```

---

## 🎨 前端實作

### 1. Product ID 搜尋元件

**檔案**: `form-analysis-server/frontend/src/components/ProductIDSearch.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:18002';

interface P3Data {
  id: string;
  lot_no: string;
  product_id?: string;
  p3_no?: string;
  product_name?: string;
  quantity?: number;
  production_date?: string;
  notes?: string;
}

interface P1Data {
  id: string;
  lot_no: string;
  product_name?: string;
  quantity?: number;
  production_date?: string;
  notes?: string;
}

interface P2Data {
  id: string;
  lot_no: string;
  sheet_width?: number;
  thickness1?: number;
  thickness2?: number;
  thickness3?: number;
  thickness4?: number;
  thickness5?: number;
  thickness6?: number;
  thickness7?: number;
  appearance?: number;
  rough_edge?: number;
  slitting_result?: number;
}

interface SearchResult {
  product_id: string;
  lot_no: string;
  p3_data: P3Data | null;
  p1_data: P1Data[];
  p2_data: P2Data[];
  p1_count: number;
  p2_count: number;
}

export const ProductIDSearch: React.FC = () => {
  const [productId, setProductId] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // 自動完成建議
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (productId.trim().length < 3) {
        setSuggestions([]);
        return;
      }

      try {
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/query/search/product-id/suggestions`,
          {
            params: { query: productId, limit: 10 }
          }
        );
        setSuggestions(response.data);
        setShowSuggestions(true);
      } catch (err) {
        console.error('取得建議失敗:', err);
      }
    };

    const debounceTimer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(debounceTimer);
  }, [productId]);

  // 搜尋函數
  const handleSearch = async () => {
    if (!productId.trim()) {
      setError('請輸入 Product ID');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSearchResult(null);

    try {
      const response = await axios.get<SearchResult>(
        `${API_BASE_URL}/api/v1/query/search/product-id`,
        {
          params: { product_id: productId.trim() }
        }
      );
      setSearchResult(response.data);
      setShowSuggestions(false);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError(`找不到 Product ID: ${productId} 的記錄`);
      } else {
        setError(err.response?.data?.detail || '搜尋時發生錯誤');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // 選擇建議項目
  const handleSelectSuggestion = (suggestion: string) => {
    setProductId(suggestion);
    setShowSuggestions(false);
  };

  return (
    <div className="product-id-search-container">
      <div className="search-section">
        <h2>根據 Product ID 搜尋</h2>
        
        {/* 搜尋輸入框 */}
        <div className="search-input-group">
          <input
            type="text"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="輸入 Product ID (例: 20250310-M01-D05-S001)"
            className="search-input"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="search-button"
          >
            {isLoading ? '搜尋中...' : '搜尋'}
          </button>
        </div>

        {/* 自動完成建議 */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="suggestions-dropdown">
            {suggestions.map((suggestion, index) => (
              <div
                key={index}
                className="suggestion-item"
                onClick={() => handleSelectSuggestion(suggestion)}
              >
                {suggestion}
              </div>
            ))}
          </div>
        )}

        {/* 錯誤訊息 */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}
      </div>

      {/* 搜尋結果 */}
      {searchResult && (
        <div className="search-results">
          {/* 基本資訊 */}
          <div className="result-summary">
            <h3>搜尋結果</h3>
            <p><strong>Product ID:</strong> {searchResult.product_id}</p>
            <p><strong>批號 (Lot No):</strong> {searchResult.lot_no}</p>
            <p>
              <strong>找到:</strong> 
              {searchResult.p3_data ? ' 1 筆 P3 資料' : ''} 
              {searchResult.p1_count > 0 ? `, ${searchResult.p1_count} 筆 P1 資料` : ''} 
              {searchResult.p2_count > 0 ? `, ${searchResult.p2_count} 筆 P2 資料` : ''}
            </p>
          </div>

          {/* P3 資料 */}
          {searchResult.p3_data && (
            <div className="data-section p3-section">
              <h4>P3 - 追蹤編號資料</h4>
              <table className="data-table">
                <tbody>
                  <tr>
                    <th>P3 編號</th>
                    <td>{searchResult.p3_data.p3_no || '-'}</td>
                  </tr>
                  <tr>
                    <th>產品名稱</th>
                    <td>{searchResult.p3_data.product_name || '-'}</td>
                  </tr>
                  <tr>
                    <th>數量</th>
                    <td>{searchResult.p3_data.quantity || '-'}</td>
                  </tr>
                  <tr>
                    <th>生產日期</th>
                    <td>{searchResult.p3_data.production_date || '-'}</td>
                  </tr>
                  <tr>
                    <th>備註</th>
                    <td>{searchResult.p3_data.notes || '-'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          {/* P1 資料 */}
          {searchResult.p1_data.length > 0 && (
            <div className="data-section p1-section">
              <h4>P1 - 產品基本資料 ({searchResult.p1_count} 筆)</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>產品名稱</th>
                    <th>數量</th>
                    <th>生產日期</th>
                    <th>備註</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResult.p1_data.map((p1, index) => (
                    <tr key={p1.id || index}>
                      <td>{p1.product_name || '-'}</td>
                      <td>{p1.quantity || '-'}</td>
                      <td>{p1.production_date || '-'}</td>
                      <td>{p1.notes || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* P2 資料 */}
          {searchResult.p2_data.length > 0 && (
            <div className="data-section p2-section">
              <h4>📏 P2 - 尺寸檢測資料 ({searchResult.p2_count} 筆)</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>片材寬度</th>
                    <th>厚度1</th>
                    <th>厚度2</th>
                    <th>厚度3</th>
                    <th>厚度4</th>
                    <th>厚度5</th>
                    <th>厚度6</th>
                    <th>厚度7</th>
                    <th>外觀</th>
                    <th>粗糙邊緣</th>
                    <th>切割結果</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResult.p2_data.map((p2, index) => (
                    <tr key={p2.id || index}>
                      <td>{p2.sheet_width?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness1?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness2?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness3?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness4?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness5?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness6?.toFixed(2) || '-'}</td>
                      <td>{p2.thickness7?.toFixed(2) || '-'}</td>
                      <td>{p2.appearance === 1 ? '✅' : p2.appearance === 0 ? '❌' : '-'}</td>
                      <td>{p2.rough_edge === 1 ? '✅' : p2.rough_edge === 0 ? '❌' : '-'}</td>
                      <td>{p2.slitting_result === 1 ? '✅' : p2.slitting_result === 0 ? '❌' : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 無資料提示 */}
          {!searchResult.p1_data.length && !searchResult.p2_data.length && (
            <div className="no-data-message">
              找到 P3 記錄，但沒有對應的 P1 或 P2 資料
            </div>
          )}
        </div>
      )}
    </div>
  );
};
```

### 2. 樣式檔案

**檔案**: `form-analysis-server/frontend/src/components/ProductIDSearch.css`

```css
.product-id-search-container {
  max-width: 1200px;
  margin: 20px auto;
  padding: 20px;
}

.search-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.search-section h2 {
  margin-bottom: 15px;
  color: #333;
}

.search-input-group {
  display: flex;
  gap: 10px;
  position: relative;
}

.search-input {
  flex: 1;
  padding: 12px 15px;
  border: 2px solid #ddd;
  border-radius: 5px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.search-input:focus {
  outline: none;
  border-color: #4CAF50;
}

.search-button {
  padding: 12px 30px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 5px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.3s;
}

.search-button:hover:not(:disabled) {
  background: #45a049;
}

.search-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 110px;
  background: white;
  border: 1px solid #ddd;
  border-top: none;
  border-radius: 0 0 5px 5px;
  max-height: 300px;
  overflow-y: auto;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  margin-top: 2px;
}

.suggestion-item {
  padding: 10px 15px;
  cursor: pointer;
  transition: background 0.2s;
}

.suggestion-item:hover {
  background: #f0f0f0;
}

.error-message {
  margin-top: 10px;
  padding: 12px;
  background: #ffebee;
  color: #c62828;
  border-radius: 5px;
  border-left: 4px solid #c62828;
}

.search-results {
  margin-top: 20px;
}

.result-summary {
  background: #e3f2fd;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 20px;
  border-left: 4px solid #2196F3;
}

.result-summary h3 {
  margin-top: 0;
  color: #1976D2;
}

.result-summary p {
  margin: 8px 0;
}

.data-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.data-section h4 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
}

.p3-section h4 {
  color: #FF9800;
}

.p1-section h4 {
  color: #4CAF50;
}

.p2-section h4 {
  color: #2196F3;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

.data-table th,
.data-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.data-table th {
  background: #f5f5f5;
  font-weight: 600;
  color: #555;
}

.data-table tbody tr:hover {
  background: #f9f9f9;
}

.no-data-message {
  padding: 20px;
  text-align: center;
  color: #666;
  background: #fff9e6;
  border-radius: 5px;
  border: 1px dashed #ffb300;
}
```

### 3. 整合到主應用

**檔案**: `form-analysis-server/frontend/src/App.tsx`

```typescript
import { ProductIDSearch } from './components/ProductIDSearch';

// 在路由配置中新增
<Route path="/product-search" element={<ProductIDSearch />} />
```

**檔案**: `form-analysis-server/frontend/src/components/layout/Header.tsx`

```typescript
// 新增導航連結
<Link to="/product-search">Product ID 搜尋</Link>
```

---

## API 文檔

### 1. 根據 Product ID 搜尋

**端點**: `GET /api/v1/query/search/product-id`

**查詢參數**:
```
product_id: string (必填) - Product ID，格式：YYYYMMDD-M##-D##-S###
```

**回應格式**:
```json
{
  "product_id": "20250310-M01-D05-S001",
  "lot_no": "2503033_01",
  "p3_data": {
    "id": "uuid",
    "lot_no": "2503033_01",
    "data_type": "P3",
    "product_id": "20250310-M01-D05-S001",
    "p3_no": "P3-001",
    "product_name": "產品A",
    "quantity": 100,
    "production_date": "2025-03-10",
    "notes": "測試資料"
  },
  "p1_data": [
    {
      "id": "uuid",
      "lot_no": "2503033_01",
      "data_type": "P1",
      "product_name": "產品A",
      "quantity": 100,
      "production_date": "2025-03-10",
      "notes": "P1 資料"
    }
  ],
  "p2_data": [
    {
      "id": "uuid",
      "lot_no": "2503033_01",
      "data_type": "P2",
      "sheet_width": 1250.5,
      "thickness1": 120.5,
      "thickness2": 121.0,
      "thickness3": 119.8,
      "thickness4": 120.2,
      "thickness5": 120.7,
      "thickness6": 120.3,
      "thickness7": 120.1,
      "appearance": 1,
      "rough_edge": 0,
      "slitting_result": 1
    }
  ],
  "p1_count": 1,
  "p2_count": 1
}
```

**錯誤回應**:
- `404`: Product ID 不存在
- `500`: 伺服器錯誤

### 2. Product ID 自動完成建議

**端點**: `GET /api/v1/query/search/product-id/suggestions`

**查詢參數**:
```
query: string (必填) - 搜尋關鍵字
limit: int (選填) - 建議數量，預設 10，最大 50
```

**回應格式**:
```json
[
  "20250310-M01-D05-S001",
  "20250310-M01-D05-S002",
  "20250310-M02-D05-S001"
]
```

---

## 🗃️ 資料庫索引優化

為了提升搜尋效能，建議建立以下索引：

```sql
-- Product ID 索引（已在遷移腳本中建立）
CREATE INDEX ix_records_product_id ON records(product_id);

-- 機台與模具組合索引
CREATE INDEX ix_records_machine_mold ON records(machine_no, mold_no);

-- Lot No 與 Data Type 組合索引（已存在）
CREATE INDEX ix_records_lot_no_data_type ON records(lot_no, data_type);
```

---

## 測試計畫

### 1. 單元測試

**檔案**: `form-analysis-server/backend/tests/test_product_id_search.py`

```python
import pytest
from app.services.product_id_generator import ProductIDGenerator
from datetime import date


def test_generate_product_id():
    """測試 Product ID 生成"""
    product_id = ProductIDGenerator.generate_product_id(
        production_date=date(2025, 3, 10),
        machine_no="1",
        mold_no="5",
        production_sequence=1
    )
    assert product_id == "20250310-M01-D05-S001"


def test_parse_product_id():
    """測試 Product ID 解析"""
    result = ProductIDGenerator.parse_product_id("20250310-M01-D05-S001")
    assert result is not None
    assert result["date"] == "20250310"
    assert result["machine_no"] == "01"
    assert result["mold_no"] == "05"
    assert result["production_sequence"] == 1


@pytest.mark.asyncio
async def test_search_by_product_id(client, test_db):
    """測試 Product ID 搜尋 API"""
    # 建立測試資料
    # ...
    
    # 搜尋測試
    response = await client.get(
        "/api/v1/query/search/product-id",
        params={"product_id": "20250310-M01-D05-S001"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "20250310-M01-D05-S001"
    assert data["p3_data"] is not None
    assert len(data["p1_data"]) > 0
```

### 2. 整合測試

1. **建立測試資料**:
   - 匯入包含 machine_no, mold_no, production_sequence 的 P3 CSV
   - 確認 Product ID 自動生成

2. **搜尋測試**:
   - 使用生成的 Product ID 進行搜尋
   - 驗證返回的 P1、P2 資料正確

3. **邊界測試**:
   - 搜尋不存在的 Product ID
   - 搜尋只有 P3 沒有 P1/P2 的情況
   - 測試自動完成建議功能

---

## 實作檢查清單

### 後端 (Backend)

- [ ] 1. 更新 `record.py` 模型，新增 product_id、machine_no、mold_no、production_sequence 欄位
- [ ] 2. 建立資料庫遷移腳本
- [ ] 3. 執行資料庫遷移 (`alembic upgrade head`)
- [ ] 4. 建立 `product_id_generator.py` 服務
- [ ] 5. 在 `routes_query.py` 新增搜尋 API 端點
- [ ] 6. 更新 `import_service.py`，在 P3 匯入時自動生成 Product ID
- [ ] 7. 更新 `QueryRecord` schema，新增 product_id 相關欄位
- [ ] 8. 撰寫單元測試
- [ ] 9. 測試 API 端點（使用 Swagger UI 或 Postman）

### 前端 (Frontend)

- [ ] 10. 建立 `ProductIDSearch.tsx` 元件
- [ ] 11. 建立 `ProductIDSearch.css` 樣式檔案
- [ ] 12. 在 `App.tsx` 新增路由
- [ ] 13. 在 Header 新增導航連結
- [ ] 14. 測試搜尋功能
- [ ] 15. 測試自動完成建議
- [ ] 16. 測試 UI 顯示（P1、P2、P3 資料）

### 文檔與測試

- [ ] 17. 更新 README.md，說明 Product ID 搜尋功能
- [ ] 18. 準備測試用 CSV 資料（包含 machine_no、mold_no、production_sequence）
- [ ] 19. 執行完整功能測試
- [ ] 20. 測試效能（大量資料下的搜尋速度）

---

## 部署建議

### 1. 資料遷移步驟

```bash
# 1. 備份資料庫
pg_dump -h localhost -p 18001 -U postgres -d form_analysis_db > backup_before_product_id.sql

# 2. 執行遷移
cd form-analysis-server/backend
alembic upgrade head

# 3. 驗證遷移
psql -h localhost -p 18001 -U postgres -d form_analysis_db -c "\d records"
```

### 2. 後向相容性

- 舊的 P3 資料（沒有 Product ID）：
  - `product_id` 欄位為 NULL
  - 不影響現有搜尋功能
  - 可選：執行資料補齊腳本為舊資料生成 Product ID

### 3. 效能監控

- 監控 Product ID 搜尋的回應時間
- 確認索引使用情況 (`EXPLAIN ANALYZE`)
- 必要時調整索引策略

---

## 💡 擴展建議

### 1. 進階搜尋

- 支援批次搜尋（一次輸入多個 Product ID）
- 支援日期範圍搜尋
- 支援機台號碼篩選

### 2. 資料匯出

- 提供搜尋結果匯出為 Excel 功能
- 支援 PDF 報表生成

### 3. 視覺化

- 顯示 P2 檢測資料的圖表（厚度分佈、合格率等）
- 時間軸顯示生產歷程

---

## 常見問題

### Q1: Product ID 格式錯誤怎麼辦？

**A**: 在匯入時進行驗證，確保 CSV 包含必要欄位（machine_no、mold_no、production_sequence），並檢查格式正確性。

### Q2: 同一個 Product ID 可能重複嗎？

**A**: 理論上不應該重複，但可以在資料庫加上唯一約束：

```sql
ALTER TABLE records ADD CONSTRAINT uq_product_id UNIQUE (product_id);
```

### Q3: 如果只有 P3 沒有 P1/P2 怎麼辦？

**A**: 系統會正常返回 P3 資料，並標示 `p1_count: 0`, `p2_count: 0`，前端顯示提示訊息。

### Q4: 搜尋速度慢怎麼辦？

**A**: 
1. 確認索引已建立 (`ix_records_product_id`, `ix_records_lot_no_data_type`)
2. 使用 `EXPLAIN ANALYZE` 分析查詢計畫
3. 考慮使用 Redis 快取熱門搜尋結果

---

## 總結

本實作方案提供了完整的 Product ID 搜尋功能，包括：

**資料庫層**：新增欄位、索引、遷移腳本  
**後端層**：Product ID 生成服務、搜尋 API、自動完成建議  
**前端層**：搜尋元件、結果顯示、自動完成  
**測試層**：單元測試、整合測試計畫  

**建議實作順序**：
1. 資料庫遷移（1-3）
2. 後端 API（4-7）
3. 前端介面（10-13）
4. 測試與驗證（8-9, 14-16）
5. 文檔與部署（17-20）

**預估工作時間**：2-3 天

如有任何問題，歡迎隨時詢問！
