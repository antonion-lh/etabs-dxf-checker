"""
tests/test_report.py
--------------------
Tests for HTML and PDF report generation.
"""

import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase3_validation import Status
from report import generate_html, generate_pdf, generate_reports


@pytest.fixture
def sample_validation_df():
    return pd.DataFrame([
        {
            "element_type": "column",
            "status": Status.MATCH,
            "etabs_name": "C1",
            "etabs_x": 1.0,
            "etabs_y": 2.0,
            "etabs_z": 0.0,
            "etabs_section": "C30x50",
            "etabs_material": "C30/37",
            "etabs_shape": "rectangular",
            "etabs_w_mm": 300.0,
            "etabs_h_mm": 500.0,
            "etabs_d_mm": None,
            "has_hinges": True,
            "hinge_count": 2,
            "hinge_details": "M3_Auto@0.05; M3_Auto@0.95",
            "dxf_dim_text": "30x50",
            "dxf_x": 1.02,
            "dxf_y": 2.01,
            "dxf_d1_mm": 300.0,
            "dxf_d2_mm": 500.0,
            "floor_label": "FLOOR_1",
            "grid_ref": "A-1",
            "xy_dist_m": 0.0224,
            "notes": "",
        },
        {
            "element_type": "beam",
            "status": Status.SECTION_MISMATCH,
            "etabs_name": "B12",
            "etabs_x": 4.5,
            "etabs_y": 2.0,
            "etabs_z": 3.2,
            "etabs_section": "B25x40",
            "etabs_material": "C25/30",
            "etabs_shape": "rectangular",
            "etabs_w_mm": 250.0,
            "etabs_h_mm": 400.0,
            "etabs_d_mm": None,
            "has_hinges": False,
            "hinge_count": 0,
            "hinge_details": "",
            "dxf_dim_text": "25x50",
            "dxf_x": 4.51,
            "dxf_y": 2.0,
            "dxf_d1_mm": 250.0,
            "dxf_d2_mm": 500.0,
            "floor_label": "FLOOR_1",
            "grid_ref": "B-2",
            "xy_dist_m": 0.010,
            "notes": "ETABS: 250x400 mm | DXF: 250x500 mm",
        },
        {
            "element_type": "wall",
            "status": Status.MATCH,
            "etabs_name": "W1",
            "etabs_x": 8.0,
            "etabs_y": 5.0,
            "etabs_z": 0.0,
            "etabs_section": "W20",
            "etabs_material": "C30/37",
            "etabs_shape": "shell",
            "etabs_w_mm": None,
            "etabs_h_mm": 200.0,
            "etabs_d_mm": None,
            "has_hinges": False,
            "hinge_count": 0,
            "hinge_details": "",
            "dxf_dim_text": "t=20",
            "dxf_x": 8.05,
            "dxf_y": 5.0,
            "dxf_d1_mm": 200.0,
            "dxf_d2_mm": 200.0,
            "floor_label": "FLOOR_1",
            "grid_ref": "C-1",
            "xy_dist_m": 0.05,
            "notes": "",
        },
        {
            "element_type": "slab",
            "status": Status.MATCH,
            "etabs_name": "S1",
            "etabs_x": 10.0,
            "etabs_y": 10.0,
            "etabs_z": 3.2,
            "etabs_section": "S18",
            "etabs_material": "C30/37",
            "etabs_shape": "shell",
            "etabs_w_mm": None,
            "etabs_h_mm": 180.0,
            "etabs_d_mm": None,
            "has_hinges": False,
            "hinge_count": 0,
            "hinge_details": "",
            "dxf_dim_text": "d=18",
            "dxf_x": 10.0,
            "dxf_y": 10.0,
            "dxf_d1_mm": 180.0,
            "dxf_d2_mm": 180.0,
            "floor_label": "FLOOR_1",
            "grid_ref": "",
            "xy_dist_m": 0.0,
            "notes": "",
        },
    ])


def test_generate_html(sample_validation_df, tmp_path):
    out_html = tmp_path / "test_report.html"
    cfg = Config(project_name="Unit Test Project")
    html_content = generate_html(sample_validation_df, str(out_html), cfg)
    
    assert out_html.exists()
    assert len(html_content) > 0
    assert "Unit Test Project" in html_content
    assert "C1" in html_content
    assert "B12" in html_content
    assert "M3_Auto@0.05" in html_content


def test_generate_pdf(sample_validation_df, tmp_path):
    out_html = tmp_path / "test_report.html"
    out_pdf = tmp_path / "test_report.pdf"
    cfg = Config(project_name="Unit Test Project")
    html_content = generate_html(sample_validation_df, str(out_html), cfg)
    
    success = generate_pdf(html_content, str(out_pdf))
    assert success is True
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0


def test_generate_reports_integration(sample_validation_df, tmp_path):
    out_html = tmp_path / "combined_report.html"
    out_pdf = tmp_path / "combined_report.pdf"
    cfg = Config(
        produce_html=True,
        produce_pdf=True,
        html_output=str(out_html),
        pdf_output=str(out_pdf),
    )
    generate_reports(sample_validation_df, cfg)
    assert out_html.exists()
    assert out_pdf.exists()
