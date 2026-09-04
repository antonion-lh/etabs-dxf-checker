"""
ui_styles.py
------------
Minimalist, high-performance CSS and typography for ETABS Model Checker.
Adheres to professional CAD / engineering software standards (SAFE, Tekla, AutoCAD):
No emojis, neutral palette, crisp typography, and functional color coding only.
"""

import streamlit as st
import pandas as pd

MINIMAL_ENGINEERING_CSS = """
<style>
/* Base container: minimal padding */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px;
}

/* Typography — standard system fonts */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #111827;
    font-size: 13px;
}

h1 {
    font-size: 18px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    margin: 0 0 4px 0 !important;
    letter-spacing: -0.01em;
}
h2 {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    margin: 12px 0 6px 0 !important;
}
h3 {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #4B5563 !important;
    margin: 8px 0 4px 0 !important;
}

/* Monospace for dimensions, coordinates, section names */
.mono {
    font-family: "SF Mono", "Menlo", "Consolas", "Monaco", monospace !important;
    font-size: 12px !important;
    color: #374151;
}

/* Top App Header Bar */
.app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #E5E7EB;
    padding-bottom: 10px;
    margin-bottom: 16px;
}
.app-header-left {
    display: flex;
    align-items: baseline;
    gap: 12px;
}
.app-header-title {
    font-size: 16px;
    font-weight: 600;
    color: #111827;
    margin: 0;
}
.app-header-meta {
    font-size: 12px;
    color: #6B7280;
}

/* Clean sidebar styling */
[data-testid="stSidebar"] {
    background-color: #F9FAFB !important;
    border-right: 1px solid #E5E7EB !important;
    padding-top: 1rem !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px !important;
}

/* Clean tabs styling without underlines */
[data-baseweb="tab-list"] {
    gap: 8px !important;
    border-bottom: 1px solid #E5E7EB !important;
    padding-bottom: 0px !important;
    margin-bottom: 16px !important;
}
[data-baseweb="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #4B5563 !important;
    padding: 8px 14px !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
}
[data-baseweb="tab"]:hover {
    color: #111827 !important;
}
[aria-selected="true"] {
    color: #111827 !important;
    border-bottom: 2px solid #111827 !important;
    font-weight: 600 !important;
}

/* Status colors (functional only) */
.status-match    { color: #16A34A; font-weight: 600; }
.status-mismatch { color: #D97706; font-weight: 600; }
.status-etabs    { color: #DC2626; font-weight: 600; }
.status-dxf      { color: #2563EB; font-weight: 600; }
.status-neutral  { color: #6B7280; font-weight: 500; }

/* Triage Code-Review Items */
.triage-item {
    border-left: 3px solid #E5E7EB;
    padding: 8px 12px;
    margin-bottom: 8px;
    background: #F9FAFB;
    border-radius: 0 4px 4px 0;
}
.triage-fail { border-left-color: #DC2626; background: #FEF2F2; }
.triage-warn { border-left-color: #D97706; background: #FFFBEB; }
.triage-pass { border-left-color: #16A34A; background: #F0FDF4; }
.triage-info { border-left-color: #9CA3AF; background: #F9FAFB; }

.triage-title {
    font-size: 13px;
    font-weight: 600;
    color: #111827;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.triage-finding {
    font-size: 12px;
    color: #374151;
    margin: 4px 0;
    line-height: 1.45;
}
.triage-action {
    font-size: 12px;
    color: #111827;
    margin-top: 4px;
}
.triage-action-arrow {
    font-weight: 600;
    color: #2563EB;
}

/* Landing Box (Empty State) */
.landing-box {
    border: 1px solid #E5E7EB;
    background: #FFFFFF;
    border-radius: 6px;
    padding: 40px 32px;
    text-align: center;
    max-width: 580px;
    margin: 40px auto 20px auto;
}
.landing-title {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 6px;
}
.landing-subtitle {
    font-size: 13px;
    color: #4B5563;
    line-height: 1.5;
    margin-bottom: 24px;
}

/* Step cards for landing screen */
.step-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 0 auto 28px auto;
    max-width: 780px;
}
.step-card {
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    padding: 16px 18px;
    background: #FFFFFF;
}
.step-num {
    font-size: 11px;
    font-weight: 700;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}
.step-title {
    font-size: 13px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 4px;
}
.step-desc {
    font-size: 12px;
    color: #6B7280;
    line-height: 1.5;
}

/* Expander: čišći izgled bez jako vidljive linije */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 6px !important;
    margin-bottom: 6px !important;
}
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    padding: 10px 14px !important;
}
[data-testid="stExpander"] summary:hover {
    background: #F9FAFB !important;
}

/* Dataframe: povećaj kontrast zaglavlja */
[data-testid="stDataFrame"] th {
    background-color: #F9FAFB !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #374151 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    padding: 8px 10px !important;
}
[data-testid="stDataFrame"] td {
    font-size: 12px !important;
    padding: 6px 10px !important;
}

/* Metric kartice: smanji padding, ujednači veličinu */
[data-testid="stMetric"] {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    padding: 10px 14px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #6B7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}
[data-testid="stMetricValue"] {
    font-size: 20px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}

/* Segmented control: čvršći kontrast aktivnog */
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    font-weight: 700 !important;
}

/* Caption text */
[data-testid="stCaptionContainer"] {
    color: #9CA3AF !important;
    font-size: 11px !important;
}

/* Spinner tekst */
[data-testid="stStatusWidget"] {
    font-size: 12px !important;
    color: #6B7280 !important;
}

/* Sidebar section labels */
[data-testid="stSidebar"] .sidebar-section-label {
    font-size: 10px;
    font-weight: 700;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 14px 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #F3F4F6;
}

/* Modern Engineering Buttons */
[data-testid="stBaseButton-primary"] {
    background-color: #0F172A !important;
    color: #FFFFFF !important;
    border: 1px solid #0F172A !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: -0.01em !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #1E293B !important;
    border-color: #1E293B !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
}
[data-testid="stBaseButton-secondary"] {
    background-color: #FFFFFF !important;
    color: #1E293B !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #F8FAFC !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
}

/* Own model card on landing screen */
.own-model-card {
    border: 1px dashed #CBD5E1;
    border-radius: 6px;
    padding: 24px 20px;
    text-align: center;
    background: #FAFAFA;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}
.own-model-title {
    font-size: 14px;
    font-weight: 600;
    color: #1E293B;
    margin-bottom: 8px;
}
.own-model-desc {
    font-size: 12px;
    color: #64748B;
    line-height: 1.5;
    margin-bottom: 12px;
}
.own-model-hint {
    font-size: 11px;
    font-weight: 600;
    color: #2563EB;
}
</style>
"""

