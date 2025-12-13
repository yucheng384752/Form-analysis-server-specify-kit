# 功能需求分析與實作方案

**文檔日期**: 2025年12月9日  
**版本**: 1.0

---

## 需求概述

本文檔針對三個新增功能需求提供詳細的技術分析和實作方案：

1. **P3 特定欄位搜尋功能**
2. **PDF 檔案上傳支援**
3. **生產日期自動套用 lot_no 邏輯**

---

## 1️⃣ P3 特定欄位搜尋功能

### 現況分析

#### 當前資料庫設計
```python
# Record 模型中的 P3 相關欄位
class Record(Base):
    # 基本欄位
    lot_no: str                    # 批號 (7位數字_2位數字)
    data_type: DataType            # P1/P2/P3
    production_date: Optional[date] # 生產日期
    
    # P3 專用欄位
    p3_no: Optional[str]           # P3追蹤編號
    product_name: Optional[str]    # 產品名稱
    quantity: Optional[int]        # 數量
    notes: Optional[str]           # 備註
    
    # 額外資料 (JSONB)
    additional_data: Optional[Dict[str, Any]]  # 儲存CSV中的其他欄位
```

#### 現有索引
```python
# 已建立的索引
Index("ix_records_lot_no_data_type", Record.lot_no, Record.data_type)
Index("ix_records_lot_no", Record.lot_no)
Index("ix_records_data_type", Record.data_type)
```

### 結論：**可以做到！**

當前資料庫設計**完全支援** P3 特定欄位搜尋，原因如下：

1. **專用欄位已定義**: `p3_no`, `product_name`, `quantity`, `notes`
2. **JSONB 彈性欄位**: `additional_data` 可儲存任何額外的 P3 欄位
3. **已有索引支援**: `lot_no` 和 `data_type` 都有索引，查詢效能良好

### 實作方案

#### 方案 A：基本欄位搜尋（推薦）

**優點**: 簡單、效能好、支援索引  
**適用**: 搜尋 `p3_no`, `product_name`, `quantity`, `notes`, `lot_no`

```python
# 在 routes_query.py 新增
@router.get(
    "/p3/search",
    response_model=QueryResponse,
    summary="P3 資料進階搜尋",
    description="支援多欄位搜尋 P3 資料"
)
async def search_p3_records(
    p3_no: Optional[str] = Query(None, description="P3追蹤編號（支援模糊搜尋）"),
    product_name: Optional[str] = Query(None, description="產品名稱（支援模糊搜尋）"),
    lot_no: Optional[str] = Query(None, description="批號（支援模糊搜尋）"),
    quantity_min: Optional[int] = Query(None, description="數量最小值"),
    quantity_max: Optional[int] = Query(None, description="數量最大值"),
    production_date_start: Optional[date] = Query(None, description="生產日期起始"),
    production_date_end: Optional[date] = Query(None, description="生產日期結束"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(20, ge=1, le=100, description="每頁記錄數"),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """P3 資料進階搜尋"""
    
    # 建構查詢條件
    conditions = [Record.data_type == DataType.P3]
    
    # P3 編號模糊搜尋
    if p3_no:
        conditions.append(Record.p3_no.ilike(f"%{p3_no}%"))
    
    # 產品名稱模糊搜尋
    if product_name:
        conditions.append(Record.product_name.ilike(f"%{product_name}%"))
    
    # 批號模糊搜尋
    if lot_no:
        conditions.append(Record.lot_no.ilike(f"%{lot_no}%"))
    
    # 數量範圍搜尋
    if quantity_min is not None:
        conditions.append(Record.quantity >= quantity_min)
    if quantity_max is not None:
        conditions.append(Record.quantity <= quantity_max)
    
    # 生產日期範圍搜尋
    if production_date_start:
        conditions.append(Record.production_date >= production_date_start)
    if production_date_end:
        conditions.append(Record.production_date <= production_date_end)
    
    # 執行查詢
    query_stmt = select(Record).where(and_(*conditions))
    
    # 計算總數
    count_query = select(func.count(Record.id)).where(and_(*conditions))
    result = await db.execute(count_query)
    total_count = result.scalar() or 0
    
    # 分頁
    offset = (page - 1) * page_size
    query_stmt = query_stmt.order_by(Record.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query_stmt)
    records = result.scalars().all()
    
    # 轉換為回應格式
    return QueryResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        records=[convert_record_to_query_record(r) for r in records]
    )
```

