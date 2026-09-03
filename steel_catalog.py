"""
steel_catalog.py
----------------
European structural steel sections database according to EN 10365 and EN 10210 / EN 10219.
Provides automatic section lookup, dimension resolution, and geometric property evaluation
for steel frames, beams, and columns without requiring explicit CAD polylines.
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Any

# Standard hot-rolled I and H sections (EN 10365)
# Dimensions in mm: h (height), b (flange width), tw (web thickness), tf (flange thickness), r (root radius)
# Area A in cm2
EUROPEAN_I_SECTIONS: Dict[str, Dict[str, Any]] = {
    # IPE series
    "IPE80":  {"h": 80,  "b": 46,  "tw": 3.8,  "tf": 5.2,  "r": 5,  "A": 7.64,  "shape": "I-section"},
    "IPE100": {"h": 100, "b": 55,  "tw": 4.1,  "tf": 5.7,  "r": 7,  "A": 10.3,  "shape": "I-section"},
    "IPE120": {"h": 120, "b": 64,  "tw": 4.4,  "tf": 6.3,  "r": 7,  "A": 13.2,  "shape": "I-section"},
    "IPE140": {"h": 140, "b": 73,  "tw": 4.7,  "tf": 6.9,  "r": 7,  "A": 16.4,  "shape": "I-section"},
    "IPE160": {"h": 160, "b": 82,  "tw": 5.0,  "tf": 7.4,  "r": 9,  "A": 20.1,  "shape": "I-section"},
    "IPE180": {"h": 180, "b": 91,  "tw": 5.3,  "tf": 8.0,  "r": 9,  "A": 23.9,  "shape": "I-section"},
    "IPE200": {"h": 200, "b": 100, "tw": 5.6,  "tf": 8.5,  "r": 12, "A": 28.5,  "shape": "I-section"},
    "IPE220": {"h": 220, "b": 110, "tw": 5.9,  "tf": 9.2,  "r": 12, "A": 33.4,  "shape": "I-section"},
    "IPE240": {"h": 240, "b": 120, "tw": 6.2,  "tf": 9.8,  "r": 15, "A": 39.1,  "shape": "I-section"},
    "IPE270": {"h": 270, "b": 135, "tw": 6.6,  "tf": 10.2, "r": 15, "A": 45.9,  "shape": "I-section"},
    "IPE300": {"h": 300, "b": 150, "tw": 7.1,  "tf": 10.7, "r": 15, "A": 53.8,  "shape": "I-section"},
    "IPE330": {"h": 330, "b": 160, "tw": 7.5,  "tf": 11.5, "r": 18, "A": 62.6,  "shape": "I-section"},
    "IPE360": {"h": 360, "b": 170, "tw": 8.0,  "tf": 12.7, "r": 18, "A": 72.7,  "shape": "I-section"},
    "IPE400": {"h": 400, "b": 180, "tw": 8.6,  "tf": 13.5, "r": 21, "A": 84.5,  "shape": "I-section"},
    "IPE450": {"h": 450, "b": 190, "tw": 9.4,  "tf": 14.6, "r": 21, "A": 98.8,  "shape": "I-section"},
    "IPE500": {"h": 500, "b": 200, "tw": 10.2, "tf": 16.0, "r": 21, "A": 116.0, "shape": "I-section"},
    "IPE550": {"h": 550, "b": 210, "tw": 11.1, "tf": 17.2, "r": 24, "A": 134.0, "shape": "I-section"},
    "IPE600": {"h": 600, "b": 220, "tw": 12.0, "tf": 19.0, "r": 24, "A": 156.0, "shape": "I-section"},

    # HEA series
    "HEA100": {"h": 96,  "b": 100, "tw": 5.0,  "tf": 8.0,  "r": 12, "A": 21.2,  "shape": "I-section"},
    "HEA120": {"h": 114, "b": 120, "tw": 5.0,  "tf": 8.0,  "r": 12, "A": 25.3,  "shape": "I-section"},
    "HEA140": {"h": 133, "b": 140, "tw": 5.5,  "tf": 8.5,  "r": 12, "A": 31.4,  "shape": "I-section"},
    "HEA160": {"h": 152, "b": 160, "tw": 6.0,  "tf": 9.0,  "r": 15, "A": 38.8,  "shape": "I-section"},
    "HEA180": {"h": 171, "b": 180, "tw": 6.0,  "tf": 9.5,  "r": 15, "A": 45.3,  "shape": "I-section"},
    "HEA200": {"h": 190, "b": 200, "tw": 6.5,  "tf": 10.0, "r": 18, "A": 53.8,  "shape": "I-section"},
    "HEA220": {"h": 210, "b": 220, "tw": 7.0,  "tf": 11.0, "r": 18, "A": 64.3,  "shape": "I-section"},
    "HEA240": {"h": 230, "b": 240, "tw": 7.5,  "tf": 12.0, "r": 21, "A": 76.8,  "shape": "I-section"},
    "HEA260": {"h": 250, "b": 260, "tw": 7.5,  "tf": 12.5, "r": 24, "A": 86.8,  "shape": "I-section"},
    "HEA280": {"h": 270, "b": 280, "tw": 8.0,  "tf": 13.0, "r": 24, "A": 97.3,  "shape": "I-section"},
    "HEA300": {"h": 290, "b": 300, "tw": 8.5,  "tf": 14.0, "r": 27, "A": 112.5, "shape": "I-section"},
    "HEA320": {"h": 310, "b": 300, "tw": 9.0,  "tf": 15.5, "r": 27, "A": 124.4, "shape": "I-section"},
    "HEA340": {"h": 330, "b": 300, "tw": 9.5,  "tf": 16.5, "r": 27, "A": 133.5, "shape": "I-section"},
    "HEA360": {"h": 350, "b": 300, "tw": 10.0, "tf": 17.5, "r": 27, "A": 142.8, "shape": "I-section"},
    "HEA400": {"h": 390, "b": 300, "tw": 11.0, "tf": 19.0, "r": 27, "A": 159.0, "shape": "I-section"},
    "HEA450": {"h": 440, "b": 300, "tw": 11.5, "tf": 21.0, "r": 27, "A": 178.0, "shape": "I-section"},
    "HEA500": {"h": 490, "b": 300, "tw": 12.0, "tf": 23.0, "r": 27, "A": 198.0, "shape": "I-section"},
    "HEA600": {"h": 590, "b": 300, "tw": 13.0, "tf": 25.0, "r": 27, "A": 226.0, "shape": "I-section"},

    # HEB series
    "HEB100": {"h": 100, "b": 100, "tw": 6.0,  "tf": 10.0, "r": 12, "A": 26.0,  "shape": "I-section"},
    "HEB120": {"h": 120, "b": 120, "tw": 6.5,  "tf": 11.0, "r": 12, "A": 34.0,  "shape": "I-section"},
    "HEB140": {"h": 140, "b": 140, "tw": 7.0,  "tf": 12.0, "r": 12, "A": 43.0,  "shape": "I-section"},
    "HEB160": {"h": 160, "b": 160, "tw": 8.0,  "tf": 13.0, "r": 15, "A": 54.3,  "shape": "I-section"},
    "HEB180": {"h": 180, "b": 180, "tw": 8.5,  "tf": 14.0, "r": 15, "A": 65.3,  "shape": "I-section"},
    "HEB200": {"h": 200, "b": 200, "tw": 9.0,  "tf": 15.0, "r": 18, "A": 78.1,  "shape": "I-section"},
    "HEB220": {"h": 220, "b": 220, "tw": 9.5,  "tf": 16.0, "r": 18, "A": 91.0,  "shape": "I-section"},
    "HEB240": {"h": 240, "b": 240, "tw": 10.0, "tf": 17.0, "r": 21, "A": 106.0, "shape": "I-section"},
    "HEB260": {"h": 260, "b": 260, "tw": 10.0, "tf": 17.5, "r": 24, "A": 118.4, "shape": "I-section"},
    "HEB280": {"h": 280, "b": 280, "tw": 10.5, "tf": 18.0, "r": 24, "A": 131.4, "shape": "I-section"},
    "HEB300": {"h": 300, "b": 300, "tw": 11.0, "tf": 19.0, "r": 27, "A": 149.1, "shape": "I-section"},
    "HEB320": {"h": 320, "b": 300, "tw": 11.5, "tf": 20.5, "r": 27, "A": 161.3, "shape": "I-section"},
    "HEB360": {"h": 360, "b": 300, "tw": 12.5, "tf": 22.5, "r": 27, "A": 180.6, "shape": "I-section"},
    "HEB400": {"h": 400, "b": 300, "tw": 13.5, "tf": 24.0, "r": 27, "A": 197.8, "shape": "I-section"},
    "HEB500": {"h": 500, "b": 300, "tw": 14.5, "tf": 28.0, "r": 27, "A": 238.6, "shape": "I-section"},
    "HEB600": {"h": 600, "b": 300, "tw": 15.5, "tf": 30.0, "r": 27, "A": 270.0, "shape": "I-section"},

    # HEM series (heavy beams)
    "HEM100": {"h": 120, "b": 106, "tw": 12.0, "tf": 20.0, "r": 12, "A": 53.2,  "shape": "I-section"},
    "HEM140": {"h": 160, "b": 146, "tw": 13.0, "tf": 22.0, "r": 12, "A": 80.6,  "shape": "I-section"},
    "HEM180": {"h": 200, "b": 186, "tw": 14.5, "tf": 24.0, "r": 15, "A": 113.3, "shape": "I-section"},
    "HEM200": {"h": 220, "b": 206, "tw": 15.0, "tf": 25.0, "r": 18, "A": 131.3, "shape": "I-section"},
    "HEM240": {"h": 270, "b": 248, "tw": 18.0, "tf": 32.0, "r": 21, "A": 199.6, "shape": "I-section"},
    "HEM300": {"h": 340, "b": 310, "tw": 21.0, "tf": 39.0, "r": 27, "A": 303.1, "shape": "I-section"},

    # UPN series (channels)
    "UPN50":  {"h": 50,  "b": 38,  "tw": 5.0,  "tf": 7.0,  "r": 7,  "A": 7.12,  "shape": "channel"},
    "UPN80":  {"h": 80,  "b": 45,  "tw": 6.0,  "tf": 8.0,  "r": 8,  "A": 11.0,  "shape": "channel"},
    "UPN100": {"h": 100, "b": 50,  "tw": 6.0,  "tf": 8.5,  "r": 8.5,"A": 13.5,  "shape": "channel"},
    "UPN120": {"h": 120, "b": 55,  "tw": 7.0,  "tf": 9.0,  "r": 9,  "A": 17.0,  "shape": "channel"},
    "UPN140": {"h": 140, "b": 60,  "tw": 7.0,  "tf": 10.0, "r": 10, "A": 20.4,  "shape": "channel"},
    "UPN160": {"h": 160, "b": 65,  "tw": 7.5,  "tf": 10.5, "r": 10.5,"A": 24.0, "shape": "channel"},
    "UPN180": {"h": 180, "b": 70,  "tw": 8.0,  "tf": 11.0, "r": 11, "A": 28.0,  "shape": "channel"},
    "UPN200": {"h": 200, "b": 75,  "tw": 8.5,  "tf": 11.5, "r": 11.5,"A": 32.2, "shape": "channel"},
    "UPN220": {"h": 220, "b": 80,  "tw": 9.0,  "tf": 12.5, "r": 12.5,"A": 37.4, "shape": "channel"},
    "UPN240": {"h": 240, "b": 85,  "tw": 9.5,  "tf": 13.0, "r": 13, "A": 42.3,  "shape": "channel"},
    "UPN260": {"h": 260, "b": 90,  "tw": 10.0, "tf": 14.0, "r": 14, "A": 48.3,  "shape": "channel"},
    "UPN300": {"h": 300, "b": 100, "tw": 10.0, "tf": 16.0, "r": 16, "A": 58.8,  "shape": "channel"},
}


def lookup_steel_section(name: str) -> Optional[Dict[str, Any]]:
    """
    Looks up a standard European steel section by name.
    Handles various naming conventions, e.g.:
    - "HEA 240", "HEA240", "HE 240 A", "HE240A", "HEA-240"
    - "HEB 200", "HEB200", "HE 200 B", "HE200B"
    - "HEM 300", "HEM300", "HE 300 M"
    - "IPE 300", "IPE300", "IPE-300", "IPE 300 A"
    - "UPN 160", "UPN160", "U 160"
    - "SHS 100x5", "SHS 100x100x5", "VKR 100x5"
    - "RHS 120x80x6", "PKR 120x80x6"
    - "PIPE 114.3x4.5", "CHS 114.3x4.5", "RO 108x4"
    """
    if not name or not isinstance(name, str):
        return None

    clean = name.upper().strip().replace("-", " ").replace("_", " ")

    # 1. Direct or normalized lookup in standard I/H/U sections table
    # Standardize HEA/HEB/HEM variants like "HE 240 A" -> "HEA240"
    m_he = re.match(r"^HE\s*(\d{2,4})\s*([ABM])$", clean)
    if m_he:
        key = f"HE{m_he.group(2)}{m_he.group(1)}"
        if key in EUROPEAN_I_SECTIONS:
            res = dict(EUROPEAN_I_SECTIONS[key])
            res["name"] = key
            res["height_mm"] = res["h"]
            res["width_mm"] = res["b"]
            return res

    # Remove spaces: "IPE 300" -> "IPE300"
    compact = re.sub(r"\s+", "", clean)
    if compact in EUROPEAN_I_SECTIONS:
        res = dict(EUROPEAN_I_SECTIONS[compact])
        res["name"] = compact
        res["height_mm"] = res["h"]
        res["width_mm"] = res["b"]
        return res

    # 2. Check for UPN variants: "U 160", "UNP 160", "UPN 160"
    m_upn = re.match(r"^(?:UPN|UNP|U)\s*(\d{2,3})$", clean)
    if m_upn:
        key = f"UPN{m_upn.group(1)}"
        if key in EUROPEAN_I_SECTIONS:
            res = dict(EUROPEAN_I_SECTIONS[key])
            res["name"] = key
            res["height_mm"] = res["h"]
            res["width_mm"] = res["b"]
            return res

    # 3. Square Hollow Sections (SHS / VKR / Kvadratna cijev)
    # e.g., "SHS 100x100x5", "SHS 100x5", "VKR 80x80x4"
    m_shs = re.search(r"(?:SHS|VKR|KVADRAT|QUAD|Q)\s*(\d+)(?:\s*[X*]\s*(\d+))?\s*[X*]\s*(\d+(?:\.\d+)?)", clean)
    if m_shs:
        size = float(m_shs.group(1))
        thick = float(m_shs.group(3))
        return {
            "name": f"SHS {int(size)}x{int(size)}x{thick:g}",
            "shape": "box",
            "shape_type": "box",
            "h": size,
            "b": size,
            "height_mm": size,
            "width_mm": size,
            "tw": thick,
            "tf": thick,
            "thickness_mm": thick,
        }

    # 4. Rectangular Hollow Sections (RHS / PKR / Pravokutna cijev)
    # e.g., "RHS 120x80x6", "PKR 140x80x5", "120x80x6"
    m_rhs = re.search(r"(?:RHS|PKR|RECT|PRAVOKUTNA)?\s*(\d+)\s*[X*]\s*(\d+)\s*[X*]\s*(\d+(?:\.\d+)?)", clean)
    if m_rhs:
        h_val = float(m_rhs.group(1))
        b_val = float(m_rhs.group(2))
        thick = float(m_rhs.group(3))
        h_dim = max(h_val, b_val)
        b_dim = min(h_val, b_val)
        return {
            "name": f"RHS {int(h_dim)}x{int(b_dim)}x{thick:g}",
            "shape": "box",
            "shape_type": "box",
            "h": h_dim,
            "b": b_dim,
            "height_mm": h_dim,
            "width_mm": b_dim,
            "tw": thick,
            "tf": thick,
            "thickness_mm": thick,
        }

    # 5. Circular Hollow Sections / Pipes (CHS / RO / Cijev)
    # e.g., "CHS 114.3x4.5", "PIPE 114.3x4.5", "RO 88.9x3.2", "FI 108x4"
    m_chs = re.search(r"(?:CHS|PIPE|RO|FI|Ø)\s*(\d+(?:\.\d+)?)\s*[X*]\s*(\d+(?:\.\d+)?)", clean)
    if m_chs:
        dia = float(m_chs.group(1))
        thick = float(m_chs.group(2))
        return {
            "name": f"CHS {dia:g}x{thick:g}",
            "shape": "pipe",
            "shape_type": "pipe",
            "diameter_mm": dia,
            "h": dia,
            "b": dia,
            "height_mm": dia,
            "width_mm": dia,
            "thickness_mm": thick,
        }

    return None
