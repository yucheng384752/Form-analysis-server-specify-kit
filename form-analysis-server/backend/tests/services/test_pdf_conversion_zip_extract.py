import io
import zipfile

import pytest

from app.services.pdf_conversion import (
    _extract_csv_texts_from_zip_bytes,
    _select_csv_name_for_pdf,
)


def _make_zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


def test_extract_csvs_from_zip_bytes_reads_csv_only():
    zip_bytes = _make_zip_bytes(
        {
            "a.csv": "col\n1\n",
            "b.CSV": "col\n2\n",
            "ignore.txt": "nope",
            "folder/c.csv": "col\n3\n",
        }
    )
    csvs = _extract_csv_texts_from_zip_bytes(zip_bytes)
    assert set(csvs.keys()) == {"a.csv", "b.CSV", "c.csv"}
    assert "2" in csvs["b.CSV"]


def test_select_csv_name_for_pdf_prefers_exact_match():
    csvs = {"A.csv": "x", "other.csv": "y"}
    assert _select_csv_name_for_pdf(csvs, "A.pdf") == "A.csv"


def test_select_csv_name_for_pdf_falls_back_to_contains_stem():
    csvs = {"report_A_2026.csv": "x", "report_B_2026.csv": "y"}
    assert _select_csv_name_for_pdf(csvs, "A.pdf") == "report_A_2026.csv"


def test_select_csv_name_for_pdf_multiple_without_match_raises():
    csvs = {"x.csv": "1", "y.csv": "2"}
    with pytest.raises(ValueError):
        _select_csv_name_for_pdf(csvs, "A.pdf")
