import pytest
from datetime import date
from app.utils.normalization import (
    normalize_lot_no,
    normalize_date,
    normalize_date_to_int,
    normalize_search_term,
    normalize_search_term_variants,
    NormalizationError,
)

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


def test_normalize_search_term_equivalences():
    expected = "pe32"
    assert normalize_search_term("PE32") == expected
    assert normalize_search_term("PE 32") == expected
    assert normalize_search_term("pe-32") == expected
    assert normalize_search_term("pe_32") == expected
    assert normalize_search_term("\tPE\n 32\r") == expected
    assert normalize_search_term("ＰＥ３２") == expected


def test_normalize_search_term_variants_includes_fullwidth():
    variants = normalize_search_term_variants("PE 32")
    assert variants[0] == "pe32"
    # Fullwidth ASCII of 'pe32' is 'ｐｅ３２'
    assert "ｐｅ３２" in variants


def test_normalize_search_term_empty_returns_none():
    assert normalize_search_term(None) is None
    assert normalize_search_term("") is None
    assert normalize_search_term("   ") is None
