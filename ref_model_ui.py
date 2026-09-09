"""
ref_model_ui.py
---------------
Čista (testabilna) logika za UI tok "Referentni model iz tlocrta":
  1. generiranje referentnog modela iz DXF bytes (build_ref_model_from_bytes),
  2. priprema tablica za prikaz/uređivanje u editoru (editable_tables),
  3. primjena korisničkih izmjena iz editora natrag u model (apply_edits),
  4. sažetak modela za prikaz (model_summary_text).

Namjerno bez importa streamlit — sve ovdje je obična Python/pandas logika koja
se može testirati bez Streamlit runtimea. streamlit_app.py samo poziva ove
funkcije i renderira rezultat (st.data_editor, st.dataframe, ...).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

import pandas as pd

from config import Config, DEFAULT_CONFIG

# Kolone koje su smislene za reviziju po tipu elementa (redoslijed = prikaz)
EDITABLE_COLUMNS = {
    "columns": ["name", "story", "x_start", "y_start", "width_mm", "height_mm",
                "section", "material", "source", "confidence"],
    "beams": ["name", "story", "x_start", "y_start", "x_end", "y_end",
              "section", "material", "source", "confidence"],
    "walls": ["name", "story", "centroid_x", "centroid_y", "thickness_mm",
              "section", "source", "confidence"],
    "slabs": ["name", "story", "centroid_x", "centroid_y", "area_m2",
              "prop_name", "source", "confidence"],
}

# Hrvatski nazivi tipova za prikaz
TYPE_LABELS_HR = {
    "columns": "Stupovi", "beams": "Grede", "walls": "Zidovi", "slabs": "Ploče",
}


def build_ref_model_from_bytes(dxf_bytes: bytes, cfg: Config = DEFAULT_CONFIG,
                               user_input: Optional[dict] = None) -> Dict[str, Any]:
    """Zapiše DXF bytes u privremenu datoteku i vrati referentni model.

    Omotač oko dxf_model.build_model_from_dxf koji radi s uploadanim bytes-ovima
    (kako Streamlit isporučuje datoteke). Uvijek čisti privremenu datoteku.
    """
    import dxf_model as dm

    if not dxf_bytes:
        return dm._empty_model(False, error="Prazan DXF sadržaj (0 bajtova).")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    try:
        tmp.write(dxf_bytes)
        tmp.close()
        return dm.build_model_from_dxf(tmp.name, cfg, user_input)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def editable_tables(model: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Vraća {tip: DataFrame} spreman za prikaz/uređivanje u editoru.

    Zadržava samo smislene kolone (EDITABLE_COLUMNS) i samo tipove koji imaju
    barem jedan element. Prazni tipovi se izostavljaju iz uređivanja.
    """
    out: Dict[str, pd.DataFrame] = {}
    for key, cols in EDITABLE_COLUMNS.items():
        df = model.get(key)
        if df is None or not hasattr(df, "empty") or df.empty:
            continue
        present = [c for c in cols if c in df.columns]
        out[key] = df[present].copy().reset_index(drop=True)
    return out


def apply_edits(model: Dict[str, Any],
                edited: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Vrati novi model s primijenjenim korisničkim izmjenama iz editora.

    Za svaki uređeni tip, ažurira uređene kolone natrag u izvorni model
    (spajanjem po poziciji retka). Nedostajuće/obrisane retke poštuje: rezultat
    ima onoliko redova koliko ih je u uređenoj tablici. Ne mijenja izvorni model
    (radi kopiju).
    """
    new_model = dict(model)
    for key, edf in (edited or {}).items():
        if edf is None:
            continue
        orig = model.get(key)
        if orig is None or not hasattr(orig, "empty"):
            # nema izvornika — koristi uređenu tablicu kakva jest
            new_model[key] = edf.copy().reset_index(drop=True) if hasattr(edf, "copy") else edf
            continue
        edf = edf.reset_index(drop=True)
        # zadrži samo retke koji postoje u uređenoj tablici (brisanje poštovano)
        base = orig.reset_index(drop=True).iloc[:len(edf)].copy()
        # dopuni bazu ako je editor dodao retke
        if len(edf) > len(base):
            extra = edf.iloc[len(base):].copy()
            base = pd.concat([base, extra], ignore_index=True)
        # prepiši uređene vrijednosti kolonu po kolonu
        for c in edf.columns:
            base[c] = edf[c].values
        new_model[key] = base.reset_index(drop=True)
    # meta zadrži, ali označi da je model revidiran
    meta = dict(new_model.get("meta", {}) or {})
    meta["edited"] = True
    new_model["meta"] = meta
    return new_model


def model_summary_text(model: Dict[str, Any]) -> List[str]:
    """Kratke stavke sažetka referentnog modela za prikaz u UI-u (hrvatski)."""
    lines: List[str] = []
    meta = model.get("meta", {}) or {}
    if not meta.get("ok", False):
        lines.append("Greška pri učitavanju: %s" % (meta.get("error") or "nepoznata"))
        return lines

    for key, label in TYPE_LABELS_HR.items():
        df = model.get(key)
        n = len(df) if df is not None and hasattr(df, "__len__") else 0
        if n:
            lines.append("%s: %d" % (label, n))

    stories = model.get("stories") or []
    if stories:
        lines.append("Etaže: %d" % len(stories))

    cs = meta.get("confidence_summary") or {}
    if cs:
        lines.append("Pouzdanost — visoka: %d, srednja: %d, niska: %d"
                     % (cs.get("visoka", 0), cs.get("srednja", 0), cs.get("niska", 0)))

    for w in (meta.get("warnings") or [])[:5]:
        lines.append("⚠ " + str(w))
    return lines


def input_signature(dxf_bytes: bytes, user_input: Optional[dict]) -> str:
    """Stabilan potpis ulaza za invalidaciju uređivanja pri promjeni DXF-a/unosa.

    Kao vektor-tab (vektor_sig): kad se promijeni potpis, editor stanje treba
    resetirati (odbaciti stare izmjene koje više ne odgovaraju modelu).
    """
    import hashlib

    h = hashlib.sha1()
    h.update(dxf_bytes or b"")
    if user_input:
        for k in sorted(user_input.keys()):
            h.update(("%s=%s;" % (k, user_input[k])).encode("utf-8"))
    return h.hexdigest()
