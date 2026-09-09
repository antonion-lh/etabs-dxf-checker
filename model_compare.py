"""
model_compare.py
----------------
Usporedba referentnog modela (rekonstruiranog iz DXF tlocrta preko
dxf_model.build_model_from_dxf) sa studentskim ETABS modelom (phase1_e2k.parse_e2k).

Cilj Faze B: profesor da studentima tlocrt kao referentni primjer; aplikacija iz
istog tlocrta gradi referentni ("ispravan") model, a zatim automatski uspoređuje
studentski E2K model s njime i prijavljuje odstupanja:
  - element nedostaje (student ga nije modelirao),
  - element je višak (student ima nešto što nije na tlocrtu),
  - kriva dimenzija presjeka,
  - pomak pozicije.

Pristup: referentni model iz tlocrta tretiramo kao "istinu" (df_dxf-oblik), a
studentski E2K kao "etabs" u postojećem phase3_validation.validate engineu koji
već radi story-aware greedy KDTree podudaranje. Time izbjegavamo dupliciranje
logike podudaranja.

Statusi (Status enum iz phase3_validation), interpretirani u kontekstu provjere:
  - MATCH             -> student ispravno modelirao element
  - SECTION_MISMATCH  -> element postoji ali kriva dimenzija presjeka
  - ETABS_ONLY        -> student ima element kojeg NEMA na referentnom tlocrtu (VIŠAK)
  - DXF_ONLY          -> referentni tlocrt ima element koji student NIJE modelirao (NEDOSTAJE)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from config import Config, DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Adapter: referentni model (dict) -> df_dxf-oblik tablica za validate()
# ---------------------------------------------------------------------------

# Kolone koje phase3_validation.validate ocekuje na df_dxf strani
_DXF_TABLE_COLUMNS = [
    "element_type", "centroid_x_m", "centroid_y_m",
    "dim1_mm", "dim2_mm", "floor_label", "layer",
]


def _rows_from_frame(df: pd.DataFrame, element_type: str) -> List[dict]:
    """Frame elementi (column/beam): pozicija iz x_start/y_start, dim iz width/height_mm."""
    rows = []
    if df is None or not hasattr(df, "empty") or df.empty:
        return rows
    for _, r in df.iterrows():
        cx = r.get("x_start")
        cy = r.get("y_start")
        # frame greda ima dvije tocke -> centar kao sredina
        if cx is not None and r.get("x_end") is not None:
            try:
                cx = (float(cx) + float(r.get("x_end"))) / 2.0
                cy = (float(cy) + float(r.get("y_end"))) / 2.0
            except (TypeError, ValueError):
                pass
        rows.append({
            "element_type": element_type,
            "centroid_x_m": _as_float(cx),
            "centroid_y_m": _as_float(cy),
            "dim1_mm": _as_float(r.get("width_mm")),
            "dim2_mm": _as_float(r.get("height_mm")),
            "floor_label": r.get("story", ""),
            "layer": r.get("layer", ""),
        })
    return rows


def _rows_from_area(df: pd.DataFrame, element_type: str) -> List[dict]:
    """Area elementi (wall/slab): pozicija iz centroid_x/centroid_y."""
    rows = []
    if df is None or not hasattr(df, "empty") or df.empty:
        return rows
    for _, r in df.iterrows():
        cx = r.get("centroid_x", r.get("x_start"))
        cy = r.get("centroid_y", r.get("y_start"))
        # zid moze imati thickness_mm kao dim1
        rows.append({
            "element_type": element_type,
            "centroid_x_m": _as_float(cx),
            "centroid_y_m": _as_float(cy),
            "dim1_mm": _as_float(r.get("thickness_mm")),
            "dim2_mm": None,
            "floor_label": r.get("story", ""),
            "layer": r.get("layer", ""),
        })
    return rows


def _as_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def ref_model_to_dxf_table(model: Dict[str, Any]) -> pd.DataFrame:
    """Pretvara referentni model (build_model_from_dxf) u df_dxf-oblik tablicu.

    Rezultat je kompatibilan s izlazom phase2_dxf.parse_dxf pa ga
    phase3_validation.validate moze koristiti bez izmjena.
    """
    if not isinstance(model, dict):
        return pd.DataFrame(columns=_DXF_TABLE_COLUMNS)

    rows: List[dict] = []
    rows += _rows_from_frame(model.get("columns"), "column")
    rows += _rows_from_frame(model.get("beams"), "beam")
    rows += _rows_from_area(model.get("walls"), "wall")
    rows += _rows_from_area(model.get("slabs"), "slab")

    if not rows:
        return pd.DataFrame(columns=_DXF_TABLE_COLUMNS)
    return pd.DataFrame(rows, columns=_DXF_TABLE_COLUMNS)


# ---------------------------------------------------------------------------
# Usporedba
# ---------------------------------------------------------------------------

def compare_models(
    student_e2k: Dict[str, pd.DataFrame],
    ref_model: Dict[str, Any],
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Uspoređuje studentski E2K model s referentnim modelom iz tlocrta.

    student_e2k : izlaz phase1_e2k.parse_e2k (dict DataFrame-ova po tipu)
    ref_model   : izlaz dxf_model.build_model_from_dxf (dict)

    Vraća df_res (kao phase3_validation.validate) gdje status znaci:
      MATCH=ispravno, SECTION_MISMATCH=kriva dimenzija,
      ETABS_ONLY=student ima visak, DXF_ONLY=student nije modelirao (nedostaje).
    """
    import phase3_validation as p3

    ref_df = ref_model_to_dxf_table(ref_model)
    return p3.validate(student_e2k, ref_df, cfg)


