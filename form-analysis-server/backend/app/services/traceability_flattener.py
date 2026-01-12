"""
追溯資料扁平化服務
處理 P3 → P2 → P1 的批次查詢與扁平化

新規定：
1. 支援多 server 並發呼叫（使用 connection pool、無全域狀態）
2. 資料庫內沒有的值填入 null，空資料維持空陣列
"""

from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import P1Record, P2Record, P3Record
from app.config.analytics_field_mapping import (
    P1_FIELD_MAPPING,
    P2_FIELD_MAPPING,
    P3_FIELD_MAPPING,
    OUTPUT_FIELD_ORDER,
    get_nested_value,
)
from ..config.analytics_config import AnalyticsConfig


def convert_yyyymmdd_to_iso(yyyymmdd: int) -> str:
    """
    將 YYYYMMDD 整數轉換為 ISO 8601 日期字串
    
    Args:
        yyyymmdd: 整數格式日期（例如：20250112）
        
    Returns:
        ISO 8601 日期字串（例如："2025-01-12"）
    """
    date_str = str(yyyymmdd)
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


class TraceabilityFlattener:
    """追溯資料扁平化核心邏輯（無狀態設計，支援並發）"""
    
    def __init__(self, session: AsyncSession):
        """
        初始化扁平化服務
        
        Args:
            session: SQLAlchemy AsyncSession（每個請求獨立 session）
        """
        self.session = session
    
    async def flatten_by_month(
        self,
        year: int,
        month: int,
        limit: Optional[int] = None
    ) -> Dict:
        """
        按月份查詢並扁平化
        
        Args:
            year: 年份（如 2025）
            month: 月份（1-12）
            limit: 最大回傳筆數（None = 不限制）
        
        Returns:
            {
                "data": [扁平化記錄],
                "count": 實際筆數,
                "has_data": bool,
                "metadata": {
                    "query_type": "monthly",
                    "year": 2025,
                    "month": 9,
                    "compression": "gzip",
                    "null_handling": "explicit"  # 明確標示 null 語義
                }
            }
        
        新規定：
        - 空資料回傳 {"data": [], "count": 0, "has_data": false}
        - 不存在的欄位填入 null
        """
        # 構造月份範圍（使用 production_date_yyyymmdd Integer 格式）
        start_yyyymmdd = year * 10000 + month * 100 + 1  # 例如: 20250901
        if month == 12:
            end_yyyymmdd = (year + 1) * 10000 + 1 * 100 + 1  # 例如: 20260101
        else:
            end_yyyymmdd = year * 10000 + (month + 1) * 100 + 1  # 例如: 20251001
        
        # 查詢該月份的 P3 記錄（使用 production_date_yyyymmdd）
        query = select(P3Record).where(
            and_(
                P3Record.production_date_yyyymmdd >= start_yyyymmdd,
                P3Record.production_date_yyyymmdd < end_yyyymmdd
            )
        ).order_by(P3Record.production_date_yyyymmdd.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        p3_records = result.scalars().all()
        
        # 新規定：空資料維持空陣列
        if not p3_records:
            return {
                "data": [],
                "count": 0,
                "has_data": False,
                "metadata": {
                    "query_type": "monthly",
                    "year": year,
                    "month": month,
                    "compression": "none",
                    "null_handling": "explicit"
                }
            }
        
        # 批次扁平化
        flattened = await self._batch_flatten(p3_records)
        
        return {
            "data": flattened,
            "count": len(flattened),
            "has_data": len(flattened) > 0,
            "metadata": {
                "query_type": "monthly",
                "year": year,
                "month": month,
                "compression": "auto" if len(flattened) >= AnalyticsConfig.AUTO_GZIP_THRESHOLD else "none",
                "null_handling": "explicit"
            }
        }
    
    async def flatten_by_product_ids(
        self,
        product_ids: List[str],
        limit: Optional[int] = None
    ) -> Dict:
        """
        按 product_id 列表查詢並扁平化
        
        Args:
            product_ids: 產品 ID 列表（如 ["P3-20250901-001", ...]）
            limit: 最大回傳筆數
        
        Returns:
            同 flatten_by_month 格式
        """
        if not product_ids:
            return {
                "data": [],
                "count": 0,
                "has_data": False,
                "metadata": {
                    "query_type": "by_ids",
                    "compression": "none",
                    "null_handling": "explicit"
                }
            }
        
        # 查詢指定 product_id 的 P3 記錄
        query = select(P3Record).where(
            P3Record.product_id.in_(product_ids)
        ).order_by(P3Record.production_date_yyyymmdd.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        p3_records = result.scalars().all()
        
        if not p3_records:
            return {
                "data": [],
                "count": 0,
                "has_data": False,
                "metadata": {
                    "query_type": "by_ids",
                    "compression": "none",
                    "null_handling": "explicit"
                }
            }
        
        flattened = await self._batch_flatten(p3_records)
        
        return {
            "data": flattened,
            "count": len(flattened),
            "has_data": len(flattened) > 0,
            "metadata": {
                "query_type": "by_ids",
                "compression": "auto" if len(flattened) >= AnalyticsConfig.AUTO_GZIP_THRESHOLD else "none",
                "null_handling": "explicit"
            }
        }
    
    async def _batch_flatten(self, p3_records: List[P3Record]) -> List[Dict]:
        """
        批次扁平化 P3 記錄（核心邏輯）
        
        新規定：
        - 不存在的欄位填入 null（而非省略）
        - 空 rows[] 會產生空陣列
        """
        if not p3_records:
            return []
        
        # 收集所有需要查詢的 lot_no
        p2_lot_nos = set()
        p1_lot_nos = set()
        
        for p3 in p3_records:
            if p3.lot_no_norm:
                p2_lot_nos.add(p3.lot_no_norm)
        
        # 批次查詢 P2（避免 N+1）
        p2_map = await self._batch_query_p2(list(p2_lot_nos))
        
        # 從 P2 收集 P1 lot_no
        for p2_records in p2_map.values():
            for p2 in p2_records:
                if p2.lot_no_norm:
                    p1_lot_nos.add(p2.lot_no_norm)
        
        # 批次查詢 P1
        p1_map = await self._batch_query_p1(list(p1_lot_nos))
        
        # 扁平化合併
        flattened_records = []
        for p3 in p3_records:
            # 取得對應的 P2 和 P1
            p2_records = p2_map.get(p3.lot_no_norm, [])
            
            # 處理 P3.extras.rows[]
            rows = p3.extras.get('rows', []) if p3.extras else []
            
            # 新規定：空 rows 會產生空陣列（不跳過）
            if not rows:
                # 仍產生一筆記錄（P3 + P2 + P1，但 P3 特定欄位為 null）
                for p2 in (p2_records or [None]):
                    p1 = None
                    if p2 and p2.lot_no_norm:
                        p1_records = p1_map.get(p2.lot_no_norm, [])
                        p1 = p1_records[0] if p1_records else None
                    
                    record = self._merge_single_record(p3, p2, p1, row_data=None)
                    flattened_records.append(record)
                
                # 如果 P2 也不存在，至少產生一筆只有 P3 的記錄
                if not p2_records:
                    record = self._merge_single_record(p3, None, None, row_data=None)
                    flattened_records.append(record)
            else:
                # 有 rows 時，展開每個 row
                for row_data in rows:
                    # 根據 source_winder 找到對應的 P2
                    source_winder = row_data.get('source_winder') or p3.extras.get('source_winder')
                    p2 = self._match_p2_by_winder(p2_records, source_winder)
                    
                    # 從 P2 追溯到 P1
                    p1 = None
                    if p2 and p2.lot_no_norm:
                        p1_records = p1_map.get(p2.lot_no_norm, [])
                        p1 = p1_records[0] if p1_records else None
                    
                    record = self._merge_single_record(p3, p2, p1, row_data)
                    flattened_records.append(record)
        
        return flattened_records
    
    async def _batch_query_p1(self, lot_nos: List[str]) -> Dict[str, List[P1Record]]:
        """批次查詢 P1（並發安全）"""
        if not lot_nos:
            return {}
        
        query = select(P1Record).where(P1Record.lot_no_norm.in_(lot_nos))
        result = await self.session.execute(query)
        p1_records = result.scalars().all()
        
        # 按 lot_no 分組
        p1_map = {}
        for p1 in p1_records:
            if p1.lot_no_norm not in p1_map:
                p1_map[p1.lot_no_norm] = []
            p1_map[p1.lot_no_norm].append(p1)
        
        return p1_map
    
    async def _batch_query_p2(self, lot_nos: List[str]) -> Dict[str, List[P2Record]]:
        """批次查詢 P2（按 lot_no 分組，支援多 winder）"""
        if not lot_nos:
            return {}
        
        query = select(P2Record).where(P2Record.lot_no_norm.in_(lot_nos))
        result = await self.session.execute(query)
        p2_records = result.scalars().all()
        
        # 按 lot_no 分組（一個 lot 可能有多個 winder）
        p2_map = {}
        for p2 in p2_records:
            if p2.lot_no_norm not in p2_map:
                p2_map[p2.lot_no_norm] = []
            p2_map[p2.lot_no_norm].append(p2)
        
        return p2_map
    
    def _match_p2_by_winder(
        self,
        p2_records: List[P2Record],
        source_winder: Optional[str]
    ) -> Optional[P2Record]:
        """根據 source_winder 匹配對應的 P2 記錄"""
        if not p2_records:
            return None
        
        if not source_winder:
            return p2_records[0]  # 預設取第一筆
        
        for p2 in p2_records:
            if p2.winder_number == source_winder:
                return p2
        
        return p2_records[0]  # 找不到匹配，取第一筆
    
    def _merge_single_record(
        self,
        p3: P3Record,
        p2: Optional[P2Record],
        p1: Optional[P1Record],
        row_data: Optional[Dict]
    ) -> Dict:
        """
        合併單筆記錄（P3 + P2 + P1）
        
        新規定：不存在的欄位填入 null
        """
        merged = {}
        
        # 按照 OUTPUT_FIELD_ORDER 順序填充
        for field_name in OUTPUT_FIELD_ORDER:
            value = None
            
            # 1. 嘗試從 P3 取值
            if field_name in P3_FIELD_MAPPING:
                value = self._extract_field(p3, P3_FIELD_MAPPING[field_name], row_data)
            
            # 2. 嘗試從 P2 取值
            elif field_name in P2_FIELD_MAPPING:
                if p2:
                    value = self._extract_field(p2, P2_FIELD_MAPPING[field_name])
                # p2 不存在 → value 保持 None
            
            # 3. 嘗試從 P1 取值
            elif field_name in P1_FIELD_MAPPING:
                if p1:
                    value = self._extract_field(p1, P1_FIELD_MAPPING[field_name])
                # p1 不存在 → value 保持 None
            
            # 新規定：明確設定 null（而非省略欄位）
            merged[field_name] = value
        
        return merged
    
    def _extract_field(
        self,
        record,
        field_spec,
        row_data: Optional[Dict] = None
    ):
        """
        從記錄中提取欄位值
        
        新規定：找不到值回傳 None（而非預設值）
        特殊處理：P3 的 production_date_yyyymmdd 需轉換為 ISO 8601
        """
        # 處理 lambda 函數（固定值）
        if callable(field_spec):
            return field_spec(record)
        
        # 處理 P3 row 資料（如 'row.lot'）
        if isinstance(field_spec, str) and field_spec.startswith('row.'):
            if not row_data:
                return None  # row 不存在
            key = field_spec.replace('row.', '')
            return row_data.get(key)  # 回傳 None if missing
        
        # 處理一般欄位（如 'lot_no_norm' 或 'extras.material'）
        if isinstance(field_spec, str):
            # 特殊處理：P3 生產日期需轉換格式
            if field_spec == 'production_date_yyyymmdd':
                if hasattr(record, 'production_date_yyyymmdd'):
                    yyyymmdd = getattr(record, 'production_date_yyyymmdd')
                    if yyyymmdd is not None:
                        return convert_yyyymmdd_to_iso(yyyymmdd)
                return None
            
            if '.' in field_spec:
                # 巢狀路徑（如 'extras.temperature.actual.C1'）
                parts = field_spec.split('.')
                if parts[0] == 'extras' and hasattr(record, 'extras'):
                    return get_nested_value(record.extras or {}, '.'.join(parts[1:]))
                else:
                    # 一般點記號（如 'some_obj.field'）
                    return get_nested_value(record.__dict__, field_spec)
            else:
                # 直接屬性（如 'lot_no_norm'）
                return getattr(record, field_spec, None)
        
        return None  # 無法解析 → null
