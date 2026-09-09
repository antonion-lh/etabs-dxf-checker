"""Testovi za dxf_model.py - geometrijska rekonstrukcija modela iz DXF-a (Faza B, Dio 1)."""

import os

import pytest

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_dxf")
AB_ZGRADA = os.path.join(SAMPLE_DIR, "ab_zgrada.dxf")
JSCAD = os.path.join(SAMPLE_DIR, "jscad_floorplan.dxf")


# --------------------------------------------------------------------------
# Zadatak 1: config.py dopune
# --------------------------------------------------------------------------
def test_config_has_dxf_model_fields():
    from config import Config
    c = Config()
    # mapiranje slojeva
    assert set(c.dxf_layer_map.keys()) >= {"column", "beam", "wall", "slab"}
    assert "STUP" in c.dxf_layer_map["column"]
    assert "WALL" in c.dxf_layer_map["wall"]
    # pragovi
    for k in ("column_max_area_m2", "wall_thickness_min_m", "beam_min_len_m", "join_tol_m"):
        assert k in c.dxf_geom_thresholds
    # 3D defaulti
    assert c.dxf_default_story_height == 3.0
    assert c.dxf_default_n_stories == 1
    # hash i dalje radi (cache kompatibilnost)
    assert isinstance(hash(c), int)


# --------------------------------------------------------------------------
# Zadatak 2: dxf_model.py kostur + classify_by_layer
# --------------------------------------------------------------------------
def test_dxf_model_exposes_api():
    import dxf_model as m
    for attr in (
        "classify_by_layer", "classify_by_geometry", "detect_walls_from_lines",
        "reconstruct_stories", "check_geometry_integrity", "build_model_from_dxf",
    ):
        assert hasattr(m, attr) and callable(getattr(m, attr)), f"nedostaje {attr}"


def test_classify_by_layer_known_types():
    import dxf_model as m
    from config import Config
    c = Config()
    assert m.classify_by_layer("STUP", c) == "column"
    assert m.classify_by_layer("S-COLUMN-01", c) == "column"
    assert m.classify_by_layer("GREDA_KAT1", c) == "beam"
    assert m.classify_by_layer("A-WALL", c) == "wall"
    assert m.classify_by_layer("PLOCA", c) == "slab"
    assert m.classify_by_layer("SLAB_L1", c) == "slab"


def test_classify_by_layer_case_insensitive():
    import dxf_model as m
    from config import Config
    c = Config()
    assert m.classify_by_layer("stup", c) == "column"
    assert m.classify_by_layer("wall_ext", c) == "wall"


def test_classify_by_layer_unknown_and_none():
    import dxf_model as m
    from config import Config
    c = Config()
    assert m.classify_by_layer("A-NOTE", c) is None
    assert m.classify_by_layer("", c) is None
    assert m.classify_by_layer(None, c) is None
    # grid/dim nisu konstruktivni tipovi -> None
    assert m.classify_by_layer("OSI", c) is None
    assert m.classify_by_layer("KOTE", c) is None


# --------------------------------------------------------------------------
# Zadatak 3: classify_by_geometry + detect_walls_from_lines
# --------------------------------------------------------------------------
def test_classify_geometry_column():
    import dxf_model as m
    from config import Config
    c = Config()
    # stup 0.4 x 0.4 m -> area 0.16, kompaktan -> column
    tip, conf = m.classify_by_geometry({"width_m": 0.4, "height_m": 0.4}, c)
    assert tip == "column"
    assert conf in ("visoka", "srednja")


def test_classify_geometry_slab():
    import dxf_model as m
    from config import Config
    c = Config()
    # velika ploca 12 x 10 m -> area 120 -> slab
    tip, conf = m.classify_by_geometry({"width_m": 12.0, "height_m": 10.0}, c)
    assert tip == "slab"
    assert conf == "visoka"


def test_classify_geometry_ambiguous():
    import dxf_model as m
    from config import Config
    c = Config()
    # srednja kontura 1.5 x 1.0 m -> ni stup (prevelik) ni ploca (premala) -> None
    tip, conf = m.classify_by_geometry({"width_m": 1.5, "height_m": 1.0}, c)
    assert tip is None
    assert conf == "niska"


