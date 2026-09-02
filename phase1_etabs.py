"""
phase1_etabs.py  —  v2 (corrected API signatures + AreaObj.GetDesignOrientation)
---------------
Extract ALL structural elements from a running ETABS v23 instance via OAPI.

Extracts:
  - Frame objects: columns, beams, braces
  - Section dimensions: from PROPERTY DEFINITIONS (eFramePropType-dispatched)
  - Area objects: walls / slabs (using GetDesignOrientation, geometry fallback)
  - Plastic hinges: per frame object

Bug fixes vs v1:
  ✓ eFramePropType enum constants corrected (official CSI values)
  ✓ GetRectangle/GetCircle/GetISection etc. include FileName+MatProp before dims
  ✓ GetHingeAssigns: defensive tuple unpacking
  ✓ GetShell_1: single call for both material and thickness
  ✓ Area classification: GetDesignOrientation primary, geometry fallback
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd

from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _connect(cfg: Config):
    try:
        import comtypes.client  # type: ignore
    except ImportError:
        raise ImportError("comtypes is not installed. Run: pip install comtypes (Windows only).")

    PROG_ID = "CSI.ETABS.API.ETABSObject"
    log.info("Attaching to running ETABS instance …")
    obj = None

    # Method 1 (CSI Official Recommended for v18+): Use ETABSv1.Helper
    try:
        helper = comtypes.client.CreateObject("ETABSv1.Helper")
        # Query interface if type library is generated
        try:
            import comtypes.gen.ETABSv1 as ETABSv1  # type: ignore
            helper = helper.QueryInterface(ETABSv1.cHelper)
        except Exception:
            pass
        obj = helper.GetObject(PROG_ID)
        log.debug("Connected via ETABSv1.Helper.GetObject.")
    except Exception as e1:
        log.debug("ETABSv1.Helper connection attempt: %s", e1)

    # Method 2 (Fallback): Direct Windows Running Object Table lookup
    if obj is None:
        try:
            obj = comtypes.client.GetActiveObject(PROG_ID)
            log.debug("Connected via comtypes.client.GetActiveObject.")
        except Exception as e2:
            raise RuntimeError(
                f"Could not attach to running ETABS instance.\n"
                f"Details: {e2}\n\n"
                f"Troubleshooting Checklist:\n"
                f"  1. Is ETABS v23 currently running with a model opened?\n"
                f"  2. If ETABS was launched 'As Administrator', you must also run this script as Administrator.\n"
                f"  3. Make sure only one ETABS model window is open.\n"
                f"  4. Verify comtypes is installed: pip install comtypes"
            ) from e2

    sap = obj.SapModel
    ret = sap.SetPresentUnits(cfg.etabs_units)
    if ret != 0:
        log.warning("SetPresentUnits(%d) returned %d.", cfg.etabs_units, ret)
    log.info("Connected to ETABS. Units → eUnits=%d (kN-m-C).", cfg.etabs_units)
    return sap


# ---------------------------------------------------------------------------
# Bulk point lookup
# ---------------------------------------------------------------------------

def _bulk_points(sap) -> dict[str, tuple[float, float, float]]:
    """Fetch all joint coordinates in a single API call."""
    ret, n, names, xs, ys, zs, _ = sap.PointObj.GetAllPoints()
    if ret != 0:
        raise RuntimeError(f"GetAllPoints() failed ({ret}).")
    return {names[i]: (xs[i], ys[i], zs[i]) for i in range(n)}


# ---------------------------------------------------------------------------
# eFramePropType enum  —  OFFICIAL CSI ETABS v23 values
# Source: csiamerica.com OAPI documentation (confirmed by research)
# ---------------------------------------------------------------------------

_SHAPE_I        = 1   # I-Section / Wide Flange  → GetISection()
_SHAPE_CHANNEL  = 2   # Channel                  → GetChannel()
_SHAPE_T        = 3   # T-Section                → GetTSection()
_SHAPE_ANGLE    = 4   # Angle
_SHAPE_DANGLE   = 5   # Double Angle
_SHAPE_BOX      = 6   # Box / Tube               → GetTube()
_SHAPE_PIPE     = 7   # Pipe / CHS               → GetPipe()
_SHAPE_RECT     = 8   # Rectangular              → GetRectangle()
_SHAPE_CIRCLE   = 9   # Circular                 → GetCircle()
_SHAPE_GENERAL  = 10  # General                  → GetGeneral()
_SHAPE_SD       = 13  # Section Designer
_SHAPE_PRECAST  = 24  # Precast I-Girder


# ---------------------------------------------------------------------------
# Section property dimension extraction
# ---------------------------------------------------------------------------

def _section_dims_from_definition(sap, prop_name: str) -> dict:
    """
    Read actual cross-section dimensions directly from the ETABS property definition.
    Returns: {shape_type, width_mm, height_mm, diameter_mm}
    All API calls use the correct OAPI signature:
      GetRectangle(Name) → (ret, FileName, MatProp, t3, t2, ...)
      GetCircle(Name)    → (ret, FileName, MatProp, t3, ...)
      etc.
    """
    result = {"shape_type": "unknown", "width_mm": None, "height_mm": None, "diameter_mm": None}
    if not prop_name:
        return result

    try:
        ret, prop_type = sap.PropFrame.GetSectionType(prop_name)
    except Exception:
        ret, prop_type = -1, -1
    if ret != 0:
        log.debug("GetSectionType failed for '%s'.", prop_name)
        return result

    # Each getter returns: (ret, FileName, MatProp, dim1, dim2, ...)
    # We always skip FileName (_fn) and MatProp (_mat) before the dimension values.

    if prop_type == _SHAPE_RECT:
        result["shape_type"] = "rectangular"
        try:
            ret2, _fn, _mat, t3, t2, *_ = sap.PropFrame.GetRectangle(prop_name)
            if ret2 == 0:
                result["height_mm"] = round(t3 * 1000)
                result["width_mm"]  = round(t2 * 1000)
        except Exception as e:
            log.debug("GetRectangle('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_CIRCLE:
        result["shape_type"] = "circular"
        try:
            ret2, _fn, _mat, t3, *_ = sap.PropFrame.GetCircle(prop_name)
            if ret2 == 0:
                d = round(t3 * 1000)
                result["diameter_mm"] = d
                result["width_mm"]  = d
                result["height_mm"] = d
        except Exception as e:
            log.debug("GetCircle('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_BOX:
        result["shape_type"] = "box"
        try:
            ret2, _fn, _mat, t3, t2, *_ = sap.PropFrame.GetTube(prop_name)
            if ret2 == 0:
                result["height_mm"] = round(t3 * 1000)
                result["width_mm"]  = round(t2 * 1000)
        except Exception as e:
            log.debug("GetTube('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_PIPE:
        result["shape_type"] = "pipe"
        try:
            ret2, _fn, _mat, t3, _tw, *_ = sap.PropFrame.GetPipe(prop_name)
            if ret2 == 0:
                d = round(t3 * 1000)
                result["diameter_mm"] = d
                result["width_mm"]  = d
                result["height_mm"] = d
        except Exception as e:
            log.debug("GetPipe('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_I:
        result["shape_type"] = "I-section"
        try:
            ret2, _fn, _mat, t3, t2, *_ = sap.PropFrame.GetISection(prop_name)
            if ret2 == 0:
                result["height_mm"] = round(t3 * 1000)
                result["width_mm"]  = round(t2 * 1000)
        except Exception as e:
            log.debug("GetISection('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_CHANNEL:
        result["shape_type"] = "channel"
        try:
            ret2, _fn, _mat, t3, t2, *_ = sap.PropFrame.GetChannel(prop_name)
            if ret2 == 0:
                result["height_mm"] = round(t3 * 1000)
                result["width_mm"]  = round(t2 * 1000)
        except Exception as e:
            log.debug("GetChannel('%s'): %s", prop_name, e)

    elif prop_type == _SHAPE_T:
        result["shape_type"] = "T-section"
        try:
            ret2, _fn, _mat, t3, t2, *_ = sap.PropFrame.GetTSection(prop_name)
            if ret2 == 0:
                result["height_mm"] = round(t3 * 1000)
                result["width_mm"]  = round(t2 * 1000)
        except Exception as e:
            log.debug("GetTSection('%s'): %s", prop_name, e)

    else:
        result["shape_type"] = "general"
        # No dimensional b/h from general properties — comparison skipped

    log.debug("  Section '%s': %s  W=%s H=%s D=%s mm",
              prop_name, result["shape_type"],
              result["width_mm"], result["height_mm"], result["diameter_mm"])
    return result


# ---------------------------------------------------------------------------
# Shell / area property thickness
# ---------------------------------------------------------------------------

def _shell_thickness_and_material(sap, prop_name: str) -> tuple[Optional[float], str]:
    """
    Single GetShell_1 call → (thickness_mm, material_name).
    Signature: GetShell_1(Name) → (ret, ShellType, bIncludeDrillingDOF,
                                    MatPropName, MatAngle, Thickness, Bending12f,
                                    Color, Notes, GUID)
    """
    if not prop_name:
        return None, ""
    try:
        ret, _shell_type, _drill, mat, _mat_ang, thickness, *_ = \
            sap.PropArea.GetShell_1(prop_name)
        if ret == 0:
            t_mm = round(thickness * 1000) if thickness else None
            return t_mm, str(mat or "")
    except Exception as e:
        log.debug("GetShell_1('%s'): %s", prop_name, e)
    return None, ""


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _normal_vector(pts: list) -> tuple[float, float, float]:
    if len(pts) < 3:
        return (0.0, 0.0, 1.0)
    ax, ay, az = pts[1][0]-pts[0][0], pts[1][1]-pts[0][1], pts[1][2]-pts[0][2]
    bx, by, bz = pts[2][0]-pts[0][0], pts[2][1]-pts[0][1], pts[2][2]-pts[0][2]
    nx = ay*bz - az*by; ny = az*bx - ax*bz; nz = ax*by - ay*bx
    mag = math.sqrt(nx*nx + ny*ny + nz*nz)
    return (nx/mag, ny/mag, nz/mag) if mag > 1e-9 else (0.0, 0.0, 1.0)


def _centroid_xyz(pts: list) -> tuple[float, float, float]:
    n = len(pts)
    return (sum(p[0] for p in pts)/n, sum(p[1] for p in pts)/n, sum(p[2] for p in pts)/n)


def _is_vertical_by_geometry(x1, y1, z1, x2, y2, z2, thresh: float) -> bool:
    dz = abs(z2 - z1)
    L  = math.sqrt((x2-x1)**2 + (y2-y1)**2 + dz**2)
    return L > 1e-9 and (dz / L) >= thresh


# ---------------------------------------------------------------------------
# Section property cache
# ---------------------------------------------------------------------------

class _SectionCache:
    def __init__(self, sap, cfg: Config):
        self._sap = sap; self._cfg = cfg
        self._frame: dict[str, dict] = {}
        self._area:  dict[str, tuple[Optional[float], str]] = {}

    def frame(self, name: str) -> dict:
        if name not in self._frame:
            self._frame[name] = _section_dims_from_definition(self._sap, name)
        return self._frame[name]

    def area(self, name: str) -> tuple[Optional[float], str]:
        if name not in self._area:
            self._area[name] = _shell_thickness_and_material(self._sap, name)
        return self._area[name]


# ---------------------------------------------------------------------------
# 1a — Frame extraction (columns / beams / braces)
# ---------------------------------------------------------------------------

def _extract_frames(sap, pt_coords: dict, cache: _SectionCache, cfg: Config) -> dict:
    ret, n, names = sap.FrameObj.GetNameList()
    if ret != 0:
        raise RuntimeError(f"FrameObj.GetNameList() failed ({ret}).")
    log.info("Frame objects total: %d", n)

    buckets: dict[str, list] = {"columns": [], "beams": [], "braces": []}

    for name in names:
        ret_o, orient = sap.FrameObj.GetDesignOrientation(name)
        label = {
            cfg.ORIENT_COLUMN: "columns",
            cfg.ORIENT_BEAM:   "beams",
            cfg.ORIENT_BRACE:  "braces",
        }.get(orient if ret_o == 0 else -1, None)

        ret_p, pt1, pt2 = sap.FrameObj.GetPoints(name)
        if ret_p != 0 or pt1 not in pt_coords or pt2 not in pt_coords:
            continue
        x1, y1, z1 = pt_coords[pt1]
        x2, y2, z2 = pt_coords[pt2]

        # Program Determined (orient == 0) — geometry fallback
        if label is None:
            if orient == 0:
                label = ("columns"
                         if _is_vertical_by_geometry(x1, y1, z1, x2, y2, z2,
                                                     cfg.column_verticality_threshold)
                         else "beams")
            else:
                continue

        if label not in cfg.extract_elements and label.rstrip("s") not in cfg.extract_elements:
            continue

        # Columns: ensure bottom (lower Z) is start
        if label == "columns" and z1 > z2:
            x1, y1, z1, x2, y2, z2 = x2, y2, z2, x1, y1, z1

        x_mid = (x1 + x2) / 2
        y_mid = (y1 + y2) / 2

        ret_s, section, *_ = sap.FrameObj.GetSection(name)
        section = section if ret_s == 0 else ""

        material = ""
        if section:
            try:
                ret_m, material = sap.PropFrame.GetMaterial(section)
                material = material if ret_m == 0 else ""
            except Exception:
                pass

        dims = cache.frame(section) if section else {}

        buckets[label].append({
            "name":         name,
            "element_type": label.rstrip("s"),
            "x_start":      x1,   "y_start": y1,   "z_start": z1,
            "x_end":        x2,   "y_end":   y2,   "z_end":   z2,
            "x_match":      x1 if label == "columns" else x_mid,
            "y_match":      y1 if label == "columns" else y_mid,
            "section":      section,
            "material":     material,
            "shape_type":   dims.get("shape_type", ""),
            "width_mm":     dims.get("width_mm"),
            "height_mm":    dims.get("height_mm"),
            "diameter_mm":  dims.get("diameter_mm"),
        })

    for k, v in buckets.items():
        log.info("  %-10s %d", k, len(v))
    return buckets


# ---------------------------------------------------------------------------
# 1b — Plastic hinge extraction
# ---------------------------------------------------------------------------

def _extract_hinges(sap, cfg: Config) -> list[dict]:
    if not cfg.report_hinges:
        return []

    ret, n, names = sap.FrameObj.GetNameList()
    if ret != 0:
        return []

    hinges = []
    HINGE_DOF = {1:"M3", 2:"M2", 3:"P", 4:"V2", 5:"V3", 6:"T"}

    for name in names:
        try:
            # Defensive unpacking — some ETABS versions return 5, some 6 items after ret+n
            result   = sap.FrameObj.GetHingeAssigns(name)
            ret_h    = result[0]
            n_h      = result[1]
            if ret_h != 0 or n_h == 0:
                continue
            h_props  = result[2] if len(result) > 2 else []
            rel_dists= result[3] if len(result) > 3 else []
            my_types = result[4] if len(result) > 4 else []
            ids      = result[5] if len(result) > 5 else []

            for i in range(n_h):
                hinges.append({
                    "frame_name":  name,
                    "hinge_prop":  h_props[i] if i < len(h_props) else "",
                    "rel_dist":    rel_dists[i] if i < len(rel_dists) else None,
                    "dof":         HINGE_DOF.get(my_types[i], str(my_types[i]))
                                   if i < len(my_types) else "",
                    "hinge_id":    ids[i] if i < len(ids) else None,
                })
        except Exception as e:
            log.debug("GetHingeAssigns('%s') skipped: %s", name, e)

    log.info("Plastic hinges: %d (on %d unique frames)",
             len(hinges), len({h["frame_name"] for h in hinges}))
    return hinges


# ---------------------------------------------------------------------------
# 1c/d — Area object extraction (walls + slabs)
# ---------------------------------------------------------------------------

def _extract_areas(sap, pt_coords: dict, cache: _SectionCache, cfg: Config) -> dict:
    try:
        ret, n, names = sap.AreaObj.GetNameList()
    except Exception as e:
        log.warning("AreaObj.GetNameList() failed: %s", e)
        return {"walls": [], "slabs": []}
    if ret != 0:
        log.warning("AreaObj.GetNameList() returned %d — skipping area objects.", ret)
        return {"walls": [], "slabs": []}
    log.info("Area objects total: %d", n)

    buckets: dict[str, list] = {"walls": [], "slabs": []}

    for name in names:
        # --- Corner points ---
        try:
            ret_p, n_pts, pt_names = sap.AreaObj.GetPoints(name)
        except Exception:
            continue
        if ret_p != 0:
            continue

        pts_3d = [pt_coords[pn] for pn in pt_names if pn in pt_coords]
        if len(pts_3d) < 3:
            continue

        # --- Wall / slab classification: GetDesignOrientation (primary) ---
        element_type = None
        try:
            ret_do, orient_area = sap.AreaObj.GetDesignOrientation(name)
            # eAreaDesignOrientation: 1=Wall, 2=Floor/Slab, 3=Ramp
            if ret_do == 0:
                if orient_area == 1:
                    element_type = "walls"
                elif orient_area == 2:
                    element_type = "slabs"
        except Exception:
            pass

        # --- Geometry fallback ---
        if element_type is None:
            _, _, nz = _normal_vector(pts_3d)
            element_type = "slabs" if abs(nz) >= 0.5 else "walls"

        allowed = {e.rstrip("s") for e in cfg.extract_elements} | {f"{e.rstrip('s')}s" for e in cfg.extract_elements}
        if element_type not in allowed:
            continue

        cx, cy, cz = _centroid_xyz(pts_3d)

        # --- Property ---
        prop_name = ""
        try:
            ret_pr, prop_name, *_ = sap.AreaObj.GetProperty(name)
            prop_name = prop_name if ret_pr == 0 else ""
        except Exception:
            pass

        # --- Thickness + material (single call) ---
        thickness_mm, material = cache.area(prop_name) if prop_name else (None, "")

        buckets[element_type].append({
            "name":          name,
            "element_type":  element_type.rstrip("s"),
            "centroid_x":    cx,   "centroid_y":   cy,   "centroid_z": cz,
            "x_match":       cx,   "y_match":       cy,
            "prop_name":     prop_name,
            "material":      material,
            "thickness_mm":  thickness_mm,
            "width_mm":      None,
            "height_mm":     thickness_mm,
            "diameter_mm":   None,
            "shape_type":    "shell",
        })

    for k, v in buckets.items():
        log.info("  %-10s %d", k, len(v))
    return buckets


# ---------------------------------------------------------------------------
# 1e — Materials, Loads, and Supports extraction
# ---------------------------------------------------------------------------

MAT_TYPES = {
    1: "Steel", 2: "Concrete", 3: "NoDesign", 4: "Aluminum",
    5: "ColdFormed", 6: "Rebar", 7: "Tendon", 8: "Masonry",
}

LOAD_TYPES = {
    1: "Dead", 2: "SuperDead", 3: "Live", 4: "ReduceLive",
    5: "Quake", 6: "Wind", 7: "Snow", 8: "Other",
}


def _extract_materials(sap, cfg: Config) -> list[dict]:
    if not cfg.audit_materials:
        return []
    materials = []
    try:
        ret, n, names = sap.PropMaterial.GetNameList()
        if ret != 0:
            return []
    except Exception as e:
        log.debug("PropMaterial.GetNameList failed: %s", e)
        return []

    for name in names:
        mat_info = {
            "name": name,
            "type": "Unknown",
            "E_gpa": None,
            "nu": None,
            "fc_mpa": None,
            "fy_mpa": None,
            "fu_mpa": None,
        }
        try:
            ret_m, mat_type, *_ = sap.PropMaterial.GetMaterial(name)
            if ret_m == 0:
                mat_info["type"] = MAT_TYPES.get(mat_type, str(mat_type))
        except Exception:
            pass

        try:
            ret_iso, e_mod, nu, *_ = sap.PropMaterial.GetMPIsotropic(name)
            if ret_iso == 0 and e_mod > 0:
                mat_info["E_gpa"] = round(e_mod / 1e6, 2)
                mat_info["nu"] = round(nu, 3)
        except Exception:
            pass

        if mat_info["type"] == "Concrete":
            try:
                ret_c = -1
                if hasattr(sap.PropMaterial, "GetOConcrete_1"):
                    ret_c, fc, *_ = sap.PropMaterial.GetOConcrete_1(name)
                if ret_c != 0 and hasattr(sap.PropMaterial, "GetOConcrete"):
                    ret_c, fc, *_ = sap.PropMaterial.GetOConcrete(name)
                if ret_c == 0:
                    mat_info["fc_mpa"] = round(fc / 1000, 2)
            except Exception:
                pass
        elif mat_info["type"] in ("Steel", "Rebar", "ColdFormed"):
            try:
                ret_s = -1
                if hasattr(sap.PropMaterial, "GetOSteel_1"):
                    ret_s, fy, fu, *_ = sap.PropMaterial.GetOSteel_1(name)
                if ret_s != 0 and hasattr(sap.PropMaterial, "GetOSteel"):
                    ret_s, fy, fu, *_ = sap.PropMaterial.GetOSteel(name)
                if ret_s == 0:
                    mat_info["fy_mpa"] = round(fy / 1000, 2)
                    mat_info["fu_mpa"] = round(fu / 1000, 2)
            except Exception:
                pass

        materials.append(mat_info)

    log.info("Extracted materials: %d", len(materials))
    return materials


def _extract_load_patterns(sap, cfg: Config) -> list[dict]:
    if not cfg.audit_loads:
        return []
    patterns = []
    try:
        ret, n, names = sap.LoadPatterns.GetNameList()
        if ret != 0:
            return []
    except Exception as e:
        log.debug("LoadPatterns.GetNameList failed: %s", e)
        return []

    for name in names:
        pat_type = "Unknown"
        self_wt = 0.0
        try:
            ret_t, t_code = sap.LoadPatterns.GetLoadType(name)
            if ret_t == 0:
                pat_type = LOAD_TYPES.get(t_code, str(t_code))
        except Exception:
            pass

        try:
            ret_w, sw = sap.LoadPatterns.GetSelfWTMultiplier(name)
            if ret_w == 0:
                self_wt = sw
        except Exception:
            pass

        patterns.append({
            "name": name,
            "type": pat_type,
            "self_weight_mult": self_wt,
        })
    log.info("Extracted load patterns: %d", len(patterns))
    return patterns


def _extract_area_loads(sap, slabs: list[dict], cfg: Config) -> list[dict]:
    if not cfg.audit_loads:
        return []
    loads = []
    for slab in slabs:
        name = slab["name"]
        try:
            try:
                ret, n_loads, area_names, load_pats, csys, dirs, vals = sap.AreaObj.GetLoadUniform(name, 0)
            except Exception:
                ret, n_loads, area_names, load_pats, csys, dirs, vals = sap.AreaObj.GetLoadUniform(name)

            if ret == 0 and n_loads > 0:
                for i in range(n_loads):
                    loads.append({
                        "area_name": name,
                        "load_pattern": load_pats[i] if i < len(load_pats) else "",
                        "val_kpa": round(vals[i], 3) if i < len(vals) else 0.0,
                        "direction": dirs[i] if i < len(dirs) else 3,
                        "floor_label": slab.get("floor_label", ""),
                        "x": slab.get("centroid_x"),
                        "y": slab.get("centroid_y"),
                    })
        except Exception as e:
            log.debug("GetLoadUniform('%s') error: %s", name, e)
    log.info("Extracted area uniform loads: %d", len(loads))
    return loads


def _extract_frame_loads(sap, beams: list[dict], cfg: Config) -> list[dict]:
    if not cfg.audit_loads:
        return []
    loads = []
    for beam in beams:
        name = beam["name"]
        try:
            try:
                ret, n_loads, frame_names, load_pats, my_type, csys, dirs, rd1, rd2, dist1, dist2, val1, val2 = sap.FrameObj.GetLoadDistributed(name, 0)
            except Exception:
                ret, n_loads, frame_names, load_pats, my_type, csys, dirs, rd1, rd2, dist1, dist2, val1, val2 = sap.FrameObj.GetLoadDistributed(name)

            if ret == 0 and n_loads > 0:
                for i in range(n_loads):
                    loads.append({
                        "frame_name": name,
                        "load_pattern": load_pats[i] if i < len(load_pats) else "",
                        "val1_kn_m": round(val1[i], 3) if i < len(val1) else 0.0,
                        "val2_kn_m": round(val2[i], 3) if i < len(val2) else 0.0,
                        "floor_label": beam.get("floor_label", ""),
                    })
        except Exception as e:
            log.debug("GetLoadDistributed('%s') error: %s", name, e)
    log.info("Extracted frame distributed loads: %d", len(loads))
    return loads


def _extract_restraints(sap, pt_coords: dict, cfg: Config) -> list[dict]:
    if not cfg.audit_restraints or not pt_coords:
        return []
    z_min = min(z for x, y, z in pt_coords.values())
    restraints = []

    for j_name, (jx, jy, jz) in pt_coords.items():
        if abs(jz - z_min) > 0.15:
            continue
        try:
            ret, val = sap.PointObj.GetRestraint(j_name)
            if ret == 0:
                u1, u2, u3, r1, r2, r3 = val[:6]
                if all([u1, u2, u3, r1, r2, r3]):
                    r_type = "Fixed"
                elif u1 and u2 and u3 and not any([r1, r2, r3]):
                    r_type = "Pinned"
                elif u3 and not any([u1, u2, r1, r2, r3]):
                    r_type = "Roller"
                elif not any([u1, u2, u3, r1, r2, r3]):
                    r_type = "FREE"
                else:
                    r_type = "Partial / Spring"

                restraints.append({
                    "joint_name": j_name,
                    "x": jx, "y": jy, "z": jz,
                    "restraint_type": r_type,
                    "is_supported": any([u1, u2, u3]),
                    "u1": u1, "u2": u2, "u3": u3,
                    "r1": r1, "r2": r2, "r3": r3,
                })
        except Exception as e:
            log.debug("GetRestraint('%s') error: %s", j_name, e)

    log.info("Extracted base restraints: %d (Ground Z=%.2f m)", len(restraints), z_min)
    return restraints


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def extract_all(cfg: Config = DEFAULT_CONFIG) -> dict[str, pd.DataFrame]:
    """
    Connect to ETABS v23 and extract all structural elements, materials, loads, and restraints.
    """
    sap = _connect(cfg)

    log.info("Building bulk point lookup …")
    pt_coords = _bulk_points(sap)
    log.info("  %d joints.", len(pt_coords))

    cache = _SectionCache(sap, cfg)

    log.info("Extracting frame objects …")
    frame_buckets = _extract_frames(sap, pt_coords, cache, cfg)

    log.info("Extracting plastic hinges …")
    hinges = _extract_hinges(sap, cfg)

    log.info("Extracting area objects …")
    area_buckets = _extract_areas(sap, pt_coords, cache, cfg)

    log.info("Extracting materials …")
    materials = _extract_materials(sap, cfg)

    log.info("Extracting load patterns …")
    load_patterns = _extract_load_patterns(sap, cfg)

    log.info("Extracting area uniform loads …")
    area_loads = _extract_area_loads(sap, area_buckets.get("slabs", []), cfg)

    log.info("Extracting frame distributed loads …")
    frame_loads = _extract_frame_loads(sap, frame_buckets.get("beams", []), cfg)

    log.info("Extracting base restraints …")
    restraints = _extract_restraints(sap, pt_coords, cfg)

    result: dict[str, pd.DataFrame] = {}
    for key in ("columns", "beams", "braces"):
        result[key] = pd.DataFrame(frame_buckets.get(key, []))
    for key in ("walls", "slabs"):
        result[key] = pd.DataFrame(area_buckets.get(key, []))
    result["hinges"] = pd.DataFrame(hinges)
    result["materials"] = pd.DataFrame(materials)
    result["load_patterns"] = pd.DataFrame(load_patterns)
    result["area_loads"] = pd.DataFrame(area_loads)
    result["frame_loads"] = pd.DataFrame(frame_loads)
    result["restraints"] = pd.DataFrame(restraints)

    log.info("─"*45)
    for k, df in result.items():
        log.info("  %-15s  %d rows", k, len(df))
    log.info("─"*45)
    return result


ALL_EXPORT_KEYS = (
    "columns", "beams", "braces", "walls", "slabs", "hinges",
    "materials", "load_patterns", "area_loads", "frame_loads", "restraints"
)


def export_to_csvs(data: dict[str, pd.DataFrame], prefix: str = "etabs") -> None:
    for key in ALL_EXPORT_KEYS:
        if key in data:
            path = f"{prefix}_{key}.csv"
            data[key].to_csv(path, index=False)
            log.info("Exported: %s (%d rows)", path, len(data[key]))


def load_from_csvs(prefix: str = "etabs") -> dict[str, pd.DataFrame]:
    import os
    data = {}
    for key in ALL_EXPORT_KEYS:
        path = f"{prefix}_{key}.csv"
        if os.path.exists(path):
            data[key] = pd.read_csv(path)
            log.debug("Loaded CSV: %s (%d rows)", path, len(data[key]))
        else:
            data[key] = pd.DataFrame()
            log.debug("CSV not found (using empty table): %s", path)
    return data


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = extract_all()
    export_to_csvs(data)
    print("Done.")