#### 方案 B：JSONB 欄位搜尋（進階）

**優點**: 支援任意動態欄位  
**適用**: 搜尋 CSV 中的其他自定義欄位（如溫度、編號等）

```python
@router.get(
    "/p3/search-advanced",
    response_model=QueryResponse,
    summary="P3 資料 JSONB 進階搜尋",
    description="支援搜尋 additional_data 中的任意欄位"
)
async def search_p3_jsonb(
    field_name: str = Query(..., description="JSONB 欄位名稱"),
    field_value: str = Query(..., description="欄位值"),
    search_mode: str = Query("exact", description="搜尋模式: exact(精確), contains(包含)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """搜尋 P3 資料的 JSONB 欄位"""
    
    conditions = [Record.data_type == DataType.P3]
    
    if search_mode == "exact":
        # 精確搜尋: additional_data->>'field_name' = 'value'
        conditions.append(
            Record.additional_data[field_name].astext == field_value
        )
    else:  # contains
        # 模糊搜尋: additional_data->>'field_name' LIKE '%value%'
        conditions.append(
            Record.additional_data[field_name].astext.ilike(f"%{field_value}%")
        )
    
    # ... 執行查詢邏輯（同方案A）
```

#### 建議的索引優化

```python
# 在 record.py 中新增索引
# 針對 P3 常用搜尋欄位建立索引
Index(
    "ix_records_p3_no",
    Record.p3_no,
    postgresql_where=(Record.data_type == 'P3'),
    postgresql_using="btree"
)

Index(
    "ix_records_p3_product_name",
    Record.product_name,
    postgresql_where=(Record.data_type == 'P3'),
    postgresql_using="btree"
)

# JSONB 欄位索引（如果需要搜尋 additional_data）
Index(
    "ix_records_additional_data_gin",
    Record.additional_data,
    postgresql_using="gin"
)
```

### 資料庫遷移

```bash
# 建立新的遷移
cd form-analysis-server/backend
alembic revision -m "add_p3_search_indexes"

# 在生成的遷移文件中添加索引
# 然後執行遷移
alembic upgrade head
```

---

## 2️⃣ PDF 檔案上傳支援

### 現況分析

#### 當前上傳邏輯
```python
# routes_upload.py
# 目前僅支援 CSV 和 Excel
def _is_supported_file(filename: str) -> bool:
    filename_lower = filename.lower()
    return (filename_lower.endswith('.csv') or 
            filename_lower.endswith('.xlsx') or 
            filename_lower.endswith('.xls'))
```

### 實作方案

#### 整體修改方向

```
現有流程: 
上傳 → 驗證格式 → 讀取表格 → 驗證資料 → 匯入資料庫

新增流程:
上傳 → 驗證格式 → 判斷檔案類型 → 
  ├─ CSV/Excel: 讀取表格 → 驗證 → 匯入
  └─ PDF: OCR提取 → 轉換為表格 → 驗證 → 匯入
```

#### 步驟 1: 安裝 PDF 處理套件

```bash
# requirements.txt 新增
pdfplumber==0.10.3      # PDF 文字提取
PyPDF2==3.0.1           # PDF 基礎操作
tabula-py==2.9.0        # PDF 表格提取（推薦）
camelot-py[cv]==0.11.0  # 進階 PDF 表格提取（可選）
pytesseract==0.3.10     # OCR 文字識別（如果需要）
Pillow==10.1.0          # 圖片處理
```

#### 步驟 2: 修改檔案驗證邏輯

