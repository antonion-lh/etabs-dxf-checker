"""
tests/test_trnsko_frame_e2k.py
-------------------------------
Unit tests for parsing and verifying RC frame structures with Section Designer
sections and nonlinear plastic hinges (Osnovna škola Trnsko model).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase1_e2k import parse_e2k
from curriculum_audit import run_curriculum_audit

TRNSKO_E2K = os.path.join(os.path.dirname(__file__), "..", "trnsko_model.e2k")


@pytest.mark.skipif(not os.path.exists(TRNSKO_E2K), reason="trnsko_model.e2k not present")
def test_parse_trnsko_frame_counts():
    """Verify that all columns, beams, slabs, restraints, and hinges are correctly parsed."""
    d = parse_e2k(TRNSKO_E2K, Config())

    cols = d["columns"]
    beams = d["beams"]
    walls = d["walls"]
    slabs = d["slabs"]
    rests = d["restraints"]
    hinges = d["hinges"]

    # 119 columns per story * 2 stories = 238
    assert len(cols) == 238
    # 192 beams per story * 2 stories = 384
    assert len(beams) == 384
    # Frame structure has no shear walls
    assert len(walls) == 0
    # 70 floor panels per story * 2 stories = 140
    assert len(slabs) == 140
    # 119 column base supports
    assert len(rests) == 119
    # 291 assigned plastic hinges
    assert len(hinges) == 291


@pytest.mark.skipif(not os.path.exists(TRNSKO_E2K), reason="trnsko_model.e2k not present")
def test_parse_trnsko_section_designer_dimensions():
    """Verify Section Designer section dimensions extraction for columns and beams."""
    d = parse_e2k(TRNSKO_E2K, Config())
    cols = d["columns"]
    beams = d["beams"]

    c_s4030 = cols[cols["section"] == "STUP40/30_sd"].iloc[0]
    assert c_s4030["width_mm"] in (300.0, 400.0)
    assert c_s4030["height_mm"] in (300.0, 400.0)

    b_g4030 = beams[beams["section"] == "GREDA40/30_sd"].iloc[0]
    assert b_g4030["width_mm"] in (300.0, 400.0)
    assert b_g4030["height_mm"] in (300.0, 400.0)

    b_g3060 = beams[beams["section"] == "GREDA30/60_sd"].iloc[0]
    assert b_g3060["width_mm"] == 300.0
    assert b_g3060["height_mm"] == 600.0


@pytest.mark.skipif(not os.path.exists(TRNSKO_E2K), reason="trnsko_model.e2k not present")
def test_parse_trnsko_stories_and_z_elevations():
    """Verify that columns and beams are instantiated on both Story1 and Story2 with accurate Z levels."""
    d = parse_e2k(TRNSKO_E2K, Config())
    cols = d["columns"]
    beams = d["beams"]

    st1_cols = cols[cols["story"] == "Story1"]
    st2_cols = cols[cols["story"] == "Story2"]
    assert len(st1_cols) == 119
    assert len(st2_cols) == 119
    assert (st1_cols["z_start"] == 0.0).all()
    assert (st1_cols["z_end"] == 3.6).all()
    assert (st2_cols["z_start"] == 3.6).all()
    assert (st2_cols["z_end"] == 7.2).all()

    st1_beams = beams[beams["story"] == "Story1"]
    st2_beams = beams[beams["story"] == "Story2"]
    assert len(st1_beams) == 192
    assert len(st2_beams) == 192
    assert (st1_beams["z_start"] == 3.6).all()
    assert (st2_beams["z_start"] == 7.2).all()


@pytest.mark.skipif(not os.path.exists(TRNSKO_E2K), reason="trnsko_model.e2k not present")
def test_trnsko_curriculum_audit():
    """Verify that curriculum audit correctly handles RC frame structure without spurious wall errors."""
    d = parse_e2k(TRNSKO_E2K, Config())
    audit_results = run_curriculum_audit(d)

    by_num = {r["num"]: r for r in audit_results}

    # Point 20: Base restraints
    assert by_num[20]["status"] == "PASS"

    # Point 25: Pier & Spandrel (not applicable for walls on frame building)
    assert by_num[25]["status"] == "PASS"

    # Point 30: Hand calculation of mass
    assert by_num[30]["status"] == "PASS"

    # Point 31: Structural wall ratio (pure frame system recognized)
    assert by_num[31]["status"] == "PASS"

    # Point 34: Overturning stability
    assert by_num[34]["status"] == "PASS"

    # Point 51: Torsional regularity from column distribution
    assert by_num[51]["status"] == "PASS"
