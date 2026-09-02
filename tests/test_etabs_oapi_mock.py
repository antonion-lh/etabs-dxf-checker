"""
tests/test_etabs_oapi_mock.py
-----------------------------
Unit tests verifying Phase 1 ETABS OAPI extraction logic using an in-memory
mock of the CSI ETABS v23 SapModel interface.
Tests all shape types, section definitions, area classification, and plastic hinges.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase1_etabs import (
    _bulk_points,
    _section_dims_from_definition,
    _shell_thickness_and_material,
    _extract_frames,
    _extract_areas,
    _extract_hinges,
    _extract_materials,
    _extract_load_patterns,
    _extract_area_loads,
    _extract_frame_loads,
    _extract_restraints,
    _SectionCache,
    _SHAPE_RECT,
    _SHAPE_CIRCLE,
    _SHAPE_BOX,
    _SHAPE_PIPE,
    _SHAPE_I,
    _SHAPE_CHANNEL,
    _SHAPE_T,
)
from phase3_validation import run_structural_sanity_checks

class MockPointObj:
    def GetAllPoints(self):
        names = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8"]
        xs = [0.0, 0.0, 6.0, 6.0, 0.0, 0.0, 3.0, 3.0]
        ys = [0.0, 0.0, 0.0, 0.0, 3.0, 5.5, 0.0, 0.0]
        zs = [0.0, 3.2, 0.0, 3.2, 0.0, 3.2, 3.2, 3.2]
        return (0, len(names), names, xs, ys, zs, "GLOBAL")

    def GetRestraint(self, name):
        if name in ("J1", "J3", "J5"):
            return (0, [True, True, True, True, True, True])  # Fixed
        elif name == "J7":
            return (0, [True, True, True, False, False, False]) # Pinned
        return (0, [False, False, False, False, False, False]) # Free

class MockPropMaterial:
    def GetNameList(self):
        return (0, 3, ["C30/37", "B500B", "S355"])

    def GetMaterial(self, name):
        mapping = {"C30/37": 2, "B500B": 6, "S355": 1}
        return (0, mapping.get(name, 2), 0, "", "")

    def GetMPIsotropic(self, name):
        mapping = {"C30/37": 33000000.0, "B500B": 200000000.0, "S355": 210000000.0}
        return (0, mapping.get(name, 30000000.0), 0.2, 0.0, 0.0)

    def GetOConcrete_1(self, name):
        return (0, 30000.0, False, 1.0, 1, 1, 0.002, 0.0035, 0.0, 0.0)

    def GetOSteel_1(self, name):
        return (0, 355000.0, 510000.0, 355000.0, 510000.0, 1, 1, 0.02, 0.15, 0.20, 0.0)

class MockLoadPatterns:
    def GetNameList(self):
        return (0, 3, ["DEAD", "SDL", "LIVE"])

    def GetLoadType(self, name):
        mapping = {"DEAD": 1, "SDL": 2, "LIVE": 3}
        return (0, mapping.get(name, 1))

    def GetSelfWTMultiplier(self, name):
        return (0, 1.0 if name == "DEAD" else 0.0)

class MockPropFrame:
    def GetSectionType(self, name):
        mapping = {
            "COL_RECT": (0, _SHAPE_RECT),
            "COL_CIRC": (0, _SHAPE_CIRCLE),
            "BM_I":     (0, _SHAPE_I),
            "TUBE_BOX": (0, _SHAPE_BOX),
            "PIPE_CHS": (0, _SHAPE_PIPE),
            "CHAN_SEC": (0, _SHAPE_CHANNEL),
            "T_BEAM":   (0, _SHAPE_T),
        }
        return mapping.get(name, (-1, -1))

    def GetRectangle(self, name):
        # (ret, FileName, MatProp, t3, t2, Color, Notes, GUID)
        # t3 = depth (h), t2 = width (b)
        return (0, "", "C30/37", 0.50, 0.40, 0, "", "")

    def GetCircle(self, name):
        # (ret, FileName, MatProp, t3, Color, Notes, GUID)
        return (0, "", "C30/37", 0.45, 0, "", "")

    def GetTube(self, name):
        # (ret, FileName, MatProp, t3, t2, tf, tw, Color, Notes, GUID)
        return (0, "", "S355", 0.30, 0.20, 0.01, 0.01, 0, "", "")

    def GetPipe(self, name):
        # (ret, FileName, MatProp, t3, tw, Color, Notes, GUID)
        return (0, "", "S355", 0.25, 0.008, 0, "", "")

    def GetISection(self, name):
        # (ret, FileName, MatProp, t3, t2, tf, tw, t2b, tfb, Color, Notes, GUID)
        return (0, "", "S355", 0.40, 0.18, 0.012, 0.008, 0.18, 0.012, 0, "", "")

    def GetChannel(self, name):
        return (0, "", "S355", 0.20, 0.08, 0.009, 0.006, 0, "", "")

    def GetTSection(self, name):
        return (0, "", "C30/37", 0.50, 0.30, 0.10, 0.08, 0.30, 0.10, 0, "", "")

    def GetMaterial(self, name):
        return (0, "C30/37")

class MockPropArea:
    def GetShell_1(self, name):
        # (ret, ShellType, bIncludeDrillingDOF, MatPropName, MatAngle, Thickness, Bending12f, Color, Notes, GUID)
        return (0, 1, True, "C30/37", 0.0, 0.25, 1.0, 0, "", "")

class MockFrameObj:
    def GetNameList(self):
        return (0, 3, ["C1", "C2", "B101"])

    def GetDesignOrientation(self, name):
        # 1=Column, 2=Beam, 3=Brace
        return (0, 1 if name.startswith("C") else 2)

    def GetPoints(self, name):
        mapping = {
            "C1": (0, "J1", "J2"),
            "C2": (0, "J3", "J4"),
            "B101": (0, "J2", "J4"),
        }
        return mapping[name]

    def GetSection(self, name):
        mapping = {
            "C1": (0, "COL_RECT", 0),
            "C2": (0, "COL_CIRC", 0),
            "B101": (0, "BM_I", 0),
        }
        return mapping[name]

    def GetHingeAssigns(self, name):
        if name == "C1":
            # (ret, n_h, hinge_props, rel_dists, my_types, ids)
            return (0, 2, ["P-M2-M3_Auto", "P-M2-M3_Auto"], [0.05, 0.95], [3, 3], [1, 2])
        return (0, 0, [], [], [], [])

    def GetLoadDistributed(self, name):
        if name == "B101":
            return (0, 1, ["B101"], ["SDL"], [1], ["GLOBAL"], [10], [0.0], [1.0], [0.0], [6.0], [4.5], [4.5])
        return (0, 0, [], [], [], [], [], [], [], [], [], [], [])

class MockAreaObj:
    def GetNameList(self):
        return (0, 2, ["W1", "S1"])

    def GetDesignOrientation(self, name):
        # 1=Wall, 2=Floor/Slab
        return (0, 1 if name == "W1" else 2)

    def GetPoints(self, name):
        mapping = {
            "W1": (0, 4, ["J1", "J5", "J6", "J2"]),
            "S1": (0, 4, ["J2", "J4", "J8", "J7"]),
        }
        return mapping[name]

    def GetProperty(self, name):
        return (0, "WALL_25" if name == "W1" else "SLAB_25")

    def GetLoadUniform(self, name):
        if name == "S1":
            return (0, 2, ["S1", "S1"], ["SDL", "LIVE"], ["GLOBAL", "GLOBAL"], [3, 3], [2.0, 3.0])
        return (0, 0, [], [], [], [], [])

class MockSapModel:
    def __init__(self):
        self.PointObj = MockPointObj()
        self.FrameObj = MockFrameObj()
        self.AreaObj = MockAreaObj()
        self.PropFrame = MockPropFrame()
        self.PropArea = MockPropArea()
        self.PropMaterial = MockPropMaterial()
        self.LoadPatterns = MockLoadPatterns()

@pytest.fixture
def mock_sap():
    return MockSapModel()

# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_bulk_points(mock_sap):
    pts = _bulk_points(mock_sap)
    assert len(pts) == 8
    assert pts["J1"] == (0.0, 0.0, 0.0)
    assert pts["J2"] == (0.0, 0.0, 3.2)

def test_section_dims_rectangular(mock_sap):
    dims = _section_dims_from_definition(mock_sap, "COL_RECT")
    assert dims["shape_type"] == "rectangular"
    assert dims["width_mm"] == 400
    assert dims["height_mm"] == 500

def test_section_dims_circular(mock_sap):
    dims = _section_dims_from_definition(mock_sap, "COL_CIRC")
    assert dims["shape_type"] == "circular"
    assert dims["diameter_mm"] == 450

def test_section_dims_tube_and_pipe(mock_sap):
    dims_tube = _section_dims_from_definition(mock_sap, "TUBE_BOX")
    assert dims_tube["shape_type"] == "box"
    assert dims_tube["width_mm"] == 200
    assert dims_tube["height_mm"] == 300

    dims_pipe = _section_dims_from_definition(mock_sap, "PIPE_CHS")
    assert dims_pipe["shape_type"] == "pipe"
    assert dims_pipe["diameter_mm"] == 250

def test_section_dims_i_channel_t(mock_sap):
    dims_i = _section_dims_from_definition(mock_sap, "BM_I")
    assert dims_i["shape_type"] == "I-section"
    assert dims_i["width_mm"] == 180
    assert dims_i["height_mm"] == 400

    dims_c = _section_dims_from_definition(mock_sap, "CHAN_SEC")
    assert dims_c["shape_type"] == "channel"
    assert dims_c["width_mm"] == 80
    assert dims_c["height_mm"] == 200

    dims_t = _section_dims_from_definition(mock_sap, "T_BEAM")
    assert dims_t["shape_type"] == "T-section"
    assert dims_t["width_mm"] == 300
    assert dims_t["height_mm"] == 500

def test_shell_thickness(mock_sap):
    t_mm, mat = _shell_thickness_and_material(mock_sap, "WALL_25")
    assert t_mm == 250
    assert mat == "C30/37"

def test_extract_frames_mock(mock_sap):
    pts = _bulk_points(mock_sap)
    cfg = Config()
    cache = _SectionCache(mock_sap, cfg)
    buckets = _extract_frames(mock_sap, pts, cache, cfg)

    assert len(buckets["columns"]) == 2
    assert len(buckets["beams"]) == 1
    assert buckets["columns"][0]["name"] == "C1"
    assert buckets["columns"][0]["width_mm"] == 400
    assert buckets["columns"][0]["height_mm"] == 500

def test_extract_areas_mock(mock_sap):
    pts = _bulk_points(mock_sap)
    cfg = Config()
    cache = _SectionCache(mock_sap, cfg)
    buckets = _extract_areas(mock_sap, pts, cache, cfg)

    assert len(buckets["walls"]) == 1
    assert len(buckets["slabs"]) == 1
    assert buckets["walls"][0]["name"] == "W1"
    assert buckets["walls"][0]["thickness_mm"] == 250
    assert buckets["slabs"][0]["name"] == "S1"
    assert buckets["slabs"][0]["thickness_mm"] == 250

def test_extract_hinges_mock(mock_sap):
    cfg = Config(report_hinges=True)
    hinges = _extract_hinges(mock_sap, cfg)

    assert len(hinges) == 2
    assert hinges[0]["frame_name"] == "C1"
    assert hinges[0]["hinge_prop"] == "P-M2-M3_Auto"
    assert hinges[0]["rel_dist"] == 0.05
    assert hinges[0]["dof"] == "P"

def test_extract_materials_mock(mock_sap):
    cfg = Config(audit_materials=True)
    mats = _extract_materials(mock_sap, cfg)
    assert len(mats) == 3
    conc = next(m for m in mats if m["name"] == "C30/37")
    assert conc["type"] == "Concrete"
    assert conc["E_gpa"] == 33.0
    assert conc["fc_mpa"] == 30.0
    steel = next(m for m in mats if m["name"] == "S355")
    assert steel["type"] == "Steel"
    assert steel["fy_mpa"] == 355.0

def test_extract_load_patterns_mock(mock_sap):
    cfg = Config(audit_loads=True)
    pats = _extract_load_patterns(mock_sap, cfg)
    assert len(pats) == 3
    dead = next(p for p in pats if p["name"] == "DEAD")
    assert dead["self_weight_mult"] == 1.0
    live = next(p for p in pats if p["name"] == "LIVE")
    assert live["self_weight_mult"] == 0.0

def test_extract_area_loads_mock(mock_sap):
    cfg = Config(audit_loads=True)
    slabs = [{"name": "S1", "centroid_x": 3.0, "centroid_y": 3.0}]
    loads = _extract_area_loads(mock_sap, slabs, cfg)
    assert len(loads) == 2
    assert loads[0]["load_pattern"] == "SDL"
    assert loads[0]["val_kpa"] == 2.0
    assert loads[1]["load_pattern"] == "LIVE"
    assert loads[1]["val_kpa"] == 3.0

def test_extract_frame_loads_mock(mock_sap):
    cfg = Config(audit_loads=True)
    beams = [{"name": "B101"}]
    loads = _extract_frame_loads(mock_sap, beams, cfg)
    assert len(loads) == 1
    assert loads[0]["load_pattern"] == "SDL"
    assert loads[0]["val1_kn_m"] == 4.5

def test_extract_restraints_mock(mock_sap):
    cfg = Config(audit_restraints=True)
    pt_coords = _bulk_points(mock_sap)
    rest = _extract_restraints(mock_sap, pt_coords, cfg)
    assert len(rest) == 3
    assert all(r["is_supported"] for r in rest)
    j1 = next(r for r in rest if r["joint_name"] == "J1")
    assert j1["restraint_type"] == "Fixed"

def test_structural_sanity_checks_mock():
    import pandas as pd
    cfg = Config()
    bad_etabs = {
        "load_patterns": pd.DataFrame([
            {"name": "DEAD", "type": "Dead", "self_weight_mult": 0.0},
            {"name": "LIVE", "type": "Live", "self_weight_mult": 1.0},
        ]),
        "restraints": pd.DataFrame([
            {"joint_name": "J_FLOATING", "x": 0.0, "y": 0.0, "z": 0.0, "restraint_type": "FREE"},
        ]),
        "slabs": pd.DataFrame([
            {"name": "SLAB_EMPTY"},
        ]),
        "area_loads": pd.DataFrame(columns=["area_name", "load_pattern", "val_kpa"])
    }
    alerts = run_structural_sanity_checks(bad_etabs, cfg)
    assert len(alerts) == 4
    categories = [a["category"] for a in alerts]
    assert "Load Pattern" in categories
    assert "Support" in categories
    assert "Area Load" in categories
