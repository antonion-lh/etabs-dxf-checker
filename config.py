"""
config.py
---------
Central configuration for the ETABS ↔ DXF validation script v2.
All tunable parameters live here — no magic numbers elsewhere.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Config:
    # ------------------------------------------------------------------ #
    # Element types to extract and validate
    # ------------------------------------------------------------------ #
    # Any subset of: "columns", "beams", "braces", "walls", "slabs"
    extract_elements: List[str] = field(
        default_factory=lambda: ["columns", "beams", "walls", "slabs"]
    )

    # ------------------------------------------------------------------ #
    # Spatial matching tolerances (meters)
    # ------------------------------------------------------------------ #
    spatial_tolerance_frame: float = 0.15   # columns, beams, braces
    spatial_tolerance_area:  float = 0.30   # walls, slabs (larger elements)
    spatial_tolerance: float | None = None  # optional backwards-compatibility alias

    def __post_init__(self):
        if self.spatial_tolerance is not None:
            self.spatial_tolerance_frame = self.spatial_tolerance
            self.spatial_tolerance_area  = self.spatial_tolerance * 2.0
        else:
            self.spatial_tolerance = self.spatial_tolerance_frame

    def __hash__(self) -> int:
        return hash((
            self.spatial_tolerance_frame,
            self.spatial_tolerance_area,
            self.section_tolerance_mm,
            self.dxf_unit_scale,
            tuple(sorted(self.extract_elements)),
            self.audit_materials,
            self.audit_loads,
            self.audit_restraints,
            self.report_hinges,
        ))

    # ------------------------------------------------------------------ #
    # Section dimension matching
    # ------------------------------------------------------------------ #
    section_tolerance_mm: float = 5.0

    # ------------------------------------------------------------------ #
    # DXF parsing
    # ------------------------------------------------------------------ #
    # Conversion factor: DXF units → meters
    # 0.001 = mm, 0.01 = cm, 1.0 = m
    dxf_unit_scale: float = 0.01

    # Optional XY offset in meters (after scaling) to align DXF with ETABS origin
    dxf_origin_offset: Tuple[float, float] = (0.0, 0.0)

    # Regex patterns for floor layer auto-detection (matched against layer names)
    floor_layer_patterns: List[str] = field(
        default_factory=lambda: [
            r"FLOOR[_\s\-]?\d+",
            r"F\d+[_\s]",
            r"LEVEL[_\s\-]?\d+",
            r".*_PLAN$",
            r"STOREY[_\s\-]?\d+",
            r"KAT[_\s\-]?\d+",    # Croatian: "kat" = floor
        ]
    )

    # Minimum area (m²) for a closed polyline to be treated as a slab-sized region
    # vs. a column/wall outline.  Tuned after scaling.
    slab_min_area_m2: float = 4.0

    # Aspect ratio threshold to distinguish beams (long/thin) from columns (squarish)
    # Bounding-box W/H ratio: if > beam_aspect_ratio_threshold → likely a beam outline
    beam_aspect_ratio_threshold: float = 3.0

    # Wall detection: min polyline length / width ratio for a thin rectangle
    wall_aspect_ratio_threshold: float = 4.0

    # ------------------------------------------------------------------ #
    # Dimension text regex patterns (per element type)
    # ------------------------------------------------------------------ #
    # Rectangular: "30x50", "300x500", "30/50", "30×50"
    rect_section_regex: str = r"(\d{2,3})\s*[xX×/]\s*(\d{2,3})"

    # Circular: "d=40", "D=400", "Ø40", "φ40"
    circ_section_regex: str = r"(?:d|D|Ø|ø|φ)\s*[=]?\s*(\d{2,3})"

    # Thickness (walls/slabs): "t=20", "d=25", "h=20", "20cm"
    thickness_regex: str = r"(?:t|d|h|e)\s*[=]\s*(\d{1,3})|(\d{1,3})\s*cm"

    # ------------------------------------------------------------------ #
    # Grid reconstruction
    # ------------------------------------------------------------------ #
    min_grid_line_length:    float = 1000.0
    grid_circle_search_radius: float = 200.0
    max_grid_label_distance: float  = 2000.0

    # Max distance from dimension TEXT to nearest closed polyline centroid (DXF units)
    max_text_to_poly_distance: float = 500.0

    # ------------------------------------------------------------------ #
    # ETABS OAPI
    # ------------------------------------------------------------------ #
    # eUnits: 6 = kN-m-C.  Script normalises all outputs to metres.
    etabs_units: int = 6

    # Design orientation values in ETABS OAPI eFrameDesignOrientation enum
    ORIENT_COLUMN: int = 1
    ORIENT_BEAM:   int = 2
    ORIENT_BRACE:  int = 3

    # Verticality fallback for orientation == 0 (Program Determined)
    column_verticality_threshold: float = 0.85

    # ------------------------------------------------------------------ #
    # Plastic hinges, Materials, Loads, & Boundary Conditions Audits
    # ------------------------------------------------------------------ #
    report_hinges:    bool = True
    audit_materials:  bool = True
    audit_loads:      bool = True
    audit_restraints: bool = True

    # Material regex patterns
    concrete_grade_regex: str = r"\b(?:C\s*\d{2}/\d{2}|MB\s*\d{2,3})\b"
    steel_grade_regex:    str = r"\b(?:S\s*\d{3}|B\s*500\s*[ABab]|FeB\s*\d{3})\b"

    # Load regex patterns: "g=2.0 kN/m²", "gk = 1.75", "q=3.0", "qk=3.0 kN/m2"
    area_load_regex:      str = r"(?:g|gk|Δg|q|qk|p)\s*=\s*(\d+(?:\.\d+)?)\s*(?:kN/m[2²])?"
    frame_load_regex:     str = r"(?:q|p|g)\s*=\s*(\d+(?:\.\d+)?)\s*(?:kN/m)\b"
    load_tolerance_kpa:   float = 0.05   # 0.05 kN/m² load match tolerance

    # ------------------------------------------------------------------ #
    # Report
    # ------------------------------------------------------------------ #
    produce_pdf:  bool = True
    produce_html: bool = True   # kept as intermediate for PDF conversion

    html_output:  str = "validation_report.html"
    pdf_output:   str = "validation_report.pdf"

    # PDF page title / project name shown on cover page
    project_name: str = "Structural Model Validation"


DEFAULT_CONFIG = Config()
