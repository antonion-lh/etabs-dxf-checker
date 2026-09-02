"""
tests/test_e2k_parser.py
------------------------
Unit tests for the ETABS .e2k text file parser (phase1_e2k.py).
Verifies parsing of points, materials, frame sections, area sections,
loads, restraints, and integration with phase3_validation.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status

SAMPLE_E2K = os.path.join(os.path.dirname(__file__), "..", "sample_building.e2k")
SAMPLE_DXF = os.path.join(os.path.dirname(__file__), "..", "sample_building.dxf")


def test_parse_e2k_structure():
    etabs_data = parse_e2k(SAMPLE_E2K)
    assert "columns" in etabs_data
    assert "beams" in etabs_data
    assert "walls" in etabs_data
    assert "slabs" in etabs_data
    assert "materials" in etabs_data
    assert "load_patterns" in etabs_data
    assert "area_loads" in etabs_data
    assert "frame_loads" in etabs_data
    assert "restraints" in etabs_data
    assert "hinges" in etabs_data

    # Check counts
    assert len(etabs_data["columns"]) == 4
    assert len(etabs_data["beams"]) == 1
    assert len(etabs_data["walls"]) == 1
    assert len(etabs_data["slabs"]) == 1
    assert len(etabs_data["hinges"]) == 2


def test_parse_e2k_dimensions():
    etabs_data = parse_e2k(SAMPLE_E2K)
    df_cols = etabs_data["columns"]

    c1 = df_cols[df_cols["name"] == "C1"].iloc[0]
    assert c1["width_mm"] == 400
    assert c1["height_mm"] == 500
    assert c1["material"] == "C30/37"

    c2 = df_cols[df_cols["name"] == "C2"].iloc[0]
    assert c2["diameter_mm"] == 450
    assert c2["shape_type"] == "circular"


def test_parse_e2k_materials():
    etabs_data = parse_e2k(SAMPLE_E2K)
    df_mats = etabs_data["materials"]

    c30 = df_mats[df_mats["name"] == "C30/37"].iloc[0]
    assert c30["type"] == "Concrete"
    assert c30["E_gpa"] == 33.0
    assert c30["fc_mpa"] == 30.0

    b500 = df_mats[df_mats["name"] == "B500B"].iloc[0]
    assert b500["type"] == "Rebar"
    assert b500["fy_mpa"] == 500.0


def test_parse_e2k_loads_and_restraints():
    etabs_data = parse_e2k(SAMPLE_E2K)
    df_pats = etabs_data["load_patterns"]
    df_aloads = etabs_data["area_loads"]
    df_rest = etabs_data["restraints"]

    dead = df_pats[df_pats["name"] == "DEAD"].iloc[0]
    assert dead["self_weight_mult"] == 1.0

    live = df_pats[df_pats["name"] == "LIVE"].iloc[0]
    assert live["self_weight_mult"] == 0.0

    assert len(df_aloads) == 2
    assert len(df_rest) == 5
    assert all(df_rest["restraint_type"] == "Fixed")


def test_e2k_validation_integration():
    cfg = Config(dxf_unit_scale=0.01)
    df_dxf = parse_dxf(SAMPLE_DXF, cfg)
    etabs_data = parse_e2k(SAMPLE_E2K, cfg)

    df_res = validate(etabs_data, df_dxf, cfg)
    assert not df_res.empty

    counts = df_res["status"].value_counts()
    assert counts.get(Status.MATCH, 0) >= 4
    assert counts.get(Status.SECTION_MISMATCH, 0) >= 1
