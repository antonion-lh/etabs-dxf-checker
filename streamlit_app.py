"""
streamlit_app.py — ETABS Model Checker
Professional structural engineering verification and curriculum audit system.
Design language: SAFE / Tekla / AutoCAD engineering standard (no emojis, functional colors, high contrast).
"""

import io
import math
import os
import tempfile
import warnings
from datetime import datetime

# Suppress PyParsing deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="ezdxf")
warnings.filterwarnings("ignore", message=".*addParseAction.*")
warnings.filterwarnings("ignore", message=".*setResultsName.*")

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status, run_structural_sanity_checks
from report import generate_pdf, generate_html
from curriculum_audit import run_curriculum_audit, calculate_audit_score
from results_parser import parse_etabs_results, create_demo_etabs_results

import importlib
import ui_styles
try:
    importlib.reload(ui_styles)
except Exception:
    pass
from ui_styles import (
    inject_app_css,
    render_header_bar,
    render_landing_screen,
    render_header_card,
    render_kpi_strip,
    render_audit_hero,
)
from ui_views import render_drawing, fig_2d, fig_3d, safe_df, render_instructions

# Backward compatibility aliases for test suite
_kpi_strip = render_kpi_strip
_fig_2d = fig_2d
_fig_3d = fig_3d
_safe_df = safe_df
_render_instructions = render_instructions
_render_drawing = render_drawing

# ─────────────────────────────────────────────────────────────
# Page Configuration & CSS
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ETABS Model Checker",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_app_css()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_SKOLA_E2K = os.path.join(SCRIPT_DIR, "STROSSMAYER_2.e2k") if os.path.exists(os.path.join(SCRIPT_DIR, "STROSSMAYER_2.e2k")) else os.path.join(SCRIPT_DIR, "demo_skola.e2k")
DEMO_SKOLA_PDF = os.path.join(SCRIPT_DIR, "OS_VARSAVSKA_arh_proj_dijelovi.pdf") if os.path.exists(os.path.join(SCRIPT_DIR, "OS_VARSAVSKA_arh_proj_dijelovi.pdf")) else os.path.join(SCRIPT_DIR, "demo_projekt_skola.pdf")

DEMO_COMMERCIAL_DXF = os.path.join(SCRIPT_DIR, "demo_commercial_building.dxf")
DEMO_COMMERCIAL_E2K = os.path.join(SCRIPT_DIR, "demo_commercial_building.e2k")
SMALL_SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SMALL_SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

STROSSMAYER_SHEET_MAP = {
    1: "Str. 1: Tehnički opis - Općenito i opseg radova",
    2: "Str. 2: Situacija i građevinska parcela",
    3: "Str. 3: Funkcija i organizacija prostora",
    4: "Str. 4: Konstruktivno ojačanje stubišta (NPI 200)",
    5: "Str. 5: Konstrukcija, materijali i seizmika (VIII MCS)",
    8: "Str. 8: Iskaz neto površina po etažama",
    10: "Str. 10: Iskaz BRP građevine",
    11: "Str. 11: Slojevi podova, stropova i zidova",
    14: "Str. 14: Tlocrt PRIZEMLJA",
    15: "Str. 15: Tlocrt I. KATA",
    16: "Str. 16: Tlocrt II. KATA",
    17: "Str. 17: Plan KROVIŠTA (Drvena krovna konstrukcija)",
    18: "Str. 18: Tlocrt KROVA",
    19: "Str. 19: Presjeci 1-1 i 2-2 & Južno pročelje",
    20: "Str. 20: Sjeverno, Istočno i Zapadno pročelje",
}

# ─────────────────────────────────────────────────────────────
# Performance Caching (Task 9b)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_parse_e2k(e2k_content: str, cfg: Config):
    return parse_e2k(io.StringIO(e2k_content), cfg)

@st.cache_data(show_spinner=False)
def _cached_parse_dxf_bytes(dxf_bytes: bytes, cfg: Config):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    try:
        tmp.write(dxf_bytes)
        tmp.close()
        return parse_dxf(tmp.name, cfg)
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass

@st.cache_data(show_spinner=False)
def _cached_validate(_etabs_data: dict, _df_dxf: pd.DataFrame, _cfg: Config):
    return validate(_etabs_data, _df_dxf, _cfg)

@st.cache_data(show_spinner=False)
def _cached_curriculum_audit(_etabs_data: dict, _results_data: dict = None):
    return run_curriculum_audit(_etabs_data, results_data=_results_data)

