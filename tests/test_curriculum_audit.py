import pytest
import pandas as pd
from curriculum_audit import run_curriculum_audit, calculate_audit_score
from phase1_e2k import parse_e2k

def test_curriculum_audit_demo_skola():
    e2k = parse_e2k("demo_skola.e2k")
    checks = run_curriculum_audit(e2k)
    assert len(checks) >= 15
    check_nums = [c["num"] for c in checks]
    assert 1 in check_nums
    assert 2 in check_nums
    assert 6 in check_nums
    assert 14 in check_nums
    assert 15 in check_nums
    assert 27 in check_nums

    score = calculate_audit_score(checks)
    assert score["percentage"] >= 90.0
    assert score["grade"] == 5

def test_curriculum_audit_detects_american_mat():
    mock_e2k = {
        "materials": pd.DataFrame([{"name": "4000Psi"}]),
        "columns": pd.DataFrame(),
        "walls": pd.DataFrame(),
    }
    checks = run_curriculum_audit(mock_e2k)
    c6 = next(c for c in checks if c["num"] == 6)
    assert c6["status"] == "FAIL"

def test_curriculum_audit_detects_american_rebar():
    mock_e2k = {
        "rebars": [{"name": "Grade 60", "diameter_m": 0.016, "area_m2": 0.0002}],
    }
    checks = run_curriculum_audit(mock_e2k)
    c7 = next(c for c in checks if c["num"] == 7)
    assert c7["status"] == "FAIL"

def test_curriculum_audit_detects_diacritics():
    mock_e2k = {
        "columns": pd.DataFrame([{"name": "Stup_Prizemlje_Čvor1", "width_mm": 400, "height_mm": 400}]),
    }
    checks = run_curriculum_audit(mock_e2k)
    c2 = next(c for c in checks if c["num"] == 2)
    assert c2["status"] == "WARNING"

def test_curriculum_audit_detects_huge_dimension():
    mock_e2k = {
        "columns": pd.DataFrame([{"name": "C1", "width_mm": 40000, "height_mm": 400}]),
    }
    checks = run_curriculum_audit(mock_e2k)
    c2 = next(c for c in checks if c["num"] == 2)
    assert c2["status"] == "FAIL"

def test_curriculum_audit_detects_orphan_joints():
    mock_e2k = {
        "all_points": {"1": (0,0,0), "2": (1,0,0), "99": (5,5,5)},
        "used_points": {"1", "2"},
    }
    checks = run_curriculum_audit(mock_e2k)
    c27 = next(c for c in checks if c["num"] == 27)
    assert c27["status"] == "WARNING"
    assert "99" in c27["finding"]

def test_curriculum_audit_detects_podest():
    mock_e2k = {
        "stories": [
            {"name": "Story1", "height": 3.0, "elevation": 3.0},
            {"name": "Podest", "height": 1.4, "elevation": 4.4},
        ]
    }
    checks = run_curriculum_audit(mock_e2k)
    c3 = next(c for c in checks if c["num"] == 3)
    assert c3["status"] == "WARNING"
    assert "podest" in c3["finding"].lower()

def test_curriculum_audit_detects_thin_walls():
    mock_e2k = {
        "walls": pd.DataFrame([
            {"name": "W_PREGRADA", "thickness_mm": 100.0, "is_opening": False},
        ])
    }
    checks = run_curriculum_audit(mock_e2k)
    c9 = next(c for c in checks if c["num"] == 9)
    assert c9["status"] == "WARNING"

def test_calculate_audit_score_empty():
    res = calculate_audit_score([])
    assert res["percentage"] == 0.0
    assert res["grade"] == 0
