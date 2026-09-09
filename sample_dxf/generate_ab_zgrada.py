#!/usr/bin/env python3
"""
Generator sintetskog viseetaznog AB (armiranobetonskog) tlocrta u DXF-u.

Namjena: realan, kompleksan testni primjer za Fazu B (izrada numerickog modela
iz DXF-a). Generira pravilan raster stupova, grede po osima, zidove jezgre
(stubiste/lift), plocu i kote presjeka, za vise etaza. Slojevi slijede jasnu
konvenciju (STUP/GREDA/ZID/PLOCA/OSI/KOTE) koju parser prepoznaje.

Pokretanje:
    python3 generate_ab_zgrada.py            # zadana zgrada -> ab_zgrada.dxf
Sve dimenzije u milimetrima (INSUNITS = 4).
"""

from __future__ import annotations

import ezdxf
from ezdxf.enums import TextEntityAlignment


# ---------------------------------------------------------------------------
# Parametri zgrade (mm)
# ---------------------------------------------------------------------------
class Param:
    # Raster osi (razmaci polja) u X i Y smjeru
    bays_x = [6000, 6000, 6000, 5000, 6000]   # 5 polja u X -> 6 osi (A..F)
    bays_y = [5000, 6000, 6000, 5000]          # 4 polja u Y -> 5 osi (1..5)

    n_stories = 4          # broj etaza
    story_height = 3200    # visina kata (mm)

    col_b = 400            # dimenzija stupa b (mm)
    col_h = 400            # dimenzija stupa h (mm)
    beam_b = 300           # sirina grede
    beam_h = 500           # visina grede
    wall_t = 250           # debljina zida jezgre
    slab_t = 200           # debljina ploce

    # Jezgra (stubiste/lift): pravokutnik zidova oko osi B-C x 2-3
    core_ox = 6000                 # pocetak jezgre po X (od osi A)
    core_oy = 5000                 # pocetak jezgre po Y (od osi 1)
    core_w = 6000                  # sirina jezgre
    core_d = 6000                  # dubina jezgre
    core_opening = 1200            # otvor (vrata) u zidu jezgre


P = Param()


def _axis_coords(bays):
    """Vraca apsolutne koordinate osi iz liste razmaka polja."""
    xs = [0]
    for b in bays:
        xs.append(xs[-1] + b)
    return xs


def build(path="ab_zgrada.dxf"):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # milimetri
    msp = doc.modelspace()

    # Slojevi s bojama (ACI) radi preglednosti
    layers = {
        "OSI":   {"color": 8},    # sivo - osi rastera
        "STUP":  {"color": 1},    # crveno - stupovi
        "GREDA": {"color": 3},    # zeleno - grede
        "ZID":   {"color": 5},    # plavo - zidovi jezgre
        "PLOCA": {"color": 4},    # cijan - ploca (obris)
        "KOTE":  {"color": 2},    # zuto - kotne oznake
        "TEKST": {"color": 7},    # bijelo/crno - opisni tekst
    }
    for name, attr in layers.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=attr["color"])

    xs = _axis_coords(P.bays_x)
    ys = _axis_coords(P.bays_y)
    Lx, Ly = xs[-1], ys[-1]

    axis_labels_x = [chr(ord("A") + i) for i in range(len(xs))]
    axis_labels_y = [str(i + 1) for i in range(len(ys))]

    # -- Generiraj svaku etazu kao zaseban tlocrt, prostorno razmaknut po X --
    # (odvojeni tlocrti = tipican nacin prikaza vise etaza na jednom listu)
    gap = Lx + 8000  # horizontalni razmak izmedju tlocrta etaza
    for s in range(P.n_stories):
        ox = s * gap
        z = s * P.story_height
        _draw_story(msp, xs, ys, ox, z, s + 1,
                    axis_labels_x, axis_labels_y, Lx, Ly)

    # naslov
    msp.add_text(
        "AB ZGRADA - SINTETSKI TESTNI TLOCRT (Faza B)",
        dxfattribs={"layer": "TEKST", "height": 400},
    ).set_placement((0, -3500))

    doc.saveas(path)
    return path


