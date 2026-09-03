"""
ui_styles.py
------------
CSS styles, theme constants, and HTML presentation cards for Streamlit UI.
"""

import streamlit as st
import pandas as pd
from phase3_validation import Status

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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

/* ─── Sidebar ─── */
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

/* ─── KPI Strip: Clean Minimalist Engineering Cards ─── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
}
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 18px;
    position: relative;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    transition: transform 0.1s ease, border-color 0.1s ease;
}
.kpi-card:hover {
    border-color: #cbd5e1;
    transform: translateY(-1px);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 10px 10px 0 0;
}
.kpi-card.green::before  { background: #10b981; }
.kpi-card.amber::before  { background: #f59e0b; }
.kpi-card.red::before    { background: #ef4444; }
.kpi-card.blue::before   { background: #0284c7; }
.kpi-card.slate::before  { background: #64748b; }
.kpi-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}
.kpi-number {
    font-size: 26px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
}
.kpi-sub {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
    font-weight: 500;
}

/* ─── Modern Toolbar & Control Badges ─── */
.story-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    color: #334155;
    height: 38px;
    width: 100%;
}

/* ─── Modern Audit Hero Card ─── */
.audit-hero-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}

/* ─── Tabs Modern Styling ─── */
[data-baseweb="tab-list"] {
    gap: 12px !important;
    border-bottom: 1px solid #e2e8f0 !important;
    padding-bottom: 0px !important;
    margin-bottom: 18px !important;
}
[data-baseweb="tab"] {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #64748b !important;
    padding: 10px 16px !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
}
[data-baseweb="tab"]:hover {
    color: #0f172a !important;
}
[aria-selected="true"] {
    color: #0284c7 !important;
    border-bottom: 2px solid #0284c7 !important;
    font-weight: 700 !important;
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
"""

def inject_app_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)

def render_header_card():
    st.markdown("""
    <div class="app-header-card">
      <div class="app-header-left">
        <div class="app-header-icon">📐</div>
        <div>
          <h1 class="app-header-title">ETABS ↔ CAD/PDF Model Checker</h1>
          <p class="app-header-sub">Eurocode HRN EN kontrola i nastavna revizija numeričkih modela zgrada</p>
        </div>
      </div>
      <div class="badge-group">
        <span class="badge-tag badge-blue">Eurocode 1, 2, 6, 8</span>
        <span class="badge-tag badge-green">ETABS v23 Verified</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_kpi_strip(df: pd.DataFrame, is_pdf_mode: bool = False, etabs_data: dict = None):
    has_type = (not df.empty) and ("element_type" in df.columns)
    has_status = (not df.empty) and ("status" in df.columns)

    if is_pdf_mode:
        n_total = len(df) if not df.empty else 0
        n_cols = len(df[df["element_type"] == "column"]) if has_type else 0
        n_beams = len(df[df["element_type"] == "beam"]) if has_type else 0
        n_walls = len(df[df["element_type"] == "wall"]) if has_type else 0
        n_slabs = len(df[df["element_type"] == "slab"]) if has_type else 0
        n_secs = df["etabs_section"].nunique() if (not df.empty and "etabs_section" in df.columns) else 0
        n_mats = len(etabs_data.get("materials", [])) if etabs_data else 0
        n_rests = len(etabs_data.get("restraints", [])) if etabs_data else 0

        detail_txt = []
        if n_cols: detail_txt.append(f"{n_cols} stupova")
        if n_beams: detail_txt.append(f"{n_beams} greda")
        if n_walls: detail_txt.append(f"{n_walls} zidova")
        if n_slabs: detail_txt.append(f"{n_slabs} ploča")
        sub_desc = ", ".join(detail_txt) if detail_txt else "Nosivi elementi"

        st.markdown(f"""
        <div class="kpi-strip">
          <div class="kpi-card green">
            <div class="kpi-label">Elementi modela</div>
            <div class="kpi-number">{n_total}</div>
            <div class="kpi-sub">{sub_desc}</div>
          </div>
          <div class="kpi-card amber">
            <div class="kpi-label">Poprečni presjeci</div>
            <div class="kpi-number">{n_secs}</div>
            <div class="kpi-sub">Različitih profila</div>
          </div>
          <div class="kpi-card blue">
            <div class="kpi-label">Materijali</div>
            <div class="kpi-number">{n_mats}</div>
            <div class="kpi-sub">Klasa betona / čelika</div>
          </div>
          <div class="kpi-card slate">
            <div class="kpi-label">Temeljni ležajevi</div>
            <div class="kpi-number">{n_rests}</div>
            <div class="kpi-sub">Pridržane točke baze</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    counts = df["status"].value_counts() if has_status else pd.Series(dtype=int)
    n_match = counts.get(Status.MATCH, 0)
    n_mis   = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs = counts.get(Status.ETABS_ONLY, 0)
    n_dxf   = counts.get(Status.DXF_ONLY, 0)
    n_total = len(df) if not df.empty else 0
    pct     = round(n_match / max(n_total, 1) * 100) if has_status else 0

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
    </div>
    """, unsafe_allow_html=True)

def render_audit_hero(score_data: dict):
    st.markdown(f"""
    <div class="audit-hero-card">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
        <div>
          <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; font-weight: 700;">Eurocode HRN EN · Inženjerska kontrola modela</div>
          <div style="font-size: 1.45rem; font-weight: 800; color: #0f172a; margin-top: 4px;">Nastavna i stručna revizija modela (Točke 1–51)</div>
          <div style="font-size: 0.92rem; color: #475569; margin-top: 4px;">
            Indeks usklađenosti: <strong style="color: #0284c7;">{score_data['percentage']}%</strong> · 
            Ocjena: <strong style="color: {score_data['badge_color']};">{score_data['grade_label']}</strong>
          </div>
        </div>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px 24px; border-radius: 10px; text-align: center;">
          <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 700;">Ocjena modela</div>
          <div style="font-size: 2.2rem; font-weight: 900; color: {score_data['badge_color']}; line-height: 1.1;">{score_data['grade']}<span style="font-size: 1.1rem; color: #94a3b8;">/5</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
