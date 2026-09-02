"""
main.py — CLI entry point v2
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import Config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="etabs_dxf_checker",
        description="Cross-check ETABS v23 structural model against 2D DXF drawing.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    inp = p.add_argument_group("Inputs")
    inp.add_argument("--dxf", required=True, help="Path to the DXF drawing file.")
    inp.add_argument("--etabs-csv-prefix", default=None,
                     help="Load ETABS data from pre-exported CSVs (prefix, e.g. 'etabs'). "
                          "Expects <prefix>_columns.csv, _beams.csv, _walls.csv, etc.")
    inp.add_argument("--floor", default=None,
                     help="Filter DXF elements by floor label (layer name).")

    elt = p.add_argument_group("Element Types")
    elt.add_argument("--element-types", nargs="+",
                     choices=["columns","beams","braces","walls","slabs"],
                     default=None,
                     help="Element types to validate (default: all).")
    elt.add_argument("--no-hinges", action="store_true",
                     help="Skip plastic hinge extraction and reporting.")

    dxf = p.add_argument_group("DXF Parameters")
    dxf.add_argument("--scale", type=float, default=None,
                     help="DXF unit→metres scale (0.001=mm, 0.01=cm, 1.0=m).")
    dxf.add_argument("--offset-x", type=float, default=None)
    dxf.add_argument("--offset-y", type=float, default=None)

    val = p.add_argument_group("Validation Parameters")
    val.add_argument("--tolerance-frame", type=float, default=None,
                     help="XY tolerance for columns/beams (m).")
    val.add_argument("--tolerance-area", type=float, default=None,
                     help="XY tolerance for walls/slabs (m).")
    val.add_argument("--section-tol", type=float, default=None,
                     help="Section dimension tolerance (mm).")

    out = p.add_argument_group("Outputs")
    out.add_argument("--output", default="validation_report",
                     help="Base name for output files (no extension).")
    out.add_argument("--no-pdf",  action="store_true", help="Skip PDF generation.")
    out.add_argument("--no-html", action="store_true", help="Skip standalone HTML (PDF still needs it internally).")
    out.add_argument("--project-name", default=None,
                     help="Project title shown on the report cover page.")
    out.add_argument("--export-etabs-csvs", default=None,
                     help="(Optional) Export extracted ETABS data to CSVs with this prefix.")

    dbg = p.add_argument_group("Debug")
    dbg.add_argument("--dxf-only", action="store_true",
                     help="Parse DXF only (no ETABS, no validation).")
    dbg.add_argument("--plot", action="store_true",
                     help="Show matplotlib debug plot of DXF results.")
    dbg.add_argument("--verbose", "-v", action="store_true")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # --- Config -------------------------------------------------------
    cfg = Config()
    if args.element_types:     cfg.extract_elements      = args.element_types
    if args.no_hinges:         cfg.report_hinges          = False
    if args.scale is not None: cfg.dxf_unit_scale         = args.scale
    if args.tolerance_frame:   cfg.spatial_tolerance_frame = args.tolerance_frame
    if args.tolerance_area:    cfg.spatial_tolerance_area  = args.tolerance_area
    if args.section_tol:       cfg.section_tolerance_mm   = args.section_tol
    if args.project_name:      cfg.project_name           = args.project_name
    if args.no_pdf:            cfg.produce_pdf            = False
    if args.no_html:           cfg.produce_html           = False
    if args.offset_x is not None or args.offset_y is not None:
        cfg.dxf_origin_offset = (args.offset_x or 0.0, args.offset_y or 0.0)
    cfg.html_output = args.output + ".html"
    cfg.pdf_output  = args.output + ".pdf"

    dxf_path = Path(args.dxf)
    if not dxf_path.exists():
        logging.error("DXF file not found: %s", dxf_path)
        return 1

    # ==================== Phase 2: DXF ==================================
    logging.info("=" * 55)
    logging.info("Phase 2 — Parsing DXF: %s", dxf_path)
    logging.info("=" * 55)
    from phase2_dxf import parse_dxf, debug_plot
    df_dxf = parse_dxf(str(dxf_path), cfg)

    # Floor filter
    if args.floor and not df_dxf.empty and "floor_label" in df_dxf.columns:
        df_dxf = df_dxf[df_dxf["floor_label"] == args.floor].reset_index(drop=True)
        logging.info("After floor filter '%s': %d DXF elements", args.floor, len(df_dxf))

    if args.plot:
        debug_plot(str(dxf_path), df_dxf, cfg)

    if args.dxf_only:
        import pandas as pd
        print(df_dxf.to_string())
        df_dxf.to_csv(args.output + "_dxf_elements.csv", index=False)
        logging.info("DXF-only mode complete. Saved %s_dxf_elements.csv", args.output)
        return 0

    # ==================== Phase 1: ETABS ================================
    logging.info("=" * 55)
    logging.info("Phase 1 — Extracting ETABS data")
    logging.info("=" * 55)

    import pandas as pd
    if args.etabs_csv_prefix:
        logging.info("Loading ETABS from CSVs with prefix: %s", args.etabs_csv_prefix)
        from phase1_etabs import load_from_csvs
        etabs_data = load_from_csvs(args.etabs_csv_prefix)
    else:
        logging.info("Connecting to live ETABS v23 …")
        from phase1_etabs import extract_all, export_to_csvs
        etabs_data = extract_all(cfg)
        if args.export_etabs_csvs:
            export_to_csvs(etabs_data, args.export_etabs_csvs)

    for k, df in etabs_data.items():
        logging.info("  %-12s %d rows", k, len(df))

    # ==================== Phase 3: Validate =============================
    logging.info("=" * 55)
    logging.info("Phase 3 — Spatial validation")
    logging.info("=" * 55)
    from phase3_validation import validate, print_summary
    df_result = validate(etabs_data, df_dxf, cfg)
    print_summary(df_result)

    # ==================== Reports =======================================
    logging.info("=" * 55)
    logging.info("Generating reports …")
    logging.info("=" * 55)
    from report import generate_reports
    generate_reports(df_result, cfg)

    logging.info("Done ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
