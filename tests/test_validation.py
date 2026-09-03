"""
tests/test_validation.py
------------------------
Unit tests for Phase 3 validation engine.
All tests use synthetic DataFrames — no ETABS or DXF files needed.
"""

import sys
import os
import math
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase3_validation import validate, Status, _dims_match, run_structural_sanity_checks


# ---------------------------------------------------------------------------
# Helpers: synthetic DataFrames
# ---------------------------------------------------------------------------

def _etabs_row(name, x, y, z_bot=0.0, z_top=3.0, section="C30x50", w=300.0, h=500.0):
    return {
        "name": name, "x_bot": x, "y_bot": y,
        "z_bot": z_bot, "z_top": z_top,
        "section": section, "material": "C30/37",
        "section_w_mm": w, "section_h_mm": h,
    }


def _dxf_row(x, y, dim="30x50", w=300.0, h=500.0, grid="A1"):
    return {
        "centroid_x_m": x, "centroid_y_m": y,
        "dim_text": dim, "width_mm": w, "height_mm": h,
        "grid_ref": grid,
    }


def _df_e(*rows): return pd.DataFrame(rows)
def _df_d(*rows): return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests: dimension matching helper
# ---------------------------------------------------------------------------

class TestDimsMatch:

    def test_exact_match(self):
        assert _dims_match(300, 500, 300, 500, 5.0)

    def test_within_tolerance(self):
        assert _dims_match(300, 500, 302, 498, 5.0)

    def test_outside_tolerance(self):
        assert not _dims_match(300, 500, 310, 490, 5.0)

    def test_flipped_orientation(self):
        # 300×500 should match 500×300
        assert _dims_match(300, 500, 500, 300, 5.0)

    def test_none_dimensions_no_mismatch(self):
        # Missing data → can't call mismatch
        assert _dims_match(None, None, 300, 500, 5.0)
        assert _dims_match(300, 500, None, None, 5.0)


# ---------------------------------------------------------------------------
# Tests: spatial matching
# ---------------------------------------------------------------------------

