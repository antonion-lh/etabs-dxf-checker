"""
streamlit_app.py — ETABS ↔ CAD/PDF Automated Structural QA Platform
Enterprise engineering tool with crystal-clear navigation, high contrast,
full CAD/PDF/image drawing support, multi-story filtering, and zero visual clutter.
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

from ui_styles import inject_app_css, render_header_card, render_kpi_strip, render_audit_hero
from ui_views import render_drawing, fig_2d, fig_3d, safe_df, render_instructions

# Backward compatibility aliases
_kpi_strip = render_kpi_strip
_fig_2d = fig_2d
_fig_3d = fig_3d
_safe_df = safe_df
_render_instructions = render_instructions
_render_drawing = render_drawing

# ─────────────────────────────────────────────────────────────
# Page setup & CSS injection
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ETABS ↔ CAD · Kontrola Numeričkih Modela",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_app_css()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_SKOLA_DXF = os.path.join(SCRIPT_DIR, "demo_skola.dxf")
DEMO_SKOLA_E2K = os.path.join(SCRIPT_DIR, "STROSSMAYER_2.e2k") if os.path.exists(os.path.join(SCRIPT_DIR, "STROSSMAYER_2.e2k")) else os.path.join(SCRIPT_DIR, "demo_skola.e2k")
DEMO_SKOLA_PDF = os.path.join(SCRIPT_DIR, "OS_VARSAVSKA_arh_proj_dijelovi.pdf") if os.path.exists(os.path.join(SCRIPT_DIR, "OS_VARSAVSKA_arh_proj_dijelovi.pdf")) else os.path.join(SCRIPT_DIR, "demo_projekt_skola.pdf")

DEMO_COMMERCIAL_DXF = os.path.join(SCRIPT_DIR, "demo_commercial_building.dxf")
DEMO_COMMERCIAL_E2K = os.path.join(SCRIPT_DIR, "demo_commercial_building.e2k")
SMALL_SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SMALL_SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

STROSSMAYER_SHEET_MAP = {
    1: "📄 Str. 1: Tehnički opis - Općenito i opseg radova",
    2: "📄 Str. 2: Situacija i građevinska parcela",
    3: "📄 Str. 3: Funkcija i organizacija prostora",
    4: "📄 Str. 4: Konstruktivno ojačanje stubišta (NPI 200)",
    5: "📄 Str. 5: Konstrukcija, materijali i seizmika (VIII MCS)",
    8: "📄 Str. 8: Iskaz neto površina po etažama",
    10: "📄 Str. 10: Iskaz BRP građevine",
    11: "📄 Str. 11: Slojevi podova, stropova i zidova",
    14: "📐 Str. 14: Tlocrt PRIZEMLJA",
    15: "📐 Str. 15: Tlocrt I. KATA",
    16: "📐 Str. 16: Tlocrt II. KATA",
    17: "📐 Str. 17: Plan KROVIŠTA (Drvena krovna konstrukcija)",
    18: "📐 Str. 18: Tlocrt KROVA",
    19: "📐 Str. 19: Presjeci 1-1 i 2-2 & Južno pročelje",
    20: "📐 Str. 20: Sjeverno, Istočno i Zapadno pročelje",
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
            help="Uključite za instantni pregled s gotovim ETABS modelom i nacrtom zgrade.",
        )
        st.session_state["use_demo"] = use_demo

        demo_model_choice = "strossmayer"
        if use_demo:
            default_idx = 0
            if st.session_state.get("demo_choice_key") == "commercial":
                default_idx = 1
            elif st.session_state.get("demo_choice_key") == "small":
                default_idx = 2
            elif st.session_state.get("demo_choice_key") == "trnsko":
                default_idx = 3

            choice_label = st.selectbox(
                "Odaberite demo model:",
                [
                    "🏫 OŠ J. J. Strossmayer (Zidana zgrada — Cjeloviti PDF elaborat i numerički model)",
                    "🏢 Poslovni centar (AB okvir — CAD DXF tlocrt + ETABS model)",
                    "📐 Edukativni referentni model (CAD + ETABS usklađeno)",
                    "🎓 OŠ Trnsko (AB skeletni okvir — 238 stupova, 384 grede, plastični zglobovi)",
                ],
                index=default_idx,
                key="demo_model_selector"
            )
            if "Strossmayer" in choice_label:
                demo_model_choice = "strossmayer"
            elif "Poslovni" in choice_label:
                demo_model_choice = "commercial"
            elif "Edukativni" in choice_label:
                demo_model_choice = "small"
            else:
                demo_model_choice = "trnsko"
            st.session_state["demo_choice_key"] = demo_model_choice

        uploaded_dxf = uploaded_pdf_doc = uploaded_e2k = uploaded_results = None
        if not use_demo:
            doc_type = st.radio(
                "Vrsta izvedbenog nacrta / dokumentacije:",
                ["📑 PDF projektni elaborat / nacrti (.pdf)", "📐 CAD vektorski nacrt (.dxf)"],
                index=0,
                key="doc_type_choice",
                help="Odaberite PDF ako imate projektni elaborat ili nacrte u PDF-u (npr. tehnički opis i tlocrti), ili DXF ako imate CAD datoteku."
            )

            if doc_type.startswith("📑"):
                uploaded_pdf_doc = st.file_uploader(
                    "Projektni elaborat / nacrti (.pdf):",
                    type=["pdf"],
                    help="Učitajte PDF dokument koji sadrži tehnički opis i/ili tlocrte etaža.",
                )
            else:
                uploaded_dxf = st.file_uploader(
                    "CAD nacrt (.dxf):",
                    type=["dxf"],
                    help="Izvedbeni tlocrt konstrukcije iz AutoCAD-a (.dxf).",
                )

            uploaded_e2k = st.file_uploader(
                "ETABS model (.e2k, .$et):",
                type=["e2k", "$et", "txt"],
                help="Tekstualni izvoz iz ETABS-a: File → Export → ETABS .e2k Text File...\n(Napomena: .edb je binarna baza podataka koju ETABS zaključava i ne može se čitati na webu bez instaliranog ETABS-a).",
            )
            st.caption("ℹ️ *Izvoz iz ETABS-a: File → Export → .e2k*")

            st.markdown("---")
            st.markdown("#### 📊 Rezultati proračuna (Faza 2 — opcija)")
            uploaded_results = st.file_uploader(
                "ETABS tablice rezultata (.xlsx, .xls, .csv):",
                type=["xlsx", "xls", "csv"],
                help="Opcionalno: Izvoz iz ETABS-a (Display → Show Tables → Export Tables to Excel) za analizu katnih pomaka (drifts), poprečnih sila, pritisaka na tlo i armature.",
                key="uploaded_results_file"
            )
            st.caption("ℹ️ *Display → Show Tables → Export to Excel (opcionalno)*")
        else:
            uploaded_results = None
            st.markdown("---")
            st.markdown("#### 📊 Rezultati proračuna (Faza 2)")
            demo_include_results = st.checkbox(
                "Uključi ogledne rezultate proračuna (Faza 2)",
                value=True,
                key="demo_include_results_chk",
                help="Automatski generira i analizira proračunske tablice (Story Drifts, Story Forces, Reakcije tla) za demonstraciju Faze 2."
            )

        uploaded_drawing = uploaded_pdf_doc
        if not use_demo and doc_type.startswith("📐"):
            st.markdown("---")
            st.markdown("#### 📑 2. Referentni nacrt (opcija)")
            uploaded_drawing = st.file_uploader(
                "Priložite PDF ili sliku uz CAD nacrt:",
                type=["pdf", "jpg", "jpeg", "png", "tif", "tiff"],
                help="Projektantski nacrt u PDF-u ili JPG/PNG formatu za usporedni pregled.",
            )

        st.markdown("---")

        # 3. Mjerne jedinice i tolerancije
        st.markdown("#### 📐 3. Jedinice i tolerancije")
        unit_scale = 0.01  # default cm

        is_dxf_selected = (not use_demo and doc_type.startswith("📐")) or (use_demo and demo_model_choice in ("commercial", "small"))
        if is_dxf_selected:
            scale_label = st.selectbox(
                "Jedinica u CAD crtežu (.dxf):",
                ["Centimetri (cm)", "Milimetri (mm)", "Metri (m)"],
                index=0,
                help="AutoCAD DXF datoteke spremaju koordinate bez fizičke jedinice. Odaberite jedinicu CAD crteža kako bi se točno preveo u metre.\n\nNapomena: Jedinice ETABS modela očitavaju se iz samog .e2k zaglavlja!",
            )
            scale_map = {"Centimetri (cm)": 0.01, "Milimetri (mm)": 0.001, "Metri (m)": 1.0}
            unit_scale = scale_map[scale_label]
            st.caption("ℹ️ *Jedinice ETABS modela sustav sam očitava iz .e2k zaglavlja.*")
        else:
            st.info("ℹ️ **Jedinice ETABS modela** automatski se očitavaju iz samog .e2k zaglavlja (npr. KN, m, °C).\n\nNa PDF nacrtima kote tlocrta su standardno u **cm**, a visinske kote u **m**.")

        with st.expander("⚙️ Prilagodba inženjerskih tolerancija"):
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

        with st.expander("❓ Brzi podsjetnik za rad"):
            st.markdown("""
            **1. Izvoz modela iz ETABS-a:**  
            →:       cannot open `→' (No such file or directory)
Export:  cannot open `Export' (No such file or directory)
→:       cannot open `→' (No such file or directory)
.e2k:    cannot open `.e2k' (No such file or directory)
Text:    cannot open `Text' (No such file or directory)
File...: cannot open `File...' (No such file or directory)
            
            **2. Mjerne jedinice:**  
            Uskladite jedinicu CAD crteža (cm, mm ili m).
            
            **3. Višeetažne zgrade:**  
            Odaberite etažu koja odgovara CAD tlocrtu.
            
            **4. Tumač boja:**  
            🟢 Usklađeno  
            🟡 Razlika u dimenziji  
            🔴 Nema u CAD-u  
            🔵 Nema u ETABS-u  
            """)

        st.markdown("---")
        st.caption("Inženjerska kontrola · Eurocode HRN EN 1992/1993")

    return use_demo, demo_model_choice, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg, uploaded_results
def main():
    use_demo, demo_model_choice, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg, uploaded_results = _sidebar()

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
    has_data = False
    is_pdf_mode = False
    dxf_path = None
    e2k_content = None

    demo_sheet_map = None
    dxf_bytes = None

    if use_demo:
        if demo_model_choice == "strossmayer":
            e2k_target = DEMO_SKOLA_E2K
            if os.path.exists(e2k_target):
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                uploaded_drawing = DEMO_SKOLA_PDF
                is_pdf_mode = True
                has_data = True
                demo_sheet_map = STROSSMAYER_SHEET_MAP
        elif demo_model_choice == "commercial":
            dxf_target = DEMO_COMMERCIAL_DXF
            e2k_target = DEMO_COMMERCIAL_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                with open(dxf_target, "rb") as f:
                    dxf_bytes = f.read()
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True
                is_pdf_mode = False
        elif demo_model_choice == "small":
            dxf_target = SMALL_SAMPLE_DXF
            e2k_target = SMALL_SAMPLE_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                with open(dxf_target, "rb") as f:
                    dxf_bytes = f.read()
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True
                is_pdf_mode = False
        elif demo_model_choice == "trnsko":
            e2k_target = os.path.join(SCRIPT_DIR, "trnsko_model.e2k")
            if os.path.exists(e2k_target):
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                is_pdf_mode = True
                has_data = True
                trnsko_pdf = os.path.join(SCRIPT_DIR, ".user_uploaded", "media_1788429757620.pdf")
                if os.path.exists(trnsko_pdf):
                    uploaded_drawing = trnsko_pdf

        if not has_data:
            st.error("Ogledne datoteke nisu pronađene na poslužitelju.")
    elif uploaded_e2k:
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        if uploaded_dxf:
            dxf_bytes = uploaded_dxf.getvalue()
            has_data = True
            is_pdf_mode = False
        elif uploaded_drawing:
            has_data = True
            is_pdf_mode = True

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

        # Big 1-click Demo Actions
        c_demo1, c_demo2 = st.columns(2)
        with c_demo1:
            if st.button("🏫 Isprobaj s modelom škole i PDF elaboratom (1 klik)", type="primary", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "strossmayer"
                st.rerun()
            st.caption("Učitava zgradu škole OŠ J. J. Strossmayer s 20-straničnim PDF elaboratom (Tehnički opis + glavni nacrti).")

        with c_demo2:
            if st.button("🏢 Isprobaj s modelom poslovne zgrade (18×7 raspona)", use_container_width=True):
                st.session_state["use_demo"] = True
                st.session_state["demo_choice_key"] = "commercial"
                st.rerun()
            st.caption("Učitava složeni model zgrade s 18×7 polja i 2 etaže (860 elemenata) prema ETABS 3D prikazu.")

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
              <div class="step-title">Učitavanje nacrta (PDF ili CAD)</div>
              <div class="step-desc">
                U lijevom izborniku priložite <b>.e2k</b> model te projektni <b>PDF elaborat</b> (ili CAD .dxf nacrt).
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

        st.write("")
        with st.expander("📖 Otvori detaljne inženjerske upute za pripremu modela i nacrta", expanded=False):
            render_instructions()
        return

    # ── Run Analysis ─────────────────────────────────────────
    with st.spinner("Automatska obrada modela i projektne dokumentacije u tijeku…"):
        try:
            etabs_data = _cached_parse_e2k(e2k_content, cfg)
            if is_pdf_mode or dxf_path is None:
                # PDF Mode: extract structural elements directly from ETABS model
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
                                "dxf_dim_text": "Provjeriti na PDF-u",
                                "dxf_dim1_mm": None,
                                "dxf_dim2_mm": None,
                                "xy_dist_m": None,
                                "notes": "Vizualno provjeriti s tlocrtom u PDF elaboratu",
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

            # Phase 2: Optional ETABS analysis results parsing
            results_data = None
            if not use_demo and uploaded_results is not None:
                try:
                    results_data = parse_etabs_results(uploaded_results.getvalue())
                except Exception as ex:
                    st.warning(f"Upozorenje pri čitanju tablica rezultata: {ex}")
            elif use_demo and st.session_state.get("demo_include_results_chk", True):
                try:
                    results_data = parse_etabs_results(create_demo_etabs_results(etabs_data))
                except Exception:
                    results_data = None

            df_res.attrs["results_data"] = results_data
        except Exception as err:
            st.error(f"Greška tijekom obrade modela: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except: pass

    # ── Stories Configuration ─────────────────────────────────
    stories = etabs_data.get("stories", [])
    if not stories:
        stories = [{"name": "Prizemlje", "display_name": "Prizemlje", "z_bottom": 0.0, "z_top": 4.0, "height": 4.0, "elevation": 4.0}]

    # ── KPI Strip (Globalni pregled modela zgrade) ─────────────
    render_kpi_strip(df_res, is_pdf_mode=is_pdf_mode, etabs_data=etabs_data)

    # ── Inženjerska kontrola modela (prikazuje se samo kod stvarnih grešaka) ──
    alerts = df_res.attrs.get("sanity_alerts", [])
    if alerts:
        err_alerts = [a for a in alerts if a.get("severity") == "ERROR"]
        if err_alerts:
            with st.expander(f"⚠️ Kritična odstupanja numeričkog modela ({len(err_alerts)})", expanded=False):
                for a in err_alerts:
                    st.markdown(f"🔴 **[{a.get('category','')}] {a.get('element','')}**: {a.get('issue','')}")

    # ── Tab Navigation: 4 Clean, Focused Sections ─────────────
    t_map, t_audit, t_elements, t_report = st.tabs([
        "📐 Model i Nacrt",
        "🎓 Inženjerska revizija (1–51)",
        "📋 Elementi i svojstva",
        "📑 Službeni izvještaj",
    ])

    # ── TAB 1: Visual Model & Reference Drawing ───────────────
    with t_map:
        stories = etabs_data.get("stories", [])
        if not stories:
            stories = [{"name": "Prizemlje", "display_name": "Prizemlje", "z_bottom": 0.0, "z_top": 4.0, "height": 4.0}]

        tab1_story_opts = [s.get("display_name", s["name"]) for s in stories] + ["🌐 Sve etaže"]

        # Default to first occupied floor (Story1 / Prizemlje), not Sve etaže
        def_idx = 0
        if len(stories) > 0:
            for i, s in enumerate(stories):
                sn = s.get("name", "").lower()
                sd = s.get("display_name", "").lower()
                if "base" not in sn and "podno" not in sd:
                    def_idx = i
                    break

        has_drawing = uploaded_drawing is not None
        view_opts = ["📐 2D Tlocrt", "🏢 3D Model"]
        if has_drawing:
            view_opts.extend(["📑 Usporedno s nacrtom", "📄 Samo nacrt"])

        # Modern Compact Unified Toolbar
        tb_col1, tb_col2 = st.columns([3.2, 2.0], gap="medium")
        with tb_col1:
            sel_view = st.segmented_control(
                "Prikaz modela:",
                options=view_opts,
                default="📐 2D Tlocrt",
                key="toolbar_view_mode",
                label_visibility="collapsed",
            ) or "📐 2D Tlocrt"

        with tb_col2:
            s_col1, s_col2 = st.columns([1.6, 1.2], gap="small")
            with s_col1:
                sel_story = st.selectbox(
                    "Odabir etaže:",
                    options=tab1_story_opts,
                    index=def_idx,
                    key="toolbar_story_sel",
                    label_visibility="collapsed",
                )
            with s_col2:
                if not sel_story.startswith("🌐"):
                    curr_idx = tab1_story_opts.index(sel_story)
                    s_info = stories[curr_idx]
                    st.markdown(f"<div class='story-badge'>Z={s_info['z_bottom']:.1f}–{s_info['z_top']:.1f}m</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='story-badge'>Cijela zgrada</div>", unsafe_allow_html=True)

        if not sel_story.startswith("🌐"):
            curr_idx = tab1_story_opts.index(sel_story)
            selected_story_data = stories[curr_idx]
            active_story_name = selected_story_data["name"]
            chosen_z = selected_story_data["z_top"]
            disp_story_title = selected_story_data.get("display_name", active_story_name)

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
            disp_story_title = "Sve etaže"
            selected_story_data = None
            chosen_z = None
            df_eval = df_res.copy()
            df_eval.attrs = dict(df_res.attrs)

        # Viewport Rendering based on Toolbar Selection
        if sel_view == "📐 2D Tlocrt":
            st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)
        elif sel_view == "🏢 3D Model":
            st.plotly_chart(fig_3d(df_res, etabs_data, active_story_name=active_story_name, etabs_color_mode=True), use_container_width=True)
        elif sel_view == "📑 Usporedno s nacrtom":
            col_m, col_d = st.columns(2, gap="medium")
            with col_m:
                st.plotly_chart(fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)
            with col_d:
                render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name, demo_sheet_map=demo_sheet_map)
        elif sel_view == "📄 Samo nacrt":
            render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name, demo_sheet_map=demo_sheet_map)

    # ── TAB 2: Studentska & Nastavna revizijska lista ───────────
    with t_audit:
        results_data = df_res.attrs.get("results_data")
        audit_results = _cached_curriculum_audit(etabs_data, results_data)
        score_data = calculate_audit_score(audit_results)

        # Quick KPI extractions from Phase 1 audit checks
        c31 = next((a for a in audit_results if a["num"] == 31), None)
        c30 = next((a for a in audit_results if a["num"] == 30), None)
        c34 = next((a for a in audit_results if a["num"] == 34), None)
        c51 = next((a for a in audit_results if a["num"] == 51), None)

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

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("🟢 Usklađene točke", f"{score_data['n_pass']} / {len(audit_results)}")
        c_m2.metric("🟡 Upozorenja", score_data["n_warn"])
        c_m3.metric("🔴 Kritična odstupanja", score_data["n_fail"])
        c_m4.metric("ℹ️ Smjernice", score_data["n_info"])

        # Quick Engineering Cards for Phase 1 analytical checks
        if c31 or c30 or c34 or c51:
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0;">
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">📐 Površina zidova (Točka 31)</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 4px;">{c31['finding'][:55] if c31 else '—'}...</div>
                <div style="font-size: 0.75rem; color: #16a34a; font-weight: 600; margin-top: 2px;">Ciljano 3.0–4.0% tlocrta</div>
              </div>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">⚖️ Masa 'na ruke' (Točka 30)</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 4px;">{c30['finding'][:55] if c30 else '—'}...</div>
                <div style="font-size: 0.75rem; color: #0284c7; font-weight: 600; margin-top: 2px;">Inženjerska procjena W_est</div>
              </div>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">🛡️ Prevrtanje zgrade (Točka 34)</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 4px;">{c34['finding'][:55] if c34 else '—'}...</div>
                <div style="font-size: 0.75rem; color: #16a34a; font-weight: 600; margin-top: 2px;">Faktor sigurnosti SF ≥ 1.50</div>
              </div>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">🌀 Torzija & Simetrija (Točka 51)</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 4px;">{c51['finding'][:55] if c51 else '—'}...</div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 2px;">Ekscentričnost krutosti ex, ey</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # Phase 2: Optional ETABS Results Dashboard
        if results_data and results_data.get("has_results"):
            if df_res.attrs.get("is_demo_results"):
                st.info("ℹ️ **Simulirani proračunski rezultati (Demo):** Prikazani dijagrami katnih pomaka i poprečnih sila generirani su za demonstraciju Faze 2. Za stvarni proračun zgrade učitajte tablice iz ETABS-a u bočnoj traci.")
            res_sum = results_data.get("summary", {})
            st.markdown("""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin: 16px 0 12px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                  <div style="font-size: 0.72rem; text-transform: uppercase; color: #0284c7; font-weight: 700; letter-spacing: 0.06em;">Faza 2 · Analiza rezultata proračuna</div>
                  <div style="font-size: 1.2rem; font-weight: 800; color: #0f172a;">📊 Katni pomaci, poprečne potresne sile i pritisak na tlo</div>
                </div>
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 5px 12px; border-radius: 6px; font-size: 0.82rem; color: #1d4ed8; font-weight: 600;">
                  ✅ Tablice obrađene
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            rc1, rc2, rc3, rc4 = st.columns(4)
            d_val = res_sum.get("max_drift_overall", 0.0)
            rc1.metric("Maks. katni pomak (dr)", f"{d_val:.4f}", "✅ Unutar EC8 (≤0.0050)" if d_val <= 0.0050 else "⚠️ Prelazi 0.0050")
            v_max = max(res_sum.get("base_shear_x_kn", 0), res_sum.get("base_shear_y_kn", 0))
            rc2.metric("Ukupni posmik V_base", f"{v_max:,.0f} kN", f"X: {res_sum.get('base_shear_x_kn', 0):,.0f} | Y: {res_sum.get('base_shear_y_kn', 0):,.0f} kN")
            rc3.metric("Max pritisak na tlo", f"{res_sum.get('max_soil_pressure_kpa', 0):.0f} kPa", "✅ Bez odizanja" if not res_sum.get("has_soil_uplift") else "⚠️ Odizanje uočeno")
            rc4.metric("Kritični stup", f"{res_sum.get('critical_frame', '—')}", f"PMM = {res_sum.get('max_pmm_ratio', 0.0):.2f} (≤ 1.00)")

            drifts_profile = res_sum.get("drift_by_story", [])
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                if drifts_profile:
                    st_names = [d["story"] for d in drifts_profile]
                    d_vals = [d["drift"] for d in drifts_profile]
                    fig_drift = go.Figure()
                    fig_drift.add_trace(go.Scatter(
                        x=d_vals, y=st_names,
                        mode="lines+markers",
                        name="Proračunski drift",
                        line=dict(color="#38bdf8", width=3),
                        marker=dict(size=9, color="#0284c7")
                    ))
                    fig_drift.add_vline(x=0.0050, line_dash="dash", line_color="#ef4444", annotation_text="EC8 limit (5.0‰)", annotation_position="top right")
                    fig_drift.update_layout(
                        title="📈 Krivulja katnih pomaka po visini (Story Drift)",
                        xaxis_title="Međukatni pomak dr [-]",
                        yaxis_title="Etaža",
                        height=260,
                        margin=dict(l=40, r=20, t=40, b=30),
                    )
                    st.plotly_chart(fig_drift, use_container_width=True)
            with col_chart2:
                df_sf = results_data.get("story_forces", pd.DataFrame())
                if not df_sf.empty:
                    col_v = "VX" if "VX" in df_sf.columns else ("vx" if "vx" in df_sf.columns else None)
                    col_s = "Story" if "Story" in df_sf.columns else ("story" if "story" in df_sf.columns else None)
                    if col_v and col_s:
                        grp_sf = df_sf.groupby(col_s)[col_v].apply(lambda s: s.abs().max()).reset_index()
                        fig_sf = go.Figure(go.Bar(
                            x=grp_sf[col_s], y=grp_sf[col_v],
                            marker_color="#6366f1"
                        ))
                        fig_sf.update_layout(
                            title="⚖️ Katne poprečne sile Vx (kN)",
                            xaxis_title="Etaža",
                            yaxis_title="Poprečna sila (kN)",
                            height=260,
                            margin=dict(l=40, r=20, t=40, b=30),
                        )
                        st.plotly_chart(fig_sf, use_container_width=True)
        else:
            st.info("💡 **Faza 2 (Opcionalno)**: Za automatski uvid u katne pomake, raspodjelu poprečne sile, pritiske na tlo i armaturu, u lijevom izborniku priložite ETABS tablice rezultata (`Display → Show Tables → Export Tables to Excel`).")

        st.markdown("<hr style='margin: 16px 0;'>", unsafe_allow_html=True)

        c_f1, c_f2, c_f3 = st.columns([1.8, 1.8, 1.4])
        with c_f1:
            all_cats = ["Sve nastavne cjeline"] + sorted(list(set(a["category"] for a in audit_results)))
            selected_cat = st.selectbox("Nastavna cjelina:", all_cats, key="audit_cat_filter")
        with c_f2:
            flt_status = st.selectbox(
                "Status točke:",
                ["Sve točke", "Samo uočena upozorenja i pogreške (⚠️ / 🔴)", "Samo usklađene točke (🟢)"],
                key="audit_filter_status"
            )
        with c_f3:
            # Download button for professor review
            audit_summary_md = "# PROFESORSKA EVALUACIJA NUMERIČKOG MODELA (ETABS .e2k)\n\n"
            audit_summary_md += f"**Ukupna ocjena modela:** {score_data['grade']}/5 ({score_data['grade_label']})\n"
            audit_summary_md += f"**Indeks usklađenosti:** {score_data['percentage']}%\n"
            audit_summary_md += f"**Datum kontrole:** {datetime.now().strftime('%d.%m.%Y. %H:%M')}\n\n"
            audit_summary_md += "---\n\n"
            for item in audit_results:
                audit_summary_md += f"### {item['title']} — [{item['status']}]\n"
                audit_summary_md += f"- **Kategorija:** {item['category']}\n"
                audit_summary_md += f"- **Nalaz u modelu:** {item['finding']}\n"
                audit_summary_md += f"- **Nastavno pravilo:** {item['rule']}\n"
                if item.get("bullets"):
                    audit_summary_md += "  - " + "\n  - ".join(item["bullets"]) + "\n"
                if item.get("recommendation"):
                    audit_summary_md += f"- **Preporuka studentu:** {item['recommendation']}\n"
                audit_summary_md += "\n"

            st.download_button(
                label="📥 Preuzmi izvješće za studenta",
                data=audit_summary_md,
                file_name="profesorska_evaluacija_modela.md",
                mime="text/markdown",
                key="dl_prof_audit"
            )

        items_to_show = audit_results
        if selected_cat != all_cats[0] and not selected_cat.startswith("Sve nastavne"):
            items_to_show = [a for a in items_to_show if a.get("category") == selected_cat]

        if "upozorenja" in flt_status.lower():
            items_to_show = [a for a in items_to_show if a["status"] in ("WARNING", "FAIL")]
        elif "usklađene" in flt_status.lower():
            items_to_show = [a for a in items_to_show if a["status"] == "PASS"]

        if not items_to_show:
            st.info("Nema točaka koje odgovaraju odabranom filtru.")

        for item in items_to_show:
            st_val = item["status"]
            if st_val == "PASS":
                icon = "🟢"
                badge_bg = "#dcfce7"
                badge_col = "#15803d"
                badge_txt = "USKLAĐENO"
            elif st_val == "WARNING":
                icon = "🟡"
                badge_bg = "#fef3c7"
                badge_col = "#b45309"
                badge_txt = "UPOZORENJE"
            elif st_val == "FAIL":
                icon = "🔴"
                badge_bg = "#fee2e2"
                badge_col = "#b91c1c"
                badge_txt = "POGREŠKA"
            else:
                icon = "ℹ️"
                badge_bg = "#e0f2fe"
                badge_col = "#0369a1"
                badge_txt = "SMJERNICA"

            bullets_html = ""
            if item.get("bullets"):
                bullets_html = "<ul style='margin: 6px 0 0 16px; padding-left: 0; color: #475569; font-size: 0.84rem;'>"
                for b in item["bullets"]:
                    bullets_html += f"<li style='margin-bottom: 3px;'>{b}</li>"
                bullets_html += "</ul>"

            rec_html = ""
            if item.get("recommendation"):
                rec_html = (
                    f'<div style="font-size: 0.84rem; color: #0369a1; background: #f0f9ff; padding: 10px 14px; border-radius: 6px; border-left: 4px solid #0284c7; margin-top: 10px;">'
                    f'<strong>💡 Uputa studentu za ispravak u ETABS-u:</strong> {item["recommendation"]}'
                    f'</div>'
                )

            card_html = (
                f'<div style="background: white; border: 1px solid #e2e8f0; border-left: 5px solid {badge_col}; border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
                f'<div>'
                f'<span style="font-size: 1.05rem; font-weight: 700; color: #0f172a;">{icon} {item["title"]}</span>'
                f'<span style="font-size: 0.76rem; color: #64748b; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; margin-left: 8px; font-weight: 600;">{item.get("category", "")}</span>'
                f'</div>'
                f'<span style="background: {badge_bg}; color: {badge_col}; font-size: 0.78rem; font-weight: 700; padding: 4px 12px; border-radius: 9999px;">{badge_txt}</span>'
                f'</div>'
                f'<div style="font-size: 0.92rem; color: #1e293b; margin-bottom: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px dashed #cbd5e1;">'
                f'<strong>🔍 Stanje u studentovom modelu:</strong> {item["finding"]}'
                f'</div>'
                f'<div style="font-size: 0.85rem; color: #334155; line-height: 1.45; background: #ffffff; padding: 6px 0;">'
                f'<strong>📖 Nastavno pravilo i zadatak:</strong> <em>{item["rule"]}</em>'
                f'{bullets_html}'
                f'</div>'
                f'{rec_html}'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    # ── TAB 3: Elementi, Presjeci i Svojstva ───────────────────
    with t_elements:
        sub_elem = st.segmented_control(
            "Prikaz svojstava:",
            options=["📐 Geometrija i presjeci", "🧪 Materijali i opterećenja", "🧱 Oslonci i zglobovi"],
            default="📐 Geometrija i presjeci",
            key="sub_elem_segmented",
            label_visibility="collapsed"
        ) or "📐 Geometrija i presjeci"

        if sub_elem.startswith("📐"):
            if is_pdf_mode:
                st.markdown("##### 📋 Kontrolni inventar elemenata modela za provjeru s PDF-om")
                st.caption("Popis nosivih elemenata po etažama s točnim dimenzijama presjeka i materijalima iz ETABS-a.")
            else:
                st.markdown("##### Detaljna usporedba dimenzija i položaja elemenata")

            f0, f1, f2, f3 = st.columns([1.3, 1.3, 1.3, 1.8])
            dfd = df_res.copy()

            with f0:
                st_opts = ["Sve etaže"] + [s.get("display_name", s["name"]) for s in stories]
                st_f = st.selectbox("Etaža:", st_opts, key="tab3_story_filter")
                if st_f != "Sve etaže":
                    s_match = next((s for s in stories if s.get("display_name", s["name"]) == st_f), None)
                    if s_match:
                        if "story" in dfd.columns:
                            dfd = dfd[dfd["story"] == s_match["name"]]
                        else:
                            z_bot = s_match["z_bottom"] - 0.20
                            z_top = s_match["z_top"] + 0.20
                            dfd = dfd[(dfd["etabs_z"] >= z_bot) & (dfd["etabs_z"] <= z_top)]

            with f1:
                if is_pdf_mode:
                    st.caption("Način: PDF elaborat")
                else:
                    st_status = st.selectbox("Status:", ["Svi statusi"] + [s.value for s in Status], key="geo_status")
                    if st_status != "Svi statusi":
                        dfd = dfd[dfd["status"].astype(str) == st_status]

            with f2:
                ty_opts = ["Svi tipovi"] + sorted(dfd["element_type"].dropna().unique()) if "element_type" in dfd.columns else ["Svi tipovi"]
                ty_f = st.selectbox("Tip elementa:", ty_opts, key="geo_type")
                if ty_f != "Svi tipovi":
                    dfd = dfd[dfd["element_type"] == ty_f]

            with f3:
                search = st.text_input("Pretraga po oznaci:", placeholder="C1, B101, W_JUG, 50x50...", key="geo_search")
                if search:
                    q = search.lower()
                    dfd = dfd[dfd.apply(lambda r: q in str(r.to_dict()).lower(), axis=1)]

            vcols = [
                "element_type", "status", "etabs_name", "etabs_z", "etabs_section",
                "etabs_w_mm", "etabs_h_mm", "dxf_dim_text", "dxf_dim1_mm", "dxf_dim2_mm", "xy_dist_m", "notes"
            ]
            vcols = [c for c in vcols if c in dfd.columns]
            tbl = safe_df(dfd[vcols], {
                "etabs_z": "{:.2f}",
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
                    "etabs_z":      st.column_config.TextColumn("Kota Z (m)"),
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

        elif sub_elem.startswith("🧪"):
            mc, lc = st.columns(2, gap="large")
            with mc:
                st.markdown("##### 🧪 Klase materijala (Beton / Čelik)")
                mats = pd.DataFrame(df_res.attrs.get("materials", []))
                if not mats.empty:
                    st.dataframe(
                        safe_df(mats, {"E_gpa": "{:.1f}", "fc_mpa": "{:.1f}", "fy_mpa": "{:.1f}", "fu_mpa": "{:.1f}"}),
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
                        safe_df(pats, {"self_weight_mult": "{:.2f}"}),
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
                    st.dataframe(safe_df(aloads), use_container_width=True, hide_index=True)

        else:
            sc, hc = st.columns(2, gap="large")
            with sc:
                st.markdown("##### 🧱 Temeljni oslonci (Rubni uvjeti)")
                rests = etabs_data.get("restraints", pd.DataFrame()) if etabs_data else pd.DataFrame(df_res.attrs.get("restraints", []))
                if not rests.empty and "joint_name" in rests.columns:
                    rcols = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in rests.columns]
                    st.dataframe(
                        safe_df(rests[rcols], {"x": "{:.2f}", "y": "{:.2f}", "z": "{:.2f}"}),
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
                        safe_df(hinges[hcols], {"rel_dist": "{:.2f}"}),
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

    # ── TAB 4: Službeni PDF Elaborat i Izvještaj ───────────────
    with t_report:
        st.markdown("""
        <div class="dl-card">
          <div style="font-size: 38px; margin-bottom: 8px;">📄</div>
          <h3 style="margin: 0 0 6px 0; color: #0f172a; font-weight: 800;">Službeni Revizijski Elaborat</h3>
          <p style="margin: 0 auto 12px auto; color: #64748b; font-size: 13px; max-width: 650px; line-height: 1.5;">
            Automatsko generiranje i preuzimanje službenog inženjerskog elaborata (A4 Landscape PDF).
            Elaborat služi kao službena tehnička dokumentacija za investitora, glavnog projektanta, revidenta ili arhiv.
          </p>
        </div>
        """, unsafe_allow_html=True)

        d1, d2 = st.columns(2)
        html_content = ""
        with d1:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
                pdf_path = fp.name
            try:
                generate_pdf(df_eval, pdf_path, cfg)
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
                html_content = generate_html(df_eval, html_path, cfg)
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

        if html_content:
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            with st.expander("👁️ Interaktivni pretpregled elaborata u aplikaciji (Uživo)", expanded=True):
                st.components.v1.html(html_content, height=550, scrolling=True)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        with st.expander("📖 Otvori detaljne inženjerske upute za pripremu modela i nacrta", expanded=False):
            render_instructions()


if __name__ == "__main__":
    main()
