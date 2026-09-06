"""Testovi za interaktivno uredjivanje vektoriziranog tlocrta (cista logika)."""

import io
import warnings


def _import_app():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import streamlit_app
    return streamlit_app


# --------------------------------------------------------------------------
# Zadatak 1: _vektor_selected_indices + _vektor_active_segments
# --------------------------------------------------------------------------
def test_selected_indices_dict_points():
    s = _import_app()
    sel = {"points": [{"curve_number": 2}, {"curve_number": 5}, {"curve_number": 2}]}
    assert s._vektor_selected_indices(sel) == {2, 5}


def test_selected_indices_camelcase():
    s = _import_app()
    sel = {"points": [{"curveNumber": 0}, {"curveNumber": 3}]}
    assert s._vektor_selected_indices(sel) == {0, 3}


def test_selected_indices_nested_selection():
    s = _import_app()
    sel = {"selection": {"points": [{"curve_number": 7}]}}
    assert s._vektor_selected_indices(sel) == {7}


def test_selected_indices_empty_and_none():
    s = _import_app()
    assert s._vektor_selected_indices(None) == set()
    assert s._vektor_selected_indices({}) == set()
    assert s._vektor_selected_indices({"points": []}) == set()


def test_active_segments_complement():
    s = _import_app()
    segs = [((0, 0), (10, 0)), ((0, 5), (10, 5)), ((0, 10), (10, 10))]
    assert s._vektor_active_segments(segs, {1}) == [segs[0], segs[2]]


def test_active_segments_empty_deleted():
    s = _import_app()
    segs = [((0, 0), (10, 0)), ((0, 5), (10, 5))]
    assert s._vektor_active_segments(segs, set()) == segs
    assert s._vektor_active_segments(segs, None) == segs


def test_active_segments_all_deleted():
    s = _import_app()
    segs = [((0, 0), (10, 0)), ((0, 5), (10, 5))]
    assert s._vektor_active_segments(segs, {0, 1}) == []


def test_active_segments_empty_input():
    s = _import_app()
    assert s._vektor_active_segments([], {0}) == []


# --------------------------------------------------------------------------
# Zadatak 2: _vektor_build_figure
# --------------------------------------------------------------------------
def test_build_figure_trace_count():
    import numpy as np
    s = _import_app()
    gray = np.full((100, 120), 255, dtype=np.uint8)
    segs = [((0, 0), (100, 0)), ((0, 50), (100, 50)), ((10, 10), (10, 90))]
    fig = s._vektor_build_figure(gray, segs)
    # svaki Scatter trag = jedna linija; pozadina je u layout.images (ne trag)
    scatter = [t for t in fig.data if t.type == "scatter"]
    assert len(scatter) == len(segs)
    # indeks traga odgovara indeksu linije: prva linija ide od x=0..100
    assert list(scatter[0].x) == [0, 100]


def test_build_figure_empty_segments():
    import numpy as np
    s = _import_app()
    gray = np.full((40, 40), 255, dtype=np.uint8)
    fig = s._vektor_build_figure(gray, [])
    scatter = [t for t in fig.data if t.type == "scatter"]
    assert len(scatter) == 0
    # pozadinska slika svejedno postavljena
    assert len(fig.layout.images) >= 1


# --------------------------------------------------------------------------
# Zadatak 4: Izvoz DXF-a iz aktivnog skupa (nakon rucnog brisanja)
# --------------------------------------------------------------------------
def _read_dxf_lines(dxf_bytes):
    from ezdxf import recover
    doc, _ = recover.read(io.BytesIO(dxf_bytes))
    return [e for e in doc.modelspace() if e.dxftype() == "LINE"]


def test_export_active_subset_line_count():
    s = _import_app()
    from raster_vectorize import segments_to_dxf
    segs = [
        ((0, 0), (100, 0)),
        ((0, 20), (100, 20)),
        ((0, 40), (100, 40)),
        ((0, 60), (100, 60)),
    ]
    deleted = {1, 3}
    active = s._vektor_active_segments(segs, deleted)
    assert len(active) == 2
    dxf = segments_to_dxf(active, 1.0, "VEKTOR_ZID", img_height_px=100)
    lines = _read_dxf_lines(dxf)
    assert len(lines) == 2
    assert all(e.dxf.layer == "VEKTOR_ZID" for e in lines)


def test_export_all_deleted_valid_empty_dxf():
    s = _import_app()
    from raster_vectorize import segments_to_dxf
    segs = [((0, 0), (100, 0)), ((0, 20), (100, 20))]
    active = s._vektor_active_segments(segs, {0, 1})
    assert active == []
    dxf = segments_to_dxf(active, 1.0, "VEKTOR_ZID", img_height_px=100)
    assert isinstance(dxf, bytes) and len(dxf) > 0
    assert len(_read_dxf_lines(dxf)) == 0


# --------------------------------------------------------------------------
# Zadatak 5: Smoke - streamlit_app izlaze sve nove helpere
# --------------------------------------------------------------------------
def test_app_exposes_vektor_edit_helpers():
    s = _import_app()
    for attr in (
        "_vektor_selected_indices",
        "_vektor_active_segments",
        "_vektor_build_figure",
        "_cached_vectorize",
        "_cached_pdf_pages",
    ):
        assert hasattr(s, attr), f"nedostaje {attr}"
        assert callable(getattr(s, attr))
