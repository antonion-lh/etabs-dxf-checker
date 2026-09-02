"""
report.py
---------
Generate HTML and PDF validation reports — v2.

PDF strategy: generate polished HTML → convert with WeasyPrint.
Fallback chain: WeasyPrint → xhtml2pdf → save HTML only (with warning).

PDF structure:
  • Cover page   — project title, timestamp, tolerances, summary counts
  • Summary page — element-type breakdown table
  • Main table   — all elements, colour-coded by status
  • Hinge appendix — frames with plastic hinges (if any)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from phase3_validation import Status
from config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

STATUS_BG = {
    Status.MATCH:            "#d4edda",
    Status.SECTION_MISMATCH: "#fff3cd",
    Status.ETABS_ONLY:       "#f8d7da",
    Status.DXF_ONLY:         "#d1ecf1",
}
STATUS_ICON = {
    Status.MATCH:            "✅",
    Status.SECTION_MISMATCH: "⚠️",
    Status.ETABS_ONLY:       "❌",
    Status.DXF_ONLY:         "🔵",
}
STATUS_CARD_CLASS = {
    Status.MATCH:            "c-match",
    Status.SECTION_MISMATCH: "c-mismatch",
    Status.ETABS_ONLY:       "c-etabs",
    Status.DXF_ONLY:         "c-dxf",
}

ELEMENT_COLORS = {
    "column": "#495057",
    "beam":   "#0d6efd",
    "brace":  "#6f42c1",
    "wall":   "#198754",
    "slab":   "#fd7e14",
}

DISPLAY_COLS = [
    "element_type", "status",
    "etabs_name", "etabs_x", "etabs_y", "etabs_z",
    "etabs_section", "etabs_material", "etabs_shape",
    "etabs_w_mm", "etabs_h_mm", "etabs_d_mm",
    "dxf_dim_text", "dxf_material", "dxf_x", "dxf_y", "dxf_d1_mm", "dxf_d2_mm",
    "floor_label", "grid_ref",
    "has_hinges", "hinge_count", "hinge_details",
    "xy_dist_m", "notes",
]
DISPLAY_HEADERS = {
    "element_type":  "Type",
    "status":        "Status",
    "etabs_name":    "ETABS ID",
    "etabs_x":       "X (m)",
    "etabs_y":       "Y (m)",
    "etabs_z":       "Z (m)",
    "etabs_section": "Section",
    "etabs_material":"ETABS Mat",
    "etabs_shape":   "Shape",
    "etabs_w_mm":    "W (mm)",
    "etabs_h_mm":    "H (mm)",
    "etabs_d_mm":    "D (mm)",
    "dxf_dim_text":  "DXF Dim",
    "dxf_material":  "CAD Mat",
    "dxf_x":         "DXF X (m)",
    "dxf_y":         "DXF Y (m)",
    "dxf_d1_mm":     "DXF D1 (mm)",
    "dxf_d2_mm":     "DXF D2 (mm)",
    "floor_label":   "Floor",
    "grid_ref":      "Grid",
    "has_hinges":    "Hinges?",
    "hinge_count":   "# Hinges",
    "hinge_details": "Hinge Detail",
    "xy_dist_m":     "Dist (m)",
    "notes":         "Notes",
}


def _fmt(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, float):
        return f"{val:.3f}"
    return str(val)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Segoe UI',Arial,sans-serif; font-size:12px; color:#212529;
       background:#f8f9fa; padding:16px; }
h1 { font-size:1.4rem; margin-bottom:4px; }
h2 { font-size:1.1rem; margin:20px 0 8px; color:#495057; border-bottom:2px solid #dee2e6; padding-bottom:4px; }
.meta { color:#6c757d; font-size:11px; margin-bottom:16px; }
.hinge-badge { background:#6f42c1; color:#fff; border-radius:10px;
               padding:1px 7px; font-size:10px; margin-left:4px; }

/* ---- Summary cards ---- */
.cards { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
.card  { border-radius:8px; padding:12px 20px; min-width:130px; text-align:center;
         box-shadow:0 1px 3px rgba(0,0,0,.1); }
.card .num { font-size:1.8rem; font-weight:700; }
.card .lbl { font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:#495057; }
.c-match    { background:#d4edda; }
.c-mismatch { background:#fff3cd; }
.c-etabs    { background:#f8d7da; }
.c-dxf      { background:#d1ecf1; }

/* ---- Type breakdown ---- */
.type-grid { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px; }
.type-card { border-radius:6px; padding:8px 14px; font-size:11px;
             box-shadow:0 1px 2px rgba(0,0,0,.08); color:#fff; }
.type-card strong { font-size:1.2rem; display:block; }

/* ---- Filter bar ---- */
.filters { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
.filters select, #search { padding:4px 8px; border:1px solid #ced4da;
                            border-radius:4px; font-size:12px; }
#search { width:200px; }

/* ---- Table ---- */
.tbl-wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; background:#fff;
        box-shadow:0 1px 3px rgba(0,0,0,.08); border-radius:6px; overflow:hidden; }
thead th { background:#343a40; color:#fff; padding:7px 9px;
           text-align:left; font-size:11px; white-space:nowrap; }
tbody tr { border-bottom:1px solid #dee2e6; }
tbody tr:hover { filter:brightness(95%); }
td { padding:5px 9px; white-space:nowrap; font-size:11px; }
td.wide { white-space:normal; max-width:220px; word-wrap:break-word; }
.badge { display:inline-block; padding:2px 7px; border-radius:10px;
         font-size:10px; font-weight:600; }
.et-badge { display:inline-block; padding:1px 7px; border-radius:10px;
            font-size:10px; font-weight:600; color:#fff; }

/* ---- Print / PDF ---- */
@media print {
  .filters, #search { display:none !important; }
  table { font-size:9px; }
  thead th { font-size:9px; padding:4px 5px; }
  td { padding:3px 5px; }
  h2 { page-break-before: always; }
  .cards, .type-grid { page-break-inside: avoid; }
}
"""