# ---------------------------------------------------------------------------
# Sazetak razlika (hrvatski)
# ---------------------------------------------------------------------------

def summarize_differences(df_res: pd.DataFrame) -> Dict[str, Any]:
    """Sažima rezultat usporedbe u brojače + hrvatske poruke po tipu elementa.

    Vraća dict:
      {
        "counts": {"match":N,"mismatch":N,"nedostaje":N,"visak":N,"ukupno":N},
        "by_type": {"column": {...}, ...},
        "messages": [str, ...],   # citljive poruke za korisnika
        "ok": bool,               # True ako nema odstupanja
      }
    """
    counts = {"match": 0, "mismatch": 0, "nedostaje": 0, "visak": 0, "ukupno": 0}
    by_type: Dict[str, Dict[str, int]] = {}
    messages: List[str] = []

    if df_res is None or not hasattr(df_res, "empty") or df_res.empty:
        return {"counts": counts, "by_type": by_type, "messages": [], "ok": True}

    # (jednina, množina) za hrvatsku gramatiku poruka
    _HR = {
        "column": ("stup", "stupova"), "beam": ("greda", "greda"),
        "wall": ("zid", "zidova"), "slab": ("ploča", "ploča"),
        "brace": ("spreg", "sprega"),
    }

    def _naziv(et, n):
        pair = _HR.get(et)
        if not pair:
            return et
        return pair[0] if n == 1 else pair[1]

    for _, r in df_res.iterrows():
        status = str(r.get("status", "")).upper()
        et = str(r.get("element_type", ""))
        bt = by_type.setdefault(et, {"match": 0, "mismatch": 0, "nedostaje": 0, "visak": 0})
        counts["ukupno"] += 1
        if "SECTION_MISMATCH" in status:
            counts["mismatch"] += 1
            bt["mismatch"] += 1
        elif "MATCH" in status:
            counts["match"] += 1
            bt["match"] += 1
        elif "DXF_ONLY" in status:
            counts["nedostaje"] += 1
            bt["nedostaje"] += 1
        elif "ETABS_ONLY" in status:
            counts["visak"] += 1
            bt["visak"] += 1

    for et, bt in sorted(by_type.items()):
        if bt["nedostaje"]:
            messages.append("Nedostaje %d %s (na tlocrtu, ali student nije modelirao)."
                            % (bt["nedostaje"], _naziv(et, bt["nedostaje"])))
        if bt["visak"]:
            messages.append("Višak %d %s (student modelirao, nema na tlocrtu)."
                            % (bt["visak"], _naziv(et, bt["visak"])))
        if bt["mismatch"]:
            messages.append("Kriva dimenzija na %d %s (presjek ne odgovara tlocrtu)."
                            % (bt["mismatch"], _naziv(et, bt["mismatch"])))

    ok = (counts["nedostaje"] == 0 and counts["visak"] == 0 and counts["mismatch"] == 0)
    if ok and counts["ukupno"] > 0:
        messages.append("Model se u potpunosti podudara s referentnim tlocrtom.")

    return {"counts": counts, "by_type": by_type, "messages": messages, "ok": ok}
