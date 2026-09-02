"""
streamlit_app.py — ETABS ↔ CAD Automated Structural QA Platform
Professional engineering SaaS UI: clean sections, large chart area, no clutter.
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
    page_title="ETABS ↔ CAD — Kontrola Modela",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

# ─────────────────────────────────────────────────────────────
# CSS  —  one focused block, no overrides
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
.block-container { padding: 1.5rem 2rem 2rem 2rem !important; max-width: 1440px; }

/* ─── Sidebar ─── */
[data-testid="stSidebar"] {
    background: #0f172a;
    border-right: none;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stCheckbox label,
[data-testid="stSidebar"] .stSlider label { color: #94a3b8 !important; font-size: 12px; }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #f1f5f9 !important; }
[data-testid="stSidebar"] hr { border-color: #334155 !important; }

/* ─── Header ─── */
.app-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 0 20px 0;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 24px;
}
.app-header-icon { font-size: 36px; line-height: 1; }
.app-header-title { font-size: 22px; font-weight: 800; color: #0f172a; letter-spacing: -0.03em; margin: 0; }
.app-header-sub { font-size: 13px; color: #64748b; margin: 2px 0 0 0; }
.app-version-badge {
    margin-left: auto;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
}

/* ─── KPI row ─── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 28px;
}
.kpi-card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 18px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 12px 12px 0 0;
}
.kpi-card.green::before  { background: #10b981; }
.kpi-card.amber::before  { background: #f59e0b; }
.kpi-card.red::before    { background: #ef4444; }
.kpi-card.blue::before   { background: #3b82f6; }
.kpi-card.slate::before  { background: #64748b; }
.kpi-label { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
.kpi-number { font-size: 30px; font-weight: 800; color: #0f172a; line-height: 1; }
.kpi-sub { font-size: 11px; color: #94a3b8; margin-top: 4px; }

/* ─── Section dividers ─── */
.section-title {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 28px 0 12px 0;
}

/* ─── Warning pills ─── */
.warn-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #fef9c3;
    border: 1px solid #fde047;
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
    background: #fee2e2;
    border: 1px solid #fca5a5;
    color: #991b1b;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 6px;
    margin-bottom: 6px;
}

/* ─── Empty state ─── */
.empty-state {
    text-align: center;
    padding: 80px 20px;
    color: #94a3b8;
}
.empty-state h2 { color: #0f172a; font-size: 20px; margin-bottom: 8px; }
.empty-state p { font-size: 14px; max-width: 420px; margin: 0 auto 24px auto; }

/* ─── Download card ─── */
.dl-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
}
.dl-card h3 { font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 8px 0; }
.dl-card p { font-size: 13px; color: #64748b; max-width: 480px; margin: 0 auto 20px auto; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
def _sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## 🏗️ ETABS↔CAD QA")
        st.caption("Kontrola numeričkog modela")
        st.markdown("---")

        st.markdown("### Ulazni podaci")
        use_sample = st.toggle("🧪 Demo ogledni primjer", value=False,
                               help="Učitaj gotov model i nacrt za testiranje.")
        uploaded_dxf = uploaded_e2k = None
        if not use_sample:
            uploaded_dxf = st.file_uploader("CAD nacrt (.dxf)", type=["dxf"])
            uploaded_e2k = st.file_uploader("ETABS model (.e2k)", type=["e2k", "$et", "txt"])

        st.markdown("---")
        st.markdown("### Mjerne jedinice")
        scale_label = st.selectbox("Jedinica u DXF-u:", [
            "Centimetri (cm)", "Milimetri (mm)", "Metri (m)"
        ])
        scale_map = {"Centimetri (cm)": 0.01, "Milimetri (mm)": 0.001, "Metri (m)": 1.0}
        unit_scale = scale_map[scale_label]

        with st.expander("⚙️ Dozvoljena odstupanja"):
            tol_frame = st.slider("Stupovi/grede (m)", 0.05, 0.40, 0.15, 0.01)
            tol_area  = st.slider("Zidovi/ploče (m)",  0.10, 0.80, 0.30, 0.05)
            tol_sec   = st.slider("Presjeci (mm)",       1.0, 25.0,  5.0,  1.0)

        st.markdown("---")
        st.markdown("### Obuhvat kontrole")
        c1, c2 = st.columns(2)
        with c1:
            chk_cols  = st.checkbox("Stupovi",  True)
            chk_beams = st.checkbox("Grede",    True)
            chk_walls = st.checkbox("Zidovi",   True)
            chk_slabs = st.checkbox("Ploče",    True)
        with c2:
            chk_mat   = st.checkbox("Materijal",    True)
            chk_load  = st.checkbox("Opterećenja",  True)
            chk_rest  = st.checkbox("Oslonci",      True)
            chk_hinge = st.checkbox("Zglobovi",     True)

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
        st.caption("v2.5 · Eurocode HRN EN 1992/1993")

    return use_sample, uploaded_dxf, uploaded_e2k, cfg


# ─────────────────────────────────────────────────────────────
# KPI strip
# ─────────────────────────────────────────────────────────────
def _kpi_strip(df: pd.DataFrame):
    counts = df["status"].value_counts()
    n_match   = counts.get(Status.MATCH, 0)
    n_mis     = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs   = counts.get(Status.ETABS_ONLY, 0)
    n_dxf     = counts.get(Status.DXF_ONLY, 0)
    n_total   = len(df)
    pct       = round(n_match / max(n_total, 1) * 100)

    st.markdown(f"""
    <div class="kpi-strip">
      <div class="kpi-card green">
        <div class="kpi-label">✅ Usklađeno</div>
        <div class="kpi-number">{n_match}</div>
        <div class="kpi-sub">{pct}% bez greške</div>
      </div>
      <div class="kpi-card amber">
        <div class="kpi-label">⚠️ Odstupanje presjeka</div>
        <div class="kpi-number">{n_mis}</div>
        <div class="kpi-sub">{'Razlika u dim.' if n_mis else 'Nema odstupanja'}</div>
      </div>
      <div class="kpi-card red">
        <div class="kpi-label">🔴 Samo u ETABS-u</div>
        <div class="kpi-number">{n_etabs}</div>
        <div class="kpi-sub">{'Višak u modelu' if n_etabs else 'Nema viška'}</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-label">🔵 Samo u CAD-u</div>
        <div class="kpi-number">{n_dxf}</div>
        <div class="kpi-sub">{'Nedostaje u modelu' if n_dxf else 'Sve uneseno'}</div>
      </div>
      <div class="kpi-card slate">
        <div class="kpi-label">📋 Ukupno</div>
        <div class="kpi-number">{n_total}</div>
        <div class="kpi-sub">Elemenata provjereno</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 2D Floorplan  (clean, correct)
