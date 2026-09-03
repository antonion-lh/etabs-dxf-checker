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
    margin: 60px auto;
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
</style>
"""

def inject_app_css():
    st.markdown(MINIMAL_ENGINEERING_CSS, unsafe_allow_html=True)

def render_header_bar(project_name: str = None, version: str = "v2.1.0"):
    proj_txt = f"Projekt: {project_name}" if project_name else "Projekt: —"
    st.markdown(f"""
    <div class="app-header">
      <div class="app-header-left">
        <span class="app-header-title">ETABS Model Checker</span>
        <span class="app-header-meta">| &nbsp; {proj_txt}</span>
      </div>
      <div class="app-header-meta">
        <span>{version}</span>
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

# Compatibility helper
def render_kpi_strip(*args, **kwargs):
    pass

def render_header_card(*args, **kwargs):
    render_header_bar()

def render_audit_hero(*args, **kwargs):
    pass