# ─────────────────────────────────────────────────────────────
# Sidebar: Minimal, Focused Engineering Controls (Task 1)
# ─────────────────────────────────────────────────────────────
def _sidebar() -> tuple:
    with st.sidebar:
        st.markdown("<div class='sidebar-section-label'>ETABS model</div>", unsafe_allow_html=True)
        if "use_demo" not in st.session_state:
            st.session_state["use_demo"] = False

        uploaded_e2k = None
        uploaded_drawing_file = None

        if st.session_state["use_demo"]:
            demo_name = st.session_state.get("demo_choice_key", "strossmayer")
            display_map = {
                "strossmayer": "STROSSMAYER_2.e2k",
                "commercial": "demo_commercial.e2k",
                "small": "sample_building.e2k",
            }
            cur_label = display_map.get(demo_name, "STROSSMAYER_2.e2k")
            st.markdown(f"<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ {cur_label}</div>", unsafe_allow_html=True)
            demo_desc_map = {
                "strossmayer": "1436 zidova · 4 etaže (OŠ Strossmayer)",
                "commercial": "304 stupa · Prizemlje DXF",
                "small": "4 stupa · 1 greda · 1 zid",
            }
            st.caption(demo_desc_map.get(demo_name, ""))

            new_demo = st.selectbox(
                "Promijeni demo model:",
                options=["strossmayer", "commercial", "small"],
                format_func=lambda x: {
                    "strossmayer": "OŠ J. J. Strossmayer (Zidana zgrada + PDF)",
                    "commercial":  "Poslovni centar (AB okvir + CAD DXF)",
                    "small":       "Referentni model (mali primjer)",
                }[x],
                index=["strossmayer", "commercial", "small"].index(
                    st.session_state.get("demo_choice_key", "strossmayer")
                ),
                key="demo_model_selector",
                label_visibility="collapsed",
            )
            if new_demo != st.session_state.get("demo_choice_key"):
                st.session_state["demo_choice_key"] = new_demo
                st.rerun()
        else:
            uploaded_e2k = st.file_uploader("Učitaj .e2k datoteku", type=["e2k", "$et", "txt"], key="sb_e2k_up", label_visibility="collapsed")

        st.markdown("<div class='sidebar-section-label'>Nacrt (CAD / PDF)</div>", unsafe_allow_html=True)

        uploaded_ref_drawing = None
        if st.session_state["use_demo"]:
            demo_name = st.session_state.get("demo_choice_key", "strossmayer")
            if demo_name == "strossmayer":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ OS_VARSAVSKA.pdf</div>", unsafe_allow_html=True)
                st.caption("20 stranica (Tehnički opis + nacrti)")
            elif demo_name == "commercial":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ commercial.dxf</div>", unsafe_allow_html=True)
                st.caption("CAD tlocrt stupova prizemlja")
                st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                uploaded_ref_drawing = st.file_uploader(
                    "Referentni PDF / slika uz CAD (opcija):",
                    type=["pdf", "jpg", "png", "jpeg"],
                    key="sb_ref_pdf_demo",
                    help="Priložite PDF ili sliku za usporedni split-screen prikaz uz komercijalni CAD model."
                )
            elif demo_name == "small":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ sample.dxf</div>", unsafe_allow_html=True)
                st.caption("CAD tlocrt")
        else:
            uploaded_drawing_file = st.file_uploader("Učitaj .dxf ili .pdf nacrt", type=["pdf", "dxf", "jpg", "png"], key="sb_drawing_up", label_visibility="collapsed")
            if uploaded_drawing_file and uploaded_drawing_file.name.lower().endswith(".dxf"):
                st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                uploaded_ref_drawing = st.file_uploader(
                    "Referentni PDF / slika uz CAD (opcija):",
                    type=["pdf", "jpg", "png", "jpeg"],
                    key="sb_ref_pdf_user",
                    help="Priložite PDF nacrt ili sliku za usporedni split-screen pregled uz CAD tlocrt."
                )

        # Tolerances & Scale (Task 1a)
        st.markdown("<div class='sidebar-section-label'>Tolerancije i mjerilo</div>", unsafe_allow_html=True)
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tol_pos_val = st.selectbox("Pozicija (m)", ["0.05", "0.10", "0.15", "0.20", "0.30"], index=2, key="sb_tol_pos")
            tol_frame = float(tol_pos_val)
            tol_area = max(tol_frame * 2.0, 0.30)
        with col_t2:
            tol_sec_val = st.selectbox("Presjek (mm)", ["1", "2", "5", "10", "20"], index=2, key="sb_tol_sec")
            tol_sec = float(tol_sec_val)

        is_dxf_selected = (
            (st.session_state.get("use_demo") and st.session_state.get("demo_choice_key") in ("commercial", "small"))
            or (not st.session_state.get("use_demo") and uploaded_drawing_file is not None and uploaded_drawing_file.name.lower().endswith(".dxf"))
        )
        if is_dxf_selected:
            unit_label = st.selectbox(
                "Jedinica u CAD crtežu (.dxf):",
                ["Centimetri (cm)", "Milimetri (mm)", "Metri (m)"],
                index=0,
                key="sb_dxf_unit_scale"
            )
            scale_map = {
                "Centimetri (cm)": 0.01,
                "Milimetri (mm)": 0.001,
                "Metri (m)": 1.0,
            }
            unit_scale = scale_map[unit_label]
        else:
            unit_scale = 0.01
            st.caption("Koordinate ETABS modela čitaju se iz .e2k zaglavlja. PDF nacrti koriste cm.")

        # Element extraction
        st.markdown("<div class='sidebar-section-label'>Kontrola elemenata</div>", unsafe_allow_html=True)
        chk_cols = st.checkbox("Stupovi", True, key="sb_chk_c")
        chk_beams = st.checkbox("Grede", True, key="sb_chk_b")
        chk_walls = st.checkbox("Zidovi", True, key="sb_chk_w")
        chk_slabs = st.checkbox("Ploče", True, key="sb_chk_s")

        elem_types = (
            (["columns"] if chk_cols  else []) +
            (["beams"]   if chk_beams else []) +
            (["walls"]   if chk_walls else []) +
            (["slabs"]   if chk_slabs else [])
        )

        # Phase 2 uploader (Task 1b)
        uploaded_results = None
        if not st.session_state.get("use_demo"):
            st.markdown("<div class='sidebar-section-label'>Rezultati proračuna</div>", unsafe_allow_html=True)
            st.caption("Opcija — Display → Show Tables → Export to Excel")
            uploaded_results = st.file_uploader(
                "ETABS tablice (.xlsx, .csv):",
                type=["xlsx", "xls", "csv"],
                key="sb_results_up",
                label_visibility="collapsed"
            )
        else:
            st.markdown("<div class='sidebar-section-label'>Rezultati proračuna</div>", unsafe_allow_html=True)
            demo_include_results = st.checkbox(
                "Uključi demo rezultate (Faza 2)",
                value=True,
                key="demo_include_results_chk"
            )
            st.session_state["demo_include_results"] = demo_include_results

        cfg = Config(
            dxf_unit_scale=unit_scale,
            spatial_tolerance_frame=tol_frame,
            spatial_tolerance_area=tol_area,
            section_tolerance_mm=tol_sec,
            extract_elements=elem_types,
            audit_materials=True,
            audit_loads=True,
            audit_restraints=True,
            report_hinges=True,
        )

        st.markdown("---")
        if st.session_state.get("use_demo"):
            if st.button("Isključi demo / Učitaj vlastiti projekt", use_container_width=True, key="btn_reset_session"):
                st.session_state["use_demo"] = False
                st.session_state["demo_choice_key"] = "strossmayer"
                st.session_state.pop("_header_badge", None)
                st.rerun()

    return uploaded_e2k, uploaded_drawing_file, cfg, uploaded_results, uploaded_ref_drawing

