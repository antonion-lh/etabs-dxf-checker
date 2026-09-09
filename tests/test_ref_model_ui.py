"""Testovi za ref_model_ui.py — čista logika UI toka referentnog modela."""
import os

import pandas as pd

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_dxf")
AB_ZGRADA = os.path.join(SAMPLE_DIR, "ab_zgrada.dxf")


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_exposes_api():
    import ref_model_ui as ui
    for fn in ("build_ref_model_from_bytes", "editable_tables", "apply_edits",
               "model_summary_text", "input_signature"):
        assert hasattr(ui, fn)


def test_build_from_bytes_ab_zgrada():
    import ref_model_ui as ui
    from config import Config
    model = ui.build_ref_model_from_bytes(_read_bytes(AB_ZGRADA), Config(),
                                          {"n_stories": 4, "story_height": 3.2})
    assert model["meta"]["ok"] is True
    assert len(model["columns"]) == 120
    assert len(model["stories"]) == 4


def test_build_from_empty_bytes_graceful():
    import ref_model_ui as ui
    from config import Config
    model = ui.build_ref_model_from_bytes(b"", Config())
    assert model["meta"]["ok"] is False
    assert model["meta"]["error"] is not None


def test_editable_tables_only_nonempty():
    import ref_model_ui as ui
    from config import Config
    model = ui.build_ref_model_from_bytes(_read_bytes(AB_ZGRADA), Config(),
                                          {"n_stories": 1})
    tables = ui.editable_tables(model)
    assert "columns" in tables
    # samo smislene kolone
    assert "width_mm" in tables["columns"].columns
    assert "name" in tables["columns"].columns


def test_apply_edits_changes_dimension():
    import ref_model_ui as ui
    model = {
        "columns": pd.DataFrame([
            {"name": "C1", "story": "P", "x_start": 0.0, "y_start": 0.0,
             "width_mm": 400, "height_mm": 400, "section": "40/40",
             "material": "", "source": "layer", "confidence": "visoka"},
        ]),
        "meta": {"ok": True},
    }
    tables = ui.editable_tables(model)
    edited = tables["columns"].copy()
    edited.loc[0, "width_mm"] = 500      # korisnik ispravi dimenziju
    new_model = ui.apply_edits(model, {"columns": edited})
    assert new_model["columns"].iloc[0]["width_mm"] == 500
    assert new_model["meta"]["edited"] is True
    # izvorni model netaknut
    assert model["columns"].iloc[0]["width_mm"] == 400


def test_apply_edits_row_deletion():
    import ref_model_ui as ui
    model = {
        "columns": pd.DataFrame([
            {"name": "C1", "story": "P", "x_start": 0.0, "y_start": 0.0,
             "width_mm": 400, "height_mm": 400},
            {"name": "C2", "story": "P", "x_start": 6.0, "y_start": 0.0,
             "width_mm": 400, "height_mm": 400},
        ]),
        "meta": {"ok": True},
    }
    tables = ui.editable_tables(model)
    edited = tables["columns"].iloc[:1].copy()   # korisnik obrisao drugi red
    new_model = ui.apply_edits(model, {"columns": edited})
    assert len(new_model["columns"]) == 1
    assert new_model["columns"].iloc[0]["name"] == "C1"


def test_model_summary_text():
    import ref_model_ui as ui
    from config import Config
    model = ui.build_ref_model_from_bytes(_read_bytes(AB_ZGRADA), Config(),
                                          {"n_stories": 4, "story_height": 3.2})
    lines = ui.model_summary_text(model)
    joined = " ".join(lines)
    assert "Stupovi" in joined
    assert "Etaže" in joined


def test_input_signature_changes_with_input():
    import ref_model_ui as ui
    b = b"abc"
    s1 = ui.input_signature(b, {"n_stories": 1})
    s2 = ui.input_signature(b, {"n_stories": 4})
    s3 = ui.input_signature(b, {"n_stories": 1})
    assert s1 != s2       # promjena unosa -> drugi potpis
    assert s1 == s3       # isti ulaz -> isti potpis


# --------------------------------------------------------------------------
# Dorada: JSON spremanje / učitavanje referentnog modela
# --------------------------------------------------------------------------
def test_model_json_roundtrip():
    import ref_model_ui as ui
    import pandas as pd
    model = {
        "columns": pd.DataFrame([
            {"name": "C1", "x_start": 0.0, "y_start": 0.0, "width_mm": 400,
             "height_mm": 400, "story": "P"}]),
        "beams": pd.DataFrame(),
        "walls": pd.DataFrame(),
        "slabs": pd.DataFrame(),
        "stories": [{"name": "P", "z_bottom": 0.0, "z_top": 3.0, "height": 3.0}],
        "meta": {"ok": True, "n_elements": 1},
    }
    text = ui.model_to_json(model)
    assert "C1" in text
    back = ui.model_from_json(text)
    assert len(back["columns"]) == 1
    assert back["columns"].iloc[0]["width_mm"] == 400
    assert back["meta"]["ok"] is True
    assert len(back["stories"]) == 1


def test_model_from_json_bytes():
    import ref_model_ui as ui
    model = {"columns": __import__("pandas").DataFrame(), "beams": None,
             "walls": None, "slabs": None, "meta": {"ok": True}}
    text = ui.model_to_json(model)
    back = ui.model_from_json(text.encode("utf-8"))
    assert back["meta"]["ok"] is True


# --------------------------------------------------------------------------
# UX popravak D.1: prijateljska poruka za neispravan JSON
# --------------------------------------------------------------------------
def test_model_from_json_friendly_error():
    import ref_model_ui as ui
    import pytest
    with pytest.raises(ValueError) as exc:
        ui.model_from_json(b"{ovo nije valjan json:}")
    assert "nije valjani JSON" in str(exc.value)


def test_model_from_json_non_dict():
    import ref_model_ui as ui
    import pytest
    with pytest.raises(ValueError):
        ui.model_from_json(b"[1, 2, 3]")   # valjan JSON ali nije dict


# --------------------------------------------------------------------------
# UX popravak 2: eksplicitan meta['source']
# --------------------------------------------------------------------------
def test_source_dxf():
    import ref_model_ui as ui
    from config import Config
    m = ui.build_ref_model_from_bytes(_read_bytes(AB_ZGRADA), Config(), {"n_stories": 1})
    assert m["meta"]["source"] == "dxf"


def test_source_json():
    import ref_model_ui as ui
    import pandas as pd
    model = {"columns": pd.DataFrame([{"name": "C1"}]), "beams": None,
             "walls": None, "slabs": None, "meta": {"ok": True}}
    text = ui.model_to_json(model)
    back = ui.model_from_json(text)
    assert back["meta"]["source"] == "json"