# ─────────────────────────────────────────────────────────────
def _fig_2d(df_res: pd.DataFrame) -> go.Figure:
    COLOR = {
        Status.MATCH:            ("#10b981", "Usklađeno"),
        Status.SECTION_MISMATCH: ("#f59e0b", "Odstupanje presjeka"),
        Status.ETABS_ONLY:       ("#ef4444", "Samo u ETABS-u"),
        Status.DXF_ONLY:         ("#3b82f6", "Samo u CAD-u"),
    }

    fig = go.Figure()

    # collect bounds
    all_x, all_y = [], []
    for _, r in df_res.iterrows():
        x = r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x")
        y = r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y")
        if pd.notna(x) and pd.notna(y):
            all_x.append(float(x)); all_y.append(float(y))

    min_x = min(all_x) if all_x else 0.0;  max_x = max(all_x) if all_x else 12.0
    min_y = min(all_y) if all_y else 0.0;  max_y = max(all_y) if all_y else 6.0
    px = max((max_x - min_x) * 0.22, 2.5)
    py = max((max_y - min_y) * 0.22, 2.5)

    # ── grid axes ──
    for gx in sorted(set(all_x)):
        fig.add_shape(type="line", x0=gx, y0=min_y-py, x1=gx, y1=max_y+py,
                      line=dict(color="#e2e8f0", width=1))
        fig.add_annotation(x=gx, y=max_y+py*0.55, text=f"<b>{gx:.0f}</b>",
                           showarrow=False, font=dict(size=10, color="#94a3b8"), yanchor="middle")
    for gy in sorted(set(all_y)):
        fig.add_shape(type="line", x0=min_x-px, y0=gy, x1=max_x+px, y1=gy,
                      line=dict(color="#e2e8f0", width=1))
        fig.add_annotation(x=min_x-px*0.55, y=gy, text=f"<b>{gy:.0f}</b>",
                           showarrow=False, font=dict(size=10, color="#94a3b8"), xanchor="center")

    # ── elements ──
    for status, (color, label) in COLOR.items():
        sub = df_res[df_res["status"] == status]
        if sub.empty:
            continue

        # columns — circles
        cols = sub[sub["element_type"] == "column"]
        if not cols.empty:
            xs = [r.get("etabs_x", r.get("dxf_x")) for _, r in cols.iterrows()]
            ys = [r.get("etabs_y", r.get("dxf_y")) for _, r in cols.iterrows()]
            tips = []
            for i, (_, r) in enumerate(cols.iterrows()):
                nm  = r.get("etabs_name", "—")
                ew  = r.get("etabs_w_mm"); eh = r.get("etabs_h_mm")
                dw  = r.get("dxf_dim1_mm"); dh = r.get("dxf_dim2_mm")
                sec = r.get("etabs_section", "—")
                tips.append(
                    f"<b>{nm}</b>  [{label}]<br>"
                    f"Presjek: {sec}<br>"
                    f"ETABS: {ew or '—'} × {eh or '—'} mm<br>"
                    f"CAD:   {dw or '—'} × {dh or '—'} mm<br>"
                    f"Pos:   ({float(xs[i]):.2f}, {float(ys[i]):.2f}) m"
                )
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers+text",
                marker=dict(size=18, symbol="square", color=color,
                            line=dict(color="white", width=2)),
                text=[r.get("etabs_name", "") for _, r in cols.iterrows()],
                textfont=dict(size=9, color="white", family="Inter"),
                textposition="middle center",
                name=label,
                hovertext=tips, hoverinfo="text",
                legendgroup=label, showlegend=True,
            ))

        # beams — thick lines
        beams = sub[sub["element_type"] == "beam"]
        for _, bm in beams.iterrows():
            x0 = bm.get("etabs_x", bm.get("dxf_x"))
            y0 = bm.get("etabs_y", bm.get("dxf_y"))
            x1 = bm.get("x_end", x0 + 6.0) if pd.notna(bm.get("x_end")) else x0 + 6.0
            y1 = bm.get("y_end", y0) if pd.notna(bm.get("y_end")) else y0
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=6),
                name=label,
                hovertext=f"<b>{bm.get('etabs_name','Greda')}</b>  [{label}]<br>"
                          f"Presjek: {bm.get('etabs_section','—')}<br>"
                          f"Pos: ({float(x0):.2f}, {float(y0):.2f}) → ({float(x1):.2f}, {float(y1):.2f}) m",
                hoverinfo="text",
                legendgroup=label, showlegend=False,
            ))

        # walls — vertical markers
        walls = sub[sub["element_type"] == "wall"]
        for _, w in walls.iterrows():
            wx = w.get("etabs_x", w.get("dxf_x"))
            wy = w.get("etabs_y", w.get("dxf_y"))
            fig.add_trace(go.Scatter(
                x=[wx], y=[wy],
                mode="markers",
                marker=dict(size=20, symbol="square", color=color,
                            line=dict(color="white", width=2)),
                name=label, legendgroup=label, showlegend=False,
                hovertext=f"<b>{w.get('etabs_name','Zid')}</b>  [{label}]<br>"
                          f"Debljina: {w.get('etabs_h_mm','—')} mm",
                hoverinfo="text",
            ))

    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40),
        height=520,
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            title="X (m)", range=[min_x - px, max_x + px],
            showgrid=False, zeroline=False,
            tickfont=dict(size=11, color="#64748b"),
        ),
        yaxis=dict(
            title="Y (m)", range=[min_y - py, max_y + py],
            scaleanchor="x", scaleratio=1,
            showgrid=False, zeroline=False,
            tickfont=dict(size=11, color="#64748b"),
        ),
        legend=dict(
            orientation="h", x=0, y=-0.12,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 3D model
# ─────────────────────────────────────────────────────────────
def _fig_3d(df_res: pd.DataFrame, etabs_data: dict) -> go.Figure:
    fig = go.Figure()
    COLOR = {
        Status.MATCH: "#10b981", Status.SECTION_MISMATCH: "#f59e0b",
        Status.ETABS_ONLY: "#ef4444", Status.DXF_ONLY: "#3b82f6",
    }
    status_by = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    cols = etabs_data.get("columns", pd.DataFrame())
    for _, c in (cols.iterrows() if not cols.empty else []):
        color = COLOR.get(status_by.get(str(c["name"]), Status.MATCH), "#10b981")
        fig.add_trace(go.Scatter3d(
            x=[c["x_start"], c["x_end"]], y=[c["y_start"], c["y_end"]], z=[c["z_start"], c["z_end"]],
            mode="lines", line=dict(color=color, width=10),
            name=f"Stup {c['name']}", showlegend=False,
            hovertext=f"<b>Stup {c['name']}</b><br>Presjek: {c.get('section','')}<br>Z: {c['z_start']:.1f}–{c['z_end']:.1f} m",
            hoverinfo="text",
        ))

    beams = etabs_data.get("beams", pd.DataFrame())
    for _, b in (beams.iterrows() if not beams.empty else []):
        color = COLOR.get(status_by.get(str(b["name"]), Status.MATCH), "#f59e0b")
        fig.add_trace(go.Scatter3d(
            x=[b["x_start"], b["x_end"]], y=[b["y_start"], b["y_end"]], z=[b["z_start"], b["z_end"]],
            mode="lines", line=dict(color=color, width=7),
            name=f"Greda {b['name']}", showlegend=False,
            hovertext=f"<b>Greda {b['name']}</b><br>{b.get('section','')}<br>Z={b['z_start']:.2f} m",
            hoverinfo="text",
        ))

    # slab surface
    fig.add_trace(go.Mesh3d(x=[0,6,6,0], y=[0,0,6,6], z=[3.2,3.2,3.2,3.2],
        i=[0,0], j=[1,2], k=[2,3], color="#3b82f6", opacity=0.25, showlegend=False,
        hovertext="<b>AB Ploča</b> d=20 cm, Z=3.20 m", hoverinfo="text"))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=520, paper_bgcolor="#ffffff",
        scene=dict(
            aspectmode="data",
            camera=dict(eye=dict(x=1.7, y=-1.9, z=1.3)),
            xaxis=dict(title="X (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            yaxis=dict(title="Y (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            zaxis=dict(title="Z (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# Table helper  (zero NaN, no attrs)
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
# Main
# ─────────────────────────────────────────────────────────────
def main():
    use_sample, uploaded_dxf, uploaded_e2k, cfg = _sidebar()

    # ── Header ──────────────────────────────────────────────
    st.markdown("""
    <div class="app-header">
      <div class="app-header-icon">🏗️</div>
      <div>
        <div class="app-header-title">ETABS ↔ CAD — Kontrola Numeričkih Modela</div>
        <div class="app-header-sub">Automatska provjera geometrije · presjeka · materijala · opterećenja · oslonaca</div>
      </div>
      <div class="app-version-badge">v2.5 · Eurocode</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Resolve inputs ───────────────────────────────────────
    has_data, dxf_path, e2k_content = False, None, None

    if use_sample:
        if os.path.exists(SAMPLE_DXF) and os.path.exists(SAMPLE_E2K):
            dxf_path, e2k_content = SAMPLE_DXF, open(SAMPLE_E2K).read()
            has_data = True
        else:
            st.error("Ogledne datoteke nisu pronađene.")
    elif uploaded_dxf and uploaded_e2k:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
        tmp.write(uploaded_dxf.getvalue()); tmp.close()
        dxf_path = tmp.name
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        has_data = True

    # ── Empty state ──────────────────────────────────────────
    if not has_data:
        st.markdown("""
        <div class="empty-state">
          <div style="font-size:56px;margin-bottom:16px;">🏗️</div>
          <h2>Dobrodošli u ETABS↔CAD kontrolu</h2>
          <p>Učitajte CAD nacrt (.dxf) i ETABS model (.e2k) u bočnoj traci — ili uključite ogledni primjer za trenutni pregled.</p>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**Korak 1 — Izvoz iz ETABS-a**")
            st.caption("File → Export → ETABS .e2k Text File…")
        with col_b:
            st.markdown("**Korak 2 — Učitaj datoteke**")
            st.caption("Priložite .dxf nacrt i .e2k model u bočnom izborniku.")
        with col_c:
            st.markdown("**Korak 3 — Preuzmi elaborat**")
            st.caption("Generirajte PDF revizijsku dokumentaciju jednim klikom.")
        return

    # ── Run analysis ─────────────────────────────────────────
    with st.spinner("Analiza u tijeku…"):
        try:
            df_dxf    = parse_dxf(dxf_path, cfg)
            etabs_data = parse_e2k(io.StringIO(e2k_content), cfg)
            df_res    = validate(etabs_data, df_dxf, cfg)
        except Exception as err:
            st.error(f"Greška: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except: pass

    # ── KPIs ─────────────────────────────────────────────────
    _kpi_strip(df_res)

    # ── Warnings (compact pills) ──────────────────────────────
    alerts = df_res.attrs.get("sanity_alerts", [])
    if alerts:
        pills = ""
        for a in alerts[:8]:
            cls  = "error-pill" if a.get("severity") == "ERROR" else "warn-pill"
            icon = "🔴" if a.get("severity") == "ERROR" else "⚠️"
            pills += f'<span class="{cls}">{icon} [{a["category"]}] {a["element"]}: {a["issue"]}</span>'
        if len(alerts) > 8:
            pills += f'<span class="warn-pill">+{len(alerts)-8} više…</span>'
        st.markdown(f"<div style='margin-bottom:20px'>{pills}</div>", unsafe_allow_html=True)

    # ── Main tabs ─────────────────────────────────────────────
    t_map, t_geo, t_mat, t_sup, t_pdf = st.tabs([
        "🗺️  Model", "📊  Odstupanja", "🧪  Materijali & Opterećenja",
        "🧱  Oslonci", "📄  PDF Elaborat",
    ])

    # ── TAB 1: visual model ───────────────────────────────────
    with t_map:
        mode = st.radio("", ["2D Tlocrt", "3D Model"], horizontal=True,
                        label_visibility="collapsed")
        if mode == "3D Model":
            st.plotly_chart(_fig_3d(df_res, etabs_data), use_container_width=True)
        else:
            st.plotly_chart(_fig_2d(df_res), use_container_width=True)

    # ── TAB 2: geometry / section table ──────────────────────
    with t_geo:
        f1, f2, f3 = st.columns([1.2, 1.2, 2.6])
        with f1:
            st_f = st.selectbox("Status:", ["Sve"] + [s.value for s in Status], key="geo_status")
        with f2:
            ty_f = st.selectbox("Tip:", ["Sve"] + sorted(df_res["element_type"].unique()), key="geo_type")
        with f3:
            search = st.text_input("Pretraži:", placeholder="C1, BM_30x40…", key="geo_search")

        dfd = df_res.copy()
        if st_f != "Sve": dfd = dfd[dfd["status"].astype(str) == st_f]
        if ty_f != "Sve": dfd = dfd[dfd["element_type"] == ty_f]
        if search:
            q = search.lower()
            dfd = dfd[dfd.apply(lambda r: q in str(r.to_dict()).lower(), axis=1)]

        vcols = ["element_type","status","etabs_name","etabs_section",
                 "etabs_w_mm","etabs_h_mm","dxf_dim_text","dxf_dim1_mm","dxf_dim2_mm","xy_dist_m","notes"]
        vcols = [c for c in vcols if c in dfd.columns]
        tbl = _safe_df(dfd[vcols], {
            "etabs_w_mm": "{:.0f}", "etabs_h_mm": "{:.0f}",
            "dxf_dim1_mm": "{:.0f}", "dxf_dim2_mm": "{:.0f}",
            "xy_dist_m": "{:.2f}",
        })
        if "status" in tbl.columns:
            tbl["status"] = tbl["status"].apply(lambda v: v.value if hasattr(v, "value") else str(v))

        st.dataframe(tbl, use_container_width=True, hide_index=True,
            column_config={
                "element_type": st.column_config.TextColumn("Tip"),
                "status":       st.column_config.TextColumn("Status"),
                "etabs_name":   st.column_config.TextColumn("ETABS ID"),
                "etabs_section":st.column_config.TextColumn("Presjek"),
                "etabs_w_mm":   st.column_config.TextColumn("b (mm)"),
                "etabs_h_mm":   st.column_config.TextColumn("h (mm)"),
                "dxf_dim_text": st.column_config.TextColumn("CAD kota"),
                "dxf_dim1_mm":  st.column_config.TextColumn("CAD b"),
                "dxf_dim2_mm":  st.column_config.TextColumn("CAD h"),
                "xy_dist_m":    st.column_config.TextColumn("Odmak (m)"),
                "notes":        st.column_config.TextColumn("Napomena"),
            })

    # ── TAB 3: materials & loads ──────────────────────────────
    with t_mat:
        mc, lc = st.columns(2)

        with mc:
            st.markdown("##### Klase materijala")
            mats = pd.DataFrame(df_res.attrs.get("materials", []))
            if not mats.empty:
                st.dataframe(
                    _safe_df(mats, {"E_gpa":"{:.1f}","fc_mpa":"{:.1f}","fy_mpa":"{:.1f}","fu_mpa":"{:.1f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "name": st.column_config.TextColumn("Materijal"),
                        "type": st.column_config.TextColumn("Tip"),
                        "E_gpa":  st.column_config.TextColumn("E (GPa)"),
                        "fc_mpa": st.column_config.TextColumn("fc (MPa)"),
                        "fy_mpa": st.column_config.TextColumn("fy (MPa)"),
                        "fu_mpa": st.column_config.TextColumn("fu (MPa)"),
                    })
            else:
                st.info("Nema podataka o materijalima.")

        with lc:
            st.markdown("##### Uzorci opterećenja")
            pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
            if not pats.empty:
                st.dataframe(
                    _safe_df(pats, {"self_weight_mult": "{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "name": st.column_config.TextColumn("Naziv"),
                        "type": st.column_config.TextColumn("Tip"),
                        "self_weight_mult": st.column_config.TextColumn("Vlastita težina"),
                    })
            else:
                st.info("Nema uzoraka opterećenja.")

            aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
            if not aloads.empty:
                st.markdown("##### Plošna opterećenja (kN/m²)")
                st.dataframe(_safe_df(aloads), use_container_width=True, hide_index=True)

    # ── TAB 4: supports & hinges ──────────────────────────────
    with t_sup:
        sc, hc = st.columns(2)

        with sc:
            st.markdown("##### Temeljni oslonci")
            rests = pd.DataFrame(df_res.attrs.get("restraints", []))
            if not rests.empty and "joint_name" in rests.columns:
                rcols = [c for c in ["joint_name","x","y","z","restraint_type","is_supported"] if c in rests.columns]
                st.dataframe(
                    _safe_df(rests[rcols], {"x":"{:.2f}","y":"{:.2f}","z":"{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "joint_name":     st.column_config.TextColumn("Čvor"),
                        "x":              st.column_config.TextColumn("X (m)"),
                        "y":              st.column_config.TextColumn("Y (m)"),
                        "z":              st.column_config.TextColumn("Z (m)"),
                        "restraint_type": st.column_config.TextColumn("Tip"),
                        "is_supported":   st.column_config.CheckboxColumn("Poduprt"),
                    })
            else:
                st.info("Nema podataka o osloncima.")

        with hc:
            st.markdown("##### Plastični zglobovi")
            hinges = etabs_data.get("hinges", pd.DataFrame())
            if not hinges.empty and "frame_name" in hinges.columns:
                hcols = [c for c in ["frame_name","hinge_prop","rel_dist","dof"] if c in hinges.columns]
                st.dataframe(
                    _safe_df(hinges[hcols], {"rel_dist":"{:.2f}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "frame_name":  st.column_config.TextColumn("Element"),
                        "hinge_prop":  st.column_config.TextColumn("Svojstvo"),
                        "rel_dist":    st.column_config.TextColumn("Lokacija"),
                        "dof":         st.column_config.TextColumn("DOF"),
                    })
            else:
                st.info("Nema plastičnih zglobova.")

    # ── TAB 5: PDF export ─────────────────────────────────────
    with t_pdf:
        st.markdown("""
        <div class="dl-card">
          <h3>📄 Preuzimanje Revizijskog Elaborata</h3>
          <p>Kompletan A4 Landscape PDF s naslovnicom, sažetkom usklađenosti,
             tlocrtnim prikazom i detaljnim tablicama presjeka, materijala i opterećenja.</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        d1, d2 = st.columns(2)
        with d1:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
                pdf_path = fp.name
            try:
                generate_pdf(df_res, pdf_path, cfg)
                st.download_button("📥 Preuzmi PDF Elaborat",
                    data=open(pdf_path,"rb").read(),
                    file_name="ETABS_CAD_Kontrola.pdf",
                    mime="application/pdf",
                    use_container_width=True)
            finally:
                try: os.unlink(pdf_path)
                except: pass

        with d2:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as fh:
                html_path = fh.name
            try:
                html_content = generate_html(df_res, html_path, cfg)
                st.download_button("🌐 Preuzmi HTML Izvještaj",
                    data=html_content.encode("utf-8"),
                    file_name="ETABS_CAD_Izvjestaj.html",
                    mime="text/html",
                    use_container_width=True)
            finally:
                try: os.unlink(html_path)
                except: pass


if __name__ == "__main__":
    main()