```python
# services/validation.py

class FileValidationService:
    
    SUPPORTED_FORMATS = {
        'csv': ['.csv'],
        'excel': ['.xlsx', '.xls'],
        'pdf': ['.pdf']
    }
    
    def _is_supported_file(self, filename: str) -> bool:
        """檢查檔案格式是否支援"""
        filename_lower = filename.lower()
        for format_type, extensions in self.SUPPORTED_FORMATS.items():
            if any(filename_lower.endswith(ext) for ext in extensions):
                return True
        return False
    
    def _get_file_type(self, filename: str) -> str:
        """取得檔案類型"""
        filename_lower = filename.lower()
        for format_type, extensions in self.SUPPORTED_FORMATS.items():
            if any(filename_lower.endswith(ext) for ext in extensions):
                return format_type
        raise ValidationError("不支援的檔案格式")
```

#### 步驟 3: 新增 PDF 處理服務

```python
# services/pdf_processor.py

import io
import pandas as pd
import tabula
from typing import BinaryIO, Dict, Any, List
from app.core.logging import get_logger

logger = get_logger(__name__)


class PDFProcessorService:
    """PDF 檔案處理服務"""
    
    def __init__(self):
        self.supported_methods = ['tabula', 'camelot', 'pdfplumber']
    
    async def extract_tables_from_pdf(
        self, 
        file_content: BinaryIO, 
        method: str = 'tabula'
    ) -> pd.DataFrame:
        """
        從 PDF 提取表格資料
        
        Args:
            file_content: PDF 檔案內容
            method: 提取方法 (tabula/camelot/pdfplumber)
            
        Returns:
            pd.DataFrame: 提取的表格資料
            
        Raises:
            ValidationError: 提取失敗時拋出
        """
        try:
            if method == 'tabula':
                return await self._extract_with_tabula(file_content)
            elif method == 'camelot':
                return await self._extract_with_camelot(file_content)
            elif method == 'pdfplumber':
                return await self._extract_with_pdfplumber(file_content)
            else:
                raise ValueError(f"不支援的提取方法: {method}")
                
        except Exception as e:
            logger.error(f"PDF 表格提取失敗: {str(e)}")
            raise ValidationError(f"無法從 PDF 提取表格資料: {str(e)}")
    
    async def _extract_with_tabula(self, file_content: BinaryIO) -> pd.DataFrame:
        """使用 tabula-py 提取 PDF 表格"""
        try:
            # 將 BinaryIO 儲存為臨時檔案
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(file_content.read())
                tmp_path = tmp.name
            
            # 使用 tabula 讀取所有表格
            tables = tabula.read_pdf(
                tmp_path,
                pages='all',
                multiple_tables=True,
                pandas_options={'header': 0}
            )
            
            if not tables:
                raise ValidationError("PDF 中未找到表格")
            
            # 如果有多個表格，合併它們
            if len(tables) > 1:
                logger.warning(f"PDF 包含 {len(tables)} 個表格，將合併為一個")
                df = pd.concat(tables, ignore_index=True)
            else:
                df = tables[0]
            
            # 清理臨時檔案
            import os
            os.unlink(tmp_path)
            
            return df
            
        except Exception as e:
            raise ValidationError(f"Tabula 提取失敗: {str(e)}")
    
    async def _extract_with_pdfplumber(self, file_content: BinaryIO) -> pd.DataFrame:
        """使用 pdfplumber 提取 PDF 表格"""
        import pdfplumber
        
        try:
            file_content.seek(0)
            with pdfplumber.open(file_content) as pdf:
                all_tables = []
                
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
                
                if not all_tables:
                    raise ValidationError("PDF 中未找到表格")
                
                # 將第一個表格的第一行作為欄位名稱
                if all_tables:
                    headers = all_tables[0][0]
                    data = []
                    for table in all_tables:
                        data.extend(table[1:])  # 跳過標題行
                    
                    df = pd.DataFrame(data, columns=headers)
                    return df
                    
        except Exception as e:
            raise ValidationError(f"PDFPlumber 提取失敗: {str(e)}")
    
    def validate_pdf_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        驗證 PDF 提取的表格結構
        
        Returns:
            Dict: 驗證結果
        """
        issues = []
        
        # 檢查是否有空白欄位名稱
        unnamed_cols = [col for col in df.columns if 'Unnamed' in str(col) or pd.isna(col)]
        if unnamed_cols:
            issues.append(f"發現 {len(unnamed_cols)} 個未命名的欄位")
        
        # 檢查是否有完全空白的行
        empty_rows = df.isna().all(axis=1).sum()
        if empty_rows > 0:
            issues.append(f"發現 {empty_rows} 個空白行")
        
        # 檢查是否有完全空白的列
        empty_cols = df.isna().all(axis=0).sum()
        if empty_cols > 0:
            issues.append(f"發現 {empty_cols} 個空白列")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'rows': len(df),
            'columns': len(df.columns)
        }


# 建立單例
pdf_processor_service = PDFProcessorService()
```

