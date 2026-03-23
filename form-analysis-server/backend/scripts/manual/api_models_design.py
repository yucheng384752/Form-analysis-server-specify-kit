"""
API 設計說明 - 以 lot_no 為唯一鍵的生產資料管理系統
設計日期: 2025-11-08
設計原則: RESTful API, 以資源為導向, lot_no 作為主要標識符
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime, date, time
from enum import Enum

# ========================================
# 1. 基礎模型定義
# ========================================

class PhaseType(str, Enum):
    P1 = "P1"
    P2 = "P2" 
    P3 = "P3"

class QualityStatus(int, Enum):
    DEFECTIVE = 0
    GOOD = 1

# ========================================
# 2. 生產序號次相關模型
# ========================================

class ProductionLotBase(BaseModel):
    """生產序號次基礎模型"""
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$', description="批號，格式：7位數字_2位數字")
    production_date: date = Field(..., description="生產日期")
    production_time_start: Optional[time] = Field(None, description="生產開始時間")
    production_time_end: Optional[time] = Field(None, description="生產結束時間")
    product_spec: Optional[str] = Field(None, max_length=100, description="品名規格")
    material: Optional[str] = Field(None, max_length=50, description="材料")
    semi_product_width: Optional[float] = Field(None, description="半成品板寬(mm)")
    semi_product_length: Optional[float] = Field(None, description="半成品米數(M)")
    weight: Optional[float] = Field(None, description="重量(Kg)")
    good_products: int = Field(0, ge=0, description="良品數")
    defective_products: int = Field(0, ge=0, description="不良品數")
    remarks: Optional[str] = Field(None, description="備註")
    phase: PhaseType = Field(..., description="生產階段")

class ProductionLotCreate(ProductionLotBase):
    """創建生產序號次請求模型"""
    pass

class ProductionLotUpdate(BaseModel):
    """更新生產序號次請求模型"""
    production_time_start: Optional[time] = None
    production_time_end: Optional[time] = None
    product_spec: Optional[str] = Field(None, max_length=100)
    material: Optional[str] = Field(None, max_length=50)
    semi_product_width: Optional[float] = None
    semi_product_length: Optional[float] = None
    weight: Optional[float] = None
    good_products: Optional[int] = Field(None, ge=0)
    defective_products: Optional[int] = Field(None, ge=0)
    remarks: Optional[str] = None

class ProductionLotResponse(ProductionLotBase):
    """生產序號次響應模型"""
    created_at: datetime
    updated_at: datetime
    quality_rate: float = Field(..., description="良率百分比")
    
    class Config:
        from_attributes = True

# ========================================
# 3. P1階段 - 押出機資料模型
# ========================================

class P1ExtrusionDataBase(BaseModel):
    """P1押出機資料基礎模型"""
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$')
    
    # 溫度資料 (實際溫度16點)
    actual_temps: List[Optional[float]] = Field(default_factory=lambda: [None] * 16, min_items=16, max_items=16)
    set_temps: List[Optional[float]] = Field(default_factory=lambda: [None] * 16, min_items=16, max_items=16)
    
    # 乾燥桶溫度
    actual_temp_buckets: Dict[str, Optional[float]] = Field(default_factory=lambda: {"A": None, "B": None, "C": None})
    set_temp_buckets: Dict[str, Optional[float]] = Field(default_factory=lambda: {"A": None, "B": None, "C": None})
    
    # 延押輪溫度
    actual_temp_rollers: Dict[str, Optional[float]] = Field(default_factory=lambda: {"top": None, "mid": None, "bottom": None})
    set_temp_rollers: Dict[str, Optional[float]] = Field(default_factory=lambda: {"top": None, "mid": None, "bottom": None})
    
    # 機器參數
    line_speed: Optional[float] = Field(None, description="線速度(M/min)")
    screw_pressure: Optional[float] = Field(None, description="螺桿壓力(psi)")
    screw_output: Optional[float] = Field(None, description="螺桿壓出量(%)")
    left_pad_thickness: Optional[float] = Field(None, description="左墊片厚度(mm)")
    right_pad_thickness: Optional[float] = Field(None, description="右墊片厚度(mm)")
    current_amperage: Optional[float] = Field(None, description="電流量(A)")
    extruder_speed: Optional[float] = Field(None, description="押出機轉速(rpm)")
    quantitative_pressure: Optional[float] = Field(None, description="定量壓力(psi)")
    quantitative_output: Optional[float] = Field(None, description="定量輸出(%)")
    carriage: Optional[float] = Field(None, description="車台(cm)")
    filter_pressure: Optional[float] = Field(None, description="濾網壓力(psi)")
    screw_rotation_speed: Optional[float] = Field(None, description="螺桿轉速(rpm)")

class P1ExtrusionDataCreate(P1ExtrusionDataBase):
    """創建P1資料請求"""
    pass

class P1ExtrusionDataResponse(P1ExtrusionDataBase):
    """P1資料響應模型"""
    id: str
    record_timestamp: datetime
    
    class Config:
        from_attributes = True

# ========================================
# 4. P2階段 - 品質檢測模型
# ========================================

class P2QualityDataBase(BaseModel):
    """P2品質資料基礎模型"""
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$')
    sheet_width: Optional[float] = Field(None, description="板寬(mm)")
    thicknesses: List[Optional[float]] = Field(default_factory=lambda: [None] * 7, min_items=7, max_items=7, description="厚度測量(μm)")
    appearance: Optional[QualityStatus] = Field(None, description="外觀品質")
    rough_edge: Optional[QualityStatus] = Field(None, description="粗糙邊緣")
    slitting_result: Optional[QualityStatus] = Field(None, description="分切結果")

class P2QualityDataCreate(P2QualityDataBase):
    """創建P2資料請求"""
    pass

class P2QualityDataResponse(P2QualityDataBase):
    """P2資料響應模型"""
    id: str
    measurement_time: datetime
    
    class Config:
        from_attributes = True

# ========================================
# 5. P3階段 - 最終檢驗模型
# ========================================

class P3InspectionDataBase(BaseModel):
    """P3檢驗資料基礎模型"""
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$')
    p3_no: Optional[str] = Field(None, max_length=50, description="P3編號")
    e_value: Optional[int] = Field(None, description="E值")
    
    # 檢驗項目 (0=不良, 1=良好)
    po_10: Optional[QualityStatus] = Field(None, description="10PO檢測")
    burr: Optional[QualityStatus] = Field(None, description="毛邊檢測")
    shift: Optional[QualityStatus] = Field(None, description="位移檢測")
    iron: Optional[QualityStatus] = Field(None, description="鐵質檢測")
    mold: Optional[QualityStatus] = Field(None, description="模具檢測")
    rubber_wheel: Optional[QualityStatus] = Field(None, description="橡膠輪檢測")
    clean: Optional[QualityStatus] = Field(None, description="清潔度檢測")
    adjustment_record: Optional[QualityStatus] = Field(None, description="調整記錄")
    finish: Optional[QualityStatus] = Field(None, description="完成狀態")

class P3InspectionDataCreate(P3InspectionDataBase):
    """創建P3資料請求"""
    pass

class P3InspectionDataResponse(P3InspectionDataBase):
    """P3資料響應模型"""
    id: str
    inspection_time: datetime
    
    class Config:
        from_attributes = True

# ========================================
# 6. 不良品記錄模型
# ========================================

class DefectRecordBase(BaseModel):
    """不良品記錄基礎模型"""
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$')
    defect_length: Optional[str] = Field(None, max_length=50, description="不良米數")
    defect_type: Optional[str] = Field(None, max_length=100, description="不良狀況")
    defect_position: Optional[str] = Field(None, max_length=200, description="不良位置")
    severity: Optional[str] = Field(None, max_length=20, description="嚴重程度")

class DefectRecordCreate(DefectRecordBase):
    """創建不良品記錄請求"""
    pass

class DefectRecordResponse(DefectRecordBase):
    """不良品記錄響應模型"""
    id: str
    recorded_at: datetime
    
    class Config:
        from_attributes = True

# ========================================
# 7. 查詢和分頁模型
# ========================================

class ProductionQuery(BaseModel):
    """生產資料查詢參數"""
    lot_no: Optional[str] = Field(None, description="批號篩選(支援模糊查詢)")
    phase: Optional[PhaseType] = Field(None, description="階段篩選")
    production_date_start: Optional[date] = Field(None, description="生產日期起")
    production_date_end: Optional[date] = Field(None, description="生產日期訖")
    material: Optional[str] = Field(None, description="材料篩選")
    product_spec: Optional[str] = Field(None, description="規格篩選")
    
class PaginationParams(BaseModel):
    """分頁參數"""
    page: int = Field(1, ge=1, description="頁碼")
    page_size: int = Field(20, ge=1, le=100, description="每頁大小")
    
class PaginatedResponse(BaseModel):
    """分頁響應"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

