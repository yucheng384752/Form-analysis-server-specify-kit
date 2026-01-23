from app.services.analytics_external import (
    _is_lot_winder_product_id,
    _is_p3_produce_no_product_id,
    _normalize_station_selection_for_product_id,
)


def test_is_lot_winder_product_id_true() -> None:
    assert _is_lot_winder_product_id("2507173_02_1") is True
    assert _is_lot_winder_product_id("2507173_01_1") is True


def test_is_lot_winder_product_id_false() -> None:
    assert _is_lot_winder_product_id(None) is False
    assert _is_lot_winder_product_id("") is False
    assert _is_lot_winder_product_id("   ") is False
    assert _is_lot_winder_product_id("P3-20250901-001") is False
    assert _is_lot_winder_product_id("2507173_02") is False
    assert _is_lot_winder_product_id("2507173_02_1_x") is False


def test_is_p3_produce_no_product_id_true() -> None:
    assert _is_p3_produce_no_product_id("20250902_P21_238-3_302") is True
    assert _is_p3_produce_no_product_id("20250902_P21_238-3_302_dup9") is True


def test_is_p3_produce_no_product_id_false() -> None:
    assert _is_p3_produce_no_product_id(None) is False
    assert _is_p3_produce_no_product_id("") is False
    assert _is_p3_produce_no_product_id("   ") is False
    assert _is_p3_produce_no_product_id("2507173_02_1") is False
    assert _is_p3_produce_no_product_id("P3-20250901-001") is False


def test_normalize_station_selection_for_product_id_forces_p2() -> None:
    assert _normalize_station_selection_for_product_id(["P3"], "2507173_02_1") == ["P2"]
    assert _normalize_station_selection_for_product_id(["ALL"], "2507173_01_1") == ["P2"]
    assert _normalize_station_selection_for_product_id([], "2507173_01_1") == ["P2"]


def test_normalize_station_selection_for_product_id_forces_p3() -> None:
    assert _normalize_station_selection_for_product_id(["P2"], "20250902_P21_238-3_302") == ["P3"]
    assert _normalize_station_selection_for_product_id(["ALL"], "20250902_P21_238-3_302_dup9") == ["P3"]


def test_normalize_station_selection_for_product_id_passthrough() -> None:
    assert _normalize_station_selection_for_product_id(["P3"], None) == ["P3"]
    assert _normalize_station_selection_for_product_id(["P2", "P3"], "P3-20250901-001") == ["P2", "P3"]
