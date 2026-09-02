import pytest
import pandas as pd
from curriculum_audit import run_curriculum_audit
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
    assert 27 in check_nums

def test_curriculum_audit_detects_american_mat():
    mock_e2k = {
        "materials": pd.DataFrame([{"name": "4000Psi"}]),
        "columns": pd.DataFrame(),
        "walls": pd.DataFrame(),
    }
    checks = run_curriculum_audit(mock_e2k)
    c6 = next(c for c in checks if c["num"] == 6)
    assert c6["status"] == "FAIL"

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
