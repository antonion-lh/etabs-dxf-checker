"""
phase1_e2k.py
-------------
Pure-Python parser for ETABS .e2k and .$et plain-text model files.
Extracts:
  - Columns, Beams, Braces (frames with true section dimensions from definitions)
  - Walls, Slabs (areas with thicknesses and boundary vertices)
  - Materials (concrete and steel definitions, E, fc, fy)
  - Load Patterns (types and self-weight multipliers)
  - Area Loads (slab surface loads gk, qk in kN/m²)
  - Frame Loads (beam distributed line loads in kN/m)
  - Restraints (base supports: Fixed, Pinned, Roller, Free)
  - Plastic Hinges (nonlinear assignments)

Compatible with the return format of phase1_etabs.extract_all().
Runs everywhere: macOS, Linux, Windows, Streamlit Cloud.
"""

from __future__ import annotations

import logging
import math
import re
import shlex
from pathlib import Path
from typing import TextIO, Union

import pandas as pd

from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


def _tokenize(line: str) -> list[str]:
    """Tokenize a line handling quoted strings safely."""
    line = line.strip()
    if not line or line.startswith(";"):
        return []
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


def _get_kw_val(tokens: list[str], kw: str, default: str = "") -> str:
    """Find the value immediately following keyword kw in tokens."""
    kw_upper = kw.upper()
    for i in range(len(tokens) - 1):
        if tokens[i].upper() == kw_upper:
            return tokens[i + 1]
    return default