def _draw_story(msp, xs, ys, ox, z, story_no, lab_x, lab_y, Lx, Ly):
    """Nacrta jedan tlocrt etaze s ishodistem (ox, 0)."""
    # --- Osi rastera ---
    for i, x in enumerate(xs):
        msp.add_line((ox + x, -1500), (ox + x, Ly + 1500),
                     dxfattribs={"layer": "OSI", "linetype": "DASHDOT"})
        msp.add_text(lab_x[i], dxfattribs={"layer": "OSI", "height": 300}
                     ).set_placement((ox + x, Ly + 1800), align=TextEntityAlignment.MIDDLE_CENTER)
    for j, y in enumerate(ys):
        msp.add_line((ox - 1500, y), (ox + Lx + 1500, y),
                     dxfattribs={"layer": "OSI", "linetype": "DASHDOT"})
        msp.add_text(lab_y[j], dxfattribs={"layer": "OSI", "height": 300}
                     ).set_placement((ox - 1800, y), align=TextEntityAlignment.MIDDLE_CENTER)

    # --- Ploca (obris etaze) kao zatvorena LWPOLYLINE ---
    msp.add_lwpolyline(
        [(ox, 0), (ox + Lx, 0), (ox + Lx, Ly), (ox, Ly)],
        close=True, dxfattribs={"layer": "PLOCA"},
    )

    # --- Stupovi na svim sjecistima osi (zatvoreni kvadrat b x h) ---
    b, h = P.col_b, P.col_h
    for x in xs:
        for y in ys:
            cx, cy = ox + x, y
            msp.add_lwpolyline(
                [(cx - b/2, cy - h/2), (cx + b/2, cy - h/2),
                 (cx + b/2, cy + h/2), (cx - b/2, cy + h/2)],
                close=True, dxfattribs={"layer": "STUP"},
            )
    # oznaka presjeka stupa (jednom, kod prvog stupa)
    msp.add_text(f"S {P.col_b}/{P.col_h}",
                 dxfattribs={"layer": "KOTE", "height": 250}
                 ).set_placement((ox + xs[0] + 300, ys[0] + 300))

    # --- Grede po osima (linije osi grede izmedju stupova) ---
    # Grede u X smjeru (duz svake osi Y)
    for y in ys:
        for i in range(len(xs) - 1):
            msp.add_line((ox + xs[i], y), (ox + xs[i+1], y),
                         dxfattribs={"layer": "GREDA"})
    # Grede u Y smjeru (duz svake osi X)
    for x in xs:
        for j in range(len(ys) - 1):
            msp.add_line((ox + x, ys[j]), (ox + x, ys[j+1]),
                         dxfattribs={"layer": "GREDA"})
    msp.add_text(f"G {P.beam_b}/{P.beam_h}",
                 dxfattribs={"layer": "KOTE", "height": 250}
                 ).set_placement((ox + xs[0] + 300, (ys[0]+ys[1])/2))

    # --- Zidovi jezgre (stubiste/lift) kao par paralelnih linija s otvorom ---
    cx0, cy0 = ox + P.core_ox, P.core_oy
    cx1, cy1 = cx0 + P.core_w, cy0 + P.core_d
    t = P.wall_t
    # cetiri zida jezgre kao zatvoreni pravokutnici debljine t
    # donji zid (s otvorom-vrata u sredini)
    _wall_with_opening(msp, (cx0, cy0), (cx1, cy0), t, P.core_opening, horizontal=True)
    # gornji zid
    _wall_segment(msp, (cx0, cy1), (cx1, cy1), t, horizontal=True)
    # lijevi zid
    _wall_segment(msp, (cx0, cy0), (cx0, cy1), t, horizontal=False)
    # desni zid
    _wall_segment(msp, (cx1, cy0), (cx1, cy1), t, horizontal=False)
    msp.add_text(f"Z t={P.wall_t}",
                 dxfattribs={"layer": "KOTE", "height": 250}
                 ).set_placement((cx0 + 300, cy1 - 500))

    # --- Naziv etaze ---
    naziv = "PRIZEMLJE" if story_no == 1 else f"{story_no-1}. KAT"
    msp.add_text(f"ETAZA {story_no} - {naziv}  (Z=+{z/1000:.2f} m)",
                 dxfattribs={"layer": "TEKST", "height": 350}
                 ).set_placement((ox, -1000))


def _wall_segment(msp, p0, p1, t, horizontal):
    """Nacrta zid kao zatvoreni pravokutnik debljine t oko osi p0-p1."""
    x0, y0 = p0
    x1, y1 = p1
    if horizontal:
        pts = [(x0, y0 - t/2), (x1, y0 - t/2), (x1, y0 + t/2), (x0, y0 + t/2)]
    else:
        pts = [(x0 - t/2, y0), (x0 + t/2, y0), (x0 + t/2, y1), (x0 - t/2, y1)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "ZID"})


def _wall_with_opening(msp, p0, p1, t, opening, horizontal):
    """Zid s otvorom (vrata) u sredini - dva segmenta."""
    x0, y0 = p0
    x1, y1 = p1
    if horizontal:
        mid = (x0 + x1) / 2
        _wall_segment(msp, (x0, y0), (mid - opening/2, y0), t, True)
        _wall_segment(msp, (mid + opening/2, y0), (x1, y0), t, True)
    else:
        mid = (y0 + y1) / 2
        _wall_segment(msp, (x0, y0), (x0, mid - opening/2), t, False)
        _wall_segment(msp, (x0, mid + opening/2), (x0, y1), t, False)


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "ab_zgrada.dxf")
    build(out)
    print("Generirano:", out)
