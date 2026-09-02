"""
streamlit_app.py
----------------
Web Application for Automated Structural ETABS v23 ↔ DXF Cross-Validation.
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

# Page configuration
st.set_page_config(
    page_title="ETABS ↔ CAD Kontrola Modela",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DXF = os.path.join(SCRIPT_DIR, "sample_building.dxf")
SAMPLE_E2K = os.path.join(SCRIPT_DIR, "sample_building.e2k")


def _render_sidebar():
    st.sidebar.title("🏗️ ETABS ↔ CAD Kontrola")
    st.sidebar.caption("Automatizirana provjera numeričkih modela konstrukcija prema izvedbenim nacrtima.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 Ulazni podaci")

    use_sample = st.sidebar.checkbox("🧪 Učitaj ogledni primjer (Demo)", value=False)

    uploaded_dxf = None
    uploaded_e2k = None

    if not use_sample:
        uploaded_dxf = st.sidebar.file_uploader(
            "1. Odaberi 2D CAD nacrt (.dxf)",
            type=["dxf"],
            help="Tlocrtni nacrt konstrukcije s kotama i elementima.",
        )
        uploaded_e2k = st.sidebar.file_uploader(
            "2. Odaberi ETABS model (.e2k)",
            type=["e2k", "$et", "txt"],
            help="Tekstualni izvoz modela iz ETABS-a (File -> Export -> ETABS .e2k Text File...).",
        )

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Postavke i Mjerilo")

    scale_label = st.sidebar.selectbox(
        "Mjerne jedinice nacrta (CAD):",
        options=["Centimetri (1 unit = 1 cm)", "Milimetri (1 unit = 1 mm)", "Metri (1 unit = 1 m)"],
        index=0,
    )
    scale_map = {
        "Centimetri (1 unit = 1 cm)": 0.01,
        "Milimetri (1 unit = 1 mm)": 0.001,
        "Metri (1 unit = 1 m)": 1.0,
    }
    unit_scale = scale_map[scale_label]

    with st.sidebar.expander("Napredne tolerancije"):
        tol_frame = st.slider("Tolerancija stupova/greda (m)", 0.05, 0.50, 0.15, 0.01)
        tol_area = st.slider("Tolerancija zidova/ploča (m)", 0.10, 1.00, 0.30, 0.05)
        tol_sec = st.slider("Tolerancija presjeka (mm)", 1.0, 30.0, 5.0, 1.0)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Opseg kontrole")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        chk_cols = st.checkbox("Stupovi", value=True)
        chk_beams = st.checkbox("Grede", value=True)
        chk_walls = st.checkbox("Zidovi", value=True)
        chk_slabs = st.checkbox("Ploče", value=True)
    with col2:
        chk_materials = st.checkbox("🧪 Materijali", value=True)
        chk_loads = st.checkbox("⚖️ Opterećenja", value=True)
        chk_restraints = st.checkbox("🧱 Oslonci", value=True)
        chk_hinges = st.checkbox("🔴 Zglobovi", value=True)

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
        audit_materials=chk_materials,
        audit_loads=chk_loads,
        audit_restraints=chk_restraints,
        report_hinges=chk_hinges,
    )

    return use_sample, uploaded_dxf, uploaded_e2k, cfg


def _render_plotly_floorplan(df_res: pd.DataFrame, df_dxf: pd.DataFrame):
    """Render interactive 2D floor plan overlay using Plotly."""
    fig = go.Figure()

    # Color map for statuses
    color_map = {
        Status.MATCH: "#198754",           # Green
        Status.SECTION_MISMATCH: "#fd7e14", # Orange
        Status.ETABS_ONLY: "#dc3545",       # Red
        Status.DXF_ONLY: "#0dcaf0",         # Cyan / Blue
    }

    # Plot matched / mismatched / ETABS elements
    for st_val, col in color_map.items():
        sub = df_res[df_res["status"] == st_val]
        if sub.empty:
            continue

        # Points (columns and area centroids)
        pts_sub = sub[sub["element_type"].isin(["column", "slab", "wall"])]
        if not pts_sub.empty:
            # Use etabs coords if present, else dxf coords
            xs = [r.get("etabs_x") if pd.notna(r.get("etabs_x")) else r.get("dxf_x") for _, r in pts_sub.iterrows()]
            ys = [r.get("etabs_y") if pd.notna(r.get("etabs_y")) else r.get("dxf_y") for _, r in pts_sub.iterrows()]
            texts = []
            for _, r in pts_sub.iterrows():
                name = r.get("etabs_name") or "CAD Polyline"
                et = r.get("element_type", "")
                ew, eh = r.get("etabs_w_mm"), r.get("etabs_h_mm")
                dw, dh = r.get("dxf_dim1_mm"), r.get("dxf_dim2_mm")
                notes = r.get("notes") or ""
                texts.append(
                    f"<b>{name}</b> ({et})<br>"
                    f"Status: {st_val.value}<br>"
                    f"ETABS Presjek: {ew or '—'}x{eh or '—'} mm<br>"
                    f"CAD Kota: {dw or '—'}x{dh or '—'} mm<br>"
                    f"Koordinate: ({xs[-1]:.2f}, {ys[-1]:.2f})<br>"
                    f"Napomena: {notes}"
                )

            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers",
                marker=dict(size=14, color=col, line=dict(width=1.5, color="#333333")),
                name=f"{st_val.value} ({len(pts_sub)})",
                hovertext=texts,
                hoverinfo="text",
            ))

        # Beams (lines)
        beams_sub = sub[sub["element_type"] == "beam"]
        for _, br in beams_sub.iterrows():
            bx = br.get("etabs_x") if pd.notna(br.get("etabs_x")) else br.get("dxf_x")
            by = br.get("etabs_y") if pd.notna(br.get("etabs_y")) else br.get("dxf_y")
            bname = br.get("etabs_name") or "CAD Beam"
            fig.add_trace(go.Scatter(
                x=[bx], y=[by],
                mode="markers",
                marker=dict(symbol="diamond", size=15, color=col, line=dict(width=1.5, color="#222")),
                name=f"Greda: {bname}",
                hovertext=f"<b>{bname}</b> (Greda)<br>Status: {st_val.value}<br>Presjek: {br.get('etabs_w_mm','—')}x{br.get('etabs_h_mm','—')} mm",
                hoverinfo="text",
                showlegend=False,
            ))

    fig.update_layout(
        title="Tlocrtni raspored elemenata i status usklađenosti (2D Model View)",
        xaxis_title="Global X (m)",
        yaxis_title="Global Y (m)",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=550,
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def main():
    use_sample, uploaded_dxf, uploaded_e2k, cfg = _render_sidebar()

    st.title("🏢 ETABS v23 ↔ CAD/DXF Kontrola Numeričkih Modela")
    st.markdown(
        "Automatsko unakrsno ispitivanje numeričkih modela konstrukcija prema izvedbenoj 2D dokumentaciji. "
        "Provjerava **Geometriju, Poprečne presjeke, Materijale, Opterećenja, Oslonce i Plastične zglobove**."
    )

    has_data = False
    dxf_path = None
    e2k_content = None

    if use_sample:
        if os.path.exists(SAMPLE_DXF) and os.path.exists(SAMPLE_E2K):
            dxf_path = SAMPLE_DXF
            with open(SAMPLE_E2K, "r", encoding="utf-8") as f:
                e2k_content = f.read()
            has_data = True
            st.info("🧪 Učitan je ogledni primjer višestambene zgrade (`sample_building.dxf` + `sample_building.e2k`).")
        else:
            st.error("Ogledne datoteke nisu pronađene na serveru.")
    elif uploaded_dxf and uploaded_e2k:
        # Save DXF to temporary file
        t_dxf = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
        t_dxf.write(uploaded_dxf.getvalue())
        t_dxf.close()
        dxf_path = t_dxf.name

        e2k_content = uploaded_e2k.getvalue().decode("utf-8", errors="replace")
        has_data = True

    if not has_data:
        st.markdown("---")
        st.subheader("📋 Kako pripremiti i pokrenuti kontrolu:")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1. Izvoz iz ETABS-a (3 sekunde)")
            st.write("U programu ETABS v23 odaberite izbornik:")
            st.code("File ➔ Export ➔ ETABS .e2k Text File...")
            st.caption("Datoteka u čistom tekstu sadrži geometriju, materijale, opterećenja i sve presjeke.")
        with c2:
            st.markdown("#### 2. Učitaj nacrt i model")
            st.write("U lijevom izborniku priložite:")
            st.markdown("- **2D CAD nacrt** (`.dxf`)\n- **ETABS model** (`.e2k`)")
            st.caption("Ili jednostavno označite '🧪 Učitaj ogledni primjer' za trenutni test.")
        with c3:
            st.markdown("#### 3. Trenutni uvid i PDF")
            st.write("Aplikacija automatski provodi analizu i generira:")
            st.markdown("- Interaktivni 2D tlocrtni prikaz\n- Usporedne tablice odstupanja\n- Službeni elaborat u **PDF formatu**.")

        st.markdown("---")
        st.info("👈 Započnite odabirom datoteka u bočnoj traci s lijeve strane!")
        return

    # Run processing
    with st.spinner("⏳ Parsiranje nacrta (DXF) i modela (ETABS .e2k)..."):
        try:
            df_dxf = parse_dxf(dxf_path, cfg)
            etabs_data = parse_e2k(io.StringIO(e2k_content), cfg)
            df_res = validate(etabs_data, df_dxf, cfg)
        except Exception as err:
            st.error(f"Došlo je do pogreške pri obradi: {err}")
            return
        finally:
            if uploaded_dxf and dxf_path and os.path.exists(dxf_path):
                try: os.unlink(dxf_path)
                except Exception: pass

    # Summary KPI Cards
    counts = df_res["status"].value_counts()
    n_match = counts.get(Status.MATCH, 0)
    n_mismatch = counts.get(Status.SECTION_MISMATCH, 0)
    n_etabs_only = counts.get(Status.ETABS_ONLY, 0)
    n_dxf_only = counts.get(Status.DXF_ONLY, 0)
    n_total = len(df_res)

    st.markdown("### 📊 Sažetak kontrole modela")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Ukupno elemenata", n_total)
    kpi2.metric("🟢 Usklađeno (Match)", n_match, delta=f"{round(n_match/max(n_total,1)*100)}%")
    kpi3.metric("🟡 Odstupanje presjeka", n_mismatch, delta="- Oprez" if n_mismatch > 0 else None, delta_color="inverse")
    kpi4.metric("🔴 Samo u ETABS-u", n_etabs_only, delta="- Višak u modelu" if n_etabs_only > 0 else None, delta_color="inverse")
    kpi5.metric("🔵 Samo u CAD-u", n_dxf_only, delta="- Nedostaje u modelu" if n_dxf_only > 0 else None, delta_color="inverse")

    # Sanity Alerts Banner
    sanity_alerts = df_res.attrs.get("sanity_alerts", [])
    if sanity_alerts:
        st.markdown("---")
        with st.expander(f"⚠️ Upozorenja statičke ispravnosti modela ({len(sanity_alerts)} detektirano)", expanded=True):
            for a in sanity_alerts:
                sev = a.get("severity", "WARNING")
                cat = a.get("category", "")
                elem = a.get("element", "")
                issue = a.get("issue", "")
                if sev == "ERROR":
                    st.error(f"**[{cat}] {elem}**: {issue}")
                else:
                    st.warning(f"**[{cat}] {elem}**: {issue}")

    # Plotly Visualizer
    st.markdown("---")
    st.plotly_chart(_render_plotly_floorplan(df_res, df_dxf), use_container_width=True)

    # Tabbed Deep-Dive Tables
    st.markdown("---")
    tab_geo, tab_mat, tab_load, tab_rest, tab_hinge = st.tabs([
        "📐 1. Geometrija i presjeci",
        "🧪 2. Materijali",
        "⚖️ 3. Opterećenja",
        "🧱 4. Oslonci / Ležajevi",
        "🔴 5. Plastični zglobovi",
    ])

    # Tab 1: Geometry & Sections
    with tab_geo:
        st.subheader("Unakrsna provjera geometrije i dimenzija presjeka")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            st_filter = st.selectbox("Filtriraj po statusu:", ["Sve"] + [s.value for s in Status])
        with f_col2:
            type_filter = st.selectbox("Filtriraj po tipu:", ["Sve"] + sorted(df_res["element_type"].unique().tolist()))
        with f_col3:
            txt_search = st.text_input("Pretraži po nazivu / oznaci:", "")

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
        st.dataframe(
            df_disp[view_cols],
            use_container_width=True,
            column_config={
                "status": st.column_config.TextColumn("Status"),
                "element_type": st.column_config.TextColumn("Tip"),
                "etabs_name": st.column_config.TextColumn("ETABS ID"),
                "etabs_section": st.column_config.TextColumn("ETABS Presjek"),
                "etabs_w_mm": st.column_config.NumberColumn("b (mm)", format="%.0f"),
                "etabs_h_mm": st.column_config.NumberColumn("h (mm)", format="%.0f"),
                "dxf_dim_text": st.column_config.TextColumn("CAD Oznaka"),
                "dxf_dim1_mm": st.column_config.NumberColumn("CAD b (mm)", format="%.0f"),
                "dxf_dim2_mm": st.column_config.NumberColumn("CAD h (mm)", format="%.0f"),
                "xy_dist_m": st.column_config.NumberColumn("Odmicanje (m)", format="%.2f"),
                "notes": st.column_config.TextColumn("Napomene i Odstupanja"),
            }
        )

    # Tab 2: Materials
    with tab_mat:
        st.subheader("🧪 Kontrola definicija materijala (klase betona i čelika)")
        df_mats = pd.DataFrame(df_res.attrs.get("materials", []))
        if not df_mats.empty and "name" in df_mats.columns:
            st.dataframe(
                df_mats,
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Naziv materijala"),
                    "type": st.column_config.TextColumn("Kategorija"),
                    "E_gpa": st.column_config.NumberColumn("Modul elastičnosti E (GPa)", format="%.1f"),
                    "fc_mpa": st.column_config.NumberColumn("Tlačna čvrstoća fc (MPa)", format="%.1f"),
                    "fy_mpa": st.column_config.NumberColumn("Granica popuštanja fy (MPa)", format="%.1f"),
                    "fu_mpa": st.column_config.NumberColumn("Vlačna čvrstoća fu (MPa)", format="%.1f"),
                }
            )
        else:
            st.info("Nema definiranih podataka o materijalima u ovom modelu.")

    # Tab 3: Loads
    with tab_load:
        st.subheader("⚖️ Kontrola uzoraka i faktora vlastite težine")
        df_pats = pd.DataFrame(df_res.attrs.get("load_patterns", []))
        if not df_pats.empty and "name" in df_pats.columns:
            st.write("**Uzorci opterećenja (*Static Load Patterns*):**")
            st.dataframe(
                df_pats,
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Uzorak"),
                    "type": st.column_config.TextColumn("Tip"),
                    "self_weight_mult": st.column_config.NumberColumn("Faktor vlastite težine (Self-Weight Mult)", format="%.2f"),
                }
            )

        df_aloads = pd.DataFrame(df_res.attrs.get("area_loads", []))
        if not df_aloads.empty:
            st.write("**Zadana plošna opterećenja na pločama ($kN/m^2$):**")
            st.dataframe(df_aloads, use_container_width=True)

    # Tab 4: Restraints
    with tab_rest:
        st.subheader("🧱 Rubni uvjeti temelja i oslonci (*Supports & Boundary Conditions*)")
        df_rest = pd.DataFrame(df_res.attrs.get("restraints", []))
        if not df_rest.empty and "joint_name" in df_rest.columns:
            st.dataframe(
                df_rest,
                use_container_width=True,
                column_config={
                    "joint_name": st.column_config.TextColumn("Čvor (Joint ID)"),
                    "x": st.column_config.NumberColumn("X (m)", format="%.2f"),
                    "y": st.column_config.NumberColumn("Y (m)", format="%.2f"),
                    "z": st.column_config.NumberColumn("Z (m)", format="%.2f"),
                    "restraint_type": st.column_config.TextColumn("Tip ležaja"),
                    "is_supported": st.column_config.CheckboxColumn("Poduprt"),
                }
            )
        else:
            st.info("Nema definiranih rubnih uvjeta u prizemlju.")

    # Tab 5: Plastic Hinges
    with tab_hinge:
        st.subheader("🔴 Plastični zglobovi i nelinearna svojstva (*Plastic Hinges*)")
        df_hinges = etabs_data.get("hinges", pd.DataFrame())
        if not df_hinges.empty and "frame_name" in df_hinges.columns:
            st.dataframe(
                df_hinges,
                use_container_width=True,
                column_config={
                    "frame_name": st.column_config.TextColumn("Element (Frame)"),
                    "hinge_prop": st.column_config.TextColumn("Tip zgloba (Property)"),
                    "rel_dist": st.column_config.NumberColumn("Relativna lokacija (L)", format="%.2f"),
                    "dof": st.column_config.TextColumn("Stupanj slobode"),
                }
            )
        else:
            st.info("U ovom modelu nisu dodijeljeni nelinearni plastični zglobovi.")

    # Download Reports Section
    st.markdown("---")
    st.subheader("📥 Preuzimanje službenih izvještaja")
    d_col1, d_col2 = st.columns(2)

    with d_col1:
        # Generate PDF in tempfile and offer download
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_pdf:
            pdf_path = f_pdf.name
        try:
            generate_pdf(df_res, pdf_path, cfg)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="📄 Preuzmi Službeni PDF Elaborat (A4 Landscape)",
                data=pdf_bytes,
                file_name="ETABS_DXF_Elaborat_Kontrole.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        finally:
            if os.path.exists(pdf_path):
                try: os.unlink(pdf_path)
                except Exception: pass

    with d_col2:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f_html:
            html_path = f_html.name
        try:
            html_content = generate_html(df_res, html_path, cfg)
            st.download_button(
                label="🌐 Preuzmi Interaktivni HTML Izvještaj",
                data=html_content.encode("utf-8"),
                file_name="ETABS_DXF_Kontrola.html",
                mime="text/html",
                use_container_width=True,
            )
        finally:
            if os.path.exists(html_path):
                try: os.unlink(html_path)
                except Exception: pass


if __name__ == "__main__":
    main()
