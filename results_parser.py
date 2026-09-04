"""
results_parser.py
-----------------
Parser for optional ETABS analysis and design output tables exported from
ETABS via Display -> Show Tables -> Export Tables to Excel / CSV.

Extracts and structures data for:
- Story Drifts (Point 18)
- Story Forces & Base Shear (Points 28 & 29)
- Pier & Spandrel Forces (Point 29)
- Joint Reactions & Base Soil Pressure (Point 33)
- Frame & Pier Design Summaries (Points 35, 36, 37)
- Joint Displacements for SLS Deflections (Point 40)
"""

import io
import math
import logging
from pathlib import Path
from typing import Union, Optional, Any
import pandas as pd

log = logging.getLogger("results_parser")


def _normalize_col_name(c: Any) -> str:
    """Clean and normalize column names for flexible matching across ETABS versions."""
    s = str(c).strip().lower()
    # Remove units in parentheses or brackets, e.g. 'FZ (KN)' -> 'fz'
    if "(" in s:
        s = s.split("(")[0].strip()
    if "[" in s:
        s = s.split("[")[0].strip()
    return s.replace(" ", "_").replace("/", "_").replace("-", "_")


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Find a column matching any of the candidate keywords."""
    cols = list(df.columns)
    # First exact match on normalized names
    for cand in candidates:
        cand_norm = cand.lower().replace(" ", "_")
        for col in cols:
            col_norm = _normalize_col_name(col)
            if col_norm == cand_norm:
                return col
    # Partial substring match
    for cand in candidates:
        cand_norm = cand.lower()
        for col in cols:
            col_norm = _normalize_col_name(col)
            if cand_norm in col_norm:
                return col
    return None


def parse_etabs_results(source: Union[str, Path, bytes, io.BytesIO, io.StringIO]) -> dict[str, Any]:
    """
    Parse ETABS output tables from an Excel (.xlsx, .xls) workbook or CSV file.
    Returns a dictionary of DataFrames and extracted engineering summaries.
    """
    raw_tables: dict[str, pd.DataFrame] = {}

    # 1. Load data into DataFrame(s)
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Results file not found: {source}")
        if p.suffix.lower() in (".xlsx", ".xls"):
            xl = pd.ExcelFile(p, engine="openpyxl")
            for sname in xl.sheet_names:
                try:
                    df = xl.parse(sname)
                    if not df.empty:
                        raw_tables[sname.strip()] = df
                except Exception as ex:
                    log.warning("Failed reading sheet %s: %s", sname, ex)
        else:
            try:
                df = pd.read_csv(p)
                raw_tables["CSV_DATA"] = df
            except Exception as ex:
                log.warning("Failed reading CSV: %s", ex)

    elif isinstance(source, (bytes, io.BytesIO)):
        bio = io.BytesIO(source) if isinstance(source, bytes) else source
        try:
            xl = pd.ExcelFile(bio, engine="openpyxl")
            for sname in xl.sheet_names:
                try:
                    df = xl.parse(sname)
                    if not df.empty:
                        raw_tables[sname.strip()] = df
                except Exception as ex:
                    log.warning("Failed reading sheet %s: %s", sname, ex)
        except Exception:
            # Fallback to CSV
            bio.seek(0)
            try:
                df = pd.read_csv(bio)
                raw_tables["CSV_DATA"] = df
            except Exception as ex:
                log.warning("Failed parsing uploaded bytes: %s", ex)
    elif isinstance(source, io.StringIO):
        try:
            df = pd.read_csv(source)
            raw_tables["CSV_DATA"] = df
        except Exception as ex:
            log.warning("Failed reading StringIO CSV: %s", ex)

    # 2. Categorize worksheets / tables into standard ETABS tables
    story_drifts = pd.DataFrame()
    story_forces = pd.DataFrame()
    pier_forces = pd.DataFrame()
    joint_reactions = pd.DataFrame()
    frame_design = pd.DataFrame()
    joint_displacements = pd.DataFrame()

    for sname, df in raw_tables.items():
        s_low = sname.lower()
        cols_norm = [_normalize_col_name(c) for c in df.columns]

        # Story Drifts
        if any(k in s_low for k in ("drift", "pomak")) or any("drift" in c for c in cols_norm):
            story_drifts = df
        # Story Forces
        elif any(k in s_low for k in ("story_force", "story force", "katne_sile", "katne sile")) or (any("vx" in c for c in cols_norm) and any("story" in c for c in cols_norm)):
            story_forces = df
        # Pier Forces
        elif any(k in s_low for k in ("pier", "spandrel")) or any("pier" in c for c in cols_norm):
            pier_forces = df
        # Joint Reactions
        elif any(k in s_low for k in ("reaction", "reakcij", "joint react", "support react")) or (any("fz" in c for c in cols_norm) and any(c in cols_norm for c in ("joint", "point", "node"))):
            joint_reactions = df
        # Design summaries
        elif any(k in s_low for k in ("design", "pmm", "rebar", "armatur")) or any("pmm" in c or "rebar" in c for c in cols_norm):
            frame_design = df
        # Joint Displacements
        elif any(k in s_low for k in ("displacement", "progib", "pomac")) or (any("uz" in c for c in cols_norm) and any(c in cols_norm for c in ("joint", "point"))):
            joint_displacements = df

    # 3. Analyze Story Drifts (Point 18)
    summary: dict[str, Any] = {
        "has_results": not story_drifts.empty or not story_forces.empty or not joint_reactions.empty,
        "max_drift_x": 0.0,
        "max_drift_y": 0.0,
        "max_drift_overall": 0.0,
        "critical_drift_story": "—",
        "critical_drift_case": "—",
        "drift_by_story": [],
        "base_shear_x_kn": 0.0,
        "base_shear_y_kn": 0.0,
        "base_vertical_kn": 0.0,
        "min_fz_kn": 0.0,
        "max_fz_kn": 0.0,
        "total_fz_kn": 0.0,
        "has_soil_uplift": False,
        "uplift_joints_count": 0,
        "max_soil_pressure_kpa": 0.0,
        "max_pmm_ratio": 0.0,
        "critical_frame": "—",
        "rebar_min_pct": 0.0,
        "rebar_max_pct": 0.0,
        "max_uz_mm": 0.0,
    }

    if not story_drifts.empty:
        col_drift = _find_col(story_drifts, ["drift", "max_drift"])
        col_story = _find_col(story_drifts, ["story", "level"])
        col_dir = _find_col(story_drifts, ["direction", "dir"])
        col_case = _find_col(story_drifts, ["output_case", "load_case", "combo"])

        if col_drift:
            story_drifts[col_drift] = pd.to_numeric(story_drifts[col_drift], errors="coerce").fillna(0.0)
            max_row = story_drifts.loc[story_drifts[col_drift].idxmax()] if not story_drifts[col_drift].empty else None
            if max_row is not None:
                summary["max_drift_overall"] = float(max_row[col_drift])
                summary["critical_drift_story"] = str(max_row[col_story]) if col_story else "—"
                summary["critical_drift_case"] = str(max_row[col_case]) if col_case else "—"

            if col_dir:
                dx_sub = story_drifts[story_drifts[col_dir].astype(str).str.upper().str.contains("X")]
                dy_sub = story_drifts[story_drifts[col_dir].astype(str).str.upper().str.contains("Y")]
                summary["max_drift_x"] = float(dx_sub[col_drift].max()) if not dx_sub.empty else summary["max_drift_overall"]
                summary["max_drift_y"] = float(dy_sub[col_drift].max()) if not dy_sub.empty else summary["max_drift_overall"]
            else:
                summary["max_drift_x"] = summary["max_drift_overall"]
                summary["max_drift_y"] = summary["max_drift_overall"]

            # Drifts per story profile
            if col_story:
                drift_grp = story_drifts.groupby(col_story)[col_drift].max().to_dict()
                summary["drift_by_story"] = [{"story": s, "drift": d} for s, d in drift_grp.items()]

    # 4. Analyze Story Forces & Base Shear (Point 28 & 29)
    if not story_forces.empty:
        col_vx = _find_col(story_forces, ["vx", "shear_x", "v1"])
        col_vy = _find_col(story_forces, ["vy", "shear_y", "v2"])
        col_p = _find_col(story_forces, ["p", "axial", "n"])
        col_loc = _find_col(story_forces, ["location", "loc"])

        for col in (col_vx, col_vy, col_p):
            if col:
                story_forces[col] = pd.to_numeric(story_forces[col], errors="coerce").fillna(0.0)

        if col_vx:
            summary["base_shear_x_kn"] = float(story_forces[col_vx].abs().max())
        if col_vy:
            summary["base_shear_y_kn"] = float(story_forces[col_vy].abs().max())
        if col_p:
            summary["base_vertical_kn"] = float(story_forces[col_p].abs().max())

    # 5. Analyze Joint Reactions (Point 33 - Soil pressure & uplift)
    if not joint_reactions.empty:
        col_fz = _find_col(joint_reactions, ["fz", "f3", "reaction_z"])
        col_jnt = _find_col(joint_reactions, ["joint", "point", "node"])

        if col_fz:
            joint_reactions[col_fz] = pd.to_numeric(joint_reactions[col_fz], errors="coerce").fillna(0.0)
            fz_vals = joint_reactions[col_fz]
            summary["min_fz_kn"] = float(fz_vals.min())
            summary["max_fz_kn"] = float(fz_vals.max())
            summary["total_fz_kn"] = float(fz_vals.sum())
            
            # Tension in ground support (uplift)
            uplift_rows = joint_reactions[joint_reactions[col_fz] < -1.0] # > 1 kN tension
            summary["has_soil_uplift"] = len(uplift_rows) > 0
            summary["uplift_joints_count"] = len(uplift_rows)

            # Estimate peak soil pressure assuming typical column footing 1.8x1.8m (A=3.24m2) or wall footing
            if summary["max_fz_kn"] > 0:
                est_footing_area = 3.24 # m2
                summary["max_soil_pressure_kpa"] = round(summary["max_fz_kn"] / est_footing_area, 1)

    # 6. Analyze Frame Design Summary (Point 35 - PMM ratio & Rebar %)
    if not frame_design.empty:
        col_pmm = _find_col(frame_design, ["pmm_ratio", "ratio", "pmm"])
        col_rebar = _find_col(frame_design, ["rebar_pct", "rebar_ratio", "rebar_%"])
        col_frm = _find_col(frame_design, ["frame", "line", "column", "beam"])

        if col_pmm:
            frame_design[col_pmm] = pd.to_numeric(frame_design[col_pmm], errors="coerce").fillna(0.0)
            summary["max_pmm_ratio"] = float(frame_design[col_pmm].max())
            if col_frm and not frame_design.empty:
                max_row = frame_design.loc[frame_design[col_pmm].idxmax()]
                summary["critical_frame"] = str(max_row[col_frm])
        if col_rebar:
            frame_design[col_rebar] = pd.to_numeric(frame_design[col_rebar], errors="coerce").fillna(0.0)
            valid_rebars = frame_design[frame_design[col_rebar] > 0][col_rebar]
            if not valid_rebars.empty:
                summary["rebar_min_pct"] = float(valid_rebars.min())
                summary["rebar_max_pct"] = float(valid_rebars.max())

    # 7. Analyze Joint Displacements (Point 40 - Deflections)
    if not joint_displacements.empty:
        col_uz = _find_col(joint_displacements, ["uz", "u3", "deflection"])
        if col_uz:
            joint_displacements[col_uz] = pd.to_numeric(joint_displacements[col_uz], errors="coerce").fillna(0.0)
            # In ETABS UZ in meters or mm, convert to mm if < 1.0
            raw_uz = float(joint_displacements[col_uz].abs().max())
            summary["max_uz_mm"] = round(raw_uz * 1000.0 if raw_uz < 1.0 else raw_uz, 2)

    return {
        "has_results": summary["has_results"],
        "story_drifts": story_drifts,
        "story_forces": story_forces,
        "pier_forces": pier_forces,
        "joint_reactions": joint_reactions,
        "frame_design": frame_design,
        "joint_displacements": joint_displacements,
        "summary": summary,
    }


def create_demo_etabs_results(etabs_data: dict) -> bytes:
    """
    Generate a realistic ETABS results Excel workbook (.xlsx) tailored to the loaded model.

    Values are scaled from the actual model geometry (footprint, story count,
    story mass) so that different buildings produce distinct, plausible Phase 2
    numbers instead of identical hardcoded figures.
    Enables instant 1-click testing of Phase 2 features.
    """
    stories = etabs_data.get("stories", [])
    story_names = [s["name"] for s in stories] if stories else ["Story2", "Story1"]
    n_stories = max(len(story_names), 1)

    # --- Derive a rough building mass and seismic base shear from geometry ---
    all_pts = etabs_data.get("all_points", {})
    xs = [p[0] for p in all_pts.values()] if all_pts else []
    ys = [p[1] for p in all_pts.values()] if all_pts else []
    span_x = (max(xs) - min(xs)) if len(xs) >= 2 else 20.0
    span_y = (max(ys) - min(ys)) if len(ys) >= 2 else 15.0
    footprint = max(span_x * span_y * 0.70, 40.0)  # m2, discount for shape

    cols = etabs_data.get("columns", pd.DataFrame())
    walls = etabs_data.get("walls", pd.DataFrame())
    n_cols = len(cols) if not cols.empty else 0
    n_walls = len(walls) if not walls.empty else 0

    # Approx. seismic weight per floor: ~10 kN/m2 gravity load on the footprint
    w_per_floor = footprint * 10.0                 # kN
    w_total = w_per_floor * n_stories              # kN
    # Base shear ~ 0.10-0.15 of seismic weight (EC8 low-ductility estimate)
    base_shear_total = round(w_total * 0.12, 1)
    # Masonry (wall-dominant) buildings are stiffer -> slightly lower drift, higher shear
    is_wall_dominant = n_walls > max(n_cols, 1) * 2
    shear_x_total = base_shear_total * (1.05 if is_wall_dominant else 1.0)
    shear_y_total = base_shear_total * (0.92 if is_wall_dominant else 0.95)

    # 1. Story Drifts — wall-dominant buildings drift less
    drifts_data = []
    base_drift = 0.0014 if is_wall_dominant else 0.0022
    for idx, s in enumerate(reversed(story_names)):
        drift_x = round(base_drift * (1.0 + 0.35 * idx), 4)
        drift_y = round(base_drift * (0.95 + 0.30 * idx), 4)
        drifts_data.append({"Story": s, "Output Case": "E_X Max", "Direction": "X", "Drift": drift_x, "Label": "Edge"})
        drifts_data.append({"Story": s, "Output Case": "E_Y Max", "Direction": "Y", "Drift": drift_y, "Label": "Edge"})
    df_drifts = pd.DataFrame(drifts_data)

    # 2. Story Forces — cumulative shear grows toward the base
    forces_data = []
    for idx, s in enumerate(reversed(story_names)):
        frac = (idx + 1) / n_stories
        vx = round(shear_x_total * frac, 1)
        vy = round(shear_y_total * frac, 1)
        p = round(w_per_floor * (idx + 1), 1)
        forces_data.append({"Story": s, "Output Case": "1.35G + 1.50Q", "Location": "Bottom", "P": -p, "VX": vx, "VY": vy})
    df_forces = pd.DataFrame(forces_data)

    # 3. Joint Reactions — scaled so total roughly matches building weight
    n_supports = max(n_cols, n_walls, 8)
    n_supports = min(n_supports, 60)
    avg_fz = w_total / n_supports if n_supports else 500.0
    react_data = []
    for p_id in range(1, n_supports + 1):
        # Vary +-35% around the average to create a realistic spread
        fz = round(avg_fz * (0.65 + 0.70 * (math.sin(float(p_id)) ** 2)), 1)
        react_data.append({"Story": "Base", "Joint": str(p_id), "Output Case": "1.35G + 1.50Q", "FX": 25.0, "FY": 18.0, "FZ": fz})
    df_react = pd.DataFrame(react_data)

    # 4. Frame Design Summary — utilization scales with column density
    design_data = []
    n_design = min(max(n_cols, 8), 40)
    # Denser column grids -> lower average utilization per column
    util_base = 0.75 if n_cols and n_cols < 40 else 0.55
    for c_id in range(1, n_design + 1):
        pmm = round(min(util_base + 0.20 * (math.sin(c_id) ** 2), 0.99), 2)
        rebar_pct = round(1.0 + 0.8 * (math.cos(c_id) ** 2), 2)
        design_data.append({"Story": story_names[-1] if story_names else "Story1", "Frame": f"C{c_id}", "Design Sect": "STUP40/30_sd", "PMM Ratio": pmm, "Rebar %": rebar_pct, "Status": "OK"})
    df_design = pd.DataFrame(design_data)

    # 5. Write to BytesIO Excel
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_drifts.to_excel(writer, sheet_name="Story Drifts", index=False)
        df_forces.to_excel(writer, sheet_name="Story Forces", index=False)
        df_react.to_excel(writer, sheet_name="Joint Reactions", index=False)
        df_design.to_excel(writer, sheet_name="Concrete Column Design", index=False)
    
    return out.getvalue()