def test_classify_geometry_from_bbox():
    import dxf_model as m
    from config import Config
    c = Config()
    tip, _ = m.classify_by_geometry({"bbox": (0.0, 0.0, 0.4, 0.4)}, c)
    assert tip == "column"


def test_detect_walls_horizontal_pair():
    import dxf_model as m
    from config import Config
    c = Config()
    # dvije horizontalne linije na y=0 i y=0.25 (razmak 0.25 = debljina), x 0..5
    lines = [
        {"x0": 0.0, "y0": 0.0, "x1": 5.0, "y1": 0.0},
        {"x0": 0.0, "y0": 0.25, "x1": 5.0, "y1": 0.25},
    ]
    walls = m.detect_walls_from_lines(lines, c)
    assert len(walls) == 1
    w = walls[0]
    assert abs(w["thickness_m"] - 0.25) < 1e-6
    assert abs(w["y_start"] - 0.125) < 1e-6  # os na sredini
    assert w["y_start"] == w["y_end"]        # horizontalni zid


def test_detect_walls_vertical_pair():
    import dxf_model as m
    from config import Config
    c = Config()
    lines = [
        {"x0": 2.0, "y0": 0.0, "x1": 2.0, "y1": 4.0},
        {"x0": 2.30, "y0": 0.0, "x1": 2.30, "y1": 4.0},
    ]
    walls = m.detect_walls_from_lines(lines, c)
    assert len(walls) == 1
    assert abs(walls[0]["thickness_m"] - 0.30) < 1e-6
    assert walls[0]["x_start"] == walls[0]["x_end"]


def test_detect_walls_too_far_apart():
    import dxf_model as m
    from config import Config
    c = Config()
    # razmak 1.0 m > wall_thickness_max (0.50) -> nije zid
    lines = [
        {"x0": 0.0, "y0": 0.0, "x1": 5.0, "y1": 0.0},
        {"x0": 0.0, "y0": 1.0, "x1": 5.0, "y1": 1.0},
    ]
    walls = m.detect_walls_from_lines(lines, c)
    assert walls == []


# --------------------------------------------------------------------------
# Zadatak 4: _load_dxf (jedinice, recover, robusnost)
# --------------------------------------------------------------------------
def test_load_dxf_ab_zgrada_units_m():
    import dxf_model as m
    from config import Config
    doc, scale, err = m._load_dxf(AB_ZGRADA, Config())
    assert err is None
    assert doc is not None
    # ab_zgrada.dxf ima INSUNITS=4 (mm) -> scale 0.001
    assert abs(scale - 0.001) < 1e-9


def test_load_dxf_jscad_readable():
    import dxf_model as m
    from config import Config
    doc, scale, err = m._load_dxf(JSCAD, Config())
    assert err is None
    assert doc is not None
    assert scale > 0


def test_load_dxf_nonexistent():
    import dxf_model as m
    from config import Config
    doc, scale, err = m._load_dxf("/nepostoji_12345.dxf", Config())
    assert doc is None
    assert err is not None
    assert scale == 0.0


def test_load_dxf_garbage(tmp_path):
    import dxf_model as m
    from config import Config
    p = tmp_path / "smece.dxf"
    p.write_text("ovo nije dxf sadrzaj")
    doc, scale, err = m._load_dxf(str(p), Config())
    assert doc is None and err is not None


def test_load_dxf_unknown_units_fallback(tmp_path):
    import ezdxf
    import dxf_model as m
    from config import Config
    # DXF bez INSUNITS -> fallback na cfg.dxf_unit_scale
    d = ezdxf.new("R2010")
    d.header["$INSUNITS"] = 0
    f = tmp_path / "nounits.dxf"
    d.saveas(str(f))
    c = Config()
    doc, scale, err = m._load_dxf(str(f), c)
    assert err is None
    assert abs(scale - c.dxf_unit_scale) < 1e-9


# --------------------------------------------------------------------------
# Zadatak 5: reconstruct_stories (2D->3D)
# --------------------------------------------------------------------------
def test_stories_from_user_input_uniform():
    import dxf_model as m
    from config import Config
    stories, assumptions = m.reconstruct_stories(None, None, Config(),
                                                 {"n_stories": 4, "story_height": 3.2})
    assert len(stories) == 4
    assert stories[0]["name"] == "PRIZEMLJE"
    assert abs(stories[0]["z_bottom"] - 0.0) < 1e-9
    assert abs(stories[0]["z_top"] - 3.2) < 1e-9
    assert abs(stories[3]["z_top"] - 12.8) < 1e-9  # 4 x 3.2
    # jednake visine -> bez napomene o visini
    assert all(abs(s["height"] - 3.2) < 1e-9 for s in stories)


