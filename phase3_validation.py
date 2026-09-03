"""
phase3_validation.py
--------------------
Spatial cross-referencing engine — v2 (multi-type, per-type tolerances, hinge reporting).

Runs a separate KD-tree match for each element type:
  columns, beams, braces → use cfg.spatial_tolerance_frame
  walls, slabs            → use cfg.spatial_tolerance_area

Section dimension comparison uses ETABS property definition values (width_mm / height_mm
/ thickness_mm) — NOT regex from section names.

Hinge data is merged onto matched frame elements as informational columns.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

try:
    from scipy.spatial import KDTree  # type: ignore
except ImportError:
    raise ImportError("scipy is required. Run: pip install scipy")

from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class Status(str, Enum):
    MATCH             = "MATCH"
    SECTION_MISMATCH  = "SECTION_MISMATCH"
    ETABS_ONLY        = "ETABS_ONLY"
    DXF_ONLY          = "DXF_ONLY"


# ---------------------------------------------------------------------------
# Dimension comparison
# ---------------------------------------------------------------------------

def _dims_match(
    etabs_w: Optional[float], etabs_h: Optional[float],
    dxf_d1:  Optional[float], dxf_d2:  Optional[float],
    tol: float,
) -> bool:
    """
    Compare cross-section dimensions (all in mm).
    Handles 2D cross sections (b x h) as well as 1D thickness dimensions (walls/slabs).
    """
    # Treat NaN as None
    if etabs_w is not None and (pd.isna(etabs_w) or np.isnan(etabs_w)): etabs_w = None
    if etabs_h is not None and (pd.isna(etabs_h) or np.isnan(etabs_h)): etabs_h = None
    if dxf_d1  is not None and (pd.isna(dxf_d1)  or np.isnan(dxf_d1)):  dxf_d1  = None
    if dxf_d2  is not None and (pd.isna(dxf_d2)  or np.isnan(dxf_d2)):  dxf_d2  = None

    # Single-dimension comparison (e.g. wall/slab thickness or circular diameter)
    if etabs_w is None and etabs_h is not None:
        target = dxf_d1 if dxf_d1 is not None else dxf_d2
        return target is None or abs(etabs_h - target) <= tol

    if etabs_h is None and etabs_w is not None:
        target = dxf_d1 if dxf_d1 is not None else dxf_d2
        return target is None or abs(etabs_w - target) <= tol

    if None in (etabs_w, etabs_h, dxf_d1, dxf_d2):
        return True

    direct  = abs(etabs_w - dxf_d1) <= tol and abs(etabs_h - dxf_d2) <= tol
    flipped = abs(etabs_w - dxf_d2) <= tol and abs(etabs_h - dxf_d1) <= tol
    return direct or flipped


# ---------------------------------------------------------------------------
# Single-type matching
# ---------------------------------------------------------------------------

def _get_coord(row, *keys, default=0.0):
    if row is None:
        return default
    for k in keys:
        try:
            val = row.get(k)
            if val is not None and pd.notna(val):
                return float(val)
        except (ValueError, TypeError, KeyError):
            continue
    return default


def _match_type(
    df_etabs:   pd.DataFrame,
    df_dxf:     pd.DataFrame,
    tol:        float,
    sec_tol:    float,
    element_type: str,
) -> pd.DataFrame:
    """
    Match one element type. Returns a DataFrame of results for that type.
    """
    results = []

    etabs_has = not df_etabs.empty
    dxf_has   = not df_dxf.empty

    # Build KD-tree from DXF positions
    dxf_matched = [False] * len(df_dxf)
    tree = None
    if dxf_has:
        dxf_xy = df_dxf[["centroid_x_m", "centroid_y_m"]].to_numpy(dtype=float)
        tree   = KDTree(dxf_xy)

    # --- ETABS → DXF -------------------------------------------------------
    if etabs_has:
        for _, er in df_etabs.iterrows():
            ex = _get_coord(er, "x_match", "centroid_x", "x_bot", "x", default=0.0)
            ey = _get_coord(er, "y_match", "centroid_y", "y_bot", "y", default=0.0)

            if tree is not None:
                dist, idx = tree.query([ex, ey], k=1)
            else:
                dist, idx = float("inf"), -1

            if dist <= tol and idx >= 0:
                dxf_matched[idx] = True
                dr = df_dxf.iloc[idx]

                ew = er.get("width_mm") if er.get("width_mm") is not None else er.get("section_w_mm")
                eh = er.get("height_mm") if er.get("height_mm") is not None else er.get("section_h_mm")
                dw = dr.get("dim1_mm") if dr.get("dim1_mm") is not None else dr.get("width_mm")
                dh = dr.get("dim2_mm") if dr.get("dim2_mm") is not None else dr.get("height_mm")

                sec_ok = _dims_match(ew, eh, dw, dh, sec_tol)
                status = Status.MATCH if sec_ok else Status.SECTION_MISMATCH

                notes = ""
                if not sec_ok:
                    if None not in (ew, eh, dw, dh):
                        notes = f"ETABS: {ew:.0f}×{eh:.0f} mm | DXF: {dw:.0f}×{dh:.0f} mm"
                    else:
                        notes = "Section dimension parse failed on one side"

                results.append(_row(status, er, dr, dist, element_type, notes))
            else:
                near = f"{dist:.3f} m" if dist < float("inf") else "N/A"
                results.append(_row(
                    Status.ETABS_ONLY, er, None, dist, element_type,
                    f"No DXF match within {tol} m (nearest: {near})"
                ))

    # --- DXF-only ----------------------------------------------------------
    if dxf_has:
        for i, matched in enumerate(dxf_matched):
            if not matched:
                dr = df_dxf.iloc[i]
                results.append(_row(
                    Status.DXF_ONLY, None, dr, None, element_type,
                    "In DXF only — not found in ETABS model"
                ))

    return pd.DataFrame(results)


def _first_valid(row, *keys, default=None):
    if row is None:
        return default
    for k in keys:
        try:
            val = row.get(k)
            if val is not None and pd.notna(val):
                return val
        except Exception:
            continue
    return default


def _row(
    status: Status,
    er,    # ETABS row (Series or None)
    dr,    # DXF row   (Series or None)
    dist:  Optional[float],
    element_type: str,
    notes: str = "",
) -> dict:
    ew = _first_valid(er, "width_mm", "section_w_mm")
    eh = _first_valid(er, "height_mm", "section_h_mm")
    dw = _first_valid(dr, "dim1_mm", "width_mm")
    dh = _first_valid(dr, "dim2_mm", "height_mm")

    ex = _first_valid(er, "x_match", "centroid_x", "x_bot")
    ey = _first_valid(er, "y_match", "centroid_y", "y_bot")
    ez = _first_valid(er, "z_start", "centroid_z", "z_bot")

    dxf_mat = _first_valid(dr, "dxf_material", default="")
    etabs_mat = _first_valid(er, "material", default="")
    mat_match = True
    if etabs_mat and dxf_mat:
        norm_e = etabs_mat.lower().replace(" ", "")
        norm_d = dxf_mat.lower().replace(" ", "")
        if norm_d not in norm_e and norm_e not in norm_d:
            mat_match = False
            notes = (notes + f" | Material: ETABS={etabs_mat} vs CAD={dxf_mat}").lstrip(" | ")

    return {
        "element_type":   element_type,
        "status":         status,
        # ETABS fields
        "etabs_name":     _first_valid(er, "name", default=""),
        "etabs_x":        ex,
        "etabs_y":        ey,
        "etabs_z":        ez,
        "story":          _first_valid(er, "story", default=""),
        "etabs_section":  _first_valid(er, "section", "prop_name", default=""),
        "etabs_material": etabs_mat,
        "etabs_shape":    _first_valid(er, "shape_type", default=""),
        "etabs_w_mm":     ew,
        "etabs_h_mm":     eh,
        "etabs_d_mm":     _first_valid(er, "diameter_mm"),
        # Hinge fields (populated later by merge)
        "has_hinges":     False,
        "hinge_count":    0,
        "hinge_details":  "",
        # DXF fields
        "dxf_dim_text":   _first_valid(dr, "dim_text", default=""),
        "dxf_x":          _first_valid(dr, "centroid_x_m"),
        "dxf_y":          _first_valid(dr, "centroid_y_m"),
        "dxf_d1_mm":      dw,
        "dxf_d2_mm":      dh,
        "dxf_w_mm":       dw,
        "dxf_h_mm":       dh,
        "dxf_material":   dxf_mat,
        "material_match": mat_match,
        "floor_label":    _first_valid(dr, "floor_label", default=""),
        "grid_ref":       _first_valid(dr, "grid_ref", default=""),
        # Loads (populated later for slabs)
        "etabs_load_g_kpa": None,
        "etabs_load_q_kpa": None,
        "dxf_load_g_kpa": _first_valid(dr, "dxf_load_g_kpa"),
        "dxf_load_q_kpa": _first_valid(dr, "dxf_load_q_kpa"),
        # Match quality
        "xy_dist_m":      round(dist, 4) if dist is not None and dist < float("inf") else None,
        "notes":          notes,
    }


# ---------------------------------------------------------------------------
# Hinge merge
# ---------------------------------------------------------------------------

def _merge_hinges(df_result: pd.DataFrame, df_hinges: pd.DataFrame) -> pd.DataFrame:
    """
    Annotate matched/ETABS-only frame rows with hinge information.
    Modifies df_result in-place and returns it.
    """
    if df_hinges.empty or df_result.empty:
        return df_result

    # Aggregate hinges per frame
    hinge_dict = {}
    for frame_name, group in df_hinges.groupby("frame_name"):
        details = "; ".join(
            f"{row['hinge_prop']}@{row['rel_dist']:.2f}"
            for _, row in group.iterrows()
            if pd.notna(row.get("hinge_prop")) and pd.notna(row.get("rel_dist"))
        )
        hinge_dict[frame_name] = {
            "hinge_count": len(group),
            "hinge_details": details,
        }

    for i, row in df_result.iterrows():
        name = row.get("etabs_name", "")
        if name and name in hinge_dict:
            h = hinge_dict[name]
            df_result.at[i, "has_hinges"]    = True
            df_result.at[i, "hinge_count"]   = int(h["hinge_count"])
            df_result.at[i, "hinge_details"] = h["hinge_details"]

    return df_result


def _merge_loads(df_result: pd.DataFrame, df_area_loads: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    if df_area_loads.empty or "area_name" not in df_area_loads.columns:
        return df_result

    slab_loads = {}
    for an, grp in df_area_loads.groupby("area_name"):
        g_val = 0.0
        q_val = 0.0
        for _, row in grp.iterrows():
            pat = str(row.get("load_pattern", "")).lower()
            val = abs(float(row.get("val_kpa", 0.0)))
            if any(k in pat for k in ("dead", "sdl", "staln", "g", "super")):
                g_val += val
            elif any(k in pat for k in ("live", "koris", "q", "p")):
                q_val += val
            else:
                g_val += val
        slab_loads[an] = (round(g_val, 2), round(q_val, 2))

    for idx, row in df_result.iterrows():
        if row["element_type"] == "slab" and row["etabs_name"] in slab_loads:
            eg, eq = slab_loads[row["etabs_name"]]
            df_result.at[idx, "etabs_load_g_kpa"] = eg
            df_result.at[idx, "etabs_load_q_kpa"] = eq

            dg = row.get("dxf_load_g_kpa")
            dq = row.get("dxf_load_q_kpa")
            notes = str(row.get("notes", ""))
            if dg is not None and abs(eg - dg) > cfg.load_tolerance_kpa:
                notes = (notes + f" | Dead load diff: ETABS {eg} vs CAD {dg} kPa").lstrip(" | ")
            if dq is not None and abs(eq - dq) > cfg.load_tolerance_kpa:
                notes = (notes + f" | Live load diff: ETABS {eq} vs CAD {dq} kPa").lstrip(" | ")
            df_result.at[idx, "notes"] = notes

    return df_result


def run_structural_sanity_checks(etabs_dict: dict, cfg: Config) -> list[dict]:
    """
    Run automated structural engineering sanity checks on model data:
      1. Dead Load self-weight multiplier must be 1.0 (other patterns 0.0)
      2. Floor slabs must not have 0.0 surface loads
      3. Base column joints must have support restraints
    """
    alerts = []

    # 1. Load Patterns Self-Weight Audit
    df_pats = etabs_dict.get("load_patterns", pd.DataFrame())
    if not df_pats.empty and "name" in df_pats.columns:
        dead_pats_with_sw = []
        dead_pats_without_sw = []
        for _, r in df_pats.iterrows():
            name = str(r.get("name", "")).strip().upper()
            ptype = str(r.get("type", "")).strip().lower()
            sw = float(r.get("self_weight_mult", 0.0))

            is_dead = (ptype == "dead" or name in ("DEAD", "G", "DL", "VLASTITA"))
            if is_dead:
                if abs(sw - 1.0) < 1e-4:
                    dead_pats_with_sw.append(name)
                else:
                    dead_pats_without_sw.append((name, sw))
            else:
                # Non-dead patterns (LIVE, SEISMIC, WIND, etc.) should have sw == 0.0
                if sw > 1e-4:
                    alerts.append({
                        "category": "Load Pattern",
                        "severity": "ERROR",
                        "element": name,
                        "issue": f"{name} ({ptype}) ima faktor vlastite težine {sw:.2f} > 0.0! Vlastita težina se dvostruko računa.",
                    })

        # Warn if NO dead load pattern has self-weight multiplier 1.0
        if not dead_pats_with_sw and dead_pats_without_sw:
            p_names = ", ".join([p[0] for p in dead_pats_without_sw])
            alerts.append({
                "category": "Load Pattern",
                "severity": "WARNING",
                "element": p_names,
                "issue": f"Stalna opterećenja ({p_names}) imaju faktor vlastite težine 0.00 (očekivano 1.0). Vlastita težina konstrukcije možda nije uzeta u obzir!",
            })
        elif len(dead_pats_with_sw) > 1:
            alerts.append({
                "category": "Load Pattern",
                "severity": "WARNING",
                "element": ", ".join(dead_pats_with_sw),
                "issue": f"Više slučajeva opterećenja ({', '.join(dead_pats_with_sw)}) ima faktor vlastite težine 1.0! Provjerite da se težina ne računa dvostruko.",
            })

    # 2. Base Supports Audit
    df_res = etabs_dict.get("restraints", pd.DataFrame())
    if not df_res.empty and "restraint_type" in df_res.columns:
        free_joints = df_res[df_res["restraint_type"] == "FREE"]
        for _, r in free_joints.iterrows():
            alerts.append({
                "category": "Support",
                "severity": "ERROR",
                "element": r.get("joint_name", ""),
                "issue": f"Čvor u bazi na koti ({r.get('x', 0):.2f}, {r.get('y', 0):.2f}) nema zadane ležajeve (slobodan čvor)! Element lebdi.",
            })

    # 3. Unloaded Floor Slabs Audit
    df_slabs = etabs_dict.get("slabs", pd.DataFrame())
    df_aloads = etabs_dict.get("area_loads", pd.DataFrame())
    if not df_slabs.empty:
        loaded_slabs = set(df_aloads["area_name"].dropna().unique()) if (not df_aloads.empty and "area_name" in df_aloads.columns) else set()
        for _, r in df_slabs.iterrows():
            s_name = r.get("name", "")
            if s_name and s_name not in loaded_slabs:
                alerts.append({
                    "category": "Area Load",
                    "severity": "WARNING",
                    "element": s_name,
                    "issue": f"Stropna ploča {s_name} nema zadano plošno opterećenje u modelu (korisno opterećenje Q / dodatno stalno VT od slojeva poda).",
                })

    return alerts


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def validate(
    etabs_data: dict[str, pd.DataFrame] | pd.DataFrame,
    df_dxf:    pd.DataFrame,
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Cross-reference all ETABS element types against DXF elements.

    Parameters
    ----------
    etabs_data : dict or DataFrame
        Output of phase1_etabs.extract_all() or single DataFrame of columns.
        Keys: "columns", "beams", "braces", "walls", "slabs", "hinges"
    df_dxf : DataFrame
        Output of phase2_dxf.parse_dxf().
    cfg : Config

    Returns
    -------
    pd.DataFrame — unified result table for all element types.
    """
    FRAME_TYPES = {"column", "beam", "brace"}
    AREA_TYPES  = {"wall", "slab"}

    # Normalize etabs_data
    if isinstance(etabs_data, pd.DataFrame):
        if etabs_data.empty:
            etabs_dict = {"columns": pd.DataFrame()}
        elif "element_type" in etabs_data.columns:
            etabs_dict = {
                (f"{t}s" if not t.endswith("s") else t): grp
                for t, grp in etabs_data.groupby("element_type")
            }
        else:
            etabs_dict = {"columns": etabs_data}
    elif isinstance(etabs_data, dict):
        etabs_dict = dict(etabs_data)
    else:
        etabs_dict = {"columns": pd.DataFrame()}

    # Normalize df_dxf
    if not df_dxf.empty and "element_type" not in df_dxf.columns:
        df_dxf = df_dxf.copy()
        df_dxf["element_type"] = "column"

    all_results = []

    # Filter DXF DataFrame by element type
    dxf_by_type: dict[str, pd.DataFrame] = {}
    if not df_dxf.empty:
        for et in df_dxf["element_type"].dropna().unique():
            dxf_by_type[str(et)] = df_dxf[df_dxf["element_type"] == et].reset_index(drop=True)

    # Collect all physical structural element types to process
    VALID_ELEMENT_TYPES = {"column", "beam", "brace", "wall", "slab"}
    active_types = set()
    for plural in etabs_dict.keys():
        s = plural.rstrip("s")
        if s in VALID_ELEMENT_TYPES:
            active_types.add(s)
    for et in dxf_by_type.keys():
        if et in VALID_ELEMENT_TYPES:
            active_types.add(et)
    # Restrict to user-selected element types if cfg.extract_elements is provided
    if cfg.extract_elements:
        allowed = {et.rstrip("s") for et in cfg.extract_elements if et.rstrip("s") in VALID_ELEMENT_TYPES}
        active_types = active_types.intersection(allowed)

    for singular in sorted(active_types):
        plural = f"{singular}s"
        df_etabs_type = etabs_dict.get(plural, etabs_dict.get(singular, pd.DataFrame()))
        df_dxf_type   = dxf_by_type.get(singular, pd.DataFrame())

        if df_etabs_type.empty and df_dxf_type.empty:
            continue

        tol = (cfg.spatial_tolerance_frame if singular in FRAME_TYPES
               else cfg.spatial_tolerance_area)

        log.info("Matching %s: ETABS=%d  DXF=%d  tol=%.2f m",
                 singular, len(df_etabs_type), len(df_dxf_type), tol)

        df_res = _match_type(df_etabs_type, df_dxf_type, tol, cfg.section_tolerance_mm, singular)
        all_results.append(df_res)

    valid_results = [df for df in all_results if not df.empty]
    if not valid_results:
        return pd.DataFrame()

    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        df_result = pd.concat(valid_results, ignore_index=True)

    # Merge hinge annotations onto frame results
    if cfg.report_hinges and "hinges" in etabs_dict:
        df_result = _merge_hinges(df_result, etabs_dict["hinges"])

    # Merge area loads onto slab results
    if cfg.audit_loads and "area_loads" in etabs_dict:
        df_result = _merge_loads(df_result, etabs_dict["area_loads"], cfg)

    # Run structural sanity checks
    sanity_alerts = run_structural_sanity_checks(etabs_dict, cfg)
    df_result.attrs["sanity_alerts"] = sanity_alerts

    def _to_recs(obj):
        if isinstance(obj, pd.DataFrame):
            recs = obj.to_dict(orient="records")
        elif isinstance(obj, list):
            recs = obj
        else:
            return []
        cleaned = []
        for r in recs:
            cleaned.append({k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()})
        return cleaned

    df_result.attrs["materials"] = _to_recs(etabs_dict.get("materials"))
    df_result.attrs["load_patterns"] = _to_recs(etabs_dict.get("load_patterns"))
    df_result.attrs["area_loads"] = _to_recs(etabs_dict.get("area_loads"))
    df_result.attrs["frame_loads"] = _to_recs(etabs_dict.get("frame_loads"))
    df_result.attrs["restraints"] = _to_recs(etabs_dict.get("restraints"))

    # Summary log
    counts = df_result["status"].value_counts()
    log.info("─" * 45)
    log.info("Validation summary (all types):")
    for st in Status:
        log.info("  %-22s %d", st, counts.get(st, 0))
    log.info("  %-22s %d", "TOTAL", len(df_result))
    log.info("─" * 45)

    if cfg.report_hinges and "has_hinges" in df_result.columns:
        n_h = df_result["has_hinges"].sum()
        log.info("Frames with plastic hinges: %d", n_h)

    return df_result


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(df_result: pd.DataFrame) -> None:
    if df_result.empty:
        print("No results."); return

    print("\n" + "="*60)
    print("  ETABS ↔ DXF VALIDATION SUMMARY")
    print("="*60)

    # Per-type breakdown
    for et, grp in df_result.groupby("element_type"):
        counts = grp["status"].value_counts()
        print(f"\n  {et.upper()}S ({len(grp)} total)")
        for st in Status:
            n = counts.get(st, 0)
            if n: print(f"    {st:<22} {n}")

    print("\n" + "-"*60)
    total_counts = df_result["status"].value_counts()
    for st in Status:
        print(f"  {st:<22} {total_counts.get(st, 0):>4}")
    print(f"  {'TOTAL':<22} {len(df_result):>4}")
    print("="*60 + "\n")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 3:
        print("Usage: python phase3_validation.py etabs_prefix dxf_elements.csv")
        sys.exit(1)
    from phase1_etabs import load_from_csvs
    etabs_data = load_from_csvs(sys.argv[1])
    df_dxf = pd.read_csv(sys.argv[2])
    df_r = validate(etabs_data, df_dxf)
    print_summary(df_r)
    df_r.to_csv("validation_results.csv", index=False)
