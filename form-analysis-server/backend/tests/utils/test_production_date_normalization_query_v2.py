from app.api.routes_query_v2 import _normalize_production_date


def test_normalize_production_date_handles_yymmdd_numericish() -> None:
    assert _normalize_production_date(250717) == "2025-07-17"
    assert _normalize_production_date(250717.0) == "2025-07-17"
    assert _normalize_production_date("250717") == "2025-07-17"
    assert _normalize_production_date("250717.0") == "2025-07-17"


def test_normalize_production_date_handles_yyyymmdd_and_suffix() -> None:
    assert _normalize_production_date("20250807") == "2025-08-07"
    assert _normalize_production_date("20250807_16_00") == "2025-08-07"


def test_normalize_production_date_handles_slash_or_iso() -> None:
    assert _normalize_production_date("2025/08/07") == "2025-08-07"
    assert _normalize_production_date("2025-8-7") == "2025-08-07"


def test_normalize_production_date_passthrough_unknown() -> None:
    assert _normalize_production_date("not-a-date") == "not-a-date"
    assert _normalize_production_date(None) is None