#### 步驟 4: 修改上傳路由

```python
# routes_upload.py

from app.services.pdf_processor import pdf_processor_service

async def upload_file(
    file: UploadFile = File(..., description="要上傳的 CSV、Excel 或 PDF 檔案"),
    db: AsyncSession = Depends(get_db)
) -> FileUploadResponse:
    """處理檔案上傳和驗證"""
    
    # ... 現有的驗證邏輯 ...
    
    # 判斷檔案類型
    file_type = file_validation_service._get_file_type(file.filename)
    
    if file_type == 'pdf':
        # PDF 特殊處理
        logger.info("處理 PDF 檔案", filename=file.filename)
        
        try:
            # 讀取 PDF 內容
            file_content = await file.read()
            file_like = io.BytesIO(file_content)
            
            # 提取表格
            df = await pdf_processor_service.extract_tables_from_pdf(file_like)
            
            # 驗證 PDF 表格結構
            structure_validation = pdf_processor_service.validate_pdf_structure(df)
            if not structure_validation['valid']:
                logger.warning("PDF 表格結構問題", issues=structure_validation['issues'])
            
            # 繼續使用現有的驗證流程
            validation_result = await file_validation_service.validate_data(
                df=df,
                filename=file.filename
            )
            
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=f"PDF 處理失敗: {str(e)}"
            )
    else:
        # CSV/Excel 使用現有邏輯
        validation_result = await file_validation_service.validate_file(
            file=file
        )
    
    # ... 剩餘的處理邏輯 ...
```

#### 步驟 5: 更新前端上傳組件

```typescript
// frontend/src/components/FileUpload.tsx

const ACCEPTED_FILE_TYPES = {
  'text/csv': ['.csv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/pdf': ['.pdf']  // 新增 PDF
};

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function FileUpload() {
  // ... 
  
  const validateFile = (file: File): boolean => {
    // 檢查檔案類型
    const isValidType = Object.entries(ACCEPTED_FILE_TYPES).some(
      ([mimeType, extensions]) => 
        file.type === mimeType || 
        extensions.some(ext => file.name.toLowerCase().endsWith(ext))
    );
    
    if (!isValidType) {
      toast.error('僅支援 CSV、Excel (.xlsx, .xls) 和 PDF 檔案');
      return false;
    }
    
    // 檢查檔案大小
    if (file.size > MAX_FILE_SIZE) {
      toast.error('檔案大小不可超過 10MB');
      return false;
    }
    
    return true;
  };
  
  // ...
}
```

### 注意事項

1. **PDF 品質影響**:
   - 掃描品質差的 PDF 可能無法正確提取
   - 建議使用電子生成的 PDF（非掃描檔）
   - 如需處理掃描 PDF，需要整合 OCR（Tesseract）

2. **表格識別**:
   - PDF 表格結構複雜時可能提取失敗
   - 建議提供「手動調整」功能讓使用者修正

3. **效能考量**:
   - PDF 處理比 CSV 慢很多
   - 建議設定較長的 timeout
   - 考慮使用背景任務處理大型 PDF

4. **錯誤處理**:
   - 提供清晰的錯誤訊息
   - 建議使用者上傳 CSV 格式以獲得最佳效果

---

## 3️⃣ 生產日期自動套用 lot_no

### 現況分析

#### Lot_no 格式規則
```
格式: YYYYMDD_BB
- YYYYMDD: 7位數字，代表年月日
  - YY: 年份後2碼 (如 25 = 2025年)
  - MM: 月份 (01-12)
  - DD: 日期 (01-31)
- BB: 批次編號 (01-99)

範例: 2503033_01
解析: 25年03月03日，第01批
```

