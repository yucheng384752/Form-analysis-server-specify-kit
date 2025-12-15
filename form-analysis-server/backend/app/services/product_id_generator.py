"""
Product ID 產生器服務

格式: YYYY-MM-DD_機台_模號_LOT
範例: 2025-09-02_P24_238-2_301

此服務提供：
1. 從 P3 資料產生唯一的 Product ID
2. 從 Product ID 解析出原始資料
"""

from datetime import date, datetime
from typing import Dict, Optional, Tuple


class ProductIDGenerator:
    """
    Product ID 產生與解析服務
    
    Product ID 格式: YYYY-MM-DD_machine_mold_lot
    - YYYY-MM-DD: 生產日期（ISO 8601 格式）
    - machine: 機台編號（如 P24）
    - mold: 模號（如 238-2）
    - lot: 批號（整數，如 301）
    
    範例:
    >>> generator = ProductIDGenerator()
    >>> product_id = generator.generate(
    ...     production_date=date(2025, 9, 2),
    ...     machine_no="P24",
    ...     mold_no="238-2",
    ...     production_lot=301
    ... )
    >>> print(product_id)
    2025-09-02_P24_238-2_301
    
    >>> parsed = generator.parse(product_id)
    >>> print(parsed)
    {
        'production_date': datetime.date(2025, 9, 2),
        'machine_no': 'P24',
        'mold_no': '238-2',
        'production_lot': 301
    }
    """
    
    def generate(
        self,
        production_date: date,
        machine_no: str,
        mold_no: str,
        production_lot: int
    ) -> str:
        """
        產生 Product ID
        
        Args:
            production_date: 生產日期（date 物件）
            machine_no: 機台編號（如 "P24"）
            mold_no: 模號（如 "238-2"）
            production_lot: 批號（整數，如 301）
        
        Returns:
            Product ID 字串，格式: YYYY-MM-DD_machine_mold_lot
        
        Raises:
            ValueError: 如果參數格式不正確
        
        Examples:
            >>> gen = ProductIDGenerator()
            >>> gen.generate(date(2025, 9, 2), "P24", "238-2", 301)
            '2025-09-02_P24_238-2_301'
        """
        # 驗證參數
        if not isinstance(production_date, date):
            raise ValueError(f"production_date 必須是 date 物件: {type(production_date)}")
        
        if not machine_no or not isinstance(machine_no, str):
            raise ValueError(f"machine_no 必須是非空字串: {machine_no}")
        
        if not mold_no or not isinstance(mold_no, str):
            raise ValueError(f"mold_no 必須是非空字串: {mold_no}")
        
        if not isinstance(production_lot, int) or production_lot < 0:
            raise ValueError(f"production_lot 必須是非負整數: {production_lot}")
        
        # 格式化日期為 YYYY-MM-DD
        date_str = production_date.strftime("%Y-%m-%d")
        
        # 組合 Product ID
        product_id = f"{date_str}_{machine_no}_{mold_no}_{production_lot}"
        
        return product_id
    
    def generate_from_strings(
        self,
        production_date_str: str,
        machine_no: str,
        mold_no: str,
        production_lot: int
    ) -> str:
        """
        從字串日期產生 Product ID
        
        Args:
            production_date_str: 生產日期字串（可接受多種格式）
            machine_no: 機台編號
            mold_no: 模號
            production_lot: 批號
        
        Returns:
            Product ID 字串
        
        Examples:
            >>> gen = ProductIDGenerator()
            >>> gen.generate_from_strings("2025-09-02", "P24", "238-2", 301)
            '2025-09-02_P24_238-2_301'
            >>> gen.generate_from_strings("20250902", "P24", "238-2", 301)
            '2025-09-02_P24_238-2_301'
        """
        # 解析日期字串
        production_date = self._parse_date(production_date_str)
        
        # 使用標準產生方法
        return self.generate(production_date, machine_no, mold_no, production_lot)
    
    def parse(self, product_id: str) -> Dict[str, any]:
        """
        解析 Product ID，取得原始資料
        
        Args:
            product_id: Product ID 字串
        
        Returns:
            包含以下欄位的字典:
            - production_date: date 物件
            - machine_no: 機台編號字串
            - mold_no: 模號字串
            - production_lot: 批號整數
        
        Raises:
            ValueError: 如果 Product ID 格式不正確
        
        Examples:
            >>> gen = ProductIDGenerator()
            >>> result = gen.parse("2025-09-02_P24_238-2_301")
            >>> result['production_date']
            datetime.date(2025, 9, 2)
            >>> result['machine_no']
            'P24'
            >>> result['production_lot']
            301
        """
        if not product_id or not isinstance(product_id, str):
            raise ValueError(f"product_id 必須是非空字串: {product_id}")
        
        # 分割 Product ID
        parts = product_id.split('_')
        
        if len(parts) != 4:
            raise ValueError(
                f"Product ID 格式錯誤，應為 'YYYY-MM-DD_machine_mold_lot'，"
                f"但收到: {product_id}"
            )
        
        date_str, machine_no, mold_no, lot_str = parts
        
        # 解析日期
        try:
            production_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(
                f"日期格式錯誤，應為 YYYY-MM-DD，但收到: {date_str}"
            ) from e
        
        # 解析批號
        try:
            production_lot = int(lot_str)
        except ValueError as e:
            raise ValueError(
                f"批號必須是整數，但收到: {lot_str}"
            ) from e
        
        return {
            'production_date': production_date,
            'machine_no': machine_no,
            'mold_no': mold_no,
            'production_lot': production_lot
        }
    
    def validate(self, product_id: str) -> Tuple[bool, Optional[str]]:
        """
        驗證 Product ID 格式是否正確
        
        Args:
            product_id: 要驗證的 Product ID
        
        Returns:
            (是否有效, 錯誤訊息) 的元組
            如果有效，錯誤訊息為 None
        
        Examples:
            >>> gen = ProductIDGenerator()
            >>> gen.validate("2025-09-02_P24_238-2_301")
            (True, None)
            >>> gen.validate("invalid_id")
            (False, 'Product ID 格式錯誤...')
        """
        try:
            self.parse(product_id)
            return (True, None)
        except ValueError as e:
            return (False, str(e))
    
    def _parse_date(self, date_str: str) -> date:
        """
        解析多種日期格式
        
        支援格式:
        - YYYY-MM-DD (ISO 8601)
        - YYYYMMDD (8位數字)
        - YYYY/MM/DD
        - DD/MM/YYYY
        - MM/DD/YYYY
        
        Args:
            date_str: 日期字串
        
        Returns:
            date 物件
        
        Raises:
            ValueError: 如果無法解析日期
        """
        # 移除空白
        date_str = date_str.strip()
        
        # 嘗試各種格式
        formats = [
            "%Y-%m-%d",      # 2025-09-02
            "%Y%m%d",        # 20250902
            "%Y/%m/%d",      # 2025/09/02
            "%d/%m/%Y",      # 02/09/2025
            "%m/%d/%Y",      # 09/02/2025
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # 所有格式都失敗
        raise ValueError(
            f"無法解析日期: {date_str}，支援格式: YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD"
        )


# 單例實例
product_id_generator = ProductIDGenerator()


# 快捷函數，方便直接匯入使用
def generate_product_id(
    production_date: date,
    machine_no: str,
    mold_no: str,
    production_lot: int
) -> str:
    """
    快捷函數: 產生 Product ID
    
    Examples:
        >>> from app.services.product_id_generator import generate_product_id
        >>> from datetime import date
        >>> generate_product_id(date(2025, 9, 2), "P24", "238-2", 301)
        '2025-09-02_P24_238-2_301'
    """
    return product_id_generator.generate(
        production_date, machine_no, mold_no, production_lot
    )


def parse_product_id(product_id: str) -> Dict[str, any]:
    """
    快捷函數: 解析 Product ID
    
    Examples:
        >>> from app.services.product_id_generator import parse_product_id
        >>> parse_product_id("2025-09-02_P24_238-2_301")
        {'production_date': datetime.date(2025, 9, 2), 'machine_no': 'P24', ...}
    """
    return product_id_generator.parse(product_id)


def validate_product_id(product_id: str) -> Tuple[bool, Optional[str]]:
    """
    快捷函數: 驗證 Product ID
    
    Examples:
        >>> from app.services.product_id_generator import validate_product_id
        >>> validate_product_id("2025-09-02_P24_238-2_301")
        (True, None)
    """
    return product_id_generator.validate(product_id)
