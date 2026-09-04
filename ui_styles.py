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
/* Base container: comfortable top padding so Streamlit's fixed navbar never overlaps */
.block-container {
    padding-top: 4.25rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px;
}

/* Streamlit Header Navbar */
[data-testid="stHeader"] {
    background-color: rgba(255, 255, 255, 0.96) !important;
    backdrop-filter: blur(8px);
    z-index: 99 !important;
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
    padding-bottom: 6px;
}
.app-header-left {
    display: flex;
    align-items: baseline;
    gap: 12px;
}
.app-header-title {
    font-size: 16px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    letter-spacing: -0.01em;
}
.app-header-meta {
    font-size: 12px;
    color: #64748B;
    font-weight: 500;
}
.app-header-divider {
    border-bottom: 1px solid #E2E8F0;
    margin-top: 4px;
    margin-bottom: 18px;
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

/* Segmented control / Button groups (Theme & Font controls): high contrast, tactile, fully visible */
[data-testid="stButtonGroup"],
[data-testid="stSegmentedControl"] {
    display: inline-flex !important;
    background-color: #F1F5F9 !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 7px !important;
    padding: 2px !important;
    gap: 2px !important;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04) !important;
}
[data-testid="stButtonGroup"] button,
[data-testid="stSegmentedControl"] button {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 5px !important;
    padding: 4px 10px !important;
    min-height: 28px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButtonGroup"] button p,
[data-testid="stButtonGroup"] button span,
[data-testid="stButtonGroup"] button div,
[data-testid="stSegmentedControl"] button p,
[data-testid="stSegmentedControl"] button span,
[data-testid="stSegmentedControl"] button div {
    color: #475569 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
}
[data-testid="stButtonGroup"] button:hover,
[data-testid="stSegmentedControl"] button:hover {
    background-color: rgba(255, 255, 255, 0.75) !important;
}
[data-testid="stButtonGroup"] button:hover p,
[data-testid="stButtonGroup"] button:hover span,
[data-testid="stSegmentedControl"] button:hover p,
[data-testid="stSegmentedControl"] button:hover span {
    color: #0F172A !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #FFFFFF !important;
    border: 1px solid #94A3B8 !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] p,
[data-testid="stButtonGroup"] button[aria-checked="true"] span,
[data-testid="stButtonGroup"] button[aria-checked="true"] div,
[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
[data-testid="stSegmentedControl"] button[aria-checked="true"] span,
[data-testid="stSegmentedControl"] button[aria-checked="true"] div {
    color: #0F172A !important;
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
    border: 1.5px solid #0F172A !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: -0.01em !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #1E293B !important;
    border-color: #1E293B !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15) !important;
}
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="stBaseButton-primary"] div {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

[data-testid="stBaseButton-secondary"] {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    border: 1.5px solid #94A3B8 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #EDF2F7 !important;
    border-color: #475569 !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1) !important;
}
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-secondary"] div {
    color: #0F172A !important;
    font-weight: 600 !important;
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
/* ═══════════════════════════════════════════════════════════════
   OBSIDIAN ENGINEERING DARK THEME (AutoCAD / GitHub Dark inspired)
   ═══════════════════════════════════════════════════════════════ */

:root {
    --primary-color: #58A6FF !important;
    --background-color: #0D1117 !important;
    --secondary-background-color: #161B22 !important;
    --text-color: #F0F6FC !important;
}

/* 1. Global app background & text */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stMain"], .main, section.main, [data-testid="stBottom"] {
    background-color: #0D1117 !important;
    color: #F0F6FC !important;
}
.block-container {
    color: #F0F6FC !important;
}
html, body, [class*="css"] {
    color: #C9D1D9 !important;
}
h1, h2, h3, h4, h5, h6 {
    color: #F0F6FC !important;
}
p, span, label {
    color: #C9D1D9;
}
.mono {
    font-family: "SF Mono", "Menlo", "Consolas", monospace !important;
    font-size: 12px !important;
    color: #79C0FF !important;
    background-color: rgba(110, 118, 129, 0.2) !important;
    padding: 1px 4px !important;
    border-radius: 3px !important;
}

/* 2. Sidebar Dark */
[data-testid="stSidebar"] {
    background-color: #161B22 !important;
    border-right: 1px solid #30363D !important;
}
[data-testid="stSidebar"] .sidebar-section-label {
    color: #8B949E !important;
    border-bottom: 1px solid #30363D !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
    color: #C9D1D9 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    color: #F0F6FC !important;
}

/* 3. Header Dark */
[data-testid="stHeader"] {
    background-color: rgba(13, 17, 23, 0.96) !important;
    backdrop-filter: blur(8px);
}
.app-header {
    border-bottom: none !important;
}
.app-header-title {
    color: #F0F6FC !important;
}
.app-header-meta {
    color: #8B949E !important;
}
.app-header-divider {
    border-bottom: 1px solid #30363D !important;
}

/* 4. Tabs Dark */
[data-baseweb="tab-list"] {
    border-bottom: 1px solid #30363D !important;
    background-color: transparent !important;
}
[data-baseweb="tab"] {
    color: #8B949E !important;
    background: transparent !important;
}
[data-baseweb="tab"]:hover {
    color: #F0F6FC !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #58A6FF !important;
    border-bottom: 2px solid #58A6FF !important;
    font-weight: 600 !important;
}
[data-baseweb="tab-highlight"] {
    background-color: #58A6FF !important;
}
[data-baseweb="tab-border"] {
    background-color: #30363D !important;
}

/* 5. Segmented Control / Button Group Dark */
[data-testid="stButtonGroup"],
[data-testid="stSegmentedControl"] {
    display: inline-flex !important;
    background-color: #161B22 !important;
    border: 1.5px solid #30363D !important;
    border-radius: 7px !important;
    padding: 2px !important;
    gap: 2px !important;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.25) !important;
}
[data-testid="stButtonGroup"] button,
[data-testid="stSegmentedControl"] button {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 5px !important;
    padding: 4px 10px !important;
    min-height: 28px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButtonGroup"] button p,
[data-testid="stButtonGroup"] button span,
[data-testid="stButtonGroup"] button div,
[data-testid="stSegmentedControl"] button p,
[data-testid="stSegmentedControl"] button span,
[data-testid="stSegmentedControl"] button div {
    color: #8B949E !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}
[data-testid="stButtonGroup"] button:hover,
[data-testid="stSegmentedControl"] button:hover {
    background-color: #21262D !important;
}
[data-testid="stButtonGroup"] button:hover p,
[data-testid="stButtonGroup"] button:hover span,
[data-testid="stSegmentedControl"] button:hover p,
[data-testid="stSegmentedControl"] button:hover span {
    color: #F0F6FC !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #21262D !important;
    border: 1px solid #388BFD !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] p,
[data-testid="stButtonGroup"] button[aria-checked="true"] span,
[data-testid="stButtonGroup"] button[aria-checked="true"] div,
[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
[data-testid="stSegmentedControl"] button[aria-checked="true"] span,
[data-testid="stSegmentedControl"] button[aria-checked="true"] div {
    color: #58A6FF !important;
    font-weight: 700 !important;
}

/* 6. Inputs, Selectboxes, Dropdowns */
div[data-baseweb="select"] > div {
    background-color: #161B22 !important;
    color: #F0F6FC !important;
    border-color: #30363D !important;
}
div[data-baseweb="select"] span {
    color: #F0F6FC !important;
}
div[data-baseweb="popover"], ul[data-baseweb="menu"], [data-baseweb="menu"] li {
    background-color: #161B22 !important;
    color: #F0F6FC !important;
    border-color: #30363D !important;
}
[data-baseweb="menu"] li:hover {
    background-color: #21262D !important;
}
input, textarea {
    background-color: #0D1117 !important;
    color: #F0F6FC !important;
    border-color: #30363D !important;
}
input:focus, textarea:focus {
    border-color: #58A6FF !important;
}
[data-testid="stFileUploader"] {
    background-color: #161B22 !important;
    border: 1px dashed #30363D !important;
}
[data-testid="stFileUploaderDropzone"] {
    background-color: #161B22 !important;
}

/* 7. Cards & Containers Dark */
.landing-box {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
}
.landing-title {
    color: #F0F6FC !important;
}
.landing-subtitle {
    color: #8B949E !important;
}
.step-card {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
}
.step-num {
    color: #58A6FF !important;
}
.step-title {
    color: #F0F6FC !important;
}
.step-desc {
    color: #8B949E !important;
}
.own-model-card {
    background: #161B22 !important;
    border: 1px dashed #30363D !important;
}
.own-model-title {
    color: #F0F6FC !important;
}
.own-model-desc {
    color: #8B949E !important;
}
.own-model-hint {
    color: #58A6FF !important;
}
[data-testid="stMetric"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
}
[data-testid="stMetricLabel"] {
    color: #8B949E !important;
}
[data-testid="stMetricValue"] {
    color: #F0F6FC !important;
}
[data-testid="stExpander"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
}
[data-testid="stExpander"] summary {
    color: #F0F6FC !important;
}
[data-testid="stExpander"] summary:hover {
    background: #21262D !important;
}

/* 8. DataFrame Dark */
[data-testid="stDataFrame"] {
    background-color: #161B22 !important;
}
[data-testid="stDataFrame"] th {
    background-color: #21262D !important;
    color: #8B949E !important;
    border-bottom: 1px solid #30363D !important;
}
[data-testid="stDataFrame"] td {
    background-color: #161B22 !important;
    color: #F0F6FC !important;
    border-bottom: 1px solid #21262D !important;
}

/* 9. Buttons Dark */
[data-testid="stBaseButton-primary"] {
    background-color: #1F6FEB !important;
    color: #FFFFFF !important;
    border: 1.5px solid #1F6FEB !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #388BFD !important;
    border-color: #388BFD !important;
}
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="stBaseButton-primary"] div {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

[data-testid="stBaseButton-secondary"] {
    background-color: #21262D !important;
    color: #F0F6FC !important;
    border: 1.5px solid #484F58 !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #30363D !important;
    border-color: #58A6FF !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3) !important;
}
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-secondary"] div {
    color: #F0F6FC !important;
    font-weight: 600 !important;
}

/* 10. Alerts & Status in Dark Mode */
[data-testid="stAlert"] {
    background-color: #161B22 !important;
    border: 1px solid #30363D !important;
    color: #F0F6FC !important;
}
.triage-item {
    background: #161B22 !important;
    border-left: 3px solid #30363D !important;
}
.triage-title {
    color: #F0F6FC !important;
}
.triage-finding {
    color: #C9D1D9 !important;
}
.triage-fail { background: rgba(248, 81, 73, 0.12) !important; border-left-color: #F85149 !important; }
.triage-warn { background: rgba(210, 153, 34, 0.12) !important; border-left-color: #D29922 !important; }
.triage-pass { background: rgba(46, 160, 67, 0.12) !important; border-left-color: #3FB950 !important; }
.triage-info { background: rgba(110, 118, 129, 0.12) !important; border-left-color: #8B949E !important; }

/* 11. Overrides for any inline styles */
table { color: #C9D1D9 !important; }
table td { color: #C9D1D9 !important; }
div[style*="border-bottom: 1px solid #E5E7EB"], div[style*="border-bottom:1px solid #E5E7EB"] { border-bottom: 1px solid #30363D !important; }
div[style*="background:#E2E8F0"], div[style*="background: #E2E8F0"] { background: #21262D !important; }
span[style*="color: #111827"], span[style*="color:#111827"], strong[style*="color: #111827"], div[style*="color: #111827"], div[style*="color:#111827"] { color: #F0F6FC !important; }
span[style*="color: #374151"], span[style*="color:#374151"], div[style*="color: #374151"], div[style*="color:#374151"] { color: #C9D1D9 !important; }
span[style*="color: #6B7280"], span[style*="color:#6B7280"], div[style*="color: #6B7280"] { color: #8B949E !important; }
div[style*="background:#FAFAFA"], div[style*="background: #FAFAFA"], div[style*="background:#F9FAFB"] { background: #161B22 !important; border-color: #30363D !important; }
div[style*="border:1px solid #E5E7EB"] { border-color: #30363D !important; }
div[style*="background:#FEF2F2"] { background: rgba(248, 81, 73, 0.15) !important; }
div[style*="background:#FFFBEB"] { background: rgba(210, 153, 34, 0.15) !important; }
div[style*="background:#F0FDF4"] { background: rgba(46, 160, 67, 0.15) !important; }
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
[data-testid="stButtonGroup"] button,
[data-testid="stSegmentedControl"] button {
    min-height: 32px !important;
    padding: 5px 12px !important;
}
[data-testid="stButtonGroup"] button p,
[data-testid="stButtonGroup"] button span,
[data-testid="stSegmentedControl"] button p,
[data-testid="stSegmentedControl"] button span {
    font-size: 13.5px !important;
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
    font-size: 14px !important;
    padding: 10px 18px !important;
}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-secondary"] p {
    font-size: 14px !important;
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
        theme_val = st.session_state.get("top_theme_ctrl") or st.session_state.get("app_theme")
        dark_mode = (theme_val == "Tamna")
    if font_scale is None and hasattr(st, "session_state"):
        font_val = st.session_state.get("top_font_ctrl") or st.session_state.get("app_font_scale")
        font_scale = "large" if (font_val == "Veliki") else "normal"

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
        {badge_html}
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