def _header_row(cols) -> str:
    return "".join(f"<th>{DISPLAY_HEADERS.get(c, c)}</th>" for c in cols)


def _clean_status(status) -> Status:
    if isinstance(status, Status):
        return status
    s = str(status)
    if s.startswith("Status."):
        s = s[7:]
    return Status(s)


def _status_badge(status) -> str:
    try:
        st = _clean_status(status)
        return (f'<span class="badge" style="background:{STATUS_BG.get(st, "#f8f9fa")}">'
                f'{STATUS_ICON.get(st, "●")} {st.value.replace("_", " ")}</span>')
    except (ValueError, KeyError):
        return f'<span class="badge" style="background:#e0f2fe;color:#0369a1;font-weight:600;">🏢 {status}</span>'


def _element_badge(et: str) -> str:
    color = ELEMENT_COLORS.get(et, "#6c757d")
    return f'<span class="et-badge" style="background:{color}">{et}</span>'


def _data_rows(df: pd.DataFrame, cols: list[str]) -> str:
    rows = []
    for _, row in df.iterrows():
        raw_status = row.get("status", "")
        try:
            st = _clean_status(raw_status)
            status_str = st.value
            bg = STATUS_BG.get(st, "#ffffff")
        except (ValueError, KeyError):
            status_str = str(raw_status)
            bg = "#f0f9ff" if "PDF" in status_str else "#ffffff"

        cells = []
        for col in cols:
            val = row.get(col, "")
            if col == "status":
                td = f"<td>{_status_badge(status_str)}</td>"
            elif col == "element_type":
                td = f"<td>{_element_badge(str(val))}</td>"
            elif col == "notes":
                td = f'<td class="wide">{_fmt(val)}</td>'
            elif col == "hinge_details":
                td = f'<td class="wide">{_fmt(val)}</td>'
            elif col == "has_hinges":
                v = bool(val) if val not in (None, "") else False
                td = ('<td><span class="hinge-badge">🔴 YES</span></td>' if v
                      else "<td>—</td>")
            else:
                td = f"<td>{_fmt(val)}</td>"
            cells.append(td)

        hinge_flag = bool(row.get("has_hinges", False))
        hinge_attr = ' data-hinge="yes"' if hinge_flag else ''
        rows.append(
            f'<tr data-status="{status_str}" data-type="{row.get("element_type","")}"'
            f'{hinge_attr} style="background:{bg}">'
            + "".join(cells) + "</tr>"
        )
    return "\n".join(rows)


def _type_breakdown_html(df: pd.DataFrame) -> str:
    cards = []
    for et, grp in df.groupby("element_type"):
        color = ELEMENT_COLORS.get(str(et), "#6c757d")
        cards.append(
            f'<div class="type-card" style="background:{color}">'
            f'<strong>{len(grp)}</strong>{str(et).upper()}</div>'
        )
    return '<div class="type-grid">' + "".join(cards) + "</div>"


def _summary_cards_html(counts: dict) -> str:
    parts = []
    for st in Status:
        n = counts.get(st, 0)
        cls = STATUS_CARD_CLASS.get(st, "")
        icon = STATUS_ICON.get(st, "●")
        parts.append(
            f'<div class="card {cls}"><div class="num">{n}</div>'
            f'<div class="lbl">{icon} {st.value.replace("_"," ")}</div></div>'
        )
    if "Za provjeru s PDF-om" in counts:
        n = counts["Za provjeru s PDF-om"]
        parts.append(
            f'<div class="card" style="background:#e0f2fe;"><div class="num">{n}</div>'
            f'<div class="lbl">🏢 Modelirani elementi</div></div>'
        )
    return '<div class="cards">' + "".join(parts) + "</div>"


