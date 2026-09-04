"""Smoke testovi za modul raster_vectorize."""

import io

import numpy as np
import pytest

import raster_vectorize as r


def _png_bytes(arr):
    from PIL import Image
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes(width_pt=200, height_pt=150):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    page.draw_line((10, 10), (width_pt - 10, height_pt - 10), width=2)
    data = doc.tobytes()
    doc.close()
    return data


def test_module_exposes_expected_api():
    for attr in (
        "rasterize_input",
        "binarize",
        "denoise",
        "detect_line_segments",
        "merge_collinear",
        "segments_to_dxf",
        "vectorize_floorplan",
        "Params",
        "Segment",
    ):
        assert hasattr(r, attr), f"Nedostaje atribut: {attr}"


def test_params_defaults():
    p = r.Params()
    assert p.min_len_px == 60
    assert p.layer_name == "VEKTOR_ZID"
    assert p.threshold is None


def test_rasterize_image_png():
    # sintetska slika: 200 (H) x 300 (W), bijela s par crnih linija
    arr = np.full((200, 300), 255, dtype=np.uint8)
    arr[50, :] = 0
    arr[:, 120] = 0
    png = _png_bytes(arr)
    out = r.rasterize_input(png, "x.png")
    assert isinstance(out, np.ndarray)
    assert out.ndim == 2
    assert out.dtype == np.uint8
    assert out.shape == (200, 300)


def test_rasterize_pdf():
    pdf = _pdf_bytes()
    out = r.rasterize_input(pdf, "x.pdf")
    assert isinstance(out, np.ndarray)
    assert out.ndim == 2
    assert out.dtype == np.uint8
    assert out.size > 0
    assert out.shape[0] > 0 and out.shape[1] > 0


def test_rasterize_bad_format():
    with pytest.raises(ValueError):
        r.rasterize_input(b"x", "x.txt")


def test_rasterize_dpi_cap_pdf():
    # velika stranica + mali max_side_px -> nijedna strana ne prelazi ~100 px
    pdf = _pdf_bytes(width_pt=2000, height_pt=1500)
    out = r.rasterize_input(pdf, "big.pdf", max_side_px=100)
    assert out.ndim == 2
    assert max(out.shape) <= 110  # tolerancija na zaokruzivanje


def test_rasterize_dpi_cap_image():
    arr = np.full((800, 600), 255, dtype=np.uint8)
    png = _png_bytes(arr)
    out = r.rasterize_input(png, "big.png", max_side_px=100)
    assert out.ndim == 2
    assert max(out.shape) <= 110


def test_otsu_bimodal():
    # dvije jasne populacije: pola 30, pola 220 -> prag izmedju
    arr = np.empty((100, 100), dtype=np.uint8)
    arr[:50, :] = 30
    arr[50:, :] = 220
    thr = r._otsu_threshold(arr)
    assert isinstance(thr, int)
    assert 30 < thr < 220


def test_binarize_counts():
    # bijela 100x100 s crnim blokom 20x20 -> tocno 400 tamnih piksela pri pragu 128
    arr = np.full((100, 100), 255, dtype=np.uint8)
    arr[10:30, 40:60] = 0
    mask = r.binarize(arr, threshold=128)
    assert mask.dtype == bool
    assert mask.shape == arr.shape
    assert int(mask.sum()) == 400


def test_binarize_otsu_none():
    arr = np.full((60, 80), 255, dtype=np.uint8)
    arr[5:15, 5:15] = 0
    mask = r.binarize(arr)  # None -> Otsu, ne smije baciti
    assert mask.dtype == bool
    assert mask.ndim == 2
    assert mask.shape == arr.shape


def test_binarize_constant_image():
    # potpuno bijela -> nista tamno (0 True); potpuno crna -> bez pada
    white = np.full((40, 40), 255, dtype=np.uint8)
    mask_w = r.binarize(white)
    assert mask_w.dtype == bool
    assert int(mask_w.sum()) == 0

    black = np.zeros((40, 40), dtype=np.uint8)
    mask_b = r.binarize(black)  # ne smije baciti
    assert mask_b.dtype == bool
    assert mask_b.shape == black.shape


