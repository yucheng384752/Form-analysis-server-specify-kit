import pandas as pd

from app.services.analytics_external import (
    _filter_df,
    _normalize_binary_target,
    _parse_date_to_yyyymmdd,
    _pick_date_column_for_station,
)


def test_parse_date_to_yyyymmdd_accepts_float_like_strings() -> None:
    assert _parse_date_to_yyyymmdd("20250901.0") == 20250901
    assert _parse_date_to_yyyymmdd("20250901.000") == 20250901


def test_pick_date_column_for_station_prefers_production_date_for_p3() -> None:
    df = pd.DataFrame(
        {
            "Production Date_y": ["20250901", None, None],
            "Slitting date": ["20250820_11_00", "20250821_11_00", "20250822_11_00"],
        }
    )

    # Even though Slitting date has more parsable rows, P3 must prefer production_date-like column.
    assert _pick_date_column_for_station(df, "P3") == "Production Date_y"
    assert _pick_date_column_for_station(df, "P2") == "Slitting date"


def test_filter_df_station_specific_date_column_selection() -> None:
    df = pd.DataFrame(
        {
            "Production Date_y": ["20250901", "20250902", "20250903"],
            "Slitting date": ["20250820_11_00", "20250821_11_00", "20250822_11_00"],
            "Finish": [1.0, 0.0, 1.0],
        }
    )

    # P3 should filter based on Production Date_y.
    out = _filter_df(
        df,
        start_date="2025-09-02",
        end_date="2025-09-02",
        product_id=None,
        station="P3",
    )
    assert len(out) == 1
    assert out.iloc[0]["Production Date_y"] == "20250902"

    # P2 should filter based on Slitting date.
    out2 = _filter_df(
        df,
        start_date="2025-08-21",
        end_date="2025-08-21",
        product_id=None,
        station="P2",
    )
    assert len(out2) == 1
    assert out2.iloc[0]["Slitting date"] == "20250821_11_00"


def test_normalize_binary_target_maps_floatish_values_to_0_1() -> None:
    assert _normalize_binary_target(0.0) == "0"
    assert _normalize_binary_target(1.0) == "1"
    assert _normalize_binary_target("0.0") == "0"
    assert _normalize_binary_target("1.0") == "1"
    assert _normalize_binary_target(False) == "0"
    assert _normalize_binary_target(True) == "1"
    assert _normalize_binary_target("NG") == "0"
    assert _normalize_binary_target("OK") == "1"
