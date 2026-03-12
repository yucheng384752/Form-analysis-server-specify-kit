from app.services.analytics_external import _matches_any_product_id


def test_matches_any_product_id_short_and_long_format_alias():
    # User input format (from complaint list): YYMMDD-P24-2382-301
    product_ids = ["250905-P24-2382-301"]
    # System-side format used in analytics workflows: YYYYMMDD_P24_238-2_301
    assert _matches_any_product_id(
        "20250905_P24_238-2_301", product_ids=product_ids
    )


def test_matches_any_product_id_keeps_backward_substring_behavior():
    product_ids = ["2507173_02_19"]
    assert _matches_any_product_id(
        "event_id=abc produce_no=2507173_02_19", product_ids=product_ids
    )


def test_matches_any_product_id_returns_false_when_unrelated():
    product_ids = ["20250910_P23_238-4_304"]
    assert not _matches_any_product_id(
        "2507173_02_19", "2b39726b-bec7-416f-99d2-9466a7580358", product_ids=product_ids
    )
