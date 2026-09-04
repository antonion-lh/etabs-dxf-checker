"""
pdf_dims.py
-----------
Extract cross-section dimensions from the TEXT LAYER of an architectural /
structural PDF drawing and cross-reference them with an ETABS model.

This only works for vector/text PDFs where dimensions are real, selectable text
(e.g. exports from AutoCAD / ETABS). Scanned raster drawings have no text layer
and are handled by a graceful fallback in the caller.

Public API:
    extract_pdf_dimensions(raw_pdf_bytes) -> dict
    pdf_has_dimension_text(raw_pdf_bytes) -> bool
    validate_against_pdf(etabs_data, raw_pdf_bytes, cfg) -> pd.DataFrame
"""

from __future__ import annotations

import io
import re
import logging
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension token patterns (all normalised to mm)
# ---------------------------------------------------------------------------
# Rectangular section: 40/40, 40x40, 30/50, 300x500, 30×50
_RE_RECT = re.compile(r"\b(\d{2,4})\s*[/xX×]\s*(\d{2,4})\b")
# Circular / diameter: d=45, D=450, Ø45, fi45, R45
_RE_CIRC = re.compile(r"(?:d|D|Ø|ø|fi|FI|φ)\s*[=:]?\s*(\d{2,4})\b")
# Thickness (walls/slabs): t=20, d=25, h=20, 20cm, 30 cm
_RE_THICK = re.compile(r"(?:t|d|h|e)\s*[=:]\s*(\d{1,3})\b|\b(\d{1,3})\s*cm\b")


def _to_mm(value: float, unit_hint: str = "cm") -> float:
    """Normalise a raw dimension number to mm.

    Architectural section labels are almost always in cm (e.g. '40/40' = 40 cm).
    Values that look like they are already in mm (>= 1000 for a section, or a
    3-digit value that is clearly mm) are handled by heuristics in the callers.
    """
    v = float(value)
    if unit_hint == "mm":
        return v
    if unit_hint == "m":
        return v * 1000.0
    # cm default
    return v * 10.0


def _classify_dim_token(text: str) -> Optional[dict]:
    """Parse a single text token into a structured dimension, or None.

    Returns dict: {kind, d1_mm, d2_mm, raw}
    kind in {"rect", "circ", "thick"}.
    Heuristic: 2-3 digit numbers in section labels are cm; 3-4 digit values
    >= 1000 are treated as mm.
    """
    t = text.strip()
    if not t:
        return None

    m = _RE_RECT.search(t)
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        # If both look like mm (>=1000 or 3-digit >= 150 typical mm sections)
        # decide unit: values <= 200 are almost certainly cm; large are mm.
        def norm(x):
            return x if x >= 1000 else (x * 10.0 if x <= 200 else x)
        d1, d2 = norm(a), norm(b)
        return {"kind": "rect", "d1_mm": min(d1, d2), "d2_mm": max(d1, d2), "raw": t}

    m = _RE_CIRC.search(t)
    if m:
        a = float(m.group(1))
        d = a if a >= 1000 else (a * 10.0 if a <= 200 else a)
        return {"kind": "circ", "d1_mm": d, "d2_mm": d, "raw": t}

    m = _RE_THICK.search(t)
    if m:
        g = m.group(1) or m.group(2)
        if g:
            a = float(g)
            d = a if a >= 1000 else (a * 10.0 if a <= 200 else a)
            return {"kind": "thick", "d1_mm": d, "d2_mm": None, "raw": t}

    return None


def pdf_has_dimension_text(raw: bytes, min_tokens: int = 2) -> bool:
    """Return True if the PDF's text layer contains at least `min_tokens`
    parseable dimension tokens across all pages."""
    try:
        import fitz
    except Exception:
        return False
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:
        return False
    count = 0
    for page in doc:
        try:
            for w in page.get_text("words"):
                if _classify_dim_token(w[4]):
                    count += 1
                    if count >= min_tokens:
                        doc.close()
                        return True
        except Exception:
            continue
    doc.close()
    return False


def extract_pdf_dimensions(raw: bytes) -> dict:
    """Extract all parseable dimension tokens from a PDF text layer.

    Returns a dict:
      {
        "has_text_dims": bool,
        "tokens": [ {page, x_pt, y_pt, kind, d1_mm, d2_mm, raw}, ... ],
        "page_count": int,
      }
    Coordinates are in PDF points (page space), used only for relative
    proximity, not absolute alignment with the model.
    """
    result = {"has_text_dims": False, "tokens": [], "page_count": 0}
    try:
        import fitz
    except Exception:
        return result
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:
        return result

    result["page_count"] = len(doc)
    tokens = []
    for pno, page in enumerate(doc):
        try:
            words = page.get_text("words")  # (x0,y0,x1,y1, "word", block, line, wno)
        except Exception:
            continue
        for w in words:
            parsed = _classify_dim_token(w[4])
            if parsed:
                cx = (w[0] + w[2]) / 2.0
                cy = (w[1] + w[3]) / 2.0
                tokens.append({
                    "page": pno + 1,
                    "x_pt": cx,
                    "y_pt": cy,
                    "kind": parsed["kind"],
                    "d1_mm": parsed["d1_mm"],
                    "d2_mm": parsed["d2_mm"],
                    "raw": parsed["raw"],
                })
    doc.close()
    result["tokens"] = tokens
    result["has_text_dims"] = len(tokens) > 0
    return result


