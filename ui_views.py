"""
ui_views.py
-----------
Interactive 2D & 3D Plotly visualizations, universal drawing viewport (PDF / CAD / Images),
and engineering documentation renderer.
"""

import os
import math
import tempfile
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from phase3_validation import Status


# ---------------------------------------------------------------------------
# Cached PDF helpers — a Streamlit rerun happens on every interaction, so
# re-opening the PDF and re-rendering the page each time makes the drawing
# viewer feel slow. Cache the page render keyed on (bytes, page, dpi).
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=64)
def _pdf_meta(raw: bytes):
    """Return (num_pages, toc_dict) for a PDF given as raw bytes."""
    import fitz
    doc = fitz.open(stream=raw, filetype="pdf")
    num_pages = len(doc)
    toc = doc.get_toc()
    toc_dict = {item[2]: item[1] for item in toc if len(item) >= 3} if toc else {}
    doc.close()
    return num_pages, toc_dict


@st.cache_data(show_spinner=False, max_entries=128)
def _pdf_page_png(raw: bytes, page_idx: int, dpi: int) -> bytes:
    """Render one PDF page to PNG bytes (cached per page + dpi)."""
    import fitz
    doc = fitz.open(stream=raw, filetype="pdf")
    idx = min(max(int(page_idx), 0), len(doc) - 1)
    pix = doc[idx].get_pixmap(dpi=int(dpi), alpha=False)
    png = pix.tobytes("png")
    doc.close()
    return png


def render_drawing(
    uploaded_drawing,
    active_story_z: float = None,
    active_story_name: str = None,
    demo_sheet_map: dict = None,
):
    """
    Renders reference architectural / structural drawings from PDF or image formats.
    Universal multi-page PDF viewer with:
      - Dynamic Table of Contents (TOC) extraction
      - Clean previous/next page navigation
      - High DPI display controls (120, 160, 200 DPI)
      - Image auto-scaling
    """
    if uploaded_drawing is None:
        st.info("Nacrt nije priložen. Učitajte PDF elaborat ili DWG/DXF nacrt u bočnoj traci.")
        return

    if isinstance(uploaded_drawing, str):
        file_name = os.path.basename(uploaded_drawing)
        with open(uploaded_drawing, "rb") as f:
            raw = f.read()
    else:
        file_name = uploaded_drawing.name
        raw = uploaded_drawing.getvalue()

    name_lower = file_name.lower()

    try:
        if name_lower.endswith(".pdf"):
            import fitz  # PyMuPDF
            num_pages, toc_dict = _pdf_meta(raw)  # cached: no re-open per rerun
            if num_pages == 0:
                st.warning("Priloženi PDF dokument ne sadrži stranice.")
                return
            if st.session_state.get("_active_pdf_filename") != file_name:
                st.session_state["_active_pdf_filename"] = file_name
                st.session_state["active_pdf_page"] = 1
                st.session_state["_last_synced_story"] = None
            page_labels_dict = {}

            for p in range(1, num_pages + 1):
                if demo_sheet_map and p in demo_sheet_map:
                    lbl = demo_sheet_map[p].replace("📄 ", "").replace("📐 ", "").strip()
                    if not lbl.lower().startswith("str"):
                        lbl = f"Str. {p}: {lbl}"
                    page_labels_dict[p] = lbl
                elif p in toc_dict and str(toc_dict[p]).strip():
                    page_labels_dict[p] = f"Str. {p}: {str(toc_dict[p]).strip()}"
                else:
                    page_labels_dict[p] = f"Stranica {p} od {num_pages}"

            if active_story_name and st.session_state.get("_last_synced_story") != active_story_name:
                st.session_state["_last_synced_story"] = active_story_name
                s_lower = str(active_story_name).lower().strip()
                target_pg = None

                stross_story_map = {
                    "story1": 14,
                    "story2": 15,
                    "story3": 16,
                    "story4": 17,
                }
                if demo_sheet_map and s_lower in stross_story_map and stross_story_map[s_lower] <= num_pages:
                    target_pg = stross_story_map[s_lower]
                elif demo_sheet_map:
                    for p_num, p_title in demo_sheet_map.items():
                        t_low = p_title.lower()
                        if "priz" in s_lower and "priz" in t_low:
                            target_pg = p_num
                            break
                        elif ("1" in s_lower or "prvi" in s_lower) and ("1. kat" in t_low or "i. kat" in t_low):
                            target_pg = p_num
                            break
                        elif ("2" in s_lower or "drugi" in s_lower) and ("2. kat" in t_low or "ii. kat" in t_low):
                            target_pg = p_num
                            break
                        elif ("3" in s_lower or "treci" in s_lower) and ("3. kat" in t_low or "iii. kat" in t_low):
                            target_pg = p_num
                            break
                        elif "krov" in s_lower and "krov" in t_low:
                            target_pg = p_num
                            break
                elif toc_dict:
                    for p_num, p_title in toc_dict.items():
                        t_low = str(p_title).lower()
                        if s_lower in t_low or any(w in t_low for w in s_lower.split() if len(w) > 3):
                            target_pg = p_num
                            break

                if target_pg and 1 <= target_pg <= num_pages:
                    st.session_state["active_pdf_page"] = target_pg

            cur_page = st.session_state.get("active_pdf_page", 1)
            if not isinstance(cur_page, int) or cur_page < 1 or cur_page > num_pages:
                st.session_state["active_pdf_page"] = 1

            is_dark_doc = (st.session_state.get("app_theme") == "Tamna") if hasattr(st, "session_state") else False
            doc_title_col = "#F0F6FC" if is_dark_doc else "#111827"
            st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: {doc_title_col}; margin-bottom: 6px;'>Nacrt: {file_name} ({num_pages} str.)</div>", unsafe_allow_html=True)

            # Quick navigation bar
            ctrl1, ctrl2, ctrl3 = st.columns([2.5, 1.1, 1.4])
            with ctrl1:
                st.selectbox(
                    "Odabir stranice nacrta:",
                    options=list(range(1, num_pages + 1)),
                    format_func=lambda p: page_labels_dict.get(p, f"Stranica {p} od {num_pages}"),
                    key="active_pdf_page",
                    label_visibility="collapsed"
                )

            with ctrl2:
                dpi_choice = st.selectbox("Oštrina:", ["120 DPI", "160 DPI", "200 DPI"], index=1, key="pdf_dpi_opt", label_visibility="collapsed")
                dpi_val = 120 if "120" in dpi_choice else (160 if "160" in dpi_choice else 200)

            with ctrl3:
                st.download_button(
                    label=f"Preuzmi PDF ({len(raw)/1024/1024:.1f} MB)",
                    data=raw,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_original_pdf_btn"
                )

            if num_pages > 1:
                def _prev_pdf_page():
                    c = int(st.session_state.get("active_pdf_page", 1))
                    st.session_state["active_pdf_page"] = max(1, c - 1)

                def _next_pdf_page():
                    c = int(st.session_state.get("active_pdf_page", 1))
                    st.session_state["active_pdf_page"] = min(num_pages, c + 1)

                np_col1, np_col2 = st.columns(2)
                cur_p = int(st.session_state.get("active_pdf_page", 1))
                with np_col1:
                    st.button("◀ Prethodna", key="btn_pdf_prev", use_container_width=True, disabled=(cur_p <= 1), on_click=_prev_pdf_page)
                with np_col2:
                    st.button("Sljedeća ▶", key="btn_pdf_next", use_container_width=True, disabled=(cur_p >= num_pages), on_click=_next_pdf_page)

            sel_page_idx = min(max(int(st.session_state.get("active_pdf_page", 1)) - 1, 0), num_pages - 1)
            img_bytes = _pdf_page_png(raw, sel_page_idx, dpi_val)  # cached render

            caption_txt = page_labels_dict.get(sel_page_idx + 1, f"Stranica {sel_page_idx + 1}")
            st.image(img_bytes, use_container_width=True, caption=f"{file_name} — {caption_txt}")

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
        st.error(f"Pogreška pri prikazu nacrta: {e}")