#### 當前生產日期處理
- P1/P2: 從檔案名稱提取 lot_no
- P3: 從 "P3_No." 欄位提取 lot_no
- 生產日期: 可能為空白或不正確

### 實作方案

#### 步驟 1: 建立 lot_no 解析工具

```python
# services/lot_no_parser.py

from datetime import date, datetime
from typing import Optional, Tuple
import re
from app.core.logging import get_logger

logger = get_logger(__name__)


class LotNoParser:
    """Lot_no 解析工具"""
    
    # lot_no 格式: YYYYMDD_BB (7位數字_2位數字)
    LOT_NO_PATTERN = re.compile(r'^(\d{2})(\d{2})(\d{2})(\d{1})_(\d{2})$')
    
    @classmethod
    def parse_production_date(cls, lot_no: str) -> Optional[date]:
        """
        從 lot_no 解析生產日期
        
        Args:
            lot_no: 批號 (格式: 2503033_01)
            
        Returns:
            date: 生產日期，解析失敗則返回 None
            
        Examples:
            >>> parse_production_date("2503033_01")
            date(2025, 3, 3)
            
            >>> parse_production_date("2412311_05")
            date(2024, 12, 31)
        """
        try:
            match = cls.LOT_NO_PATTERN.match(lot_no)
            if not match:
                logger.warning(f"lot_no 格式不正確: {lot_no}")
                return None
            
            yy, mm, dd_tens, dd_ones, batch = match.groups()
            
            # 組合日期
            year = 2000 + int(yy)  # 25 -> 2025
            month = int(mm)
            day = int(dd_tens + dd_ones)  # "3" + "3" -> 33 (錯誤！)
            
            # 特殊處理: dd可能是 "033" 格式 (月份+日期)
            # 2503033 應該解析為: 25年03月03日
            if day > 31:
                # 重新解析: 前2位是月份，後2位是日期
                date_part = yy + mm + dd_tens + dd_ones  # "2503033"
                year = 2000 + int(date_part[0:2])   # "25" -> 2025
                month = int(date_part[2:4])          # "03" -> 3
                day = int(date_part[4:6])            # "03" -> 3
            
            # 驗證日期合法性
            production_date = date(year, month, day)
            
            logger.debug(f"解析 lot_no: {lot_no} -> {production_date}")
            return production_date
            
        except (ValueError, AttributeError) as e:
            logger.error(f"解析 lot_no 失敗: {lot_no}, 錯誤: {str(e)}")
            return None
    
    @classmethod
    def validate_lot_no_format(cls, lot_no: str) -> Tuple[bool, Optional[str]]:
        """
        驗證 lot_no 格式
        
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 錯誤訊息)
        """
        if not lot_no or not isinstance(lot_no, str):
            return False, "lot_no 不可為空"
        
        if not cls.LOT_NO_PATTERN.match(lot_no):
            return False, f"lot_no 格式錯誤: {lot_no}，應為 YYYYMDD_BB 格式"
        
        # 嘗試解析日期
        production_date = cls.parse_production_date(lot_no)
        if production_date is None:
            return False, f"lot_no 包含無效的日期: {lot_no}"
        
        return True, None
    
    @classmethod
    def extract_batch_number(cls, lot_no: str) -> Optional[str]:
        """
        提取批次編號
        
        Args:
            lot_no: 批號 (格式: 2503033_01)
            
        Returns:
            str: 批次編號 (如 "01")
        """
        try:
            match = cls.LOT_NO_PATTERN.match(lot_no)
            if match:
                return match.group(5)  # 返回 BB 部分
            return None
        except Exception:
            return None


# 建立單例
lot_no_parser = LotNoParser()
```

#### 步驟 2: 修改驗證服務

