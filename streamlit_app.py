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

from ui_styles import (
    inject_app_css,
    render_header_bar,
    render_landing_screen,
    render_header_card,
    render_kpi_strip,
    render_audit_hero,
)
from ui_views import render_drawing, fig_2d, fig_3d, safe_df, render_instructions

# Backward compatibility aliases
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
# Performance Caching (Fast 0ms Tab Switching)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_parse_e2k(e2k_content: str, _cfg: Config):
    return parse_e2k(io.StringIO(e2k_content), _cfg)

@st.cache_data(show_spinner=False)
def _cached_parse_dxf_bytes(dxf_bytes: bytes, _cfg: Config):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    try:
        tmp.write(dxf_bytes)
        tmp.close()
        return parse_dxf(tmp.name, _cfg)
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass

@st.cache_data(show_spinner=False)
def _cached_validate(_etabs_data: dict, _df_dxf: pd.DataFrame, _cfg: Config):
    return validate(_etabs_data, _df_dxf, _cfg)

@st.cache_data(show_spinner=False)
def _cached_curriculum_audit(_etabs_data: dict, _results_data: dict = None):
    return run_curriculum_audit(_etabs_data, _results_data)

# ─────────────────────────────────────────────────────────────
# Sidebar: Minimal, Focused Engineering Controls
# ─────────────────────────────────────────────────────────────
def _sidebar() -> tuple:
    with st.sidebar:
        st.markdown("### ETABS model")
        if "use_demo" not in st.session_state:
            st.session_state["use_demo"] = False

        uploaded_e2k = None
        e2k_loaded_name = st.session_state.get("active_e2k_name")

        if not st.session_state["use_demo"] and not e2k_loaded_name:
            uploaded_e2k = st.file_uploader("Učitaj .e2k datoteku", type=["e2k", "$et", "txt"], key="sb_e2k_up", label_visibility="collapsed")
        elif st.session_state["use_demo"]:
            demo_name = st.session_state.get("demo_choice_key", "strossmayer")
            display_map = {
                "strossmayer": "STROSSMAYER_2.e2k",
                "commercial": "demo_commercial.e2k",
                "small": "sample_building.e2k",
                "trnsko": "trnsko_model.e2k",
            }
            cur_label = display_map.get(demo_name, "STROSSMAYER_2.e2k")
            st.markdown(f"<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ {cur_label}</div>", unsafe_allow_html=True)
            demo_desc_map = {
                "strossmayer": "1436 zidova · 4 etaže (OŠ Strossmayer)",
                "commercial": "304 stupa · 554 grede (2 etaže)",
                "small": "4 stupa · 1 greda · 1 zid",
                "trnsko": "238 stupova · 384 grede · 140 ploča",
            }
            st.caption(demo_desc_map.get(demo_name, ""))
        elif e2k_loaded_name:
            st.markdown(f"<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ {e2k_loaded_name}</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("### Nacrt (CAD / PDF)")
        uploaded_drawing_file = None
        drawing_loaded_name = st.session_state.get("active_drawing_name")

        if not st.session_state["use_demo"] and not drawing_loaded_name:
            uploaded_drawing_file = st.file_uploader("Učitaj .dxf ili .pdf nacrt", type=["pdf", "dxf", "jpg", "png"], key="sb_drawing_up", label_visibility="collapsed")
        elif st.session_state["use_demo"]:
            demo_name = st.session_state.get("demo_choice_key", "strossmayer")
            if demo_name == "strossmayer":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ OS_VARSAVSKA.pdf</div>", unsafe_allow_html=True)
                st.caption("20 stranica (Tehnički opis + nacrti)")
            elif demo_name == "commercial":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ commercial.dxf</div>", unsafe_allow_html=True)
                st.caption("CAD tlocrt stupova")
            elif demo_name == "small":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ sample.dxf</div>", unsafe_allow_html=True)
                st.caption("CAD tlocrt")
            elif demo_name == "trnsko":
                st.markdown("<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ trnsko.pdf</div>", unsafe_allow_html=True)
                st.caption("14 stranica nacrta")
        elif drawing_loaded_name:
            st.markdown(f"<div class='mono' style='font-size:12px; color:#16A34A; font-weight:600;'>✓ {drawing_loaded_name}</div>", unsafe_allow_html=True)

        st.markdown("---")

        # Tolerances
        st.markdown("### Tolerancije")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tol_pos_val = st.selectbox("Pozicija (m)", ["0.05", "0.10", "0.15", "0.20", "0.30"], index=2, key="sb_tol_pos")
            tol_frame = float(tol_pos_val)
            tol_area = max(tol_frame * 2.0, 0.30)
        with col_t2:
            tol_sec_val = st.selectbox("Presjek (mm)", ["1", "2", "5", "10", "20"], index=2, key="sb_tol_sec")
            tol_sec = float(tol_sec_val)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Element extraction
        st.markdown("### Kontrola elemenata")
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

        cfg = Config(
            dxf_unit_scale=0.01,
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
        if st.session_state.get("use_demo") or e2k_loaded_name:
            if st.button("Učitaj drugi projekt / Reset", use_container_width=True, key="btn_reset_session"):
                st.session_state["use_demo"] = False
                st.session_state["active_e2k_name"] = None
                st.session_state["active_drawing_name"] = None
                st.session_state["demo_choice_key"] = "strossmayer"
                st.rerun()

    return uploaded_e2k, uploaded_drawing_file, cfg

# ─────────────────────────────────────────────────────────────
# Main Application Flow
# ─────────────────────────────────────────────────────────────
def main():
    uploaded_e2k, uploaded_drawing_file, cfg = _sidebar()

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
        elif demo_choice == "trnsko":
            e2k_target = os.path.join(SCRIPT_DIR, "trnsko_model.e2k")
            if os.path.exists(e2k_target):
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                is_pdf_mode = True
                has_data = True
                trnsko_pdf = os.path.join(SCRIPT_DIR, ".user_uploaded", "media_1788429757620.pdf")
                if os.path.exists(trnsko_pdf):
                    uploaded_drawing = trnsko_pdf
                project_label = "OŠ Trnsko"

    elif uploaded_e2k:
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        project_label = uploaded_e2k.name
        st.session_state["active_e2k_name"] = uploaded_e2k.name
        if uploaded_drawing_file:
            st.session_state["active_drawing_name"] = uploaded_drawing_file.name
            fname_l = uploaded_drawing_file.name.lower()
            if fname_l.endswith(".dxf"):
                dxf_bytes = uploaded_drawing_file.getvalue()
                is_pdf_mode = False
            else:
                uploaded_drawing = uploaded_drawing_file
                is_pdf_mode = True
        else:
            is_pdf_mode = True
        has_data = True

    # ── Top App Header Bar ────────────────────────────────────
    render_header_bar(project_name=project_label, version="v2.1.0")

    # ── Landing State: Minimalist clean screen ────────────────
    if not has_data:
        render_landing_screen()
        c_l1, c_l2 = st.columns(2, gap="medium")
        with c_l1:
            st.markdown("<div style='text-align: center; margin-bottom: 8px; font-weight:600; color:#374151;'>Ogledni primjeri</div>", unsafe_allow_html=True)
            if st.button("Otvori OŠ Strossmayer (Zidana zgrada + PDF)", use_container_width=True, type="primary"):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "strossmayer"
                st.rerun()
            if st.button("Otvori Poslovni centar (AB okvir + CAD DXF)", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "commercial"
                st.rerun()
            if st.button("Otvori OŠ Trnsko (Okvir sa zglobovima)", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "trnsko"
                st.rerun()
        with c_l2:
            st.markdown("<div style='text-align: center; margin-bottom: 8px; font-weight:600; color:#374151;'>Vlastiti model</div>", unsafe_allow_html=True)
            st.caption("U lijevom izborniku priložite .e2k datoteku iz ETABS-a (File → Export → ETABS .e2k Text File...) i pripadajući arhitektonski nacrt (.dxf ili .pdf).")
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

            # Optional Phase 2 results
            results_data = None
            if use_demo:
                try:
                    results_data = parse_etabs_results(create_demo_etabs_results(etabs_data))
                except Exception:
                    results_data = None
            df_res.attrs["results_data"] = results_data

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

    # ── TAB 1: Model ──────────────────────────────────────────
    with t_model:
        story_names = [s.get("display_name", s["name"]) for s in stories]
        story_opts = story_names + ["Sve etaže"]

        tb_col1, tb_col2 = st.columns([3.5, 1.5])
        with tb_col1:
            sel_story = st.segmented_control(
                "Odabir etaže:",
                options=story_opts,
                default=story_names[0] if story_names else "Sve etaže",
                key="tab1_story_pills",
                label_visibility="collapsed"
            ) or story_opts[0]

        with tb_col2:
            is_3d_active = st.toggle("3D prikaz modela", value=False, key="t1_3d_toggle")

        if sel_story != "Sve etaže":
            curr_idx = story_names.index(sel_story)
            selected_story_data = stories[curr_idx]
            active_story_name = selected_story_data["name"]
            chosen_z = selected_story_data["z_top"]

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
            active_story_name = None
            selected_story_data = None
            chosen_z = None
            df_eval = df_res.copy()
            df_eval.attrs = dict(df_res.attrs)

        # Layout: Split View (ETABS on Left, Drawing on Right)
        has_drawing = (uploaded_drawing is not None)
        if has_drawing and not is_3d_active:
            col_m, col_d = st.columns(2, gap="medium")
            with col_m:
                st.markdown("<div style='font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 6px;'>Numerički model (ETABS)</div>", unsafe_allow_html=True)
                st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)
            with col_d:
                render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name, demo_sheet_map=demo_sheet_map)
        elif is_3d_active:
            st.plotly_chart(fig_3d(df_res, etabs_data, active_story_name=active_story_name, etabs_color_mode=True), use_container_width=True)
        else:
            st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)

    # ── TAB 2: Revizija (Triage Code-Review) ───────────────────
    with t_audit:
        results_data = df_res.attrs.get("results_data")
        audit_results = _cached_curriculum_audit(etabs_data, results_data)
        score_data = calculate_audit_score(audit_results)

        # Summary Bar
        grade_num = score_data.get("grade", 1)
        grade_simple = {5: "Izvrstan", 4: "Vrlo dobar", 3: "Dobar", 2: "Dovoljan", 1: "Nedovoljan"}.get(grade_num, "Dobar")
        pct_num = score_data.get("percentage", 0.0)

        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #E5E7EB; padding-bottom: 10px; margin-bottom: 16px;">
          <div>
            <span style="font-size: 16px; font-weight: 600; color: #111827;">Ocjena: {grade_num} — {grade_simple}</span>
            <span style="color: #6B7280; font-size: 13px; margin-left: 12px;">{pct_num} / 100 bodova</span>
          </div>
          <div class="mono" style="color: #6B7280; font-size: 12px;">
            {len(audit_results)} točaka provjereno
          </div>
        </div>
        """, unsafe_allow_html=True)

        attention_items = [a for a in audit_results if a.get("status") in ("FAIL", "WARNING")]
        pass_items = [a for a in audit_results if a.get("status") == "PASS"]
        info_items = [a for a in audit_results if a.get("status") == "INFO"]

        # Triage 1: Zahtijeva pažnju (Always expanded at top!)
        if attention_items:
            st.markdown(f"<div style='font-size: 14px; font-weight: 600; color: #111827; margin: 12px 0 8px 0;'>Zahtijeva pažnju ({len(attention_items)})</div>", unsafe_allow_html=True)
            for item in attention_items:
                is_fail = (item.get("status") == "FAIL")
                icon = "✗" if is_fail else "⚠"
                css_cls = "triage-fail" if is_fail else "triage-warn"
                icon_color = "#DC2626" if is_fail else "#D97706"

                rec_txt = item.get("recommendation", "")
                st.markdown(f"""
                <div class="triage-item {css_cls}">
                  <div class="triage-title">
                    <span style="color: {icon_color}; font-weight: 700;">{icon} &nbsp; T{item['num']} · {item['title']}</span>
                    <span class="mono" style="font-size: 11px; font-weight: normal; color: #6B7280;">Težina: {item.get('weight', 5)}</span>
                  </div>
                  <div class="triage-finding">{item.get('finding', '')}</div>
                  {f'<div class="triage-action"><span class="triage-action-arrow">→ </span>{rec_txt}</div>' if rec_txt else ''}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #16A34A; font-weight: 600; margin: 12px 0;'>✓ Nema uočenih grešaka ni upozorenja u modelu.</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Triage 2: Zadovoljava (Collapsed)
        with st.expander(f"Zadovoljava ({len(pass_items)})", expanded=False):
            for item in pass_items:
                st.markdown(f"""
                <div style="padding: 4px 0; font-size: 13px; color: #374151; border-bottom: 1px solid #F3F4F6;">
                  <span style="color: #16A34A; font-weight: 700;">✓</span> &nbsp;
                  <strong>T{item['num']} · {item['title']}</strong>:
                  <span style="color: #4B5563;">{item.get('finding', '')}</span>
                </div>
                """, unsafe_allow_html=True)

        # Triage 3: Info / ne primjenjuje se (Collapsed)
        with st.expander(f"Info / ne primjenjuje se ({len(info_items)})", expanded=False):
            for item in info_items:
                st.markdown(f"""
                <div style="padding: 4px 0; font-size: 13px; color: #4B5563; border-bottom: 1px solid #F3F4F6;">
                  <span style="color: #6B7280;">○</span> &nbsp;
                  <strong>T{item['num']} · {item['title']}</strong>:
                  <span style="color: #6B7280;">{item.get('finding', '')}</span>
                </div>
                """, unsafe_allow_html=True)

    # ── TAB 3: Elementi ───────────────────────────────────────
    with t_elements:
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

        col_f1, col_f2 = st.columns([3.5, 1.5])
        with col_f1:
            sel_pill = st.segmented_control(
                "Status elementa:",
                options=pill_opts,
                default="Svi",
                key="elem_status_pills",
                label_visibility="collapsed"
            ) or "Svi"
        with col_f2:
            search_txt = st.text_input("Pretraga", placeholder="Naziv, presjek...", label_visibility="collapsed", key="tb_srch")

        dfd = df_res.copy()
        if "Usklađeno" in sel_pill:
            dfd = dfd[dfd["status"] == Status.MATCH]
        elif "Odstupanje" in sel_pill:
            dfd = dfd[dfd["status"] == Status.SECTION_MISMATCH]
        elif "Samo ETABS" in sel_pill:
            dfd = dfd[dfd["status"] == Status.ETABS_ONLY]
        elif "Samo nacrt" in sel_pill:
            dfd = dfd[dfd["status"] == Status.DXF_ONLY]

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
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    # ── TAB 4: Izvještaj ──────────────────────────────────────
    with t_report:
        st.markdown("<div style='font-size: 15px; font-weight: 600; color: #111827; margin-bottom: 12px;'>Revizijski elaborat</div>", unsafe_allow_html=True)

        date_str = datetime.now().strftime("%d.%m.%Y.")
        score_data = calculate_audit_score(_cached_curriculum_audit(etabs_data, df_res.attrs.get("results_data")))
        grade_num = score_data.get("grade", 1)
        grade_simple = {5: "Izvrstan", 4: "Vrlo dobar", 3: "Dobar", 2: "Dovoljan", 1: "Nedovoljan"}.get(grade_num, "Dobar")

        meta_col1, meta_col2 = st.columns([2, 3])
        with meta_col1:
            st.markdown(f"""
            <table style="width: 100%; font-size: 13px; color: #374151; border-collapse: collapse;">
              <tr><td style="padding: 4px 0; color: #6B7280; width: 80px;">Projekt:</td><td style="font-weight: 600;">{project_label or "—"}</td></tr>
              <tr><td style="padding: 4px 0; color: #6B7280;">Model:</td><td class="mono">{os.path.basename(DEMO_SKOLA_E2K) if use_demo else (project_label or "model.e2k")}</td></tr>
              <tr><td style="padding: 4px 0; color: #6B7280;">Datum:</td><td>{date_str}</td></tr>
              <tr><td style="padding: 4px 0; color: #6B7280;">Ocjena:</td><td style="font-weight: 600;">{grade_num} — {grade_simple} ({score_data['percentage']}%)</td></tr>
            </table>
            """, unsafe_allow_html=True)

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name

            try:
                generate_pdf(df_res, tmp_pdf_path, cfg)
                with open(tmp_pdf_path, "rb") as f_pdf:
                    pdf_bytes = f_pdf.read()
            except Exception as e:
                pdf_bytes = None
            finally:
                try: os.unlink(tmp_pdf_path)
                except Exception: pass

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
            with btn_c2:
                html_code = generate_html(df_res, None, cfg)
                st.download_button(
                    "Preuzmi HTML",
                    data=html_code,
                    file_name="revizijski_elaborat.html",
                    mime="text/html",
                    use_container_width=True
                )

        with meta_col2:
            st.markdown("<div style='font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 6px;'>Pretpregled izvještaja</div>", unsafe_allow_html=True)
            html_code = generate_html(df_res, None, cfg)
            st.components.v1.html(html_code, height=480, scrolling=True)

if __name__ == "__main__":
    main()