def _speckle_mask():
    # 50x50 sve False; nekoliko izoliranih True (sol-papar) + puna linija debljine 3px, duzine 40.
    b = np.zeros((50, 50), dtype=bool)
    for (y, x) in [(5, 5), (10, 40), (30, 20), (45, 45), (2, 25)]:
        b[y, x] = True
    for row in (20, 21, 22):
        b[row, 5:45] = True
    return b


def test_denoise_removes_speckle():
    b = _speckle_mask()
    before_total = int(b.sum())
    out = r.denoise(b, iters=1)
    assert out.dtype == bool
    # izolirani pikseli uklonjeni -> ukupan broj True pada
    assert int(out.sum()) < before_total
    isolated = [(5, 5), (10, 40), (30, 20), (45, 45), (2, 25)]
    assert sum(int(out[y, x]) for (y, x) in isolated) == 0
    # linija (debljine 3px) vecinski ostaje: sredisnji red barem 30 True
    assert int(out[21, :].sum()) >= 30


def test_denoise_iters_zero():
    b = _speckle_mask()
    out = r.denoise(b, iters=0)
    assert np.array_equal(out, b)


def test_denoise_preserves_shape():
    b = _speckle_mask()
    out = r.denoise(b, iters=1)
    assert out.shape == b.shape
    assert out.dtype == bool



def test_detect_horizontal_line():
    b = np.zeros((100, 100), dtype=bool)
    b[50, 10:90] = True  # x = 10..89 (duzina 80), redak y = 50
    segs = r.detect_line_segments(b, min_len_px=60)
    assert len(segs) >= 1
    horiz = [s for s in segs if s[0][1] == s[1][1]]
    assert horiz, "nema horizontalnog segmenta"
    (x0, y0), (x1, y1) = horiz[0]
    assert y0 == y1 == 50
    xs = sorted((x0, x1))
    assert xs[0] == 10 and xs[1] == 89
    assert (xs[1] - xs[0] + 1) >= 60


def test_detect_vertical_line():
    b = np.zeros((100, 100), dtype=bool)
    b[5:85, 30] = True  # y = 5..84 (duzina 80), stupac x = 30
    segs = r.detect_line_segments(b, min_len_px=60)
    assert len(segs) >= 1
    vert = [s for s in segs if s[0][0] == s[1][0]]
    assert vert, "nema vertikalnog segmenta"
    (x0, y0), (x1, y1) = vert[0]
    assert x0 == x1 == 30
    ys = sorted((y0, y1))
    assert ys[0] == 5 and ys[1] == 84
    assert (ys[1] - ys[0] + 1) >= 60


def test_detect_min_len_filter():
    b = np.zeros((100, 100), dtype=bool)
    b[50, 10:30] = True  # duzina 20
    segs = r.detect_line_segments(b, min_len_px=60)
    # kratka linija se ne smije pojaviti kao segment
    assert all(
        not (s[0][1] == s[1][1] == 50 and abs(s[1][0] - s[0][0]) + 1 >= 60)
        for s in segs
    )
    assert segs == []


def test_detect_empty():
    b = np.zeros((100, 100), dtype=bool)
    assert r.detect_line_segments(b) == []


def test_detect_both():
    b = np.zeros((100, 100), dtype=bool)
    b[50, 10:90] = True   # horizontalna
    b[5:85, 30] = True    # vertikalna
    segs = r.detect_line_segments(b, min_len_px=60)
    assert len(segs) >= 2
    horiz = [s for s in segs if s[0][1] == s[1][1]]
    vert = [s for s in segs if s[0][0] == s[1][0]]
    assert horiz, "nema horizontalne linije"
    assert vert, "nema vertikalne linije"
    # H ima y0 == y1
    assert horiz[0][0][1] == horiz[0][1][1]
    # V ima x0 == x1
    assert vert[0][0][0] == vert[0][1][0]


def test_merge_two_collinear_h():
    segs = [((10, 50), (40, 50)), ((48, 50), (90, 50))]
    out = r.merge_collinear(segs, max_gap_px=12)
    assert len(out) == 1
    (x0, y0), (x1, y1) = out[0]
    assert y0 == y1 == 50
    assert (x0, x1) == (10, 90)


def test_merge_gap_too_large():
    segs = [((10, 50), (40, 50)), ((70, 50), (90, 50))]
    out = r.merge_collinear(segs, max_gap_px=12)
    assert len(out) == 2


