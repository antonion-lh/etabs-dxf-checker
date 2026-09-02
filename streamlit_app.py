"""
streamlit_app.py
----------------
Enterprise Web Application for Automated Structural ETABS v23 ↔ DXF Cross-Validation.
Zero-installation for end users — runs directly in the web browser on Streamlit Cloud.
Audits:
  1. Geometrija (Geometry): coordinates, grids, spans, floor elevations
  2. Poprečni presjeci (Cross-sections): true dimensions from section definitions
  3. Materijali (Materials): concrete & steel grades, E modulus, fc, fy
  4. Opterećenja (Loads & Equilibrium): self-weight multipliers, slab uniform surface loads
  5. Oslonci / Ležajevi (Supports): base boundary conditions, floating joint detection
  6. Nelinearnosti (Plastic Hinges): frame hinge assignments and DOFs
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
# Page configuration & Custom Styling
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

CUSTOM_CSS = """
<style>
/* Modern Typography & Base Spacing */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Hero Header Banner */
.hero-banner {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 24px 32px;
    border-radius: 14px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.12);
    border: 1px solid #334155;
}
.hero-badge {
    background: #2563eb;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 10px;
    border-radius: 999px;
    display: inline-block;
    margin-bottom: 8px;
}
.hero-title {
    font-size: 26px;
    font-weight: 700;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
}
.hero-subtitle {
    font-size: 14px;
    color: #94a3b8;
    margin: 0;
    line-height: 1.5;
}

