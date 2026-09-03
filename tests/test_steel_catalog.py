"""
test_steel_catalog.py
---------------------
Unit tests for the European structural steel catalog (EN 10365, EN 10210/10219).
"""

import pytest
from steel_catalog import lookup_steel_section, EUROPEAN_I_SECTIONS
from phase3_validation import _dims_match


def test_ipe_lookup():
    sec = lookup_steel_section("IPE 300")
    assert sec is not None
    assert sec["height_mm"] == 300
    assert sec["width_mm"] == 150
    assert sec["tw"] == 7.1
    assert sec["tf"] == 10.7
    assert sec["shape"] == "I-section"

    # Variations in formatting
    for var in ["ipe300", "IPE-300", "IPE300", "  ipe 300  "]:
        res = lookup_steel_section(var)
        assert res is not None
        assert res["height_mm"] == 300
        assert res["width_mm"] == 150


def test_hea_heb_hem_lookup():
    # HEA 240
    hea = lookup_steel_section("HEA 240")
    assert hea is not None
    assert hea["height_mm"] == 230
    assert hea["width_mm"] == 240
    assert hea["tw"] == 7.5
    assert hea["tf"] == 12.0

    # HE 240 A format
    hea_alt = lookup_steel_section("HE 240 A")
    assert hea_alt is not None
    assert hea_alt["height_mm"] == 230

    # HEB 200
    heb = lookup_steel_section("HEB 200")
    assert heb is not None
    assert heb["height_mm"] == 200
    assert heb["width_mm"] == 200

    # HEM 300
    hem = lookup_steel_section("HEM 300")
    assert hem is not None
    assert hem["height_mm"] == 340
    assert hem["width_mm"] == 310


def test_upn_lookup():
    upn = lookup_steel_section("UPN 160")
    assert upn is not None
    assert upn["height_mm"] == 160
    assert upn["width_mm"] == 65
    assert upn["shape"] == "channel"

    # Alternative U 160
    u_alt = lookup_steel_section("U 160")
    assert u_alt is not None
    assert u_alt["height_mm"] == 160


def test_shs_and_rhs_parametric_lookup():
    # SHS 100x5
    shs1 = lookup_steel_section("SHS 100x5")
    assert shs1 is not None
    assert shs1["height_mm"] == 100.0
    assert shs1["width_mm"] == 100.0
    assert shs1["thickness_mm"] == 5.0

    # SHS 80x80x4
    shs2 = lookup_steel_section("VKR 80x80x4")
    assert shs2 is not None
    assert shs2["height_mm"] == 80.0
    assert shs2["width_mm"] == 80.0

    # RHS 160x80x6
    rhs = lookup_steel_section("RHS 160x80x6")
    assert rhs is not None
    assert rhs["height_mm"] == 160.0
    assert rhs["width_mm"] == 80.0
    assert rhs["thickness_mm"] == 6.0


def test_chs_pipe_lookup():
    chs = lookup_steel_section("PIPE 114.3x4.5")
    assert chs is not None
    assert chs["height_mm"] == 114.3
    assert chs["shape"] == "pipe"
    assert chs["thickness_mm"] == 4.5


def test_invalid_names():
    assert lookup_steel_section("") is None
    assert lookup_steel_section(None) is None
    assert lookup_steel_section("WALL_25") is None
    assert lookup_steel_section("RANDOM_TEXT_123") is None


def test_steel_dims_match_integration():
    sec = lookup_steel_section("HEA 240")
    # ETABS model has HEA 240 (240x230), CAD has 240x230
    assert _dims_match(sec["width_mm"], sec["height_mm"], 240.0, 230.0, 5.0) is True
    # Flipped
    assert _dims_match(sec["width_mm"], sec["height_mm"], 230.0, 240.0, 5.0) is True