def test_stories_variable_heights():
    import dxf_model as m
    from config import Config
    stories, _ = m.reconstruct_stories(None, None, Config(),
                                       {"n_stories": 3, "story_height": [4.0, 3.0, 3.0]})
    assert len(stories) == 3
    assert abs(stories[0]["z_top"] - 4.0) < 1e-9
    assert abs(stories[1]["z_top"] - 7.0) < 1e-9
    assert abs(stories[2]["z_top"] - 10.0) < 1e-9


def test_stories_no_input_defaults_2d():
    import dxf_model as m
    from config import Config
    stories, assumptions = m.reconstruct_stories(None, None, Config(), None)
    # default n_stories=1 -> 2D, jedna razina + napomena
    assert len(stories) == 1
    assert stories[0]["name"] == "PRIZEMLJE"
    assert any("2D" in a for a in assumptions)


def test_stories_custom_names():
    import dxf_model as m
    from config import Config
    stories, _ = m.reconstruct_stories(None, None, Config(),
                                       {"n_stories": 2, "story_height": 3.0,
                                        "story_names": ["SUTEREN", "PRIZEMLJE"]})
    assert stories[0]["name"] == "SUTEREN"
    assert stories[1]["name"] == "PRIZEMLJE"


# --------------------------------------------------------------------------
# Zadatak 6: build_model_from_dxf (na sintetskom ab_zgrada.dxf)
# --------------------------------------------------------------------------
def test_build_model_ab_zgrada_structure():
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(AB_ZGRADA, Config(), {"n_stories": 4, "story_height": 3.2})
    assert r["meta"]["ok"] is True
    # kljucevi kompatibilni s phase1_e2k
    for k in ("columns", "beams", "walls", "slabs", "stories", "grid", "meta"):
        assert k in r
    # ab_zgrada: 30 stupova/etaza -> 120 (svi na sloju STUP), 4 ploce
    assert len(r["columns"]) == 120
    assert len(r["slabs"]) == 4
    assert len(r["walls"]) >= 4        # zidovi jezgre
    assert len(r["beams"]) > 0
    assert len(r["stories"]) == 4


def test_build_model_columns_have_phase1_columns():
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(AB_ZGRADA, Config(), {"n_stories": 1})
    cols = r["columns"]
    for c in ("name", "element_type", "x_start", "y_start", "story", "section",
              "material", "source", "confidence"):
        assert c in cols.columns
    # klasifikacija po sloju STUP -> visoka pouzdanost
    assert (cols["source"] == "layer").all()
    assert (cols["confidence"] == "visoka").all()


def test_build_model_confidence_summary():
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(AB_ZGRADA, Config(), {"n_stories": 4, "story_height": 3.2})
    cs = r["meta"]["confidence_summary"]
    assert cs.get("visoka", 0) > 0
    assert r["meta"]["n_elements"] == (
        len(r["columns"]) + len(r["beams"]) + len(r["walls"]) + len(r["slabs"]))


def test_build_model_bad_input_graceful():
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf("/nepostoji.dxf", Config())
    assert r["meta"]["ok"] is False
    assert r["meta"]["error"] is not None
    assert r["meta"]["n_elements"] == 0


# --------------------------------------------------------------------------
# Zadatak 7: check_geometry_integrity
# --------------------------------------------------------------------------
def test_integrity_clean_model():
    import pandas as pd
    import dxf_model as m
    from config import Config
    model = {
        "columns": pd.DataFrame([
            {"name": "C1", "x_start": 0.0, "y_start": 0.0, "story": "P",
             "width_mm": 400, "height_mm": 400},
            {"name": "C2", "x_start": 6.0, "y_start": 0.0, "story": "P",
             "width_mm": 400, "height_mm": 400},
        ]),
        "walls": pd.DataFrame([{"name": "W1", "thickness_mm": 250}]),
    }
    assert m.check_geometry_integrity(model, Config()) == []


