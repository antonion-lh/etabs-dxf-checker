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

def test_curriculum_audit_detects_elevated_restraint():
    mock_e2k = {
        "restraints": pd.DataFrame([
            {"joint_name": "1", "z": 0.0},
            {"joint_name": "101", "z": 3.5},
        ])
    }
    checks = run_curriculum_audit(mock_e2k)
    c20 = next(c for c in checks if c["num"] == 20)
    assert c20["status"] == "FAIL"
    assert "101" in c20["finding"]

def test_curriculum_audit_detects_envelope_in_design():
    mock_e2k = {
        "load_combinations": {"COMBO_ENVELOPE": {}}
    }
    checks = run_curriculum_audit(mock_e2k)
    c22 = next(c for c in checks if c["num"] == 22)
    assert c22["status"] == "WARNING"

def test_curriculum_audit_detects_unassigned_piers():
    mock_e2k = {
        "piers": ["P1", "P2"],
        "pier_assigns": {}
    }
    checks = run_curriculum_audit(mock_e2k)
    c25 = next(c for c in checks if c["num"] == 25)
    assert c25["status"] == "WARNING"
    assert "P1" in c25["finding"]

def test_curriculum_audit_calculates_hand_mass():
    mock_e2k = {
        "all_points": {"1": (0, 0, 0), "2": (20, 10, 12)},
        "stories": [{"name": "Story1"}, {"name": "Story2"}, {"name": "Story3"}],
    }
    checks = run_curriculum_audit(mock_e2k)
    c30 = next(c for c in checks if c["num"] == 30)
    assert c30["status"] == "PASS"
    assert "kN" in c30["finding"]

def test_curriculum_audit_calculates_wall_ratio():
    mock_e2k = {
        "all_points": {"1": (0, 0, 0), "2": (20, 10, 0)},
        "walls": pd.DataFrame([
            {"name": "W1", "story": "Story2", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 0, "thickness_mm": 300, "is_opening": False},
            {"name": "W2", "story": "Story2", "x_start": 0, "y_start": 0, "x_end": 0, "y_end": 10, "thickness_mm": 300, "is_opening": False},
        ])
    }
    checks = run_curriculum_audit(mock_e2k)
    c31 = next(c for c in checks if c["num"] == 31)
    assert c31["status"] in ("PASS", "WARNING")
    assert "Awx" in c31["finding"]
    assert "Awy" in c31["finding"]

def test_curriculum_audit_modal_modes():
    mock_few_modes = {
        "modal_cases": [{"name": "Modal", "max_modes": 12, "type": "Modal - Eigen"}]
    }
    checks = run_curriculum_audit(mock_few_modes)
    c16 = next(c for c in checks if c["num"] == 16)
    assert c16["status"] == "WARNING"

    mock_many_modes = {
        "modal_cases": [{"name": "Modal", "max_modes": 30, "type": "Modal - Eigen"}]
    }
    checks2 = run_curriculum_audit(mock_many_modes)
    c16_pass = next(c for c in checks2 if c["num"] == 16)
    assert c16_pass["status"] == "PASS"

def test_curriculum_audit_strossmayer_phase1():
    e2k = parse_e2k("STROSSMAYER_2.e2k")
    checks = run_curriculum_audit(e2k)
    assert len(checks) == 27
    nums = [c["num"] for c in checks]
    for req in [16, 20, 22, 25, 30, 31, 32, 34, 51]:
        assert req in nums
