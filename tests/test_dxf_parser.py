"""tests/test_dxf_parser.py — v2"""

import math, sys, os, re, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from phase2_dxf import (
    _polygon_centroid, _polygon_area, _bounding_box, _classify_polyline,
    _is_closed_lwpoly, _lwpoly_verts,
    extract_all_dimension_texts, collect_closed_polylines,
    associate_and_classify, detect_floor_layers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_doc(entities_fn):
    try:
        import ezdxf
    except ImportError:
        pytest.skip("ezdxf not installed")
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    entities_fn(doc, msp)
    return doc, msp


def _basic_doc():
    def _add(doc, msp):
        # Column: closed square 50×50 centred at (100, 200)
        msp.add_lwpolyline(
            [(75,175),(125,175),(125,225),(75,225)],
            close=True, dxfattribs={"layer": "FLOOR_1"},
        )
        # Beam: long thin rectangle 200×30 centred at (300, 100)
        msp.add_lwpolyline(
            [(200,85),(400,85),(400,115),(200,115)],
            close=True, dxfattribs={"layer": "FLOOR_1"},
        )
        # Wall: similar long thin shape but annotated with thickness
        msp.add_lwpolyline(
            [(500,50),(700,50),(700,70),(500,70)],
            close=True, dxfattribs={"layer": "FLOOR_2"},
        )
        # Slab: large area > 4 m² at scale 0.01
        # side = 300 DXF → 3m at 0.01 scale, but 3×3=9 m²  > slab_min_area_m2=4 ✓
        msp.add_lwpolyline(
            [(0,0),(300,0),(300,300),(0,300)],
            close=True, dxfattribs={"layer": "FLOOR_1"},
        )
        # Dimension texts
        msp.add_text("30x50", dxfattribs={"insert":(100,210),"height":8,"layer":"FLOOR_1"})
        msp.add_text("20x30", dxfattribs={"insert":(300,105),"height":8,"layer":"FLOOR_1"})
        msp.add_text("t=20",  dxfattribs={"insert":(600,60), "height":8,"layer":"FLOOR_2"})
        msp.add_text("Ø40",   dxfattribs={"insert":(100,210),"height":8,"layer":"FLOOR_1"})
        # Floor layers
        doc.layers.new("FLOOR_1")
        doc.layers.new("FLOOR_2")
    return _make_doc(_add)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

class TestPolygonCentroid:
    def test_square(self):
        cx, cy = _polygon_centroid([(0,0),(4,0),(4,4),(0,4)])
        assert abs(cx-2)<1e-6 and abs(cy-2)<1e-6

    def test_offset_square(self):
        cx, cy = _polygon_centroid([(75,175),(125,175),(125,225),(75,225)])
        assert abs(cx-100)<1e-6 and abs(cy-200)<1e-6

    def test_triangle(self):
        cx, cy = _polygon_centroid([(0,0),(6,0),(3,6)])
        assert abs(cx-3)<1e-6 and abs(cy-2)<1e-6

    def test_degenerate(self):
        assert _polygon_centroid([(0,0),(1,0)]) is None

    def test_collinear(self):
        assert _polygon_centroid([(0,0),(1,0),(2,0)]) is None


class TestPolygonArea:
    def test_square(self):
        assert abs(_polygon_area([(0,0),(4,0),(4,4),(0,4)]) - 16) < 1e-6

    def test_rectangle(self):
        assert abs(_polygon_area([(0,0),(10,0),(10,4),(0,4)]) - 40) < 1e-6


class TestBoundingBox:
    def test_basic(self):
        xmin,ymin,xmax,ymax = _bounding_box([(0,0),(4,0),(4,3),(0,3)])
        assert (xmin,ymin,xmax,ymax) == (0,0,4,3)


# ---------------------------------------------------------------------------
# Polyline classification
# ---------------------------------------------------------------------------

class TestClassifyPolyline:
    def _poly(self, verts, scale=0.01):
        area = _polygon_area(verts)
        xmin,ymin,xmax,ymax = _bounding_box(verts)
        w = xmax-xmin; h = ymax-ymin
        aspect = max(w,h)/max(min(w,h),1e-3)
        return {"area_dxf":area,"width_dxf":w,"height_dxf":h,"aspect_ratio":aspect}

    def test_small_square_is_column(self):
        # 50×50 DXF @ 0.01 → 0.5×0.5 m → area=0.25 m² < slab_min, aspect~1 < beam_thresh
        p = self._poly([(0,0),(50,0),(50,50),(0,50)])
        assert _classify_polyline(p, 0.01, Config()) == "column"

    def test_long_thin_is_beam(self):
        # 200×30 DXF @ 0.01 → small area, high aspect
        p = self._poly([(0,0),(200,0),(200,30),(0,30)])
        assert _classify_polyline(p, 0.01, Config()) == "beam"

    def test_large_area_is_slab(self):
        # 300×300 DXF @ 0.01 → 3×3 = 9 m² > slab_min=4
        p = self._poly([(0,0),(300,0),(300,300),(0,300)])
        assert _classify_polyline(p, 0.01, Config()) == "slab"


# ---------------------------------------------------------------------------
# Floor layer detection
# ---------------------------------------------------------------------------

class TestFloorLayerDetection:
    def test_detects_floor_layers(self):
        doc, msp = _basic_doc()
        floor_map = detect_floor_layers(doc, Config())
        assert "FLOOR_1" in floor_map or "FLOOR_2" in floor_map

    def test_fallback_to_all(self):
        def _no_floors(doc, msp):
            msp.add_text("30x50", dxfattribs={"insert":(0,0),"height":5})
        doc, msp = _make_doc(_no_floors)
        floor_map = detect_floor_layers(doc, Config())
        assert "ALL" in floor_map


# ---------------------------------------------------------------------------
# Dimension text extraction
# ---------------------------------------------------------------------------

class TestDimensionTextExtraction:
    def test_finds_rect(self):
        doc, msp = _basic_doc()
        texts = extract_all_dimension_texts(msp, Config())
        hits = [t for t in texts if t["hint_type"] == "rect"]
        assert len(hits) >= 1

    def test_finds_thickness(self):
        doc, msp = _basic_doc()
        texts = extract_all_dimension_texts(msp, Config())
        hits = [t for t in texts if t["hint_type"] == "thickness"]
        assert len(hits) >= 1, f"thickness not found; got: {[t['dim_text'] for t in texts]}"

    def test_finds_circular(self):
        doc, msp = _basic_doc()
        texts = extract_all_dimension_texts(msp, Config())
        hits = [t for t in texts if t["hint_type"] == "circ"]
        assert len(hits) >= 1, f"circ not found; got: {[t['dim_text'] for t in texts]}"

    def test_dims_extracted_correctly(self):
        doc, msp = _basic_doc()
        texts = extract_all_dimension_texts(msp, Config())
        rect_hits = [t for t in texts if t["hint_type"]=="rect" and "30" in t["dim_text"]]
        assert rect_hits, "30x50 not extracted"
        h = rect_hits[0]
        assert h["dim1"] in (30.0, 50.0)
        assert h["dim2"] in (30.0, 50.0)


def test_regex_variants():
    """All dimension regex formats."""
    from config import DEFAULT_CONFIG
    RECT  = re.compile(DEFAULT_CONFIG.rect_section_regex)
    CIRC  = re.compile(DEFAULT_CONFIG.circ_section_regex)
    THICK = re.compile(DEFAULT_CONFIG.thickness_regex)

    for text, pat in [
        ("30x50",   RECT), ("30X50",   RECT), ("30/50", RECT),
        ("300×500", RECT), ("30 x 50", RECT),
        ("d=40",    CIRC), ("D=400",   CIRC), ("Ø40", CIRC), ("φ40", CIRC),
        ("t=20",    THICK),("h=20",    THICK),("20cm", THICK),
    ]:
        assert pat.search(text), f"No match for '{text}'"


# ---------------------------------------------------------------------------
# Closed polyline collection
# ---------------------------------------------------------------------------

class TestClosedPolylines:
    def test_finds_closed(self):
        doc, msp = _basic_doc()
        polys = collect_closed_polylines(msp)
        assert len(polys) >= 3  # column + beam + wall + slab

    def test_centroid_correct(self):
        doc, msp = _basic_doc()
        polys = collect_closed_polylines(msp)
        centroids = {(round(p["centroid_x"]), round(p["centroid_y"])) for p in polys}
        assert (100, 200) in centroids, f"Column centroid missing: {centroids}"


# ---------------------------------------------------------------------------
# Association
# ---------------------------------------------------------------------------

class TestAssociation:
    def test_elements_produced(self):
        doc, msp = _basic_doc()
        cfg = Config(max_text_to_poly_distance=200, dxf_unit_scale=0.01)
        texts = extract_all_dimension_texts(msp, cfg)
        polys = collect_closed_polylines(msp)
        from phase2_dxf import detect_floor_layers
        floor_map = detect_floor_layers(doc, cfg)
        elements = associate_and_classify(texts, polys, [], floor_map, cfg)
        assert len(elements) >= 1

    def test_coordinates_scaled(self):
        doc, msp = _basic_doc()
        cfg = Config(max_text_to_poly_distance=200, dxf_unit_scale=0.01)
        texts = extract_all_dimension_texts(msp, cfg)
        polys = collect_closed_polylines(msp)
        from phase2_dxf import detect_floor_layers
        floor_map = detect_floor_layers(doc, cfg)
        elements = associate_and_classify(texts, polys, [], floor_map, cfg)
        # Column centroid at DXF(100,200) with scale=0.01 → (1.0, 2.0) m
        xs = [e["centroid_x_m"] for e in elements]
        ys = [e["centroid_y_m"] for e in elements]
        assert any(abs(x-1.0)<0.1 for x in xs), f"Scaled X not ~1.0: {xs}"
        assert any(abs(y-2.0)<0.1 for y in ys), f"Scaled Y not ~2.0: {ys}"

    def test_dims_converted_to_mm(self):
        doc, msp = _basic_doc()
        cfg = Config(max_text_to_poly_distance=200, dxf_unit_scale=0.01)
        texts = extract_all_dimension_texts(msp, cfg)
        polys = collect_closed_polylines(msp)
        from phase2_dxf import detect_floor_layers
        floor_map = detect_floor_layers(doc, cfg)
        elements = associate_and_classify(texts, polys, [], floor_map, cfg)
        # "30x50" → dim1=30, dim2=50 → after <100 rule: 300mm, 500mm
        d1s = [e["dim1_mm"] for e in elements if e.get("dim1_mm")]
        assert any(abs(d-300)<1 or abs(d-500)<1 for d in d1s), f"mm conversion wrong: {d1s}"