# ─────────────────────────────────────────────────────────────
# Main Application Flow
# ─────────────────────────────────────────────────────────────
def main():
    uploaded_e2k, uploaded_drawing_file, cfg, uploaded_results, uploaded_ref_drawing = _sidebar()

    # Determine Active Data Source
    use_demo = st.session_state.get("use_demo", False)
    demo_choice = st.session_state.get("demo_choice_key", "strossmayer")

    has_data = False
    is_pdf_mode = False
    dxf_bytes = None
    e2k_content = None
    uploaded_drawing = None
    demo_sheet_map = None
    project_label = None

    if use_demo:
        if demo_choice == "strossmayer":
            e2k_target = DEMO_SKOLA_E2K
            if os.path.exists(e2k_target):
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                uploaded_drawing = DEMO_SKOLA_PDF
                is_pdf_mode = True
                has_data = True
                demo_sheet_map = STROSSMAYER_SHEET_MAP
                project_label = "OŠ J. J. Strossmayer"
        elif demo_choice == "commercial":
            dxf_target = DEMO_COMMERCIAL_DXF
            e2k_target = DEMO_COMMERCIAL_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                with open(dxf_target, "rb") as f:
                    dxf_bytes = f.read()
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True
                is_pdf_mode = False
                project_label = "Poslovni centar"
                cfg.extract_elements = ["columns"]
                if uploaded_ref_drawing:
                    uploaded_drawing = uploaded_ref_drawing
        elif demo_choice == "small":
            dxf_target = SMALL_SAMPLE_DXF
            e2k_target = SMALL_SAMPLE_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                with open(dxf_target, "rb") as f:
                    dxf_bytes = f.read()
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True
                is_pdf_mode = False
                project_label = "Referentni model"
                if uploaded_ref_drawing:
                    uploaded_drawing = uploaded_ref_drawing

    elif uploaded_e2k:
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        project_label = uploaded_e2k.name
        if uploaded_drawing_file:
            fname_l = uploaded_drawing_file.name.lower()
            if fname_l.endswith(".dxf"):
                dxf_bytes = uploaded_drawing_file.getvalue()
                is_pdf_mode = False
                if uploaded_ref_drawing:
                    uploaded_drawing = uploaded_ref_drawing
            else:
                uploaded_drawing = uploaded_drawing_file
                is_pdf_mode = True
        else:
            is_pdf_mode = True
        has_data = True

    # Reset transient session state if active model changes
    cur_model_id = (demo_choice if use_demo else (project_label or "uploaded")) if has_data else None
    if st.session_state.get("_last_loaded_model_id") != cur_model_id:
        st.session_state["_last_loaded_model_id"] = cur_model_id
        st.session_state.pop("tab1_story_pills", None)
        st.session_state.pop("tab1_view_pills", None)
        st.session_state.pop("active_pdf_page", None)
        st.session_state.pop("_last_synced_story", None)
        st.session_state.pop("_active_pdf_filename", None)
        st.session_state.pop("audit_cat_filter", None)
        st.session_state.pop("audit_filter_status", None)
        st.session_state.pop("sub_elem_view", None)
        st.session_state.pop("elem_status_pills", None)
        if not has_data:
            st.session_state.pop("_header_badge", None)

    # ── Top App Header & Controls ─────────────────────────────
    is_dark = (st.session_state.get("app_theme") == "Tamna")
    active_badge = st.session_state.get("_header_badge") if has_data else None

    col_hdr, col_theme, col_font = st.columns([3.6, 0.85, 0.85])
    with col_hdr:
        try:
            render_header_bar(
                project_name=project_label,
                version="v2.1.0",
                status_badge=active_badge
            )
        except TypeError:
            render_header_bar(project_name=project_label, version="v2.1.0")

    with col_theme:
        theme_mode = st.segmented_control(
            "Tema:",
            options=["Svijetla", "Tamna"],
            default=st.session_state.get("app_theme", "Svijetla"),
            key="top_theme_ctrl",
            label_visibility="collapsed"
        ) or "Svijetla"
        if theme_mode != st.session_state.get("app_theme"):
            st.session_state["app_theme"] = theme_mode
            st.rerun()

    with col_font:
        font_choice = st.segmented_control(
            "Font:",
            options=["Normal", "Veliki"],
            default=st.session_state.get("app_font_scale", "Normal"),
            key="top_font_ctrl",
            label_visibility="collapsed"
        ) or "Normal"
        if font_choice != st.session_state.get("app_font_scale"):
            st.session_state["app_font_scale"] = font_choice
            st.rerun()

    st.markdown("<div class='app-header-divider'></div>", unsafe_allow_html=True)

    # ── Landing State: Minimalist clean screen ────────────────
    if not has_data:
        render_landing_screen()
        c_l1, c_l2 = st.columns(2, gap="large")
        with c_l1:
            lbl_c = "#F0F6FC" if is_dark else "#1E293B"
            st.markdown(f"<div style='margin-bottom: 8px; font-weight:600; color:{lbl_c}; font-size:14px;'>Ogledni inženjerski primjeri</div>", unsafe_allow_html=True)
            if st.button("OŠ Strossmayer — Zidana zgrada + PDF elaborat", use_container_width=True, type="primary"):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "strossmayer"
                st.rerun()
            if st.button("Poslovni centar — AB okvir + CAD DXF nacrt", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "commercial"
                st.rerun()
            if st.button("Referentni model — 4 stupa, 1 greda, 1 zid (brzi test)", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "small"
                st.rerun()
        with c_l2:
            st.markdown("""
            <div class="own-model-card">
              <div class="own-model-title">Učitavanje vlastitog projekta</div>
              <div class="own-model-desc">
                U lijevom bočnom izborniku učitajte <strong>.e2k</strong> tekstualnu datoteku iz ETABS-a te pripadajući <strong>.dxf</strong> ili <strong>.pdf</strong> nacrt.
              </div>
              <div class="own-model-hint">← Otvorite bočni izbornik za početak</div>
            </div>
            """, unsafe_allow_html=True)
        return

    # ── Process Model & Data ─────────────────────────────────
    with st.spinner("Obrada numeričkog modela..."):
        try:
            etabs_data = _cached_parse_e2k(e2k_content, cfg)
            if is_pdf_mode or dxf_bytes is None:
                all_items = []
                for elem_type, key in [("column", "columns"), ("beam", "beams"), ("wall", "walls"), ("slab", "slabs")]:
                    df_sub = etabs_data.get(key, pd.DataFrame())
                    if not df_sub.empty:
                        for _, row in df_sub.iterrows():
                            all_items.append({
                                "element_type": elem_type,
                                "status": "Za provjeru s PDF-om",
                                "etabs_name": row.get("name", ""),
                                "story": row.get("story", ""),
                                "etabs_x": row.get("x_start", row.get("centroid_x", 0.0)),
                                "etabs_y": row.get("y_start", row.get("centroid_y", 0.0)),
                                "etabs_z": row.get("z_end", row.get("centroid_z", row.get("z_start", 0.0))),
                                "etabs_section": row.get("section", row.get("prop_name", "")),
                                "etabs_w_mm": row.get("width_mm"),
                                "etabs_h_mm": row.get("height_mm", row.get("thickness_mm")),
                                "etabs_material": row.get("material", ""),
                                "dxf_dim_text": "—",
                                "dxf_dim1_mm": None,
                                "dxf_dim2_mm": None,
                                "xy_dist_m": None,
                                "notes": "Element u ETABS modelu",
                            })
                STANDARD_COLS = [
                    "element_type", "status", "etabs_name", "story", "etabs_x", "etabs_y", "etabs_z",
                    "etabs_section", "etabs_w_mm", "etabs_h_mm", "etabs_material",
                    "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm", "xy_dist_m", "notes"
                ]
                df_res = pd.DataFrame(all_items) if all_items else pd.DataFrame(columns=STANDARD_COLS)
                df_res.attrs["sanity_alerts"] = run_structural_sanity_checks(etabs_data, cfg)
                df_res.attrs["materials"] = etabs_data.get("materials", [])
                df_res.attrs["load_patterns"] = etabs_data.get("load_patterns", pd.DataFrame())
                df_res.attrs["area_loads"] = etabs_data.get("area_loads", pd.DataFrame())
                df_res.attrs["frame_loads"] = etabs_data.get("frame_loads", pd.DataFrame())
                df_res.attrs["restraints"] = etabs_data.get("restraints", pd.DataFrame())
                df_res.attrs["hinges"] = etabs_data.get("hinges", pd.DataFrame())
            else:
                df_dxf = _cached_parse_dxf_bytes(dxf_bytes, cfg)
                df_res = _cached_validate(etabs_data, df_dxf, cfg)

            # Phase 2 results handling (Task 4a)
            results_data = None
            if use_demo and st.session_state.get("demo_include_results", True):
                try:
                    results_data = parse_etabs_results(create_demo_etabs_results(etabs_data))
                    df_res.attrs["is_demo_results"] = True
                except Exception:
                    results_data = None
            elif uploaded_results is not None:
                try:
                    results_data = parse_etabs_results(uploaded_results)
                    df_res.attrs["is_demo_results"] = False
                except Exception:
                    results_data = None
            df_res.attrs["results_data"] = results_data

            audit_quick = _cached_curriculum_audit(etabs_data, results_data)
            score_quick = calculate_audit_score(audit_quick)
            g = score_quick.get("grade", 1)
            badge_colors = {5:"#16A34A", 4:"#2563EB", 3:"#D97706",
                            2:"#EA580C", 1:"#DC2626"}
            badge_labels = {5:"Izvrstan", 4:"Vrlo dobar", 3:"Dobar",
                            2:"Dovoljan", 1:"Nedovoljan"}
            st.session_state["_header_badge"] = (
                f"Ocjena {g} — {badge_labels.get(g,'?')}",
                badge_colors.get(g, "#6B7280")
            )

        except Exception as err:
            st.error(f"Pogreška tijekom obrade modela: {err}")
            return

    # Stories configuration
    stories = etabs_data.get("stories", [])
    if not stories:
        stories = [{"name": "Prizemlje", "display_name": "Prizemlje", "z_bottom": 0.0, "z_top": 4.0, "height": 4.0}]

    # ── Main Tabs (4 clean sections, NO EMOJIS) ───────────────
    t_model, t_audit, t_elements, t_report = st.tabs([
        "Model",
        "Revizija",
        "Elementi",
        "Izvještaj",
    ])

    # ── TAB 1: Model (Task 2) ─────────────────────────────────
    with t_model:
        story_names = [s.get("display_name", s["name"]) for s in stories]
        story_opts = story_names + ["Sve etaže"]
        has_drawing = (uploaded_drawing is not None)

        if has_drawing:
            view_opts = ["2D Tlocrt", "3D Model", "Usporedno s nacrtom", "Samo nacrt"]
        else:
            view_opts = ["2D Tlocrt", "3D Model"]

        tb_col1, tb_col_z, tb_col2 = st.columns([2.8, 1.2, 3.0])
        with tb_col1:
            sel_story = st.segmented_control(
                "Odabir etaže:",
                options=story_opts,
                default=story_names[0] if story_names else "Sve etaže",
                key="tab1_story_pills",
                label_visibility="collapsed"
            ) or story_opts[0]

        if sel_story != "Sve etaže" and sel_story in story_names:
            curr_idx = story_names.index(sel_story)
            selected_story_data = stories[curr_idx]
            active_story_name = selected_story_data["name"]
            chosen_z = selected_story_data["z_top"]
        else:
            active_story_name = None
            selected_story_data = None
            chosen_z = None

        with tb_col_z:
            if sel_story != "Sve etaže" and selected_story_data:
                z_bot = selected_story_data.get("z_bottom", 0.0)
                z_top = selected_story_data.get("z_top", 4.0)
                z_bg = "#161B22" if is_dark else "#F9FAFB"
                z_bdr = "#30363D" if is_dark else "#E5E7EB"
                z_txt = "#8B949E" if is_dark else "#6B7280"
                st.markdown(
                    f"<div class='mono' style='font-size:11px; color:{z_txt};"
                    f"padding:4px 8px; background:{z_bg}; border:1px solid "
                    f"{z_bdr}; border-radius:4px; display:inline-block; margin-top:2px;'>"
                    f"Z = {z_bot:.1f} – {z_top:.1f} m</div>",
                    unsafe_allow_html=True
                )

        with tb_col2:
            sel_view = st.segmented_control(
                "Prikaz modela:",
                options=view_opts,
                default="2D Tlocrt",
                key="tab1_view_pills",
                label_visibility="collapsed"
            ) or "2D Tlocrt"

        if sel_story != "Sve etaže" and selected_story_data:
            if "story" in df_res.columns:
                df_eval = df_res[
                    (df_res["story"] == active_story_name) |
                    (df_res["status"] == Status.DXF_ONLY)
                ].copy()
                if df_eval[df_eval["status"] != Status.DXF_ONLY].empty and not df_res.empty:
                    df_eval = df_res.copy()
            else:
                z_bot = selected_story_data["z_bottom"] - 0.20
                z_top = selected_story_data["z_top"] + 0.20
                df_eval = df_res[
                    ((df_res["etabs_z"] >= z_bot) & (df_res["etabs_z"] <= z_top)) |
                    (df_res["status"] == Status.DXF_ONLY)
                ].copy()
                if df_eval[df_eval["status"] != Status.DXF_ONLY].empty and not df_res.empty:
                    df_eval = df_res.copy()
            df_eval.attrs = dict(df_res.attrs)
        else:
            df_eval = df_res.copy()
            df_eval.attrs = dict(df_res.attrs)

        cad_plot_cfg = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
        # Viewport rendering by sel_view (Task 2b)
        if sel_view == "3D Model":
            st.plotly_chart(fig_3d(df_res, etabs_data, active_story_name=active_story_name, etabs_color_mode=True), use_container_width=True, config=cad_plot_cfg)
        elif sel_view == "Usporedno s nacrtom" and has_drawing:
            col_m, col_d = st.columns(2, gap="medium")
            with col_m:
                m_txt_c = "#F0F6FC" if is_dark else "#111827"
                st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: {m_txt_c}; margin-bottom: 6px;'>Numerički model (ETABS)</div>", unsafe_allow_html=True)
                st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True, config=cad_plot_cfg)
            with col_d:
                render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name, demo_sheet_map=demo_sheet_map)
        elif sel_view == "Samo nacrt" and has_drawing:
            render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name, demo_sheet_map=demo_sheet_map)
        else:
            st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True, config=cad_plot_cfg)

    # ── TAB 2: Revizija (Triage Code-Review) (Tasks 3, 4, 5, 6) ─
    with t_audit:
        results_data = df_res.attrs.get("results_data")
        audit_results = _cached_curriculum_audit(etabs_data, results_data)
        score_data = calculate_audit_score(audit_results)

        # Summary Bar
        grade_num = score_data.get("grade", 1)
        grade_simple = {5: "Izvrstan", 4: "Vrlo dobar", 3: "Dobar", 2: "Dovoljan", 1: "Nedovoljan"}.get(grade_num, "Dobar")
        pct_num = score_data.get("percentage", 0.0)
        badge_colors = {
            5: "#3FB950" if is_dark else "#16A34A",
            4: "#58A6FF" if is_dark else "#2563EB",
            3: "#D29922" if is_dark else "#D97706",
            2: "#DB6D28" if is_dark else "#EA580C",
            1: "#F85149" if is_dark else "#DC2626"
        }
        bar_color = badge_colors.get(grade_num, "#8B949E" if is_dark else "#6B7280")
        score_title_col = "#F0F6FC" if is_dark else "#111827"
        score_sub_col = "#8B949E" if is_dark else "#6B7280"
        score_bdr_col = "#30363D" if is_dark else "#E5E7EB"
        score_trk_col = "#21262D" if is_dark else "#E2E8F0"

        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid {score_bdr_col}; padding-bottom: 10px; margin-bottom: 8px;">
          <div>
            <span style="font-size: 16px; font-weight: 600; color: {score_title_col};">Ocjena: {grade_num} — {grade_simple}</span>
            <span style="color: {score_sub_col}; font-size: 13px; margin-left: 12px;">{pct_num} / 100 bodova</span>
            <span style="color: {score_sub_col}; font-size: 12px; margin-left: 12px;">{score_data.get('grade_label', '')}</span>
          </div>
          <div class="mono" style="color: {score_sub_col}; font-size: 12px;">
            {len(audit_results)} točaka provjereno
          </div>
        </div>
        <div style="background:{score_trk_col}; border-radius:3px; height:5px; width:100%; margin-bottom:14px; overflow:hidden;">
          <div style="background:{bar_color}; width:{min(max(pct_num, 0), 100)}%; height:100%; border-radius:3px;"></div>
        </div>
        """, unsafe_allow_html=True)

        sanity_alerts = df_res.attrs.get("sanity_alerts", [])
        if sanity_alerts:
            for alert in sanity_alerts:
                sev = alert.get("severity", "WARNING")
                if sev == "ERROR":
                    bg = "rgba(248, 81, 73, 0.15)" if is_dark else "#FEF2F2"
                    bc = "#F85149" if is_dark else "#DC2626"
                    prefix = "Greška"
                else:
                    bg = "rgba(210, 153, 34, 0.15)" if is_dark else "#FFFBEB"
                    bc = "#D29922" if is_dark else "#D97706"
                    prefix = "Upozorenje"
                txt_c = "#F0F6FC" if is_dark else "#374151"
                st.markdown(
                    f'<div style="background:{bg}; border-left:3px solid {bc};'
                    f'border-radius:0 4px 4px 0; padding:8px 12px;'
                    f'margin-bottom:6px; font-size:12px; color:{txt_c};">'
                    f'<strong style="color:{bc};">{prefix} · '
                    f'{alert.get("category","")}</strong> — '
                    f'{alert.get("issue","")}</div>',
                    unsafe_allow_html=True
                )

        # Task 3: Engineering KPI cards (T30, T31, T34, T51)
        c30 = next((a for a in audit_results if a["num"] == 30), None)
        c31 = next((a for a in audit_results if a["num"] == 31), None)
        c34 = next((a for a in audit_results if a["num"] == 34), None)
        c51 = next((a for a in audit_results if a["num"] == 51), None)

        card_data = [
            ("Površina zidova",    "T31",  c31, "Ciljano 3.0–4.0% tlocrta"),
            ("Masa zgrade",        "T30",  c30, "Procjena W_est"),
            ("Faktor prevrtanja",  "T34",  c34, "SF ≥ 1.50"),
            ("Torzija / Simetrija","T51",  c51, "Ekscentričnost ex, ey"),
        ]

        cols = st.columns(4)
        for col, (label, tnum, item, hint) in zip(cols, card_data):
            finding_short = item["finding"][:60] + "..." if item else "—"
            status_color = ("#3FB950" if is_dark else "#16A34A") if (item and item["status"] == "PASS") else \
                           ("#D29922" if is_dark else "#D97706") if (item and item["status"] == "WARNING") else \
                           ("#F85149" if is_dark else "#DC2626") if (item and item["status"] == "FAIL") else \
                           ("#8B949E" if is_dark else "#6B7280")
            card_bg = "#161B22" if is_dark else "#FAFAFA"
            card_bdr = "#30363D" if is_dark else "#E5E7EB"
            card_lbl = "#8B949E" if is_dark else "#6B7280"
            card_val = "#F0F6FC" if is_dark else "#111827"
            col.markdown(f"""
            <div style="border:1px solid {card_bdr}; border-left:3px solid {status_color};
                 border-radius:4px; padding:10px 12px; background:{card_bg};">
              <div style="font-size:10px; font-weight:700; color:{card_lbl};
                   text-transform:uppercase; letter-spacing:0.05em;">
                   {tnum} · {label}</div>
              <div style="font-size:12px; color:{card_val}; margin:4px 0;
                   line-height:1.4;">{finding_short}</div>
              <div style="font-size:10px; color:{status_color}; font-weight:600;">{hint}</div>
            </div>""", unsafe_allow_html=True)

        # Task 4: Faza 2 Dashboard
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if results_data and results_data.get("has_results"):
            if df_res.attrs.get("is_demo_results"):
                st.info("Demo rezultati: generirani automatski za prikaz Faze 2.")

            res_sum = results_data.get("summary", {})
            d_val = res_sum.get("max_drift_overall", 0.0)
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric(
                "Maks. katni pomak",
                f"{d_val:.4f}",
                "unutar EC8" if d_val <= 0.0050 else "prelazi limit"
            )
            v_max = max(res_sum.get("base_shear_x_kn", 0), res_sum.get("base_shear_y_kn", 0))
            rc2.metric("V_base", f"{v_max:,.0f} kN")
            rc3.metric(
                "Pritisak na tlo",
                f"{res_sum.get('max_soil_pressure_kpa', 0):.0f} kPa",
                "odizanje" if res_sum.get("has_soil_uplift") else "bez odizanja"
            )
            rc4.metric(
                "PMM kritični stup",
                f"{res_sum.get('max_pmm_ratio', 0.0):.2f}",
                res_sum.get("critical_frame", "—")
            )

            drifts = res_sum.get("drift_by_story", [])
            df_sf = results_data.get("story_forces", pd.DataFrame())
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                if drifts:
                    fig_drift = go.Figure()
                    fig_drift.add_trace(go.Scatter(
                        x=[d["drift"] for d in drifts],
                        y=[d["story"] for d in drifts],
                        mode="lines+markers",
                        line=dict(color="#2563EB", width=2),
                        marker=dict(size=7, color="#2563EB"),
                        name="Katni pomak"
                    ))
                    fig_drift.add_vline(
                        x=0.0050, line_dash="dash", line_color="#DC2626",
                        annotation_text="EC8 ≤ 5.0‰"
                    )
                    is_dark = (st.session_state.get("app_theme") == "Tamna")
                    c_bg = "#131B2E" if is_dark else "#FFFFFF"
                    c_txt = "#F8FAFC" if is_dark else "#111827"
                    c_grid = "#1E293B" if is_dark else "#F1F5F9"

                    fig_drift.update_layout(
                        title=dict(text="Katni pomaci (Story Drift)", font=dict(color=c_txt)),
                        xaxis=dict(title="dr [-]", gridcolor=c_grid, tickfont=dict(color=c_txt), title_font=dict(color=c_txt)),
                        yaxis=dict(title="Etaža", gridcolor=c_grid, tickfont=dict(color=c_txt), title_font=dict(color=c_txt)),
                        height=260, margin=dict(l=40, r=20, t=36, b=30),
                        plot_bgcolor=c_bg, paper_bgcolor=c_bg
                    )
                    st.plotly_chart(fig_drift, use_container_width=True, config={"displaylogo": False})
            with c_g2:
                if not df_sf.empty:
                    col_v = next((c for c in ["VX", "vx", "Vx"] if c in df_sf.columns), None)
                    col_s = next((c for c in ["Story", "story"] if c in df_sf.columns), None)
                    if col_v and col_s:
                        grp = df_sf.groupby(col_s)[col_v].apply(lambda s: s.abs().max()).reset_index()
                        fig_sf = go.Figure(go.Bar(
                            x=grp[col_s], y=grp[col_v],
                            marker_color="#60A5FA" if is_dark else "#374151"
                        ))
                        fig_sf.update_layout(
                            title=dict(text="Poprečne sile po etažama (kN)", font=dict(color=c_txt)),
                            xaxis=dict(title="Etaža", gridcolor=c_grid, tickfont=dict(color=c_txt), title_font=dict(color=c_txt)),
                            yaxis=dict(title="Vx (kN)", gridcolor=c_grid, tickfont=dict(color=c_txt), title_font=dict(color=c_txt)),
                            height=260, margin=dict(l=40, r=20, t=36, b=30),
                            plot_bgcolor=c_bg, paper_bgcolor=c_bg
                        )
                        st.plotly_chart(fig_sf, use_container_width=True, config={"displaylogo": False})
        else:
            st.caption("Opcija — učitajte ETABS tablice u sidebar za prikaz katnih pomaka, poprečnih sila i provjere armature.")

        # Task 5: Category filter and Markdown download
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        c_f1, c_f2, c_f3 = st.columns([1.8, 1.8, 1.4])

        with c_f1:
            all_cats = ["Sve kategorije"] + sorted(set(
                a.get("category", "") for a in audit_results if a.get("category")
            ))
            selected_cat = st.selectbox(
                "Kategorija:", all_cats, key="audit_cat_filter",
                label_visibility="collapsed"
            )

        with c_f2:
            flt_status = st.selectbox(
                "Status:",
                ["Sve točke", "Upozorenja i pogreške", "Usklađene točke"],
                key="audit_filter_status",
                label_visibility="collapsed"
            )

        with c_f3:
            audit_md = (
                f"# Evaluacija modela\n\n"
                f"Ocjena: {score_data['grade']}/5 ({score_data['grade_label']})\n"
                f"Indeks: {score_data['percentage']}%\n\n---\n\n"
            )
            for item in audit_results:
                audit_md += f"### T{item['num']} — {item['title']} [{item['status']}]\n"
                audit_md += f"- Nalaz: {item['finding']}\n"
                audit_md += f"- Pravilo: {item['rule']}\n"
                if item.get("recommendation"):
                    audit_md += f"- Preporuka: {item['recommendation']}\n"
                audit_md += "\n"
            st.download_button(
                "Preuzmi izvješće (.md)",
                data=audit_md,
                file_name="evaluacija_modela.md",
                mime="text/markdown",
                use_container_width=True,
                key="dl_audit_md"
            )

        if selected_cat != "Sve kategorije":
            audit_results_filtered = [
                a for a in audit_results if a.get("category") == selected_cat
            ]
        else:
            audit_results_filtered = audit_results

        if "Upozorenja" in flt_status:
            audit_results_filtered = [
                a for a in audit_results_filtered
                if a["status"] in ("WARNING", "FAIL")
            ]
        elif "Usklađene" in flt_status:
            audit_results_filtered = [
                a for a in audit_results_filtered if a["status"] == "PASS"
            ]

        attention_items = [a for a in audit_results_filtered
                           if a.get("status") in ("FAIL", "WARNING")]
        pass_items      = [a for a in audit_results_filtered
                           if a.get("status") == "PASS"]
        info_items      = [a for a in audit_results_filtered
                           if a.get("status") == "INFO"]

        # Task 6: Triage details with st.expander
        if attention_items:
            att_title_c = "#F0F6FC" if is_dark else "#111827"
            st.markdown(f"<div style='font-size: 14px; font-weight: 600; color: {att_title_c}; margin: 12px 0 8px 0;'>Zahtijeva pažnju ({len(attention_items)})</div>", unsafe_allow_html=True)
            for item in attention_items:
                border_col = "#F85149" if (is_dark and item["status"] == "FAIL") else "#DC2626" if item["status"] == "FAIL" else "#D29922" if is_dark else "#D97706"
                with st.expander(
                    f"{'✗' if item['status'] == 'FAIL' else '⚠'} "
                    f"T{item['num']} · {item['title']}",
                    expanded=(item["status"] == "FAIL")
                ):
                    st.markdown(f"**Nalaz u modelu:** {item['finding']}")
                    st.markdown(f"*Pravilo:* {item['rule']}")
                    if item.get("bullets"):
                        for b in item["bullets"]:
                            st.markdown(f"- {b}")
                    if item.get("recommendation"):
                        st.info(f"Uputa za ispravak: {item['recommendation']}")
        elif "Usklađene" not in flt_status:
            pass_c = "#3FB950" if is_dark else "#16A34A"
            st.markdown(f"<div style='color: {pass_c}; font-weight: 600; margin: 12px 0;'>✓ Nema uočenih grešaka ni upozorenja u modelu.</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        with st.expander(f"Zadovoljava ({len(pass_items)})", expanded=False):
            mut_c = "#8B949E" if is_dark else "#6B7280"
            for item in pass_items:
                st.markdown(
                    f"✓ **T{item['num']}** {item['title']} — "
                    f"<span style='color:{mut_c}'>{item['finding'][:80]}</span>",
                    unsafe_allow_html=True
                )

        with st.expander(f"Info / ne primjenjuje se ({len(info_items)})", expanded=False):
            info_mut_c = "#8B949E" if is_dark else "#9CA3AF"
            for item in info_items:
                st.markdown(
                    f"○ **T{item['num']}** {item['title']} — "
                    f"<span style='color:{info_mut_c}'>{item['finding'][:80]}</span>",
                    unsafe_allow_html=True
                )

    # ── TAB 3: Elementi (Task 7) ───────────────────────────────
    with t_elements:
        sub_view = st.segmented_control(
            "Prikaz:",
            options=["Geometrija i presjeci", "Materijali i opterećenja", "Oslonci i zglobovi"],
            default="Geometrija i presjeci",
            key="sub_elem_view",
            label_visibility="collapsed"
        ) or "Geometrija i presjeci"

        if sub_view == "Geometrija i presjeci":
            n_match = len(df_res[df_res["status"] == Status.MATCH]) if "status" in df_res.columns else 0
            n_mis   = len(df_res[df_res["status"] == Status.SECTION_MISMATCH]) if "status" in df_res.columns else 0
            n_etabs = len(df_res[df_res["status"] == Status.ETABS_ONLY]) if "status" in df_res.columns else 0
            n_dxf   = len(df_res[df_res["status"] == Status.DXF_ONLY]) if "status" in df_res.columns else 0

            pill_opts = ["Svi"]
            if not is_pdf_mode:
                pill_opts.extend([
                    f"✓ Usklađeno ({n_match})",
                    f"⚠ Odstupanje ({n_mis})",
                    f"✗ Samo ETABS ({n_etabs})",
                    f"○ Samo nacrt ({n_dxf})"
                ])

            if is_pdf_mode:
                st.caption(
                    "PDF mod — prikaz elemenata iz ETABS modela bez "
                    "geometrijske usporedbe s nacrtom."
                )

            dfd = df_res.copy()
            total_el = len(dfd)
            if total_el > 0 and not is_pdf_mode and "status" in dfd.columns:
                n_ok  = len(dfd[dfd["status"] == Status.MATCH])
                n_mis = len(dfd[dfd["status"] == Status.SECTION_MISMATCH])
                n_et  = len(dfd[dfd["status"] == Status.ETABS_ONLY])
                n_dx  = len(dfd[dfd["status"] == Status.DXF_ONLY])
                pct   = round(100 * n_ok / total_el) if total_el else 0
                tot_c = "#F0F6FC" if is_dark else "#111827"
                ok_c = "#3FB950" if is_dark else "#16A34A"
                mis_c = "#D29922" if is_dark else "#D97706"
                et_c = "#F85149" if is_dark else "#DC2626"
                dx_c = "#58A6FF" if is_dark else "#2563EB"
                mut_c = "#8B949E" if is_dark else "#6B7280"
                st.markdown(
                    f'<div style="font-size:12px; color:{mut_c};'
                    f'margin-bottom:10px;">'
                    f'<span style="color:{tot_c}; font-weight:600;">'
                    f'{total_el} elemenata</span>'
                    f'&nbsp;·&nbsp;'
                    f'<span style="color:{ok_c};">{n_ok} usklađeno</span>'
                    f'&nbsp;·&nbsp;'
                    f'<span style="color:{mis_c};">{n_mis} odstupanje</span>'
                    f'&nbsp;·&nbsp;'
                    f'<span style="color:{et_c};">{n_et} samo ETABS</span>'
                    f'&nbsp;·&nbsp;'
                    f'<span style="color:{dx_c};">{n_dx} samo nacrt</span>'
                    f'&nbsp;·&nbsp;'
                    f'<strong style="color:{tot_c};">{pct}% usklađeno</strong>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            col_f1, col_f2, col_f3, col_f4 = st.columns([2.3, 1.2, 1.5, 1.0])
            with col_f1:
                sel_pill = st.segmented_control(
                    "Status elementa:",
                    options=pill_opts,
                    default="Svi",
                    key="elem_status_pills",
                    label_visibility="collapsed"
                ) or "Svi"

            if "Usklađeno" in sel_pill:
                dfd = dfd[dfd["status"] == Status.MATCH]
            elif "Odstupanje" in sel_pill:
                dfd = dfd[dfd["status"] == Status.SECTION_MISMATCH]
            elif "Samo ETABS" in sel_pill:
                dfd = dfd[dfd["status"] == Status.ETABS_ONLY]
            elif "Samo nacrt" in sel_pill:
                dfd = dfd[dfd["status"] == Status.DXF_ONLY]

            with col_f2:
                ty_opts = ["Svi tipovi"] + sorted(
                    dfd["element_type"].dropna().unique().tolist()
                ) if "element_type" in dfd.columns else ["Svi tipovi"]
                ty_f = st.selectbox("Tip:", ty_opts, key="geo_type", label_visibility="collapsed")
                if ty_f != "Svi tipovi":
                    dfd = dfd[dfd["element_type"] == ty_f]

            with col_f3:
                search_txt = st.text_input("Pretraga", placeholder="Naziv, presjek...", label_visibility="collapsed", key="tb_srch")

            with col_f4:
                st.download_button(
                    "Izvoz .csv",
                    data=dfd.to_csv(index=False).encode("utf-8"),
                    file_name=f"elementi_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_dl_csv_tab3"
                )

            if search_txt:
                q = search_txt.lower()
                dfd = dfd[dfd.apply(lambda r: q in str(r.to_dict()).lower(), axis=1)]

            # Display table
            vcols = [
                "element_type", "status", "etabs_name", "story", "etabs_section",
                "etabs_w_mm", "etabs_h_mm", "dxf_dim_text", "xy_dist_m", "notes"
            ]
            vcols = [c for c in vcols if c in dfd.columns]
            tbl = safe_df(dfd[vcols], {
                "etabs_w_mm": "{:.0f}",
                "etabs_h_mm": "{:.0f}",
                "xy_dist_m": "{:.2f}",
            })
            st.dataframe(
                tbl,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "element_type":  st.column_config.TextColumn("Tip"),
                    "etabs_name":    st.column_config.TextColumn("ETABS ID"),
                    "story":         st.column_config.TextColumn("Etaža"),
                    "etabs_section": st.column_config.TextColumn("Presjek"),
                    "etabs_w_mm":    st.column_config.TextColumn("b (mm)"),
                    "etabs_h_mm":    st.column_config.TextColumn("h (mm)"),
                    "dxf_dim_text":  st.column_config.TextColumn("CAD oznaka"),
                    "xy_dist_m":     st.column_config.TextColumn("Odmak (m)"),
                    "notes":         st.column_config.TextColumn("Napomena"),
                }
            )

        elif sub_view == "Materijali i opterećenja":
            mc, lc = st.columns(2, gap="large")
            with mc:
                st.markdown("**Klase materijala**")
                mats = pd.DataFrame(df_res.attrs.get("materials", []))
                if not mats.empty:
                    st.dataframe(
                        safe_df(mats, {
                            "E_gpa": "{:.1f}", "fc_mpa": "{:.1f}",
                            "fy_mpa": "{:.1f}", "fu_mpa": "{:.1f}"
                        }),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "name":   st.column_config.TextColumn("Naziv"),
                            "type":   st.column_config.TextColumn("Tip"),
                            "E_gpa":  st.column_config.TextColumn("E (GPa)"),
                            "fc_mpa": st.column_config.TextColumn("fck (MPa)"),
                            "fy_mpa": st.column_config.TextColumn("fyk (MPa)"),
                            "fu_mpa": st.column_config.TextColumn("fuk (MPa)"),
                        }
                    )
                else:
                    st.caption("Nema definiranih materijala.")

            with lc:
                st.markdown("**Uzorci opterećenja**")
                pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
                if not pats.empty:
                    st.dataframe(
                        safe_df(pats, {"self_weight_mult": "{:.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "name":             st.column_config.TextColumn("Uzorak"),
                            "type":             st.column_config.TextColumn("Tip"),
                            "self_weight_mult": st.column_config.TextColumn("SW faktor"),
                        }
                    )

                aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
                if not aloads.empty:
                    st.markdown("**Plošna opterećenja (kN/m²)**")
                    st.dataframe(safe_df(aloads), use_container_width=True, hide_index=True)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            with st.expander("Kataloška baza europskih čeličnih profila (EN 10365 / EN 10210)", expanded=False):
                st.caption("Pretraživanje i uvid u dimenzije standardnih IPE, HEA, HEB, HEM, UPN i SHS/RHS čeličnih profila.")
                c_st1, c_st2 = st.columns([1.5, 2.5])
                with c_st1:
                    st_query = st.text_input("Unesite profil:", value="HEA 240", key="steel_cat_query_tab3")
                with c_st2:
                    from steel_catalog import lookup_steel_section
                    info = lookup_steel_section(st_query) if st_query else None
                    if info:
                        st_txt_c = "#F0F6FC" if is_dark else "#111827"
                        st.markdown(
                            f"<div style='font-size:13px; color:{st_txt_c}; padding:4px 0;'>"
                            f"<strong>Profil:</strong> <span class='mono'>{info['name']}</span> ({info.get('shape', 'profil')})<br>"
                            f"• Visina <em>h</em> = <strong>{info.get('height_mm', '-')} mm</strong> | "
                            f"Širina <em>b</em> = <strong>{info.get('width_mm', '-')} mm</strong><br>"
                            f"• Hrbat <em>t<sub>w</sub></em> = <strong>{info.get('tw', '-')} mm</strong> | "
                            f"Pojas <em>t<sub>f</sub></em> = <strong>{info.get('tf', '-')} mm</strong><br>"
                            f"• Površina <em>A</em> = <strong>{info.get('A', '-')} cm²</strong>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.info("Profil nije pronađen u bazi (provjerite format zapisa, npr. IPE 300, HEA 240, UPN 160, SHS 100x5).")

        elif sub_view == "Oslonci i zglobovi":
            sc, hc = st.columns(2, gap="large")
            with sc:
                st.markdown("**Temeljni oslonci**")
                rests = etabs_data.get("restraints")
                if not isinstance(rests, pd.DataFrame):
                    rests = pd.DataFrame(rests if isinstance(rests, list) else [])
                if not rests.empty and "joint_name" in rests.columns:
                    rcols = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in rests.columns]
                    st.dataframe(
                        safe_df(rests[rcols], {"x": "{:.2f}", "y": "{:.2f}", "z": "{:.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "joint_name":     st.column_config.TextColumn("Čvor"),
                            "x":              st.column_config.TextColumn("X (m)"),
                            "y":              st.column_config.TextColumn("Y (m)"),
                            "z":              st.column_config.TextColumn("Z (m)"),
                            "restraint_type": st.column_config.TextColumn("Tip"),
                            "is_supported":   st.column_config.CheckboxColumn("Poduprt"),
                        }
                    )
                else:
                    st.caption("Nema podataka o osloncima.")

            with hc:
                st.markdown("**Plastični zglobovi (Pushover)**")
                hinges = etabs_data.get("hinges")
                if not isinstance(hinges, pd.DataFrame):
                    hinges = pd.DataFrame(hinges if isinstance(hinges, list) else [])
                if not hinges.empty and "frame_name" in hinges.columns:
                    hcols = [c for c in ["frame_name", "hinge_prop", "rel_dist", "dof"] if c in hinges.columns]
                    st.dataframe(
                        safe_df(hinges[hcols], {"rel_dist": "{:.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "frame_name": st.column_config.TextColumn("Element"),
                            "hinge_prop": st.column_config.TextColumn("Svojstvo"),
                            "rel_dist":   st.column_config.TextColumn("Pozicija"),
                            "dof":        st.column_config.TextColumn("DOF"),
                        }
                    )
                else:
                    st.caption("Nema plastičnih zglobova (linearni proračun).")

    # ── TAB 4: Izvještaj (Task 8) ──────────────────────────────
    with t_report:
        hdr_c = "#F0F6FC" if is_dark else "#111827"
        st.markdown(f"<div style='font-size: 15px; font-weight: 600; color: {hdr_c}; margin-bottom: 12px;'>Revizijski elaborat</div>", unsafe_allow_html=True)

        if df_res is None or df_res.empty:
            st.info("Nema podataka za generiranje elaborata. Učitajte model ili odaberite demo projekt.")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y.")
            results_data = df_res.attrs.get("results_data")
            score_data = calculate_audit_score(_cached_curriculum_audit(etabs_data, results_data))
            grade_num = score_data.get("grade", 1)
            grade_simple = {5: "Izvrstan", 4: "Vrlo dobar", 3: "Dobar", 2: "Dovoljan", 1: "Nedovoljan"}.get(grade_num, "Dobar")

            try:
                html_code = generate_html(df_res, None, cfg)
            except Exception as _e:
                html_code = f"<p>Greška pri generiranju izvještaja: {_e}</p>"

            _model_filename = (
                os.path.basename(DEMO_SKOLA_E2K)      if (use_demo and demo_choice == "strossmayer") else
                os.path.basename(DEMO_COMMERCIAL_E2K) if (use_demo and demo_choice == "commercial") else
                os.path.basename(SMALL_SAMPLE_E2K)    if (use_demo and demo_choice == "small") else
                (project_label or "model.e2k")
            )

            meta_col1, meta_col2 = st.columns([2, 3])
            with meta_col1:
                tbl_txt = "#F0F6FC" if is_dark else "#374151"
                tbl_lbl = "#8B949E" if is_dark else "#6B7280"
                st.markdown(f"""
                <table style="width: 100%; font-size: 13px; color: {tbl_txt}; border-collapse: collapse;">
                  <tr><td style="padding: 4px 0; color: {tbl_lbl}; width: 80px;">Projekt:</td><td style="font-weight: 600;">{project_label or "—"}</td></tr>
                  <tr><td style="padding: 4px 0; color: {tbl_lbl};">Model:</td><td class="mono">{_model_filename}</td></tr>
                  <tr><td style="padding: 4px 0; color: {tbl_lbl};">Datum:</td><td>{date_str}</td></tr>
                  <tr><td style="padding: 4px 0; color: {tbl_lbl};">Ocjena:</td><td style="font-weight: 600;">{grade_num} — {grade_simple} ({score_data['percentage']}%)</td></tr>
                </table>
                """, unsafe_allow_html=True)

                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                pdf_bytes = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                        tmp_pdf_path = tmp_pdf.name
                    generate_pdf(df_res, tmp_pdf_path, cfg)
                    with open(tmp_pdf_path, "rb") as f_pdf:
                        pdf_bytes = f_pdf.read()
                except Exception as e:
                    pdf_bytes = None
                finally:
                    try: os.unlink(tmp_pdf_path)
                    except Exception: pass

                import zipfile

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    if pdf_bytes:
                        zf.writestr("revizijski_elaborat.pdf", pdf_bytes)
                    if html_code:
                        zf.writestr("revizijski_elaborat.html", html_code)
                    if not df_res.empty:
                        csv_data = df_res.to_csv(index=False).encode("utf-8")
                        zf.writestr("odstupanja_elemenata.csv", csv_data)
                    # Include markdown audit summary
                    audit_items = _cached_curriculum_audit(etabs_data, results_data)
                    audit_summary_md = (
                        f"# Evaluacija modela\n\n"
                        f"Projekt: {project_label or '—'}\n"
                        f"Ocjena: {grade_num} ({grade_simple}) — {score_data['percentage']}%\n\n---\n\n"
                    )
                    for item in audit_items:
                        audit_summary_md += f"### T{item['num']} — {item['title']} [{item['status']}]\n"
                        audit_summary_md += f"- Nalaz: {item['finding']}\n"
                        audit_summary_md += f"- Pravilo: {item['rule']}\n"
                        if item.get("recommendation"):
                            audit_summary_md += f"- Preporuka: {item['recommendation']}\n"
                        audit_summary_md += "\n"
                    zf.writestr("evaluacija_modela.md", audit_summary_md.encode("utf-8"))

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if pdf_bytes:
                        st.download_button(
                            "Preuzmi PDF elaborat",
                            data=pdf_bytes,
                            file_name="revizijski_elaborat.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="primary"
                        )
                    st.download_button(
                        "Preuzmi HTML izvještaj",
                        data=html_code,
                        file_name="revizijski_elaborat.html",
                        mime="text/html",
                        use_container_width=True
                    )
                with btn_c2:
                    st.download_button(
                        "Preuzmi cjeloviti paket (.zip)",
                        data=zip_buffer.getvalue(),
                        file_name="revizijski_paket_elaborat.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                    st.download_button(
                        "Preuzmi sažetak (.md)",
                        data=audit_summary_md,
                        file_name="evaluacija_modela.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

            with meta_col2:
                st.markdown(f"<div style='font-size: 12px; font-weight: 600; color: {tbl_lbl}; margin-bottom: 6px;'>Pretpregled izvještaja</div>", unsafe_allow_html=True)
                st.components.v1.html(html_code, height=480, scrolling=True)

            # Task 8: Expander with engineering instructions
            st.markdown("---")
            with st.expander("Inženjerske upute za pripremu modela i nacrta", expanded=False):
                render_instructions()

if __name__ == "__main__":
    main()
