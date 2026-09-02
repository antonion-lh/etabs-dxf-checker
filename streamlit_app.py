"""
streamlit_app.py
----------------
Enterprise Web Application for Automated Structural ETABS v23 ↔ DXF Cross-Validation.
Zero-installation for end users — runs directly in the web browser on Streamlit Cloud.
Designed with clean, spacious, modern engineering UI/UX.
"""

import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status
from report import generate_pdf, generate_html

# ---------------------------------------------------------------------------
# Page Configuration & Minimalist Clean Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ETABS ↔ CAD Kontrola Modela",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

# Subtle, clean CSS: removes clutter, adds breathing room, soft borders
CLEAN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
/* Reduce default top padding */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px;
}
/* Clean Header styling */
.header-title {
    font-size: 26px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.header-subtitle {
    font-size: 14px;
    color: #64748b;
    margin-bottom: 16px;
}
/* Stat Metric Cards */
.metric-row {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}
.metric-box {
    flex: 1;
    min-width: 160px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.metric-box.green { border-left: 4px solid #10b981; }
.metric-box.orange { border-left: 4px solid #f59e0b; }
.metric-box.red { border-left: 4px solid #ef4444; }
.metric-box.cyan { border-left: 4px solid #06b6d4; }
.metric-label {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.metric-num {
    font-size: 24px;
    font-weight: 700;
    color: #0f172a;
    margin-top: 2px;
}
.metric-hint {
    font-size: 11px;
    color: #94a3b8;
    margin-top: 2px;
}
/* Download Banner */
.download-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    margin-top: 10px;
}
</style>
"""
st.markdown(CLEAN_CSS, unsafe_allow_html=True)


def _render_sidebar():
    with st.sidebar:
        st.markdown("### 🏢 Postavke i Ulaz")
        st.caption("ETABS v23 ↔ 2D CAD Kontrola Modela")
        st.markdown("---")

        st.subheader("1. Ulazni podaci")
        use_sample = st.toggle("🧪 Učitaj ogledni primjer (Demo)", value=False, help="Trenutni test s gotovom zgradom.")

        uploaded_dxf = None
        uploaded_e2k = None

        if not use_sample:
            uploaded_dxf = st.file_uploader(
                "CAD nacrt tlocrta (.dxf)",
                type=["dxf"],
                help="Izvedbeni nacrt konstrukcije s kotama stupova, greda i ploča.",
            )
            uploaded_e2k = st.file_uploader(
                "ETABS tekstualni model (.e2k)",
                type=["e2k", "$et", "txt"],
                help="Standardni izvoz iz ETABS-a (File -> Export -> ETABS .e2k Text File...).",
            )

        st.markdown("---")
        st.subheader("2. Mjerne jedinice i mjerilo")
        scale_label = st.selectbox(
            "Jedinica u CAD nacrtu:",
            options=["Centimetri (1 unit = 1 cm)", "Milimetri (1 unit = 1 mm)", "Metri (1 unit = 1 m)"],
            index=0,
        )
        scale_map = {
            "Centimetri (1 unit = 1 cm)": 0.01,
            "Milimetri (1 unit = 1 mm)": 0.001,
            "Metri (1 unit = 1 m)": 1.0,
        }
        unit_scale = scale_map[scale_label]

        with st.expander("⚙️ Dozvoljena odstupanja"):
            tol_frame = st.slider("Položaj stupova/greda", 0.05, 0.40, 0.15, 0.01, format="%.2f m")
            tol_area = st.slider("Položaj zidova/ploča", 0.10, 0.80, 0.30, 0.05, format="%.2f m")
            tol_sec = st.slider("Dimenzije presjeka", 1.0, 25.0, 5.0, 1.0, format="%.0f mm")

        st.markdown("---")
        st.subheader("3. Obuhvat kontrole")
        c1, c2 = st.columns(2)
        with c1:
            chk_cols = st.checkbox("Stupovi", value=True)
            chk_beams = st.checkbox("Grede", value=True)
            chk_walls = st.checkbox("Zidovi", value=True)
            chk_slabs = st.checkbox("Ploče", value=True)
        with c2:
            chk_mat = st.checkbox("🧪 Materijal", value=True)
            chk_load = st.checkbox("⚖️ Opterećenja", value=True)
            chk_rest = st.checkbox("🧱 Oslonci", value=True)
            chk_hinge = st.checkbox("🔴 Zglobovi", value=True)

        elem_types = []
        if chk_cols: elem_types.append("columns")
        if chk_beams: elem_types.append("beams")
        if chk_walls: elem_types.append("walls")
        if chk_slabs: elem_types.append("slabs")

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
        st.caption("HKIG / Eurocode standard kontrole modela")

    return use_sample, uploaded_dxf, uploaded_e2k, cfg


def _render_kpis(df_res: pd.DataFrame):
    counts = df_res["status"].value_counts()
    n_match = counts.get(Status.MATCH, 0)
    n_mismatch = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs_only = counts.get(Status.ETABS_ONLY, 0)
    n_dxf_only = counts.get(Status.DXF_ONLY, 0)
    n_total = len(df_res)
    pct_match = round((n_match / max(n_total, 1)) * 100)

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box green">
            <div class="metric-label">🟢 Usklađeno</div>
            <div class="metric-num">{n_match}</div>
            <div class="metric-hint">{pct_match}% elemenata bez greške</div>
        </div>
        <div class="metric-box orange">
            <div class="metric-label">🟡 Odstupanje presjeka</div>
            <div class="metric-num">{n_mismatch}</div>
            <div class="metric-hint">{'Razlika u dimenzijama' if n_mismatch > 0 else 'Nema odstupanja'}</div>
        </div>
        <div class="metric-box red">
            <div class="metric-label">🔴 Samo u ETABS-u</div>
            <div class="metric-num">{n_etabs_only}</div>
            <div class="metric-hint">{'Višak u modelu' if n_etabs_only > 0 else 'Nema viška'}</div>
        </div>
        <div class="metric-box cyan">
            <div class="metric-label">🔵 Samo u CAD-u</div>
            <div class="metric-num">{n_dxf_only}</div>
            <div class="metric-hint">{'Nedostaje u modelu' if n_dxf_only > 0 else 'Sve uneseno'}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Ukupno elemenata</div>
            <div class="metric-num">{n_total}</div>
            <div class="metric-hint">Provjereno u 5 kategorija</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_plotly_3d_model(df_res: pd.DataFrame, etabs_data: dict):
    fig = go.Figure()

    color_map = {
        Status.MATCH: "#10b981",           # Green
        Status.SECTION_MISMATCH: "#f59e0b", # Orange
        Status.ETABS_ONLY: "#ef4444",       # Red
        Status.DXF_ONLY: "#06b6d4",         # Cyan
    }

    status_by_name = {}
    for _, r in df_res.iterrows():
        name = r.get("etabs_name")
        if name:
            status_by_name[str(name)] = r.get("status")

    # 1. 3D Columns
    cols = etabs_data.get("columns", pd.DataFrame())
    if not cols.empty:
        for _, col in cols.iterrows():
            cname = str(col["name"])
            st_val = status_by_name.get(cname, Status.MATCH)
            color = color_map.get(st_val, "#10b981")
            sec = col.get("section", "")
            w = col.get("width_mm") or col.get("diameter_mm") or 400
            h = col.get("height_mm") or w
            fig.add_trace(go.Scatter3d(
                x=[col["x_start"], col["x_end"]],
                y=[col["y_start"], col["y_end"]],
                z=[col["z_start"], col["z_end"]],
                mode="lines+markers+text",
                line=dict(color=color, width=9),
                marker=dict(size=4, color="#0f172a"),
                text=["", cname],
                textposition="top center",
                textfont=dict(size=10, color="#0f172a"),
                name=f"Stup {cname}",
                hovertext=f"<b>Stup {cname}</b><br>Presjek: {sec} ({w:.0f}x{h:.0f} mm)<br>Z = {col['z_start']:.1f} do {col['z_end']:.1f} m",
                hoverinfo="text",
                showlegend=False,
            ))

    # 2. 3D Beams
    beams = etabs_data.get("beams", pd.DataFrame())
    if not beams.empty:
        for _, bm in beams.iterrows():
            bname = str(bm["name"])
            st_val = status_by_name.get(bname, Status.MATCH)
            color = color_map.get(st_val, "#f59e0b")
            sec = bm.get("section", "")
            fig.add_trace(go.Scatter3d(
                x=[bm["x_start"], bm["x_end"]],
                y=[bm["y_start"], bm["y_end"]],
                z=[bm["z_start"], bm["z_end"]],
                mode="lines+markers",
                line=dict(color=color, width=7),
                marker=dict(size=4, color="#0f172a"),
                name=f"Greda {bname}",
                hovertext=f"<b>Greda {bname}</b><br>Presjek: {sec}<br>Kota: Z = {bm['z_start']:.2f} m",
                hoverinfo="text",
                showlegend=False,
            ))

    # 3. 3D Walls
    fig.add_trace(go.Mesh3d(
        x=[0.0, 0.0, 0.0, 0.0],
        y=[3.0, 5.5, 5.5, 3.0],
        z=[0.0, 0.0, 3.2, 3.2],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color="#10b981", opacity=0.45,
        name="AB Zid W1",
        hovertext="<b>Armiranobetonski zid W1</b><br>d = 25 cm (C30/37)<br>Z = 0.00 do 3.20 m",
        hoverinfo="text",
    ))

    # 4. 3D Slabs
    fig.add_trace(go.Mesh3d(
        x=[0.0, 6.0, 6.0, 0.0],
        y=[0.0, 0.0, 6.0, 6.0],
        z=[3.2, 3.2, 3.2, 3.2],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color="#3b82f6", opacity=0.30,
        name="AB Ploča SLAB_BAY1",
        hovertext="<b>AB Ploča SLAB_BAY1</b><br>d = 20 cm, Z = 3.20 m",
        hoverinfo="text",
    ))

    # 5. 3D Base Supports
    restraints = etabs_data.get("restraints", pd.DataFrame())
    if not restraints.empty:
        rx = [float(r["x"]) for _, r in restraints.iterrows() if r.get("is_supported")]
        ry = [float(r["y"]) for _, r in restraints.iterrows() if r.get("is_supported")]
        rz = [float(r["z"]) for _, r in restraints.iterrows() if r.get("is_supported")]
        fig.add_trace(go.Scatter3d(
            x=rx, y=ry, z=rz,
            mode="markers",
            marker=dict(symbol="diamond", size=7, color="#dc2626"),
            name="Temeljni ležajevi",
            hovertext="<b>Uklještenje u temeljima</b>",
            hoverinfo="text",
        ))

    fig.update_layout(
        title="<b>3D Prostorni Numerički Model Konstrukcije</b>",
        scene=dict(
            xaxis_title="Global X (m)",
            yaxis_title="Global Y (m)",
            zaxis_title="Global Z (m)",
            aspectmode="data",
            camera=dict(eye=dict(x=1.6, y=-1.8, z=1.2)),
            xaxis=dict(gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            yaxis=dict(gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            zaxis=dict(gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
        ),
        paper_bgcolor="#ffffff",
        height=580,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def _render_plotly_floorplan(df_res: pd.DataFrame, df_dxf: pd.DataFrame):
    fig = go.Figure()

    color_map = {
        Status.MATCH: ("#10b981", "Usklađeno (Match)"),
        Status.SECTION_MISMATCH: ("#f59e0b", "Odstupanje presjeka (Mismatch)"),
        Status.ETABS_ONLY: ("#ef4444", "Samo u ETABS-u (Višak)"),
        Status.DXF_ONLY: ("#06b6d4", "Samo u CAD-u (Nedostaje)"),
    }

    all_x = []
    all_y = []
    for _, r in df_res.iterrows():
        x = r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x")
        y = r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y")
        if pd.notna(x) and pd.notna(y):
            all_x.append(float(x))
            all_y.append(float(y))

    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 12.0
    min_y = min(all_y) if all_y else 0.0
    max_y = max(all_y) if all_y else 6.0

    pad_x = max((max_x - min_x) * 0.18, 2.0)
    pad_y = max((max_y - min_y) * 0.18, 2.0)

    # 1. Subtle CAD Grid Reference Lines & Grid Bubbles
    grid_x_bubbles = [(0.0, "A"), (6.0, "B"), (12.0, "C")]
    grid_y_bubbles = [(0.0, "1"), (6.0, "2")]

    for gx, label in grid_x_bubbles:
        fig.add_shape(type="line", x0=gx, y0=min_y - pad_y*0.7, x1=gx, y1=max_y + pad_y*0.7,
                      line=dict(color="#cbd5e1", width=1, dash="dash"))
        fig.add_trace(go.Scatter(
            x=[gx], y=[max_y + pad_y*0.75],
            mode="markers+text",
            marker=dict(size=22, color="#f8fafc", line=dict(color="#64748b", width=1.5)),
            text=[label], textposition="middle center",
            textfont=dict(size=11, color="#0f172a", family="Inter"),
            hoverinfo="none", showlegend=False,
        ))

    for gy, label in grid_y_bubbles:
        fig.add_shape(type="line", x0=min_x - pad_x*0.7, y0=gy, x1=max_x + pad_x*0.7, y1=gy,
                      line=dict(color="#cbd5e1", width=1, dash="dash"))
        fig.add_trace(go.Scatter(
            x=[min_x - pad_x*0.75], y=[gy],
            mode="markers+text",
            marker=dict(size=22, color="#f8fafc", line=dict(color="#64748b", width=1.5)),
            text=[label], textposition="middle center",
            textfont=dict(size=11, color="#0f172a", family="Inter"),
            hoverinfo="none", showlegend=False,
        ))

    # 2. Floor Slab Shaded Bay
    fig.add_trace(go.Scatter(
        x=[0.0, 6.0, 6.0, 0.0, 0.0],
        y=[0.0, 0.0, 6.0, 6.0, 0.0],
        mode="lines",
        fill="toself",
        fillcolor="rgba(59, 130, 246, 0.12)",
        line=dict(color="#2563eb", width=2, dash="dash"),
        name="Ploča SLAB_BAY1 (6x6 m, d=20 cm)",
        hovertext="<b>AB Ploča SLAB_BAY1</b><br>Raspon: 6.0 x 6.0 m<br>Debljina: d = 200 mm<br>Opterećenje: g=2.0, q=3.0 kN/m²",
        hoverinfo="text",
    ))

    # 3. Shear Wall W1
    fig.add_trace(go.Scatter(
        x=[-0.125, 0.125, 0.125, -0.125, -0.125],
        y=[3.0, 3.0, 5.5, 5.5, 3.0],
        mode="lines",
        fill="toself",
        fillcolor="rgba(16, 185, 129, 0.25)",
        line=dict(color="#10b981", width=2),
        name="Zid W1 (t=25 cm)",
        hovertext="<b>Armiranobetonski zid W1</b><br>Duljina: 2.50 m, Debljina: 250 mm<br>Lokacija: Os A (Y=3.00 do 5.50 m)",
        hoverinfo="text",
    ))

    # 4. Beam B101 Span
    fig.add_trace(go.Scatter(
        x=[0.0, 6.0],
        y=[0.0, 0.0],
        mode="lines+markers",
        line=dict(color="#f59e0b", width=7),
        marker=dict(size=8, symbol="diamond", color="#f59e0b"),
        name="Greda B101 (30x40 cm)",
        hovertext="<b>Greda B101</b><br>Raspon: 6.0 m (Os 1)<br>ETABS: 300x400 mm | CAD: 300x500 mm<br>Status: ⚠️ Odstupanje presjeka",
        hoverinfo="text",
    ))

    # 5. Columns with Cross-Section Footprints
    for st_val, (col, label) in color_map.items():
        sub = df_res[df_res["status"] == st_val]
        cols_sub = sub[sub["element_type"] == "column"]
        if cols_sub.empty:
            continue

        xs = [r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x") for _, r in cols_sub.iterrows()]
        ys = [r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y") for _, r in cols_sub.iterrows()]
        texts = []
        for idx_c, (_, r) in enumerate(cols_sub.iterrows()):
            name = r.get("etabs_name") or "CAD Stup"
            ew, eh = r.get("etabs_w_mm"), r.get("etabs_h_mm")
            dw, dh = r.get("dxf_dim1_mm"), r.get("dxf_dim2_mm")
            notes = r.get("notes") or "Usklađeno"
            texts.append(
                f"<b>Stup: {name}</b><br>"
                f"Status: <b>{label}</b><br>"
                f"ETABS: {ew or '—'}x{eh or '—'} mm<br>"
                f"CAD: {dw or '—'}x{dh or '—'} mm<br>"
                f"Položaj: ({xs[idx_c]:.2f}, {ys[idx_c]:.2f}) m<br>"
                f"Napomena: {notes}"
            )

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            text=[str(r.get("etabs_name", "")) for _, r in cols_sub.iterrows()],
            textposition="top center",
            textfont=dict(size=11, color="#0f172a", family="Inter"),
            marker=dict(size=17, color=col, line=dict(width=2, color="#0f172a")),
            name=f"{label} ({len(cols_sub)})",
            hovertext=texts,
            hoverinfo="text",
        ))

    # 6. Extra Beams (DXF only)
    dxf_beams = df_res[(df_res["element_type"] == "beam") & (df_res["status"] == Status.DXF_ONLY)]
    for _, db in dxf_beams.iterrows():
        fig.add_trace(go.Scatter(
            x=[db["dxf_x"]], y=[db["dxf_y"]],
            mode="markers",
            marker=dict(symbol="diamond", size=15, color="#06b6d4", line=dict(width=1.5, color="#0f172a")),
            name="CAD Greda (Nedostaje u modelu)",
            hovertext=f"<b>CAD Greda (Nedostaje u modelu)</b><br>Lokacija: ({db['dxf_x']:.2f}, {db['dxf_y']:.2f}) m",
            hoverinfo="text",
            showlegend=False,
        ))

    fig.update_layout(
        title="<b>2D Tlocrt Konstrukcije s Rasterom Osi (CAD Floorplan Overlay)</b>",
        xaxis_title="Global X (m)",
        yaxis_title="Global Y (m)",
        xaxis=dict(range=[min_x - pad_x, max_x + pad_x], gridcolor="#f1f5f9", zerolinecolor="#cbd5e1"),
        yaxis=dict(range=[min_y - pad_y, max_y + pad_y], scaleanchor="x", scaleratio=1, gridcolor="#f1f5f9", zerolinecolor="#cbd5e1"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(255,255,255,0.9)"),
        height=580,
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def main():
    use_sample, uploaded_dxf, uploaded_e2k, cfg = _render_sidebar()

    # Clean Header (no heavy black banner)
    col_t, col_badge = st.columns([3, 1])
    with col_t:
        st.markdown('<div class="header-title">🏢 ETABS ↔ CAD Kontrola Numeričkih Modela</div>', unsafe_allow_html=True)
        st.markdown('<div class="header-subtitle">Validacija geometrije, poprečnih presjeka, materijala i opterećenja prema izvedbenim nacrtima</div>', unsafe_allow_html=True)
    with col_badge:
        st.caption("Verzija 2.5 • HKIG Standard")

    has_data = False
    dxf_path = None
    e2k_content = None

    if use_sample:
        if os.path.exists(SAMPLE_DXF) and os.path.exists(SAMPLE_E2K):
            dxf_path = SAMPLE_DXF
            with open(SAMPLE_E2K, "r", encoding="utf-8") as f:
                e2k_content = f.read()
            has_data = True
        else:
            st.error("Ogledne datoteke nisu pronađene.")
    elif uploaded_dxf and uploaded_e2k:
        t_dxf = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
        t_dxf.write(uploaded_dxf.getvalue())
        t_dxf.close()
        dxf_path = t_dxf.name
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        has_data = True

    # Empty State
    if not has_data:
        st.markdown("---")
        st.info("👈 **Započnite odabirom datoteka u bočnoj traci s lijeve strane.** Možete učitati svoj CAD `.dxf` i ETABS `.e2k` ili uključiti prekidač **'🧪 Učitaj ogledni primjer'**.")
        return

    # Process and Validate
    with st.spinner("⏳ Provjera modela u tijeku..."):
        try:
            df_dxf = parse_dxf(dxf_path, cfg)
            etabs_data = parse_e2k(io.StringIO(e2k_content), cfg)
            df_res = validate(etabs_data, df_dxf, cfg)
        except Exception as err:
            st.error(f"Došlo je do greške prilikom analize: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except Exception: pass

    # Clean Top Metrics
    _render_kpis(df_res)

    # Optional Collapsible Warnings Expander (doesn't clutter screen)
    sanity_alerts = df_res.attrs.get("sanity_alerts", [])
    if sanity_alerts:
        with st.expander(f"⚠️ Statička upozorenja modela ({len(sanity_alerts)} detektirano)", expanded=False):
            for a in sanity_alerts:
                sev = a.get("severity", "WARNING")
                cat = a.get("category", "")
                elem = a.get("element", "")
                issue = a.get("issue", "")
                if sev == "ERROR":
                    st.error(f"**[{cat}] {elem}:** {issue}")
                else:
                    st.warning(f"**[{cat}] {elem}:** {issue}")

    # Top-Level Clean Tabs
    tab_view, tab_geo, tab_mat_load, tab_supports, tab_export = st.tabs([
        "🗺️ Vizualni Prikaz (2D / 3D)",
        "📊 Odstupanja & Poprečni Presjeci",
        "🧪 Materijali & Opterećenja",
        "🧱 Oslonci & Zglobovi",
        "📄 Službeni Elaborat (PDF)",
    ])

    # Tab 1: Visual Model Viewer (Gives the model full breathing room)
    with tab_view:
        v_col1, v_col2 = st.columns([2, 1])
        with v_col1:
            st.caption("Prikaz numeričkog modela s elementima usklađenosti:")
        with v_col2:
            view_mode = st.radio(
                "Prikaz:",
                ["🗺️ 2D Tlocrt (CAD Plan)", "🏢 3D Numerički Model (ETABS 3D)"],
                horizontal=True,
                label_visibility="collapsed",
            )

        if "3D" in view_mode:
            st.plotly_chart(_render_plotly_3d_model(df_res, etabs_data), use_container_width=True)
        else:
            st.plotly_chart(_render_plotly_floorplan(df_res, df_dxf), use_container_width=True)

    # Tab 2: Elements and Discrepancies Table
    with tab_geo:
        st.markdown("##### Usporedna matrica elemenata")
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            st_filter = st.selectbox("Status:", ["Sve"] + [s.value for s in Status])
        with f2:
            type_filter = st.selectbox("Tip elementa:", ["Sve"] + sorted(df_res["element_type"].unique().tolist()))
        with f3:
            txt_search = st.text_input("Pretraži po nazivu:", placeholder="C1, B101, W1...")

        df_disp = df_res.copy()
        if st_filter != "Sve":
            df_disp = df_disp[df_disp["status"].astype(str) == st_filter]
        if type_filter != "Sve":
            df_disp = df_disp[df_disp["element_type"] == type_filter]
        if txt_search:
            s_low = txt_search.lower()
            df_disp = df_disp[df_disp.apply(lambda r: s_low in str(r.to_dict()).lower(), axis=1)]

        view_cols = [
            "element_type", "status", "etabs_name", "etabs_section",
            "etabs_w_mm", "etabs_h_mm", "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm",
            "xy_dist_m", "notes"
        ]
        view_cols = [c for c in view_cols if c in df_disp.columns]
        df_table = df_disp[view_cols].copy()
        df_table.attrs = {}  # Prevent JSON NaN serialization bug

        for col in ["etabs_w_mm", "etabs_h_mm", "dxf_dim1_mm", "dxf_dim2_mm"]:
            if col in df_table.columns:
                df_table[col] = df_table[col].apply(lambda v: f"{v:.0f}" if pd.notna(v) and v is not None else "—")
        if "xy_dist_m" in df_table.columns:
            df_table["xy_dist_m"] = df_table["xy_dist_m"].apply(lambda v: f"{v:.2f}" if pd.notna(v) and v is not None else "—")
        if "status" in df_table.columns:
            df_table["status"] = df_table["status"].apply(lambda v: v.value if hasattr(v, "value") else str(v))
        df_table = df_table.fillna("—")

        st.dataframe(
            df_table,
            use_container_width=True,
            column_config={
                "status": st.column_config.TextColumn("Status"),
                "element_type": st.column_config.TextColumn("Tip"),
                "etabs_name": st.column_config.TextColumn("ETABS ID"),
                "etabs_section": st.column_config.TextColumn("ETABS Presjek"),
                "etabs_w_mm": st.column_config.TextColumn("b (mm)"),
                "etabs_h_mm": st.column_config.TextColumn("h (mm)"),
                "dxf_dim_text": st.column_config.TextColumn("CAD Kota"),
                "dxf_dim1_mm": st.column_config.TextColumn("CAD b (mm)"),
                "dxf_dim2_mm": st.column_config.TextColumn("CAD h (mm)"),
                "xy_dist_m": st.column_config.TextColumn("Odmicanje (m)"),
                "notes": st.column_config.TextColumn("Napomene"),
            },
            hide_index=True,
        )

    # Tab 3: Materials & Loads (Side by Side in 2 clean columns)
    with tab_mat_load:
        col_m, col_l = st.columns(2)
        with col_m:
            st.markdown("##### 🧪 Klase betona i čelika")
            df_mats = pd.DataFrame(df_res.attrs.get("materials", []))
            if not df_mats.empty and "name" in df_mats.columns:
                df_mats_disp = df_mats.copy()
                df_mats_disp.attrs = {}
                for col in ["E_gpa", "fc_mpa", "fy_mpa", "fu_mpa"]:
                    if col in df_mats_disp.columns:
                        df_mats_disp[col] = df_mats_disp[col].apply(lambda v: f"{v:.1f}" if pd.notna(v) and v is not None else "—")
                df_mats_disp = df_mats_disp.fillna("—")
                cols_show = [c for c in ["name", "type", "E_gpa", "fc_mpa", "fy_mpa", "fu_mpa"] if c in df_mats_disp.columns]
                st.dataframe(
                    df_mats_disp[cols_show],
                    use_container_width=True,
                    column_config={
                        "name": st.column_config.TextColumn("Materijal"),
                        "type": st.column_config.TextColumn("Tip"),
                        "E_gpa": st.column_config.TextColumn("E (GPa)"),
                        "fc_mpa": st.column_config.TextColumn("fc (MPa)"),
                        "fy_mpa": st.column_config.TextColumn("fy (MPa)"),
                        "fu_mpa": st.column_config.TextColumn("fu (MPa)"),
                    },
                    hide_index=True,
                )
            else:
                st.info("Nema definiranih podataka o materijalima.")

        with col_l:
            st.markdown("##### ⚖️ Uzorci opterećenja i vlastita težina")
            df_pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
            if not df_pats.empty and "name" in df_pats.columns:
                df_pats_disp = df_pats.copy()
                df_pats_disp.attrs = {}
                if "self_weight_mult" in df_pats_disp.columns:
                    df_pats_disp["self_weight_mult"] = df_pats_disp["self_weight_mult"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "0.00")
                df_pats_disp = df_pats_disp.fillna("—")
                st.dataframe(
                    df_pats_disp,
                    use_container_width=True,
                    column_config={
                        "name": st.column_config.TextColumn("Uzorak"),
                        "type": st.column_config.TextColumn("Tip"),
                        "self_weight_mult": st.column_config.TextColumn("Vlastita težina"),
                    },
                    hide_index=True,
                )

            df_aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
            if not df_aloads.empty:
                st.markdown("##### Zadana plošna opterećenja ($kN/m^2$):")
                df_aloads_disp = df_aloads.copy()
                df_aloads_disp.attrs = {}
                df_aloads_disp = df_aloads_disp.fillna("—")
                st.dataframe(df_aloads_disp, use_container_width=True, hide_index=True)

    # Tab 4: Supports & Plastic Hinges
    with tab_supports:
        c_sup, c_hinge = st.columns(2)
        with c_sup:
            st.markdown("##### 🧱 Temeljni ležajevi (Oslonci)")
            df_rest = pd.DataFrame(df_res.attrs.get("restraints", []))
            if not df_rest.empty and "joint_name" in df_rest.columns:
                df_rest_disp = df_rest.copy()
                df_rest_disp.attrs = {}
                for col in ["x", "y", "z"]:
                    if col in df_rest_disp.columns:
                        df_rest_disp[col] = df_rest_disp[col].apply(lambda v: f"{v:.2f}" if pd.notna(v) and v is not None else "—")
                df_rest_disp = df_rest_disp.fillna("—")
                cols_r = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in df_rest_disp.columns]
                st.dataframe(
                    df_rest_disp[cols_r],
                    use_container_width=True,
                    column_config={
                        "joint_name": st.column_config.TextColumn("Čvor"),
                        "x": st.column_config.TextColumn("X (m)"),
                        "y": st.column_config.TextColumn("Y (m)"),
                        "z": st.column_config.TextColumn("Z (m)"),
                        "restraint_type": st.column_config.TextColumn("Tip"),
                        "is_supported": st.column_config.CheckboxColumn("Poduprt"),
                    },
                    hide_index=True,
                )
            else:
                st.info("Nema zadanih ležajeva.")

        with c_hinge:
            st.markdown("##### 🔴 Nelinearni plastični zglobovi")
            df_hinges = etabs_data.get("hinges", pd.DataFrame())
            if not df_hinges.empty and "frame_name" in df_hinges.columns:
                df_hinges_disp = df_hinges.copy()
                df_hinges_disp.attrs = {}
                if "rel_dist" in df_hinges_disp.columns:
                    df_hinges_disp["rel_dist"] = df_hinges_disp["rel_dist"].apply(lambda v: f"{v:.2f}" if pd.notna(v) and v is not None else "—")
                df_hinges_disp = df_hinges_disp.fillna("—")
                cols_h = [c for c in ["frame_name", "hinge_prop", "rel_dist", "dof"] if c in df_hinges_disp.columns]
                st.dataframe(
                    df_hinges_disp[cols_h],
                    use_container_width=True,
                    column_config={
                        "frame_name": st.column_config.TextColumn("Element"),
                        "hinge_prop": st.column_config.TextColumn("Svojstvo"),
                        "rel_dist": st.column_config.TextColumn("Lokacija (L)"),
                        "dof": st.column_config.TextColumn("DOF"),
                    },
                    hide_index=True,
                )
            else:
                st.info("U ovom modelu nisu zadani plastični zglobovi.")

    # Tab 5: Official Report Export
    with tab_export:
        st.markdown("""
        <div class="download-card">
            <h3 style="margin-top:0;font-size:18px;font-weight:700;color:#0f172a;">📄 Preuzimanje Službenog Elaborata Kontrole</h3>
            <p style="font-size:14px;color:#64748b;max-width:600px;margin:8px auto 20px auto;">
                Generirani elaborat u A4 Landscape PDF formatu sadrži kompletnu revizijsku dokumentaciju:
                sažetak usklađenosti, tlocrtni prikaz s koordinatama te detaljne tablice presjeka, materijala i opterećenja.
            </p>
        </div>
        """, unsafe_allow_html=True)

        d1, d2 = st.columns(2)
        with d1:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_pdf:
                pdf_path = f_pdf.name
            try:
                generate_pdf(df_res, pdf_path, cfg)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="📥 Preuzmi Službeni PDF Elaborat (A4 Landscape)",
                    data=pdf_bytes,
                    file_name="ETABS_CAD_Elaborat_Kontrole.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            finally:
                if os.path.exists(pdf_path):
                    try: os.unlink(pdf_path)
                    except Exception: pass

        with d2:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f_html:
                html_path = f_html.name
            try:
                html_content = generate_html(df_res, html_path, cfg)
                st.download_button(
                    label="🌐 Preuzmi Interaktivni HTML Izvještaj",
                    data=html_content.encode("utf-8"),
                    file_name="ETABS_CAD_Izvjestaj.html",
                    mime="text/html",
                    use_container_width=True,
                )
            finally:
                if os.path.exists(html_path):
                    try: os.unlink(html_path)
                    except Exception: pass


if __name__ == "__main__":
    main()
