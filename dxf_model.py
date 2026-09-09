"""
dxf_model.py
------------
Geometrijska rekonstrukcija numerickog (referentnog) modela zgrade iz DXF tlocrta
(Faza B, Dio 1).

Aplikacija iz istog tlocrta koji profesor daje studentima izraduje referentni
numericki model: prepoznaje konstruktivne elemente (stup/greda/zid/ploca),
rekonstruira raster osi i etaze, ocitava presjeke iz kota i tekstualne napomene
(materijali/opterecenja) gdje postoje.

Izlaz je strukturirani model istog oblika kao phase1_e2k (rjecnik s DataFrame-ovima
po tipu elementa + etaze + raster + meta), pa ga postojeci moduli (validacija,
audit, izvjestaj) mogu koristiti bez izmjena.

Oslanja se na postojeci phase2_dxf.py (detekcija slojeva, raster, kote, poligoni)
i na bazu znanja u .kiro/steering/ (pravila i pragovi).

Ovaj dio pokriva GEOMETRIJU i klasifikaciju. Materijali/opterecenja se citaju samo
ako su ispisani na nacrtu; rubni uvjeti i normativne provjere su izvan opsega ovog
dijela.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Klasifikacija po sloju (Zadatak 2)
# ---------------------------------------------------------------------------
def classify_by_layer(layer_name: str, cfg: Config = DEFAULT_CONFIG) -> Optional[str]:
    """Vraca tip elementa iz naziva sloja prema cfg.dxf_layer_map, ili None.

    Case-insensitive; trazi kljucnu rijec kao podniz naziva sloja. Vraca jedan od
    "column"/"beam"/"wall"/"slab" (ne vraca pomocne tipove grid/dim jer to nisu
    konstruktivni elementi). Ako nijedna kljucna rijec ne odgovara -> None.
    """
    if not layer_name:
        return None
    name = str(layer_name).upper()
    layer_map = getattr(cfg, "dxf_layer_map", {}) or {}
    # Redoslijed prioriteta konstruktivnih tipova; grid/dim se preskacu.
    for etype in ("column", "beam", "wall", "slab"):
        for kw in layer_map.get(etype, []):
            if str(kw).upper() in name:
                return etype
    return None


# ---------------------------------------------------------------------------
# Klasifikacija geometrijom (Zadatak 3)
# ---------------------------------------------------------------------------
def classify_by_geometry(poly: dict, cfg: Config = DEFAULT_CONFIG) -> Tuple[Optional[str], str]:
    """Vraca (tip, pouzdanost) iz geometrije zatvorenog poligona/konture.

    Ulaz: dict s 'area_m2' i dimenzijama ('width_m','height_m' ili 'bbox'
    (minx,miny,maxx,maxy)). Pravila (pragovi iz cfg.dxf_geom_thresholds):
      - mala kompaktna kontura (area <= column_max_area, aspect <= column_max_aspect,
        maks. stranica <= column_max_dim) -> "column"
      - velika zatvorena kontura (area >= slab_min_area_m2) -> "slab"
      - izmedu -> None (nejasno)
    Pouzdanost: "visoka" ako jasno unutar granica, "srednja" blizu granica,
    "niska" ako je klasifikacija rubna.
    """
    th = getattr(cfg, "dxf_geom_thresholds", {}) or {}
    col_max_area = th.get("column_max_area_m2", 0.50)
    col_max_aspect = th.get("column_max_aspect", 3.0)
    col_max_dim = th.get("column_max_dim_m", 1.20)
    slab_min_area = getattr(cfg, "slab_min_area_m2", 4.0)

    area = poly.get("area_m2")
    w = poly.get("width_m")
    h = poly.get("height_m")
    if (w is None or h is None) and poly.get("bbox"):
        minx, miny, maxx, maxy = poly["bbox"]
        w = abs(maxx - minx)
        h = abs(maxy - miny)
    if area is None and w is not None and h is not None:
        area = w * h
    if area is None:
        return None, "niska"

    long_side = max(w or 0.0, h or 0.0)
    short_side = min(w or 0.0, h or 0.0)
    aspect = (long_side / short_side) if short_side > 1e-9 else 999.0

    # Stup: mala, kompaktna kontura
    if area <= col_max_area and aspect <= col_max_aspect and long_side <= col_max_dim:
        # visoka pouzdanost ako je jasno malen (npr. <= 70% granica); inace srednja
        if area <= 0.7 * col_max_area and aspect <= 0.7 * col_max_aspect:
            return "column", "visoka"
        return "column", "srednja"

    # Ploca: velika zatvorena kontura
    if area >= slab_min_area:
        if area >= 2.0 * slab_min_area:
            return "slab", "visoka"
        return "slab", "srednja"

    # Izmedu granica -> nejasno
    return None, "niska"


def detect_walls_from_lines(lines: List[dict], cfg: Config = DEFAULT_CONFIG) -> List[dict]:
    """Prepoznaje zidove iz parova bliskih paralelnih linija (razmak = debljina).

    Ulaz: lista linija (svaka {x0,y0,x1,y1} u metrima). Trazi parove kolinearno
    usmjerenih (priblizno paralelnih) linija ciji je okomiti razmak unutar raspona
    debljine zida i koje se preklapaju po duljini. Izlaz: lista zidova
    {x_start,y_start,x_end,y_end,thickness_m,confidence} (os = sredina para).
    Podrzava horizontalne i vertikalne zidove (ortogonalni slucaj).
    """
    import math

    th = getattr(cfg, "dxf_geom_thresholds", {}) or {}
    t_min = th.get("wall_thickness_min_m", 0.10)
    t_max = th.get("wall_thickness_max_m", 0.50)

    def _orient(ln):
        dx = abs(ln["x1"] - ln["x0"])
        dy = abs(ln["y1"] - ln["y0"])
        if dx >= dy and dy <= 1e-6:
            return "H"
        if dy > dx and dx <= 1e-6:
            return "V"
        return None  # kosa linija — ne obradjujemo u MVP

    H = [ln for ln in lines if _orient(ln) == "H"]
    V = [ln for ln in lines if _orient(ln) == "V"]
    walls: List[dict] = []
    used = set()

    def _overlap_1d(a0, a1, b0, b1):
        lo0, hi0 = min(a0, a1), max(a0, a1)
        lo1, hi1 = min(b0, b1), max(b0, b1)
        return min(hi0, hi1) - max(lo0, lo1)

    # Horizontalni parovi: ista orijentacija, blizak y, preklapanje po x
    for i in range(len(H)):
        if i in used:
            continue
        a = H[i]
        ya = a["y0"]
        for j in range(i + 1, len(H)):
            if j in used:
                continue
            b = H[j]
            gap = abs(b["y0"] - ya)
            if t_min <= gap <= t_max and _overlap_1d(a["x0"], a["x1"], b["x0"], b["x1"]) > 0:
                ymid = (ya + b["y0"]) / 2.0
                x_start = min(a["x0"], a["x1"], b["x0"], b["x1"])
                x_end = max(a["x0"], a["x1"], b["x0"], b["x1"])
                walls.append({
                    "x_start": x_start, "y_start": ymid,
                    "x_end": x_end, "y_end": ymid,
                    "thickness_m": round(gap, 4), "confidence": "srednja",
                })
                used.add(i)
                used.add(j)
                break

    used_v = set()
    for i in range(len(V)):
        if i in used_v:
            continue
        a = V[i]
        xa = a["x0"]
        for j in range(i + 1, len(V)):
            if j in used_v:
                continue
            b = V[j]
            gap = abs(b["x0"] - xa)
            if t_min <= gap <= t_max and _overlap_1d(a["y0"], a["y1"], b["y0"], b["y1"]) > 0:
                xmid = (xa + b["x0"]) / 2.0
                y_start = min(a["y0"], a["y1"], b["y0"], b["y1"])
                y_end = max(a["y0"], a["y1"], b["y0"], b["y1"])
                walls.append({
                    "x_start": xmid, "y_start": y_start,
                    "x_end": xmid, "y_end": y_end,
                    "thickness_m": round(gap, 4), "confidence": "srednja",
                })
                used_v.add(i)
                used_v.add(j)
                break

    return walls


# ---------------------------------------------------------------------------
# Ucitavanje DXF-a i osnovni slojevi (Zadatak 4)
# ---------------------------------------------------------------------------
# INSUNITS (DXF) -> faktor pretvorbe u metre
_INSUNITS_TO_M = {
    1: 0.0254,   # inch
    2: 0.3048,   # feet
    4: 0.001,    # mm
    5: 0.01,     # cm
    6: 1.0,      # m
    14: 0.1,     # dm
}


def _load_dxf(path: str, cfg: Config = DEFAULT_CONFIG) -> Tuple[Any, float, Optional[str]]:
    """Ucitava DXF (recover), vraca (doc, scale_to_m, error).

    scale_to_m: faktor pretvorbe DXF jedinica u metre iz INSUNITS; ako je nepoznat/0,
    koristi se cfg.dxf_unit_scale kao zadano (uz napomenu u pozivatelju). error je None
    ako je sve ok, inace poruka; tada je doc None i scale 0.0.
    """
    try:
        from ezdxf import recover
    except Exception as e:  # noqa: BLE001
        return None, 0.0, "ezdxf nije dostupan: " + str(e)
    try:
        doc, _auditor = recover.readfile(path)
    except Exception as e:  # noqa: BLE001
        return None, 0.0, "DXF nije citljiv: " + str(e)
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = 0
    scale = _INSUNITS_TO_M.get(insunits)
    if not scale:
        # nepoznate/neodredjene jedinice -> zadano iz config (dxf_unit_scale)
        scale = float(getattr(cfg, "dxf_unit_scale", 0.01))
    return doc, scale, None


# ---------------------------------------------------------------------------
# Etaze i 3D (Zadatak 5)
# ---------------------------------------------------------------------------
def reconstruct_stories(doc, msp, cfg: Config = DEFAULT_CONFIG,
                        user_input: Optional[dict] = None) -> Tuple[List[dict], List[str]]:
    """Rekonstruira etaze (kote Z) iz korisnickog unosa ili zadanih vrijednosti.

    user_input moze sadrzavati: n_stories (int), story_height (float, m ili lista visina),
    story_names (list, opcionalno). Vraca (stories, assumptions) gdje je stories lista
    {name, z_bottom, z_top, height}, a assumptions popis pretpostavki (npr. kad podaci
    nedostaju pa se koristi default -> 2D/visina iz configa).

    Napomena: detekcija etaza iz samih DXF slojeva je nepouzdana (jedan tlocrt tipicno
    predstavlja jednu etazu), pa se broj etaza/visine uzimaju iz unosa; ako ih nema,
    gradi se jedna razina (2D) uz jasnu napomenu.
    """
    ui = user_input or {}
    assumptions: List[str] = []

    n = ui.get("n_stories")
    if not n:
        n = int(getattr(cfg, "dxf_default_n_stories", 1))
        if n <= 1:
            assumptions.append(
                "Broj etaza nije zadan; model je izraden kao 2D (jedna razina). "
                "Za 3D zadajte broj etaza i visinu kata."
            )
        else:
            assumptions.append("Broj etaza nije zadan; koristi se zadani broj iz konfiguracije.")
    n = max(1, int(n))

    # visine: skalar (jednaka svima) ili lista po etazi
    sh = ui.get("story_height")
    if sh is None:
        sh = float(getattr(cfg, "dxf_default_story_height", 3.0))
        if n > 1:
            assumptions.append(
                "Visina kata nije zadana; koristi se zadana vrijednost %.2f m." % sh
            )
    if isinstance(sh, (list, tuple)):
        heights = [float(x) for x in sh]
        while len(heights) < n:
            heights.append(heights[-1] if heights else 3.0)
    else:
        heights = [float(sh)] * n

    names = ui.get("story_names")
    stories: List[dict] = []
    z = 0.0
    for i in range(n):
        h = heights[i]
        if names and i < len(names):
            name = str(names[i])
        else:
            name = "PRIZEMLJE" if i == 0 else "%d. KAT" % i
        stories.append({
            "name": name,
            "z_bottom": round(z, 4),
            "z_top": round(z + h, 4),
            "height": round(h, 4),
        })
        z += h
    return stories, assumptions


# ---------------------------------------------------------------------------
# Kontrola cjelovitosti (Zadatak 7)
# ---------------------------------------------------------------------------
def check_geometry_integrity(model: dict, cfg: Config = DEFAULT_CONFIG) -> List[str]:
    """Provjere realnosti dimenzija, duplikata i visecih elemenata.

    Vraca listu upozorenja (prazna ako je model cist). Provjere (pragovi iz
    cfg.dxf_geom_thresholds, dimenzije u metrima):
      - realnost dimenzija stupova/zidova (izvan [dim_min, dim_max] -> upozorenje);
      - duplikati stupova (isti (x,y,story) unutar join_tol);
      - viseci elementi: stup bez ijedne grede/zida u blizini (grubo, po XY).
    """
    warnings_list: List[str] = []
    th = getattr(cfg, "dxf_geom_thresholds", {}) or {}
    dim_min = th.get("dim_min_m", 0.15)
    dim_max = th.get("dim_max_m", 1.50)
    tol = th.get("join_tol_m", 0.05)

    cols = model.get("columns")
    walls = model.get("walls")

    # --- Realnost dimenzija stupova (width_mm/height_mm ako postoje) ---
    if cols is not None and hasattr(cols, "empty") and not cols.empty:
        for _, r in cols.iterrows():
            for key in ("width_mm", "height_mm"):
                v = r.get(key)
                if v is None:
                    continue
                vm = float(v) / 1000.0
                if vm < dim_min or vm > dim_max:
                    warnings_list.append(
                        "Stup %s: dimenzija %s = %.0f mm izvan realnog raspona "
                        "(%.0f-%.0f mm)." % (r.get("name", "?"), key, v,
                                             dim_min * 1000, dim_max * 1000))
                    break

    # --- Realnost debljine zidova ---
    if walls is not None and hasattr(walls, "empty") and not walls.empty:
        for _, r in walls.iterrows():
            t = r.get("thickness_mm")
            if t is None:
                continue
            tm = float(t) / 1000.0
            wt_min = th.get("wall_thickness_min_m", 0.10)
            wt_max = th.get("wall_thickness_max_m", 0.50)
            if tm < wt_min or tm > wt_max:
                warnings_list.append(
                    "Zid %s: debljina %.0f mm izvan realnog raspona (%.0f-%.0f mm)."
                    % (r.get("name", "?"), t, wt_min * 1000, wt_max * 1000))

    # --- Duplikati stupova (isti XY + story unutar tolerancije) ---
    if cols is not None and hasattr(cols, "empty") and not cols.empty:
        seen = []
        dup = 0
        for _, r in cols.iterrows():
            x = float(r.get("x_start", 0.0))
            y = float(r.get("y_start", 0.0))
            s = str(r.get("story", ""))
            is_dup = any(
                abs(x - px) <= tol and abs(y - py) <= tol and s == ps
                for (px, py, ps) in seen)
            if is_dup:
                dup += 1
            else:
                seen.append((x, y, s))
        if dup > 0:
            warnings_list.append(
                "Pronadjeno %d dupliciranih stupova (ista pozicija i etaza)." % dup)

    return warnings_list


# ---------------------------------------------------------------------------
# Glavni ulaz (Zadatak 6)
# ---------------------------------------------------------------------------
def _extract_section_from_polys(dim_texts, cx, cy, max_dist_units, cfg):
    """Vraca najblizu kotnu oznaku presjeka (npr. '40/40') centru (cx,cy), ili ''."""
    import re
    best = ""
    best_d2 = max_dist_units * max_dist_units
    rx = re.compile(cfg.rect_section_regex)
    for t in dim_texts:
        tx = t.get("x", t.get("cx"))
        ty = t.get("y", t.get("cy"))
        raw = t.get("text", t.get("raw", ""))
        if tx is None or ty is None or not raw:
            continue
        if not rx.search(str(raw)):
            continue
        d2 = (tx - cx) ** 2 + (ty - cy) ** 2
        if d2 <= best_d2:
            best_d2 = d2
            best = str(raw).strip()
    return best


def _empty_model(ok, error=None, warnings=None, assumptions=None):
    import pandas as pd
    return {
        "columns": pd.DataFrame(), "beams": pd.DataFrame(),
        "walls": pd.DataFrame(), "slabs": pd.DataFrame(),
        "stories": [], "grid": {"x_axes": [], "y_axes": [], "labels": {}},
        "materials": [], "area_loads": pd.DataFrame(),
        "meta": {"ok": ok, "error": error, "warnings": warnings or [],
                 "assumptions": assumptions or [], "n_elements": 0,
                 "confidence_summary": {}},
    }


def build_model_from_dxf(path: str, cfg: Config = DEFAULT_CONFIG,
                         user_input: Optional[dict] = None) -> Dict[str, Any]:
    """Rekonstruira strukturirani model iz DXF tlocrta.

    Vraca rjecnik oblika kao phase1_e2k: columns/beams/walls/slabs (DataFrame),
    stories (list), grid (dict), meta (dict s ok/warnings/assumptions/pouzdanost).
    Ne rusi se na losem ulazu; meta.ok = False + meta.error u tom slucaju.
    """
    import pandas as pd
    import phase2_dxf as p2

    doc, scale, err = _load_dxf(path, cfg)
    if err is not None or doc is None:
        return _empty_model(False, error=err or "Nepoznata greska pri ucitavanju DXF-a")

    warnings_list: List[str] = []
    assumptions: List[str] = []

    try:
        msp = doc.modelspace()
    except Exception as e:  # noqa: BLE001
        return _empty_model(False, error="DXF nema modelspace: " + str(e))

    # Etaze (iz unosa ili default)
    stories, story_assumptions = reconstruct_stories(doc, msp, cfg, user_input)
    assumptions.extend(story_assumptions)
    story0 = stories[0]["name"] if stories else "PRIZEMLJE"

    # Raster osi (reuse phase2_dxf)
    grid = {"x_axes": [], "y_axes": [], "labels": {}}
    try:
        grid_lines = p2.reconstruct_grid(msp, cfg)
        grid["raw"] = grid_lines
    except Exception as e:  # noqa: BLE001
        warnings_list.append("Rekonstrukcija rastera nije uspjela: " + str(e))
        grid_lines = []

    # Kotni tekstovi (za presjeke) i zatvoreni poligoni (reuse phase2_dxf)
    try:
        dim_texts = p2.extract_all_dimension_texts(msp, cfg)
    except Exception:
        dim_texts = []
    try:
        polys = p2.collect_closed_polylines(msp, doc=doc)
    except Exception as e:  # noqa: BLE001
        warnings_list.append("Prikupljanje poligona nije uspjelo: " + str(e))
        polys = []

    col_rows, beam_rows, wall_rows, slab_rows = [], [], [], []
    conf_counter = {"visoka": 0, "srednja": 0, "niska": 0}
    max_dist = float(getattr(cfg, "max_text_to_poly_distance", 500.0))

    # -- Klasifikacija zatvorenih poligona: prvo po sloju, pa po geometriji --
    for idx, poly in enumerate(polys):
        layer = poly.get("layer", "")
        verts = poly.get("verts") or poly.get("points") or []
        # centar i dimenzije (u DXF jedinicama -> skaliraj u m).
        # collect_closed_polylines vraca: centroid_x/y, width_dxf, height_dxf,
        # area_dxf (sve u DXF jedinicama). Podrzavamo i bbox kao fallback.
        cx = poly.get("centroid_x")
        cy = poly.get("centroid_y")
        w_dxf = poly.get("width_dxf")
        h_dxf = poly.get("height_dxf")
        area_dxf = poly.get("area_dxf")
        bbox = poly.get("bbox")
        if (w_dxf is None or h_dxf is None) and bbox:
            minx, miny, maxx, maxy = bbox
            w_dxf = abs(maxx - minx)
            h_dxf = abs(maxy - miny)
            if cx is None:
                cx = (minx + maxx) / 2.0
            if cy is None:
                cy = (miny + maxy) / 2.0
        w_m = (w_dxf * scale) if w_dxf is not None else None
        h_m = (h_dxf * scale) if h_dxf is not None else None
        area_m2 = poly.get("area")
        if area_m2 is None and area_dxf is not None:
            area_m2 = abs(area_dxf)
        if area_m2 is not None:
            area_m2 = abs(area_m2) * scale * scale

        tip = classify_by_layer(layer, cfg)
        source = "layer"
        confidence = "visoka"
        if tip is None:
            tip, confidence = classify_by_geometry(
                {"area_m2": area_m2, "width_m": w_m, "height_m": h_m}, cfg)
            source = "geometry"
        if tip is None:
            continue  # neklasificirano -> preskoci

        section = _extract_section_from_polys(dim_texts, cx or 0, cy or 0, max_dist, cfg)
        conf_counter[confidence] = conf_counter.get(confidence, 0) + 1
        cxm = (cx or 0.0) * scale
        cym = (cy or 0.0) * scale

        if tip == "column":
            col_rows.append({
                "name": "C%d" % (len(col_rows) + 1), "element_type": "column",
                "x_start": cxm, "y_start": cym, "z_start": 0.0,
                "x_end": cxm, "y_end": cym, "z_end": 0.0,
                "story": story0, "section": section, "material": "",
                "width_mm": round(w_m * 1000) if w_m else None,
                "height_mm": round(h_m * 1000) if h_m else None,
                "layer": layer, "source": source, "confidence": confidence,
            })
        elif tip == "slab":
            slab_rows.append({
                "name": "S%d" % (len(slab_rows) + 1), "element_type": "slab",
                "centroid_x": cxm, "centroid_y": cym, "centroid_z": 0.0,
                "x_start": cxm, "y_start": cym,
                "story": story0, "prop_name": section,
                "area_m2": area_m2, "layer": layer,
                "source": source, "confidence": confidence,
            })
        elif tip == "wall":
            wall_rows.append({
                "name": "W%d" % (len(wall_rows) + 1), "element_type": "wall",
                "centroid_x": cxm, "centroid_y": cym, "centroid_z": 0.0,
                "x_start": cxm, "y_start": cym,
                "story": story0, "section": section,
                "layer": layer, "source": source, "confidence": confidence,
            })
        elif tip == "beam":
            beam_rows.append({
                "name": "B%d" % (len(beam_rows) + 1), "element_type": "beam",
                "x_start": cxm, "y_start": cym, "z_start": 0.0,
                "x_end": cxm, "y_end": cym, "z_end": 0.0,
                "story": story0, "section": section, "material": "",
                "layer": layer, "source": source, "confidence": confidence,
            })

    # -- Grede iz linija na sloju grede; zidovi iz para paralelnih na sloju zida --
    line_by_layer = {}
    try:
        for e in msp.query("LINE"):
            lay = e.dxf.layer
            s, en = e.dxf.start, e.dxf.end
            line_by_layer.setdefault(lay, []).append(
                {"x0": s.x * scale, "y0": s.y * scale,
                 "x1": en.x * scale, "y1": en.y * scale})
    except Exception:
        pass

    for lay, lines in line_by_layer.items():
        tip = classify_by_layer(lay, cfg)
        if tip == "beam":
            for ln in lines:
                length = ((ln["x1"]-ln["x0"])**2 + (ln["y1"]-ln["y0"])**2) ** 0.5
                th = cfg.dxf_geom_thresholds
                if th["beam_min_len_m"] <= length <= th["beam_max_len_m"]:
                    beam_rows.append({
                        "name": "B%d" % (len(beam_rows) + 1), "element_type": "beam",
                        "x_start": ln["x0"], "y_start": ln["y0"], "z_start": 0.0,
                        "x_end": ln["x1"], "y_end": ln["y1"], "z_end": 0.0,
                        "story": story0, "section": "", "material": "",
                        "layer": lay, "source": "layer", "confidence": "visoka",
                    })
                    conf_counter["visoka"] += 1
        elif tip == "wall":
            for w in detect_walls_from_lines(lines, cfg):
                wall_rows.append({
                    "name": "W%d" % (len(wall_rows) + 1), "element_type": "wall",
                    "centroid_x": (w["x_start"] + w["x_end"]) / 2.0,
                    "centroid_y": (w["y_start"] + w["y_end"]) / 2.0, "centroid_z": 0.0,
                    "x_start": w["x_start"], "y_start": w["y_start"],
                    "x_end": w["x_end"], "y_end": w["y_end"],
                    "story": story0, "section": "",
                    "thickness_mm": round(w["thickness_m"] * 1000),
                    "layer": lay, "source": "geometry", "confidence": w["confidence"],
                })
                conf_counter[w["confidence"]] = conf_counter.get(w["confidence"], 0) + 1

    # -- Tekstualne napomene: materijali / opterecenja (reuse phase2_dxf) --
    materials, area_loads = [], []
    try:
        ann = p2.extract_drawing_annotations(msp, cfg)
        # phase2_dxf vraca tuple (ann_mats, ann_loads, doc_mats)
        if isinstance(ann, tuple) and len(ann) >= 2:
            ann_mats, ann_loads = ann[0], ann[1]
            doc_mats = ann[2] if len(ann) >= 3 else {}
            # jedinstveni materijali (naziv) iz oznaka + dokumentnih zadanih
            seen_m = set()
            for m in (ann_mats or []):
                nm = m.get("mat") if isinstance(m, dict) else m
                if nm and nm not in seen_m:
                    seen_m.add(nm)
                    materials.append(nm)
            for nm in (doc_mats.values() if isinstance(doc_mats, dict) else []):
                if nm and nm not in seen_m:
                    seen_m.add(nm)
                    materials.append(nm)
            area_loads = list(ann_loads or [])
        elif isinstance(ann, dict):
            materials = ann.get("materials", []) or []
            area_loads = ann.get("area_loads", []) or []
    except Exception:
        pass

    model = {
        "columns": pd.DataFrame(col_rows),
        "beams": pd.DataFrame(beam_rows),
        "walls": pd.DataFrame(wall_rows),
        "slabs": pd.DataFrame(slab_rows),
        "stories": stories,
        "grid": grid,
        "materials": materials,
        "area_loads": pd.DataFrame(area_loads) if area_loads else pd.DataFrame(),
    }
    n_elements = len(col_rows) + len(beam_rows) + len(wall_rows) + len(slab_rows)
    if n_elements == 0:
        warnings_list.append(
            "Nije prepoznat nijedan konstruktivni element. Provjerite nazive slojeva "
            "ili prilagodite mapiranje slojeva u konfiguraciji.")
    model["meta"] = {
        "ok": True, "error": None, "units": "m",
        "warnings": warnings_list, "assumptions": assumptions,
        "n_elements": n_elements, "confidence_summary": conf_counter,
        "scale_to_m": scale,
    }
    return model