```python
# services/validation.py

from app.services.lot_no_parser import lot_no_parser

class FileValidationService:
    
    async def validate_data(self, df: pd.DataFrame, filename: str) -> Dict[str, Any]:
        """驗證資料內容"""
        
        errors = []
        valid_rows = 0
        invalid_rows = 0
        
        for idx, row in df.iterrows():
            row_errors = []
            
            # 取得 lot_no
            lot_no = self._extract_lot_no(row, filename)
            
            # 驗證 lot_no 格式
            is_valid, error_msg = lot_no_parser.validate_lot_no_format(lot_no)
            if not is_valid:
                row_errors.append({
                    'row_index': idx,
                    'field': 'lot_no',
                    'error_code': 'INVALID_FORMAT',
                    'message': error_msg
                })
            
            # 自動解析生產日期（針對 P1 和 P2）
            if is_valid:
                production_date = lot_no_parser.parse_production_date(lot_no)
                if production_date:
                    # 將解析的日期寫入 row
                    df.at[idx, 'production_date'] = production_date
                    logger.info(f"自動設定生產日期: {lot_no} -> {production_date}")
            
            # ... 其他驗證邏輯 ...
            
            if row_errors:
                errors.extend(row_errors)
                invalid_rows += 1
            else:
                valid_rows += 1
        
        return {
            'valid': len(errors) == 0,
            'total_rows': len(df),
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows,
            'errors': errors,
            'dataframe': df  # 返回更新後的 DataFrame
        }
```

#### 步驟 3: 修改匯入服務

```python
# services/import_service.py

from app.services.lot_no_parser import lot_no_parser

class DataImportService:
    
    async def import_records(
        self, 
        df: pd.DataFrame, 
        data_type: DataType,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """匯入資料記錄"""
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # 提取 lot_no
                lot_no = row.get('lot_no')
                
                # 自動解析生產日期（如果沒有提供）
                production_date = row.get('production_date')
                if pd.isna(production_date) or production_date is None:
                    # P1 和 P2 從 lot_no 解析
                    if data_type in [DataType.P1, DataType.P2]:
                        production_date = lot_no_parser.parse_production_date(lot_no)
                        if production_date:
                            logger.info(f"自動設定生產日期: {lot_no} -> {production_date}")
                    # P3 需要特殊處理（見下方）
                    elif data_type == DataType.P3:
                        production_date = self._extract_p3_production_date(row)
                
                # 建立記錄
                record = Record(
                    lot_no=lot_no,
                    data_type=data_type,
                    production_date=production_date,
                    # ... 其他欄位 ...
                )
                
                db.add(record)
                imported_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append({
                    'row_index': idx,
                    'error': str(e)
                })
        
        await db.commit()
        
        return {
            'imported_count': imported_count,
            'failed_count': failed_count,
            'errors': errors
        }
    
    def _extract_p3_production_date(self, row: pd.Series) -> Optional[date]:
        """
        提取 P3 的生產日期
        
        P3 特殊規則:
        1. 如果 CSV 中有 "生產日期" 欄位，優先使用
        2. 否則從 lot_no 解析
        3. 如果都沒有，使用當前日期
        """
        # 方法 1: 從 CSV 欄位讀取
        if '生產日期' in row and not pd.isna(row['生產日期']):
            try:
                return pd.to_datetime(row['生產日期']).date()
            except:
                pass
        
        # 方法 2: 從 lot_no 解析
        lot_no = row.get('lot_no')
        if lot_no:
            parsed_date = lot_no_parser.parse_production_date(lot_no)
            if parsed_date:
                return parsed_date
        
        # 方法 3: 使用當前日期（最後的fallback）
        logger.warning(f"無法確定 P3 生產日期，使用當前日期")
        return date.today()
```

#### 步驟 4: 更新查詢邏輯

```python
# routes_query.py

@router.get(
    "/records",
    response_model=QueryResponse,
    summary="查詢資料記錄（支援生產日期顯示）"
)
async def query_records(
    lot_no: str = Query(..., description="批號"),
    data_type: Optional[DataType] = Query(None, description="資料類型"),
    show_parsed_date: bool = Query(True, description="是否顯示從 lot_no 解析的日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """查詢資料記錄，自動顯示生產日期"""
    
    # ... 查詢邏輯 ...
    
    for record in records:
        query_record = QueryRecord(
            id=str(record.id),
            lot_no=record.lot_no,
            data_type=record.data_type.value,
            created_at=record.created_at.isoformat(),
            display_name=record.display_name
        )
        
        # 生產日期處理
        if show_parsed_date and record.data_type in [DataType.P1, DataType.P2]:
            # 如果沒有生產日期，從 lot_no 解析
            if record.production_date:
                query_record.production_date = record.production_date.isoformat()
            else:
                parsed_date = lot_no_parser.parse_production_date(record.lot_no)
                if parsed_date:
                    query_record.production_date = parsed_date.isoformat()
                    query_record.production_date_source = "parsed"  # 標記為解析的
        else:
            query_record.production_date = (
                record.production_date.isoformat() 
                if record.production_date 
                else None
            )
        
        # P3 特殊處理
        if record.data_type == DataType.P3:
            query_record.p3_no = record.p3_no
            query_record.product_name = record.product_name
            query_record.quantity = record.quantity
            query_record.notes = record.notes
            # P3 的生產日期可能需要從 additional_data 中取得
        
        query_records.append(query_record)
    
    return QueryResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        records=query_records
    )
```