class TestValidate:

    def test_perfect_match(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d(_dxf_row(1.0, 2.0))
        cfg  = Config(spatial_tolerance=0.15)
        res  = validate(df_e, df_d, cfg)
        assert len(res) == 1
        assert res.iloc[0]["status"] == Status.MATCH

    def test_within_tolerance_match(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d(_dxf_row(1.10, 2.10))  # 0.141 m away
        cfg  = Config(spatial_tolerance=0.15)
        res  = validate(df_e, df_d, cfg)
        assert res.iloc[0]["status"] == Status.MATCH

    def test_outside_tolerance_etabs_only(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d(_dxf_row(1.5, 2.5))  # 0.707 m away — too far
        cfg  = Config(spatial_tolerance=0.15)
        res  = validate(df_e, df_d, cfg)
        # C1 → ETABS_ONLY; DXF row → DXF_ONLY
        statuses = set(res["status"].tolist())
        assert Status.ETABS_ONLY in statuses
        assert Status.DXF_ONLY   in statuses

    def test_section_mismatch_detected(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0, section="C30x50", w=300, h=500))
        df_d = _df_d(_dxf_row(1.0, 2.0, dim="30x70", w=300, h=700))
        cfg  = Config(spatial_tolerance=0.15, section_tolerance_mm=5.0)
        res  = validate(df_e, df_d, cfg)
        assert res.iloc[0]["status"] == Status.SECTION_MISMATCH

    def test_section_mismatch_notes_populated(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0, w=300, h=500))
        df_d = _df_d(_dxf_row(1.0, 2.0, w=300, h=700))
        res  = validate(df_e, df_d, Config())
        notes = res.iloc[0]["notes"]
        assert "300" in notes or "500" in notes or "700" in notes

    def test_dxf_only_detected(self):
        df_e = _df_e()  # empty
        df_d = _df_d(_dxf_row(1.0, 2.0))
        res  = validate(df_e, df_d, Config())
        assert len(res) == 1
        assert res.iloc[0]["status"] == Status.DXF_ONLY

    def test_etabs_only_detected(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d()  # empty
        res  = validate(df_e, df_d, Config())
        assert len(res) == 1
        assert res.iloc[0]["status"] == Status.ETABS_ONLY

    def test_both_empty(self):
        res = validate(pd.DataFrame(), pd.DataFrame(), Config())
        assert res.empty or len(res) == 0

    def test_multiple_columns(self):
        df_e = _df_e(
            _etabs_row("C1", 0.0, 0.0),
            _etabs_row("C2", 5.0, 5.0),
            _etabs_row("C3", 10.0, 0.0),
        )
        df_d = _df_d(
            _dxf_row(0.0, 0.0),   # matches C1
            _dxf_row(5.05, 5.05), # matches C2 (within 0.07 m)
            _dxf_row(20.0, 0.0),  # no match
        )
        cfg = Config(spatial_tolerance=0.15)
        res = validate(df_e, df_d, cfg)

        counts = res["status"].value_counts()
        assert counts.get(Status.MATCH, 0) >= 2
        assert counts.get(Status.ETABS_ONLY, 0) >= 1  # C3
        assert counts.get(Status.DXF_ONLY, 0) >= 1    # the (20, 0) point

    def test_result_has_required_columns(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d(_dxf_row(1.0, 2.0))
        res  = validate(df_e, df_d, Config())
        required = [
            "status", "etabs_name", "etabs_x", "etabs_y",
            "etabs_section", "dxf_dim_text", "dxf_x", "dxf_y",
            "xy_dist_m", "notes",
        ]
        for col in required:
            assert col in res.columns, f"Missing column: {col}"

    def test_xy_dist_recorded(self):
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0))
        df_d = _df_d(_dxf_row(1.1, 2.1))
        res  = validate(df_e, df_d, Config(spatial_tolerance=0.2))
        dist = res.iloc[0]["xy_dist_m"]
        expected = math.sqrt(0.01 + 0.01)
        assert abs(dist - expected) < 0.01

    def test_flipped_section_dimensions_still_match(self):
        # ETABS 300×500, DXF 500×300 — should still be MATCH
        df_e = _df_e(_etabs_row("C1", 1.0, 2.0, w=300, h=500))
        df_d = _df_d(_dxf_row(1.0, 2.0, w=500, h=300))
        res  = validate(df_e, df_d, Config())
        assert res.iloc[0]["status"] == Status.MATCH


class TestMultiTypeValidation:

    def test_multi_type_dict_input(self):
        etabs_data = {
            "columns": pd.DataFrame([{
                "name": "C1", "element_type": "column", "x_match": 1.0, "y_match": 2.0,
                "section": "C30x50", "width_mm": 300.0, "height_mm": 500.0
            }]),
            "beams": pd.DataFrame([{
                "name": "B1", "element_type": "beam", "x_match": 5.0, "y_match": 2.0,
                "section": "B25x40", "width_mm": 250.0, "height_mm": 400.0
            }]),
            "walls": pd.DataFrame([{
                "name": "W1", "element_type": "wall", "x_match": 8.0, "y_match": 5.0,
                "prop_name": "W20", "thickness_mm": 200.0, "height_mm": 200.0
            }]),
            "slabs": pd.DataFrame([{
                "name": "S1", "element_type": "slab", "x_match": 12.0, "y_match": 12.0,
                "prop_name": "S18", "thickness_mm": 180.0, "height_mm": 180.0
            }]),
            "hinges": pd.DataFrame([{
                "frame_name": "C1", "hinge_prop": "M3_Auto", "rel_dist": 0.05, "dof": "M3"
            }])
        }
        df_dxf = pd.DataFrame([
            {"element_type": "column", "centroid_x_m": 1.0, "centroid_y_m": 2.0, "dim_text": "30x50", "dim1_mm": 300.0, "dim2_mm": 500.0},
            {"element_type": "beam", "centroid_x_m": 5.0, "centroid_y_m": 2.0, "dim_text": "25x40", "dim1_mm": 250.0, "dim2_mm": 400.0},
            {"element_type": "wall", "centroid_x_m": 8.0, "centroid_y_m": 5.0, "dim_text": "t=20", "dim1_mm": 200.0, "dim2_mm": 200.0},
            {"element_type": "slab", "centroid_x_m": 12.0, "centroid_y_m": 12.0, "dim_text": "d=18", "dim1_mm": 180.0, "dim2_mm": 180.0},
        ])

        cfg = Config()
        res = validate(etabs_data, df_dxf, cfg)

        assert len(res) == 4
        assert set(res["status"].tolist()) == {Status.MATCH}
        assert set(res["element_type"].tolist()) == {"column", "beam", "wall", "slab"}

        # Check hinge was merged onto C1
        c1_row = res[res["etabs_name"] == "C1"].iloc[0]
        assert bool(c1_row["has_hinges"]) is True
        assert c1_row["hinge_count"] == 1
        assert "M3_Auto" in c1_row["hinge_details"]

    def test_different_tolerances_for_frame_and_area(self):
        # Beam with distance 0.18m (fails frame tol 0.15m -> ETABS_ONLY)
        # Wall with distance 0.25m (passes area tol 0.30m -> MATCH)
        etabs_data = {
            "beams": pd.DataFrame([{
                "name": "B1", "element_type": "beam", "x_match": 5.0, "y_match": 2.0,
                "section": "B25x40", "width_mm": 250.0, "height_mm": 400.0
            }]),
            "walls": pd.DataFrame([{
                "name": "W1", "element_type": "wall", "x_match": 8.0, "y_match": 5.0,
                "prop_name": "W20", "thickness_mm": 200.0, "height_mm": 200.0
            }])
        }
        df_dxf = pd.DataFrame([
            {"element_type": "beam", "centroid_x_m": 5.18, "centroid_y_m": 2.0, "dim_text": "25x40", "dim1_mm": 250.0, "dim2_mm": 400.0},
            {"element_type": "wall", "centroid_x_m": 8.25, "centroid_y_m": 5.0, "dim_text": "t=20", "dim1_mm": 200.0, "dim2_mm": 200.0},
        ])
        cfg = Config(spatial_tolerance_frame=0.15, spatial_tolerance_area=0.30)
        res = validate(etabs_data, df_dxf, cfg)

        b1_status = res[res["etabs_name"] == "B1"]["status"].iloc[0]
        w1_status = res[res["etabs_name"] == "W1"]["status"].iloc[0]
        assert b1_status == Status.ETABS_ONLY
        assert w1_status == Status.MATCH

    def test_validate_with_none_inputs(self):
        res = validate(None, None)
        assert isinstance(res, pd.DataFrame)
        assert res.empty

    def test_run_structural_sanity_checks_with_none(self):
        alerts = run_structural_sanity_checks(None)
        assert alerts == []

    def test_run_structural_sanity_checks_grouped_alerts(self):
        # 10 unloaded slabs should be grouped into a single summary alert
        mock_e2k = {
            "slabs": pd.DataFrame([{"name": f"F_{i}"} for i in range(10)]),
            "area_loads": pd.DataFrame(),
            "restraints": pd.DataFrame([{"joint_name": f"J_{i}", "restraint_type": "FREE", "x": i, "y": 0} for i in range(10)])
        }
        alerts = run_structural_sanity_checks(mock_e2k)
        assert len(alerts) == 2  # 1 for grouped slabs, 1 for grouped free joints
        assert "10 stropnih ploča" in alerts[1]["element"]
        assert "10 čvorova baze" in alerts[0]["element"]