# ========================================
# 8. 彙總統計模型
# ========================================

class ProductionSummary(BaseModel):
    """生產彙總統計"""
    total_lots: int = Field(..., description="總批次數")
    total_good_products: int = Field(..., description="總良品數")
    total_defective_products: int = Field(..., description="總不良品數")
    overall_quality_rate: float = Field(..., description="整體良率")
    phase_distribution: Dict[str, int] = Field(..., description="各階段分佈")
    daily_production: List[Dict[str, Any]] = Field(..., description="每日生產統計")

class LotDetailResponse(BaseModel):
    """批次詳細資料響應"""
    lot_info: ProductionLotResponse
    p1_data: List[P1ExtrusionDataResponse] = Field(default_factory=list)
    p2_data: List[P2QualityDataResponse] = Field(default_factory=list)
    p3_data: List[P3InspectionDataResponse] = Field(default_factory=list)
    defect_records: List[DefectRecordResponse] = Field(default_factory=list)

# ========================================
# 9. 批量操作模型
# ========================================

class BulkUploadRequest(BaseModel):
    """批量上傳請求"""
    file_type: PhaseType = Field(..., description="檔案類型")
    lot_no: str = Field(..., pattern=r'^\d{7}_\d{2}$', description="批號")
    override_existing: bool = Field(False, description="是否覆蓋既有資料")

class BulkUploadResponse(BaseModel):
    """批量上傳響應"""
    success_count: int = Field(..., description="成功處理數量")
    error_count: int = Field(..., description="錯誤數量")
    errors: List[str] = Field(default_factory=list, description="錯誤詳情")
    created_records: List[str] = Field(default_factory=list, description="創建的記錄ID")

# ========================================
# 10. 錯誤響應模型
# ========================================

class ErrorResponse(BaseModel):
    """錯誤響應模型"""
    error_code: str = Field(..., description="錯誤程式碼")
    message: str = Field(..., description="錯誤訊息")
    details: Optional[Dict[str, Any]] = Field(None, description="錯誤詳情")
    timestamp: datetime = Field(default_factory=datetime.now, description="錯誤時間")