#### 步驟 5: 更新前端顯示

```typescript
// frontend/src/components/QueryResults.tsx

interface QueryRecord {
  id: string;
  lot_no: string;
  data_type: 'P1' | 'P2' | 'P3';
  production_date?: string;
  production_date_source?: 'database' | 'parsed';  // 新增欄位
  // ... 其他欄位
}

function QueryResults({ records }: { records: QueryRecord[] }) {
  const formatProductionDate = (record: QueryRecord): string => {
    if (!record.production_date) {
      return '未設定';
    }
    
    const dateStr = new Date(record.production_date).toLocaleDateString('zh-TW');
    
    // 如果是從 lot_no 解析的，顯示標記
    if (record.production_date_source === 'parsed') {
      return (
        <span className="flex items-center gap-1">
          {dateStr}
          <Tooltip content="此日期由批號自動解析">
            <InfoIcon className="w-4 h-4 text-blue-500" />
          </Tooltip>
        </span>
      );
    }
    
    return dateStr;
  };
  
  return (
    <table>
      <thead>
        <tr>
          <th>批號</th>
          <th>類型</th>
          <th>生產日期</th>
          {/* ... */}
        </tr>
      </thead>
      <tbody>
        {records.map(record => (
          <tr key={record.id}>
            <td>{record.lot_no}</td>
            <td>{record.data_type}</td>
            <td>{formatProductionDate(record)}</td>
            {/* ... */}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### P3 特殊處理規則

由於 P3 的 lot_no 來自 "P3_No." 欄位，可能包含多個不同的批號，需要特殊處理：

```python
# P3 生產日期優先順序
1. CSV 中的 "生產日期" 欄位（最高優先）
2. 從 lot_no 解析（P3_No. 欄位前9碼）
3. 從 additional_data 中尋找相關日期欄位
4. 使用當前日期（最後fallback）
```

---

## 總結

### 可行性評估

| 需求 | 可行性 | 複雜度 | 優先級 |
|------|--------|--------|--------|
| P3 欄位搜尋 | 完全可行 | 低 | 高 |
| PDF 上傳 | 可行 | 中-高 | 中 |
| 生產日期套用 | 完全可行 | 低-中 | 高 |

### 實作順序建議

1. **第一階段**: P3 欄位搜尋（1-2天）
   - 實作基本欄位搜尋 API
   - 新增必要索引
   - 測試搜尋功能

2. **第二階段**: 生產日期自動套用（2-3天）
   - 實作 lot_no 解析器
   - 修改驗證和匯入邏輯
   - 更新前端顯示

3. **第三階段**: PDF 上傳支援（3-5天）
   - 安裝和測試 PDF 處理套件
   - 實作 PDF 提取服務
   - 整合到現有上傳流程
   - 充分測試各種 PDF 格式

### 風險與注意事項

1. **PDF 處理風險**:
   - 提取準確度取決於 PDF 品質
   - 處理時間較長
   - 可能需要使用者手動調整

2. **效能考量**:
   - PDF 處理需要較多資源
   - JSONB 搜尋需要適當索引
   - 大量資料時需要分頁

3. **維護性**:
   - 需要定期更新 PDF 處理庫
   - lot_no 格式變更需要更新解析器
   - 新增測試案例確保穩定性

---

**文檔版本**: 1.0  
**最後更新**: 2025年12月9日
