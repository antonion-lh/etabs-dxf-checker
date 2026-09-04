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


def test_pdf_aggregation_counts_all_occurrences():
    """Bug-condition exploration test (task 1.1).

    A section "50/50" appears FOUR times on the vector PDF. The ETABS model
    has one element with that section (width_mm=500, height_mm=500). The row
    for that element must report pdf_match_count == 4.

    On the UNFIXED code this FAILS: validate_against_pdf stops at the first
    match (break) and produces no pdf_match_count column.
    """
    import pandas as pd

    raw = _make_text_pdf(["50/50", "50/50", "50/50", "50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C1",
                "story": "S1",
                "section": "C50",
                "width_mm": 500.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    row = df[df["etabs_name"] == "C1"].iloc[0]
    assert "pdf_match_count" in df.columns, "nema kolone pdf_match_count"
    assert row["pdf_match_count"] == 4, (
        "ocekivano 4 pojave, dobiveno %r" % row.get("pdf_match_count")
    )


def test_pdf_only_dimension_reported():
    """Bug-condition exploration test (task 1.2).

    A vector PDF contains the section dimension "60/60", but the ETABS model
    has NO element with a 60/60 section (only a 30/50 column). Because the
    comparison is currently one-directional (model -> drawing), a dimension
    that exists ONLY on the drawing is never reported.

    The expected (desired) behaviour is that validate_against_pdf produces a
    row with status "\u004b\u006f\u0074\u0061 na nacrtu bez elementa u modelu".

    On the UNFIXED code this FAILS: no such status/row is ever produced.
    """
    import pandas as pd

    PDF_ONLY = "\u004b\u006f\u0074\u0061 na nacrtu bez elementa u modelu"

    raw = _make_text_pdf(["Stup 30/50", "Kota 60/60"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C1",
                "story": "S1",
                "section": "C3050",
                "width_mm": 300.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    statuses = set(df["status"]) if not df.empty else set()
    assert PDF_ONLY in statuses, (
        "ocekivan status %r za kotu 60/60 koja nema element u modelu; dobiveno %r"
        % (PDF_ONLY, sorted(statuses))
    )


def test_dim_token_respects_word_boundaries():
    """Bug-condition exploration test (task 1.3).

    Word-boundary / substring safety. When the drawing shows a LARGER number
    (e.g. "1400", "1450", "2400", "4000") we look for a section value of 40 cm
    (= 400 mm). "40" is a textual substring of "1400" etc., so a naive matcher
    could falsely confirm a 40 cm section.

    Two layers are checked:

    (a) Direct _classify_dim_token layer:
        A pure longer number token MUST NOT yield a small 40 / 140 dimension.

    (b) End-to-end validate_against_pdf layer:
        A drawing whose ONLY dimension-like tokens are larger numbers that
        merely CONTAIN the target as a substring MUST NOT confirm a 400 mm
        (40 cm) element.

    Observed behaviour on the unfixed code:
      * Pure isolated tokens ("1400", "1450", "2400", "4000") -> None, because
        the regexes anchor with \\b / limited digit counts. So the pure
        substring case is already safe.
      * BUT the regexes use re.search (not a full-token match). A COMBINED
        token such as "kota1400 t=40" is a single PDF word that still contains
        a valid "t=40" fragment, so _classify_dim_token happily extracts a
        400 mm thickness and validate_against_pdf FALSELY confirms the 40 cm
        element. That combined token is the real counterexample this test
        pins down.
    """
    import pandas as pd

    CONFIRM = "Dimenzija potvr\u0111ena na nacrtu"

    # (a) Direct token layer: pure longer numbers must not extract 40 / 140.
    pure_longer = ["1400", "1450", "2400", "4000"]
    for tok in pure_longer:
        parsed = _classify_dim_token(tok)
        got = None if parsed is None else parsed.get("d1_mm")
        assert got not in (40.0, 140.0, 400.0), (
            "token %r ne smije dati laznu dimenziju 40/140/400 mm, dobiveno %r"
            % (tok, got)
        )

    # (b) End-to-end: a drawing full of larger numbers that only CONTAIN the
    #     target 40 as a substring must NOT confirm a 400 mm (40 cm) element.
    #     The combined token "kota1400 t=40" is included because it is the
    #     concrete counterexample that triggers the false substring match.
    etabs_data = {
        "walls": pd.DataFrame([
            {
                "name": "W1",
                "story": "S1",
                "section": "Z40",
                "width_mm": 400.0,
                "thickness_mm": 400.0,
                "material": "C30/37",
            }
        ])
    }

    substring_only_drawings = [
        ["1400"],
        ["1450"],
        ["2400"],
        ["4000"],
        ["1400", "1450", "2400", "4000"],
        ["kota1400 t=40"],
    ]
    for lines in substring_only_drawings:
        raw = _make_text_pdf(lines)
        df = validate_against_pdf(etabs_data, raw, Config())
        statuses = set(df["status"]) if not df.empty else set()
        assert CONFIRM not in statuses, (
            "nacrt %r sadrzi 40 samo kao podniz vece brojke i NE smije "
            "potvrditi presjek 40 cm; dobiveni statusi %r"
            % (lines, sorted(statuses))
        )


def test_pdf_summary_attr_present():
    """Bug-condition exploration test (task 1.4).

    After a comparison over the whole model, an aggregated model-level
    summary must be exposed on the returned DataFrame as
    ``df.attrs["pdf_summary"]``. It must be a dict that contains at least
    the keys "confirmed", "not_found" and "pdf_only".

    Here the vector PDF contains a "50/50" section (confirmed by the model
    element C1 with width_mm=500, height_mm=500), so there is at least one
    confirmed dimension and at least one model element.

    On the UNFIXED code this FAILS: df.attrs only carries "pdf_dim_tokens"
    and "pdf_has_text_dims"; there is no "pdf_summary" attribute.
    """
    import pandas as pd

    raw = _make_text_pdf(["Stupovi 50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C1",
                "story": "S1",
                "section": "C50",
                "width_mm": 500.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    assert "pdf_summary" in df.attrs, (
        "nema atributa pdf_summary; prisutni atributi: %r"
        % sorted(df.attrs.keys())
    )
    summary = df.attrs["pdf_summary"]
    assert isinstance(summary, dict), (
        "pdf_summary mora biti dict, dobiveno %r" % type(summary)
    )
    for key in ("confirmed", "not_found", "pdf_only"):
        assert key in summary, (
            "pdf_summary mora sadrzavati kljuc %r; prisutni kljucevi: %r"
            % (key, sorted(summary.keys()))
        )


def test_pdf_match_confidence_present():
    """Bug-condition exploration test (task 1.5).

    Confidence level. A vector PDF contains a confirmed section "50/50" and the
    ETABS model has one element with that section (width_mm=500, height_mm=500).
    The returned DataFrame must expose a per-row confidence column
    ``pdf_match_confidence`` whose value for the confirmed row is one of
    {"visoka", "srednja", "niska"}.

    On the UNFIXED code this FAILS: there is no pdf_match_confidence column at
    all (only the STANDARD_COLS defined in validate_against_pdf).
    """
    import pandas as pd

    CONF_LOCAL = "Dimenzija potvr\u0111ena na nacrtu"
    ALLOWED = {"visoka", "srednja", "niska"}

    raw = _make_text_pdf(["Stupovi 50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C1",
                "story": "S1",
                "section": "C50",
                "width_mm": 500.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    # (a) column must exist
    assert "pdf_match_confidence" in df.columns, (
        "nema kolone pdf_match_confidence; prisutne kolone: %r"
        % sorted(df.columns)
    )
    # (b) confirmed row value must be in the allowed confidence set
    confirmed = df[df["status"] == CONF_LOCAL]
    assert not confirmed.empty, "nema potvr\u0111enog reda za presjek 50/50"
    val = confirmed.iloc[0]["pdf_match_confidence"]
    assert val in ALLOWED, (
        "razina pouzdanosti mora biti u %r; dobiveno %r"
        % (sorted(ALLOWED), val)
    )


# ---------------------------------------------------------------------------
# Task 2 - Preservation tests (baseline behaviour that the fix MUST NOT change)
# Observed on the UNFIXED code and pinned here. These MUST PASS pre-fix.
# ---------------------------------------------------------------------------

CONFIRMED_STATUS = "Dimenzija potvr\u0111ena na nacrtu"
NO_MODEL_DIM_STATUS = "Nema dimenzije u modelu"
NOT_FOUND_STATUS = "Dimenzija nije na\u0111ena na nacrtu"


def test_preserve_unique_confirmed():
    """2.1 A section "50/50" appearing EXACTLY once on the drawing, matched by a
    model column (width_mm=500, height_mm=500), keeps the status
    "Dimenzija potvr\u0111ena na nacrtu". _Req 3.3_"""
    import pandas as pd

    raw = _make_text_pdf(["50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C1",
                "story": "S1",
                "section": "C50",
                "width_mm": 500.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    row = df[df["etabs_name"] == "C1"].iloc[0]
    assert row["status"] == CONFIRMED_STATUS, (
        "ocekivan status %r, dobiveno %r" % (CONFIRMED_STATUS, row["status"])
    )


def test_preserve_no_model_dim():
    """2.2 An element with no parseable section (width_mm=None and
    height_mm=None) keeps the status "Nema dimenzije u modelu". _Req 3.2_"""
    import pandas as pd

    raw = _make_text_pdf(["50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C2",
                "story": "S1",
                "section": "X",
                "width_mm": None,
                "height_mm": None,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    row = df[df["etabs_name"] == "C2"].iloc[0]
    assert row["status"] == NO_MODEL_DIM_STATUS, (
        "ocekivan status %r, dobiveno %r" % (NO_MODEL_DIM_STATUS, row["status"])
    )


def test_preserve_not_found():
    """2.3 A model element "30/60" (width_mm=300, height_mm=600) and a drawing
    that only shows "20/20" keeps the status
    "Dimenzija nije na\u0111ena na nacrtu". _Req 3.4_"""
    import pandas as pd

    raw = _make_text_pdf(["20/20"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C3",
                "story": "S1",
                "section": "C3060",
                "width_mm": 300.0,
                "height_mm": 600.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    row = df[df["etabs_name"] == "C3"].iloc[0]
    assert row["status"] == NOT_FOUND_STATUS, (
        "ocekivan status %r, dobiveno %r" % (NOT_FOUND_STATUS, row["status"])
    )


def test_preserve_scanned_pdf_no_text():
    """2.4 A PDF with no textual dimension tokens (empty page) yields
    pdf_has_dimension_text(...) is False, so the scanned-PDF fallback is
    preserved. _Req 3.1, 3.5_"""
    raw = _make_text_pdf([])
    assert pdf_has_dimension_text(raw) is False


def test_preserve_standard_cols_and_no_spatial():
    """2.5 After validate_against_pdf all existing STANDARD_COLS are present in
    df.columns and xy_dist_m is None for every row (no spatial matching).
    _Req 3.6, 3.7_"""
    import pandas as pd

    expected_cols = [
        "element_type", "status", "etabs_name", "story", "etabs_x", "etabs_y",
        "etabs_z", "etabs_section", "etabs_w_mm", "etabs_h_mm", "etabs_material",
        "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm", "xy_dist_m", "notes",
    ]
    raw = _make_text_pdf(["50/50"])
    etabs_data = {
        "columns": pd.DataFrame([
            {
                "name": "C5",
                "story": "S1",
                "section": "C50",
                "width_mm": 500.0,
                "height_mm": 500.0,
                "material": "C30/37",
            }
        ])
    }
    df = validate_against_pdf(etabs_data, raw, Config())
    assert not df.empty
    for col in expected_cols:
        assert col in df.columns, (
            "nedostaje standardna kolona %r; prisutne: %r"
            % (col, list(df.columns))
        )
    assert df["xy_dist_m"].isna().all(), (
        "xy_dist_m mora biti None u svim redovima (bez prostornog poklapanja); "
        "dobiveno %r" % list(df["xy_dist_m"])
    )
