"""
tests/test_pdf_dims.py
----------------------
Tests for pdf_dims.py - extraction of section dimensions from a PDF text layer
and cross-referencing them with an ETABS model (Option B).
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase1_e2k import parse_e2k
from pdf_dims import (
    _classify_dim_token,
    pdf_has_dimension_text,
    extract_pdf_dimensions,
    validate_against_pdf,
)

fitz = pytest.importorskip("fitz")

CONF = "Dimenzija potvr\u0111ena na nacrtu"
NOTF = "Dimenzija nije na\u0111ena na nacrtu"


def _make_text_pdf(lines):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for ln in lines:
        page.insert_text((80, y), ln, fontsize=11)
        y += 40
    data = doc.tobytes()
    doc.close()
    return data


def test_classify_dim_token_variants():
    assert _classify_dim_token("40/40")["kind"] == "rect"
    assert _classify_dim_token("30x50")["d2_mm"] == 500.0
    assert _classify_dim_token("d=45")["kind"] == "circ"
    assert _classify_dim_token("t=20")["kind"] == "thick"
    assert _classify_dim_token("STUP") is None
    assert _classify_dim_token("") is None


def test_rect_cm_to_mm():
    tok = _classify_dim_token("40/40")
    assert tok["d1_mm"] == 400.0 and tok["d2_mm"] == 400.0


def test_extract_from_text_pdf():
    raw = _make_text_pdf(["50/50", "40/40", "d=45"])
    ext = extract_pdf_dimensions(raw)
    assert ext["has_text_dims"] is True
    kinds = {t["kind"] for t in ext["tokens"]}
    assert "rect" in kinds and "circ" in kinds


def test_has_dimension_text_true_and_false():
    raw_dims = _make_text_pdf(["50/50", "40/40"])
    assert pdf_has_dimension_text(raw_dims) is True
    raw_none = _make_text_pdf(["PRIZEMLJE", "TLOCRT"])
    assert pdf_has_dimension_text(raw_none) is False


def test_validate_against_pdf_confirms_matching_sections():
    e2k = (
        '$ STORIES\n  STORY "S1" HEIGHT 3.0\n'
        '$ POINT COORDINATES\n  POINT "1" 0 0 0\n'
        '$ FRAME SECTIONS\n'
        '  FRAMESECTION "C50" MAT "C30/37" SHAPE "Rectangular" T3 0.5 T2 0.5\n'
        '$ LINE CONNECTIVITIES\n  LINE "C1" COLUMN "1" "1" 1\n'
        '$ LINE ASSIGNS\n  LINEASSIGN "C1" "S1" SECTION "C50"\n'
    )
    e = parse_e2k(io.StringIO(e2k), Config())
    raw = _make_text_pdf(["Stupovi 50/50"])
    df = validate_against_pdf(e, raw, Config())
    assert not df.empty
    assert CONF in set(df["status"])


def test_validate_against_pdf_reports_missing_dimension():
    e2k = (
        '$ STORIES\n  STORY "S1" HEIGHT 3.0\n'
        '$ POINT COORDINATES\n  POINT "1" 0 0 0\n'
        '$ FRAME SECTIONS\n'
        '  FRAMESECTION "C50" MAT "C30/37" SHAPE "Rectangular" T3 0.5 T2 0.5\n'
        '$ LINE CONNECTIVITIES\n  LINE "C1" COLUMN "1" "1" 1\n'
        '$ LINE ASSIGNS\n  LINEASSIGN "C1" "S1" SECTION "C50"\n'
    )
    e = parse_e2k(io.StringIO(e2k), Config())
    raw = _make_text_pdf(["Greda 30/60"])
    df = validate_against_pdf(e, raw, Config())
    assert NOTF in set(df["status"])


def test_scanned_pdf_has_no_text_dims():
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    raw = doc.tobytes()
    doc.close()
    assert pdf_has_dimension_text(raw) is False
