# ETABS v23 ↔ DXF Structural Validation Tool (v2)

Automated cross-checking of structural ETABS v23 models against unstructured multi-floor 2D DXF drawings and engineering documentation.

Supports full audit of:
- 📐 **Geometrija (Geometry)**: Column grids, beam spans, wall alignments, slab elevations, coordinates.
- 📏 **Poprečni presjeci (Cross-sections)**: Checks true dimensions directly from ETABS section definitions (rectangular, circular, box/tube, pipe, I-beam, channel, T-beam, slab/wall thicknesses).
- 🧪 **Materijali (Materials)**: Cross-checks concrete classes (C25/30, C30/37, etc.), rebar & structural steel grades (B500B, S355), Elastic Modulus $E$, compressive strength $f_{ck}$, and yield strength $f_y$.
- ⚖️ **Opterećenja (Loads & Equilibrium)**: Self-weight multiplier sanity check (verifies Dead=1.0 and other cases=0.0 to prevent double-counting), applied slab uniform area loads ($kN/m^2$) against CAD annotations, distributed line loads on beams ($kN/m$), and detection of un-loaded floor slabs.
- 🧱 **Oslonci / Ležajevi (Supports & Boundary Conditions)**: Verifies ground-level boundary conditions (Fixed, Pinned, Roller) and flags unconstrained / floating base joints (`FREE`).
- 🔴 **Nelinearnosti (Plastic Hinges)**: Extracts and tabulates nonlinear hinge assignments (P-M2-M3, M3, FEMA-356, etc.).
- 🖥️ **Desktop GUI & 1-Click Launcher**: Built-in graphical desktop interface (`Launch_App.bat`) with zero-install dependencies.
- 📑 **Landscape PDF & Interactive HTML Reports**: High-quality landscape A4 engineering reports for structural review.

---

## Key Features

1. **All Structural Types Supported**:
   - **Columns (Stupovi)**: Vertical frame elements (`eFrameDesignOrientation = 1` or verticality fallback)
   - **Beams (Grede)**: Horizontal frame elements (`eFrameDesignOrientation = 2`)
   - **Walls (Zidovi)**: Vertical area elements (`eAreaDesignOrientation = 1` or normal vector $|n_z| < 0.5$)
   - **Slabs (Ploče)**: Horizontal area elements (`eAreaDesignOrientation = 2` or normal vector $|n_z| \ge 0.5$)
   - **Braces (Dijagonale)**: Diagonal frame elements

2. **Definition-Based Section Dimensions**:
   - Cross-section dimensions are read directly from ETABS property definitions (`PropFrame.GetRectangle`, `GetCircle`, `GetTube`, `GetPipe`, `GetISection`, `GetChannel`, `GetTSection` and `PropArea.GetShell_1`).
   - Does NOT rely on dimension numbers in section names (handles arbitrary names like `COL_TYPE_A`, `W_CORE`, etc.).

3. **Materials Specification Audit**:
   - Extracts material definitions from ETABS OAPI (`PropMaterial.GetMaterial`, `GetMPIsotropic`, `GetOConcrete_1`, `GetOSteel_1`).
   - Parses drawing general notes and element tags for matching steel/concrete classes.

4. **Loads & Equilibrium Verification**:
   - Audits load patterns and self-weight multipliers.
   - Cross-checks applied surface loads on slabs ($g_k, q_k$) against design drawings.
   - Detects floor slabs with zero surface load assignments.

5. **Base Restraints Audit**:
   - Inspects ground-level joint boundary conditions (`PointObj.GetRestraint`) across all 6 DOFs ($U_1, U_2, U_3, R_1, R_2, R_3$).
   - Flags unsupported columns (critical error).

6. **Nonlinear Plastic Hinges**:
   - Extracts all hinge assignments per frame (`GetHingeAssigns`), including relative distance along the member and degree of freedom (e.g. M3, P-M2-M3).
   - Reports hinge counts and definitions in an appendix of the report.

---

## Installation

```bash
# Set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# On Windows (for live ETABS OAPI):
pip install comtypes
```

---

## Quick Start

### 1. Full Live Run (Windows + ETABS v23 Open)
```bash
python main.py --dxf path/to/drawings.dxf
# Produces: validation_report.html and validation_report.pdf
```

### 2. Offline Run (from Pre-exported ETABS CSVs)
```bash
# Step 1: On Windows with ETABS open, export model data:
python phase1_etabs.py
# → Writes etabs_columns.csv, etabs_beams.csv, etabs_walls.csv, etabs_slabs.csv, etabs_hinges.csv

# Step 2: Validate against DXF on any machine (macOS / Linux / Windows):
python main.py --dxf drawings.dxf --etabs-csv-prefix etabs
```

### 3. Filter by Specific Floor or Element Types
```bash
# Filter only columns and walls on 2nd floor:
python main.py --dxf drawings.dxf --floor FLOOR_2 --element-types columns walls
```

### 4. Debug DXF Parsing Only
```bash
python main.py --dxf drawings.dxf --dxf-only --plot
```

---

## Configuration (`config.py`)

All tolerances and heuristics are centrally managed in `config.py` and can be overridden via CLI flags:

| Parameter | Default | CLI Flag | Description |
|-----------|---------|----------|-------------|
| `dxf_unit_scale` | `0.01` | `--scale` | DXF units to meters (0.001=mm, 0.01=cm, 1.0=m) |
| `spatial_tolerance_frame` | `0.15` m | `--tolerance-frame` | Coordinate matching tolerance for columns/beams |
| `spatial_tolerance_area` | `0.30` m | `--tolerance-area` | Coordinate matching tolerance for walls/slabs |
| `section_tolerance_mm` | `5.0` mm | `--section-tol` | Max allowed difference in cross-section dimensions |
| `report_hinges` | `True` | `--no-hinges` | Capture and report plastic hinges |
| `produce_pdf` | `True` | `--no-pdf` | Generate PDF report |

---

## Report Statuses

- 🟢 **`MATCH`**: Element coordinates and cross-section dimensions align within tolerance.
- 🟡 **`SECTION_MISMATCH`**: Element is present at the location, but dimensions differ (e.g. 300×500 vs 300×600 mm).
- 🔴 **`ETABS_ONLY`**: Element exists in ETABS but no corresponding contour was found in DXF.
- 🔵 **`DXF_ONLY`**: Element drawn in DXF but missing in the ETABS structural model.

---

## Running Tests

```bash
pytest tests/ -v
```
All 45 automated unit tests verify geometric centroids, multi-floor layer recognition, dimension regex variations, multi-type spatial matching, and PDF/HTML report generation.
