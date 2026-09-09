"""Testovi za model_compare.py — adapter ref-model->df_dxf + usporedba + sažetak."""
import os

import pandas as pd

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_dxf")
AB_ZGRADA = os.path.join(SAMPLE_DIR, "ab_zgrada.dxf")


# --------------------------------------------------------------------------
# Zadatak 2: adapter ref_model_to_dxf_table
# --------------------------------------------------------------------------
def test_adapter_exposes_api():
    import model_compare as mc
    assert hasattr(mc, "ref_model_to_dxf_table")
    assert hasattr(mc, "compare_models")
    assert hasattr(mc, "summarize_differences")


def test_adapter_produces_dxf_columns():
    import model_compare as mc
    model = {
        "columns": pd.DataFrame([
            {"name": "C1", "x_start": 1.0, "y_start": 2.0, "x_end": 1.0, "y_end": 2.0,
             "width_mm": 400, "height_mm": 400, "story": "P", "layer": "STUP"},
        ]),
        "beams": pd.DataFrame(),
        "walls": pd.DataFrame(),
        "slabs": pd.DataFrame(),
    }
    df = mc.ref_model_to_dxf_table(model)
    for c in ("element_type", "centroid_x_m", "centroid_y_m", "dim1_mm", "dim2_mm"):
        assert c in df.columns
    assert len(df) == 1
    row = df.iloc[0]
    assert row["element_type"] == "column"
    assert row["centroid_x_m"] == 1.0
    assert row["dim1_mm"] == 400.0


def test_adapter_beam_centroid_is_midpoint():
    import model_compare as mc
    model = {"beams": pd.DataFrame([
        {"name": "B1", "x_start": 0.0, "y_start": 0.0, "x_end": 4.0, "y_end": 0.0,
         "width_mm": 300, "height_mm": 500, "story": "P"}])}
    df = mc.ref_model_to_dxf_table(model)
    assert df.iloc[0]["centroid_x_m"] == 2.0  # sredina 0..4


def test_adapter_area_uses_centroid():
    import model_compare as mc
    model = {"slabs": pd.DataFrame([
        {"name": "S1", "centroid_x": 5.0, "centroid_y": 6.0, "story": "P"}])}
    df = mc.ref_model_to_dxf_table(model)
    assert df.iloc[0]["element_type"] == "slab"
    assert df.iloc[0]["centroid_x_m"] == 5.0
    assert df.iloc[0]["centroid_y_m"] == 6.0


def test_adapter_empty_model():
    import model_compare as mc
    df = mc.ref_model_to_dxf_table({})
    assert df.empty
    df2 = mc.ref_model_to_dxf_table(None)
    assert df2.empty


def test_adapter_on_real_ab_zgrada():
    import model_compare as mc
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(AB_ZGRADA, Config(), {"n_stories": 1})
    df = mc.ref_model_to_dxf_table(r)
    # svi stupovi + grede + zidovi + ploce prebaceni u jednu tablicu
    assert len(df) == r["meta"]["n_elements"]
    # stupovi imaju dimenzije 400x400
    cols = df[df["element_type"] == "column"]
    assert (cols["dim1_mm"] == 400.0).all()


# --------------------------------------------------------------------------
# Zadatak 3: compare_models + summarize_differences
# --------------------------------------------------------------------------
def _ref_three_columns():
    return {
        "columns": pd.DataFrame([
            {"name": "C1", "x_start": 0.0, "y_start": 0.0, "x_end": 0.0, "y_end": 0.0,
             "width_mm": 400, "height_mm": 400, "story": "PRIZEMLJE"},
            {"name": "C2", "x_start": 6.0, "y_start": 0.0, "x_end": 6.0, "y_end": 0.0,
             "width_mm": 400, "height_mm": 400, "story": "PRIZEMLJE"},
            {"name": "C3", "x_start": 6.0, "y_start": 6.0, "x_end": 6.0, "y_end": 6.0,
             "width_mm": 400, "height_mm": 400, "story": "PRIZEMLJE"},
        ]),
        "beams": pd.DataFrame(), "walls": pd.DataFrame(), "slabs": pd.DataFrame(),
    }


def _student(rows):
    return {"columns": pd.DataFrame(rows)}


def test_compare_perfect_match():
    """Student modelirao točno kao tlocrt -> sve MATCH, ok=True."""
    import model_compare as mc
    from config import Config
    ref = _ref_three_columns()
    student = _student([
        {"name": "SC1", "element_type": "column", "x_match": 0.0, "y_match": 0.0,
         "centroid_x": 0.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
        {"name": "SC2", "element_type": "column", "x_match": 6.0, "y_match": 0.0,
         "centroid_x": 6.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
        {"name": "SC3", "element_type": "column", "x_match": 6.0, "y_match": 6.0,
         "centroid_x": 6.0, "centroid_y": 6.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
    ])
    df = mc.compare_models(student, ref, Config())
    s = mc.summarize_differences(df)
    assert s["counts"]["match"] == 3
    assert s["ok"] is True


def test_compare_detects_missing_column():
    """Student izostavio jedan stup -> DXF_ONLY -> 'nedostaje'."""
    import model_compare as mc
    from config import Config
    ref = _ref_three_columns()
    student = _student([
        {"name": "SC1", "element_type": "column", "x_match": 0.0, "y_match": 0.0,
         "centroid_x": 0.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
        {"name": "SC2", "element_type": "column", "x_match": 6.0, "y_match": 0.0,
         "centroid_x": 6.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
    ])
    df = mc.compare_models(student, ref, Config())
    s = mc.summarize_differences(df)
    assert s["counts"]["nedostaje"] >= 1
    assert any("Nedostaje" in msg and "stup" in msg for msg in s["messages"])
    assert s["ok"] is False


def test_compare_detects_extra_and_mismatch():
    """Student ima višak stupa i jedan krivo dimenzioniran."""
    import model_compare as mc
    from config import Config
    ref = _ref_three_columns()
    student = _student([
        {"name": "SC1", "element_type": "column", "x_match": 0.0, "y_match": 0.0,
         "centroid_x": 0.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
        {"name": "SC2", "element_type": "column", "x_match": 6.0, "y_match": 0.0,
         "centroid_x": 6.0, "centroid_y": 0.0, "width_mm": 300, "height_mm": 300,
         "story": "PRIZEMLJE", "section": "30/30"},   # kriva dimenzija
        {"name": "SC3", "element_type": "column", "x_match": 6.0, "y_match": 6.0,
         "centroid_x": 6.0, "centroid_y": 6.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},
        {"name": "SC4", "element_type": "column", "x_match": 12.0, "y_match": 12.0,
         "centroid_x": 12.0, "centroid_y": 12.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"},   # visak
    ])
    df = mc.compare_models(student, ref, Config())
    s = mc.summarize_differences(df)
    assert s["counts"]["visak"] >= 1
    assert s["counts"]["mismatch"] >= 1
    assert any("Višak" in msg for msg in s["messages"])
    assert any("Kriva dimenzija" in msg for msg in s["messages"])


def test_summarize_empty_result():
    import model_compare as mc
    s = mc.summarize_differences(pd.DataFrame())
    assert s["ok"] is True
    assert s["counts"]["ukupno"] == 0
    assert s["messages"] == []
