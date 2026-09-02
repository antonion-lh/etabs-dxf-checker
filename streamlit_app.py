"""
streamlit_app.py — ETABS ↔ CAD Automated Structural QA Platform
Enterprise engineering tool with crystal-clear navigation, high contrast,
full CAD/PDF/image drawing support, and zero visual clutter.
"""

import io
import os
import tempfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status
from report import generate_pdf, generate_html

# ─────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ETABS ↔ CAD · Kontrola Numeričkih Modela",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

# ─────────────────────────────────────────────────────────────
# High-contrast, clean CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Base page setup — generous top padding to NEVER clip under Streamlit header */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.block-container {
    padding-top: 5rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px;
}

/* ─── Sidebar: crisp, high contrast, legible ─── */
[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #0f172a !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: #1e293b !important;
    font-weight: 500;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stCheckbox label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #1e293b !important;
}

/* ─── Header Card ─── */
.app-header-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.app-header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}
.app-header-icon {
    font-size: 38px;
    line-height: 1;
}
.app-header-title {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
    margin: 0;
    letter-spacing: -0.02em;
}
.app-header-sub {
    font-size: 13px;
    color: #64748b;
    margin: 4px 0 0 0;
}
.badge-group {
    display: flex;
    gap: 8px;
    align-items: center;
}
.badge-tag {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.badge-blue {
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
}
.badge-green {
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
}

/* ─── KPI Strip ─── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 18px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    border-radius: 12px 12px 0 0;
}
.kpi-card.green::before  { background: #10b981; }
.kpi-card.amber::before  { background: #f59e0b; }
.kpi-card.red::before    { background: #ef4444; }
.kpi-card.blue::before   { background: #3b82f6; }
.kpi-card.slate::before  { background: #64748b; }
.kpi-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.kpi-number {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1;
}
.kpi-sub {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
    font-weight: 500;
}

/* ─── Legend / Explanations ─── */
.legend-banner {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    font-size: 12px;
    color: #334155;
    align-items: center;
}
.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.dot-green { color: #10b981; font-weight: 700; }
.dot-amber { color: #f59e0b; font-weight: 700; }
.dot-red   { color: #ef4444; font-weight: 700; }
.dot-blue  { color: #3b82f6; font-weight: 700; }

/* ─── Warning Pills ─── */
.warn-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #fefce8;
    border: 1px solid #fef08a;
    color: #854d0e;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 6px;
    margin-bottom: 6px;
}
.error-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #991b1b;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 6px;
    margin-bottom: 6px;
}

/* ─── Welcome / Empty State ─── */
.welcome-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 40px 32px;
    text-align: center;
    margin-bottom: 28px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.step-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    height: 100%;
}
.step-number {
    display: inline-block;
    background: #0284c7;
    color: white;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    text-align: center;
    line-height: 26px;
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 12px;
}
.step-title {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 6px;
}
.step-desc {
    font-size: 13px;
    color: #64748b;
    line-height: 1.5;
}

/* ─── Download Card ─── */
.dl-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 28px;
    text-align: center;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Sidebar: Clean, crisp, high-contrast
# ─────────────────────────────────────────────────────────────
def _sidebar() -> tuple:
    with st.sidebar:
        st.markdown("### 🏢 ETABS ↔ CAD QA")
        st.caption("Alat za automatsku reviziju proračunskih modela")
        st.markdown("---")

        # 1. Ulazni podaci
        st.markdown("#### 📂 1. Ulazne datoteke")
        if "use_demo" not in st.session_state:
            st.session_state["use_demo"] = False

        use_demo = st.toggle(
            "🧪 Učitaj ogledni primjer (Demo)",
            value=st.session_state["use_demo"],
            key="sidebar_demo_toggle",
            help="Uključite za instantni pregled s gotovim ETABS modelom i CAD nacrtom zgrade.",
        )
        st.session_state["use_demo"] = use_demo

        uploaded_dxf = uploaded_e2k = None
        if not use_demo:
            uploaded_dxf = st.file_uploader(
                "CAD nacrt (.dxf):",
                type=["dxf"],
                help="Izvedbeni tlocrt konstrukcije iz AutoCAD-a ili drugog CAD softvera.",
            )
            uploaded_e2k = st.file_uploader(
                "ETABS model (.e2k, .$et):",
                type=["e2k", "$et", "txt"],
                help="Tekstualni izvoz modela iz ETABS-a (File → Export → ETABS .e2k Text File).",
            )

        st.markdown("---")

        # 2. Referentni nacrt (PDF / slika)
        st.markdown("#### 📑 2. Referentni nacrt (opcija)")
        uploaded_drawing = st.file_uploader(
            "Priložite PDF ili sliku nacrta:",
            type=["pdf", "jpg", "jpeg", "png", "tif", "tiff"],
            help="Projektantski nacrt u PDF-u ili JPG/PNG formatu za usporedni vizualni pregled uz numerički model.",
        )

        st.markdown("---")

        # 3. Mjerne jedinice i tolerancije
        st.markdown("#### 📐 3. Jedinice i tolerancije")
        scale_label = st.selectbox(
            "Jedinica u CAD crtežu:",
            ["Centimetri (cm)", "Milimetri (mm)", "Metri (m)"],
            index=0,
            help="Odaberite mjernu jedinicu u kojoj je crtan CAD nacrt.",
        )
        scale_map = {"Centimetri (cm)": 0.01, "Milimetri (mm)": 0.001, "Metri (m)": 1.0}
        unit_scale = scale_map[scale_label]

        with st.expander("⚙️ Prilagodba tolerancija odstupanja"):
            tol_frame = st.slider("Tolerancija pozicije stupova/greda (m):", 0.05, 0.50, 0.15, 0.01)
            tol_area  = st.slider("Tolerancija pozicije zidova/ploča (m):", 0.10, 1.00, 0.30, 0.05)
            tol_sec   = st.slider("Dozvoljeno odstupanje presjeka (mm):", 1.0, 30.0, 5.0, 1.0)

        st.markdown("---")

        # 4. Obuhvat kontrole
        st.markdown("#### 🔍 4. Obuhvat kontrole")
        col_a, col_b = st.columns(2)
        with col_a:
            chk_cols  = st.checkbox("Stupovi", True)
            chk_beams = st.checkbox("Grede", True)
            chk_walls = st.checkbox("Zidovi", True)
            chk_slabs = st.checkbox("Ploče", True)
        with col_b:
            chk_mat   = st.checkbox("Materijali", True)
            chk_load  = st.checkbox("Opterećenja", True)
            chk_rest  = st.checkbox("Oslonci", True)
            chk_hinge = st.checkbox("Zglobovi", True)

        elem_types = (
            (["columns"] if chk_cols  else []) +
            (["beams"]   if chk_beams else []) +
            (["walls"]   if chk_walls else []) +
            (["slabs"]   if chk_slabs else [])
        )

        cfg = Config(
            dxf_unit_scale=unit_scale,
            spatial_tolerance_frame=tol_frame,
            spatial_tolerance_area=tol_area,
            section_tolerance_mm=tol_sec,
            extract_elements=elem_types,
            audit_materials=chk_mat,
            audit_loads=chk_load,
            audit_restraints=chk_rest,
            report_hinges=chk_hinge,
        )

        st.markdown("---")
        st.caption("Inženjerska kontrola · Eurocode HRN EN 1992/1993")

    return use_demo, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg


# ─────────────────────────────────────────────────────────────
# Reference Drawing Viewer (PDF / JPEG / PNG / TIFF)
# ─────────────────────────────────────────────────────────────
def _render_drawing(uploaded_drawing):
    """Renders uploaded PDF or image with page controls."""
    if uploaded_drawing is None:
        return

    name = uploaded_drawing.name.lower()
    raw  = uploaded_drawing.getvalue()

    try:
        if name.endswith(".pdf"):
            import fitz  # PyMuPDF
            doc  = fitz.open(stream=raw, filetype="pdf")
            num_pages = len(doc)

            selected_page = 0
            if num_pages > 1:
                selected_page = st.number_input(
                    f"Stranica PDF nacrta (ukupno {num_pages}):",
                    min_value=1, max_value=num_pages, value=1, step=1, key="pdf_page_selector"
                ) - 1

            page = doc[selected_page]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            img_bytes = pix.tobytes("png")
            st.image(img_bytes, use_container_width=True,
                     caption=f"Nacrt: {uploaded_drawing.name} (stranica {selected_page + 1}/{num_pages})")
        else:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(raw))
            max_w = 3200
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
            st.image(img, use_container_width=True, caption=f"Nacrt: {uploaded_drawing.name}")
    except Exception as e:
        st.error(f"Pogreška pri učitavanju nacrta: {e}")


# ─────────────────────────────────────────────────────────────
# KPI Strip: Colored indicator borders, crisp typography
# ─────────────────────────────────────────────────────────────
def _kpi_strip(df: pd.DataFrame):
    counts = df["status"].value_counts()
    n_match = counts.get(Status.MATCH, 0)
    n_mis   = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs = counts.get(Status.ETABS_ONLY, 0)
    n_dxf   = counts.get(Status.DXF_ONLY, 0)
    n_total = len(df)
    pct     = round(n_match / max(n_total, 1) * 100)

    st.markdown(f"""
    <div class="kpi-strip">
      <div class="kpi-card green">
        <div class="kpi-label">✅ Usklađeno</div>
        <div class="kpi-number">{n_match}</div>
        <div class="kpi-sub">{pct}% elemenata točno</div>
      </div>
      <div class="kpi-card amber">
        <div class="kpi-label">⚠️ Odstupanje presjeka</div>
        <div class="kpi-number">{n_mis}</div>
        <div class="kpi-sub">{'Razlika u dimenzijama' if n_mis else 'Nema odstupanja'}</div>
      </div>
      <div class="kpi-card red">
        <div class="kpi-label">🔴 Samo u ETABS-u</div>
        <div class="kpi-number">{n_etabs}</div>
        <div class="kpi-sub">{'Nema u CAD nacrtu' if n_etabs else 'Nema viška'}</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-label">🔵 Samo u CAD-u</div>
        <div class="kpi-number">{n_dxf}</div>
        <div class="kpi-sub">{'Nedostaje u modelu' if n_dxf else 'Sve uneseno'}</div>
      </div>
      <div class="kpi-card slate">
        <div class="kpi-label">📋 Ukupno provjereno</div>
        <div class="kpi-number">{n_total}</div>
        <div class="kpi-sub">Elemenata analizirano</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 2D Floorplan: True architectural layout with CAD axis bubbles
# ─────────────────────────────────────────────────────────────
def _fig_2d(df_res: pd.DataFrame, etabs_data: dict) -> go.Figure:
    COLOR_MAP = {
        Status.MATCH:            ("#10b981", "Usklađeno s nacrtom"),
        Status.SECTION_MISMATCH: ("#f59e0b", "Odstupanje dimenzija"),
        Status.ETABS_ONLY:       ("#ef4444", "Samo u ETABS-u"),
        Status.DXF_ONLY:         ("#3b82f6", "Samo u CAD nacrtu"),
    }

    fig = go.Figure()

    # Collect coordinates to set view limits
    all_x, all_y = [], []
    for _, r in df_res.iterrows():
        x = r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x")
        y = r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y")
        if pd.notna(x) and pd.notna(y):
            all_x.append(float(x)); all_y.append(float(y))

    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 12.0
    min_y = min(all_y) if all_y else 0.0
    max_y = max(all_y) if all_y else 6.0

    pad_x = max((max_x - min_x) * 0.20, 2.5)
    pad_y = max((max_y - min_y) * 0.20, 2.5)

    status_map = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    # 1. Background Slab Polygons
    slabs = etabs_data.get("slabs", pd.DataFrame())
    if not slabs.empty:
        # Draw slab boundary (e.g. 0 to 6 in X, 0 to 6 in Y)
        fig.add_trace(go.Scatter(
            x=[0, 6, 6, 0, 0], y=[0, 0, 6, 6, 0],
            fill="toself",
            fillcolor="rgba(241, 245, 249, 0.6)",
            line=dict(color="#cbd5e1", width=1, dash="dash"),
            name="AB Ploča d=20 cm",
            hovertext="<b>AB Ploča SLAB_BAY1</b><br>Debljina: 200 mm<br>Raspon: 6.0 × 6.0 m",
            hoverinfo="text",
            showlegend=False,
        ))

    # 2. Beams: Exact lines between joints
    beams = etabs_data.get("beams", pd.DataFrame())
    if not beams.empty:
        for _, bm in beams.iterrows():
            st_val = status_map.get(str(bm["name"]), Status.MATCH)
            col, lbl = COLOR_MAP.get(st_val, ("#10b981", "Usklađeno"))
            x0, y0 = bm["x_start"], bm["y_start"]
            x1, y1 = bm["x_end"], bm["y_end"]
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=col, width=6),
                name=f"Grede [{lbl}]",
                hovertext=f"<b>Greda {bm['name']}</b> [{lbl}]<br>Presjek: {bm.get('section','—')}<br>Od: ({x0:.1f}, {y0:.1f}) do ({x1:.1f}, {y1:.1f}) m",
                hoverinfo="text",
                legendgroup="Grede",
                showlegend=False,
            ))

    # Any DXF-only beams
    dxf_only_beams = df_res[(df_res["status"] == Status.DXF_ONLY) & (df_res["element_type"] == "beam")]
    for _, bm in dxf_only_beams.iterrows():
        bx = bm.get("dxf_x", 0.0)
        by = bm.get("dxf_y", 0.0)
        fig.add_trace(go.Scatter(
            x=[bx, bx + 6.0], y=[by, by],
            mode="lines",
            line=dict(color="#3b82f6", width=5, dash="dot"),
            name="Samo u CAD-u",
            hovertext=f"<b>Greda (samo u CAD-u)</b><br>Kota: {bm.get('dxf_dim_text','—')}<br>Lokacija: Y = {by:.2f} m",
            hoverinfo="text",
            showlegend=False,
        ))

    # 3. Walls
    walls = etabs_data.get("walls", pd.DataFrame())
    if not walls.empty:
        for _, w in walls.iterrows():
            st_val = status_map.get(str(w["name"]), Status.MATCH)
            col, lbl = COLOR_MAP.get(st_val, ("#10b981", "Usklađeno"))
            wx, wy = w["centroid_x"], w["centroid_y"]
            fig.add_trace(go.Scatter(
                x=[wx, wx], y=[wy - 1.75, wy + 1.75],
                mode="lines",
                line=dict(color=col, width=10),
                name="Zidovi",
                hovertext=f"<b>AB Zid {w['name']}</b> [{lbl}]<br>Debljina: {w.get('thickness_mm', 250):.0f} mm<br>Pozicija: X={wx:.1f}, Y={wy:.1f} m",
                hoverinfo="text",
                showlegend=False,
            ))

    # 4. Columns: Sharp colored squares with clear ID badges
    col_records = df_res[df_res["element_type"] == "column"]
    for status, (color, label) in COLOR_MAP.items():
        sub_cols = col_records[col_records["status"] == status]
        if sub_cols.empty:
            continue

        xs = [r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x") for _, r in sub_cols.iterrows()]
        ys = [r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y") for _, r in sub_cols.iterrows()]
        texts = [r.get("etabs_name") or r.get("dxf_name") or "C" for _, r in sub_cols.iterrows()]

        tips = []
        for _, r in sub_cols.iterrows():
            nm = r.get("etabs_name") or r.get("dxf_name") or "Stup"
            sec = r.get("etabs_section") or "—"
            ew, eh = r.get("etabs_w_mm"), r.get("etabs_h_mm")
            dw, dh = r.get("dxf_dim1_mm"), r.get("dxf_dim2_mm")
            tips.append(
                f"<b>{nm}</b> [{label}]<br>"
                f"Presjek: {sec}<br>"
                f"ETABS dim.: {f'{ew:.0f}×{eh:.0f}' if pd.notna(ew) and pd.notna(eh) else '—'} mm<br>"
                f"CAD dim.:   {f'{dw:.0f}×{dh:.0f}' if pd.notna(dw) and pd.notna(dh) else '—'} mm<br>"
                f"Status: {r.get('notes') or label}"
            )

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(
                size=22,
                symbol="square",
                color=color,
                line=dict(color="#ffffff", width=2),
            ),
            text=texts,
            textposition="top center",
            textfont=dict(size=11, color="#0f172a", family="Inter", weight="bold"),
            name=f"Stupovi — {label}",
            hovertext=tips,
            hoverinfo="text",
            showlegend=True,
        ))

    # 5. Architectural CAD Grid Bubbles (Osi A, B, C i 1, 2)
    grid_x = [0.0, 6.0, 12.0]
    labels_x = ["A", "B", "C"]
    y_bubble = max_y + 1.2

    for gx, lx in zip(grid_x, labels_x):
        # Guideline
        fig.add_shape(type="line", x0=gx, y0=min_y - 0.5, x1=gx, y1=y_bubble,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        # Circle Bubble
        fig.add_trace(go.Scatter(
            x=[gx], y=[y_bubble],
            mode="markers+text",
            marker=dict(size=24, color="#3b82f6", line=dict(color="#ffffff", width=2)),
            text=[lx], textfont=dict(color="white", size=11, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {lx} (X = {gx:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    grid_y = [0.0, 6.0]
    labels_y = ["1", "2"]
    x_bubble = min_x - 1.2

    for gy, ly in zip(grid_y, labels_y):
        # Guideline
        fig.add_shape(type="line", x0=x_bubble, y0=gy, x1=max_x + 0.5, y1=gy,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        # Circle Bubble
        fig.add_trace(go.Scatter(
            x=[x_bubble], y=[gy],
            mode="markers+text",
            marker=dict(size=24, color="#0284c7", line=dict(color="#ffffff", width=2)),
            text=[ly], textfont=dict(color="white", size=11, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {ly} (Y = {gy:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    fig.update_layout(
        margin=dict(l=30, r=20, t=20, b=40),
        height=540,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            title="X koordinata (m)",
            range=[min_x - pad_x, max_x + pad_x],
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=True,
            zerolinecolor="#cbd5e1",
            tickfont=dict(size=11, color="#64748b"),
        ),
        yaxis=dict(
            title="Y koordinata (m)",
            range=[min_y - pad_y, max_y + pad_y],
            scaleanchor="x",
            scaleratio=1,
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=True,
            zerolinecolor="#cbd5e1",
            tickfont=dict(size=11, color="#64748b"),
        ),
        legend=dict(
            orientation="h",
            x=0, y=-0.14,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e2e8f0",
            borderwidth=1,
            font=dict(size=11, color="#334155"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 3D Model: Wireframe with color-coded status
# ─────────────────────────────────────────────────────────────
def _fig_3d(df_res: pd.DataFrame, etabs_data: dict) -> go.Figure:
    fig = go.Figure()
    COLOR_MAP = {
        Status.MATCH: "#10b981", Status.SECTION_MISMATCH: "#f59e0b",
        Status.ETABS_ONLY: "#ef4444", Status.DXF_ONLY: "#3b82f6",
    }
    status_by = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    # Columns
    cols = etabs_data.get("columns", pd.DataFrame())
    for _, c in (cols.iterrows() if not cols.empty else []):
        color = COLOR_MAP.get(status_by.get(str(c["name"]), Status.MATCH), "#10b981")
        fig.add_trace(go.Scatter3d(
            x=[c["x_start"], c["x_end"]], y=[c["y_start"], c["y_end"]], z=[c["z_start"], c["z_end"]],
            mode="lines", line=dict(color=color, width=9),
            name=f"Stup {c['name']}", showlegend=False,
            hovertext=f"<b>Stup {c['name']}</b><br>Presjek: {c.get('section','')}<br>Visina: {c['z_start']:.1f} do {c['z_end']:.1f} m",
            hoverinfo="text",
        ))

    # Beams
    beams = etabs_data.get("beams", pd.DataFrame())
    for _, b in (beams.iterrows() if not beams.empty else []):
        color = COLOR_MAP.get(status_by.get(str(b["name"]), Status.MATCH), "#f59e0b")
        fig.add_trace(go.Scatter3d(
            x=[b["x_start"], b["x_end"]], y=[b["y_start"], b["y_end"]], z=[b["z_start"], b["z_end"]],
            mode="lines", line=dict(color=color, width=6),
            name=f"Greda {b['name']}", showlegend=False,
            hovertext=f"<b>Greda {b['name']}</b><br>Presjek: {b.get('section','')}<br>Kota Z = {b['z_start']:.2f} m",
            hoverinfo="text",
        ))

    # Slab
    fig.add_trace(go.Mesh3d(
        x=[0, 6, 6, 0], y=[0, 0, 6, 6], z=[3.2, 3.2, 3.2, 3.2],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color="#3b82f6", opacity=0.20, showlegend=False,
        hovertext="<b>AB Ploča</b> d=20 cm, Z=3.20 m", hoverinfo="text"
    ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=540,
        paper_bgcolor="#ffffff",
        scene=dict(
            aspectmode="data",
            camera=dict(eye=dict(x=1.6, y=-1.8, z=1.2)),
            xaxis=dict(title="X (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            yaxis=dict(title="Y (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            zaxis=dict(title="Z (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# Table helper: Cleans attrs & formats floats safely
# ─────────────────────────────────────────────────────────────
def _safe_df(df: pd.DataFrame, float_fmt=None) -> pd.DataFrame:
    out = df.copy()
    out.attrs = {}
    if float_fmt:
        for col, fmt in float_fmt.items():
            if col in out.columns:
                out[col] = out[col].apply(lambda v: fmt.format(v) if pd.notna(v) and v is not None else "—")
    out = out.fillna("—")
    return out


# ─────────────────────────────────────────────────────────────
# Main Application Flow
# ─────────────────────────────────────────────────────────────
def main():
    use_demo, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg = _sidebar()

    # ── Header Card ──────────────────────────────────────────
    st.markdown("""
    <div class="app-header-card">
      <div class="app-header-left">
        <span class="app-header-icon">🏢</span>
        <div>
          <h1 class="app-header-title">ETABS ↔ CAD · Kontrola Numeričkih Modela</h1>
          <p class="app-header-sub">Automatska verifikacija geometrije, dimenzija presjeka, materijala i opterećenja konstrukcije</p>
        </div>
      </div>
      <div class="badge-group">
        <span class="badge-tag badge-blue">v2.5 Enterprise</span>
        <span class="badge-tag badge-green">Eurocode HRN EN</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Resolve Input Files ──────────────────────────────────
    has_data, dxf_path, e2k_content = False, None, None

    if use_demo:
        if os.path.exists(SAMPLE_DXF) and os.path.exists(SAMPLE_E2K):
            dxf_path = SAMPLE_DXF
            with open(SAMPLE_E2K, "r", encoding="utf-8", errors="replace") as f:
                e2k_content = f.read()
            has_data = True
        else:
            st.error("Ogledne datoteke nisu pronađene na poslužitelju.")
    elif uploaded_dxf and uploaded_e2k:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
        tmp.write(uploaded_dxf.getvalue())
        tmp.close()
        dxf_path = tmp.name
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        has_data = True

    # ── Welcome / Empty State: Clear instructions & 1-click Demo
    if not has_data:
        st.markdown("""
        <div class="welcome-card">
          <div style="font-size: 46px; margin-bottom: 12px;">🏗️</div>
          <h2 style="font-size: 22px; font-weight: 800; color: #0f172a; margin-bottom: 8px;">
            Dobrodošli u sustav kontrole numeričkih modela
          </h2>
          <p style="font-size: 14px; color: #64748b; max-width: 620px; margin: 0 auto 20px auto; line-height: 1.6;">
            Ovaj alat automatski uspoređuje proračunski model iz <b>ETABS v23</b> s izvedbenim <b>CAD nacrtom (.dxf)</b>
            te otkriva razlike u dimenzijama stupova i greda, nedostajuće elemente, odstupanja u materijalima i opterećenjima.
          </p>
        </div>
        """, unsafe_allow_html=True)

        # Big 1-click Demo Action
        col_demo, col_empty = st.columns([1.5, 1])
        with col_demo:
            if st.button("🚀 Isprobaj odmah s oglednim primjerom (1 klik)", type="primary", use_container_width=True):
                st.session_state["use_demo"] = True
                st.rerun()
            st.caption("Učitava gotov proračunski model zgrade i CAD nacrt za trenutni prikaz funkcionalnosti.")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # 3-Step Guide
        st.markdown("#### 📖 Kako funkcionira provjera u 3 koraka:")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown("""
            <div class="step-card">
              <span class="step-number">1</span>
              <div class="step-title">Izvoz iz ETABS-a</div>
              <div class="step-desc">
                U ETABS v23 odaberite: <code>File → Export → ETABS .e2k Text File...</code>
                i spremite tekstualni model na računalo.
              </div>
            </div>
            """, unsafe_allow_html=True)
        with s2:
            st.markdown("""
            <div class="step-card">
              <span class="step-number">2</span>
              <div class="step-title">Učitavanje datoteka</div>
              <div class="step-desc">
                U lijevom izborniku priložite <b>.e2k</b> datoteku i izvedbeni <b>CAD .dxf</b> nacrt
                (ili referentni PDF nacrta).
              </div>
            </div>
            """, unsafe_allow_html=True)
        with s3:
            st.markdown("""
            <div class="step-card">
              <span class="step-number">3</span>
              <div class="step-title">Analiza i elaborat</div>
              <div class="step-desc">
                Sustav u nekoliko sekundi pronalazi sva odstupanja na tlocrtu i generira
                službeni PDF elaborat za reviziju.
              </div>
            </div>
            """, unsafe_allow_html=True)
        return

    # ── Run Analysis ─────────────────────────────────────────
    with st.spinner("Automatska analiza geometrije i proračunskog modela u tijeku…"):
        try:
            df_dxf = parse_dxf(dxf_path, cfg)
            etabs_data = parse_e2k(io.StringIO(e2k_content), cfg)
            df_res = validate(etabs_data, df_dxf, cfg)
        except Exception as err:
            st.error(f"Greška tijekom obrade modela: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except: pass

    # ── KPI Strip ─────────────────────────────────────────────
    _kpi_strip(df_res)

    # ── Legend / Color Explanations ───────────────────────────
    st.markdown("""
    <div class="legend-banner">
      <span style="font-weight: 700; color: #0f172a;">Tumač statusa:</span>
      <span class="legend-item"><span class="dot-green">● Zeleno</span> Usklađeno (lokacija i presjek odgovaraju nacrtu)</span>
      <span class="legend-item"><span class="dot-amber">● Narančasto</span> Odstupanje u dimenzijama presjeka</span>
      <span class="legend-item"><span class="dot-red">● Crveno</span> Samo u ETABS-u (nema na CAD nacrtu)</span>
      <span class="legend-item"><span class="dot-blue">● Plavo</span> Samo u CAD-u (nedostaje u numeričkom modelu)</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Compact Sanity Warning Pills ──────────────────────────
    alerts = df_res.attrs.get("sanity_alerts", [])
    if alerts:
        pills = ""
        for a in alerts[:6]:
            cls = "error-pill" if a.get("severity") == "ERROR" else "warn-pill"
            icon = "🔴" if a.get("severity") == "ERROR" else "⚠️"
            pills += f'<span class="{cls}">{icon} [{a["category"]}] {a["element"]}: {a["issue"]}</span>'
        if len(alerts) > 6:
            pills += f'<span class="warn-pill">+{len(alerts)-6} dodatnih provjera…</span>'
        st.markdown(f"<div style='margin-bottom: 16px;'>{pills}</div>", unsafe_allow_html=True)

    # ── Tab Navigation: Clear, descriptive titles ─────────────
    t_map, t_geo, t_mat, t_sup, t_pdf = st.tabs([
        "🗺️ 1. Vizualni model (2D/3D)",
        "📊 2. Tablica odstupanja",
        "🧪 3. Materijali & Opterećenja",
        "🧱 4. Oslonci & Zglobovi",
        "📄 5. Službeni PDF Elaborat",
    ])

    # ── TAB 1: Visual Model & Reference Drawing ───────────────
    with t_map:
        has_drawing = uploaded_drawing is not None

        if has_drawing:
            view_mode = st.radio(
                "Način prikaza:",
                ["📐 Usporedni prikaz (Model + Referentni nacrt)", "🏢 Samo numerički model", "📑 Samo referentni nacrt"],
                horizontal=True,
                key="drawing_view_mode",
            )

            if view_mode.startswith("📐"):
                col_m, col_d = st.columns(2, gap="medium")
                with col_m:
                    st.markdown("##### Numerički model (ETABS)")
                    sub_m = st.radio("Tip prikaza:", ["2D Tlocrt", "3D Wireframe"], horizontal=True, key="sub_m1")
                    if sub_m == "3D Wireframe":
                        st.plotly_chart(_fig_3d(df_res, etabs_data), use_container_width=True)
                    else:
                        st.plotly_chart(_fig_2d(df_res, etabs_data), use_container_width=True)
                with col_d:
                    st.markdown("##### Referentni nacrt")
                    _render_drawing(uploaded_drawing)

            elif view_mode.startswith("🏢"):
                sub_m = st.radio("Tip prikaza:", ["2D Tlocrt s osima", "3D Wireframe"], horizontal=True, key="sub_m2")
                if sub_m.startswith("3D"):
                    st.plotly_chart(_fig_3d(df_res, etabs_data), use_container_width=True)
                else:
                    st.plotly_chart(_fig_2d(df_res, etabs_data), use_container_width=True)

            else:
                _render_drawing(uploaded_drawing)

        else:
            sub_col, cap_col = st.columns([1, 2])
            with sub_col:
                mode = st.radio("Tip prikaza modela:", ["2D Tlocrt s osima", "3D Wireframe model"], horizontal=True, key="mode_full")
            with cap_col:
                st.caption("💡 Za usporedni prikaz nacrta uz model, priložite PDF ili sliku u bočnoj traci (Referentni nacrt).")

            if mode.startswith("3D"):
                st.plotly_chart(_fig_3d(df_res, etabs_data), use_container_width=True)
            else:
                st.plotly_chart(_fig_2d(df_res, etabs_data), use_container_width=True)

    # ── TAB 2: Deviations & Geometry Table ────────────────────
    with t_geo:
        st.markdown("##### Detaljna usporedba dimenzija i položaja elemenata")
        f1, f2, f3 = st.columns([1.5, 1.5, 2])
        with f1:
            st_f = st.selectbox("Filtriraj po statusu:", ["Svi statusi"] + [s.value for s in Status], key="geo_status")
        with f2:
            ty_f = st.selectbox("Filtriraj po tipu:", ["Svi tipovi"] + sorted(df_res["element_type"].unique()), key="geo_type")
        with f3:
            search = st.text_input("Pretraga po oznaci:", placeholder="C1, B101, 30x40...", key="geo_search")

        dfd = df_res.copy()
        if st_f != "Svi statusi":
            dfd = dfd[dfd["status"].astype(str) == st_f]
        if ty_f != "Svi tipovi":
            dfd = dfd[dfd["element_type"] == ty_f]
        if search:
            q = search.lower()
            dfd = dfd[dfd.apply(lambda r: q in str(r.to_dict()).lower(), axis=1)]

        vcols = [
            "element_type", "status", "etabs_name", "etabs_section",
            "etabs_w_mm", "etabs_h_mm", "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm", "xy_dist_m", "notes"
        ]
        vcols = [c for c in vcols if c in dfd.columns]
        tbl = _safe_df(dfd[vcols], {
            "etabs_w_mm": "{:.0f}", "etabs_h_mm": "{:.0f}",
            "dxf_dim1_mm": "{:.0f}", "dxf_dim2_mm": "{:.0f}",
            "xy_dist_m": "{:.2f}",
        })
        if "status" in tbl.columns:
            tbl["status"] = tbl["status"].apply(lambda v: v.value if hasattr(v, "value") else str(v))

        st.dataframe(
            tbl, use_container_width=True, hide_index=True,
            column_config={
                "element_type": st.column_config.TextColumn("Tip"),
                "status":       st.column_config.TextColumn("Status"),
                "etabs_name":   st.column_config.TextColumn("ETABS ID"),
                "etabs_section":st.column_config.TextColumn("Presjek"),
                "etabs_w_mm":   st.column_config.TextColumn("ETABS b (mm)"),
                "etabs_h_mm":   st.column_config.TextColumn("ETABS h (mm)"),
                "dxf_dim_text": st.column_config.TextColumn("CAD oznaka"),
                "dxf_dim1_mm":  st.column_config.TextColumn("CAD b (mm)"),
                "dxf_dim2_mm":  st.column_config.TextColumn("CAD h (mm)"),
                "xy_dist_m":    st.column_config.TextColumn("Odmak (m)"),
                "notes":        st.column_config.TextColumn("Inženjerska napomena"),
            }
        )

    # ── TAB 3: Materials & Loads ──────────────────────────────
    with t_mat:
        mc, lc = st.columns(2, gap="large")

        with mc:
            st.markdown("##### 🧪 Klase materijala (Beton / Čelik)")
            mats = pd.DataFrame(df_res.attrs.get("materials", []))
            if not mats.empty:
                st.dataframe(
                    _safe_df(mats, {"E_gpa": "{:.1f}", "fc_mpa": "{:.1f}", "fy_mpa": "{:.1f}", "fu_mpa": "{:.1f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "name":   st.column_config.TextColumn("Naziv materijala"),
                        "type":   st.column_config.TextColumn("Tip"),
                        "E_gpa":  st.column_config.TextColumn("Modul E (GPa)"),
                        "fc_mpa": st.column_config.TextColumn("fck (MPa)"),
                        "fy_mpa": st.column_config.TextColumn("fyk (MPa)"),
                        "fu_mpa": st.column_config.TextColumn("fuk (MPa)"),
                    }
                )
            else:
                st.info("Nema definiranih materijala u modelu.")

        with lc:
            st.markdown("##### ⚖️ Uzorci opterećenja (Load Patterns)")
            pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
            if not pats.empty:
                st.dataframe(
                    _safe_df(pats, {"self_weight_mult": "{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "name":             st.column_config.TextColumn("Uzorak"),
                        "type":             st.column_config.TextColumn("Tip opterećenja"),
                        "self_weight_mult": st.column_config.TextColumn("Faktor vl. težine"),
                    }
                )
            else:
                st.info("Nema definiranih uzoraka opterećenja.")

            aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
            if not aloads.empty:
                st.markdown("##### Plošna opterećenja na pločama (kN/m²)")
                st.dataframe(_safe_df(aloads), use_container_width=True, hide_index=True)

    # ── TAB 4: Supports & Hinges ──────────────────────────────
    with t_sup:
        sc, hc = st.columns(2, gap="large")

        with sc:
            st.markdown("##### 🧱 Temeljni oslonci (Rubni uvjeti)")
            rests = pd.DataFrame(df_res.attrs.get("restraints", []))
            if not rests.empty and "joint_name" in rests.columns:
                rcols = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in rests.columns]
                st.dataframe(
                    _safe_df(rests[rcols], {"x": "{:.2f}", "y": "{:.2f}", "z": "{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "joint_name":     st.column_config.TextColumn("Čvor"),
                        "x":              st.column_config.TextColumn("X (m)"),
                        "y":              st.column_config.TextColumn("Y (m)"),
                        "z":              st.column_config.TextColumn("Z (m)"),
                        "restraint_type": st.column_config.TextColumn("Tip oslonca"),
                        "is_supported":   st.column_config.CheckboxColumn("Poduprt"),
                    }
                )
            else:
                st.info("Nema podataka o osloncima.")

        with hc:
            st.markdown("##### 🔗 Nelinearni plastični zglobovi")
            hinges = etabs_data.get("hinges", pd.DataFrame())
            if not hinges.empty and "frame_name" in hinges.columns:
                hcols = [c for c in ["frame_name", "hinge_prop", "rel_dist", "dof"] if c in hinges.columns]
                st.dataframe(
                    _safe_df(hinges[hcols], {"rel_dist": "{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "frame_name": st.column_config.TextColumn("Element"),
                        "hinge_prop": st.column_config.TextColumn("Svojstvo zgloba"),
                        "rel_dist":   st.column_config.TextColumn("Pozicija"),
                        "dof":        st.column_config.TextColumn("DOF"),
                    }
                )
            else:
                st.info("U modelu nisu definirani plastični zglobovi (linearni proračun).")

    # ── TAB 5: PDF Elaborat ───────────────────────────────────
    with t_pdf:
        st.markdown("""
        <div class="dl-card">
          <div style="font-size: 38px; margin-bottom: 8px;">📄</div>
          <h3 style="margin: 0 0 6px 0; color: #0f172a; font-weight: 800;">Službeni Revizijski Elaborat</h3>
          <p style="margin: 0 auto; color: #64748b; font-size: 13px; max-width: 520px; line-height: 1.5;">
            Generirajte formalni A4 Landscape revizijski dokument s naslovnicom, sažetkom usklađenosti prema Eurocodu,
            grafičkim tlocrtom i potpunim inženjerskim tablicama za arhiviranje i ovjeru.
          </p>
        </div>
        """, unsafe_allow_html=True)

        d1, d2 = st.columns(2)
        with d1:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
                pdf_path = fp.name
            try:
                generate_pdf(df_res, pdf_path, cfg)
                st.download_button(
                    "📥 Preuzmi PDF Elaborat (A4 Landscape)",
                    data=open(pdf_path, "rb").read(),
                    file_name="ETABS_CAD_Revizijski_Elaborat.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
            finally:
                try: os.unlink(pdf_path)
                except: pass

        with d2:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as fh:
                html_path = fh.name
            try:
                html_content = generate_html(df_res, html_path, cfg)
                st.download_button(
                    "🌐 Preuzmi HTML Izvještaj (Web pregled)",
                    data=html_content.encode("utf-8"),
                    file_name="ETABS_CAD_Izvjestaj.html",
                    mime="text/html",
                    use_container_width=True,
                )
            finally:
                try: os.unlink(html_path)
                except: pass


if __name__ == "__main__":
    main()
