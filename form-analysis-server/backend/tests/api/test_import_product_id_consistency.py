from datetime import date

from app.api.routes_import import _compose_p3_product_id, _extract_production_lot


def test_extract_production_lot_uses_lot_columns_only():
    row = {
        "lot": "302",
        "Produce_No.": "2509303_24_17_301",
    }
    assert _extract_production_lot(row) == 302


def test_extract_production_lot_does_not_fallback_to_produce_no():
    row = {
        "Produce_No.": "2509303_24_17_301",
    }
    assert _extract_production_lot(row) is None


def test_compose_p3_product_id_uses_production_lot_as_last_segment():
    pid = _compose_p3_product_id(
        production_date=date(2025, 9, 30),
        machine_no="P24",
        mold_no="238-4",
        production_lot=302,
    )
    assert pid == "20250930_P24_238-4_302"