DARK_ENGINEERING_CSS = """
<style>
/* Dark Mode Theme */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #0B0F19 !important;
    color: #E2E8F0 !important;
}
.block-container {
    color: #E2E8F0 !important;
}
html, body, [class*="css"] {
    color: #E2E8F0 !important;
}
h1, h2, h3 {
    color: #F8FAFC !important;
}
p, span, label {
    color: #CBD5E1 !important;
}
.mono {
    color: #94A3B8 !important;
    background-color: rgba(30, 41, 59, 0.6) !important;
}

/* Sidebar Dark */
[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    border-right: 1px solid #1E293B !important;
}
[data-testid="stSidebar"] .sidebar-section-label {
    color: #94A3B8 !important;
    border-bottom: 1px solid #1E293B !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    color: #F8FAFC !important;
}

/* Header Dark */
.app-header {
    border-bottom: 1px solid #1E293B !important;
}
.app-header-title {
    color: #F8FAFC !important;
}
.app-header-meta {
    color: #94A3B8 !important;
}

/* Tabs Dark */
[data-baseweb="tab-list"] {
    border-bottom: 1px solid #1E293B !important;
}
[data-baseweb="tab"] {
    color: #94A3B8 !important;
    background: transparent !important;
}
[data-baseweb="tab"]:hover {
    color: #F8FAFC !important;
}
[aria-selected="true"] {
    color: #60A5FA !important;
    border-bottom: 2px solid #60A5FA !important;
}

/* Segmented Control Dark */
[data-testid="stSegmentedControl"] {
    background-color: #1E293B !important;
}
[data-testid="stSegmentedControl"] button {
    color: #94A3B8 !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #0F172A !important;
    color: #F8FAFC !important;
}

/* Inputs, Selectboxes, Dropdowns */
div[data-baseweb="select"] > div {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border-color: #334155 !important;
}
div[data-baseweb="select"] span {
    color: #F8FAFC !important;
}
input, textarea {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border-color: #334155 !important;
}

/* Cards & Containers Dark */
.landing-box {
    background: #131B2E !important;
    border: 1px solid #1E293B !important;
}
.landing-title {
    color: #F8FAFC !important;
}
.landing-subtitle {
    color: #94A3B8 !important;
}
.step-card {
    background: #131B2E !important;
    border: 1px solid #1E293B !important;
}
.step-num {
    color: #64748B !important;
}
.step-title {
    color: #F8FAFC !important;
}
.step-desc {
    color: #94A3B8 !important;
}
.own-model-card {
    background: #131B2E !important;
    border: 1px dashed #334155 !important;
}
.own-model-title {
    color: #F8FAFC !important;
}
.own-model-desc {
    color: #94A3B8 !important;
}
.own-model-hint {
    color: #60A5FA !important;
}
[data-testid="stMetric"] {
    background: #131B2E !important;
    border: 1px solid #1E293B !important;
}
[data-testid="stMetricLabel"] {
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"] {
    color: #F8FAFC !important;
}
[data-testid="stExpander"] {
    background: #131B2E !important;
    border: 1px solid #1E293B !important;
}
[data-testid="stExpander"] summary {
    color: #F8FAFC !important;
}
[data-testid="stExpander"] summary:hover {
    background: #1E293B !important;
}

/* DataFrame Dark */
[data-testid="stDataFrame"] {
    background-color: #131B2E !important;
}
[data-testid="stDataFrame"] th {
    background-color: #1E293B !important;
    color: #94A3B8 !important;
    border-bottom: 1px solid #334155 !important;
}
[data-testid="stDataFrame"] td {
    background-color: #131B2E !important;
    color: #E2E8F0 !important;
    border-bottom: 1px solid #1E293B !important;
}

/* Buttons Dark */
[data-testid="stBaseButton-primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #2563EB !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
}
[data-testid="stBaseButton-secondary"] {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border: 1px solid #334155 !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #334155 !important;
    border-color: #475569 !important;
    color: #FFFFFF !important;
}

/* Triage Items Dark */
.triage-item {
    background: #131B2E !important;
    border-left: 3px solid #334155 !important;
}
.triage-title {
    color: #F8FAFC !important;
}
.triage-finding {
    color: #CBD5E1 !important;
}
.triage-fail { background: rgba(225, 29, 72, 0.15) !important; border-left-color: #F43F5E !important; }
.triage-warn { background: rgba(217, 119, 6, 0.15) !important; border-left-color: #F59E0B !important; }
.triage-pass { background: rgba(16, 185, 129, 0.15) !important; border-left-color: #10B981 !important; }
/* Tables and Div inline overrides */
table { color: #CBD5E1 !important; }
table td { color: #CBD5E1 !important; }
div[style*="border-bottom: 1px solid #E5E7EB"] { border-bottom: 1px solid #1E293B !important; }
div[style*="background:#E2E8F0"] { background: #1E293B !important; }
span[style*="color: #111827"], strong[style*="color: #111827"], div[style*="color: #111827"] { color: #F8FAFC !important; }
span[style*="color: #374151"], div[style*="color: #374151"] { color: #CBD5E1 !important; }
span[style*="color: #6B7280"] { color: #94A3B8 !important; }
</style>
"""