def test_integrity_unrealistic_column_dim():
    import pandas as pd
    import dxf_model as m
    from config import Config
    model = {"columns": pd.DataFrame([
        {"name": "C1", "x_start": 0.0, "y_start": 0.0, "story": "P",
         "width_mm": 3000, "height_mm": 400}]),  # 3000 mm = 3 m > dim_max 1.5 m
        "walls": pd.DataFrame()}
    w = m.check_geometry_integrity(model, Config())
    assert any("izvan realnog raspona" in x for x in w)


def test_integrity_unrealistic_wall_thickness():
    import pandas as pd
    import dxf_model as m
    from config import Config
    model = {"columns": pd.DataFrame(),
             "walls": pd.DataFrame([{"name": "W1", "thickness_mm": 800}])}  # 0.8 m > 0.5
    w = m.check_geometry_integrity(model, Config())
    assert any("Zid" in x and "izvan realnog raspona" in x for x in w)


def test_integrity_duplicate_columns():
    import pandas as pd
    import dxf_model as m
    from config import Config
    model = {"columns": pd.DataFrame([
        {"name": "C1", "x_start": 0.0, "y_start": 0.0, "story": "P",
         "width_mm": 400, "height_mm": 400},
        {"name": "C2", "x_start": 0.0, "y_start": 0.0, "story": "P",
         "width_mm": 400, "height_mm": 400}]),  # isti XY+story = duplikat
        "walls": pd.DataFrame()}
    w = m.check_geometry_integrity(model, Config())
    assert any("duplicira" in x for x in w)


# --------------------------------------------------------------------------
# Zadatak 8: integracijski testovi (stvarni DXF-ovi + robusnost)
# --------------------------------------------------------------------------
def test_integration_ab_zgrada_full_model():
    """Sintetski AB primjer: ~120 stupova, 4 etaže, potpuni model."""
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(AB_ZGRADA, Config(),
                               {"n_stories": 4, "story_height": 3.2})
    assert r["meta"]["ok"] is True
    assert len(r["columns"]) == 120
    assert len(r["slabs"]) == 4
    assert len(r["stories"]) == 4
    # svi elementi klasificirani po sloju -> visoka pouzdanost
    assert r["meta"]["confidence_summary"].get("visoka", 0) == r["meta"]["n_elements"]
    # etaze: prizemlje na dnu, zadnja na 4*3.2 = 12.8 m
    assert r["stories"][0]["z_bottom"] == 0.0
    assert abs(r["stories"][-1]["z_top"] - 12.8) < 1e-6
    # integritet: model je cist (realne dimenzije, bez duplikata)
    assert m.check_geometry_integrity(r, Config()) == []


def test_integration_jscad_real_floorplan():
    """Realni MIT jscad tlocrt: jednoetažni, zidovi dominiraju."""
    import dxf_model as m
    from config import Config
    r = m.build_model_from_dxf(JSCAD, Config())
    assert r["meta"]["ok"] is True
    # uspjesna rekonstrukcija: prepoznat barem koji element
    assert r["meta"]["n_elements"] > 0
    # zidovi su glavni konstruktivni element u tlocrtu
    assert len(r["walls"]) > 0
    # bez unosa etaza -> jedna razina (2D)
    assert len(r["stories"]) == 1


def test_integration_empty_dxf_graceful(tmp_path):
    """Prazan (validan) DXF: bez rusenja, ok=True, 0 elemenata + upozorenje."""
    import ezdxf
    import dxf_model as m
    from config import Config
    doc = ezdxf.new()
    p = tmp_path / "prazan.dxf"
    doc.saveas(str(p))
    r = m.build_model_from_dxf(str(p), Config())
    assert r["meta"]["ok"] is True
    assert r["meta"]["n_elements"] == 0
    # jasna povratna informacija korisniku
    assert any("nijedan konstruktivni element" in w for w in r["meta"]["warnings"])


def test_integration_unreadable_dxf_graceful(tmp_path):
    """Nečitljiv DXF: graceful, ok=False, error postavljen, bez iznimke."""
    import dxf_model as m
    from config import Config
    p = tmp_path / "pokvaren.dxf"
    p.write_text("ovo definitivno nije DXF sadrzaj\n" * 5, encoding="utf-8")
    r = m.build_model_from_dxf(str(p), Config())
    assert r["meta"]["ok"] is False
    assert r["meta"]["error"] is not None
    assert r["meta"]["n_elements"] == 0