def test_merge_vertical():
    segs = [((30, 5), (30, 40)), ((30, 46), (30, 84))]
    out = r.merge_collinear(segs, max_gap_px=12)
    assert len(out) == 1
    (x0, y0), (x1, y1) = out[0]
    assert x0 == x1 == 30
    assert (y0, y1) == (5, 84)


def test_merge_different_lines_untouched():
    segs = [((10, 50), (40, 50)), ((10, 80), (40, 80))]
    out = r.merge_collinear(segs, max_gap_px=12)
    assert len(out) == 2


def test_merge_empty():
    assert r.merge_collinear([]) == []


def _h(y, x0, x1):
    return ((x0, y), (x1, y))


def test_reduce_removes_short():
    # dva duga (>=60) i dva kratka (<60) H segmenta -> kratki otpadaju
    segs = [
        _h(10, 0, 100),   # duljina 101
        _h(200, 0, 80),   # duljina 81
        _h(30, 0, 30),    # duljina 31 (< 60)
        _h(40, 0, 20),    # duljina 21 (< 60)
    ]
    out = r.reduce_noise(segs, min_len_px=60)
    assert _h(10, 0, 100) in out
    assert _h(200, 0, 80) in out
    assert _h(30, 0, 30) not in out
    assert _h(40, 0, 20) not in out
    assert len(out) == 2


def test_reduce_removes_dense_parallel():
    # 12 gusto naslaganih H segmenata (y=100,103,...,133), svaki dug 81, X-preklapaju
    stairs = [_h(100 + 3 * i, 200, 280) for i in range(12)]
    # dva normalna zida daleko jedan od drugog
    wall_top = _h(50, 0, 400)
    wall_bot = _h(300, 0, 400)
    out = r.reduce_noise(stairs + [wall_top, wall_bot], dense_parallel_thresh=8)
    # gusti snop je uklonjen (skoro) u cijelosti
    remaining_stairs = sum(1 for s in out if s in stairs)
    assert remaining_stairs <= 2
    # normalni zidovi prezive
    assert wall_top in out
    assert wall_bot in out


def test_reduce_keeps_normal_walls():
    # 4 normalna zida razmaknuta po y > 30px, svaki dug -> svi ostaju
    walls = [_h(50, 0, 300), _h(100, 0, 300), _h(150, 0, 300), _h(200, 0, 300)]
    out = r.reduce_noise(walls)
    for w in walls:
        assert w in out
    assert len(out) == 4


def test_reduce_empty():
    assert r.reduce_noise([]) == []


def _read_dxf_bytes(dxf_bytes):
    # Ucitaj DXF natrag: ezdxf.recover.read prima BytesIO (ne StringIO).
    from ezdxf import recover
    doc, _auditor = recover.read(io.BytesIO(dxf_bytes))
    return doc


def _lines(doc):
    return [e for e in doc.modelspace() if e.dxftype() == "LINE"]


def test_dxf_roundtrip_count():
    segs = [((0, 0), (10, 0)), ((10, 0), (10, 20)), ((10, 20), (0, 20))]
    data = r.segments_to_dxf(segs)
    assert isinstance(data, bytes) and len(data) > 0
    doc = _read_dxf_bytes(data)
    lines = _lines(doc)
    assert len(lines) == 3
    assert all(e.dxf.layer == "VEKTOR_ZID" for e in lines)


def test_dxf_layer_name():
    segs = [((0, 0), (10, 0))]
    data = r.segments_to_dxf(segs, layer="TEST_SLOJ")
    doc = _read_dxf_bytes(data)
    lines = _lines(doc)
    assert len(lines) == 1
    assert lines[0].dxf.layer == "TEST_SLOJ"
    assert doc.layers.has_entry("TEST_SLOJ")


def test_dxf_scaling_and_yflip():
    segs = [((0, 0), (10, 0))]
    data = r.segments_to_dxf(segs, px_to_unit=2.0, img_height_px=100)
    doc = _read_dxf_bytes(data)
    lines = _lines(doc)
    assert len(lines) == 1
    start = lines[0].dxf.start
    end = lines[0].dxf.end
    # x skaliran: 0*2=0 i 10*2=20; y-flip: (100-0)*2=200 za oba kraja.
    assert abs(start.x - 0.0) < 1e-6
    assert abs(end.x - 20.0) < 1e-6
    assert abs(start.y - 200.0) < 1e-6
    assert abs(end.y - 200.0) < 1e-6