LARGE_FONT_CSS = """
<style>
/* Large Font Accessibility Mode (+15-20%) */
html, body, [class*="css"] {
    font-size: 15px !important;
}
h1 {
    font-size: 21px !important;
}
h2 {
    font-size: 16px !important;
}
h3 {
    font-size: 15px !important;
}
.mono {
    font-size: 13.5px !important;
}
.app-header-title {
    font-size: 18px !important;
}
.app-header-meta {
    font-size: 13.5px !important;
}
.step-title {
    font-size: 14.5px !important;
}
.step-desc {
    font-size: 13px !important;
}
.landing-title {
    font-size: 21px !important;
}
.landing-subtitle {
    font-size: 14.5px !important;
}
.own-model-title {
    font-size: 15px !important;
}
.own-model-desc {
    font-size: 13px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 12px !important;
}
[data-testid="stMetricValue"] {
    font-size: 23px !important;
}
[data-testid="stDataFrame"] th {
    font-size: 12px !important;
}
[data-testid="stDataFrame"] td {
    font-size: 13.5px !important;
}
[data-testid="stExpander"] summary {
    font-size: 14px !important;
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
    font-size: 14px !important;
    padding: 10px 18px !important;
}
[data-testid="stSidebar"] .sidebar-section-label {
    font-size: 11px !important;
}
.triage-title {
    font-size: 14px !important;
}
.triage-finding {
    font-size: 13px !important;
}
</style>
"""

