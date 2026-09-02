"""
streamlit_app.py — ETABS ↔ CAD Automated Structural QA Platform
Enterprise engineering tool with crystal-clear navigation, high contrast,
full CAD/PDF/image drawing support, multi-story filtering, and zero visual clutter.
"""

import io
import math
import os
import tempfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import Config
from phase1_e2k import parse_e2k
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status, run_structural_sanity_checks
from report import generate_pdf, generate_html
from curriculum_audit import run_curriculum_audit

# ─────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ETABS ↔ CAD · Kontrola Numeričkih Modela",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_SKOLA_DXF = os.path.join(SCRIPT_DIR, "demo_skola.dxf")
DEMO_SKOLA_E2K = os.path.join(SCRIPT_DIR, "demo_skola.e2k")
DEMO_SKOLA_PDF = os.path.join(SCRIPT_DIR, "demo_projekt_skola.pdf")

DEMO_COMMERCIAL_DXF = os.path.join(SCRIPT_DIR, "demo_commercial_building.dxf")
DEMO_COMMERCIAL_E2K = os.path.join(SCRIPT_DIR, "demo_commercial_building.e2k")
SMALL_SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SMALL_SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")

# Default demo files
SAMPLE_DXF = DEMO_SKOLA_DXF
SAMPLE_E2K = DEMO_SKOLA_E2K

# ─────────────────────────────────────────────────────────────
# High-contrast, clean CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Base page setup — generous top padding to NEVER clip under Streamlit header */
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

/* ─── Sidebar: crisp, high contrast, legible ─── */
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