def _hinge_table_html(df: pd.DataFrame, cols: list[str]) -> str:
    if "has_hinges" not in df.columns:
        return "<p>No hinge data available.</p>"
    df_h = df[df["has_hinges"] == True]
    if df_h.empty:
        return "<p>No plastic hinges found in this model.</p>"
    hinge_cols = ["element_type","etabs_name","etabs_x","etabs_y","etabs_section",
                  "etabs_material","hinge_count","hinge_details","floor_label","grid_ref"]
    hinge_cols = [c for c in hinge_cols if c in df.columns]
    return (
        f'<table><thead><tr>{_header_row(hinge_cols)}</tr></thead>'
        f'<tbody>{_data_rows(df_h, hinge_cols)}</tbody></table>'
    )


def _sanity_alerts_html(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    rows = []
    for a in alerts:
        col = "#dc3545" if a.get("severity") == "ERROR" else "#b07d00"
        rows.append(
            f"<tr><td><strong>{a.get('category','')}</strong></td>"
            f"<td><span style='color:{col};font-weight:bold;'>{a.get('severity','')}</span></td>"
            f"<td><code>{a.get('element','')}</code></td>"
            f"<td>{a.get('issue','')}</td></tr>"
        )
    return (
        '<div style="background:#fff3cd;border:1px solid #ffeeba;border-radius:8px;padding:14px;margin:20px 0;">'
        '<h3 style="margin-top:0;color:#856404;font-size:14px;">⚠️ Model Sanity Warnings & Alerts</h3>'
        '<table style="margin-top:8px;">'
        '<thead><tr><th>Category</th><th>Severity</th><th>Element</th><th>Issue Description</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _materials_table_html(df_mats: pd.DataFrame) -> str:
    if df_mats.empty or "name" not in df_mats.columns:
        return "<p>No material audit data available.</p>"
    rows = []
    for _, r in df_mats.iterrows():
        rows.append(
            f"<tr><td><strong>{r.get('name','')}</strong></td>"
            f"<td>{r.get('type','')}</td>"
            f"<td>{r.get('E_gpa','—') if pd.notna(r.get('E_gpa')) else '—'}</td>"
            f"<td>{r.get('fc_mpa','—') if pd.notna(r.get('fc_mpa')) else '—'}</td>"
            f"<td>{r.get('fy_mpa','—') if pd.notna(r.get('fy_mpa')) else '—'}</td>"
            f"<td>{r.get('fu_mpa','—') if pd.notna(r.get('fu_mpa')) else '—'}</td></tr>"
        )
    return (
        '<table><thead><tr>'
        '<th>Material Name</th><th>Type</th><th>Modulus E (GPa)</th>'
        '<th>fc (MPa)</th><th>fy (MPa)</th><th>fu (MPa)</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _loads_table_html(df_pats: pd.DataFrame, df_result: pd.DataFrame) -> str:
    parts = []
    if not df_pats.empty and "name" in df_pats.columns:
        rows = []
        for _, r in df_pats.iterrows():
            name = str(r.get("name",""))
            ptype = str(r.get("type",""))
            sw = float(r.get("self_weight_mult",0.0))
            is_dead = ptype.lower() == "dead" or name.upper() == "DEAD"
            if is_dead:
                st = "<span style='color:#198754;font-weight:bold;'>OK (Dead 1.0)</span>" if abs(sw-1.0)<1e-4 else "<span style='color:#dc3545;font-weight:bold;'>ERROR (Dead != 1.0)</span>"
            else:
                st = "<span style='color:#198754;font-weight:bold;'>OK (0.0)</span>" if sw == 0.0 else "<span style='color:#dc3545;font-weight:bold;'>ERROR (Double Counted!)</span>"
            rows.append(
                f"<tr><td><strong>{name}</strong></td><td>{ptype}</td><td>{sw:.2f}</td><td>{st}</td></tr>"
            )
        parts.append(
            '<h3 style="font-size:13px;margin-top:14px;">Static Load Patterns & Self-Weight Multipliers</h3>'
            '<table><thead><tr><th>Pattern Name</th><th>Type</th><th>Self-Weight Mult</th><th>Audit Status</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    df_slabs = df_result[df_result["element_type"] == "slab"] if not df_result.empty else pd.DataFrame()
    if not df_slabs.empty and "etabs_load_g_kpa" in df_slabs.columns:
        s_rows = []
        for _, sr in df_slabs.iterrows():
            eg = sr.get("etabs_load_g_kpa")
            eq = sr.get("etabs_load_q_kpa")
            dg = sr.get("dxf_load_g_kpa")
            dq = sr.get("dxf_load_q_kpa")
            s_rows.append(
                f"<tr><td><strong>{sr.get('etabs_name','')}</strong></td>"
                f"<td>{sr.get('floor_label','')}</td>"
                f"<td>{f'{eg:.2f}' if pd.notna(eg) else '—'}</td>"
                f"<td>{f'{eq:.2f}' if pd.notna(eq) else '—'}</td>"
                f"<td>{f'{dg:.2f}' if pd.notna(dg) else '—'}</td>"
                f"<td>{f'{dq:.2f}' if pd.notna(dq) else '—'}</td>"
                f"<td>{sr.get('notes','')}</td></tr>"
            )
        parts.append(
            '<h3 style="font-size:13px;margin-top:14px;">Floor Slabs Applied Uniform Loads (kN/m²) vs CAD</h3>'
            '<table><thead><tr><th>Slab ID</th><th>Floor</th><th>ETABS Dead (g)</th><th>ETABS Live (q)</th><th>CAD Dead (g)</th><th>CAD Live (q)</th><th>Notes</th></tr></thead>'
            f'<tbody>{"".join(s_rows)}</tbody></table>'
        )

    return "".join(parts) if parts else "<p>No load audit data available.</p>"


def _restraints_table_html(df_rest: pd.DataFrame) -> str:
    if df_rest.empty or "joint_name" not in df_rest.columns:
        return "<p>No boundary condition data available.</p>"
    rows = []
    for _, r in df_rest.iterrows():
        rtype = str(r.get("restraint_type",""))
        col = "#dc3545" if rtype == "FREE" else ("#198754" if rtype in ("Fixed", "Pinned") else "#b07d00")
        rows.append(
            f"<tr><td><strong>{r.get('joint_name','')}</strong></td>"
            f"<td>({r.get('x',0):.2f}, {r.get('y',0):.2f}, {r.get('z',0):.2f})</td>"
            f"<td><span style='color:{col};font-weight:bold;'>{rtype}</span></td>"
            f"<td>{r.get('u1')}, {r.get('u2')}, {r.get('u3')}</td>"
            f"<td>{r.get('r1')}, {r.get('r2')}, {r.get('r3')}</td></tr>"
        )
    return (
        '<table><thead><tr><th>Joint ID</th><th>Location (X, Y, Z)</th><th>Support Type</th><th>Translations (U1, U2, U3)</th><th>Rotations (R1, R2, R3)</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{project_name} — Validation Report</title>
<style>{css}</style>
</head>
<body>

<!-- ===== COVER PAGE ===== -->
<div style="min-height:80vh;display:flex;flex-direction:column;justify-content:center;padding:40px 0;">
  <h1 style="font-size:2rem;margin-bottom:8px;">⚙️ {project_name}</h1>
  <h1 style="font-size:1.4rem;color:#6c757d;font-weight:400;margin-bottom:30px;">
    Structural Model Validation Report</h1>
  <p class="meta">Generated: <strong>{generated_at}</strong></p>
  <p class="meta">Spatial tolerance (frames): <strong>±{tol_frame} m</strong> &nbsp;|&nbsp;
                  Spatial tolerance (areas): <strong>±{tol_area} m</strong></p>
  <p class="meta">Section tolerance: <strong>±{tol_sec} mm</strong></p>
  <hr style="margin:24px 0;"/>
  {summary_cards}
</div>

{sanity_alerts}

<!-- ===== SUMMARY BY TYPE ===== -->
<h2>Elements by Type</h2>
{type_breakdown}

<!-- ===== MAIN TABLE ===== -->
<h2>1. Geometry & Cross-Sections Cross-Check</h2>
<div class="filters">
  <select id="statusFilter" onchange="applyFilters()">
    <option value="">All statuses</option>
    <option value="MATCH">✅ Match</option>
    <option value="SECTION_MISMATCH">⚠️ Section Mismatch</option>
    <option value="ETABS_ONLY">❌ ETABS Only</option>
    <option value="DXF_ONLY">🔵 DXF Only</option>
  </select>
  <select id="typeFilter" onchange="applyFilters()">
    <option value="">All types</option>
    <option value="column">Column</option>
    <option value="beam">Beam</option>
    <option value="wall">Wall</option>
    <option value="slab">Slab</option>
    <option value="brace">Brace</option>
  </select>
  <select id="hingeFilter" onchange="applyFilters()">
    <option value="">All</option>
    <option value="yes">With hinges only</option>
  </select>
  <input id="search" type="text" placeholder="Search ID / section / grid…" oninput="applyFilters()"/>
</div>
<div class="tbl-wrap">
<table id="mainTable">
  <thead><tr>{header_row}</tr></thead>
  <tbody id="tableBody">{data_rows}</tbody>
</table>
</div>

<!-- ===== MATERIALS AUDIT ===== -->
<h2>2. Materials Specification Audit (Materijali)</h2>
{materials_table}

<!-- ===== LOADS AUDIT ===== -->
<h2>3. Load Patterns & Equilibrium Audit (Opterećenja)</h2>
{loads_table}

<!-- ===== SUPPORTS AUDIT ===== -->
<h2>4. Base Boundary Conditions & Supports (Oslonci)</h2>
{restraints_table}

<!-- ===== HINGE APPENDIX ===== -->
<h2>5. Appendix — Plastic Hinges</h2>
{hinge_table}

<script>
function applyFilters() {{
  var sf = document.getElementById('statusFilter').value.toLowerCase();
  var tf = document.getElementById('typeFilter').value.toLowerCase();
  var hf = document.getElementById('hingeFilter').value.toLowerCase();
  var tx = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#tableBody tr').forEach(function(tr) {{
    var s = (tr.dataset.status || '').toLowerCase();
    var t = (tr.dataset.type   || '').toLowerCase();
    var h = (tr.dataset.hinge  || '').toLowerCase();
    var c = tr.textContent.toLowerCase();
    var ok = (sf===''||s===sf) && (tf===''||t===tf) &&
             (hf===''||hf==='yes'&&h==='yes') &&
             (tx===''||c.includes(tx));
    tr.style.display = ok ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""


def generate_html(
    df_result: pd.DataFrame,
    output_path: str,
    cfg: Config = DEFAULT_CONFIG,
) -> str:
    """Write HTML report and return the HTML string (for PDF conversion)."""
    counts = df_result["status"].value_counts() if not df_result.empty else {}
    cols   = [c for c in DISPLAY_COLS if c in df_result.columns]

    html = _HTML_TEMPLATE.format(
        project_name     = cfg.project_name,
        css              = _CSS,
        generated_at     = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tol_frame        = cfg.spatial_tolerance_frame,
        tol_area         = cfg.spatial_tolerance_area,
        tol_sec          = cfg.section_tolerance_mm,
        summary_cards    = _summary_cards_html(counts),
        sanity_alerts    = _sanity_alerts_html(df_result.attrs.get("sanity_alerts", [])),
        type_breakdown   = _type_breakdown_html(df_result) if not df_result.empty else "",
        header_row       = _header_row(cols),
        data_rows        = _data_rows(df_result, cols) if not df_result.empty else "",
        materials_table  = _materials_table_html(pd.DataFrame(df_result.attrs.get("materials", []))) if cfg.audit_materials else "",
        loads_table      = _loads_table_html(pd.DataFrame(df_result.attrs.get("load_patterns", [])), df_result) if cfg.audit_loads else "",
        restraints_table = _restraints_table_html(pd.DataFrame(df_result.attrs.get("restraints", []))) if cfg.audit_restraints else "",
        hinge_table      = _hinge_table_html(df_result, cols),
    )
    Path(output_path).write_text(html, encoding="utf-8")
    log.info("HTML report written: %s", output_path)
    return html


# ---------------------------------------------------------------------------
# PDF generation (ReportLab native -> WeasyPrint -> xhtml2pdf fallback)
# ---------------------------------------------------------------------------

def _generate_pdf_reportlab(df: pd.DataFrame, output_path: str, cfg: Config) -> bool:
    """Generate professional landscape PDF report using ReportLab directly."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
    except ImportError:
        return False

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Heading1"],
        fontSize=18, leading=22, textColor=colors.HexColor("#212529")
    )
    sub_style = ParagraphStyle(
        "DocSub", parent=styles["Normal"],
        fontSize=9, leading=13, textColor=colors.HexColor("#6c757d")
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"],
        fontSize=8, leading=10
    )
    cell_bold = ParagraphStyle(
        "CellBold", parent=styles["Normal"],
        fontSize=8, leading=10, fontName="Helvetica-Bold"
    )

    story = []

    # Title & Metadata
    story.append(Paragraph(f"<b>ETABS v23 ↔ DXF Structural Validation Report</b>", title_style))
    story.append(Paragraph(
        f"Project: <b>{cfg.project_name}</b> | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Frame Tol: ±{cfg.spatial_tolerance_frame}m | Area Tol: ±{cfg.spatial_tolerance_area}m | Sec Tol: ±{cfg.section_tolerance_mm}mm",
        sub_style
    ))
    story.append(Spacer(1, 5*mm))

    # Summary Statistics Cards
    counts = df["status"].value_counts() if not df.empty else {}
    sum_data = [
        [
            Paragraph("<b>MATCH</b>", cell_bold),
            Paragraph("<b>SECTION MISMATCH</b>", cell_bold),
            Paragraph("<b>ETABS ONLY</b>", cell_bold),
            Paragraph("<b>DXF ONLY</b>", cell_bold),
            Paragraph("<b>TOTAL</b>", cell_bold),
        ],
        [
            Paragraph(f"<font size=13 color='#198754'><b>{counts.get(Status.MATCH, 0)}</b></font>", cell_style),
            Paragraph(f"<font size=13 color='#b07d00'><b>{counts.get(Status.SECTION_MISMATCH, 0)}</b></font>", cell_style),
            Paragraph(f"<font size=13 color='#dc3545'><b>{counts.get(Status.ETABS_ONLY, 0)}</b></font>", cell_style),
            Paragraph(f"<font size=13 color='#0d6efd'><b>{counts.get(Status.DXF_ONLY, 0)}</b></font>", cell_style),
            Paragraph(f"<font size=13><b>{len(df)}</b></font>", cell_style),
        ]
    ]
    t_sum = Table(sum_data, colWidths=[55*mm, 55*mm, 55*mm, 55*mm, 55*mm])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e9ecef")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#ced4da")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_sum)

    # --- Sanity Alerts Banner ---
    alerts = df.attrs.get("sanity_alerts", [])
    if alerts:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("<b>⚠️ Model Sanity Warnings & Alerts:</b>", cell_bold))
        alert_rows = [[
            Paragraph("<b>Category</b>", cell_bold),
            Paragraph("<b>Severity</b>", cell_bold),
            Paragraph("<b>Element</b>", cell_bold),
            Paragraph("<b>Detected Issue</b>", cell_bold)
        ]]
        for a in alerts:
            sev_col = "#dc3545" if a.get("severity") == "ERROR" else "#b07d00"
            alert_rows.append([
                Paragraph(a.get("category", ""), cell_style),
                Paragraph(f"<font color='{sev_col}'><b>{a.get('severity','')}</b></font>", cell_style),
                Paragraph(a.get("element", ""), cell_style),
                Paragraph(a.get("issue", ""), cell_style),
            ])
        t_al = Table(alert_rows, colWidths=[35*mm, 25*mm, 35*mm, 180*mm])
        t_al.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#fff3cd")),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#ced4da")),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(t_al)

    story.append(Spacer(1, 5*mm))

    # --- Section 1: Geometry & Cross-Sections Matrix ---
    story.append(Paragraph("<b>1. Geometry & Cross-Sections Cross-Check Matrix</b>", cell_bold))
    story.append(Spacer(1, 2*mm))

    headers = [
        "Type", "Status", "ETABS ID", "ETABS Loc", "ETABS Section",
        "DXF Dim", "DXF Loc", "Grid", "Material", "Dist(m)", "Discrepancy Notes"
    ]
    col_widths = [18*mm, 28*mm, 22*mm, 26*mm, 32*mm, 22*mm, 24*mm, 15*mm, 24*mm, 15*mm, 49*mm]

    STATUS_BG_COLOR = {
        Status.MATCH: colors.HexColor("#d4edda"),
        Status.SECTION_MISMATCH: colors.HexColor("#fff3cd"),
        Status.ETABS_ONLY: colors.HexColor("#f8d7da"),
        Status.DXF_ONLY: colors.HexColor("#d1ecf1"),
        "Za provjeru s PDF-om": colors.HexColor("#e0f2fe"),
    }

    table_data = [[Paragraph(f"<font color='white'><b>{h}</b></font>", cell_bold) for h in headers]]
    row_bg_commands = []

    for idx, row in df.iterrows():
        st_val = row.get("status")
        st_str = str(st_val.value if isinstance(st_val, Status) else st_val)
        et = str(row.get("element_type", "")).upper()
        name = str(row.get("etabs_name", "") or "—")

        ex, ey = row.get("etabs_x"), row.get("etabs_y")
        eloc = f"({ex:.2f}, {ey:.2f})" if pd.notna(ex) and pd.notna(ey) else "—"

        sec = str(row.get("etabs_section", "") or "—")
        ew, eh = row.get("etabs_w_mm"), row.get("etabs_h_mm")
        if pd.notna(ew) and pd.notna(eh):
            sec += f"<br/><font size=7 color='#555'>({ew:.0f}x{eh:.0f}mm)</font>"

        ddim = str(row.get("dxf_dim_text", "") or "—")
        dx, dy = row.get("dxf_x"), row.get("dxf_y")
        dloc = f"({dx:.2f}, {dy:.2f})" if pd.notna(dx) and pd.notna(dy) else "—"

        grid = str(row.get("grid_ref", "") or "—")
        mat = str(row.get("etabs_material", "") or row.get("dxf_material", "") or "—")
        dist = f"{row.get('xy_dist_m'):.3f}" if pd.notna(row.get("xy_dist_m")) else "—"
        notes = str(row.get("notes", "") or "")

        row_cells = [
            Paragraph(et, cell_style),
            Paragraph(st_str, cell_bold),
            Paragraph(name, cell_style),
            Paragraph(eloc, cell_style),
            Paragraph(sec, cell_style),
            Paragraph(ddim, cell_style),
            Paragraph(dloc, cell_style),
            Paragraph(grid, cell_style),
            Paragraph(mat, cell_style),
            Paragraph(dist, cell_style),
            Paragraph(notes, cell_style),
        ]
        table_data.append(row_cells)

        row_idx = len(table_data) - 1
        try:
            st_enum = Status(st_str)
            bg = STATUS_BG_COLOR.get(st_enum, colors.white)
        except Exception:
            bg = colors.white
        row_bg_commands.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

    t_main = Table(table_data, colWidths=col_widths, repeatRows=1)
    base_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#343a40")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#adb5bd")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 2.5),
        ('RIGHTPADDING', (0,0), (-1,-1), 2.5),
    ]
    t_main.setStyle(TableStyle(base_style + row_bg_commands))
    story.append(t_main)

    # --- Section 2: Materials Verification Audit ---
    df_mats = pd.DataFrame(df.attrs.get("materials", []))
    if cfg.audit_materials and not df_mats.empty:
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("<b>2. Materials Specification Audit (Materijali)</b>", cell_bold))
        story.append(Spacer(1, 2*mm))
        mat_rows = [[
            Paragraph("<b>Material Name</b>", cell_bold),
            Paragraph("<b>Type</b>", cell_bold),
            Paragraph("<b>Modulus E (GPa)</b>", cell_bold),
            Paragraph("<b>fc (MPa)</b>", cell_bold),
            Paragraph("<b>fy (MPa)</b>", cell_bold),
            Paragraph("<b>fu (MPa)</b>", cell_bold),
        ]]
        for _, mr in df_mats.iterrows():
            mat_rows.append([
                Paragraph(str(mr.get("name", "")), cell_style),
                Paragraph(str(mr.get("type", "")), cell_style),
                Paragraph(f"{mr.get('E_gpa'):.1f}" if pd.notna(mr.get("E_gpa")) else "—", cell_style),
                Paragraph(f"{mr.get('fc_mpa'):.1f}" if pd.notna(mr.get("fc_mpa")) else "—", cell_style),
                Paragraph(f"{mr.get('fy_mpa'):.1f}" if pd.notna(mr.get("fy_mpa")) else "—", cell_style),
                Paragraph(f"{mr.get('fu_mpa'):.1f}" if pd.notna(mr.get("fu_mpa")) else "—", cell_style),
            ])
        t_mat = Table(mat_rows, colWidths=[65*mm, 45*mm, 45*mm, 40*mm, 40*mm, 40*mm])
        t_mat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#495057")),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#adb5bd")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ]))
        story.append(t_mat)

    # --- Section 3: Loads & Equilibrium Audit (Opterećenja) ---
    df_pats = pd.DataFrame(df.attrs.get("load_patterns", []))
    if cfg.audit_loads and not df_pats.empty:
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("<b>3. Load Patterns & Equilibrium Audit (Opterećenja)</b>", cell_bold))
        story.append(Spacer(1, 2*mm))
        pat_rows = [[
            Paragraph("<b>Pattern Name</b>", cell_bold),
            Paragraph("<b>Type</b>", cell_bold),
            Paragraph("<b>Self-Weight Mult</b>", cell_bold),
            Paragraph("<b>Status / Audit Check</b>", cell_bold),
        ]]
        for _, pr in df_pats.iterrows():
            pname = str(pr.get("name", ""))
            ptype = str(pr.get("type", ""))
            sw = float(pr.get("self_weight_mult", 0.0))
            is_dead = ptype.lower() == "dead" or pname.upper() == "DEAD"
            if is_dead:
                st_pat = "<font color='#198754'><b>OK (Dead 1.0)</b></font>" if abs(sw-1.0) < 1e-4 else "<font color='#dc3545'><b>ERROR (Dead != 1.0)</b></font>"
            else:
                st_pat = "<font color='#198754'><b>OK (0.0)</b></font>" if sw == 0.0 else "<font color='#dc3545'><b>ERROR (Double Counted!)</b></font>"
            pat_rows.append([
                Paragraph(pname, cell_style),
                Paragraph(ptype, cell_style),
                Paragraph(f"{sw:.2f}", cell_style),
                Paragraph(st_pat, cell_style),
            ])
        t_pat = Table(pat_rows, colWidths=[70*mm, 60*mm, 65*mm, 80*mm])
        t_pat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#495057")),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#adb5bd")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ]))
        story.append(t_pat)

    # --- Section 4: Base Restraints (Oslonci) ---
    df_rest = pd.DataFrame(df.attrs.get("restraints", []))
    if cfg.audit_restraints and not df_rest.empty:
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("<b>4. Base Boundary Conditions & Supports (Oslonci / Ležajevi)</b>", cell_bold))
        story.append(Spacer(1, 2*mm))
        res_rows = [[
            Paragraph("<b>Joint ID</b>", cell_bold),
            Paragraph("<b>Location (X, Y, Z)</b>", cell_bold),
            Paragraph("<b>Support Type</b>", cell_bold),
            Paragraph("<b>Translations (U1, U2, U3)</b>", cell_bold),
            Paragraph("<b>Rotations (R1, R2, R3)</b>", cell_bold),
        ]]
        for _, rr in df_rest.iterrows():
            rtype = str(rr.get("restraint_type", ""))
            rcolor = "#dc3545" if rtype == "FREE" else ("#198754" if rtype in ("Fixed", "Pinned") else "#b07d00")
            res_rows.append([
                Paragraph(str(rr.get("joint_name", "")), cell_style),
                Paragraph(f"({rr.get('x',0):.2f}, {rr.get('y',0):.2f}, {rr.get('z',0):.2f})", cell_style),
                Paragraph(f"<font color='{rcolor}'><b>{rtype}</b></font>", cell_style),
                Paragraph(f"{rr.get('u1')}, {rr.get('u2')}, {rr.get('u3')}", cell_style),
                Paragraph(f"{rr.get('r1')}, {rr.get('r2')}, {rr.get('r3')}", cell_style),
            ])
        t_res = Table(res_rows, colWidths=[55*mm, 65*mm, 55*mm, 50*mm, 50*mm])
        t_res.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#495057")),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#adb5bd")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ]))
        story.append(t_res)

    doc.build(story)
    log.info("PDF report written (ReportLab native): %s", output_path)
    return True


def generate_pdf(
    content_or_df: Union[str, pd.DataFrame],
    output_path: str,
    df_result: Optional[pd.DataFrame] = None,
    cfg: Config = DEFAULT_CONFIG,
) -> bool:
    """
    Convert validation results to PDF.
    Tries ReportLab native first; falls back to WeasyPrint and xhtml2pdf.
    Supports calling as generate_pdf(df, path, cfg) or generate_pdf(html, path, df, cfg).
    """
    if isinstance(content_or_df, pd.DataFrame):
        df_target = content_or_df
        html_content = ""
        if isinstance(df_result, Config):
            cfg = df_result
    else:
        html_content = str(content_or_df)
        df_target = df_result

    # --- 1. Try ReportLab native (best reliability & cross-platform) ---
    if df_target is not None and not df_target.empty:
        try:
            if _generate_pdf_reportlab(df_target, output_path, cfg):
                return True
        except Exception as e:
            log.warning("ReportLab generation failed (%s) — trying WeasyPrint/xhtml2pdf …", e)

    # --- 2. Try WeasyPrint ------------------------------------------------
    try:
        import weasyprint  # type: ignore
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        log.info("PDF written (WeasyPrint): %s", output_path)
        return True
    except (ImportError, OSError):
        pass
    except Exception as e:
        log.warning("WeasyPrint failed (%s) — trying xhtml2pdf …", e)

    # --- 3. Try xhtml2pdf -------------------------------------------------
    try:
        from xhtml2pdf import pisa  # type: ignore
        with open(output_path, "wb") as f:
            result = pisa.CreatePDF(html_content.encode("utf-8"), dest=f)
        if not result.err:
            log.info("PDF written (xhtml2pdf): %s", output_path)
            return True
    except Exception as e:
        log.warning("xhtml2pdf failed: %s", e)

    log.error("PDF generation failed. The HTML report is still usable: %s",
              output_path.replace(".pdf", ".html"))
    return False


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def generate_reports(
    df_result:  pd.DataFrame,
    cfg: Config = DEFAULT_CONFIG,
    html_path:  Optional[str] = None,
    pdf_path:   Optional[str] = None,
) -> None:
    """Generate HTML and/or PDF reports according to config."""
    h_path = html_path or cfg.html_output
    p_path = pdf_path  or cfg.pdf_output

    html_str = generate_html(df_result, h_path, cfg)

    if cfg.produce_pdf:
        generate_pdf(html_str, p_path, df_result=df_result, cfg=cfg)
