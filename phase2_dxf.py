"""
phase2_dxf.py
-------------
Heuristic DXF parsing for ALL structural element types in a single multi-floor file.

Pipeline
--------
1. Floor layer detection  — auto-detect floor layers by name patterns
2. Grid reconstruction    — long lines + grid bubbles → named axes
3. Element text scan      — regex match dimension annotations (rect / circ / thickness)
4. Polyline association   — nearest closed polyline → centroid per text match
5. Element classification — column / beam / wall / slab by polyline geometry heuristics
6. Output                 — unified DataFrame with element_type, floor_label, centroid_m, dims_mm
"""

from __future__ import annotations

import logging
import math
import re
from typing import Optional

import pandas as pd

try:
    import ezdxf
    from ezdxf import recover
except ImportError:
    raise ImportError("ezdxf is required. Run: pip install ezdxf")

from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _dist(ax, ay, bx, by):  return math.sqrt((bx-ax)**2 + (by-ay)**2)
def _dist2(ax, ay, bx, by): return (bx-ax)**2 + (by-ay)**2


def _polygon_centroid(verts: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
    n = len(verts)
    if n < 3: return None
    area = cx = cy = 0.0
    for i in range(n):
        x0, y0 = verts[i]; x1, y1 = verts[(i+1) % n]
        cross = x0*y1 - x1*y0
        area += cross; cx += (x0+x1)*cross; cy += (y0+y1)*cross
    area *= 0.5
    if abs(area) < 1e-12: return None
    return cx/(6*area), cy/(6*area)


def _polygon_area(verts: list[tuple[float, float]]) -> float:
    n = len(verts)
    if n < 3: return 0.0
    a = sum(verts[i][0]*verts[(i+1)%n][1] - verts[(i+1)%n][0]*verts[i][1]
            for i in range(n))
    return abs(a) * 0.5


def _bounding_box(verts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]
    return min(xs), min(ys), max(xs), max(ys)


def _line_length(e) -> float:
    return _dist(e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y)


def _lwpoly_verts(e) -> list[tuple[float, float]]:
    """Return 2D vertices in WCS from a LWPOLYLINE entity."""
    try:
        pts_wcs = list(e.vertices_in_wcs())
        return [(p.x, p.y) for p in pts_wcs]
    except Exception:
        return [(p[0], p[1]) for p in e]


def _is_closed_lwpoly(e) -> bool:
    closed = getattr(e, "is_closed", None) or getattr(e, "closed", False)
    if not closed:
        pts = [(p[0], p[1]) for p in e]
        if len(pts) >= 3 and _dist2(*pts[0], *pts[-1]) < 1.0:
            return True
    return closed


# ---------------------------------------------------------------------------
# Step 1 — Floor layer detection
# ---------------------------------------------------------------------------

def detect_floor_layers(doc, cfg: Config) -> dict[str, list[str]]:
    """
    Scan DXF layers for floor-indicator names.

    Returns: {floor_label: [layer_name, ...]}
    If no floor layers found, returns {"ALL": []}  (treat whole file as one plan).
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in cfg.floor_layer_patterns]
    floor_map: dict[str, list[str]] = {}

    for layer in doc.layers:
        name = layer.dxf.name
        for pat in compiled:
            if pat.search(name):
                # Use the matched group (e.g. "FLOOR_3" → label "FLOOR_3")
                floor_map.setdefault(name, []).append(name)
                break

    if not floor_map:
        log.info("No floor layers detected — treating entire DXF as a single plan.")
        return {"ALL": []}

    log.info("Floor layers detected: %s", list(floor_map.keys()))
    return floor_map


def _layer_to_floor(layer_name: str, floor_map: dict[str, list[str]]) -> str:
    """Map a DXF layer name to its floor label."""
    if "ALL" in floor_map:
        return "ALL"
    for floor_label, layers in floor_map.items():
        if layer_name in layers or floor_label == layer_name:
            return floor_label
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Step 2 — Grid reconstruction
# ---------------------------------------------------------------------------

def reconstruct_grid(msp, cfg: Config) -> list[dict]:
    """Find structural grid axes from long lines near labeled circles."""
    circles = [
        {"cx": e.dxf.center.x, "cy": e.dxf.center.y, "r": e.dxf.radius}
        for e in msp.query("CIRCLE")
    ]
    GRID_RE = re.compile(r"^[A-Za-z]{1,3}$|^\d{1,3}$")
    texts = []
    for e in msp.query("TEXT MTEXT"):
        raw = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        raw = raw.strip()
        if GRID_RE.match(raw):
            pos = e.dxf.insert
            texts.append({"x": pos.x, "y": pos.y, "label": raw})

    r2 = cfg.grid_circle_search_radius ** 2
    grid_lines = []
    for e in msp.query("LINE"):
        if _line_length(e) < cfg.min_grid_line_length:
            continue
        sx, sy = e.dxf.start.x, e.dxf.start.y
        ex, ey = e.dxf.end.x, e.dxf.end.y
        for c in circles:
            if _dist2(sx, sy, c["cx"], c["cy"]) <= r2 or \
               _dist2(ex, ey, c["cx"], c["cy"]) <= r2:
                label = min(texts, key=lambda t: _dist2(t["x"], t["y"], c["cx"], c["cy"]),
                            default={"label": "?"})["label"] if texts else "?"
                grid_lines.append({
                    "label": label, "circle_cx": c["cx"], "circle_cy": c["cy"],
                    "length": _line_length(e), "line_entity": e,
                })
                break
    log.info("Grid lines found: %d", len(grid_lines))
    return grid_lines


# ---------------------------------------------------------------------------
# Step 3 — Dimension text extraction (multi-type)
# ---------------------------------------------------------------------------

def _clean_mtext(e) -> str:
    try:
        return e.plain_text()
    except Exception:
        try:
            return e.dxf.text
        except Exception:
            return ""


def extract_all_dimension_texts(msp, cfg: Config) -> list[dict]:
    """
    Scan all TEXT/MTEXT for any dimension annotation.
    Tries rectangular, circular, and thickness patterns.
    Returns list of dicts: {x, y, dim_text, hint_type, dim1, dim2, layer}
    hint_type: "rect", "circ", "thickness"
    """
    RECT_RE  = re.compile(cfg.rect_section_regex)
    CIRC_RE  = re.compile(cfg.circ_section_regex)
    THICK_RE = re.compile(cfg.thickness_regex)

    results = []
    for e in msp.query("TEXT MTEXT"):
        raw = _clean_mtext(e) if e.dxftype() == "MTEXT" else e.dxf.text
        raw = raw.strip()
        pos = e.dxf.insert
        layer = getattr(e.dxf, "layer", "0")

        matched = False

        # 1. Rectangular (e.g. 30x50, 30/50, 300x500)
        for m in RECT_RE.finditer(raw):
            results.append({
                "x": pos.x, "y": pos.y,
                "dim_text": m.group(0),
                "hint_type": "rect",
                "dim1": float(m.group(1)),
                "dim2": float(m.group(2)),
                "layer": layer,
            })
            matched = True

        if matched:
            continue

        # 2. Thickness (e.g. t=20, d=20, h=20, 20cm) - check before circular
        for m in THICK_RE.finditer(raw):
            val = m.group(1) or m.group(2)
            if val:
                results.append({
                    "x": pos.x, "y": pos.y,
                    "dim_text": m.group(0),
                    "hint_type": "thickness",
                    "dim1": float(val),
                    "dim2": float(val),
                    "layer": layer,
                })
                matched = True

        if matched:
            continue

        # 3. Circular (e.g. Ø40, φ40, D=400)
        for m in CIRC_RE.finditer(raw):
            results.append({
                "x": pos.x, "y": pos.y,
                "dim_text": m.group(0),
                "hint_type": "circ",
                "dim1": float(m.group(1)),
                "dim2": float(m.group(1)),
                "layer": layer,
            })

    log.info("Dimension text annotations found: %d", len(results))
    return results


# ---------------------------------------------------------------------------
# Step 4 — Closed polyline collection
# ---------------------------------------------------------------------------

def collect_closed_polylines(msp) -> list[dict]:
    """
    Collect all closed LWPOLYLINE and legacy POLYLINE entities.
    Returns list of {centroid_x, centroid_y, verts, area_dxf, aspect_ratio, entity}
    """
    polys = []

    # LWPOLYLINE
    for e in msp.query("LWPOLYLINE"):
        if not _is_closed_lwpoly(e):
            continue
        verts = _lwpoly_verts(e)
        if len(verts) < 3:
            continue
        # Remove repeated closing vertex
        if _dist2(*verts[0], *verts[-1]) < 1.0:
            verts = verts[:-1]
        cen = _polygon_centroid(verts)
        if cen is None:
            continue
        area = _polygon_area(verts)
        xmin, ymin, xmax, ymax = _bounding_box(verts)
        w = xmax - xmin; h = ymax - ymin
        aspect = max(w, h) / max(min(w, h), 1e-3)
        polys.append({
            "centroid_x": cen[0], "centroid_y": cen[1],
            "verts": verts, "area_dxf": area,
            "width_dxf": w, "height_dxf": h,
            "aspect_ratio": aspect,
            "layer": getattr(e.dxf, "layer", "0"),
            "entity": e,
        })

    # Legacy POLYLINE (R12)
    for e in msp.query("POLYLINE"):
        try:
            verts_3d = [v.dxf.location for v in e.vertices]
        except Exception:
            continue
        verts = [(v.x, v.y) for v in verts_3d]
        closed = bool(getattr(e.dxf, "flags", 0) & 1)
        if not closed and len(verts) >= 3 and _dist2(*verts[0], *verts[-1]) < 1.0:
            verts = verts[:-1]; closed = True
        if not closed or len(verts) < 3:
            continue
        cen = _polygon_centroid(verts)
        if cen is None:
            continue
        area = _polygon_area(verts)
        xmin, ymin, xmax, ymax = _bounding_box(verts)
        w = xmax - xmin; h = ymax - ymin
        aspect = max(w, h) / max(min(w, h), 1e-3)
        polys.append({
            "centroid_x": cen[0], "centroid_y": cen[1],
            "verts": verts, "area_dxf": area,
            "width_dxf": w, "height_dxf": h,
            "aspect_ratio": aspect,
            "layer": getattr(e.dxf, "layer", "0"),
            "entity": e,
        })

    log.info("Closed polylines found: %d", len(polys))
    return polys


# ---------------------------------------------------------------------------
# Step 5 — Classify polyline by geometry
# ---------------------------------------------------------------------------

def _classify_polyline(poly: dict, scale: float, cfg: Config) -> str:
    """
    Classify a closed polyline as column / beam / wall / slab based on
    its geometry (area, aspect ratio).

    Returns: "column" | "beam" | "wall" | "slab" | "unknown"
    """
    area_m2   = poly["area_dxf"] * scale * scale
    aspect    = poly["aspect_ratio"]

    if area_m2 > cfg.slab_min_area_m2:
        return "slab"

    if aspect >= cfg.beam_aspect_ratio_threshold:
        # Long and thin — could be beam outline or wall
        if area_m2 < 2.5:
            return "beam"
        return "wall"

    # Roughly square / rectangular and small → column
    return "column"


# ---------------------------------------------------------------------------
# Step 6 — Associate texts to polylines and finalise
# ---------------------------------------------------------------------------

def _nearest_grid_label(cx, cy, grid_lines, max_dist) -> str:
    best, best_d2 = "", max_dist**2
    for gl in grid_lines:
        d2 = _dist2(cx, cy, gl["circle_cx"], gl["circle_cy"])
        if d2 < best_d2:
            best_d2 = d2; best = gl["label"]
    return best


def associate_and_classify(
    dim_texts:   list[dict],
    closed_polys: list[dict],
    grid_lines:  list[dict],
    floor_map:   dict[str, list[str]],
    cfg: Config,
) -> list[dict]:
    """
    For each dimension text: find nearest closed polyline, classify it,
    convert coordinates to metres.
    """
    scale  = cfg.dxf_unit_scale
    ox, oy = cfg.dxf_origin_offset
    max_d2 = cfg.max_text_to_poly_distance ** 2

    elements = []
    
    # 1. Collect all valid (distance, text_idx, poly_idx) candidate pairs
    candidates = []
    for t_idx, st in enumerate(dim_texts):
        tx, ty = st["x"], st["y"]
        for p_idx, poly in enumerate(closed_polys):
            d2 = _dist2(tx, ty, poly["centroid_x"], poly["centroid_y"])
            if d2 <= max_d2:
                candidates.append((d2, t_idx, p_idx))

    # Sort so closest text-to-contour pairs are matched first
    candidates.sort(key=lambda x: x[0])

    assigned_texts = set()
    assigned_polys = set()

    def to_mm(v):
        if v is None: return None
        return v * 10 if v < 100 else v

    # 2. Assign closest pairs 1-to-1
    for d2, t_idx, p_idx in candidates:
        if t_idx in assigned_texts or p_idx in assigned_polys:
            continue
        assigned_texts.add(t_idx)
        assigned_polys.add(p_idx)

        st = dim_texts[t_idx]
        poly = closed_polys[p_idx]
        cx_m = poly["centroid_x"] * scale + ox
        cy_m = poly["centroid_y"] * scale + oy

        floor_label = _layer_to_floor(poly["layer"], floor_map)
        geom_type = _classify_polyline(poly, scale, cfg)

        hint = st["hint_type"]
        if hint == "thickness" and geom_type in ("beam", "column"):
            geom_type = "wall"
        elif hint == "circ" and geom_type == "column":
            geom_type = "column"

        grid_ref = _nearest_grid_label(
            poly["centroid_x"], poly["centroid_y"],
            grid_lines, cfg.max_grid_label_distance
        )

        elements.append({
            "element_type":  geom_type,
            "centroid_x_m":  cx_m,
            "centroid_y_m":  cy_m,
            "dim_text":      st["dim_text"],
            "hint_type":     hint,
            "dim1_mm":       to_mm(st["dim1"]),
            "dim2_mm":       to_mm(st["dim2"]),
            "floor_label":   floor_label,
            "grid_ref":      grid_ref,
            "layer":         poly["layer"],
            "poly_area_m2":  round(poly["area_dxf"] * scale * scale, 4),
            "poly_aspect":   round(poly["aspect_ratio"], 2),
        })

    # 3. Handle any remaining unattached dimension texts (e.g. beam line tags)
    for t_idx, st in enumerate(dim_texts):
        if t_idx in assigned_texts:
            continue
        tx, ty = st["x"], st["y"]
        cx_m = tx * scale + ox
        cy_m = ty * scale + oy
        hint = st["hint_type"]
        geom_type = "beam" if hint == "rect" else ("wall" if hint == "thickness" else "column")
        floor_label = _layer_to_floor(st["layer"], floor_map)
        grid_ref = _nearest_grid_label(tx, ty, grid_lines, cfg.max_grid_label_distance)

        elements.append({
            "element_type":  geom_type,
            "centroid_x_m":  cx_m,
            "centroid_y_m":  cy_m,
            "dim_text":      st["dim_text"],
            "hint_type":     hint,
            "dim1_mm":       to_mm(st["dim1"]),
            "dim2_mm":       to_mm(st["dim2"]),
            "floor_label":   floor_label,
            "grid_ref":      grid_ref,
            "layer":         st["layer"],
            "poly_area_m2":  None,
            "poly_aspect":   None,
        })

    log.info("DXF elements associated: %d", len(elements))
    return elements


def extract_drawing_annotations(msp, cfg: Config) -> tuple[list[dict], list[dict], dict]:
    """
    Scan drawing text and title blocks for:
      - Concrete grades (e.g. C25/30, C30/37, MB 30)
      - Steel grades (e.g. S355, B500B)
      - Design loads (e.g. g=2.0 kN/m², q=3.0 kN/m²)
    """
    CONC_RE = re.compile(cfg.concrete_grade_regex, re.I)
    STEEL_RE = re.compile(cfg.steel_grade_regex, re.I)
    AREA_LOAD_RE = re.compile(cfg.area_load_regex, re.I)

    materials = []
    loads = []
    doc_summary = {"concrete": None, "steel": None}

    for e in msp.query("TEXT MTEXT"):
        raw = _clean_mtext(e) if e.dxftype() == "MTEXT" else getattr(e.dxf, "text", "")
        raw = raw.strip()
        pos = getattr(e.dxf, "insert", None)
        px = pos.x if pos else 0.0
        py = pos.y if pos else 0.0

        for m in CONC_RE.finditer(raw):
            val = m.group(0).replace(" ", "").upper()
            materials.append({"x": px, "y": py, "mat": val, "type": "concrete"})
            if not doc_summary["concrete"]:
                doc_summary["concrete"] = val

        for m in STEEL_RE.finditer(raw):
            val = m.group(0).replace(" ", "").upper()
            materials.append({"x": px, "y": py, "mat": val, "type": "steel"})
            if not doc_summary["steel"]:
                doc_summary["steel"] = val

        for m in AREA_LOAD_RE.finditer(raw):
            matched_txt = m.group(0)
            val = float(m.group(1))
            tag = "g" if any(k in matched_txt.lower() for k in ("g", "gk", "δg", "staln")) else "q"
            loads.append({"x": px, "y": py, "load_tag": tag, "val_kpa": val, "text": matched_txt})

    log.info("Drawing annotations: %d materials, %d loads found. General spec: %s",
             len(materials), len(loads), doc_summary)
    return materials, loads, doc_summary


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def parse_dxf(path: str, cfg: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """
    Parse a 2D structural DXF drawing (all floors in one file).

    Returns
    -------
    pd.DataFrame with columns:
        element_type, centroid_x_m, centroid_y_m,
        dim_text, hint_type, dim1_mm, dim2_mm,
        floor_label, grid_ref, layer, poly_area_m2, poly_aspect,
        dxf_material, dxf_load_g_kpa, dxf_load_q_kpa
    """
    log.info("Loading DXF: %s", path)
    try:
        doc, _ = recover.readfile(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to read DXF '{path}': {exc}") from exc

    msp = doc.modelspace()

    floor_map    = detect_floor_layers(doc, cfg)
    grid_lines   = reconstruct_grid(msp, cfg)
    dim_texts    = extract_all_dimension_texts(msp, cfg)
    closed_polys = collect_closed_polylines(msp)
    elements     = associate_and_classify(dim_texts, closed_polys, grid_lines, floor_map, cfg)

    # Extract materials and loads from drawing notes
    ann_mats, ann_loads, doc_mats = extract_drawing_annotations(msp, cfg)
    scale = cfg.dxf_unit_scale
    ox, oy = cfg.dxf_origin_offset
    load_search_d2 = (cfg.max_text_to_poly_distance * 3) ** 2
    mat_search_d2 = (cfg.max_text_to_poly_distance * 2) ** 2

    for el in elements:
        ex_dxf = (el["centroid_x_m"] - ox) / scale
        ey_dxf = (el["centroid_y_m"] - oy) / scale

        # Material association
        best_mat = None
        best_mat_d2 = mat_search_d2
        for m in ann_mats:
            d2 = _dist2(ex_dxf, ey_dxf, m["x"], m["y"])
            if d2 < best_mat_d2:
                best_mat_d2 = d2
                best_mat = m["mat"]
        el["dxf_material"] = best_mat or doc_mats.get("concrete")

        # Load association (for slabs)
        el["dxf_load_g_kpa"] = None
        el["dxf_load_q_kpa"] = None
        if el["element_type"] == "slab":
            for ld in ann_loads:
                d2 = _dist2(ex_dxf, ey_dxf, ld["x"], ld["y"])
                if d2 <= load_search_d2:
                    if ld["load_tag"] == "g" and el["dxf_load_g_kpa"] is None:
                        el["dxf_load_g_kpa"] = ld["val_kpa"]
                    elif ld["load_tag"] == "q" and el["dxf_load_q_kpa"] is None:
                        el["dxf_load_q_kpa"] = ld["val_kpa"]

    df = pd.DataFrame(elements)
    df.attrs["doc_materials"] = doc_mats
    if df.empty:
        log.warning(
            "No elements extracted. Check:\n"
            "  - cfg.dxf_unit_scale (mm=0.001, cm=0.01, m=1.0)\n"
            "  - cfg.max_text_to_poly_distance\n"
            "  - run with --dxf-only --plot to inspect visually"
        )
    else:
        log.info("Elements by type:")
        for t, grp in df.groupby("element_type"):
            log.info("  %-10s %d", t, len(grp))

    return df


# ---------------------------------------------------------------------------
# Debug plot
# ---------------------------------------------------------------------------

def debug_plot(dxf_path: str, df: pd.DataFrame, cfg: Config = DEFAULT_CONFIG) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        log.error("matplotlib required: pip install matplotlib"); return

    TYPE_COLORS = {
        "column": "red", "beam": "blue", "wall": "green",
        "slab": "orange", "unknown": "gray",
    }

    doc, _ = recover.readfile(dxf_path)
    msp = doc.modelspace()
    scale  = cfg.dxf_unit_scale
    ox, oy = cfg.dxf_origin_offset

    fig, ax = plt.subplots(figsize=(16, 12))

    for e in msp.query("LWPOLYLINE"):
        if _is_closed_lwpoly(e):
            pts = _lwpoly_verts(e)
            xs = [p[0] for p in pts] + [pts[0][0]]
            ys = [p[1] for p in pts] + [pts[0][1]]
            ax.plot(xs, ys, "k-", lw=0.4, alpha=0.3)

    for e in msp.query("LINE"):
        if _line_length(e) >= cfg.min_grid_line_length:
            ax.plot([e.dxf.start.x, e.dxf.end.x],
                    [e.dxf.start.y, e.dxf.end.y], "b-", lw=0.6, alpha=0.25)

    if not df.empty:
        for _, row in df.iterrows():
            color = TYPE_COLORS.get(str(row.get("element_type", "")), "gray")
            cx_dxf = (row["centroid_x_m"] - ox) / scale
            cy_dxf = (row["centroid_y_m"] - oy) / scale
            ax.scatter(cx_dxf, cy_dxf, c=color, s=50, zorder=5)
            ax.annotate(f"{row['element_type']}\n{row['dim_text']}",
                        (cx_dxf, cy_dxf), fontsize=5, color=color)

    patches = [mpatches.Patch(color=c, label=t) for t, c in TYPE_COLORS.items()]
    ax.legend(handles=patches, fontsize=8)
    ax.set_aspect("equal")
    ax.set_title(f"DXF Debug — {dxf_path}")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python phase2_dxf.py <drawing.dxf> [--plot]")
        sys.exit(1)
    df = parse_dxf(sys.argv[1])
    print(df.to_string())
    df.to_csv("dxf_elements.csv", index=False)
    if "--plot" in sys.argv:
        debug_plot(sys.argv[1], df)
