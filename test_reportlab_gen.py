import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

def build_pdf_report(df, output_path="sample_report.pdf", project_name="Structural Model Validation"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#212529")
    )
    sub_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#6c757d")
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold"
    )

    story = []

    # Title
    story.append(Paragraph(f"<b>ETABS v23 ↔ DXF Structural Validation Report</b>", title_style))
    story.append(Paragraph(f"Project: {project_name} | Generated automatically", sub_style))
    story.append(Spacer(1, 6*mm))

    # Summary Statistics Cards / Table
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
            Paragraph(f"<font size=14 color='#198754'><b>{counts.get('MATCH', 0)}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#b07d00'><b>{counts.get('SECTION_MISMATCH', 0)}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#dc3545'><b>{counts.get('ETABS_ONLY', 0)}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#0d6efd'><b>{counts.get('DXF_ONLY', 0)}</b></font>", cell_style),
            Paragraph(f"<font size=14><b>{len(df)}</b></font>", cell_style),
        ]
    ]
    t_sum = Table(sum_data, colWidths=[55*mm, 55*mm, 55*mm, 55*mm, 55*mm])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e9ecef")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#ced4da")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_sum)
    story.append(Spacer(1, 8*mm))

    # Main Comparison Table
    headers = [
        "Type", "Status", "ETABS ID", "ETABS Location", "ETABS Section",
        "DXF Dim", "DXF Location", "Grid", "Hinges", "Dist (m)", "Discrepancy Notes"
    ]
    col_widths = [18*mm, 28*mm, 24*mm, 28*mm, 30*mm, 22*mm, 24*mm, 15*mm, 16*mm, 16*mm, 55*mm]

    STATUS_BG_COLOR = {
        "MATCH": colors.HexColor("#d4edda"),
        "SECTION_MISMATCH": colors.HexColor("#fff3cd"),
        "ETABS_ONLY": colors.HexColor("#f8d7da"),
        "DXF_ONLY": colors.HexColor("#d1ecf1"),
    }

    table_data = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in headers]]
    row_bg_commands = []

    for idx, row in df.iterrows():
        st = str(row.get("status", ""))
        et = str(row.get("element_type", "")).upper()
        name = str(row.get("etabs_name", "") or "—")
        
        # Format ETABS location
        ex, ey, ez = row.get("etabs_x"), row.get("etabs_y"), row.get("etabs_z")
        eloc = f"({ex:.2f}, {ey:.2f})" if pd.notna(ex) and pd.notna(ey) else "—"
        
        # Section and dims
        sec = str(row.get("etabs_section", "") or "—")
        ew, eh = row.get("etabs_w_mm"), row.get("etabs_h_mm")
        if pd.notna(ew) and pd.notna(eh):
            sec += f"<br/><font size=7 color='#666'>({ew:.0f}x{eh:.0f}mm)</font>"
        
        # DXF info
        ddim = str(row.get("dxf_dim_text", "") or "—")
        dx, dy = row.get("dxf_x"), row.get("dxf_y")
        dloc = f"({dx:.2f}, {dy:.2f})" if pd.notna(dx) and pd.notna(dy) else "—"
        
        grid = str(row.get("grid_ref", "") or "—")
        hinge = "YES" if row.get("has_hinges") else "—"
        dist = f"{row.get('xy_dist_m'):.3f}" if pd.notna(row.get("xy_dist_m")) else "—"
        notes = str(row.get("notes", "") or "")

        row_cells = [
            Paragraph(et, cell_style),
            Paragraph(st, cell_bold),
            Paragraph(name, cell_style),
            Paragraph(eloc, cell_style),
            Paragraph(sec, cell_style),
            Paragraph(ddim, cell_style),
            Paragraph(dloc, cell_style),
            Paragraph(grid, cell_style),
            Paragraph(hinge, cell_style),
            Paragraph(dist, cell_style),
            Paragraph(notes, cell_style),
        ]
        table_data.append(row_cells)

        row_idx = len(table_data) - 1
        bg = STATUS_BG_COLOR.get(st, colors.white)
        row_bg_commands.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

    t_main = Table(table_data, colWidths=col_widths, repeatRows=1)
    base_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#343a40")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#adb5bd")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ]
    # In table headers, make text white
    for col in range(len(headers)):
        base_style.append(('TEXTCOLOR', (col, 0), (col, 0), colors.white))

    t_main.setStyle(TableStyle(base_style + row_bg_commands))
    story.append(t_main)

    doc.build(story)
    print(f"Successfully generated PDF via ReportLab: {output_path}")

if __name__ == "__main__":
    df_res = pd.read_csv("test_verification_report_dxf_elements.csv") if False else None
    from phase3_validation import validate
    from phase1_etabs import load_from_csvs
    from phase2_dxf import parse_dxf
    from config import Config
    
    cfg = Config()
    d_etabs = load_from_csvs("etabs_sample")
    df_d = parse_dxf("sample_building.dxf", cfg)
    res = validate(d_etabs, df_d, cfg)
    build_pdf_report(res, "sample_reportlab_report.pdf")
