"""Regresijski testovi za robusnost pronadjenu tijekom sveobuhvatnog testiranja."""

import warnings

import pandas as pd


def _cfg():
    from config import Config
    return Config()


# --------------------------------------------------------------------------
# Bug #3: curriculum_audit mora raditi i kad materials/load_patterns/restraints/
# area_loads dodju kao LISTA (dictova) umjesto DataFrame-a.
# --------------------------------------------------------------------------
def test_audit_accepts_list_fields():
    from curriculum_audit import run_curriculum_audit, calculate_audit_score
    d = {
        "columns": pd.DataFrame(), "beams": pd.DataFrame(),
        "walls": pd.DataFrame(), "slabs": pd.DataFrame(), "stories": [],
        "materials": [{"name": "BETON C30/37"}, {"name": "OPEKA"}],
        "load_patterns": [{"name": "DEAD"}],
        "restraints": [], "area_loads": [],
    }
    audit = run_curriculum_audit(d)  # ne smije baciti
    score = calculate_audit_score(audit)
    assert "grade" in score and "percentage" in score
    assert len(audit) > 0


def test_audit_empty_all_dataframes():
    from curriculum_audit import run_curriculum_audit, calculate_audit_score
    d = {
        "columns": pd.DataFrame(), "beams": pd.DataFrame(),
        "walls": pd.DataFrame(), "slabs": pd.DataFrame(), "stories": [],
        "materials": pd.DataFrame(), "load_patterns": pd.DataFrame(),
        "restraints": pd.DataFrame(), "area_loads": pd.DataFrame(),
    }
    audit = run_curriculum_audit(d)
    assert calculate_audit_score(audit)["grade"] in (1, 2, 3, 4, 5)


# --------------------------------------------------------------------------
# Bug #4: generate_html ne smije baciti KeyError ako df nema element_type kolonu.
# --------------------------------------------------------------------------
def test_generate_html_df_without_element_type():
    from report import generate_html
    html = generate_html(pd.DataFrame({"x": [1, 2]}), None, _cfg())
    assert isinstance(html, str) and len(html) > 0


def test_generate_html_empty_df():
    from report import generate_html
    html = generate_html(pd.DataFrame(), None, _cfg())
    assert isinstance(html, str) and len(html) > 0


# --------------------------------------------------------------------------
# Bug #1: _make_overlay (Image.fromarray bez deprecated mode=) mora raditi.
# --------------------------------------------------------------------------
def test_make_overlay_no_deprecated_mode():
    import numpy as np
    import raster_vectorize as r
    gray = np.full((60, 80), 255, dtype=np.uint8)
    png = r._make_overlay(gray, [((0, 0), (70, 0)), ((10, 5), (10, 55))])
    assert isinstance(png, bytes) and len(png) > 0
