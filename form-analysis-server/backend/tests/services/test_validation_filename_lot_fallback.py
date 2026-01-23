from app.services.validation import file_validation_service


def test_p1_p2_lot_no_can_fallback_from_filename_when_missing_in_content():
    # CSV intentionally has no lot_no column/value.
    csv_bytes = b"quantity\n1\n"

    result = file_validation_service.validate_file(csv_bytes, "P1_2507173_02.csv")
    assert result["invalid_rows"] == 0
    assert result["total_rows"] == 1


def test_p1_missing_lot_no_still_errors_when_filename_has_no_lot():
    csv_bytes = b"quantity\n1\n"

    result = file_validation_service.validate_file(csv_bytes, "P1_no_lot.csv")
    assert result["invalid_rows"] == 1
    assert any(e.get("error_code") == "REQUIRED_FIELD" for e in result.get("errors", []))


def test_p3_does_not_fallback_from_filename_for_lot_no():
    # P3 requires lot_no from content (lot no or P3_No.)
    csv_bytes = b"Machine NO,Mold NO\n1,2\n"

    result = file_validation_service.validate_file(csv_bytes, "P3_2507173_02.csv")
    assert result["invalid_rows"] == 1
    # Error should point to missing lot field
    assert any(e.get("error_code") == "REQUIRED_FIELD" for e in result.get("errors", []))
