"""
侑特 (UT) 資料扁平化服務
支援按月查詢 P1, P2, P3 及組合資料
"""

from typing import List, Dict, Optional
from datetime import date, datetime
from sqlalchemy import select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import P1Record
from app.models.p2_item import P2Item
from app.models.p2_record import P2Record
from app.models.p3_item import P3Item
from app.config.ut_field_mapping import (
    P1_FIELD_MAPPING,
    P2_FIELD_MAPPING,
    P3_FIELD_MAPPING,
    P1_P2_P3_FIELD_MAPPING,
    get_nested_value,
)


def convert_yyyymmdd_to_yymmdd(yyyymmdd: int) -> str:
    """將 YYYYMMDD 轉換為 YYMMDD 字串（P1/P2 格式）"""
    date_str = str(yyyymmdd)
    return date_str[2:]  # "20250303" → "250303"


def convert_yyyymmdd_to_iso(yyyymmdd: int) -> str:
    """將 YYYYMMDD 轉換為 ISO 字串（P3 格式）"""
    return str(yyyymmdd)  # "20250401" → "20250401"


class UTFlattener:
    """侑特資料扁平化服務（支援 location 參數）"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def flatten_by_month(
        self,
        year: int,
        month: int,
        location: str = "P1+P2+P3"
    ) -> List[Dict]:
        """
        按月查詢並扁平化資料
        
        Args:
            year: 年份
            month: 月份
            location: 資料來源 ("P1", "P2", "P3", "P1+P2+P3")
        
        Returns:
            扁平化資料列表
        """
        if location == "P1":
            return await self._flatten_p1(year, month)
        elif location == "P2":
            return await self._flatten_p2(year, month)
        elif location == "P3":
            return await self._flatten_p3(year, month)
        elif location == "P1+P2+P3":
            return await self._flatten_p1_p2_p3(year, month)
        else:
            raise ValueError(f"Invalid location: {location}")
    
    async def _flatten_p1(self, year: int, month: int) -> List[Dict]:
        """查詢並扁平化 P1 資料"""
        # 計算日期範圍（YYYYMMDD）
        start_yyyymmdd = year * 10000 + month * 100 + 1
        if month == 12:
            end_yyyymmdd = (year + 1) * 10000 + 1 * 100 + 1
        else:
            end_yyyymmdd = year * 10000 + (month + 1) * 100 + 1
        
        # 查詢 P1 記錄（根據 created_at 或其他時間欄位）
        # 注意：P1Record 可能使用 created_at，需要轉換為 YYYYMMDD 比較
        query = select(P1Record).where(
            P1Record.created_at >= f"{year}-{month:02d}-01"
        ).order_by(P1Record.created_at.desc())
        
        result = await self.session.execute(query)
        p1_records = result.scalars().all()
        
        # 扁平化
        flattened = []
        for p1 in p1_records:
            # 提取時間戳（從 created_at 轉為 YYMMDD）
            timestamp = convert_yyyymmdd_to_yymmdd(
                int(p1.created_at.strftime("%Y%m%d"))
            )
            
            # 構建 metrics
            metrics = {}
            for field_name, field_spec in P1_FIELD_MAPPING.items():
                value = self._extract_field(p1, field_spec)
                metrics[field_name] = value
            
            flattened.append({
                "timestamp": timestamp,
                "type": "ut",
                "location": "P1",
                "metrics": metrics
            })
        
        return flattened
    
    async def _flatten_p2(self, year: int, month: int) -> List[Dict]:
        """查詢並扁平化 P2 資料（從 p2_records，然後手動查 p2_items）"""
        # 構建日期範圍
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # 查詢 P2Record
        query = select(P2Record).where(
            and_(
                P2Record.created_at >= start_date,
                P2Record.created_at < end_date
            )
        )
        
        result = await self.session.execute(query)
        p2_records = result.scalars().all()
        
        flattened = []
        for p2_record in p2_records:
            # 從 extras 取得 production_date
            production_date_str = p2_record.extras.get('production_date', '')
            if production_date_str:
                # 嘗試解析日期（可能是 "2026-01-09" 或 "20260109"）
                try:
                    if '-' in production_date_str:
                        prod_date = datetime.strptime(production_date_str, "%Y-%m-%d")
                    else:
                        prod_date = datetime.strptime(production_date_str, "%Y%m%d")
                    timestamp = convert_yyyymmdd_to_yymmdd(int(prod_date.strftime("%Y%m%d")))
                except:
                    timestamp = "000000"  # fallback
            else:
                timestamp = convert_yyyymmdd_to_yymmdd(int(p2_record.created_at.strftime("%Y%m%d")))
            
            # 查詢該 record 的所有 p2_items
            items_query = select(P2Item).where(P2Item.record_id == p2_record.id)
            items_result = await self.session.execute(items_query)
            p2_items = items_result.scalars().all()
            
            # 如果沒有 items，從 p2_record.extras.rows 提取（fallback）
            if not p2_items and p2_record.extras.get('rows'):
                # 使用舊格式（從 extras.rows）
                for row in p2_record.extras['rows']:
                    metrics = {}
                    for field_name, field_spec in P2_FIELD_MAPPING.items():
                        # 從 row dict 提取
                        if field_name == "Sheet Width(mm)":
                            value = row.get("Board Width(mm)")
                        elif field_name.startswith("Thicknessss"):
                            # 使用 Thicknessss Low/High
                            value = row.get("Thicknessss Low(μm)")
                        elif field_name == "Winder number":
                            value = row.get("Winder number")
                        elif field_name == "Semi_No.":
                            value = p2_record.lot_no_norm
                        else:
                            value = row.get(field_name)
                        metrics[field_name] = value
                    
                    flattened.append({
                        "timestamp": timestamp,
                        "type": "ut",
                        "location": "P2",
                        "metrics": metrics
                    })
            else:
                # 使用 p2_items
                for p2_item in p2_items:
                    metrics = {}
                    for field_name, field_spec in P2_FIELD_MAPPING.items():
                        value = self._extract_field_from_item(p2_item, field_spec)
                        metrics[field_name] = value
                    
                    flattened.append({
                        "timestamp": timestamp,
                        "type": "ut",
                        "location": "P2",
                        "metrics": metrics
                    })
        
        return flattened
    
    async def _flatten_p3(self, year: int, month: int) -> List[Dict]:
        """查詢並扁平化 P3 資料（從 p3_items 表）"""
        # P3 使用 production_date
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        query = select(P3Item).where(
            and_(
                P3Item.production_date >= start_date,
                P3Item.production_date < end_date
            )
        ).order_by(P3Item.production_date.desc())
        
        result = await self.session.execute(query)
        p3_items = result.scalars().all()
        
        flattened = []
        for p3_item in p3_items:
            # P3 時間戳為 8 位數 YYYYMMDD
            timestamp = convert_yyyymmdd_to_iso(
                int(p3_item.production_date.strftime("%Y%m%d"))
            )
            
            metrics = {}
            for field_name, field_spec in P3_FIELD_MAPPING.items():
                value = self._extract_field_from_item(p3_item, field_spec)
                metrics[field_name] = value
            
            flattened.append({
                "timestamp": timestamp,
                "type": "ut",
                "location": "P3",
                "metrics": metrics
            })
        
        return flattened
    
    async def _flatten_p1_p2_p3(self, year: int, month: int) -> List[Dict]:
        """
        查詢並扁平化 P1+P2+P3 組合資料（追溯邏輯）
        邏輯：P3 → P2 → P1
        """
        # 先查詢 P3 items
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        query = select(P3Item).where(
            and_(
                P3Item.production_date >= start_date,
                P3Item.production_date < end_date
            )
        ).order_by(P3Item.production_date.desc())
        
        result = await self.session.execute(query)
        p3_items = result.scalars().all()
        
        flattened = []
        for p3_item in p3_items:
            # 從 P3 追溯到 P2（透過 lot_no 或 source_winder）
            p2_item = None
            if p3_item.lot_no:
                p2_query = select(P2Item).where(
                    P2Item.lot_no == p3_item.lot_no
                ).limit(1)
                p2_result = await self.session.execute(p2_query)
                p2_item = p2_result.scalar_one_or_none()
            
            # 從 P2 追溯到 P1（透過 lot_no）
            p1_record = None
            if p2_item and p2_item.lot_no:
                p1_query = select(P1Record).where(
                    P1Record.lot_no_norm == p2_item.lot_no
                ).limit(1)
                p1_result = await self.session.execute(p1_query)
                p1_record = p1_result.scalar_one_or_none()
            
            # 構建組合資料
            timestamp = convert_yyyymmdd_to_iso(
                int(p3_item.production_date.strftime("%Y%m%d"))
            )
            
            metrics = {}
            
            # 從 P1 提取欄位
            for field_name, field_spec in P1_FIELD_MAPPING.items():
                if field_name in ["Machine_No.", "Semi_No."]:
                    # 這些欄位需要加前綴
                    prefixed_name = f"P1.{field_name}"
                    value = self._extract_field(p1_record, field_spec) if p1_record else None
                    metrics[prefixed_name] = value
                else:
                    value = self._extract_field(p1_record, field_spec) if p1_record else None
                    metrics[field_name] = value
            
            # 從 P2 提取欄位
            for field_name, field_spec in P2_FIELD_MAPPING.items():
                if field_name == "Semi_No.":
                    # 加前綴
                    prefixed_name = "P2.Semi_No."
                    value = self._extract_field_from_item(p2_item, field_spec) if p2_item else None
                    metrics[prefixed_name] = value
                else:
                    value = self._extract_field_from_item(p2_item, field_spec) if p2_item else None
                    metrics[field_name] = value
            
            # 從 P3 提取欄位
            for field_name, field_spec in P3_FIELD_MAPPING.items():
                if field_name == "Machine_No.":
                    # 加前綴
                    prefixed_name = "P3.Machine_No."
                    value = self._extract_field_from_item(p3_item, field_spec)
                    metrics[prefixed_name] = value
                else:
                    value = self._extract_field_from_item(p3_item, field_spec)
                    metrics[field_name] = value
            
            flattened.append({
                "timestamp": timestamp,
                "type": "ut",
                "location": "P1+P2+P3",
                "metrics": metrics
            })
        
        return flattened
    
    def _extract_field_from_item(
        self,
        item,
        field_spec: str
    ):
        """
        從 P2Item 或 P3Item 提取欄位值
        
        Args:
            item: P2Item 或 P3Item 實例
            field_spec: 欄位規格（如 "row_data.E Value" 或直接屬性名）
        
        Returns:
            欄位值或 None
        """
        if not item:
            return None
        
        # 處理 row_data JSON 欄位
        if isinstance(field_spec, str) and field_spec.startswith('row_data.'):
            if not hasattr(item, 'row_data') or not item.row_data:
                return None
            key = field_spec.replace('row_data.', '')
            return item.row_data.get(key)
        
        # 處理舊格式 "row.XXX"（向後相容）
        if isinstance(field_spec, str) and field_spec.startswith('row.'):
            if not hasattr(item, 'row_data') or not item.row_data:
                return None
            key = field_spec.replace('row.', '')
            return item.row_data.get(key)
        
        # 處理直接屬性（如 P2Item 的 sheet_width, thickness1 等）
        if isinstance(field_spec, str):
            if '.' not in field_spec:
                return getattr(item, field_spec, None)
            else:
                # 處理巢狀路徑（如需要）
                return get_nested_value(item.__dict__, field_spec)
        
        return None
    
    def _extract_field(
        self,
        record,
        field_spec: str,
        row_data: Optional[Dict] = None
    ):
        """
        從記錄中提取欄位值（用於 P1Record）
        
        Args:
            record: P1Record 實例
            field_spec: 欄位規格（如 "extras.temperature.actual.C1"）
            row_data: 不使用（保留參數以相容舊程式碼）
        
        Returns:
            欄位值或 None
        """
        if not record:
            return None
        
        # 處理一般欄位
        if isinstance(field_spec, str):
            if '.' in field_spec:
                # 巢狀路徑
                parts = field_spec.split('.')
                if parts[0] == 'extras' and hasattr(record, 'extras'):
                    return get_nested_value(record.extras or {}, '.'.join(parts[1:]))
                else:
                    return get_nested_value(record.__dict__, field_spec)
            else:
                # 直接屬性
                return getattr(record, field_spec, None)
        
        return None