def inject_app_css(dark_mode: bool = None, font_scale: str = None):
    st.markdown(MINIMAL_ENGINEERING_CSS, unsafe_allow_html=True)
    if dark_mode is None and hasattr(st, "session_state"):
        dark_mode = (st.session_state.get("app_theme") == "Tamna")
    if font_scale is None and hasattr(st, "session_state"):
        font_scale = "large" if (st.session_state.get("app_font_scale") == "Veliki") else "normal"

    if dark_mode:
        st.markdown(DARK_ENGINEERING_CSS, unsafe_allow_html=True)
    if font_scale == "large":
        st.markdown(LARGE_FONT_CSS, unsafe_allow_html=True)

def render_header_bar(
    project_name: str = None,
    version: str = "v2.1.0",
    status_badge: tuple = None,
    *args,
    **kwargs
):
    if status_badge is None and "status_badge" in kwargs:
        status_badge = kwargs["status_badge"]
    proj_txt = f"Projekt: {project_name}" if project_name else "Projekt: —"
    badge_html = ""
    if status_badge and isinstance(status_badge, (tuple, list)) and len(status_badge) == 2:
        try:
            badge_text, badge_color = status_badge
            badge_html = (
                f'<span style="background:{badge_color}18; color:{badge_color};'
                f'border:1px solid {badge_color}40; border-radius:4px;'
                f'padding:2px 10px; font-size:11px; font-weight:600;'
                f'margin-left:12px;">{badge_text}</span>'
            )
        except Exception:
            badge_html = ""
    st.markdown(f"""
    <div class="app-header">
      <div class="app-header-left">
        <span class="app-header-title">ETABS Model Checker</span>
        <span class="app-header-meta">| &nbsp; {proj_txt}</span>
      </div>
      <div class="app-header-meta">
        <span>{version}</span>{badge_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_landing_screen():
    st.markdown("""
    <div class="landing-box">
      <div class="landing-title">ETABS Model Checker</div>
      <div class="landing-subtitle">
        Učitajte <b>.e2k</b> model i nacrt (<b>.dxf</b> ili <b>.pdf</b>) za automatsku geometrijsku reviziju i Eurocode provjeru.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="step-row">
      <div class="step-card">
        <div class="step-num">Korak 1</div>
        <div class="step-title">Učitaj .e2k model</div>
        <div class="step-desc">Izvezi iz ETABS-a:<br>
          File → Export → .e2k Text File</div>
      </div>
      <div class="step-card">
        <div class="step-num">Korak 2</div>
        <div class="step-title">Priloži nacrt</div>
        <div class="step-desc">DXF tlocrt ili PDF elaborat
          za automatsku geometrijsku usporedbu</div>
      </div>
      <div class="step-card">
        <div class="step-num">Korak 3</div>
        <div class="step-title">Preuzmi elaborat</div>
        <div class="step-desc">PDF revizijski izvještaj
          spreman za potpis i arhivu</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Compatibility helper
def render_kpi_strip(*args, **kwargs):
    pass

def render_header_card(*args, **kwargs):
    render_header_bar()

def render_audit_hero(*args, **kwargs):
    pass
