import pytest
from datetime import date
from app.utils.normalization import normalize_lot_no, normalize_date, normalize_date_to_int, NormalizationError

def test_normalize_lot_no():
    assert normalize_lot_no("1234567-01") == 123456701
    assert normalize_lot_no("1234567_01") == 123456701
    assert normalize_lot_no("123456701") == 123456701
    assert normalize_lot_no("123-45") == 12345
    
    with pytest.raises(NormalizationError) as exc:
        normalize_lot_no("abc")
    assert exc.value.code == "E_LOT_FORMAT"

    with pytest.raises(NormalizationError) as exc:
        normalize_lot_no("")
    assert exc.value.code == "E_LOT_EMPTY"

def test_normalize_date():
    expected = date(2023, 1, 1)
    
    # YYYY-MM-DD
    assert normalize_date("2023-01-01") == expected
    
    # YYYYMMDD
    assert normalize_date("20230101") == expected
    assert normalize_date(20230101) == expected
    
    # ROC YYYMMDD
    assert normalize_date("1120101") == expected
    assert normalize_date(1120101) == expected
    
    # Date object
    assert normalize_date(expected) == expected

    # Invalid
    with pytest.raises(NormalizationError) as exc:
        normalize_date("invalid")
    assert exc.value.code == "E_DATE_FORMAT"

def test_normalize_date_to_int():
    assert normalize_date_to_int("2023-01-01") == 20230101
    assert normalize_date_to_int("1120101") == 20230101