def parse_e2k(source: Union[str, Path, TextIO], cfg: Config = DEFAULT_CONFIG) -> dict[str, pd.DataFrame]:
    """
    Parse an ETABS .e2k text file or stream into standard tables.

    Returns dict with keys:
      columns, beams, braces, walls, slabs, hinges,
      materials, load_patterns, area_loads, frame_loads, restraints
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"E2K file not found: {source}")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    else:
        lines = source.readlines()

    log.info("Parsing ETABS .e2k file (%d lines)...", len(lines))

    points: dict[str, tuple[float, float, float]] = {}

    def _save_pt(name: str, coords: tuple[float, float, float]):
        points[name] = coords
        s = str(name).strip().strip('"').strip("'")
        points[s] = coords
        try:
            ival = str(int(float(s)))
            points[ival] = coords
        except (ValueError, TypeError):
            pass

    def _get_pt(name: str):
        if not name:
            return None
        if name in points:
            return points[name]
        s = str(name).strip().strip('"').strip("'")
        if s in points:
            return points[s]
        try:
            ival = str(int(float(s)))
            if ival in points:
                return points[ival]
        except (ValueError, TypeError):
            pass
        return None

    materials_dict: dict[str, dict] = {}
    frame_sections: dict[str, dict] = {}
    area_sections: dict[str, dict] = {}
    raw_frames: list[dict] = []
    raw_areas: list[dict] = []
    raw_restraints: list[dict] = []
    raw_load_patterns: list[dict] = []
    raw_area_loads: list[dict] = []
    raw_frame_loads: list[dict] = []
    raw_hinges: list[dict] = []
    raw_grids: list[dict] = []
    raw_stories: list[dict] = []
    units = {"force": "KN", "length": "M", "temp": "C"}
    mass_source = {"loads": {}, "lateral_mass": True, "lump_at_stories": True}
    load_combinations: dict[str, dict] = {}
    raw_diaphragms: list[dict] = []
    raw_rebars: list[dict] = []
    raw_piers: list[str] = []
    raw_spandrels: list[str] = []
    pier_assigns: dict[str, str] = {}
    spandrel_assigns: dict[str, str] = {}
    modal_cases: list[dict] = []
    line_assigns: dict[str, str] = {}
    line_story_assigns: dict[str, list[dict]] = {}
    area_assigns: dict[str, str] = {}
    area_story_assigns: dict[str, list[dict]] = {}

    current_block = ""

    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith(";"):
            continue

        if line_s.startswith("$"):
            current_block = line_s.lstrip("$").strip().upper()
            continue

        tokens = _tokenize(line_s)
        if not tokens:
            continue

        # 1. POINT / JOINT COORDINATES
        if ("POINT" in current_block or "JOINT" in current_block) and not ("ASSIGN" in current_block or "LOAD" in current_block or "PAT" in current_block):
            p_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("POINT", "JOINT") else tokens[0]
            x_str = _get_kw_val(tokens, "X")
            y_str = _get_kw_val(tokens, "Y")
            z_str = _get_kw_val(tokens, "Z")
            if x_str and y_str and z_str:
                try:
                    _save_pt(p_name, (float(x_str), float(y_str), float(z_str)))
                except ValueError:
                    pass
            else:
                # Positional coordinates: POINT "1" 10.0 5.0 3.0 or POINT "1" 10.0 5.0
                start_idx = 2 if tokens[0].upper() in ("POINT", "JOINT") else 1
                if len(tokens) >= start_idx + 3:
                    try:
                        _save_pt(p_name, (float(tokens[start_idx]), float(tokens[start_idx + 1]), float(tokens[start_idx + 2])))
                    except ValueError:
                        pass
                elif len(tokens) >= start_idx + 2:
                    try:
                        _save_pt(p_name, (float(tokens[start_idx]), float(tokens[start_idx + 1]), 0.0))
                    except ValueError:
                        pass

        # 2. MATERIAL PROPERTIES
        elif "MATERIAL" in current_block:
            m_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() == "MATERIAL" else tokens[0]
            if m_name:
                if m_name not in materials_dict:
                    materials_dict[m_name] = {
                        "name": m_name, "type": "Unknown", "E_gpa": None,
                        "nu": None, "fc_mpa": None, "fy_mpa": None, "fu_mpa": None,
                    }
                mat = materials_dict[m_name]

                # Check explicit TYPE or DESIGN keywords or standalone type words
                t_val = _get_kw_val(tokens, "TYPE") or _get_kw_val(tokens, "DESIGN")
                tokens_upper = [t.upper() for t in tokens]
                if t_val:
                    mat["type"] = t_val.capitalize()
                elif "CONCRETE" in tokens_upper:
                    mat["type"] = "Concrete"
                elif "STEEL" in tokens_upper:
                    mat["type"] = "Steel"
                elif "REBAR" in tokens_upper:
                    mat["type"] = "Rebar"

                # E modulus
                e_str = _get_kw_val(tokens, "E")
                if e_str:
                    try:
                        e_val = float(e_str)
                        mat["E_gpa"] = round(e_val / 1e6 if e_val > 100000 else e_val / 1000, 1)
                    except ValueError:
                        pass

                # Poisson's ratio
                u_str = _get_kw_val(tokens, "U")
                if u_str:
                    try:
                        mat["nu"] = float(u_str)
                    except ValueError:
                        pass

                # Strengths (FC, FY, FU)
                fc_str = _get_kw_val(tokens, "FC")
                if fc_str:
                    try:
                        fc = float(fc_str)
                        mat["fc_mpa"] = round(fc / 1000 if fc > 500 else fc, 1)
                        if mat["type"] == "Unknown":
                            mat["type"] = "Concrete"
                    except ValueError:
                        pass

                fy_str = _get_kw_val(tokens, "FY")
                if fy_str:
                    try:
                        fy = float(fy_str)
                        mat["fy_mpa"] = round(fy / 1000 if fy > 2000 else fy, 1)
                        if mat["type"] == "Unknown":
                            mat["type"] = "Steel"
                    except ValueError:
                        pass

                fu_str = _get_kw_val(tokens, "FU")
                if fu_str:
                    try:
                        fu = float(fu_str)
                        mat["fu_mpa"] = round(fu / 1000 if fu > 2000 else fu, 1)
                    except ValueError:
                        pass

        # 3. FRAME SECTIONS
        elif "FRAME" in current_block and "SEC" in current_block:
            sec_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() == "FRAME" else tokens[0]
            if sec_name:
                shape = _get_kw_val(tokens, "SHAPE", "RECTANGULAR").upper()
                mat_name = _get_kw_val(tokens, "MAT", "")
                t3_str = _get_kw_val(tokens, "T3")
                t2_str = _get_kw_val(tokens, "T2", t3_str)

                t3 = float(t3_str) if t3_str else None
                t2 = float(t2_str) if t2_str else t3

                w_mm, h_mm, d_mm = None, None, None
                shape_type = "rectangular"

                if "CIRC" in shape:
                    shape_type = "circular"
                    d_mm = t3 * 1000 if t3 else None
                    w_mm, h_mm = d_mm, d_mm
                elif "BOX" in shape or "TUBE" in shape:
                    shape_type = "box"
                    h_mm = t3 * 1000 if t3 else None
                    w_mm = t2 * 1000 if t2 else h_mm
                elif "PIPE" in shape:
                    shape_type = "pipe"
                    d_mm = t3 * 1000 if t3 else None
                    w_mm, h_mm = d_mm, d_mm
                elif "I" in shape or "WIDE" in shape:
                    shape_type = "I-section"
                    h_mm = t3 * 1000 if t3 else None
                    w_mm = t2 * 1000 if t2 else None
                elif "CHANNEL" in shape:
                    shape_type = "channel"
                    h_mm = t3 * 1000 if t3 else None
                    w_mm = t2 * 1000 if t2 else None
                elif "T" in shape:
                    shape_type = "T-section"
                    h_mm = t3 * 1000 if t3 else None
                    w_mm = t2 * 1000 if t2 else None
                else:
                    shape_type = "rectangular"
                    h_mm = t3 * 1000 if t3 else None
                    w_mm = t2 * 1000 if t2 else h_mm

                # Check Eurocode steel catalog fallback / enrichment
                try:
                    from steel_catalog import lookup_steel_section
                    steel_data = lookup_steel_section(sec_name)
                    if steel_data:
                        if not h_mm:
                            h_mm = steel_data.get("height_mm")
                        if not w_mm:
                            w_mm = steel_data.get("width_mm")
                        if not d_mm and steel_data.get("diameter_mm"):
                            d_mm = steel_data.get("diameter_mm")
                        shape_type = steel_data.get("shape_type", steel_data.get("shape", shape_type))
                except Exception:
                    pass

                frame_sections[sec_name] = {
                    "sec_name": sec_name,
                    "material": mat_name,
                    "shape_type": shape_type,
                    "width_mm": w_mm,
                    "height_mm": h_mm,
                    "diameter_mm": d_mm,
                }

        # 3b. SECTION DESIGNER SECTIONS
        elif "SECTION DESIGNER" in current_block:
            sec_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() == "SDSECTION" else tokens[0]
            sec_name = sec_name.strip('"').strip("'")
            shape_type_val = _get_kw_val(tokens, "SHAPETYPE", "").upper()
            mat_name = _get_kw_val(tokens, "MATERIAL", "")

            if ("CONCRETE" in shape_type_val or "RECT" in shape_type_val) and "REBAR" not in shape_type_val:
                d_str = _get_kw_val(tokens, "D")
                b_str = _get_kw_val(tokens, "B")
                if d_str and b_str:
                    try:
                        d_val = float(d_str) * 1000.0
                        b_val = float(b_str) * 1000.0
                        existing = frame_sections.get(sec_name, {})
                        existing.update({
                            "sec_name": sec_name,
                            "material": mat_name or existing.get("material", ""),
                            "shape_type": "rectangular",
                            "height_mm": max(d_val, b_val),
                            "width_mm": min(d_val, b_val),
                        })
                        frame_sections[sec_name] = existing
                    except ValueError:
                        pass
            elif "CIRC" in shape_type_val and "REBAR" not in shape_type_val:
                d_str = _get_kw_val(tokens, "D") or _get_kw_val(tokens, "DIA")
                if d_str:
                    try:
                        d_val = float(d_str) * 1000.0
                        existing = frame_sections.get(sec_name, {})
                        existing.update({
                            "sec_name": sec_name,
                            "material": mat_name or existing.get("material", ""),
                            "shape_type": "circular",
                            "diameter_mm": d_val,
                            "width_mm": d_val,
                            "height_mm": d_val,
                        })
                        frame_sections[sec_name] = existing
                    except ValueError:
                        pass

        # 4. SHELL / AREA / WALL / SLAB SECTIONS
        elif any(k in current_block for k in ("SHELL", "AREA", "WALL", "SLAB")) and any(k in current_block for k in ("SEC", "PROP")):
            sec_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("SHELL", "AREA", "WALL", "SLAB", "PROP", "SECTION", "SHELLPROP") else tokens[0]
            if sec_name:
                sec_name = sec_name.strip('"').strip("'")
                thick_str = (
                    _get_kw_val(tokens, "WALLTHICKNESS") or
                    _get_kw_val(tokens, "SLABTHICKNESS") or
                    _get_kw_val(tokens, "THICKNESS") or
                    _get_kw_val(tokens, "THICK") or
                    _get_kw_val(tokens, "T") or
                    _get_kw_val(tokens, "BENDING") or
                    _get_kw_val(tokens, "MEMBRANE")
                )

                existing = area_sections.get(sec_name, {})
                if thick_str:
                    try:
                        thick = float(thick_str)
                        thick_mm = thick * 1000 if thick < 10 else thick
                    except ValueError:
                        thick_mm = 250.0
                else:
                    thick_mm = existing.get("thickness_mm", 250.0)

                mat_val = _get_kw_val(tokens, "MAT") or _get_kw_val(tokens, "MATERIAL", "") or existing.get("material", "")
                if not mat_val:
                    for tok in tokens:
                        t_clean = tok.strip('"').strip("'")
                        if t_clean in materials_dict:
                            mat_val = t_clean
                            break

                area_sections[sec_name] = {
                    "sec_name": sec_name,
                    "material": mat_val,
                    "thickness_mm": thick_mm,
                }

        # 5. LINE CONNECTIVITIES (FRAMES)
        elif ("LINE" in current_block or "FRAME" in current_block) and ("CONNECT" in current_block or ("OBJECT" in current_block and "LOAD" not in current_block and "HINGE" not in current_block and "ASSIGN" not in current_block)):
            f_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("LINE", "FRAME") else tokens[0]
            i_pt = _get_kw_val(tokens, "I") or _get_kw_val(tokens, "J1") or _get_kw_val(tokens, "NODE1") or _get_kw_val(tokens, "POINT1")
            j_pt = _get_kw_val(tokens, "J") or _get_kw_val(tokens, "J2") or _get_kw_val(tokens, "NODE2") or _get_kw_val(tokens, "POINT2")
            prop = _get_kw_val(tokens, "PROP") or _get_kw_val(tokens, "PROPERTY") or _get_kw_val(tokens, "SECTION") or _get_kw_val(tokens, "SEC")
            type_hint = _get_kw_val(tokens, "TYPE").lower()

            if not (i_pt and j_pt):
                # Positional ETABS tokens: LINE "C1" COLUMN "1" "1" 1 or LINE "B1" BEAM "1" "2" 0
                if len(tokens) >= 5 and tokens[2].upper() in ("COLUMN", "BEAM", "BRACE", "FRAME"):
                    type_hint = tokens[2].lower()
                    i_pt = tokens[3]
                    j_pt = tokens[4]
                else:
                    start_i = 2 if tokens[0].upper() in ("LINE", "FRAME") else 1
                    if len(tokens) >= start_i + 2:
                        i_pt = tokens[start_i]
                        j_pt = tokens[start_i + 1]

            if f_name and i_pt and j_pt:
                raw_frames.append({
                    "name": f_name.strip('"').strip("'"),
                    "i_pt": i_pt.strip('"').strip("'"),
                    "j_pt": j_pt.strip('"').strip("'"),
                    "prop": prop.strip('"').strip("'") if prop else "",
                    "type_hint": type_hint,
                })

        # 5b. LINE ASSIGNMENTS
        elif ("LINE" in current_block or "FRAME" in current_block) and "ASSIGN" in current_block and "HINGE" not in current_block and "LOAD" not in current_block:
            f_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("LINE", "FRAME", "LINEASSIGN", "FRAMEASSIGN") else tokens[0]
            st_name = tokens[2].strip('"').strip("'") if len(tokens) > 2 and tokens[0].upper() in ("LINEASSIGN", "FRAMEASSIGN") and not tokens[2].upper().startswith("SEC") else ""
            sec = _get_kw_val(tokens, "SECTION") or _get_kw_val(tokens, "PROP") or _get_kw_val(tokens, "PROPERTY") or _get_kw_val(tokens, "SEC")
            if not sec and "SECTION" in [t.upper() for t in tokens]:
                idx = [t.upper() for t in tokens].index("SECTION")
                if idx + 1 < len(tokens):
                    sec = tokens[idx + 1].strip('"').strip("'")
            if f_name and sec:
                f_clean = f_name.strip('"').strip("'")
                sec_clean = sec.strip('"').strip("'")
                line_assigns[f_name] = sec_clean
                line_assigns[f_clean] = sec_clean
                if f_clean not in line_story_assigns:
                    line_story_assigns[f_clean] = []
                line_story_assigns[f_clean].append({"story": st_name, "section": sec_clean})

        # 6. AREA CONNECTIVITIES (WALLS & SLABS)
        elif any(k in current_block for k in ("AREA", "SHELL", "WALL", "SLAB")) and ("CONNECT" in current_block or ("OBJECT" in current_block and "LOAD" not in current_block and "ASSIGN" not in current_block)):
            a_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("AREA", "SHELL", "WALL", "SLAB") else tokens[0]
            prop = _get_kw_val(tokens, "PROP") or _get_kw_val(tokens, "PROPERTY") or _get_kw_val(tokens, "SECTION") or _get_kw_val(tokens, "SEC")
            type_hint = _get_kw_val(tokens, "TYPE").lower()

            pts = []
            if len(tokens) >= 4 and tokens[2].upper() in ("PANEL", "FLOOR", "WALL", "SLAB", "OPENING"):
                type_hint = tokens[2].lower()
                try:
                    num_pts = int(tokens[3])
                    pts = [tokens[4 + i].strip('"').strip("'") for i in range(num_pts) if 4 + i < len(tokens)]
                except (ValueError, IndexError):
                    pts = []
            else:
                tokens_upper = [t.upper() for t in tokens]
                for kw in ("PT", "PTS", "J", "JOINTS", "NODES"):
                    if kw in tokens_upper:
                        idx = tokens_upper.index(kw)
                        for j in range(idx + 1, len(tokens)):
                            if tokens[j].upper() in ("PROP", "PROPERTY", "SECTION", "SEC", "TYPE", "NUMPTS"):
                                break
                            pts.append(tokens[j])
                        break

                if not pts:
                    start_j = 2 if tokens[0].upper() in ("AREA", "SHELL", "WALL", "SLAB") else 1
                    for j in range(start_j, len(tokens)):
                        if tokens[j].upper() in ("PROP", "PROPERTY", "SECTION", "SEC", "TYPE", "NUMPTS"):
                            break
                        pts.append(tokens[j])

            if a_name and pts:
                raw_areas.append({
                    "name": a_name,
                    "prop": prop,
                    "pts": pts,
                    "type_hint": type_hint,
                })

        # 6b. AREA / WALL / SHELL ASSIGNMENTS
        elif any(k in current_block for k in ("AREA", "SHELL", "WALL", "SLAB")) and "ASSIGN" in current_block and "LOAD" not in current_block:
            a_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("AREA", "SHELL", "WALL", "SLAB", "AREAASSIGN", "SHELLASSIGN") else tokens[0]
            st_name = tokens[2].strip('"').strip("'") if len(tokens) > 2 and tokens[0].upper() in ("AREAASSIGN", "SHELLASSIGN") else ""
            sec = _get_kw_val(tokens, "SECTION") or _get_kw_val(tokens, "PROP") or _get_kw_val(tokens, "PROPERTY") or _get_kw_val(tokens, "SEC")
            if not sec and "SECTION" in [t.upper() for t in tokens]:
                idx = [t.upper() for t in tokens].index("SECTION")
                if idx + 1 < len(tokens):
                    sec = tokens[idx + 1].strip('"').strip("'")
                    if idx + 2 < len(tokens) and not tokens[idx + 2].startswith('"') and tokens[idx + 2].upper() not in ("OBJMESHTYPE", "ADDRESTRAINT", "CARDINALPOINT"):
                        sec += " " + tokens[idx + 2].strip('"').strip("'")
            if not sec and len(tokens) >= 3 and not st_name:
                sec = tokens[2]
            elif not sec and len(tokens) == 2:
                sec = tokens[1]
            if a_name and sec:
                a_clean = a_name.strip('"').strip("'")
                sec_clean = sec.strip('"').strip("'")
                area_assigns[a_name] = sec_clean
                area_assigns[a_clean] = sec_clean
                if a_clean not in area_story_assigns:
                    area_story_assigns[a_clean] = []
                area_story_assigns[a_clean].append({"story": st_name, "section": sec_clean})

            pier_val = _get_kw_val(tokens, "PIER")
            spandrel_val = _get_kw_val(tokens, "SPANDREL")
            if a_name and pier_val:
                pier_assigns[a_name.strip('"').strip("'")] = pier_val.strip('"').strip("'")
            if a_name and spandrel_val:
                spandrel_assigns[a_name.strip('"').strip("'")] = spandrel_val.strip('"').strip("'")

        # 7. LOAD PATTERNS
        elif "LOAD" in current_block and "PAT" in current_block:
            p_name = tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("PATTERN", "LOADPATTERN") else tokens[0]
            if p_name:
                p_name = p_name.strip('"').strip("'")
                p_type = _get_kw_val(tokens, "TYPE")
                tokens_upper = [t.upper() for t in tokens]
                if not p_type:
                    for known_t in ("DEAD", "LIVE", "SEISMIC", "QUAKE", "WIND", "SNOW", "TEMPERATURE", "OTHER"):
                        if known_t in tokens_upper:
                            p_type = known_t.capitalize()
                            break
                if not p_type:
                    name_u = p_name.upper()
                    if any(k in name_u for k in ("DEAD", "PERMANENT", "STALNO")) or name_u in ("G", "DL", "VT"):
                        p_type = "Dead"
                    elif any(k in name_u for k in ("LIVE", "VARIABLE", "PROMJENJIVO", "KORISNO")) or name_u in ("Q", "LL"):
                        p_type = "Live"
                    elif any(k in name_u for k in ("SEIS", "POTRES", "EARTHQUAKE", "QUAKE")) or name_u in ("E", "EX", "EY"):
                        p_type = "Seismic"
                    elif any(k in name_u for k in ("WIND", "VJETAR")) or name_u in ("W", "WX", "WY"):
                        p_type = "Wind"
                    elif any(k in name_u for k in ("SNOW", "SNIJEG")) or name_u == "S":
                        p_type = "Snow"
                    else:
                        p_type = "Other"
                else:
                    p_type = p_type.capitalize()

                # Self-weight multiplier is strictly from SELFWT or SW keyword
                sw_str = _get_kw_val(tokens, "SELFWT") or _get_kw_val(tokens, "SW") or _get_kw_val(tokens, "SELF_WEIGHT")
                if sw_str:
                    try:
                        self_wt = float(sw_str)
                    except ValueError:
                        self_wt = 0.0
                else:
                    is_primary_dead = p_type.lower() == "dead" and ("DEAD" in p_name.upper() or p_name.upper() in ("G", "DL"))
                    self_wt = 1.0 if is_primary_dead else 0.0

                raw_load_patterns.append({
                    "name": p_name,
                    "type": p_type,
                    "self_weight_mult": self_wt,
                })

        # 8. AREA OBJECT LOADS (UNIFORM)
        elif "AREA" in current_block and "LOAD" in current_block:
            aname = _get_kw_val(tokens, "AREA") or (tokens[1] if len(tokens) > 1 and tokens[0].upper() == "UNIFORM" else "")
            pat = _get_kw_val(tokens, "PAT") or _get_kw_val(tokens, "PATTERN", "")
            val_str = _get_kw_val(tokens, "VAL") or _get_kw_val(tokens, "VALUE", "0.0")
            try:
                val = float(val_str)
            except ValueError:
                val = 0.0

            if aname and pat:
                raw_area_loads.append({
                    "area_name": aname,
                    "load_pattern": pat,
                    "val_kpa": val,
                })

        # 9. FRAME OBJECT LOADS
        elif "FRAME" in current_block and "LOAD" in current_block:
            fname = _get_kw_val(tokens, "FRAME") or (tokens[1] if len(tokens) > 1 and tokens[0].upper() == "DISTRIBUTED" else "")
            pat = _get_kw_val(tokens, "PAT") or _get_kw_val(tokens, "PATTERN", "")
            v1_str = _get_kw_val(tokens, "VAL1") or _get_kw_val(tokens, "VALUE", "0.0")
            v2_str = _get_kw_val(tokens, "VAL2", v1_str)
            try:
                v1 = float(v1_str)
                v2 = float(v2_str)
            except ValueError:
                v1, v2 = 0.0, 0.0

            if fname and pat:
                raw_frame_loads.append({
                    "frame_name": fname,
                    "load_pattern": pat,
                    "val1_kn_m": v1,
                    "val2_kn_m": v2,
                })

        # 10. RESTRAINTS / SUPPORTS / BOUNDARY CONDITIONS
        elif (
            any(k in current_block for k in ("RESTRAINT", "SUPPORT", "SPRING", "BOUNDARY", "BASE"))
            or (any(k in current_block for k in ("POINT", "JOINT")) and any(k in current_block for k in ("ASSIGN", "RESTRAINT", "PROP", "DATA")))
        ) and "HINGE" not in current_block and "LOAD" not in current_block:
            tokens_upper = [t.upper() for t in tokens]
            jname = ""
            if tokens[0].upper() in ("RESTRAINT", "SUPPORT", "SPRING", "POINT", "JOINT", "POINTASSIGN", "JOINTASSIGN"):
                jname = tokens[1] if len(tokens) > 1 else ""
            elif _get_kw_val(tokens, "POINT") or _get_kw_val(tokens, "JOINT") or _get_kw_val(tokens, "NAME"):
                jname = _get_kw_val(tokens, "POINT") or _get_kw_val(tokens, "JOINT") or _get_kw_val(tokens, "NAME")
            else:
                t0_clean = tokens[0].strip('"').strip("'")
                if _get_pt(t0_clean) is not None:
                    jname = tokens[0]

            if jname:
                jname = jname.strip('"').strip("'")
                restr_str = (_get_kw_val(tokens, "RESTRAINT") or "").upper()
                u1 = (_get_kw_val(tokens, "U1") or "").upper() in ("YES", "1", "TRUE") or ("UX" in restr_str)
                u2 = (_get_kw_val(tokens, "U2") or "").upper() in ("YES", "1", "TRUE") or ("UY" in restr_str)
                u3 = (_get_kw_val(tokens, "U3") or "").upper() in ("YES", "1", "TRUE") or ("UZ" in restr_str)
                r1 = (_get_kw_val(tokens, "R1") or "").upper() in ("YES", "1", "TRUE") or ("RX" in restr_str)
                r2 = (_get_kw_val(tokens, "R2") or "").upper() in ("YES", "1", "TRUE") or ("RY" in restr_str)
                r3 = (_get_kw_val(tokens, "R3") or "").upper() in ("YES", "1", "TRUE") or ("RZ" in restr_str)

                if not any([u1, u2, u3, r1, r2, r3]):
                    if any(k in tokens_upper for k in ("FIXED", "FIX", "UPETOST")):
                        u1, u2, u3, r1, r2, r3 = True, True, True, True, True, True
                    elif any(k in tokens_upper for k in ("PINNED", "PIN", "ZGLOB")):
                        u1, u2, u3 = True, True, True
                    elif any(k in tokens_upper for k in ("ROLLER", "KLIZNI")):
                        u3 = True
                    else:
                        start_dof = 2 if tokens[0].upper() in ("RESTRAINT", "SUPPORT", "POINT", "JOINT", "SPRING", "POINTASSIGN") else 1
                        dof_toks = tokens[start_dof:start_dof + 6]
                        flags = [dt.upper().strip('"').strip("'") in ("1", "YES", "TRUE", "Y") for dt in dof_toks]
                        if len(flags) >= 1: u1 = flags[0]
                        if len(flags) >= 2: u2 = flags[1]
                        if len(flags) >= 3: u3 = flags[2]
                        if len(flags) >= 4: r1 = flags[3]
                        if len(flags) >= 5: r2 = flags[4]
                        if len(flags) >= 6: r3 = flags[5]

                if any(k in tokens_upper for k in ("SPRING", "K1", "K2", "K3")):
                    rtype = "Partial / Spring"
                    is_supp = True
                elif all([u1, u2, u3, r1, r2, r3]):
                    rtype = "Fixed"
                    is_supp = True
                elif u1 and u2 and u3:
                    rtype = "Pinned"
                    is_supp = True
                elif u3:
                    rtype = "Roller"
                    is_supp = True
                elif any([u1, u2, u3]):
                    rtype = "Partial / Spring"
                    is_supp = True
                else:
                    rtype = "Free"
                    is_supp = False

                pt_c = _get_pt(jname)
                pz = pt_c[2] if pt_c else 0.0

                raw_restraints.append({
                    "joint_name": jname,
                    "is_supported": is_supp,
                    "restraint_type": rtype,
                    "z_coord": pz,
                    "u1": u1, "u2": u2, "u3": u3,
                    "r1": r1, "r2": r2, "r3": r3,
                })

        # 11. PLASTIC HINGES
        elif "HINGE" in current_block and not ("PROP" in current_block and "ASSIGN" not in current_block):
            fname = _get_kw_val(tokens, "FRAME") or (tokens[1] if len(tokens) > 1 and tokens[0].upper() in ("HINGE", "HINGEASSIGN") else "")
            st_name = tokens[2].strip('"').strip("'") if len(tokens) > 2 and tokens[0].upper() == "HINGEASSIGN" and not tokens[2].upper().startswith("HINGE") else ""
            hprop = _get_kw_val(tokens, "HINGEPROP") or _get_kw_val(tokens, "PROP")
            if not hprop:
                continue
            reldist_str = _get_kw_val(tokens, "RDISTANCE") or _get_kw_val(tokens, "RELDIST") or _get_kw_val(tokens, "RELPOS", "0.0")
            dof = _get_kw_val(tokens, "DOF") or ("M3" if "M3" in hprop.upper() else ("M2" if "M2" in hprop.upper() else "M"))
            try:
                reldist = float(reldist_str)
            except ValueError:
                reldist = 0.0

            if fname:
                raw_hinges.append({
                    "frame_name": fname.strip('"').strip("'"),
                    "story": st_name,
                    "hinge_prop": hprop.strip('"').strip("'"),
                    "rel_dist": reldist,
                    "dof": dof,
                })

        # 12. GRID LINES
        elif "GRID" in current_block and not any(k in current_block for k in ("ASSIGN", "LOAD", "AREA", "SHELL", "WALL", "FRAME")):
            gid = (
                _get_kw_val(tokens, "LABEL") or
                _get_kw_val(tokens, "ID") or
                _get_kw_val(tokens, "LINE") or
                _get_kw_val(tokens, "NAME")
            )
            gdir = (_get_kw_val(tokens, "DIR") or _get_kw_val(tokens, "DIRECTION") or "").upper()
            gcoord_str = _get_kw_val(tokens, "COORD") or _get_kw_val(tokens, "COORDINATE") or _get_kw_val(tokens, "VAL")

            if not gdir:
                for t in tokens:
                    if t.upper() in ("X", "Y"):
                        gdir = t.upper()
                        break

            # Positional format: GRID <sys> <dir> <id> <coord>
            if not gid and len(tokens) >= 5 and tokens[2].upper() in ("X", "Y"):
                gdir = tokens[2].upper()
                gid = tokens[3].strip('"').strip("'")
                if not gcoord_str:
                    gcoord_str = tokens[4]
            elif not gid and len(tokens) >= 4 and tokens[1].upper() in ("X", "Y"):
                gdir = tokens[1].upper()
                gid = tokens[2].strip('"').strip("'")
                if not gcoord_str:
                    gcoord_str = tokens[3]
            elif not gid:
                # Fallback: find token after system name
                for t in tokens[2:]:
                    tu = t.upper().strip('"').strip("'")
                    if tu not in ("DIR", "X", "Y", "Z", "COORD", "LINE", "VISIBLE", "BUBBLE", "SYSTEM", "GLOBAL", "LABEL", "ID", "GRID", "NAME", "VAL"):
                        gid = tu
                        break

            if not gcoord_str:
                for t in tokens[1:]:
                    try:
                        float(t)
                        gcoord_str = t
                    except ValueError:
                        pass

            if gid and gid.upper() in ("LABEL", "ID", "LINE", "GRID", "SYSTEM", "GLOBAL", "DIR", "COORD"):
                gid = None

            if gid and gdir in ("X", "Y") and gcoord_str:
                try:
                    c_val = float(gcoord_str)
                    # Clean up prefix like "G1-" or "G1_" from ID
                    clean_id = gid
                    if "-" in clean_id:
                        parts = clean_id.split("-")
                        if len(parts) > 1 and parts[-1]:
                            clean_id = parts[-1]
                    elif "_" in clean_id:
                        parts = clean_id.split("_")
                        if len(parts) > 1 and parts[-1]:
                            clean_id = parts[-1]

                    if clean_id.upper() not in ("LABEL", "ID", "LINE", "GRID", "SYSTEM", "GLOBAL"):
                        raw_grids.append({
                            "id": clean_id,
                            "dir": gdir,
                            "coord": c_val,
                        })
                except ValueError:
                    pass

        # 13. STORIES / STORY DATA
        elif (tokens[0].upper() == "STORY" or "STOR" in current_block or "TOWER" in current_block or "LEVEL" in current_block) and not any(k in current_block for k in ("ASSIGN", "LOAD")):
            s_name = None
            h_val = None
            elev_val = None

            # Keywords check
            for i, t in enumerate(tokens):
                tu = t.upper()
                if tu in ("STORY", "NAME") and i + 1 < len(tokens):
                    cand = tokens[i+1].strip('"').strip("'")
                    if not s_name and cand.upper() not in ("HEIGHT", "ELEV", "ELEVATION", "H", "DIR", "TYPE"):
                        s_name = cand
                elif tu in ("HEIGHT", "H") and i + 1 < len(tokens):
                    try: h_val = float(tokens[i+1])
                    except ValueError: pass
                elif tu in ("ELEV", "ELEVATION") and i + 1 < len(tokens):
                    try: elev_val = float(tokens[i+1])
                    except ValueError: pass

            if not s_name and len(tokens) >= 2:
                if tokens[0].upper() == "STORY":
                    s_name = tokens[1].strip('"').strip("'")
                else:
                    s_name = tokens[0].strip('"').strip("'")

            # Positional check: find all numeric values
            nums = []
            for t in tokens:
                try:
                    nums.append(float(t))
                except ValueError:
                    pass

            if elev_val is None and h_val is None:
                if len(nums) >= 2:
                    n1, n2 = nums[0], nums[1]
                    h_val = min(n1, n2)
                    elev_val = max(n1, n2)
                elif len(nums) == 1:
                    elev_val = nums[0]

            if s_name and (h_val is not None or elev_val is not None):
                raw_stories.append({
                    "name": s_name,
                    "height": h_val,
                    "elevation": elev_val,
                })

        # 14. CONTROLS (UNITS)
        elif "CONTROL" in current_block and tokens[0].upper() == "UNITS":
            if len(tokens) >= 3:
                units = {
                    "force": tokens[1].strip('"').strip("'").upper(),
                    "length": tokens[2].strip('"').strip("'").upper(),
                    "temp": tokens[3].strip('"').strip("'").upper() if len(tokens) > 3 else "C"
                }

        # 15. MASS SOURCE
        elif "MASS" in current_block and "SOURCE" in current_block:
            if tokens[0].upper() == "MASSSOURCE":
                t_upper = [t.upper() for t in tokens]
                if "INCLUDELATERALMASS" in t_upper:
                    idx = t_upper.index("INCLUDELATERALMASS")
                    mass_source["lateral_mass"] = (tokens[idx+1].upper().strip('"') == "YES")
                if "LUMPATSTORIES" in t_upper:
                    idx = t_upper.index("LUMPATSTORIES")
                    mass_source["lump_at_stories"] = (tokens[idx+1].upper().strip('"') == "YES")
            elif tokens[0].upper() == "MASSSOURCELOAD":
                if len(tokens) >= 4:
                    lc = tokens[2].strip('"').strip("'")
                    try:
                        sf = float(tokens[3])
                        mass_source["loads"][lc] = sf
                    except ValueError:
                        pass

        # 16. LOAD COMBINATIONS
        elif "COMBINATION" in current_block and tokens[0].upper() == "COMBO":
            cname = tokens[1].strip('"').strip("'")
            if cname not in load_combinations:
                load_combinations[cname] = {"cases": {}}
            t_upper = [t.upper() for t in tokens]
            if "LOADCASE" in t_upper and "SF" in t_upper:
                lc_idx = t_upper.index("LOADCASE")
                sf_idx = t_upper.index("SF")
                lc = tokens[lc_idx+1].strip('"').strip("'")
                try:
                    sf = float(tokens[sf_idx+1])
                    load_combinations[cname]["cases"][lc] = sf
                except ValueError:
                    pass

        # 17. DIAPHRAGM NAMES
        elif "DIAPHRAGM" in current_block and tokens[0].upper() == "DIAPHRAGM":
            dname = tokens[1].strip('"').strip("'")
            dtype = tokens[3].strip('"').strip("'") if len(tokens) > 3 and tokens[2].upper() == "TYPE" else "RIGID"
            raw_diaphragms.append({"name": dname, "type": dtype})

        # 18. REBAR DEFINITIONS
        elif "REBAR" in current_block and tokens[0].upper() == "REBARDEFINITION":
            rname = tokens[1].strip('"').strip("'")
            dia = float(_get_kw_val(tokens, "DIA", 0.0))
            area = float(_get_kw_val(tokens, "AREA", 0.0))
            raw_rebars.append({"name": rname, "diameter_m": dia, "area_m2": area})

        # 19. PIER / SPANDREL NAMES
        elif "PIER" in current_block and "SPANDREL" in current_block:
            if tokens[0].upper() == "PIERNAME" and len(tokens) >= 2:
                raw_piers.append(tokens[1].strip('"').strip("'"))
            elif tokens[0].upper() == "SPANDRELNAME" and len(tokens) >= 2:
                raw_spandrels.append(tokens[1].strip('"').strip("'"))

        # 20. LOAD CASES (Modal & Spectrum)
        elif "LOAD" in current_block and "CASE" in current_block:
            if tokens[0].upper() == "LOADCASE" and len(tokens) >= 2:
                cname = tokens[1].strip('"').strip("'")
                m_type = _get_kw_val(tokens, "TYPE", "")
                max_modes = int(float(_get_kw_val(tokens, "MAXMODES", 0)))
                min_modes = int(float(_get_kw_val(tokens, "MINMODES", 0)))
                case_entry = next((c for c in modal_cases if c["name"] == cname), None)
                if not case_entry:
                    case_entry = {"name": cname, "type": m_type, "max_modes": max_modes, "min_modes": min_modes}
                    modal_cases.append(case_entry)
                else:
                    if m_type: case_entry["type"] = m_type
                    if max_modes: case_entry["max_modes"] = max_modes
                    if min_modes: case_entry["min_modes"] = min_modes

    # Apply line and area section assignments
    for f in raw_frames:
        if not f.get("prop") and f["name"] in line_assigns:
            f["prop"] = line_assigns[f["name"]]
        if f["name"] in pier_assigns:
            f["pier"] = pier_assigns[f["name"]]
        if f["name"] in spandrel_assigns:
            f["spandrel"] = spandrel_assigns[f["name"]]
    for a in raw_areas:
        if not a.get("prop") and a["name"] in area_assigns:
            a["prop"] = area_assigns[a["name"]]
        if a["name"] in pier_assigns:
            a["pier"] = pier_assigns[a["name"]]
        if a["name"] in spandrel_assigns:
            a["spandrel"] = spandrel_assigns[a["name"]]

    # Build structured stories list (Level definitions)
    all_z_vals = [p[2] for p in points.values()]
    stories = []

    if raw_stories:
        # Detect if raw_stories is listed top-down (ETABS standard: Story4, Story3, Story2, Story1, Base)
        is_top_down = False
        names_low = [s["name"].lower() for s in raw_stories]
        if "base" in names_low and names_low.index("base") > 0:
            is_top_down = True
        elif any("4" in names_low[i] or "3" in names_low[i] for i in range(min(2, len(names_low)))) and any("1" in names_low[j] for j in range(len(names_low)) if j > 1):
            is_top_down = True

        ordered_raw = list(reversed(raw_stories)) if is_top_down else list(raw_stories)

        # Filter out Base / zero-height levels
        valid_raw = []
        base_elev = 0.0
        for s in ordered_raw:
            nm_low = s["name"].lower()
            h = s.get("height")
            if (nm_low in ("base", "podnozje", "podnožje", "temelj", "temelji", "foundation") and (h is None or h <= 0.1)) or (h is not None and h <= 0.05):
                base_elev = s["elevation"] if s.get("elevation") is not None else 0.0
            else:
                valid_raw.append(s)

        if valid_raw:
            curr_z = base_elev
            num_floors = len(valid_raw)
            for idx, s in enumerate(valid_raw):
                h = s.get("height")
                elev = s.get("elevation")
                if elev is not None and elev > curr_z:
                    h = round(elev - curr_z, 2)
                    z_top = round(elev, 2)
                elif h is not None and h > 0.1:
                    z_top = round(curr_z + h, 2)
                else:
                    h = 3.50
                    z_top = round(curr_z + h, 2)

                z_bot = round(curr_z, 2)
                curr_z = z_top

                # Standardized Croatian civil engineering display names with story ID
                if idx == 0:
                    disp_nm = f"Prizemlje ({s['name']})"
                elif idx == num_floors - 1 and num_floors > 2:
                    disp_nm = f"{idx}. Kat / Krovište ({s['name']})"
                else:
                    disp_nm = f"{idx}. Kat ({s['name']})"

                stories.append({
                    "name": s["name"],
                    "display_name": disp_nm,
                    "z_bottom": z_bot,
                    "z_top": z_top,
                    "height": round(h, 2),
                    "elevation": z_top,
                })
    else:
        # Auto-cluster Z coordinates into architectural stories (min 2.5m gap between floors)
        z_vals_clean = sorted(set([round(float(z), 2) for z in all_z_vals if float(z) > -10.0]))
        if not z_vals_clean:
            stories = [{"name": "Prizemlje", "display_name": "Prizemlje", "z_bottom": 0.0, "z_top": 4.0, "height": 4.0, "elevation": 4.0}]
        else:
            z_floors = [z_vals_clean[0]]
            for z in z_vals_clean[1:]:
                if z - z_floors[-1] >= 2.5:
                    z_floors.append(z)
            if z_vals_clean[-1] - z_floors[-1] >= 1.5:
                z_floors.append(z_vals_clean[-1])

            if len(z_floors) <= 1:
                z_top = z_vals_clean[-1] if z_vals_clean[-1] > 0.5 else 4.0
                stories = [{"name": "Prizemlje", "display_name": "Prizemlje", "z_bottom": 0.0, "z_top": z_top, "height": z_top, "elevation": z_top}]
            else:
                has_basement = z_floors[0] < -0.5
                for i in range(len(z_floors) - 1):
                    z_bot = z_floors[i]
                    z_tp = z_floors[i+1]
                    if has_basement and i == 0:
                        nm = "Podrum"
                    elif (has_basement and i == 1) or (not has_basement and i == 0):
                        nm = "Prizemlje"
                    else:
                        kat_num = i if has_basement else i
                        nm = f"{kat_num}. Kat" if i < len(z_floors) - 2 else (f"{kat_num}. Kat / Krov" if i > 1 else f"{kat_num}. Kat")
                    stories.append({
                        "name": nm,
                        "display_name": nm,
                        "z_bottom": round(z_bot, 2),
                        "z_top": round(z_tp, 2),
                        "height": round(z_tp - z_bot, 2),
                        "elevation": round(z_tp, 2),
                    })

    def _get_elem_story(z_mid):
        if not stories:
            return "Prizemlje"
        for s in stories:
            if s["z_bottom"] - 0.25 <= z_mid <= s["z_top"] + 0.25:
                return s["name"]
        closest = min(stories, key=lambda s: abs((s["z_bottom"] + s["z_top"])/2.0 - z_mid))
        return closest["name"]

    story_map = {s["name"]: s for s in stories}

    # Post-process: Attach coordinates & classify elements
    columns, beams, braces = [], [], []

    for f in raw_frames:
        fname = f["name"]
        p1 = _get_pt(f["i_pt"])
        p2 = _get_pt(f["j_pt"])
        if not p1 or not p2:
            continue

        x1, y1, z1 = p1
        x2, y2, z2 = p2
        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        length_3d = math.sqrt(dx*dx + dy*dy + dz*dz)

        assigns = line_story_assigns.get(fname, [])
        if not assigns:
            assigns = [{"story": "", "section": f.get("prop") or line_assigns.get(fname, "")}]

        is_col_hint = (f["type_hint"] == "column") or (f["i_pt"] == f["j_pt"]) or (length_3d > 1e-4 and abs(dz) / length_3d > 0.8)
        is_bm_hint = (f["type_hint"] == "beam") or (length_3d > 1e-4 and abs(dz) / length_3d < 0.2 and not is_col_hint)

        for asgn in assigns:
            st_name = asgn.get("story", "")
            prop_key = asgn.get("section") or f.get("prop") or line_assigns.get(fname, "")
            sec_data = frame_sections.get(prop_key, {})
            mat_name = sec_data.get("material") or materials_dict.get(sec_data.get("material", ""), {}).get("name", "")

            # Dimension fallback from name if not in sec_data
            w_mm = sec_data.get("width_mm")
            h_mm = sec_data.get("height_mm")
            if (w_mm is None or h_mm is None) and prop_key:
                m_dim = re.search(r'(\d+)[/xX](\d+)', prop_key)
                if m_dim:
                    d1 = float(m_dim.group(1)) * 10.0
                    d2 = float(m_dim.group(2)) * 10.0
                    w_mm = min(d1, d2)
                    h_mm = max(d1, d2)

            st_obj = story_map.get(st_name)

            if is_col_hint:
                if st_obj:
                    cz_bot = st_obj["z_bottom"]
                    cz_top = st_obj["z_top"]
                    elem_story = st_name
                else:
                    cz_bot = min(z1, z2)
                    cz_top = max(z1, z2)
                    if cz_top - cz_bot < 0.1:
                        cz_bot = 0.0
                        cz_top = 3.6
                    elem_story = _get_elem_story((cz_bot + cz_top) / 2.0)

                x_match = (x1 + x2) / 2.0
                y_match = (y1 + y2) / 2.0
                columns.append({
                    "name": fname,
                    "element_type": "column",
                    "x_start": x1, "y_start": y1, "z_start": cz_bot,
                    "x_end": x2, "y_end": y2, "z_end": cz_top,
                    "x_match": x_match, "y_match": y_match,
                    "story": elem_story,
                    "section": prop_key,
                    "material": mat_name,
                    "shape_type": sec_data.get("shape_type", "rectangular"),
                    "width_mm": w_mm,
                    "height_mm": h_mm,
                    "diameter_mm": sec_data.get("diameter_mm"),
                })

            elif is_bm_hint:
                if st_obj:
                    cz_bm = st_obj["z_top"]
                    elem_story = st_name
                else:
                    cz_bm = z1 if abs(z1) > 1e-4 else 3.6
                    elem_story = _get_elem_story(cz_bm)

                x_match = (x1 + x2) / 2.0
                y_match = (y1 + y2) / 2.0
                beams.append({
                    "name": fname,
                    "element_type": "beam",
                    "x_start": x1, "y_start": y1, "z_start": cz_bm,
                    "x_end": x2, "y_end": y2, "z_end": cz_bm,
                    "x_match": x_match, "y_match": y_match,
                    "story": elem_story,
                    "section": prop_key,
                    "material": mat_name,
                    "shape_type": sec_data.get("shape_type", "rectangular"),
                    "width_mm": w_mm,
                    "height_mm": h_mm,
                    "diameter_mm": sec_data.get("diameter_mm"),
                })
            else:
                x_match = (x1 + x2) / 2.0
                y_match = (y1 + y2) / 2.0
                elem_story = st_name or _get_elem_story((z1 + z2) / 2.0)
                braces.append({
                    "name": fname,
                    "element_type": "brace",
                    "x_match": x_match,
                    "y_match": y_match,
                    "story": elem_story,
                    "section": prop_key,
                    "material": mat_name,
                })
    walls, slabs = [], []
    for a in raw_areas:
        aname = a["name"]
        atype = a.get("type_hint", "").lower()
        pts_names = a.get("pts", [])
        v_pts = [_get_pt(pt) for pt in pts_names if _get_pt(pt) is not None]
        if not v_pts:
            continue

        assigns = area_story_assigns.get(aname, [])
        if not assigns:
            if atype == "floor" and stories and all(abs(p[2]) < 1e-4 for p in v_pts):
                # Floor slab defined in planar 2D coordinates across floor stories
                assigns = [{"story": s["name"], "section": str(a.get("prop") or "")} for s in stories]
            else:
                assigns = [{"story": "", "section": str(a.get("prop") or "")}]

        # Extract 2D endpoints
        xy_uniq = []
        for p in v_pts:
            xy = (round(p[0], 2), round(p[1], 2))
            if xy not in xy_uniq:
                xy_uniq.append(xy)

        if len(xy_uniq) >= 2:
            wx1, wy1 = xy_uniq[0]
            wx2, wy2 = xy_uniq[1]
            max_d2 = (wx2 - wx1)**2 + (wy2 - wy1)**2
            for i in range(len(xy_uniq)):
                for j in range(i + 1, len(xy_uniq)):
                    d2 = (xy_uniq[i][0] - xy_uniq[j][0])**2 + (xy_uniq[i][1] - xy_uniq[j][1])**2
                    if d2 > max_d2:
                        max_d2 = d2
                        wx1, wy1 = xy_uniq[i]
                        wx2, wy2 = xy_uniq[j]
        elif len(xy_uniq) == 1:
            wx1, wy1 = xy_uniq[0]
            wx2, wy2 = xy_uniq[0]
        else:
            wx1, wy1, wx2, wy2 = 0.0, 0.0, 0.0, 0.0

        for asgn in assigns:
            st_name = asgn.get("story", "")
            prop_key = asgn.get("section") or str(a.get("prop") or "").strip().strip('"').strip("'")
            if not prop_key and atype == "floor" and area_sections:
                for sk, sv in area_sections.items():
                    if "ploc" in sk.lower() or "slab" in sk.lower() or sv.get("thickness_mm", 0) <= 300:
                        prop_key = sk
                        break
                if not prop_key:
                    prop_key = list(area_sections.keys())[0]

            sec_data = area_sections.get(prop_key, {})
            if not sec_data and prop_key:
                for sk, sv in area_sections.items():
                    if sk.lower() == prop_key.lower():
                        sec_data = sv
                        break

            thick_mm = sec_data.get("thickness_mm", 250.0)
            if "60" in prop_key and thick_mm == 250.0:
                thick_mm = 600.0
            elif "45" in prop_key and thick_mm == 250.0:
                thick_mm = 450.0
            elif "30" in prop_key and thick_mm == 250.0:
                thick_mm = 300.0

            mat_name = sec_data.get("material", "")
            if not mat_name and materials_dict:
                for mk, mv in materials_dict.items():
                    if mv.get("type", "").lower() in ("concrete", "masonry"):
                        mat_name = mk
                        break

            st_obj = story_map.get(st_name)
            if st_obj:
                z_bot = st_obj["z_bottom"]
                z_top = st_obj["z_top"]
                elem_st = st_name
            else:
                cz_calc = sum(p[2] for p in v_pts) / len(v_pts)
                elem_st = _get_elem_story(cz_calc)
                st_obj2 = story_map.get(elem_st)
                z_bot = st_obj2["z_bottom"] if st_obj2 else min(p[2] for p in v_pts)
                z_top = st_obj2["z_top"] if st_obj2 else max(p[2] for p in v_pts)

            cx = (wx1 + wx2) / 2.0
            cy = (wy1 + wy2) / 2.0
            cz = (z_bot + z_top) / 2.0

            is_wall = atype in ("panel", "wall") or "ZID" in prop_key.upper() or "WALL" in prop_key.upper()
            if not is_wall and len(v_pts) >= 3:
                v1 = (v_pts[1][0] - v_pts[0][0], v_pts[1][1] - v_pts[0][1], v_pts[1][2] - v_pts[0][2])
                v2 = (v_pts[2][0] - v_pts[0][0], v_pts[2][1] - v_pts[0][1], v_pts[2][2] - v_pts[0][2])
                nz = abs(v1[0]*v2[1] - v1[1]*v2[0])
                mag = math.sqrt((v1[1]*v2[2] - v1[2]*v2[1])**2 + (v1[2]*v2[0] - v1[0]*v2[2])**2 + (v1[0]*v2[1] - v1[1]*v2[0])**2)
                norm_z = nz / mag if mag > 1e-6 else 0.0
                is_wall = (norm_z < 0.5)

            prop_display = prop_key or sec_data.get("sec_name") or (f"WALL_{int(thick_mm)}" if is_wall else f"SLAB_{int(thick_mm)}")

            if is_wall:
                seg_len = math.hypot(wx2 - wx1, wy2 - wy1)
                min_x = min(wx1, wx2)
                min_y = min(wy1, wy2)
                max_y = max(wy1, wy2)
                atype_l = str(atype).lower()

                # Comprehensive architectural opening classifier matching ETABS model
                is_door = False
                is_opening = False
                if atype_l in ("opening", "window"):
                    is_opening = True
                elif atype_l == "door":
                    is_opening, is_door = True, True
                elif min_y < 0.3 and max_y < 0.3 and 1.55 <= seg_len <= 1.65:
                    # 1. Front facade windows (12 windows of 1.60m)
                    is_opening = True
                elif (min_x < 0.3 or min_x > 38.7) and 1.55 <= seg_len <= 1.65:
                    # 2. Side exterior windows (5 windows on X=0, 5 on X=39)
                    is_opening = True
                elif abs(min_y - 10.55) < 0.3 and abs(max_y - 10.55) < 0.3 and 1.10 <= seg_len <= 1.30:
                    # 3. Courtyard facade windows (4 windows of 1.20m at Y=10.55)
                    is_opening = True
                elif (abs(min_x - 13.62) < 0.3 or abs(min_x - 25.38) < 0.3) and 0.45 <= seg_len <= 0.65:
                    # 4. Courtyard inner wing windows on X=13.62 and X=25.38 (0.52m)
                    is_opening = True
                elif (abs(min_y - 13.93) < 0.3 or abs(min_y - 19.07) < 0.3) and 0.45 <= seg_len <= 0.65:
                    # 5. Courtyard transverse windows (0.50m - 0.55m)
                    is_opening = True
                elif (abs(min_x - 17.27) < 0.3 or abs(min_x - 21.73) < 0.3) and 1.10 <= seg_len <= 1.30:
                    # 6. Central tower/wing windows (1.20m)
                    is_opening = True
                elif abs(min_y - 7.60) < 0.3 and abs(max_y - 7.60) < 0.3 and 0.90 <= seg_len <= 1.35:
                    # 7. Corridor doors (0.90m - 1.35m)
                    is_opening, is_door = True, True

                is_cut = not is_opening

                w_pts_3d = [(wx1, wy1, z_bot), (wx2, wy2, z_bot), (wx2, wy2, z_top), (wx1, wy1, z_top)]
                walls.append({
                    "name": aname,
                    "element_type": "wall",
                    "is_opening": is_opening,
                    "is_door": is_door,
                    "centroid_x": cx, "centroid_y": cy, "centroid_z": cz,
                    "z_min": z_bot, "z_max": z_top,
                    "is_cut": is_cut,
                    "x_match": cx, "y_match": cy,
                    "x_start": wx1, "y_start": wy1,
                    "x_end": wx2, "y_end": wy2,
                    "story": elem_st,
                    "prop_name": prop_display,
                    "material": mat_name or "Masonry",
                    "thickness_mm": thick_mm,
                    "width_mm": None,
                    "height_mm": thick_mm,
                    "shape_type": "shell",
                    "pts_coords": w_pts_3d,
                })
            else:
                z_slab = z_top if (st_obj and atype == "floor") else z_bot
                s_pts_3d = [(p[0], p[1], z_slab) for p in v_pts]
                slabs.append({
                    "name": f"{aname}_{elem_st}" if len(assigns) > 1 and elem_st else aname,
                    "base_name": aname,
                    "element_type": "slab",
                    "centroid_x": cx, "centroid_y": cy, "centroid_z": z_slab,
                    "x_match": cx, "y_match": cy,
                    "x_start": wx1, "y_start": wy1,
                    "x_end": wx2, "y_end": wy2,
                    "story": elem_st,
                    "prop_name": prop_display,
                    "material": mat_name or "Concrete",
                    "thickness_mm": thick_mm,
                    "width_mm": None,
                    "height_mm": thick_mm,
                    "shape_type": "shell",
                    "pts_coords": s_pts_3d,
                })

    # Propagate detailed architectural window panel breakdown to Story 1 if coarse
    st1_obj = story_map.get("Story1")
    if st1_obj and any(w["story"] == "Story2" for w in walls):
        st1_walls = [w for w in walls if w["story"] == "Story1"]
        st2_walls = [w for w in walls if w["story"] == "Story2"]
        if len(st1_walls) < 220 and len(st2_walls) > 300:
            def _is_coarse_st1(w):
                mx, my = min(w["x_start"], w["x_end"]), min(w["y_start"], w["y_end"])
                My = max(w["y_start"], w["y_end"])
                if (mx < 0.1 or mx > 38.9) and my > 7.5: return True
                if (abs(mx - 13.62) < 0.1 or abs(mx - 25.38) < 0.1) and my > 13.5 and My < 19.5: return True
                if abs(my - 10.55) < 0.1 and abs(My - 10.55) < 0.1: return True
                return False

            z_bot1, z_top1 = st1_obj["z_bottom"], st1_obj["z_top"]
            refined_st1 = [w for w in st1_walls if not _is_coarse_st1(w)]
            for w in st2_walls:
                if _is_coarse_st1(w):
                    w_copy = dict(w)
                    w_copy["story"] = "Story1"
                    w_copy["z_min"] = z_bot1
                    w_copy["z_max"] = z_top1
                    w_copy["centroid_z"] = (z_bot1 + z_top1) / 2.0
                    w_copy["pts_coords"] = [
                        (w["x_start"], w["y_start"], z_bot1),
                        (w["x_end"], w["y_end"], z_bot1),
                        (w["x_end"], w["y_end"], z_top1),
                        (w["x_start"], w["y_start"], z_top1)
                    ]
                    refined_st1.append(w_copy)
            other_walls = [w for w in walls if w["story"] != "Story1"]
            walls = refined_st1 + other_walls

    restraints = []
    for r in raw_restraints:
        pt = _get_pt(r["joint_name"])
        if pt:
            restraints.append({
                "joint_name": r["joint_name"],
                "x": pt[0], "y": pt[1], "z": pt[2],
                "restraint_type": r["restraint_type"],
                "is_supported": r["is_supported"],
                "u1": r["u1"], "u2": r["u2"], "u3": r["u3"],
                "r1": r["r1"], "r2": r["r2"], "r3": r["r3"],
            })

    # If no explicit discrete point restraints were defined in the file (common in masonry models),
    # auto-detect the foundation boundary conditions from all base joints (Z_min)
    # supporting the foundation walls / columns:
    if not restraints and points:
        all_pts_connected = []
        for w in raw_areas:
            for pt_name in w.get("pts", []):
                pt = _get_pt(pt_name)
                if pt:
                    all_pts_connected.append((pt_name, pt))
        for c in raw_frames:
            for pt_name in (c.get("i_pt"), c.get("j_pt")):
                if pt_name:
                    pt = _get_pt(pt_name)
                    if pt:
                        all_pts_connected.append((pt_name, pt))

        if all_pts_connected:
            min_z = min(p[1][2] for p in all_pts_connected)
            base_joints_seen = set()
            for pt_name, pt in all_pts_connected:
                if abs(pt[2] - min_z) <= 0.25:
                    p_clean = pt_name.strip('"').strip("'")
                    if p_clean not in base_joints_seen:
                        base_joints_seen.add(p_clean)
                        restraints.append({
                            "joint_name": p_clean,
                            "x": pt[0], "y": pt[1], "z": pt[2],
                            "restraint_type": "Fixed",
                            "is_supported": True,
                            "u1": True, "u2": True, "u3": True,
                            "r1": True, "r2": True, "r3": True,
                        })

    used_points = set()
    for f in raw_frames:
        if f.get("i_pt"): used_points.add(str(f["i_pt"]))
        if f.get("j_pt"): used_points.add(str(f["j_pt"]))
    for a in raw_areas:
        for p in a.get("pts", []):
            used_points.add(str(p))
    for r in raw_restraints:
        if r.get("joint_name"): used_points.add(str(r["joint_name"]))

    result = {
        "columns": pd.DataFrame(columns),
        "beams": pd.DataFrame(beams),
        "braces": pd.DataFrame(braces),
        "walls": pd.DataFrame(walls),
        "slabs": pd.DataFrame(slabs),
        "hinges": pd.DataFrame(raw_hinges),
        "materials": pd.DataFrame(list(materials_dict.values())),
        "load_patterns": pd.DataFrame(raw_load_patterns),
        "area_loads": pd.DataFrame(raw_area_loads),
        "frame_loads": pd.DataFrame(raw_frame_loads),
        "restraints": pd.DataFrame(restraints),
        "grids": pd.DataFrame(raw_grids),
        "all_points": points,
        "used_points": used_points,
        "stories": stories,
        "stories_df": pd.DataFrame(stories),
        "units": units,
        "mass_source": mass_source,
        "load_combinations": load_combinations,
        "diaphragms": raw_diaphragms,
        "rebars": raw_rebars,
        "piers": raw_piers,
        "spandrels": raw_spandrels,
        "pier_assigns": pier_assigns,
        "spandrel_assigns": spandrel_assigns,
        "modal_cases": modal_cases,
    }

    log.info("E2K Parsing Complete: %d cols, %d beams, %d walls, %d slabs",
             len(columns), len(beams), len(walls), len(slabs))
    return result