/* Stat KPI Cards */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
}
.kpi-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border-left: 4px solid #cbd5e1;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.06);
}
.kpi-card.match { border-left-color: #10b981; }
.kpi-card.mismatch { border-left-color: #f59e0b; }
.kpi-card.etabs { border-left-color: #ef4444; }
.kpi-card.dxf { border-left-color: #06b6d4; }
.kpi-title {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.1;
}
.kpi-meta {
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
}
.kpi-meta.match { color: #10b981; }
.kpi-meta.mismatch { color: #d97706; }
.kpi-meta.etabs { color: #dc2626; }
.kpi-meta.dxf { color: #0891b2; }

/* Workflow Steps */
.stepper-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 24px;
}
.step-item {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    height: 100%;
}
.step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: #2563eb;
    color: #ffffff;
    font-weight: 700;
    font-size: 13px;
    border-radius: 50%;
    margin-bottom: 8px;
}

/* Callout Box for Sanity Alerts */
.sanity-alert-box {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-left: 5px solid #f59e0b;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 20px;
}

/* Action Toolbar */
.action-box {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 18px 24px;
    margin-top: 24px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _render_sidebar():
    with st.sidebar:
        st.markdown("### 🏢 Postavke i Ulaz")
        st.caption("ETABS v23 ↔ 2D CAD Kontrola Modela")
        st.markdown("---")

        st.subheader("1. Odabir datoteka")
        use_sample = st.toggle("🧪 Učitaj ogledni primjer (Demo)", value=False, help="Trenutni test s gotovim modelom i nacrtom zgrade.")

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

        with st.expander("⚙️ Prilagodi dozvoljena odstupanja"):
            tol_frame = st.slider("Položaj stupova / greda", 0.05, 0.40, 0.15, 0.01, format="%.2f m")
            tol_area = st.slider("Položaj zidova / ploča", 0.10, 0.80, 0.30, 0.05, format="%.2f m")
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
        st.caption("Razvijeno za inženjere konstrukcija • ETABS v23 OAPI standard")

    return use_sample, uploaded_dxf, uploaded_e2k, cfg


def _render_hero():
    st.markdown("""
    <div class="hero-banner">
        <div class="hero-badge">Enterprise Structural QA • v2.5</div>
        <h1 class="hero-title">Automatizirana Kontrola Numeričkih Modela (ETABS ↔ CAD)</h1>
        <p class="hero-subtitle">
            Usporedna provjera geometrije, poprečnih presjeka, specifikacije materijala, uzoraka opterećenja i rubnih uvjeta
            između ETABS v23 numeričkog modela i izvedbene 2D CAD dokumentacije.
        </p>
    </div>
    """, unsafe_allow_html=True)


def _render_kpis(df_res: pd.DataFrame):
    counts = df_res["status"].value_counts()
    n_match = counts.get(Status.MATCH, 0)
    n_mismatch = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs_only = counts.get(Status.ETABS_ONLY, 0)
    n_dxf_only = counts.get(Status.DXF_ONLY, 0)
    n_total = len(df_res)
    pct_match = round((n_match / max(n_total, 1)) * 100)

    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card match">
            <div class="kpi-title">Usklađeni elementi</div>
            <div class="kpi-value">{n_match}</div>
            <div class="kpi-meta match">✓ {pct_match}% ukupnog modela</div>
        </div>
        <div class="kpi-card mismatch">
            <div class="kpi-title">Odstupanje presjeka</div>
            <div class="kpi-value">{n_mismatch}</div>
            <div class="kpi-meta mismatch">{'⚠️ Provjeriti dimenzije' if n_mismatch > 0 else '✓ Sve usklađeno'}</div>
        </div>
        <div class="kpi-card etabs">
            <div class="kpi-title">Samo u ETABS-u</div>
            <div class="kpi-value">{n_etabs_only}</div>
            <div class="kpi-meta etabs">{'Element viška u modelu' if n_etabs_only > 0 else '✓ Nema viška'}</div>
        </div>
        <div class="kpi-card dxf">
            <div class="kpi-title">Samo u CAD-u</div>
            <div class="kpi-value">{n_dxf_only}</div>
            <div class="kpi-meta dxf">{'Nije uneseno u model' if n_dxf_only > 0 else '✓ Sve uneseno'}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Ukupno pregledano</div>
            <div class="kpi-value">{n_total}</div>
            <div class="kpi-meta" style="color:#64748b;">Analizirano u 5 domena</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_plotly_floorplan(df_res: pd.DataFrame, df_dxf: pd.DataFrame):
    fig = go.Figure()

    color_map = {
        Status.MATCH: ("#10b981", "Usklađeno (Match)"),
        Status.SECTION_MISMATCH: ("#f59e0b", "Odstupanje presjeka (Section Mismatch)"),
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

    # Subtle CAD Grid reference lines
    for gx in [0.0, 6.0, 12.0]:
        fig.add_shape(type="line", x0=gx, y0=min_y - pad_y*0.7, x1=gx, y1=max_y + pad_y*0.7,
                      line=dict(color="#e2e8f0", width=1, dash="dash"))
    for gy in [0.0, 6.0]:
        fig.add_shape(type="line", x0=min_x - pad_x*0.7, y0=gy, x1=max_x + pad_x*0.7, y1=gy,
                      line=dict(color="#e2e8f0", width=1, dash="dash"))

    # Plot floor outline / slab polygons first for backdrop
    slabs = df_res[df_res["element_type"] == "slab"]
    for _, s in slabs.iterrows():
        sx = s.get("etabs_x") if pd.notna(s.get("etabs_x")) else s.get("dxf_x")
        sy = s.get("etabs_y") if pd.notna(s.get("etabs_y")) else s.get("dxf_y")
        fig.add_trace(go.Scatter(
            x=[sx], y=[sy],
            mode="markers",
            marker=dict(size=28, symbol="square", color="rgba(59, 130, 246, 0.15)", line=dict(color="#2563eb", width=1.5)),
            name="Ploča (Slab Contour)",
            hovertext=f"<b>Ploča: {s.get('etabs_name','SLAB')}</b><br>Debljina: {s.get('etabs_h_mm', 200):.0f} mm<br>Koordinate: ({sx:.2f}, {sy:.2f}) m",
            hoverinfo="text",
            showlegend=False,
        ))

    # Plot columns and walls by status
    for st_val, (col, label) in color_map.items():
        sub = df_res[df_res["status"] == st_val]
        if sub.empty:
            continue

        # Columns
        cols_sub = sub[sub["element_type"] == "column"]
        if not cols_sub.empty:
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
                    f"ETABS model: {ew or '—'}x{eh or '—'} mm<br>"
                    f"CAD nacrt: {dw or '—'}x{dh or '—'} mm<br>"
                    f"Položaj: ({xs[idx_c]:.2f}, {ys[idx_c]:.2f}) m<br>"
                    f"Napomena: {notes}"
                )

            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers+text",
                text=[str(r.get("etabs_name", "")) for _, r in cols_sub.iterrows()],
                textposition="top center",
                textfont=dict(size=11, color="#0f172a", family="Inter"),
                marker=dict(size=15, color=col, line=dict(width=2, color="#0f172a")),
                name=f"{label} ({len(cols_sub)})",
                hovertext=texts,
                hoverinfo="text",
            ))

        # Beams
        beams_sub = sub[sub["element_type"] == "beam"]
        for _, br in beams_sub.iterrows():
            bx = br.get("etabs_x") if pd.notna(br.get("etabs_x")) else br.get("dxf_x")
            by = br.get("etabs_y") if pd.notna(br.get("etabs_y")) else br.get("dxf_y")
            bname = br.get("etabs_name") or "CAD Greda"
            fig.add_trace(go.Scatter(
                x=[bx], y=[by],
                mode="markers",
                marker=dict(symbol="diamond", size=16, color=col, line=dict(width=1.5, color="#0f172a")),
                name=f"Greda: {bname}",
                hovertext=f"<b>Greda: {bname}</b><br>Status: {label}<br>ETABS: {br.get('etabs_w_mm','—')}x{br.get('etabs_h_mm','—')} mm<br>CAD: {br.get('dxf_dim_text','—')}<br>Napomena: {br.get('notes','')}",
                hoverinfo="text",
                showlegend=False,
            ))

        # Walls
        walls_sub = sub[sub["element_type"] == "wall"]
        for _, wr in walls_sub.iterrows():
            wx = wr.get("etabs_x") if pd.notna(wr.get("etabs_x")) else wr.get("dxf_x")
            wy = wr.get("etabs_y") if pd.notna(wr.get("etabs_y")) else wr.get("dxf_y")
            wname = wr.get("etabs_name") or "CAD Zid"
            fig.add_trace(go.Scatter(
                x=[wx], y=[wy],
                mode="markers",
                marker=dict(symbol="cross", size=18, color=col, line=dict(width=2.5, color="#0f172a")),
                name=f"Zid: {wname}",
                hovertext=f"<b>Armiranobetonski zid: {wname}</b><br>Status: {label}<br>Debljina: {wr.get('etabs_h_mm', 250):.0f} mm<br>Položaj: ({wx:.2f}, {wy:.2f}) m",
                hoverinfo="text",
                showlegend=False,
            ))

    fig.update_layout(
        title="<b>Interaktivni 2D Tlocrt Konstrukcije (Model Coordinate Overlay)</b>",
        xaxis_title="Global X (m)",
        yaxis_title="Global Y (m)",
        xaxis=dict(
            range=[min_x - pad_x, max_x + pad_x],
            gridcolor="#f1f5f9",
            zerolinecolor="#cbd5e1",
        ),
        yaxis=dict(
            range=[min_y - pad_y, max_y + pad_y],
            scaleanchor="x",
            scaleratio=1,
            gridcolor="#f1f5f9",
            zerolinecolor="#cbd5e1",
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(255,255,255,0.9)"),
        height=580,
        margin=dict(l=30, r=30, t=60, b=30),
    )
    return fig


def main():
    _render_hero()
    use_sample, uploaded_dxf, uploaded_e2k, cfg = _render_sidebar()

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
            st.error("Ogledne datoteke nisu pronađene na poslužitelju.")
    elif uploaded_dxf and uploaded_e2k:
        t_dxf = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
        t_dxf.write(uploaded_dxf.getvalue())
        t_dxf.close()
        dxf_path = t_dxf.name
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        has_data = True

    # Empty State: Guidance Walkthrough
    if not has_data:
        st.markdown("""
        <div class="stepper-box">
            <h3 style="margin-top:0;font-size:16px;font-weight:700;color:#1e293b;">Kako funkcionira kontrola u 3 jednostavna koraka:</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:16px;margin-top:14px;">
                <div class="step-item">
                    <div class="step-number">1</div>
                    <div style="font-weight:700;font-size:14px;color:#0f172a;margin-bottom:6px;">Izvoz iz ETABS-a (3 sec)</div>
                    <div style="font-size:13px;color:#64748b;line-height:1.4;">
                        U programu ETABS v23 otvorite model i kliknite:
                        <code style="display:block;margin-top:6px;padding:4px 8px;background:#f1f5f9;border-radius:6px;">File ➔ Export ➔ ETABS .e2k Text File...</code>
                    </div>
                </div>
                <div class="step-item">
                    <div class="step-number">2</div>
                    <div style="font-weight:700;font-size:14px;color:#0f172a;margin-bottom:6px;">Učitavanje datoteka</div>
                    <div style="font-size:13px;color:#64748b;line-height:1.4;">
                        U lijevom izborniku priložite <b>.dxf nacrt</b> i izvezenu <b>.e2k datoteku</b> modela.
                    </div>
                </div>
                <div class="step-item">
                    <div class="step-number">3</div>
                    <div style="font-weight:700;font-size:14px;color:#0f172a;margin-bottom:6px;">Trenutni uvid i PDF</div>
                    <div style="font-size:13px;color:#64748b;line-height:1.4;">
                        Pregledajte 2D tlocrt, provjerite materijale i opterećenja te jednim klikom preuzmite gotov <b>PDF elaborat kontrole</b>.
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.info("💡 **Želite odmah isprobati aplikaciju?** U lijevom izborniku uključite prekidač **'🧪 Učitaj ogledni primjer (Demo)'**.")
        return

    # Process and Validate
    with st.spinner("⏳ Provjera geometrije, presjeka, materijala i opterećenja..."):
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

    # Render High-level KPIs
    _render_kpis(df_res)

    # Sanity Alerts Callout Box
    sanity_alerts = df_res.attrs.get("sanity_alerts", [])
    if sanity_alerts:
        alert_items = []
        for a in sanity_alerts:
            sev = a.get("severity", "WARNING")
            cat = a.get("category", "")
            elem = a.get("element", "")
            issue = a.get("issue", "")
            badge_color = "#dc2626" if sev == "ERROR" else "#d97706"
            alert_items.append(
                f"<div style='margin-bottom:8px;font-size:13px;'>"
                f"<span style='background:{badge_color};color:white;padding:2px 8px;border-radius:4px;font-weight:700;font-size:11px;'>{sev}</span> "
                f"<b>[{cat}] {elem}:</b> {issue}</div>"
            )
        st.markdown(f"""
        <div class="sanity-alert-box">
            <div style="font-weight:700;font-size:14px;color:#92400e;margin-bottom:8px;">
                ⚠️ Upozorenja statičke ispravnosti modela ({len(sanity_alerts)} detektirano):
            </div>
            {''.join(alert_items)}
        </div>
        """, unsafe_allow_html=True)

    # Interactive CAD Visualizer
    st.plotly_chart(_render_plotly_floorplan(df_res, df_dxf), use_container_width=True)

    # Tabbed Deep-Dive Tables
    st.markdown("### 📋 Detaljni elaborat po poglavljima")
    tab_geo, tab_mat, tab_load, tab_rest, tab_hinge = st.tabs([
        "📐 1. Geometrija & Poprečni presjeci",
        "🧪 2. Materijali (fc, fy, E)",
        "⚖️ 3. Opterećenja & Vlastita težina",
        "🧱 4. Oslonci / Ležajevi",
        "🔴 5. Plastični zglobovi",
    ])

    # Tab 1: Geometry & Sections
    with tab_geo:
        st.markdown("##### Usporedna matrica elemenata")
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            st_filter = st.selectbox("Status usklađenosti:", ["Sve"] + [s.value for s in Status])
        with f2:
            type_filter = st.selectbox("Tip elementa:", ["Sve"] + sorted(df_res["element_type"].unique().tolist()))
        with f3:
            txt_search = st.text_input("Pretraži po oznaci (ID ili profil):", placeholder="npr. C1, BM_30x40, 40x50...")

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

        # Format numerical fields to string to eliminate JSON NaN serialization issues
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
                "notes": st.column_config.TextColumn("Napomene o odstupanjima"),
            },
            hide_index=True,
        )

    # Tab 2: Materials
    with tab_mat:
        st.markdown("##### 🧪 Klase betona i čelika zadane u numeričkom modelu")
        df_mats = pd.DataFrame(df_res.attrs.get("materials", []))
        if not df_mats.empty and "name" in df_mats.columns:
            df_mats_disp = df_mats.copy()
            for col in ["E_gpa", "fc_mpa", "fy_mpa", "fu_mpa"]:
                if col in df_mats_disp.columns:
                    df_mats_disp[col] = df_mats_disp[col].apply(lambda v: f"{v:.1f}" if pd.notna(v) and v is not None else "—")
            df_mats_disp = df_mats_disp.fillna("—")
            cols_show = [c for c in ["name", "type", "E_gpa", "fc_mpa", "fy_mpa", "fu_mpa"] if c in df_mats_disp.columns]
            st.dataframe(
                df_mats_disp[cols_show],
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Naziv materijala"),
                    "type": st.column_config.TextColumn("Kategorija"),
                    "E_gpa": st.column_config.TextColumn("Modul elastičnosti E (GPa)"),
                    "fc_mpa": st.column_config.TextColumn("Tlačna čvrstoća fc (MPa)"),
                    "fy_mpa": st.column_config.TextColumn("Granica popuštanja fy (MPa)"),
                    "fu_mpa": st.column_config.TextColumn("Vlačna čvrstoća fu (MPa)"),
                },
                hide_index=True,
            )
        else:
            st.info("Nema definiranih podataka o materijalima.")

    # Tab 3: Loads
    with tab_load:
        st.markdown("##### ⚖️ Uzorci opterećenja i provjera dvostrukog uračunavanja vlastite težine")
        df_pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
        if not df_pats.empty and "name" in df_pats.columns:
            df_pats_disp = df_pats.copy()
            if "self_weight_mult" in df_pats_disp.columns:
                df_pats_disp["self_weight_mult"] = df_pats_disp["self_weight_mult"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "0.00")
            df_pats_disp = df_pats_disp.fillna("—")
            st.dataframe(
                df_pats_disp,
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Uzorak"),
                    "type": st.column_config.TextColumn("Tip"),
                    "self_weight_mult": st.column_config.TextColumn("Faktor vlastite težine (1.0=Dead, 0.0=ostalo)"),
                },
                hide_index=True,
            )

        df_aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
        if not df_aloads.empty:
            st.markdown("##### Zadana plošna opterećenja na pločama ($kN/m^2$):")
            df_aloads_disp = df_aloads.copy().fillna("—")
            st.dataframe(df_aloads_disp, use_container_width=True, hide_index=True)

    # Tab 4: Restraints
    with tab_rest:
        st.markdown("##### 🧱 Temeljni ležajevi i rubni uvjeti (Boundary Restraints)")
        df_rest = pd.DataFrame(df_res.attrs.get("restraints", []))
        if not df_rest.empty and "joint_name" in df_rest.columns:
            df_rest_disp = df_rest.copy()
            for col in ["x", "y", "z"]:
                if col in df_rest_disp.columns:
                    df_rest_disp[col] = df_rest_disp[col].apply(lambda v: f"{v:.2f}" if pd.notna(v) and v is not None else "—")
            df_rest_disp = df_rest_disp.fillna("—")
            cols_r = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in df_rest_disp.columns]
            st.dataframe(
                df_rest_disp[cols_r],
                use_container_width=True,
                column_config={
                    "joint_name": st.column_config.TextColumn("Čvor (Joint ID)"),
                    "x": st.column_config.TextColumn("X (m)"),
                    "y": st.column_config.TextColumn("Y (m)"),
                    "z": st.column_config.TextColumn("Z (m)"),
                    "restraint_type": st.column_config.TextColumn("Tip ležaja"),
                    "is_supported": st.column_config.CheckboxColumn("Poduprt"),
                },
                hide_index=True,
            )
        else:
            st.info("Nema zadanih ležajeva u prizemlju.")

    # Tab 5: Plastic Hinges
    with tab_hinge:
        st.markdown("##### 🔴 Nelinearni plastični zglobovi (Frame Plastic Hinges)")
        df_hinges = etabs_data.get("hinges", pd.DataFrame())
        if not df_hinges.empty and "frame_name" in df_hinges.columns:
            df_hinges_disp = df_hinges.copy()
            if "rel_dist" in df_hinges_disp.columns:
                df_hinges_disp["rel_dist"] = df_hinges_disp["rel_dist"].apply(lambda v: f"{v:.2f}" if pd.notna(v) and v is not None else "—")
            df_hinges_disp = df_hinges_disp.fillna("—")
            cols_h = [c for c in ["frame_name", "hinge_prop", "rel_dist", "dof"] if c in df_hinges_disp.columns]
            st.dataframe(
                df_hinges_disp[cols_h],
                use_container_width=True,
                column_config={
                    "frame_name": st.column_config.TextColumn("Element (Frame ID)"),
                    "hinge_prop": st.column_config.TextColumn("Tip zgloba (Property)"),
                    "rel_dist": st.column_config.TextColumn("Relativna pozicija (L)"),
                    "dof": st.column_config.TextColumn("Stupanj slobode"),
                },
                hide_index=True,
            )
        else:
            st.info("U ovom modelu nisu zadani plastični zglobovi.")

    # Download Action Bar
    st.markdown("""
    <div class="action-box">
        <h4 style="margin-top:0;font-size:16px;font-weight:700;color:#0f172a;">📥 Preuzimanje Službenih Elaborata Kontrole</h4>
        <p style="font-size:13px;color:#64748b;margin:0 0 14px 0;">
            Generirani dokumenti sadrže naslovnicu, sažetak odstupanja, tlocrtni prikaz i detaljna poglavlja za reviziju projekta.
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
                label="📄 Preuzmi Službeni PDF Elaborat (A4 Landscape)",
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
