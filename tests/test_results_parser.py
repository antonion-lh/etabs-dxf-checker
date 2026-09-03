"""
tests/test_results_parser.py
----------------------------
Unit tests for optional ETABS analysis results parsing and Phase 2 curriculum audit rules.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase1_e2k import parse_e2k
from results_parser import parse_etabs_results, create_demo_etabs_results
from curriculum_audit import run_curriculum_audit, calculate_audit_score

TRNSKO_E2K = os.path.join(os.path.dirname(__file__), "..", "trnsko_model.e2k")


def test_results_parser_empty():
    """Verify handling of empty or non-results data."""
    res = parse_etabs_results(b"")
    assert res["has_results"] is False
    assert res["summary"]["max_drift_overall"] == 0.0


def test_results_parser_demo():
    """Verify extraction from synthetic demo ETABS Excel workbook."""
    e2k_data = parse_e2k(TRNSKO_E2K) if os.path.exists(TRNSKO_E2K) else {}
    demo_bytes = create_demo_etabs_results(e2k_data)
    res = parse_etabs_results(demo_bytes)

    assert res["has_results"] is True
    s = res["summary"]
    assert s["max_drift_overall"] > 0.0
    assert s["base_shear_x_kn"] > 0.0
    assert s["max_fz_kn"] > 0.0
    assert s["has_soil_uplift"] is False
    assert s["max_pmm_ratio"] > 0.0


def test_curriculum_audit_without_results():
    """Verify that Points 18, 28, 29, 33, 35, 36, 40 are INFO with weight=0 when results are omitted."""
    e2k_data = parse_e2k(TRNSKO_E2K) if os.path.exists(TRNSKO_E2K) else {}
    checks = run_curriculum_audit(e2k_data, results_data=None)

    by_num = {c["num"]: c for c in checks}
    for p in [18, 28, 29, 33, 35, 36, 40]:
        assert by_num[p]["status"] == "INFO"
        assert by_num[p]["weight"] == 0

    score = calculate_audit_score(checks)
    assert score["percentage"] > 0.0


def test_curriculum_audit_with_results():
    """Verify that Points 18, 28, 29, 33, 35, 36, 40 become PASS/WARNING with positive weight when results are supplied."""
    e2k_data = parse_e2k(TRNSKO_E2K) if os.path.exists(TRNSKO_E2K) else {}
    demo_bytes = create_demo_etabs_results(e2k_data)
    res = parse_etabs_results(demo_bytes)

    checks = run_curriculum_audit(e2k_data, results_data=res)
    by_num = {c["num"]: c for c in checks}

    for p in [18, 28, 29, 33, 35, 36, 40]:
        assert by_num[p]["status"] in ("PASS", "WARNING")
        assert by_num[p]["weight"] > 0
