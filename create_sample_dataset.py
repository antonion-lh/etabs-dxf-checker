"""
create_sample_dataset.py
------------------------
Generates a realistic multi-floor structural test case:
1. sample_building.dxf (Multi-floor DXF with grid, columns, beams, walls, slabs)
2. etabs_sample_*.csv  (Matching ETABS model data with intentional discrepancies + hinges)
"""

import math
import ezdxf
import pandas as pd

def create_dxf(filename="sample_building.dxf"):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.new("FLOOR_1")
    doc.layers.new("FLOOR_2")
    doc.layers.new("GRID")

    # Grid axes at scale 0.01 (100 units = 1 meter)
    # Grids X: A=0, B=600 (6m), C=1200 (12m)
    # Grids Y: 1=0, 2=600 (6m), 3=1200 (12m)
    # Grid lines (length 1600 units, with bubbles at ends)
    for name, x in [("A", 0), ("B", 600), ("C", 1200)]:
        msp.add_line((x, -200), (x, 1400), dxfattribs={"layer": "GRID"})
        # Bubble circle
        msp.add_circle((x, 1450), radius=35, dxfattribs={"layer": "GRID"})
        msp.add_text(name, dxfattribs={"insert": (x-12, 1438), "height": 25, "layer": "GRID"})

    for name, y in [("1", 0), ("2", 600), ("3", 1200)]:
        msp.add_line((-200, y), (1400, y), dxfattribs={"layer": "GRID"})
        msp.add_circle((-250, y), radius=35, dxfattribs={"layer": "GRID"})
        msp.add_text(name, dxfattribs={"insert": (-262, y-12), "height": 25, "layer": "GRID"})

    # --- FLOOR 1 Elements ---
    # 1. Column C1 at (0, 0) [A-1]: 40x50 cm
    msp.add_lwpolyline([(-20, -25), (20, -25), (20, 25), (-20, 25)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("40x50", dxfattribs={"insert": (30, 0), "height": 14, "layer": "FLOOR_1"})

    # 2. Column C2 at (600, 0) [B-1]: Circular Ø45 cm
    # Approximate circle as regular polygon for LWPOLYLINE or square box
    msp.add_lwpolyline([(580, -20), (620, -20), (620, 20), (580, 20)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("Ø45", dxfattribs={"insert": (630, 0), "height": 14, "layer": "FLOOR_1"})

    # 3. Column C3 at (1200, 0) [C-1]: 30x60 cm
    msp.add_lwpolyline([(1185, -30), (1215, -30), (1215, 30), (1185, 30)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("30x60", dxfattribs={"insert": (1225, 0), "height": 14, "layer": "FLOOR_1"})

    # 4. Beam B1 along Grid 1 between (20, 0) and (580, 0): span ~5.6m, width 30cm (outline 560x30)
    msp.add_lwpolyline([(30, -15), (570, -15), (570, 15), (30, 15)], close=True, dxfattribs={"layer": "FLOOR_1"})
    # Dimension in DXF says 30x50, but ETABS has 30x40 (SECTION MISMATCH!)
    msp.add_text("30x50", dxfattribs={"insert": (300, 25), "height": 14, "layer": "FLOOR_1"})

    # 5. Shear Wall W1 along Grid A between Y=300 and Y=550 (length 2.5m, thickness 25cm -> 25x250)
    msp.add_lwpolyline([(-12, 300), (12, 300), (12, 550), (-12, 550)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("t=25", dxfattribs={"insert": (25, 420), "height": 14, "layer": "FLOOR_1"})

    # 6. Floor Slab S1 covering bay A-B / 1-2 (area 6x6m = 36 m² > 4m²)
    msp.add_lwpolyline([(0, 0), (600, 0), (600, 600), (0, 600)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("d=20", dxfattribs={"insert": (280, 280), "height": 16, "layer": "FLOOR_1"})

    # 7. Extra column in DXF at (600, 600) [B-2]: 30x30 (DXF ONLY - not modeled in ETABS!)
    msp.add_lwpolyline([(585, 585), (615, 585), (615, 615), (585, 615)], close=True, dxfattribs={"layer": "FLOOR_1"})
    msp.add_text("30x30", dxfattribs={"insert": (625, 600), "height": 14, "layer": "FLOOR_1"})

    # 8. Add General Material & Load notes in DXF
    msp.add_text("BETON: C30/37, CELIK: B500B", dxfattribs={"insert": (0, -100), "height": 18, "layer": "FLOOR_1"})
    msp.add_text("g=2.00 kN/m2, q=3.00 kN/m2", dxfattribs={"insert": (120, 200), "height": 14, "layer": "FLOOR_1"})

    doc.saveas(filename)
    print(f"Created DXF: {filename}")

def create_etabs_csvs(prefix="etabs_sample"):
    # Scale: DXF 100 units = 1 meter (dxf_unit_scale=0.01)
    # Columns
    df_cols = pd.DataFrame([
        # 1. C1 at (0, 0): MATCH (400x500 mm)
        {"name": "C1", "element_type": "column", "x_start": 0.0, "y_start": 0.0, "z_start": 0.0,
         "x_end": 0.0, "y_end": 0.0, "z_end": 3.2, "x_match": 0.0, "y_match": 0.0,
         "section": "COL_40x50", "material": "C30/37", "shape_type": "rectangular",
         "width_mm": 400.0, "height_mm": 500.0, "diameter_mm": None},
        # 2. C2 at (6.0, 0.0): MATCH Circular (450 mm diameter)
        {"name": "C2", "element_type": "column", "x_start": 6.0, "y_start": 0.0, "z_start": 0.0,
         "x_end": 6.0, "y_end": 0.0, "z_end": 3.2, "x_match": 6.0, "y_match": 0.0,
         "section": "COL_CIRC_45", "material": "C30/37", "shape_type": "circular",
         "width_mm": 450.0, "height_mm": 450.0, "diameter_mm": 450.0},
        # 3. C3 at (12.0, 0.0): MATCH (300x600 mm)
        {"name": "C3", "element_type": "column", "x_start": 12.0, "y_start": 0.0, "z_start": 0.0,
         "x_end": 12.0, "y_end": 0.0, "z_end": 3.2, "x_match": 12.0, "y_match": 0.0,
         "section": "COL_30x60", "material": "C30/37", "shape_type": "rectangular",
         "width_mm": 300.0, "height_mm": 600.0, "diameter_mm": None},
        # 4. C4 at (0.0, 12.0): ETABS ONLY! (Present in model, omitted from DXF drawing)
        {"name": "C4_ROOF", "element_type": "column", "x_start": 0.0, "y_start": 12.0, "z_start": 0.0,
         "x_end": 0.0, "y_end": 12.0, "z_end": 3.2, "x_match": 0.0, "y_match": 12.0,
         "section": "COL_40x40", "material": "C30/37", "shape_type": "rectangular",
         "width_mm": 400.0, "height_mm": 400.0, "diameter_mm": None},
    ])
    df_cols.to_csv(f"{prefix}_columns.csv", index=False)

    # Beams
    # B1 midpoint is at (3.0, 0.0). In ETABS: 300x400 mm. In DXF: 30x50 cm -> SECTION MISMATCH!
    df_beams = pd.DataFrame([
        {"name": "B101", "element_type": "beam", "x_start": 0.0, "y_start": 0.0, "z_start": 3.2,
         "x_end": 6.0, "y_end": 0.0, "z_end": 3.2, "x_match": 3.0, "y_match": 0.0,
         "section": "BM_30x40", "material": "C25/30", "shape_type": "rectangular",
         "width_mm": 300.0, "height_mm": 400.0, "diameter_mm": None}
    ])
    df_beams.to_csv(f"{prefix}_beams.csv", index=False)

    # Walls
    # W1 centroid is at (0.0, 4.25). In ETABS thickness is 250mm. DXF has t=25 -> MATCH!
    df_walls = pd.DataFrame([
        {"name": "W1", "element_type": "wall", "centroid_x": 0.0, "centroid_y": 4.25, "centroid_z": 1.6,
         "x_match": 0.0, "y_match": 4.25, "prop_name": "WALL_25", "material": "C30/37",
         "thickness_mm": 250.0, "width_mm": None, "height_mm": 250.0, "shape_type": "shell"}
    ])
    df_walls.to_csv(f"{prefix}_walls.csv", index=False)

    # Slabs
    # S1 centroid is at (3.0, 3.0). In ETABS thickness is 200mm. DXF has d=20 -> MATCH!
    df_slabs = pd.DataFrame([
        {"name": "SLAB_BAY1", "element_type": "slab", "centroid_x": 3.0, "centroid_y": 3.0, "centroid_z": 3.2,
         "x_match": 3.0, "y_match": 3.0, "prop_name": "SLAB_20", "material": "C30/37",
         "thickness_mm": 200.0, "width_mm": None, "height_mm": 200.0, "shape_type": "shell"}
    ])
    df_slabs.to_csv(f"{prefix}_slabs.csv", index=False)

    # Braces (empty in this sample)
    pd.DataFrame(columns=["name", "x_match", "y_match"]).to_csv(f"{prefix}_braces.csv", index=False)

    # Plastic Hinges (Nonlinearities) assigned to C1 and B101
    df_hinges = pd.DataFrame([
        {"frame_name": "C1", "hinge_prop": "P-M2-M3_Auto", "rel_dist": 0.05, "dof": "P-M2-M3", "hinge_id": 1},
        {"frame_name": "C1", "hinge_prop": "P-M2-M3_Auto", "rel_dist": 0.95, "dof": "P-M2-M3", "hinge_id": 2},
        {"frame_name": "B101", "hinge_prop": "M3_FEMA356", "rel_dist": 0.08, "dof": "M3", "hinge_id": 3},
        {"frame_name": "B101", "hinge_prop": "M3_FEMA356", "rel_dist": 0.92, "dof": "M3", "hinge_id": 4},
    ])
    df_hinges.to_csv(f"{prefix}_hinges.csv", index=False)

    # Materials (Materijali)
    df_mats = pd.DataFrame([
        {"name": "C30/37", "type": "Concrete", "E_gpa": 33.0, "nu": 0.2, "fc_mpa": 30.0, "fy_mpa": None, "fu_mpa": None},
        {"name": "C25/30", "type": "Concrete", "E_gpa": 31.0, "nu": 0.2, "fc_mpa": 25.0, "fy_mpa": None, "fu_mpa": None},
        {"name": "B500B",  "type": "Rebar",    "E_gpa": 200.0, "nu": 0.3, "fc_mpa": None, "fy_mpa": 500.0, "fu_mpa": 550.0},
        {"name": "S355",   "type": "Steel",    "E_gpa": 210.0, "nu": 0.3, "fc_mpa": None, "fy_mpa": 355.0, "fu_mpa": 510.0},
    ])
    df_mats.to_csv(f"{prefix}_materials.csv", index=False)

    # Load Patterns (Opterećenja)
    df_pats = pd.DataFrame([
        {"name": "DEAD",    "type": "Dead",      "self_weight_mult": 1.0},
        {"name": "SDL",     "type": "SuperDead", "self_weight_mult": 0.0},
        {"name": "LIVE",    "type": "Live",      "self_weight_mult": 0.0},
        {"name": "WIND_X",  "type": "Wind",      "self_weight_mult": 0.0},
    ])
    df_pats.to_csv(f"{prefix}_load_patterns.csv", index=False)

    # Area Uniform Loads (Opterećenja ploča)
    df_aloads = pd.DataFrame([
        {"area_name": "SLAB_BAY1", "load_pattern": "SDL",  "val_kpa": 2.00, "direction": 3, "floor_label": "FLOOR_1", "x": 3.0, "y": 3.0},
        {"area_name": "SLAB_BAY1", "load_pattern": "LIVE", "val_kpa": 3.00, "direction": 3, "floor_label": "FLOOR_1", "x": 3.0, "y": 3.0},
    ])
    df_aloads.to_csv(f"{prefix}_area_loads.csv", index=False)

    # Frame Distributed Loads (Linijska opterećenja greda)
    df_floads = pd.DataFrame([
        {"frame_name": "B101", "load_pattern": "SDL", "val1_kn_m": 4.50, "val2_kn_m": 4.50, "floor_label": "FLOOR_1"},
    ])
    df_floads.to_csv(f"{prefix}_frame_loads.csv", index=False)

    # Base Restraints (Oslonci / Ležajevi)
    df_rest = pd.DataFrame([
        {"joint_name": "J1", "x": 0.0,  "y": 0.0,  "z": 0.0, "restraint_type": "Fixed",  "is_supported": True, "u1": True, "u2": True, "u3": True, "r1": True, "r2": True, "r3": True},
        {"joint_name": "J2", "x": 6.0,  "y": 0.0,  "z": 0.0, "restraint_type": "Fixed",  "is_supported": True, "u1": True, "u2": True, "u3": True, "r1": True, "r2": True, "r3": True},
        {"joint_name": "J3", "x": 12.0, "y": 0.0,  "z": 0.0, "restraint_type": "Pinned", "is_supported": True, "u1": True, "u2": True, "u3": True, "r1": False, "r2": False, "r3": False},
        {"joint_name": "J4", "x": 0.0,  "y": 12.0, "z": 0.0, "restraint_type": "Fixed",  "is_supported": True, "u1": True, "u2": True, "u3": True, "r1": True, "r2": True, "r3": True},
    ])
    df_rest.to_csv(f"{prefix}_restraints.csv", index=False)

    print(f"Created ETABS CSV files with prefix: {prefix}")

if __name__ == "__main__":
    create_dxf()
    create_etabs_csvs()
