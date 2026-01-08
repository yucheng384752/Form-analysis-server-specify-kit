import re
from datetime import date, datetime
from typing import Union, Optional

class NormalizationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

def normalize_lot_no(val: str) -> int:
    """
    Normalize lot number string to integer.
    Removes non-digit characters.
    e.g. "1234567-01" -> 123456701
    """
    if not val:
        raise NormalizationError("E_LOT_EMPTY", "Lot number is empty")
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str(val))
    
    if not digits:
        raise NormalizationError("E_LOT_FORMAT", f"Invalid lot number format: {val}")
        
    try:
        return int(digits)
    except ValueError:
        raise NormalizationError("E_LOT_FORMAT", f"Invalid lot number format: {val}")

def normalize_date(val: Union[str, int, date, datetime]) -> date:
    """
    Normalize date to date object.
    Supports:
    - "YYYY-MM-DD"
    - "YYYYMMDD"
    - "YYYMMDD" (ROC year, e.g. 1120101 -> 2023-01-01)
    - int (20230101 or 1120101)
    """
    if val is None:
        raise NormalizationError("E_DATE_EMPTY", "Date is empty")
    
    if isinstance(val, (date, datetime)):
        if isinstance(val, datetime):
            return val.date()
        return val
        
    s_val = str(val).strip()
    
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(s_val, "%Y-%m-%d").date()
    except ValueError:
        pass
        
    # Try YYYYMMDD or YYYMMDD
    # Remove non-digits
    digits = re.sub(r'\D', '', s_val)
    
    if len(digits) == 8:
        # YYYYMMDD
        try:
            return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
             raise NormalizationError("E_DATE_FORMAT", f"Invalid date format: {val}")
             
    elif len(digits) == 7:
        # YYYMMDD (ROC)
        try:
            roc_year = int(digits[:3])
            month = int(digits[3:5])
            day = int(digits[5:])
            
            ad_year = roc_year + 1911
            return date(ad_year, month, day)
        except ValueError:
             raise NormalizationError("E_DATE_FORMAT", f"Invalid date format: {val}")
    
    raise NormalizationError("E_DATE_FORMAT", f"Invalid date format: {val}")

def normalize_date_to_int(val: Union[str, int, date, datetime]) -> int:
    """
    Normalize date to YYYYMMDD integer.
    """
    d = normalize_date(val)
    return int(d.strftime("%Y%m%d"))