# ---------------------------------------------------------------------------
# Cross-reference extracted PDF dimensions with ETABS element sections
# ---------------------------------------------------------------------------
def _dims_close(a: Optional[float], b: Optional[float], tol_mm: float) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol_mm


def _section_matches_token(ew, eh, tok: dict, tol_mm: float) -> bool:
    """Does an ETABS element (ew x eh mm) match a PDF dimension token?"""
    d1, d2 = tok.get("d1_mm"), tok.get("d2_mm")
    if tok["kind"] in ("circ", "thick"):
        target = d1
        # single dimension: compare against either ETABS dim present
        for e in (ew, eh):
            if e is not None and _dims_close(e, target, tol_mm):
                return True
        return False
    # rectangular: compare unordered pair
    if ew is None or eh is None or d1 is None or d2 is None:
        return False
    e_lo, e_hi = min(ew, eh), max(ew, eh)
    t_lo, t_hi = min(d1, d2), max(d1, d2)
    return _dims_close(e_lo, t_lo, tol_mm) and _dims_close(e_hi, t_hi, tol_mm)


def validate_against_pdf(etabs_data: dict, raw: bytes, cfg=None) -> pd.DataFrame:
    """Cross-reference ETABS element sections with dimensions read from a PDF
    text layer.

    Because a PDF's coordinate space does not align with the model, matching is
    done on the SECTION DIMENSION VALUE: for each ETABS element we check whether
    a matching cross-section dimension appears anywhere on the drawing.

    Status semantics (Croatian, matching the rest of the app):
      - "Dimenzija potvrđena na nacrtu"  : element's section found on the drawing
      - "Dimenzija nije nađena na nacrtu": no matching dimension text on drawing
      - "Nema dimenzije u modelu"        : element has no parseable ETABS section

    Returns a DataFrame with the same columns the Elements tab expects.
    """
    sec_tol = float(getattr(cfg, "section_tolerance_mm", 20.0)) if cfg else 20.0
    # For PDF text dims we allow a looser tolerance (rounding on drawings)
    tol = max(sec_tol, 20.0)

    extraction = extract_pdf_dimensions(raw)
    tokens = extraction["tokens"]
    has_dims = extraction["has_text_dims"]

    STANDARD_COLS = [
        "element_type", "status", "etabs_name", "story", "etabs_x", "etabs_y", "etabs_z",
        "etabs_section", "etabs_w_mm", "etabs_h_mm", "etabs_material",
        "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm", "xy_dist_m", "notes",
    ]

    rows = []
    for elem_type, key in [("column", "columns"), ("beam", "beams"), ("wall", "walls"), ("slab", "slabs")]:
        df_sub = etabs_data.get(key, pd.DataFrame())
        if df_sub is None or df_sub.empty:
            continue
        for _, r in df_sub.iterrows():
            ew = r.get("width_mm")
            eh = r.get("height_mm", r.get("thickness_mm"))
            # Find a matching token on the drawing
            matched_tok = None
            for tok in tokens:
                if _section_matches_token(ew, eh, tok, tol):
                    matched_tok = tok
                    break
            if ew is None and eh is None:
                status = "Nema dimenzije u modelu"
                note = "Presjek elementa nije očitan iz .e2k"
                dim_text = "—"
            elif matched_tok is not None:
                status = "Dimenzija potvrđena na nacrtu"
                note = f"Presjek {matched_tok['raw']} pronađen na str. {matched_tok['page']} nacrta"
                dim_text = matched_tok["raw"]
            else:
                status = "Dimenzija nije nađena na nacrtu"
                note = "Nijedna kota na nacrtu ne odgovara ovom presjeku"
                dim_text = "—"
            rows.append({
                "element_type": elem_type,
                "status": status,
                "etabs_name": r.get("name", ""),
                "story": r.get("story", ""),
                "etabs_x": r.get("x_start", r.get("centroid_x", 0.0)),
                "etabs_y": r.get("y_start", r.get("centroid_y", 0.0)),
                "etabs_z": r.get("z_end", r.get("centroid_z", r.get("z_start", 0.0))),
                "etabs_section": r.get("section", r.get("prop_name", "")),
                "etabs_w_mm": ew,
                "etabs_h_mm": eh,
                "etabs_material": r.get("material", ""),
                "dxf_dim_text": dim_text,
                "dxf_dim1_mm": matched_tok["d1_mm"] if matched_tok else None,
                "dxf_dim2_mm": matched_tok["d2_mm"] if matched_tok else None,
                "xy_dist_m": None,
                "notes": note,
            })

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=STANDARD_COLS)
    df.attrs["pdf_dim_tokens"] = len(tokens)
    df.attrs["pdf_has_text_dims"] = has_dims
    return df