def test_dxf_empty():
    data = r.segments_to_dxf([])
    assert isinstance(data, bytes) and len(data) > 0
    doc = _read_dxf_bytes(data)
    assert len(_lines(doc)) == 0
    assert doc.layers.has_entry("VEKTOR_ZID")


def _framed_plan_png():
    # Bijela 300x400 slika s DEBELIM okvirom pravokutnika (zidovi 5px).
    # Debljina 5px prezivi 3x3 denoise opening (zadatak 4).
    arr = np.full((300, 400), 255, dtype=np.uint8)
    t = 5
    arr[0:t, :] = 0        # gornji zid
    arr[-t:, :] = 0        # donji zid
    arr[:, 0:t] = 0        # lijevi zid
    arr[:, -t:] = 0        # desni zid
    return _png_bytes(arr)


def test_vectorize_floorplan_synthetic():
    png = _framed_plan_png()
    res = r.vectorize_floorplan(png, "plan.png", r.Params(min_len_px=50))

    assert isinstance(res, dict)
    for key in ("gray", "binary", "segments", "dxf_bytes", "overlay_png", "n_segments"):
        assert key in res, f"nedostaje kljuc: {key}"

    assert isinstance(res["gray"], np.ndarray)
    assert res["gray"].ndim == 2
    assert isinstance(res["binary"], np.ndarray)
    assert res["binary"].ndim == 2
    assert res["binary"].dtype == bool
    assert isinstance(res["segments"], list)
    assert isinstance(res["dxf_bytes"], bytes) and len(res["dxf_bytes"]) > 0
    assert isinstance(res["overlay_png"], bytes) and len(res["overlay_png"]) > 0

    # bar par zidnih linija okvira detektirano
    assert res["n_segments"] >= 2
    assert res["n_segments"] == len(res["segments"])

    # DXF se ucita natrag i ima barem jedan LINE entitet
    doc = _read_dxf_bytes(res["dxf_bytes"])
    lines = _lines(doc)
    assert len(lines) >= 1


def test_vectorize_floorplan_defaults():
    png = _framed_plan_png()
    res = r.vectorize_floorplan(png, "plan.png", None)  # params=None ne smije baciti
    assert isinstance(res, dict)
    for key in ("gray", "binary", "segments", "dxf_bytes", "overlay_png", "n_segments"):
        assert key in res, f"nedostaje kljuc: {key}"



def test_vectorize_empty_input():
    # Prazan ulaz ne smije baciti; ok=False, warning ne-None, 0 segmenata.
    res = r.vectorize_floorplan(b"", "x.png")
    assert isinstance(res, dict)
    assert res["ok"] is False
    assert res["warning"] is not None
    assert res["n_segments"] == 0
    assert res["segments"] == []


def test_vectorize_bad_format():
    # Nepodrzan format (.txt) -> ne baca; ok=False; warning naznacuje gresku.
    res = r.vectorize_floorplan(b"nesto", "x.txt")
    assert isinstance(res, dict)
    assert res["ok"] is False
    assert res["warning"] is not None
    low = res["warning"].lower()
    assert ("format" in low) or ("greska" in low)
    assert res["n_segments"] == 0


def test_vectorize_blank_image_zero_segments():
    # Potpuno bijela slika (nema linija) -> ok=True, 0 segmenata, warning ne-None.
    arr = np.full((120, 160), 255, dtype=np.uint8)
    png = _png_bytes(arr)
    res = r.vectorize_floorplan(png, "blank.png")
    assert res["ok"] is True
    assert res["n_segments"] == 0
    assert res["warning"] is not None
    # DXF je valjan i ucita se natrag s 0 LINE entiteta.
    assert isinstance(res["dxf_bytes"], bytes) and len(res["dxf_bytes"]) > 0
    doc = _read_dxf_bytes(res["dxf_bytes"])
    assert len(_lines(doc)) == 0


def test_vectorize_corrupt_pdf():
    # Ostecen PDF -> ne baca; ok=False; warning ne-None.
    res = r.vectorize_floorplan(b"%PDF-1.4 garbage", "x.pdf")
    assert isinstance(res, dict)
    assert res["ok"] is False
    assert res["warning"] is not None
    assert res["n_segments"] == 0