/* ─── KPI Strip ─── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 18px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    border-radius: 12px 12px 0 0;
}
.kpi-card.green::before  { background: #10b981; }
.kpi-card.amber::before  { background: #f59e0b; }
.kpi-card.red::before    { background: #ef4444; }
.kpi-card.blue::before   { background: #3b82f6; }
.kpi-card.slate::before  { background: #64748b; }
.kpi-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.kpi-number {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1;
}
.kpi-sub {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
    font-weight: 500;
}

/* ─── Legend / Explanations ─── */
.legend-banner {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    font-size: 12px;
    color: #334155;
    align-items: center;
}
.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.dot-green { color: #10b981; font-weight: 700; }
.dot-amber { color: #f59e0b; font-weight: 700; }
.dot-red   { color: #ef4444; font-weight: 700; }
.dot-blue  { color: #3b82f6; font-weight: 700; }

/* ─── Warning Pills ─── */
.warn-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #fefce8;
    border: 1px solid #fef08a;
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
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #991b1b;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
    margin-right: 6px;
    margin-bottom: 6px;
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
""", unsafe_allow_html=True)


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
            help="Uključite za instantni pregled s gotovim ETABS modelom i CAD nacrtom zgrade.",
        )
        st.session_state["use_demo"] = use_demo

        demo_model_choice = "school"
        if use_demo:
            default_idx = 0
            if st.session_state.get("demo_choice_key") == "commercial":
                default_idx = 1
            elif st.session_state.get("demo_choice_key") == "small":
                default_idx = 2

            choice_label = st.selectbox(
                "Odaberite demo model:",
                [
                    "🏫 OŠ J. J. Strossmayer (Zidana zgrada — Cjeloviti PDF elaborat s tehničkim opisom i nacrtima)",
                    "🏢 Poslovna zgrada (18×7 polja, 2 etaže — 860 elemenata)",
                    "🏠 Manji ogledni model (3 polja, 1 etaža)",
                ],
                index=default_idx,
                key="demo_model_selector"
            )
            if choice_label.startswith("🏫"):
                demo_model_choice = "school"
            elif choice_label.startswith("🏢"):
                demo_model_choice = "commercial"
            else:
                demo_model_choice = "small"
            st.session_state["demo_choice_key"] = demo_model_choice

        uploaded_dxf = uploaded_pdf_doc = uploaded_e2k = None
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

        is_dxf_selected = (not use_demo and doc_type.startswith("📐")) or (use_demo and demo_model_choice == "commercial")
        if is_dxf_selected:
            scale_label = st.selectbox(
                "Jedinica u CAD crtežu (.dxf):",
                ["Centimetri (cm)", "Milimetri (mm)", "Metri (m)"],
                index=0,
                help="AutoCAD DXF datoteke spremaju koordinate bez fizičke jedinice (samo brojeve). Odaberite u kojoj je jedinici crtan CAD nacrt kako bi se točno preveo u metre.\n\nNapomena: Jedinice ETABS modela automatski se očitavaju iz samog .e2k zaglavlja!",
            )
            scale_map = {"Centimetri (cm)": 0.01, "Milimetri (mm)": 0.001, "Metri (m)": 1.0}
            unit_scale = scale_map[scale_label]
            st.caption("ℹ️ *Jedinice ETABS modela sustav sam očitava iz .e2k zaglavlja.*")
        else:
            st.info("ℹ️ **Jedinice ETABS modela** automatski se očitavaju iz samog `.e2k` zaglavlja (npr. KN, m, °C).\n\nNa PDF nacrtima kote tlocrta su standardno u **cm**, a visinske kote u **m**.")

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
            `File → Export → .e2k Text File...`
            
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

    return use_demo, demo_model_choice, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg


# ─────────────────────────────────────────────────────────────
# Reference Drawing Viewer (PDF / JPEG / PNG / TIFF)
# ─────────────────────────────────────────────────────────────
def _render_drawing(uploaded_drawing, active_story_z=None, active_story_name=None):
    """Renders uploaded PDF or image with sheet selector, quick jump buttons, DPI zoom, and download."""
    if uploaded_drawing is None:
        return

    if isinstance(uploaded_drawing, str):
        file_path = uploaded_drawing
        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            raw = f.read()
    else:
        file_name = uploaded_drawing.name
        raw = uploaded_drawing.getvalue()

    name_lower = file_name.lower()

    try:
        if name_lower.endswith(".pdf"):
            import fitz  # PyMuPDF
            doc = fitz.open(stream=raw, filetype="pdf")
            num_pages = len(doc)

            # Known sheet mapping for OS Strossmayer project elaborat
            SHEET_MAP = {
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

            is_school_doc = num_pages == 20 or any(k in name_lower for k in ("varsavska", "skola", "strossmayer", "stross", "os_"))

            if is_school_doc and active_story_name:
                s_lower = str(active_story_name).lower()
                target_pg = None
                if "priz" in s_lower:
                    target_pg = 14
                elif "1" in s_lower or "prvi" in s_lower:
                    target_pg = 15
                elif "2" in s_lower or "drugi" in s_lower:
                    target_pg = 16
                elif "krov" in s_lower or "potkrov" in s_lower or "tavan" in s_lower:
                    target_pg = 17

                if target_pg and st.session_state.get("_last_synced_story") != active_story_name:
                    st.session_state["active_pdf_page"] = target_pg
                    st.session_state["_last_synced_story"] = active_story_name

            # Default initial page: Page 14 (Prizemlje) for school drawings, else Page 1
            if "active_pdf_page" not in st.session_state:
                st.session_state["active_pdf_page"] = 14 if is_school_doc else 1

            st.markdown(f"###### 📑 Projektni elaborat: **{file_name}** ({num_pages} str.)")

            if is_school_doc:
                # Quick jump buttons for structural drawings and description
                c_b1, c_b2, c_b3, c_b4, c_b5 = st.columns(5)
                with c_b1:
                    if st.button("📐 Prizemlje (14)", key="btn_priz", use_container_width=True):
                        st.session_state["active_pdf_page"] = 14
                        st.rerun()
                with c_b2:
                    if st.button("📐 1. Kat (15)", key="btn_kat1", use_container_width=True):
                        st.session_state["active_pdf_page"] = 15
                        st.rerun()
                with c_b3:
                    if st.button("📐 2. Kat (16)", key="btn_kat2", use_container_width=True):
                        st.session_state["active_pdf_page"] = 16
                        st.rerun()
                with c_b4:
                    if st.button("📐 Presjeci (19)", key="btn_presjeci", use_container_width=True):
                        st.session_state["active_pdf_page"] = 19
                        st.rerun()
                with c_b5:
                    if st.button("📄 Teh. opis (5)", key="btn_opis", use_container_width=True):
                        st.session_state["active_pdf_page"] = 5
                        st.rerun()

            ctrl1, ctrl2, ctrl3 = st.columns([2.2, 1.2, 1.4])
            with ctrl1:
                if is_school_doc:
                    opts = [SHEET_MAP.get(p, f"Stranica {p}") for p in range(1, num_pages + 1)]
                    cur_idx = min(max(st.session_state["active_pdf_page"] - 1, 0), num_pages - 1)
                    chosen_opt = st.selectbox(
                        "Brzi skok na nacrt / poglavlje:",
                        opts,
                        index=cur_idx,
                        key="pdf_sheet_dropdown"
                    )
                    st.session_state["active_pdf_page"] = opts.index(chosen_opt) + 1
                else:
                    st.session_state["active_pdf_page"] = st.number_input(
                        f"Stranica (ukupno {num_pages}):",
                        min_value=1, max_value=num_pages,
                        value=st.session_state["active_pdf_page"],
                        step=1, key="pdf_direct_num"
                    )

            with ctrl2:
                dpi_choice = st.selectbox("Oštrina prikaza:", ["120 DPI (Normalno)", "160 DPI (Oštro)", "200 DPI (Ultra)"], index=1, key="pdf_dpi_opt")
                dpi_val = 120 if "120" in dpi_choice else (160 if "160" in dpi_choice else 200)

            with ctrl3:
                st.download_button(
                    label=f"📥 Preuzmi PDF ({len(raw)/1024/1024:.1f} MB)",
                    data=raw,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_original_pdf_btn"
                )

            sel_page_idx = min(max(st.session_state["active_pdf_page"] - 1, 0), num_pages - 1)
            page = doc[sel_page_idx]
            pix = page.get_pixmap(dpi=dpi_val, alpha=False)
            img_bytes = pix.tobytes("png")

            caption_txt = SHEET_MAP.get(sel_page_idx + 1, f"Stranica {sel_page_idx + 1}") if is_school_doc else f"Stranica {sel_page_idx + 1} od {num_pages}"
            st.image(img_bytes, use_container_width=True, caption=f"📄 {file_name} — {caption_txt}")

        else:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(raw))
            max_w = 3200
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
            st.image(img, use_container_width=True, caption=f"Nacrt: {file_name}")
    except Exception as e:
        st.error(f"Pogreška pri učitavanju nacrta: {e}")


# ─────────────────────────────────────────────────────────────
# KPI Strip: Colored indicator borders, crisp typography
# ─────────────────────────────────────────────────────────────
def _kpi_strip(df: pd.DataFrame, is_pdf_mode: bool = False, etabs_data: dict = None):
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
            <div class="kpi-label">🏢 Elementi modela</div>
            <div class="kpi-number">{n_total}</div>
            <div class="kpi-sub">{sub_desc}</div>
          </div>
          <div class="kpi-card amber">
            <div class="kpi-label">📐 Poprečni presjeci</div>
            <div class="kpi-number">{n_secs}</div>
            <div class="kpi-sub">Različitih profila</div>
          </div>
          <div class="kpi-card blue">
            <div class="kpi-label">🧪 Materijali modela</div>
            <div class="kpi-number">{n_mats}</div>
            <div class="kpi-sub">Klasa betona / čelika / opeke</div>
          </div>
          <div class="kpi-card slate">
            <div class="kpi-label">🧱 Temeljni ležajevi</div>
            <div class="kpi-number">{n_rests}</div>
            <div class="kpi-sub">Pridržanih točaka baze</div>
          </div>
          <div class="kpi-card purple" style="border-left: 4px solid #8b5cf6;">
            <div class="kpi-label">📑 Način kontrole</div>
            <div class="kpi-number" style="font-size: 18px; font-weight: 700; color: #8b5cf6; padding-top: 4px;">PDF Dokument</div>
            <div class="kpi-sub">Usporedba s PDF nacrtom</div>
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
      <div class="kpi-card slate">
        <div class="kpi-label">📋 Ukupno provjereno</div>
        <div class="kpi-number">{n_total}</div>
        <div class="kpi-sub">Elemenata analizirano</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 2D Floorplan: True architectural layout with CAD axis bubbles
# ─────────────────────────────────────────────────────────────
def _fig_2d(df_res: pd.DataFrame, etabs_data: dict, active_story_name: str = None) -> go.Figure:
    COLOR_MAP = {
        Status.MATCH:            ("#10b981", "Usklađeno s nacrtom"),
        Status.SECTION_MISMATCH: ("#f59e0b", "Odstupanje dimenzija"),
        Status.ETABS_ONLY:       ("#ef4444", "Samo u ETABS-u"),
        Status.DXF_ONLY:         ("#3b82f6", "Samo u CAD nacrtu"),
        "Za provjeru s PDF-om":  ("#0284c7", "Element u modelu"),
    }

    fig = go.Figure()

    cols_all = etabs_data.get("columns", pd.DataFrame())
    beams_all = etabs_data.get("beams", pd.DataFrame())
    slabs_all = etabs_data.get("slabs", pd.DataFrame())
    walls_all = etabs_data.get("walls", pd.DataFrame())

    # Infer active_story_name if not provided but df_res is filtered
    if not active_story_name and not df_res.empty and "story" in df_res.columns:
        u_st = [s for s in df_res["story"].dropna().unique() if s]
        if len(u_st) == 1:
            active_story_name = u_st[0]

    # Collect coordinates for bounding box based on active elements
    if active_story_name and not walls_all.empty and "story" in walls_all.columns:
        st_walls = walls_all[walls_all["story"] == active_story_name]
        if not st_walls.empty:
            all_x = sorted(set([round(float(w["x_start"]), 2) for _, w in st_walls.iterrows()] + [round(float(w["x_end"]), 2) for _, w in st_walls.iterrows()]))
            all_y = sorted(set([round(float(w["y_start"]), 2) for _, w in st_walls.iterrows()] + [round(float(w["y_end"]), 2) for _, w in st_walls.iterrows()]))
        else:
            all_x, all_y = [], []
    else:
        all_x, all_y = [], []

    if not all_x:
        if not cols_all.empty:
            all_x = sorted(set([round(float(x), 2) for x in cols_all["x_start"].dropna()]))
            all_y = sorted(set([round(float(y), 2) for y in cols_all["y_start"].dropna()]))
        else:
            all_x = sorted(set([round(float(r["etabs_x"]), 2) for _, r in df_res.iterrows() if pd.notna(r.get("etabs_x"))]))
            all_y = sorted(set([round(float(r["etabs_y"]), 2) for _, r in df_res.iterrows() if pd.notna(r.get("etabs_y"))]))

    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 12.0
    min_y = min(all_y) if all_y else 0.0
    max_y = max(all_y) if all_y else 6.0

    pad_x = max((max_x - min_x) * 0.08, 2.5)
    pad_y = max((max_y - min_y) * 0.12, 2.5)

    status_map = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    # 1. Background Slab Polygons
    if not slabs_all.empty or (max_x > min_x and max_y > min_y):
        fig.add_trace(go.Scatter(
            x=[min_x, max_x, max_x, min_x, min_x],
            y=[min_y, min_y, max_y, max_y, min_y],
            fill="toself",
            fillcolor="rgba(241, 245, 249, 0.7)",
            line=dict(color="#cbd5e1", width=1, dash="dash"),
            name="Ploča konstrukcije",
            hovertext=f"<b>Ploča konstrukcije ({active_story_name or 'Sve etaže'})</b><br>Raspon: {max_x - min_x:.1f} × {max_y - min_y:.1f} m",
            hoverinfo="text",
            showlegend=False,
        ))

    # 2. Beams: connecting grid lines
    if not beams_all.empty:
        if active_story_name and "story" in beams_all.columns:
            beams_to_draw = beams_all[beams_all["story"] == active_story_name]
            if beams_to_draw.empty:
                beams_to_draw = beams_all
        else:
            active_beam_names = set(df_res[df_res["element_type"] == "beam"]["etabs_name"].dropna().astype(str))
            if active_beam_names:
                beams_to_draw = beams_all[beams_all["name"].astype(str).isin(active_beam_names)]
            else:
                beams_to_draw = beams_all

        b_xs, b_ys = [], []
        for _, bm in beams_to_draw.iterrows():
            b_xs.extend([bm["x_start"], bm["x_end"], None])
            b_ys.extend([bm["y_start"], bm["y_end"], None])
        if b_xs:
            fig.add_trace(go.Scatter(
                x=b_xs, y=b_ys,
                mode="lines",
                line=dict(color="#cbd5e1", width=2),
                name="Mreža greda",
                hoverinfo="skip",
                showlegend=False,
            ))

    # Any DXF-only beams
    dxf_only_beams = df_res[(df_res["status"] == Status.DXF_ONLY) & (df_res["element_type"] == "beam")]
    for _, bm in dxf_only_beams.iterrows():
        bx = bm.get("dxf_x", 0.0)
        by = bm.get("dxf_y", 0.0)
        fig.add_trace(go.Scatter(
            x=[bx, bx + 5.0], y=[by, by],
            mode="lines",
            line=dict(color="#3b82f6", width=4, dash="dot"),
            name="Samo u CAD-u",
            hovertext=f"<b>Greda (samo u CAD-u)</b><br>Kota: {bm.get('dxf_dim_text','—')}<br>Lokacija: Y = {by:.2f} m",
            hoverinfo="text",
            showlegend=False,
        ))

    # 3. Walls: True geometric baseline with solid physical thickness
    if not walls_all.empty:
        if active_story_name and "story" in walls_all.columns:
            walls_to_draw = walls_all[walls_all["story"] == active_story_name]
            if walls_to_draw.empty:
                walls_to_draw = walls_all
        else:
            active_wall_names = set(df_res[df_res["element_type"] == "wall"]["etabs_name"].dropna().astype(str))
            walls_to_draw = walls_all[walls_all["name"].astype(str).isin(active_wall_names)] if active_wall_names else walls_all

        for _, w in walls_to_draw.iterrows():
            st_val = status_map.get(str(w["name"]), Status.MATCH)
            col, lbl = COLOR_MAP.get(st_val, ("#0284c7", "Element u modelu"))
            x1 = w.get("x_start", w.get("centroid_x", 0.0))
            y1 = w.get("y_start", w.get("centroid_y", 0.0))
            x2 = w.get("x_end", w.get("centroid_x", 0.0))
            y2 = w.get("y_end", w.get("centroid_y", 0.0))

            thick_m = float(w.get("thickness_mm", 250.0)) / 1000.0
            dx = x2 - x1
            dy = y2 - y1
            L = math.hypot(dx, dy)

            if L < 0.05:
                cx, cy = w.get("centroid_x", 0.0), w.get("centroid_y", 0.0)
                ht = max(thick_m / 2.0, 0.15)
                poly_x = [cx - ht, cx + ht, cx + ht, cx - ht, cx - ht]
                poly_y = [cy - ht, cy - ht, cy + ht, cy + ht, cy - ht]
            else:
                nx = -dy / L
                ny = dx / L
                ht = max(thick_m / 2.0, 0.12)
                poly_x = [
                    x1 + nx * ht, x2 + nx * ht,
                    x2 - nx * ht, x1 - nx * ht,
                    x1 + nx * ht
                ]
                poly_y = [
                    y1 + ny * ht, y2 + ny * ht,
                    y2 - ny * ht, y1 - ny * ht,
                    y1 + ny * ht
                ]

            fig.add_trace(go.Scatter(
                x=poly_x, y=poly_y,
                fill="toself",
                fillcolor=col,
                line=dict(color="#0369a1", width=1.5),
                mode="lines",
                name="Zidovi",
                hovertext=(
                    f"<b>Zid {w['name']}</b> [{lbl}]<br>"
                    f"Presjek: {w.get('prop_name', '—')} (Debljina: {thick_m*1000:.0f} mm)<br>"
                    f"Središnja os: ({x1:.2f}, {y1:.2f}) → ({x2:.2f}, {y2:.2f})<br>"
                    f"Model: Od sredine do sredine zida (±{thick_m*500:.0f} mm do lica)<br>"
                    f"Materijal: {w.get('material', '—')}"
                ),
                hoverinfo="text",
                showlegend=False,
            ))

            # Proračunska os (od sredine do sredine zida)
            fig.add_trace(go.Scatter(
                x=[x1, x2], y=[y1, y2],
                mode="lines",
                line=dict(color="#ffffff", width=1.8, dash="dash"),
                name="Središnja os zida",
                hoverinfo="skip",
                showlegend=False,
            ))

    # 4. Columns: Sharp colored squares
    if active_story_name and "story" in df_res.columns:
        col_records = df_res[(df_res["element_type"] == "column") & (df_res["story"] == active_story_name)]
        if col_records.empty:
            col_records = df_res[df_res["element_type"] == "column"]
    else:
        col_records = df_res[df_res["element_type"] == "column"]
    marker_size = 12 if len(col_records) > 50 else 22
    show_text_on_marker = len(col_records) <= 25

    for status, (color, label) in COLOR_MAP.items():
        sub_cols = col_records[col_records["status"] == status]
        if sub_cols.empty:
            continue

        xs = [r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x") for _, r in sub_cols.iterrows()]
        ys = [r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y") for _, r in sub_cols.iterrows()]
        texts = [r.get("etabs_name") or r.get("dxf_name") or "C" for _, r in sub_cols.iterrows()] if show_text_on_marker else None

        tips = []
        for _, r in sub_cols.iterrows():
            nm = r.get("etabs_name") or r.get("dxf_name") or "Stup"
            sec = r.get("etabs_section") or "—"
            ew, eh = r.get("etabs_w_mm"), r.get("etabs_h_mm")
            dw, dh = r.get("dxf_dim1_mm"), r.get("dxf_dim2_mm")
            tips.append(
                f"<b>{nm}</b> [{label}]<br>"
                f"Presjek: {sec}<br>"
                f"ETABS dim.: {f'{ew:.0f}×{eh:.0f}' if pd.notna(ew) and pd.notna(eh) else '—'} mm<br>"
                f"CAD dim.:   {f'{dw:.0f}×{dh:.0f}' if pd.notna(dw) and pd.notna(dh) else '—'} mm<br>"
                f"Status: {r.get('notes') or label}"
            )

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text" if show_text_on_marker else "markers",
            marker=dict(
                size=marker_size,
                symbol="square",
                color=color,
                line=dict(color="#ffffff", width=1.5),
            ),
            text=texts if show_text_on_marker else None,
            textposition="top center",
            textfont=dict(size=10, color="#0f172a", family="Inter", weight="bold"),
            name=f"{label} ({len(sub_cols)})",
            hovertext=tips,
            hoverinfo="text",
            showlegend=True,
        ))

    # 5. Architectural Grid Bubbles (From ETABS or clean clustered axes)
    df_grids = etabs_data.get("grids", pd.DataFrame())
    if not df_grids.empty and "dir" in df_grids.columns and "coord" in df_grids.columns:
        x_grids = df_grids[df_grids["dir"] == "X"].sort_values("coord")
        y_grids = df_grids[df_grids["dir"] == "Y"].sort_values("coord")
        bubble_xs = x_grids["coord"].tolist() if not x_grids.empty else []
        labels_x = x_grids["id"].tolist() if not x_grids.empty else []
        bubble_ys = y_grids["coord"].tolist() if not y_grids.empty else []
        labels_y = y_grids["id"].tolist() if not y_grids.empty else []
    else:
        bubble_xs, labels_x = [], []
        bubble_ys, labels_y = [], []

    def _cluster_coords(coords, min_gap=3.5):
        if not coords:
            return []
        sorted_c = sorted(coords)
        out = [sorted_c[0]]
        for c in sorted_c[1:]:
            if c - out[-1] >= min_gap:
                out.append(c)
        if sorted_c[-1] - out[-1] > min_gap * 0.6:
            out.append(sorted_c[-1])
        return out

    if not bubble_xs:
        bubble_xs = _cluster_coords(all_x, min_gap=4.0)
        labels_x = [chr(65 + i) if i < 26 else f"A{i}" for i in range(len(bubble_xs))]
    y_bubble = max_y + pad_y * 0.45

    for gx, lx in zip(bubble_xs, labels_x):
        fig.add_shape(type="line", x0=gx, y0=min_y - 0.5, x1=gx, y1=y_bubble,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=[gx], y=[y_bubble],
            mode="markers+text",
            marker=dict(size=22, color="#3b82f6", line=dict(color="#ffffff", width=1.5)),
            text=[lx], textfont=dict(color="white", size=10, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {lx} (X = {gx:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    if not bubble_ys:
        bubble_ys = _cluster_coords(all_y, min_gap=4.0)
        labels_y = [str(i + 1) for i in range(len(bubble_ys))]
    x_bubble = min_x - pad_x * 0.45

    for gy, ly in zip(bubble_ys, labels_y):
        fig.add_shape(type="line", x0=x_bubble, y0=gy, x1=max_x + 0.5, y1=gy,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=[x_bubble], y=[gy],
            mode="markers+text",
            marker=dict(size=22, color="#0284c7", line=dict(color="#ffffff", width=1.5)),
            text=[ly], textfont=dict(color="white", size=10, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {ly} (Y = {gy:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    fig.update_layout(
        title=dict(
            text=f"<b>📐 Tlocrt: {active_story_name}</b>" if active_story_name else "<b>📐 Tlocrt numeričkog modela (Sve etaže)</b>",
            x=0.02, y=0.98,
            font=dict(size=14, color="#0f172a"),
        ),
        margin=dict(l=30, r=20, t=40, b=40),
        height=540,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            title="X koordinata (m)",
            range=[min_x - pad_x, max_x + pad_x],
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=True,
            zerolinecolor="#cbd5e1",
            tickfont=dict(size=11, color="#64748b"),
        ),
        yaxis=dict(
            title="Y koordinata (m)",
            range=[min_y - pad_y, max_y + pad_y],
            scaleanchor="x",
            scaleratio=1,
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=True,
            zerolinecolor="#cbd5e1",
            tickfont=dict(size=11, color="#64748b"),
        ),
        legend=dict(
            orientation="h",
            x=0, y=-0.14,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e2e8f0",
            borderwidth=1,
            font=dict(size=11, color="#334155"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 3D Model: Fast segmented wireframe matching ETABS appearance
# ─────────────────────────────────────────────────────────────
def _fig_3d(df_res: pd.DataFrame, etabs_data: dict, etabs_color_mode: bool = True, active_story_name: str = None) -> go.Figure:
    fig = go.Figure()

    cols = etabs_data.get("columns", pd.DataFrame())
    beams = etabs_data.get("beams", pd.DataFrame())
    walls = etabs_data.get("walls", pd.DataFrame())
    slabs = etabs_data.get("slabs", pd.DataFrame())

    if active_story_name:
        if not cols.empty and "story" in cols.columns:
            cols = cols[cols["story"] == active_story_name]
        if not beams.empty and "story" in beams.columns:
            beams = beams[beams["story"] == active_story_name]
        if not walls.empty and "story" in walls.columns:
            walls = walls[walls["story"] == active_story_name]
        if not slabs.empty and "story" in slabs.columns:
            slabs = slabs[slabs["story"] == active_story_name]

    status_by = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    if etabs_color_mode:
        # Authentic ETABS magenta wireframe view (matching screenshot)
        if not cols.empty:
            c_xs, c_ys, c_zs = [], [], []
            for _, c in cols.iterrows():
                c_xs.extend([c["x_start"], c["x_end"], None])
                c_ys.extend([c["y_start"], c["y_end"], None])
                c_zs.extend([c["z_start"], c["z_end"], None])
            fig.add_trace(go.Scatter3d(
                x=c_xs, y=c_ys, z=c_zs,
                mode="lines",
                line=dict(color="#d946ef", width=5),
                name="Stupovi (ETABS)",
            ))

        if not beams.empty:
            b_xs, b_ys, b_zs = [], [], []
            for _, b in beams.iterrows():
                b_xs.extend([b["x_start"], b["x_end"], None])
                b_ys.extend([b["y_start"], b["y_end"], None])
                b_zs.extend([b["z_start"], b["z_end"], None])
            fig.add_trace(go.Scatter3d(
                x=b_xs, y=b_ys, z=b_zs,
                mode="lines",
                line=dict(color="#a855f7", width=3),
                name="Grede (ETABS)",
            ))
    else:
        # Audit color mode: Green = Matched, Amber = Section mismatch, Red = ETABS only
        for st_val, col_hex, lbl in [
            (Status.MATCH, "#10b981", "Usklađeni stupovi"),
            (Status.SECTION_MISMATCH, "#f59e0b", "Odstupanje presjeka"),
            (Status.ETABS_ONLY, "#ef4444", "Samo u ETABS-u"),
        ]:
            c_xs, c_ys, c_zs = [], [], []
            for _, c in (cols.iterrows() if not cols.empty else []):
                if status_by.get(str(c["name"]), Status.MATCH) == st_val:
                    c_xs.extend([c["x_start"], c["x_end"], None])
                    c_ys.extend([c["y_start"], c["y_end"], None])
                    c_zs.extend([c["z_start"], c["z_end"], None])
            if c_xs:
                fig.add_trace(go.Scatter3d(
                    x=c_xs, y=c_ys, z=c_zs,
                    mode="lines",
                    line=dict(color=col_hex, width=6),
                    name=lbl,
                ))

        # Beams
        if not beams.empty:
            b_xs, b_ys, b_zs = [], [], []
            for _, b in beams.iterrows():
                b_xs.extend([b["x_start"], b["x_end"], None])
                b_ys.extend([b["y_start"], b["y_end"], None])
                b_zs.extend([b["z_start"], b["z_end"], None])
            fig.add_trace(go.Scatter3d(
                x=b_xs, y=b_ys, z=b_zs,
                mode="lines",
                line=dict(color="#64748b", width=3),
                name="Grede",
            ))

    # Walls in 3D: Shaded structural panels & wireframe contours
    walls = etabs_data.get("walls", pd.DataFrame())
    if not walls.empty:
        w_xs, w_ys, w_zs = [], [], []
        mesh_x, mesh_y, mesh_z = [], [], []
        mesh_i, mesh_j, mesh_k = [], [], []
        v_offset = 0

        for _, w in walls.iterrows():
            pts = w.get("pts_coords")
            if isinstance(pts, (list, tuple)) and len(pts) >= 3:
                for p in pts:
                    w_xs.append(p[0])
                    w_ys.append(p[1])
                    w_zs.append(p[2])
                w_xs.append(pts[0][0])
                w_ys.append(pts[0][1])
                w_zs.append(pts[0][2])
                w_xs.append(None)
                w_ys.append(None)
                w_zs.append(None)

                if len(pts) == 4:
                    for p in pts:
                        mesh_x.append(p[0])
                        mesh_y.append(p[1])
                        mesh_z.append(p[2])
                    mesh_i.extend([v_offset, v_offset])
                    mesh_j.extend([v_offset + 1, v_offset + 2])
                    mesh_k.extend([v_offset + 2, v_offset + 3])
                    v_offset += 4
                elif len(pts) == 3:
                    for p in pts:
                        mesh_x.append(p[0])
                        mesh_y.append(p[1])
                        mesh_z.append(p[2])
                    mesh_i.append(v_offset)
                    mesh_j.append(v_offset + 1)
                    mesh_k.append(v_offset + 2)
                    v_offset += 3
            else:
                x1 = w.get("x_start", w["centroid_x"])
                y1 = w.get("y_start", w["centroid_y"])
                x2 = w.get("x_end", w["centroid_x"])
                y2 = w.get("y_end", w["centroid_y"])
                cz = w.get("centroid_z", 0.0)
                h = 3.0
                w_xs.extend([x1, x2, x2, x1, x1, None])
                w_ys.extend([y1, y2, y2, y1, y1, None])
                w_zs.extend([cz - h/2, cz - h/2, cz + h/2, cz + h/2, cz - h/2, None])

        if mesh_x:
            fig.add_trace(go.Mesh3d(
                x=mesh_x, y=mesh_y, z=mesh_z,
                i=mesh_i, j=mesh_j, k=mesh_k,
                color="#0284c7" if etabs_color_mode else "#10b981",
                opacity=0.22,
                name="Plohe zidova (ETABS)",
                hoverinfo="skip",
            ))

        if w_xs:
            fig.add_trace(go.Scatter3d(
                x=w_xs, y=w_ys, z=w_zs,
                mode="lines",
                line=dict(color="#0369a1" if etabs_color_mode else "#059669", width=2.5),
                name="Konture zidova (ETABS)",
                hoverinfo="skip",
            ))

    # Slabs in 3D: Shaded plane & borders
    slabs = etabs_data.get("slabs", pd.DataFrame())
    if not slabs.empty:
        s_xs, s_ys, s_zs = [], [], []
        s_mesh_x, s_mesh_y, s_mesh_z = [], [], []
        s_mesh_i, s_mesh_j, s_mesh_k = [], [], []
        s_v_offset = 0

        for _, s in slabs.iterrows():
            pts = s.get("pts_coords")
            if isinstance(pts, (list, tuple)) and len(pts) >= 3:
                for p in pts:
                    s_xs.append(p[0])
                    s_ys.append(p[1])
                    s_zs.append(p[2])
                s_xs.append(pts[0][0])
                s_ys.append(pts[0][1])
                s_zs.append(pts[0][2])
                s_xs.append(None)
                s_ys.append(None)
                s_zs.append(None)

                if len(pts) >= 4:
                    for p in pts[:4]:
                        s_mesh_x.append(p[0])
                        s_mesh_y.append(p[1])
                        s_mesh_z.append(p[2])
                    s_mesh_i.extend([s_v_offset, s_v_offset])
                    s_mesh_j.extend([s_v_offset + 1, s_v_offset + 2])
                    s_mesh_k.extend([s_v_offset + 2, s_v_offset + 3])
                    s_v_offset += 4

        if s_mesh_x:
            fig.add_trace(go.Mesh3d(
                x=s_mesh_x, y=s_mesh_y, z=s_mesh_z,
                i=s_mesh_i, j=s_mesh_j, k=s_mesh_k,
                color="#f59e0b",
                opacity=0.18,
                name="Međukatna ploča",
                hoverinfo="skip",
            ))

        if s_xs:
            fig.add_trace(go.Scatter3d(
                x=s_xs, y=s_ys, z=s_zs,
                mode="lines",
                line=dict(color="#d97706", width=2, dash="dash"),
                name="Ploče (ETABS)",
                hoverinfo="skip",
            ))

    # Base restraints (fixed / pinned foundation joints at Z=0)
    rests = etabs_data.get("restraints", pd.DataFrame())
    if not rests.empty and "x" in rests.columns:
        fig.add_trace(go.Scatter3d(
            x=rests["x"], y=rests["y"], z=rests["z"],
            mode="markers",
            marker=dict(size=4, color="#0284c7", symbol="square"),
            name="Oslonci temelja (Base)",
        ))

    # Slabs
    if not cols.empty:
        max_x = cols["x_end"].max()
        max_y = cols["y_end"].max()
        z_levels = sorted(set(cols["z_end"].dropna().tolist()))
        for zl in z_levels:
            fig.add_trace(go.Mesh3d(
                x=[0, max_x, max_x, 0],
                y=[0, 0, max_y, max_y],
                z=[zl, zl, zl, zl],
                i=[0, 0], j=[1, 2], k=[2, 3],
                color="#0284c7", opacity=0.10, showlegend=False,
                hovertext=f"Ploča etaže Z = {zl:.2f} m", hoverinfo="text",
            ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=540,
        paper_bgcolor="#ffffff",
        scene=dict(
            aspectmode="data",
            camera=dict(eye=dict(x=-1.6, y=-1.6, z=0.9)),
            xaxis=dict(title="X (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            yaxis=dict(title="Y (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
            zaxis=dict(title="Z (m)", gridcolor="#e2e8f0", backgroundcolor="#f8fafc"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# Table helper: Cleans attrs & formats floats safely
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
# User Guide & Engineering Instructions Component
# ─────────────────────────────────────────────────────────────
def _render_instructions():
    """Renders comprehensive user manual and engineering guide."""
    st.markdown("""
    ### 📖 Inženjerski Vodič za Kontrolu Numeričkih Modela (ETABS ↔ CAD)

    Ovaj sustav omogućuje **automatiziranu reviziju i kontrolu kvalitete (QA/QC)** proračunskih modela iz softvera **CSI ETABS v23** u odnosu na izvedbene arhitektonske i građevinske nacrte (**AutoCAD .dxf, PDF ili slike**) u skladu s **Eurocode normama (HRN EN 1990, EN 1992, EN 1993, EN 1998)**.

    ---

    #### 1️⃣ Korak 1 — Izvoz modela iz ETABS-a (2 klika)
    1. Otvorite svoj projekt u programu **ETABS v23** (ili ranijim verzijama).
    2. U glavnom izborniku na vrhu odaberite:  
       👉 **`File` → `Export` → `ETABS .e2k Text File...`**
    3. Odaberite mapu i spremite datoteku na računalo (npr. `Projekt_Konstrukcije.e2k`).
    4. *Zašto .e2k a ne .edb?*  
       Datoteka `.edb` je interna binarna baza podataka koju ETABS zaključava i koja se ne može sigurno čitati na webu bez instaliranog Windows ETABS-a i aktivne licence. Datoteka `.e2k` je službeni, čisti tekstualni format namijenjen upravo za vanjsku razmjenu, arhiviranje i neovisnu reviziju modela.

    ---

    #### 2️⃣ Korak 2 — Priprema i učitavanje CAD nacrta (.dxf)
    1. U AutoCAD-u otvorite tlocrt oplate ili armature etaže koju želite provjeriti.
    2. Spremite ga u DXF formatu: **`File` → `Save As` → `AutoCAD 2010/2018 DXF (*.dxf)`**.
    3. **Mjerne jedinice:** U lijevom izborniku aplikacije pod *Jedinica u CAD crtežu* obavezno odaberite jedinicu u kojoj je crtano:
       - **Centimetri (cm)** — najčešći standard u visokogradnji (stup 50×50 cm je nacrtan kao 50×50).
       - **Milimetri (mm)** — čest u detaljima i čeličnim konstrukcijama (stup je 500×500).
       - **Metri (m)** — u geodeziji ili općim situacijama (stup je 0.50×0.50).
    4. **Podržani elementi u CAD-u:**
       - Stupovi mogu biti nacrtani kao zatvorene **polilinije** (`LWPOLYLINE`) ili **AutoCAD blokovi** (`INSERT`).
       - Sustav automatski mjeri dimenzije iz same geometrije polilinije, a ako postoji tekstualna oznaka (npr. `50x50`, `Ø45`), provjerava i nju!
    5. **Referentni PDF ili slika nacrta (opcija):**
       - Ako nemate DXF ili želite vizualnu usporedbu, u polje *Referentni nacrt* učitajte PDF nacrt (ili JPG/PNG). Aplikacija će ga prikazati usporedo s modelom u prvom tabu!

    ---

    #### 3️⃣ Korak 3 — Rad s višeetažnim zgradama (Story Filter)
    Budući da CAD nacrt obično prikazuje **jednu etažu** (npr. *Tlocrt oplate 1. kata*), a ETABS model sadrži **cijelu zgradu u 3D prostoru**:
    - Iznad rezultata koristite padajući izbornik: **"Odabir etaže za provjeru s CAD nacrtom"**.
    - Odaberite odgovarajući kat (npr. `1️⃣ Prizemlje / 1. Kat (Z = 3.80 m)`).
    - Aplikacija će trenutno filtrirati stupove, grede i ploče te etaže i usporediti ih s nacrtom, bez lažnih odstupanja s gornjih katova.

    ---

    #### 4️⃣ Korak 4 — Tumač statusa i boja
    - 🟢 **Usklađeno (Match):** Element je pronađen na točnoj lokaciji i njegove dimenzije u potpunosti odgovaraju nacrtu unutar zadane tolerancije.
    - 🟡 **Odstupanje presjeka (Section Mismatch):** Pozicija odgovara, ali postoji razlika u dimenzijama (npr. CAD 40×40 cm vs. ETABS 50×50 cm). Potrebno uskladiti proračunski model s izvedbenim projektom!
    - 🔴 **Samo u ETABS-u (ETABS Only):** Element postoji u numeričkom modelu, ali ga nema u nacrtu (mogući uzrok: element s druge etaže, privremeni štap ili višak).
    - 🔵 **Samo u CAD-u (CAD Only):** Element je ucrtan na nacrtu, ali nije unesen u ETABS model (potencijalno zaboravljeni nosivi stup ili greda!).

    ---

    #### 5️⃣ Korak 5 — Podešavanje inženjerskih tolerancija
    U lijevom izborniku pod `📐 3. Jedinice i tolerancije`:
    - **Tolerancija pozicije stupova/greda (m):** Dozvoljeni prostorni razmak osi elementa i nacrta (preporučeno 0.15 m = 15 cm).
    - **Dozvoljeno odstupanje presjeka (mm):** Dozvoljena razlika u dimenziji prije označavanja greške (preporučeno 5 mm).

    ---

    #### 6️⃣ Korak 6 — Preuzimanje službenog elaborata
    U tabu **📄 5. Službeni PDF Elaborat** kliknite:
    - **📥 Preuzmi PDF Elaborat (A4 Landscape):** Generira formalni dokument s naslovnicom, sažetkom usklađenosti po elementima, tlocrtom i tablicom svih odstupanja, spreman za arhivu i potpis ovlaštenog inženjera ili revidenta.
    """)


# ─────────────────────────────────────────────────────────────
# Main Application Flow
# ─────────────────────────────────────────────────────────────
def main():
    use_demo, demo_model_choice, uploaded_dxf, uploaded_e2k, uploaded_drawing, cfg = _sidebar()

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

    if use_demo:
        if demo_model_choice == "school":
            # School project demo: ETABS model + 20-page PDF elaborat (no DXF required!)
            e2k_target = DEMO_SKOLA_E2K
            if os.path.exists(e2k_target):
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                uploaded_drawing = DEMO_SKOLA_PDF
                is_pdf_mode = True
                has_data = True
        elif demo_model_choice == "commercial":
            dxf_target = DEMO_COMMERCIAL_DXF
            e2k_target = DEMO_COMMERCIAL_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                dxf_path = dxf_target
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True
        else:
            dxf_target = SMALL_SAMPLE_DXF
            e2k_target = SMALL_SAMPLE_E2K
            if os.path.exists(dxf_target) and os.path.exists(e2k_target):
                dxf_path = dxf_target
                with open(e2k_target, "r", encoding="utf-8", errors="replace") as f:
                    e2k_content = f.read()
                has_data = True

        if not has_data:
            st.error("Ogledne datoteke nisu pronađene na poslužitelju.")
    elif uploaded_e2k:
        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        if uploaded_dxf:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
            tmp.write(uploaded_dxf.getvalue())
            tmp.close()
            dxf_path = tmp.name
            has_data = True
            is_pdf_mode = False
        elif uploaded_drawing:
            # User uploaded ETABS model + PDF project document instead of CAD!
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
                st.session_state["demo_choice_key"] = "school"
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
            _render_instructions()
        return

    # ── Run Analysis ─────────────────────────────────────────
    with st.spinner("Automatska obrada modela i projektne dokumentacije u tijeku…"):
        try:
            etabs_data = parse_e2k(io.StringIO(e2k_content), cfg)
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
                df_dxf = parse_dxf(dxf_path, cfg)
                df_res = validate(etabs_data, df_dxf, cfg)
        except Exception as err:
            st.error(f"Greška tijekom obrade modela: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except: pass

    # ── Multi-Story / Story Filter ────────────────────────────
    stories = etabs_data.get("stories", [])
    if not stories:
        stories = [{"name": "Prizemlje", "z_bottom": 0.0, "z_top": 4.0, "height": 4.0, "elevation": 4.0}]

    story_opts = [f"🏢 {s['name']} (Z = {s['z_bottom']:.2f} – {s['z_top']:.2f} m)" for s in stories]
    story_opts.append("🌐 Sve etaže (Cijela zgrada)")

    c_story, c_info = st.columns([2.4, 2.6])
    with c_story:
        choice_story = st.selectbox(
            "📍 Odabir etaže za prikaz tlocrta i kontrolu:",
            story_opts,
            index=0,
            key="active_story_filter"
        )
    with c_info:
        st.caption("ℹ️ *Arhitektonski nacrti prikazuju pojedinačne etaže. Odabirom etaže tlocrt i tablice prikazuju isključivo elemente tog kata.*")

    active_story_name = None
    chosen_z = None
    selected_story_data = None

    if not choice_story.startswith("🌐"):
        sel_idx = story_opts.index(choice_story)
        selected_story_data = stories[sel_idx]
        active_story_name = selected_story_data["name"]
        chosen_z = selected_story_data["z_top"]

        if "story" in df_res.columns:
            df_eval = df_res[
                (df_res["story"] == active_story_name) |
                (df_res["status"] == Status.DXF_ONLY)
            ].copy()
        else:
            z_bot = selected_story_data["z_bottom"] - 0.20
            z_top = selected_story_data["z_top"] + 0.20
            df_eval = df_res[
                ((df_res["etabs_z"] >= z_bot) & (df_res["etabs_z"] <= z_top)) |
                (df_res["status"] == Status.DXF_ONLY)
            ].copy()
        df_eval.attrs = dict(df_res.attrs)
    else:
        df_eval = df_res.copy()
        df_eval.attrs = dict(df_res.attrs)

    # ── KPI Strip ─────────────────────────────────────────────
    _kpi_strip(df_eval, is_pdf_mode=is_pdf_mode, etabs_data=etabs_data)

    # ── Legend / Color Explanations ───────────────────────────
    if is_pdf_mode:
        st.markdown("""
        <div class="legend-banner">
          <span style="font-weight: 700; color: #0f172a;">Način rada:</span>
          <span>📑 <b>Vizualna revizija uz PDF elaborat</b> — Usporedite geometriju i dimenzije modela s nacrtom etaže u desnom prozoru (Tab 1).</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="legend-banner">
          <span style="font-weight: 700; color: #0f172a;">Tumač statusa:</span>
          <span class="legend-item"><span class="dot-green">● Zeleno</span> Usklađeno (lokacija i presjek odgovaraju nacrtu)</span>
          <span class="legend-item"><span class="dot-amber">● Narančasto</span> Odstupanje u dimenzijama presjeka</span>
          <span class="legend-item"><span class="dot-red">● Crveno</span> Samo u ETABS-u (nema na CAD nacrtu)</span>
          <span class="legend-item"><span class="dot-blue">● Plavo</span> Samo u CAD-u (nedostaje u numeričkom modelu)</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Inženjerska kontrola modela (Sanity Alerts) ───────────
    alerts = df_res.attrs.get("sanity_alerts", [])
    if alerts:
        seen_alerts = set()
        dedup_alerts = []
        for a in alerts:
            k = (a.get("category"), a.get("element"), a.get("issue"))
            if k not in seen_alerts:
                seen_alerts.add(k)
                dedup_alerts.append(a)

        err_count = sum(1 for a in dedup_alerts if a.get("severity") == "ERROR")
        warn_count = sum(1 for a in dedup_alerts if a.get("severity") == "WARNING")

        if err_count > 0 or warn_count > 0:
            exp_title = f"⚠️ Inženjerska kontrola modela ({err_count} upozorenja, {warn_count} napomena)" if err_count > 0 else f"ℹ️ Inženjerske napomene za model ({warn_count})"
            with st.expander(exp_title, expanded=False):
                for a in dedup_alerts:
                    icon = "🔴" if a.get("severity") == "ERROR" else ("⚠️" if a.get("severity") == "WARNING" else "ℹ️")
                    st.markdown(f"{icon} **[{a.get('category','')}] {a.get('element','')}**: {a.get('issue','')}")

    # ── Tab Navigation: Clear, descriptive titles ─────────────
    t_map, t_audit, t_geo, t_mat, t_sup, t_pdf, t_guide = st.tabs([
        "🗺️ 1. Vizualni model (2D/3D)",
        "🎓 2. Nastavna & Studentska revizija (1–27)",
        "📊 3. Tablica odstupanja",
        "🧪 4. Materijali & Opterećenja",
        "🧱 5. Oslonci & Zglobovi",
        "📄 6. Službeni PDF Elaborat",
        "📖 7. Upute za rad & Vodič",
    ])

    # ── TAB 1: Visual Model & Reference Drawing ───────────────
    with t_map:
        if active_story_name and selected_story_data:
            st.success(f"🏢 **Aktivna etaža: {active_story_name} (Z = {selected_story_data['z_bottom']:.2f} do {selected_story_data['z_top']:.2f} m)** | Tlocrt prikazuje isključivo nosive elemente ove etaže. Bijela crtkana linija označava proračunsku os zida (od sredine do sredine zida).")
        else:
            st.info("📐 **Prikaz cjelokupnog modela (Sve etaže):** Za izolirani pregled pojedinog kata, odaberite željenu etažu u gornjem izborniku.")

        has_drawing = uploaded_drawing is not None

        if has_drawing:
            view_mode = st.radio(
                "Način prikaza:",
                ["📐 Usporedni prikaz (Model + Referentni nacrt)", "🏢 Samo numerički model", "📑 Samo referentni nacrt"],
                horizontal=True,
                key="drawing_view_mode",
            )

            if view_mode.startswith("📐"):
                col_m, col_d = st.columns(2, gap="medium")
                with col_m:
                    st.markdown("##### Numerički model (ETABS)")
                    sub_m = st.radio("Tip prikaza:", ["2D Tlocrt", "3D Wireframe"], horizontal=True, key="sub_m1")
                    if sub_m == "3D Wireframe":
                        st.plotly_chart(_fig_3d(df_res, etabs_data, active_story_name=active_story_name), use_container_width=True)
                    else:
                        st.plotly_chart(_fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)
                with col_d:
                    st.markdown("##### Referentni nacrt")
                    _render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name)

            elif view_mode.startswith("🏢"):
                sub_m = st.radio("Tip prikaza:", ["2D Tlocrt s osima", "3D Wireframe"], horizontal=True, key="sub_m2")
                if sub_m.startswith("3D"):
                    st.plotly_chart(_fig_3d(df_res, etabs_data, active_story_name=active_story_name), use_container_width=True)
                else:
                    st.plotly_chart(_fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)

            else:
                _render_drawing(uploaded_drawing, active_story_z=chosen_z, active_story_name=active_story_name)

        else:
            sub_col, col_mode_opt = st.columns([1.2, 1.8])
            with sub_col:
                mode = st.radio("Tip prikaza modela:", ["2D Tlocrt s osima", "3D Wireframe model"], horizontal=True, key="mode_full")

            if mode.startswith("3D"):
                with col_mode_opt:
                    c1_opt, c2_opt = st.columns(2)
                    with c1_opt:
                        c_mode = st.radio(
                            "Bojanje 3D modela:",
                            ["🟣 ETABS originalni prikaz (Magenta)", "🔍 Kontrola usklađenosti (Status)"],
                            horizontal=True,
                            key="color_mode_3d"
                        )
                    with c2_opt:
                        iso_3d = st.checkbox(f"Izoliraj {active_story_name}" if active_story_name else "Izoliraj etažu", value=False, key="iso_3d_chk")
                st.plotly_chart(_fig_3d(df_res, etabs_data, etabs_color_mode=c_mode.startswith("🟣"), active_story_name=active_story_name if iso_3d else None), use_container_width=True)
            else:
                with col_mode_opt:
                    st.caption("💡 Za usporedni prikaz nacrta uz model, priložite PDF ili sliku u bočnoj traci (Referentni nacrt).")
                st.plotly_chart(_fig_2d(df_eval, etabs_data, active_story_name=active_story_name), use_container_width=True)

    # ── TAB 2: Studentska & Nastavna revizijska lista ───────────
    with t_audit:
        st.markdown("#### 🎓 Nastavne napomene za pregled modela (Kontrolni list 1–27)")
        st.caption("Automatizirana kontrola numeričkog ETABS (.e2k) modela prema službenom nastavnom zadatku za studente građevinarstva.")

        audit_results = run_curriculum_audit(etabs_data)

        n_pass = sum(1 for a in audit_results if a["status"] == "PASS")
        n_warn = sum(1 for a in audit_results if a["status"] == "WARNING")
        n_fail = sum(1 for a in audit_results if a["status"] == "FAIL")
        n_info = sum(1 for a in audit_results if a["status"] == "INFO")

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("🟢 Usklađene točke", f"{n_pass} / {len(audit_results)}")
        c_m2.metric("🟡 Upozorenja", n_warn)
        c_m3.metric("🔴 Kritična odstupanja", n_fail)
        c_m4.metric("ℹ️ Smjernice", n_info)

        st.markdown("<hr style='margin: 16px 0;'>", unsafe_allow_html=True)

        c_filter, _ = st.columns([2.0, 3.0])
        with c_filter:
            flt_status = st.selectbox(
                "Prikaz točaka kontrolnog lista:",
                ["Sve točke (1–27)", "Samo upozorenja i kritična odstupanja (⚠️/🔴)", "Samo usklađene točke (🟢)"],
                key="audit_filter_status"
            )

        items_to_show = audit_results
        if "upozorenja" in flt_status.lower():
            items_to_show = [a for a in audit_results if a["status"] in ("WARNING", "FAIL")]
        elif "usklađene" in flt_status.lower():
            items_to_show = [a for a in audit_results if a["status"] == "PASS"]

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

            st.markdown(f"""
            <div style="background: white; border: 1px solid #e2e8f0; border-left: 5px solid {badge_col}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 1.05rem; font-weight: 700; color: #0f172a;">{icon} {item['title']}</span>
                <span style="background: {badge_bg}; color: {badge_col}; font-size: 0.78rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">{badge_txt}</span>
              </div>
              <div style="font-size: 0.92rem; color: #1e293b; margin-bottom: 8px; background: #f8fafc; padding: 10px 12px; border-radius: 6px; border: 1px dashed #cbd5e1;">
                <strong>🔍 Nalaz u modelu:</strong> {item['finding']}
              </div>
              <div style="font-size: 0.85rem; color: #64748b; line-height: 1.4;">
                <strong>📖 Nastavno pravilo:</strong> <em>{item['rule']}</em>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB 3: Deviations & Geometry Table ────────────────────
    with t_geo:
        if is_pdf_mode:
            st.markdown("##### 📋 Kontrolni inventar elemenata modela za provjeru s PDF-om")
            st.caption("Popis nosivih elemenata po etažama s točnim dimenzijama presjeka i materijalima iz ETABS-a.")
        else:
            st.markdown("##### Detaljna usporedba dimenzija i položaja elemenata")

        f1, f2, f3 = st.columns([1.5, 1.5, 2])
        dfd = df_eval.copy()

        with f1:
            if is_pdf_mode:
                st.info("ℹ️ Način kontrole: PDF elaborat")
            else:
                st_f = st.selectbox("Filtriraj po statusu:", ["Svi statusi"] + [s.value for s in Status], key="geo_status")
                if st_f != "Svi statusi":
                    dfd = dfd[dfd["status"].astype(str) == st_f]

        with f2:
            ty_f = st.selectbox("Filtriraj po tipu:", ["Svi tipovi"] + sorted(df_eval["element_type"].unique()), key="geo_type")
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
        tbl = _safe_df(dfd[vcols], {
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

    # ── TAB 3: Materials & Loads ──────────────────────────────
    with t_mat:
        mc, lc = st.columns(2, gap="large")

        with mc:
            st.markdown("##### 🧪 Klase materijala (Beton / Čelik)")
            mats = pd.DataFrame(df_res.attrs.get("materials", []))
            if not mats.empty:
                st.dataframe(
                    _safe_df(mats, {"E_gpa": "{:.1f}", "fc_mpa": "{:.1f}", "fy_mpa": "{:.1f}", "fu_mpa": "{:.1f}"}),
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
                    _safe_df(pats, {"self_weight_mult": "{:.2f}"}),
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
                st.dataframe(_safe_df(aloads), use_container_width=True, hide_index=True)

    # ── TAB 4: Supports & Hinges ──────────────────────────────
    with t_sup:
        sc, hc = st.columns(2, gap="large")

        with sc:
            st.markdown("##### 🧱 Temeljni oslonci (Rubni uvjeti)")
            rests = etabs_data.get("restraints", pd.DataFrame()) if etabs_data else pd.DataFrame(df_res.attrs.get("restraints", []))
            if not rests.empty and "joint_name" in rests.columns:
                rcols = [c for c in ["joint_name", "x", "y", "z", "restraint_type", "is_supported"] if c in rests.columns]
                st.dataframe(
                    _safe_df(rests[rcols], {"x": "{:.2f}", "y": "{:.2f}", "z": "{:.2f}"}),
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
                    _safe_df(hinges[hcols], {"rel_dist": "{:.2f}"}),
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

    # ── TAB 5: PDF Elaborat ───────────────────────────────────
    with t_pdf:
        st.markdown("""
        <div class="dl-card">
          <div style="font-size: 38px; margin-bottom: 8px;">📄</div>
          <h3 style="margin: 0 0 6px 0; color: #0f172a; font-weight: 800;">Službeni Revizijski Elaborat</h3>
          <p style="margin: 0 auto 12px auto; color: #64748b; font-size: 13px; max-width: 650px; line-height: 1.5;">
            Ova stranica služi za <b>automatsko generiranje i preuzimanje službenog inženjerskog elaborata</b> (A4 Landscape PDF).
            Elaborat služi kao službena tehnička dokumentacija za investitora, glavnog projektanta, revidenta ili tehnički arhiv.
          </p>
        </div>
        """, unsafe_allow_html=True)

        i1, i2, i3 = st.columns(3)
        with i1:
            st.info("📋 **1. Naslovnica & Parametri**\n\nPodaci o projektu, inženjerske tolerancije (±50 mm), datum revizije i globalni sažetak elemenata.")
        with i2:
            st.info("📐 **2. Matrica geometrije (Str. 1–6)**\n\nSvih 110 elemenata (zidovi W108–W581, ploča F1), točne koordinate centroida, debljine i materijali.")
        with i3:
            st.info("🧱 **3. Materijali & Opterećenja (Str. 7)**\n\nVerifikacija svih 6 materijala, modula elastičnosti i potpuna revizija ravnoteže opterećenja (G, VT, Q, Potres).")

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
                st.caption("ℹ️ *Ispod je izravan prikaz generiranog elaborata. Identičan sadržaj nalazi se u preuzetom PDF dokumentu:*")
                st.components.v1.html(html_content, height=550, scrolling=True)

    # ── TAB 6: User Guide & Instructions ──────────────────────
    with t_guide:
        _render_instructions()


if __name__ == "__main__":
    main()