def _classify_wall_opening(wx1, wy1, wx2, wy2, atype=""):
    """
    Fallback classification of a wall panel as a door/window opening based on
    the ETABS area type or property/section name keywords. Model-independent:
    it never invents openings from raw coordinates. Returns (is_opening, is_door).
    """
    atype_l = str(atype).lower()

    if atype_l in ("opening", "window", "prozor"):
        return True, False
    if atype_l in ("door", "vrata"):
        return True, True

    if any(k in atype_l for k in ("door", "vrata")):
        return True, True
    if any(k in atype_l for k in ("prozor", "window", "otvor", "opening", "win")):
        return True, False

    return False, False

_classify_wall_opening_st = _classify_wall_opening


def fig_2d(df_res: pd.DataFrame, etabs_data: dict, active_story_name: str = None, is_dark: bool = None) -> go.Figure:
    COLOR_MAP = {
        Status.MATCH:            ("#16A34A", "Usklađeno"),
        Status.SECTION_MISMATCH: ("#D97706", "Odstupanje presjeka"),
        Status.ETABS_ONLY:       ("#DC2626", "Samo u ETABS-u"),
        Status.DXF_ONLY:         ("#2563EB", "Samo u nacrtu"),
        "Za provjeru s PDF-om":  ("#374151", "Element u modelu"),
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
    all_x = []
    all_y = []
    if active_story_name and not walls_all.empty and "story" in walls_all.columns:
        st_walls = walls_all[walls_all["story"] == active_story_name]
        for _, w in st_walls.iterrows():
            if pd.notna(w.get("x_start")): all_x.append(float(w["x_start"]))
            if pd.notna(w.get("x_end")): all_x.append(float(w["x_end"]))
            if pd.notna(w.get("centroid_x")): all_x.append(float(w["centroid_x"]))
            if pd.notna(w.get("y_start")): all_y.append(float(w["y_start"]))
            if pd.notna(w.get("y_end")): all_y.append(float(w["y_end"]))
            if pd.notna(w.get("centroid_y")): all_y.append(float(w["centroid_y"]))

    if not all_x:
        for df, xk, yk in [(cols_all, "x_start", "y_start"), (walls_all, "centroid_x", "centroid_y"), (beams_all, "x_start", "y_start")]:
            if not df.empty and xk in df.columns:
                all_x.extend(df[xk].dropna().astype(float).tolist())
            if not df.empty and yk in df.columns:
                all_y.extend(df[yk].dropna().astype(float).tolist())

    if not all_x and not df_res.empty:
        all_x = [float(r["etabs_x"]) for _, r in df_res.iterrows() if pd.notna(r.get("etabs_x"))]
        all_y = [float(r["etabs_y"]) for _, r in df_res.iterrows() if pd.notna(r.get("etabs_y"))]

    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 12.0
    min_y = min(all_y) if all_y else 0.0
    max_y = max(all_y) if all_y else 6.0

    pad_x = max((max_x - min_x) * 0.10, 3.5)
    pad_y = max((max_y - min_y) * 0.14, 3.5)

    status_map = {str(r.get("etabs_name")): r.get("status") for _, r in df_res.iterrows() if r.get("etabs_name")}

    if is_dark is None:
        is_dark = (st.session_state.get("app_theme") == "Tamna") if hasattr(st, "session_state") else False

    # 1. Background Slab Polygons
    if not slabs_all.empty or (max_x > min_x and max_y > min_y):
        fig.add_trace(go.Scatter(
            x=[min_x, max_x, max_x, min_x, min_x],
            y=[min_y, min_y, max_y, max_y, min_y],
            fill="toself",
            fillcolor="rgba(30, 41, 59, 0.4)" if is_dark else "rgba(241, 245, 249, 0.7)",
            line=dict(color="#475569" if is_dark else "#cbd5e1", width=1, dash="dash"),
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
        bm_cx, bm_cy, bm_tips = [], [], []
        for _, bm in beams_to_draw.iterrows():
            b_xs.extend([bm["x_start"], bm["x_end"], None])
            b_ys.extend([bm["y_start"], bm["y_end"], None])
            mx = (bm["x_start"] + bm["x_end"]) / 2.0
            my = (bm["y_start"] + bm["y_end"]) / 2.0
            bm_cx.append(mx)
            bm_cy.append(my)
            sec_lbl = bm.get("section") or "Greda"
            w_str = f"{bm['width_mm']:.0f}" if pd.notna(bm.get("width_mm")) else "—"
            h_str = f"{bm['height_mm']:.0f}" if pd.notna(bm.get("height_mm")) else "—"
            L_str = f"{math.hypot(bm['x_end']-bm['x_start'], bm['y_end']-bm['y_start']):.2f}"
            bm_tips.append(
                f"<b>Greda {bm.get('name', 'B')}</b> ({bm.get('story', '')})<br>"
                f"Presjek: {sec_lbl}<br>"
                f"Dimenzije: {w_str}×{h_str} mm<br>"
                f"Raspon: L = {L_str} m"
            )
        if b_xs:
            fig.add_trace(go.Scatter(
                x=b_xs, y=b_ys,
                mode="lines",
                line=dict(color="#334155", width=3.2),
                name=f"Grede ({len(beams_to_draw)})",
                hoverinfo="skip",
                showlegend=True,
            ))
            fig.add_trace(go.Scatter(
                x=bm_cx, y=bm_cy,
                mode="markers",
                marker=dict(size=6, color="#475569", symbol="diamond"),
                name="Središta greda (info)",
                hovertext=bm_tips,
                hoverinfo="text",
                showlegend=False,
            ))

    # Any DXF-only beams
    dxf_only_beams = df_res[(df_res["status"] == Status.DXF_ONLY) & (df_res["element_type"] == "beam")] if not df_res.empty and "status" in df_res.columns and "element_type" in df_res.columns else pd.DataFrame()
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

    # 2b. Room Slabs: Architectural room floor fill
    slabs_all = etabs_data.get("slabs", pd.DataFrame())
    if not slabs_all.empty:
        slabs_to_draw = slabs_all[slabs_all["story"] == active_story_name] if (active_story_name and "story" in slabs_all.columns) else slabs_all
        if slabs_to_draw.empty:
            slabs_to_draw = slabs_all
        for _, s in slabs_to_draw.iterrows():
            pts = s.get("pts_coords")
            if isinstance(pts, (list, tuple)) and len(pts) >= 3:
                poly_x = [p[0] for p in pts] + [pts[0][0]]
                poly_y = [p[1] for p in pts] + [pts[0][1]]
                fig.add_trace(go.Scatter(
                    x=poly_x, y=poly_y,
                    fill="toself",
                    fillcolor="rgba(33, 38, 45, 0.85)" if is_dark else "rgba(241, 245, 249, 0.88)",
                    line=dict(color="#30363D" if is_dark else "#cbd5e1", width=1.2),
                    mode="lines",
                    name="Ploča / Prostorije",
                    hoverinfo="skip",
                    showlegend=False,
                ))

    # 3. Walls: True geometric baseline with solid physical thickness
    if not walls_all.empty:
        if active_story_name and "story" in walls_all.columns:
            walls_to_draw = walls_all[walls_all["story"] == active_story_name]
            if walls_to_draw.empty:
                walls_to_draw = walls_all
        else:
            active_wall_names = set(df_res[df_res["element_type"] == "wall"]["etabs_name"].dropna().astype(str)) if not df_res.empty and "element_type" in df_res.columns and "etabs_name" in df_res.columns else set()
            walls_to_draw = walls_all[walls_all["name"].astype(str).isin(active_wall_names)] if active_wall_names else walls_all

        drawn_openings = set()
        drawn_walls = set()

        for _, w in walls_to_draw.iterrows():
            x1 = w.get("x_start", w.get("centroid_x", 0.0))
            y1 = w.get("y_start", w.get("centroid_y", 0.0))
            x2 = w.get("x_end", w.get("centroid_x", 0.0))
            y2 = w.get("y_end", w.get("centroid_y", 0.0))
            thick_m = float(w.get("thickness_mm", 250.0)) / 1000.0
            dx = x2 - x1
            dy = y2 - y1
            L = math.hypot(dx, dy)

            # Auto-detect opening if tagged or matched architectural opening
            is_opening = bool(w.get("is_opening", False))
            is_door = bool(w.get("is_door", False))
            if not is_opening:
                is_opening, is_door = _classify_wall_opening_st(x1, y1, x2, y2, w.get("atype", ""))
            is_cut = not is_opening

            loc_key = (w.get("story", ""), round(min(x1, x2), 2), round(min(y1, y2), 2), round(max(x1, x2), 2), round(max(y1, y2), 2))
            if is_opening:
                if loc_key in drawn_openings:
                    continue
                drawn_openings.add(loc_key)
            else:
                if loc_key in drawn_walls:
                    continue
                drawn_walls.add(loc_key)

            st_val = status_map.get(str(w["name"]), Status.MATCH)
            col, lbl = COLOR_MAP.get(st_val, ("#0284c7", "Element u modelu"))
            is_brick = "brick" in str(w.get("material", "")).lower() or "opeka" in str(w.get("material", "")).lower() or "masonry" in str(w.get("material", "")).lower() or "wall" in str(w.get("prop_name", "")).lower() or "zid" in str(w.get("prop_name", "")).lower()
            wall_fill_col = "#dc2626" if (is_brick and st_val == Status.MATCH) else col
            wall_line_col = "#991b1b" if (is_brick and st_val == Status.MATCH) else "#0f172a"

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

            if is_cut and not is_opening:
                # Puni nosivi zid u presjeku (Solid structural wall cut at +1.2m)
                fig.add_trace(go.Scatter(
                    x=poly_x, y=poly_y,
                    fill="toself",
                    fillcolor=wall_fill_col,
                    opacity=0.92,
                    line=dict(color=wall_line_col, width=1.5),
                    mode="lines",
                    name="Nosivi zid (presjek)",
                    hovertext=(
                        f"<b>Nosivi zid {w['name']}</b> [{lbl}]<br>"
                        f"Presjek: {w.get('prop_name', '—')} (Debljina: {thick_m*1000:.0f} mm)<br>"
                        f"Središnja os: ({x1:.2f}, {y1:.2f}) → ({x2:.2f}, {y2:.2f})<br>"
                        f"Proračunski model: Od sredine do sredine zida (±{thick_m*500:.0f} mm do lica)<br>"
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
            elif is_door:
                # OTVOR ZA VRATA / PROLAZ — clear void: opaque background fill cuts
                # through the wall band, with crisp red jambs at each end.
                void_fill = "#0D1117" if is_dark else "#FFFFFF"
                fig.add_trace(go.Scatter(
                    x=poly_x, y=poly_y,
                    fill="toself",
                    fillcolor=void_fill,
                    line=dict(color="#94a3b8", width=1.0, dash="dot"),
                    mode="lines",
                    name="Otvor vrata",
                    hovertext=(
                        f"<b>Otvor vrata / prolaz {w['name']}</b><br>"
                        f"Širina otvora: {L:.2f} m<br>"
                        f"Položaj: ({x1:.2f}, {y1:.2f}) → ({x2:.2f}, {y2:.2f})"
                    ),
                    hoverinfo="text",
                    showlegend=False,
                ))
                if L >= 0.05:
                    nxd = -dy / L
                    nyd = dx / L
                    htd = max(thick_m / 2.0, 0.12)
                    # Crisp wall jambs (špalete) at both ends of the doorway
                    for jx, jy in ((x1, y1), (x2, y2)):
                        fig.add_trace(go.Scatter(
                            x=[jx - nxd*htd, jx + nxd*htd],
                            y=[jy - nyd*htd, jy + nyd*htd],
                            mode="lines",
                            line=dict(color="#991b1b", width=3.0),
                            hoverinfo="skip",
                            showlegend=False,
                        ))
            else:
                # PROZORSKI OTVOR — clear void: opaque background fill cuts the wall
                # band, crisp red jambs at each end, and a thin double glazing line.
                void_fill = "#0D1117" if is_dark else "#FFFFFF"
                fig.add_trace(go.Scatter(
                    x=poly_x, y=poly_y,
                    fill="toself",
                    fillcolor=void_fill,
                    line=dict(color="#64748b", width=1.0, dash="dot"),
                    mode="lines",
                    name="Prozorski otvor",
                    hovertext=(
                        f"<b>Prozorski otvor {w['name']}</b><br>"
                        f"Širina otvora: {L:.2f} m<br>"
                        f"Debljina zida: {thick_m*1000:.0f} mm<br>"
                        f"Položaj: ({x1:.2f}, {y1:.2f}) → ({x2:.2f}, {y2:.2f})"
                    ),
                    hoverinfo="text",
                    showlegend=False,
                ))

                if L >= 0.05:
                    nx = -dy / L
                    ny = dx / L
                    ht = max(thick_m / 2.0, 0.12)
                    # Crisp wall jambs (špalete) at both ends of the window
                    for jx, jy in ((x1, y1), (x2, y2)):
                        fig.add_trace(go.Scatter(
                            x=[jx - nx*ht, jx + nx*ht],
                            y=[jy - ny*ht, jy + ny*ht],
                            mode="lines",
                            line=dict(color="#991b1b", width=3.0),
                            hoverinfo="skip",
                            showlegend=False,
                        ))
                    # Double glazing lines (two thin panes) spanning the opening
                    off = ht * 0.30
                    fig.add_trace(go.Scatter(
                        x=[x1 + nx*off, x2 + nx*off],
                        y=[y1 + ny*off, y2 + ny*off],
                        mode="lines",
                        line=dict(color="#0284c7", width=1.4),
                        name="Staklo prozora",
                        hoverinfo="skip",
                        showlegend=False,
                    ))
                    fig.add_trace(go.Scatter(
                        x=[x1 - nx*off, x2 - nx*off],
                        y=[y1 - ny*off, y2 - ny*off],
                        mode="lines",
                        line=dict(color="#0284c7", width=1.4),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

    # 4. Columns: Sharp colored squares
    if not df_res.empty and "element_type" in df_res.columns:
        if active_story_name and "story" in df_res.columns:
            col_records = df_res[(df_res["element_type"] == "column") & (df_res["story"] == active_story_name)]
            if col_records.empty:
                col_records = df_res[df_res["element_type"] == "column"]
        else:
            col_records = df_res[df_res["element_type"] == "column"]
    else:
        col_records = pd.DataFrame()
    marker_size = 12 if len(col_records) > 50 else 22
    show_text_on_marker = len(col_records) <= 25

    if not col_records.empty and "status" in col_records.columns:
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
    def _cluster_coords(coords, min_gap=4.0):
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

    def _cluster_grid_axis(coords, ids, min_gap=4.0):
        if not coords:
            return [], []
        pairs = sorted(zip(coords, ids), key=lambda p: p[0])
        filtered = [p for p in pairs if (min_x - pad_x*0.8) <= p[0] <= (max_x + pad_x*0.8)]
        if not filtered:
            filtered = pairs

        out_c = [filtered[0][0]]
        out_id = [str(filtered[0][1])]
        for c, gid in filtered[1:]:
            if c - out_c[-1] >= min_gap:
                out_c.append(c)
                out_id.append(str(gid))
        if filtered[-1][0] - out_c[-1] > min_gap * 0.6:
            out_c.append(filtered[-1][0])
            out_id.append(str(filtered[-1][1]))
        return out_c, out_id

    df_grids = etabs_data.get("grids", pd.DataFrame())
    bubble_xs, labels_x = [], []
    bubble_ys, labels_y = [], []

    if not df_grids.empty and "dir" in df_grids.columns and "coord" in df_grids.columns:
        x_grids = df_grids[df_grids["dir"] == "X"].sort_values("coord")
        y_grids = df_grids[df_grids["dir"] == "Y"].sort_values("coord")
        if not x_grids.empty:
            bubble_xs, labels_x = _cluster_grid_axis(x_grids["coord"].tolist(), x_grids["id"].tolist(), min_gap=4.0)
        if not y_grids.empty:
            bubble_ys, labels_y = _cluster_grid_axis(y_grids["coord"].tolist(), y_grids["id"].tolist(), min_gap=4.0)

    if not bubble_xs:
        c_x = _cluster_coords(all_x, min_gap=5.0)
        bubble_xs = c_x
        labels_x = [chr(65 + i) if i < 26 else f"A{i}" for i in range(len(bubble_xs))]

    if not bubble_ys:
        c_y = _cluster_coords(all_y, min_gap=5.0)
        bubble_ys = c_y
        labels_y = [str(i + 1) for i in range(len(bubble_ys))]

    y_bubble = max_y + pad_y * 0.45
    for gx, lx in zip(bubble_xs, labels_x):
        fig.add_shape(type="line", x0=gx, y0=min_y - 0.5, x1=gx, y1=y_bubble,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=[gx], y=[y_bubble],
            mode="markers+text",
            marker=dict(size=22, color="#3b82f6", line=dict(color="#ffffff", width=1.5)),
            text=[str(lx)[:4]], textfont=dict(color="white", size=10, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {lx} (X = {gx:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    x_bubble = min_x - pad_x * 0.45
    for gy, ly in zip(bubble_ys, labels_y):
        fig.add_shape(type="line", x0=x_bubble, y0=gy, x1=max_x + 0.5, y1=gy,
                      line=dict(color="#e2e8f0", width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=[x_bubble], y=[gy],
            mode="markers+text",
            marker=dict(size=22, color="#0284c7", line=dict(color="#ffffff", width=1.5)),
            text=[str(ly)[:4]], textfont=dict(color="white", size=10, weight="bold"),
            textposition="middle center",
            hovertext=f"Grid Os {ly} (Y = {gy:.1f} m)", hoverinfo="text",
            showlegend=False,
        ))

    # Story title display
    s_disp = active_story_name
    if active_story_name:
        for s in etabs_data.get("stories", []):
            if s["name"] == active_story_name:
                s_disp = s.get("display_name", s["name"])
                break
        if s_disp and s_disp.lower() in ("base", "podnozje", "podnožje"):
            s_disp = "Prizemlje"

    bg_col = "#0D1117" if is_dark else "#ffffff"
    title_col = "#F0F6FC" if is_dark else "#0f172a"
    grid_col = "#21262D" if is_dark else "#f1f5f9"
    zero_col = "#30363D" if is_dark else "#cbd5e1"
    tick_col = "#8B949E" if is_dark else "#64748b"
    leg_bg = "rgba(22, 27, 34, 0.95)" if is_dark else "rgba(255,255,255,0.9)"
    leg_border = "#30363D" if is_dark else "#e2e8f0"
    leg_text = "#F0F6FC" if is_dark else "#334155"

    fig.update_layout(
        title=dict(
            text=f"<b>📐 Tlocrt: {s_disp}</b>" if s_disp else "<b>📐 Tlocrt numeričkog modela (Sve etaže)</b>",
            x=0.02, y=0.98,
            font=dict(size=14, color=title_col),
        ),
        margin=dict(l=30, r=20, t=40, b=40),
        height=540,
        plot_bgcolor=bg_col,
        paper_bgcolor=bg_col,
        xaxis=dict(
            title=dict(text="X koordinata (m)", font=dict(color=tick_col)),
            range=[min_x - pad_x, max_x + pad_x],
            showgrid=True,
            gridcolor=grid_col,
            zeroline=True,
            zerolinecolor=zero_col,
            tickfont=dict(size=11, color=tick_col),
        ),
        yaxis=dict(
            title=dict(text="Y koordinata (m)", font=dict(color=tick_col)),
            range=[min_y - pad_y, max_y + pad_y],
            scaleanchor="x",
            scaleratio=1,
            showgrid=True,
            gridcolor=grid_col,
            zeroline=True,
            zerolinecolor=zero_col,
            tickfont=dict(size=11, color=tick_col),
        ),
        legend=dict(
            orientation="h",
            x=0, y=-0.14,
            bgcolor=leg_bg,
            bordercolor=leg_border,
            borderwidth=1,
            font=dict(size=11, color=leg_text),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 3D Model: Fast segmented wireframe matching ETABS appearance
# ─────────────────────────────────────────────────────────────
def fig_3d(df_res: pd.DataFrame, etabs_data: dict, etabs_color_mode: bool = True, active_story_name: str = None, is_dark: bool = None) -> go.Figure:
    fig = go.Figure()

    cols = etabs_data.get("columns", pd.DataFrame())
    beams = etabs_data.get("beams", pd.DataFrame())
    walls = etabs_data.get("walls", pd.DataFrame())
    slabs = etabs_data.get("slabs", pd.DataFrame())

    if active_story_name:
        if not cols.empty and "story" in cols.columns:
            sub_c = cols[cols["story"] == active_story_name]
            if not sub_c.empty: cols = sub_c
        if not beams.empty and "story" in beams.columns:
            sub_b = beams[beams["story"] == active_story_name]
            if not sub_b.empty: beams = sub_b
        if not walls.empty and "story" in walls.columns:
            sub_w = walls[walls["story"] == active_story_name]
            if not sub_w.empty: walls = sub_w
        if not slabs.empty and "story" in slabs.columns:
            sub_s = slabs[slabs["story"] == active_story_name]
            if not sub_s.empty: slabs = sub_s

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

    # Walls in 3D: Shaded structural panels & wireframe contours matching ETABS
    if not walls.empty:
        w_xs, w_ys, w_zs = [], [], []
        mesh_x, mesh_y, mesh_z = [], [], []
        mesh_i, mesh_j, mesh_k = [], [], []
        v_offset = 0

        drawn_openings_3d = set()
        drawn_walls_3d = set()

        for _, w in walls.iterrows():
            x1 = w.get("x_start", w["centroid_x"])
            y1 = w.get("y_start", w["centroid_y"])
            x2 = w.get("x_end", w["centroid_x"])
            y2 = w.get("y_end", w["centroid_y"])
            z_bot = w.get("z_min", 0.0)
            z_top = w.get("z_max", 3.5)
            L = math.hypot(x2 - x1, y2 - y1)
            is_opening = bool(w.get("is_opening", False))
            is_door = bool(w.get("is_door", False))
            if not is_opening:
                is_opening, is_door = _classify_wall_opening_st(x1, y1, x2, y2, w.get("atype", ""))

            loc_key = (w.get("story", ""), round(min(x1, x2), 2), round(min(y1, y2), 2), round(max(x1, x2), 2), round(max(y1, y2), 2))
            if is_opening:
                if loc_key in drawn_openings_3d:
                    continue
                drawn_openings_3d.add(loc_key)
            else:
                if loc_key in drawn_walls_3d:
                    continue
                drawn_walls_3d.add(loc_key)

            story_h = max(z_top - z_bot, 0.1)
            if is_opening:
                if is_door:
                    # Doorway: open cutout from floor to door head (~2.10 m),
                    # only a lintel band remains above. Scale head to story height.
                    z_head = z_bot + min(2.10, story_h * 0.85)
                    z_l = min(z_head, z_top - 0.10)
                    sub_panels = [
                        [(x1, y1, z_l), (x2, y2, z_l), (x2, y2, z_top), (x1, y1, z_top)],  # Lintel
                    ]
                else:
                    # Window: parapet (sill) band at bottom + open hole + lintel band
                    # at top. Standard heights, clamped to the actual story height so
                    # it works for any model regardless of facade orientation.
                    z_sill = z_bot + min(0.90, story_h * 0.30)
                    z_head = z_bot + min(2.20, story_h * 0.75)
                    if z_head <= z_sill + 0.10:
                        z_head = min(z_sill + 0.30, z_top - 0.05)
                    z_p = z_sill
                    z_l = min(z_head, z_top - 0.05)
                    sub_panels = [
                        [(x1, y1, z_bot), (x2, y2, z_bot), (x2, y2, z_p), (x1, y1, z_p)],  # Parapet panel
                        [(x1, y1, z_l), (x2, y2, z_l), (x2, y2, z_top), (x1, y1, z_top)],  # Lintel panel
                    ]
            else:
                pts = w.get("pts_coords")
                if isinstance(pts, (list, tuple)) and len(pts) == 4:
                    sub_panels = [pts]
                else:
                    sub_panels = [[(x1, y1, z_bot), (x2, y2, z_bot), (x2, y2, z_top), (x1, y1, z_top)]]

            for s_pts in sub_panels:
                for p in s_pts:
                    w_xs.append(p[0])
                    w_ys.append(p[1])
                    w_zs.append(p[2])
                w_xs.append(s_pts[0][0])
                w_ys.append(s_pts[0][1])
                w_zs.append(s_pts[0][2])
                w_xs.append(None)
                w_ys.append(None)
                w_zs.append(None)

                for p in s_pts:
                    mesh_x.append(p[0])
                    mesh_y.append(p[1])
                    mesh_z.append(p[2])
                mesh_i.extend([v_offset, v_offset])
                mesh_j.extend([v_offset + 1, v_offset + 2])
                mesh_k.extend([v_offset + 2, v_offset + 3])
                v_offset += 4


        if mesh_x:
            fig.add_trace(go.Mesh3d(
                x=mesh_x, y=mesh_y, z=mesh_z,
                i=mesh_i, j=mesh_j, k=mesh_k,
                color="#dc2626" if etabs_color_mode else "#10b981",
                opacity=0.75,
                flatshading=True,
                lighting=dict(ambient=0.90, diffuse=0.1, specular=0.0),
                name="Plohe zidova (ETABS)",
                hoverinfo="skip",
            ))

        if w_xs:
            fig.add_trace(go.Scatter3d(
                x=w_xs, y=w_ys, z=w_zs,
                mode="lines",
                line=dict(color="#ffffff" if etabs_color_mode else "#059669", width=2.0),
                name="Mreža zidova (ETABS)",
                hoverinfo="skip",
            ))

    # Slabs in 3D: Light gray concrete floor panels matching ETABS
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
                color="#cbd5e1" if active_story_name else "#94a3b8",
                opacity=0.88 if active_story_name else 0.55,
                flatshading=True,
                lighting=dict(ambient=0.88, diffuse=0.15, specular=0.0),
                name="Podna ploča (ETABS)",
                hoverinfo="skip",
            ))

        if s_xs:
            fig.add_trace(go.Scatter3d(
                x=s_xs, y=s_ys, z=s_zs,
                mode="lines",
                line=dict(color="#334155", width=2.0),
                name="Rub ploče (ETABS)",
                hoverinfo="skip",
            ))

    if is_dark is None:
        is_dark = (st.session_state.get("app_theme") == "Tamna") if hasattr(st, "session_state") else False
    fig_bg = "#0D1117" if is_dark else "#ffffff"

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=580,
        paper_bgcolor=fig_bg,
        plot_bgcolor=fig_bg,
        scene=dict(
            aspectmode="data",
            camera=dict(
                eye=dict(x=-1.25, y=-1.75, z=1.35) if active_story_name else dict(x=-1.60, y=-2.10, z=1.15),
                center=dict(x=0, y=0, z=-0.15) if active_story_name else dict(x=0, y=0, z=0.0),
                up=dict(x=0, y=0, z=1)
            ),
            xaxis=dict(visible=False, showgrid=False, showbackground=False, zeroline=False),
            yaxis=dict(visible=False, showgrid=False, showbackground=False, zeroline=False),
            zaxis=dict(visible=False, showgrid=False, showbackground=False, zeroline=False),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# Table helper: Cleans attrs & formats floats safely
# ─────────────────────────────────────────────────────────────
def safe_df(df: pd.DataFrame, float_fmt=None) -> pd.DataFrame:
    out = df.copy()
    out.attrs = {}
    if float_fmt:
        for col, fmt in float_fmt.items():
            if col in out.columns:
                out[col] = out[col].apply(lambda v: fmt.format(v) if pd.notna(v) and v is not None and not isinstance(v, str) else str(v or "—"))
    for col in out.columns:
        out[col] = out[col].apply(lambda v: "—" if pd.isna(v) or v is None or str(v).strip() in ("", "None", "nan") else str(v))
    return out


# ─────────────────────────────────────────────────────────────
# User Guide & Engineering Instructions Component
# ─────────────────────────────────────────────────────────────
def render_instructions():
    """Renders comprehensive user manual and engineering guide."""
    st.markdown("""
    ### Inženjerski vodič za kontrolu numeričkih modela (ETABS ↔ CAD)

    Ovaj sustav omogućuje **automatiziranu reviziju i kontrolu kvalitete (QA/QC)** proračunskih modela iz softvera **CSI ETABS v23** u odnosu na izvedbene arhitektonske i građevinske nacrte (**AutoCAD .dxf, PDF ili slike**) u skladu s **Eurocode normama (HRN EN 1990, EN 1992, EN 1993, EN 1998)**.

    ---

    #### Korak 1 — Izvoz modela iz ETABS-a
    1. Otvorite projekt u programu **ETABS v23** (ili ranijim verzijama).
    2. U glavnom izborniku odaberite:  
       **`File` → `Export` → `ETABS .e2k Text File...`**
    3. Spremite datoteku na računalo (npr. `Projekt_Konstrukcije.e2k`).
    4. *Zašto .e2k a ne .edb?*  
       Datoteka `.edb` je interna binarna baza podataka koju ETABS zaključava i koja se ne može čitati na webu bez instaliranog Windows ETABS-a i aktivne licence. Datoteka `.e2k` je službeni, čisti tekstualni format namijenjen upravo za vanjsku razmjenu, arhiviranje i neovisnu reviziju modela.

    ---

    #### Korak 2 — Priprema i učitavanje CAD nacrta (.dxf)
    1. U AutoCAD-u otvorite tlocrt oplate ili armature etaže koju želite provjeriti.
    2. Spremite ga u DXF formatu: **`File` → `Save As` → `AutoCAD 2010/2018 DXF (*.dxf)`**.
    3. **Mjerne jedinice:** U lijevom izborniku pod *Jedinica DXF nacrta* odaberite jedinicu u kojoj je crtano:
       - **Centimetri (cm, 0.01)** — standard u visokogradnji.
       - **Milimetri (mm, 0.001)** — detalji i čelične konstrukcije.
       - **Metri (m, 1.0)** — geodezija i opće situacije.
    4. **Podržani elementi u CAD-u:**
       - Stupovi mogu biti nacrtani kao zatvorene **polilinije** (`LWPOLYLINE`) ili **AutoCAD blokovi** (`INSERT`).
       - Dimenzije se mjere izravno iz geometrije polilinije, a tekstualne oznake se automatski uspoređuju.
    5. **Referentni PDF nacrt:**
       - Ako nemate DXF ili želite vizualnu usporedbu, u polje *Nacrt* učitajte PDF elaborat. Aplikacija će ga prikazati usporedo s modelom u Tabu 1.

    ---

    #### Korak 3 — Rad s višeetažnim zgradama (Filter etaža)
    Budući da CAD nacrt obično prikazuje **jednu etažu**, a ETABS model sadrži cijelu zgradu:
    - Koristite vodoravni selektor etaža na vrhu Taba 1 (`Prizemlje`, `1. Kat`...).
    - Aplikacija filtrira elemente te etaže i uspoređuje ih s nacrtom, bez lažnih odstupanja s gornjih katova.

    ---

    #### Korak 4 — Tumač statusa i boja
    - **Usklađeno (Match):** Element je pronađen na točnoj lokaciji i njegove dimenzije u potpunosti odgovaraju nacrtu unutar zadane tolerancije.
    - **Odstupanje presjeka (Section Mismatch):** Pozicija odgovara, ali postoji razlika u dimenzijama (npr. CAD 40×40 cm vs. ETABS 50×50 cm).
    - **Samo u ETABS-u (ETABS Only):** Element postoji u numeričkom modelu, ali ga nema u nacrtu.
    - **Samo u nacrtu (CAD Only):** Element je ucrtan na nacrtu, ali nije unesen u ETABS model.

    ---

    #### Korak 5 — Podešavanje inženjerskih tolerancija
    U lijevom izborniku pod *Tolerancije*:
    - **Pozicija (m):** Dozvoljeni prostorni razmak osi elementa i nacrta (zadano 0.15 m).
    - **Presjek (mm):** Dozvoljena razlika u dimenziji prije označavanja odstupanja (zadano 5 mm).

    ---

    #### Korak 6 — Preuzimanje elaborata
    U tabu **Izvještaj**:
    - **Preuzmi PDF elaborat (A4 Landscape):** Generira formalni dokument s naslovnicom, sažetkom usklađenosti, tlocrtom i tablicom svih odstupanja, spreman za reviziju i arhivu.
    """)

