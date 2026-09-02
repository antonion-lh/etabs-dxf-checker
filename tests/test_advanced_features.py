"""
test_advanced_features.py
-------------------------
Tests for advanced enterprise functionalities:
- Unannotated geometric closed polylines (drawings without text labels)
- AutoCAD block references (INSERT entities)
- Multi-bay commercial building parsing & validation (860 elements)
- Multi-story elevation filtering (Story / Level)
- Element type filtering via cfg.extract_elements
- Full PDF and HTML report generation under load
"""

import os
import tempfile
import ezdxf
import pytest

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status
from report import generate_pdf, generate_html

COMMERCIAL_E2K = os.path.join(os.path.dirname(__file__), "..", "demo_commercial_building.e2k")
COMMERCIAL_DXF = os.path.join(os.path.dirname(__file__), "..", "demo_commercial_building.dxf")


def test_geometric_polylines_without_text():
    """Test that closed rectangles on structural layers without text are auto-detected & measured."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("STUPOVI", color=1)

    for i in range(3):
        x = i * 400
        msp.add_lwpolyline([(x, 0), (x + 40, 0), (x + 40, 60), (x, 60)], close=True, dxfattribs={"layer": "STUPOVI"})

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        doc.saveas(f.name)
        dxf_path = f.name

    try:
        cfg = Config(dxf_unit_scale=0.01)
        df = parse_dxf(dxf_path, cfg)
        assert len(df) == 3
        assert (df["element_type"] == "column").all()
        assert (df["dim1_mm"] == 400).all()
        assert (df["dim2_mm"] == 600).all()
    finally:
        os.unlink(dxf_path)


def test_autocad_block_reference_inserts():
    """Test that AutoCAD block references (INSERT) are resolved and extracted."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("STUPOVI", color=2)

    blk = doc.blocks.new(name="COL_BLOCK")
    blk.add_lwpolyline([(-25, -25), (25, -25), (25, 25), (-25, 25)], close=True)

    msp.add_blockref("COL_BLOCK", insert=(0, 0), dxfattribs={"layer": "STUPOVI"})
    msp.add_blockref("COL_BLOCK", insert=(500, 0), dxfattribs={"layer": "STUPOVI"})

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        doc.saveas(f.name)
        dxf_path = f.name

    try:
        cfg = Config(dxf_unit_scale=0.01)
        df = parse_dxf(dxf_path, cfg)
        assert len(df) == 2
        assert (df["element_type"] == "column").all()
        assert (df["dim1_mm"] == 500).all()
        assert (df["dim2_mm"] == 500).all()
    finally:
        os.unlink(dxf_path)


def test_complex_commercial_building_validation():
    """Test full pipeline on 860-element commercial building."""
    assert os.path.exists(COMMERCIAL_E2K)
    assert os.path.exists(COMMERCIAL_DXF)

    cfg = Config(dxf_unit_scale=0.01)
    df_dxf = parse_dxf(COMMERCIAL_DXF, cfg)
    with open(COMMERCIAL_E2K) as f:
        etabs = parse_e2k(f, cfg)

    assert len(etabs["columns"]) == 304
    assert len(etabs["beams"]) == 554
    assert len(etabs["restraints"]) == 152

    df_res = validate(etabs, df_dxf, cfg)
    assert len(df_res) >= 850

    # Check floor 1 evaluation
    cols_data = etabs["columns"]
    cols_fl1 = set(cols_data[cols_data["z_end"] <= 4.0]["name"].astype(str))
    df_fl1 = df_res[df_res["etabs_name"].astype(str).isin(cols_fl1) | (df_res["status"] == Status.DXF_ONLY)]

    # Floor 1 has 149 matches, 3 deliberate mismatches, 1 dxf only
    counts = df_fl1["status"].value_counts()
    assert counts.get(Status.MATCH, 0) == 149
    assert counts.get(Status.SECTION_MISMATCH, 0) == 3
    assert counts.get(Status.DXF_ONLY, 0) == 1


def test_element_type_filter_strictness():
    """Verify that cfg.extract_elements strictly restricts output types."""
    cfg = Config(dxf_unit_scale=0.01, extract_elements=["columns"])
    df_dxf = parse_dxf(COMMERCIAL_DXF, cfg)
    with open(COMMERCIAL_E2K) as f:
        etabs = parse_e2k(f, cfg)

    df_res = validate(etabs, df_dxf, cfg)
    assert set(df_res["element_type"].unique()) == {"column"}


def test_pdf_and_html_generation_under_load():
    """Verify report generation on large building."""
    cfg = Config(dxf_unit_scale=0.01)
    df_dxf = parse_dxf(COMMERCIAL_DXF, cfg)
    with open(COMMERCIAL_E2K) as f:
        etabs = parse_e2k(f, cfg)
    df_res = validate(etabs, df_dxf, cfg)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_pdf:
        pdf_path = f_pdf.name
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f_html:
        html_path = f_html.name

    try:
        generate_pdf(df_res, pdf_path, cfg)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 10000

        html_content = generate_html(df_res, html_path, cfg)
        assert os.path.exists(html_path)
        assert len(html_content) > 10000
    finally:
        try: os.unlink(pdf_path)
        except: pass
        try: os.unlink(html_path)
        except: pass


def test_kpi_strip_safety_on_empty_or_corrupt_dataframe():
    """Verify _kpi_strip never raises KeyError on empty or column-less DataFrames."""
    import pandas as pd
    from streamlit_app import _kpi_strip

    # Empty DataFrame
    df_empty = pd.DataFrame()
    _kpi_strip(df_empty, is_pdf_mode=True, etabs_data={})
    _kpi_strip(df_empty, is_pdf_mode=False, etabs_data={})

    # DataFrame with missing columns
    df_missing = pd.DataFrame([{"foo": "bar"}])
    _kpi_strip(df_missing, is_pdf_mode=True, etabs_data={})
    _kpi_strip(df_missing, is_pdf_mode=False, etabs_data={})


def test_e2k_positional_and_assigns_blocks():
    """Verify e2k parser handles positional coordinates and separate ASSIGN blocks."""
    import io
    from phase1_e2k import parse_e2k

    e2k_sample = """
$ POINT COORDINATES
  POINT "P1" 0.0 0.0 0.0
  POINT "P2" 0.0 0.0 3.5

$ LINE OBJECT CONNECTIVITY
  LINE "C1" "P1" "P2"

$ LINE ASSIGNS
  LINE "C1" SECTION "COL_40x40"

$ FRAME SECTIONS
  FRAME "COL_40x40" SHAPE "RECTANGULAR" T3 0.40 T2 0.40
"""
    etabs = parse_e2k(io.StringIO(e2k_sample))
    cols = etabs["columns"]
    assert len(cols) == 1
    assert cols.iloc[0]["name"] == "C1"
    assert cols.iloc[0]["section"] == "COL_40x40"
    assert cols.iloc[0]["height_mm"] == 400.0

