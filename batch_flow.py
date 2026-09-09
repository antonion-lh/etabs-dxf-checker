"""
batch_flow.py
-------------
Batch provjera: profesor učita jedan referentni model (iz JSON-a spremljenog u
wizardu ILI generiran iz DXF tlocrta) i više studentskih .e2k modela odjednom,
te dobije tablicu ocjena po studentu + statistiku razreda.

Čista logika (run_batch, batch_statistics, parse pomoćnici) je odvojena od
render_batch(st, cfg) radi testabilnosti bez Streamlit runtimea.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from config import Config, DEFAULT_CONFIG


def run_batch(ref_model: Dict[str, Any],
              students: List[Tuple[str, bytes]],
              cfg: Config = DEFAULT_CONFIG,
              progress_cb=None):
    """Uspoređuje više studentskih E2K (bytes) protiv referentnog modela.

    students : lista (naziv_datoteke, e2k_bytes).
    progress_cb : opcionalni callback(i, n, naziv) za prikaz napretka.
    Vraća DataFrame ocjena (kao model_compare.compare_batch). Neispravan E2K
    ne ruši batch — dobiva red s greškom.
    """
    import wizard_flow
    import model_compare

    total = len(students or [])
    parsed: List[Tuple[str, Any]] = []
    for i, (name, data) in enumerate(students or []):
        if progress_cb is not None:
            try:
                progress_cb(i, total, name)
            except Exception:  # noqa: BLE001
                pass
        try:
            parsed.append((name, wizard_flow.parse_e2k_bytes(data, cfg)))
        except Exception as e:  # noqa: BLE001
            parsed.append((name, {"__error__": str(e)}))

    if progress_cb is not None:
        try:
            progress_cb(total, total, "")
        except Exception:  # noqa: BLE001
            pass

    # compare_batch se sam nosi s neispravnim modelima (ocjena None)
    return model_compare.compare_batch(parsed, ref_model, cfg)


def batch_statistics(df) -> Dict[str, Any]:
    """Statistika razreda iz batch rezultata (prosjek ocjene/točnosti, raspodjela)."""
    stats: Dict[str, Any] = {
        "n_students": 0, "avg_grade": None, "avg_accuracy": None,
        "distribution": {}, "n_failed": 0,
    }
    if df is None or not hasattr(df, "empty") or df.empty:
        return stats

    def _valid(v):
        # odbaci None i NaN (pandas None -> NaN u numerickoj koloni)
        return v is not None and v == v

    stats["n_students"] = len(df)
    grades = [g for g in df.get("ocjena", []) if _valid(g)]
    accs = [a for a in df.get("tocnost_%", []) if _valid(a)]
    if grades:
        stats["avg_grade"] = round(sum(grades) / len(grades), 2)
        dist = {}
        for g in grades:
            dist[int(g)] = dist.get(int(g), 0) + 1
        stats["distribution"] = dict(sorted(dist.items()))
    if accs:
        stats["avg_accuracy"] = round(sum(accs) / len(accs), 1)
    stats["n_failed"] = int(sum(1 for g in df.get("ocjena", []) if not _valid(g)))
    return stats


def load_reference(ref_json: Optional[bytes] = None,
                   dxf_bytes: Optional[bytes] = None,
                   cfg: Config = DEFAULT_CONFIG,
                   user_input: Optional[dict] = None) -> Dict[str, Any]:
    """Učitava referentni model iz JSON-a (prioritet) ili generira iz DXF-a."""
    import ref_model_ui

    if ref_json:
        return ref_model_ui.model_from_json(ref_json)
    if dxf_bytes:
        return ref_model_ui.build_ref_model_from_bytes(dxf_bytes, cfg, user_input)
    import dxf_model
    return dxf_model._empty_model(False, error="Nije zadan referentni model.")


# ---------------------------------------------------------------------------
# Render (Streamlit)
# ---------------------------------------------------------------------------

_SS = {
    "active": "batch_active",
    "ref": "batch_ref_model",
    "results": "batch_results",
    "unit": "batch_unit_label",
}


def reset_batch(st) -> None:
    for k in _SS.values():
        st.session_state.pop(k, None)


def render_batch(st, cfg: Config = DEFAULT_CONFIG) -> None:
    """Ekran batch provjere više studentskih modela protiv referentnog."""
    import ref_model_ui
    import model_compare
    import wizard_flow

    st.markdown("## Batch provjera više modela")
    _, top_r = st.columns([4, 1])
    with top_r:
        if st.button("Natrag na početak", key="batch_exit", use_container_width=True):
            reset_batch(st)
            st.rerun()

    st.markdown("---")
    st.markdown("### 1. Referentni model")
    st.caption("Učitajte ranije spremljeni referentni model (JSON) ili ga "
               "generirajte iz DXF tlocrta.")

    tab_json, tab_dxf = st.columns(2)
    with tab_json:
        up_json = st.file_uploader("Spremljeni model (JSON)", type=["json"],
                                   key="batch_json_up")
        if up_json is not None:
            try:
                st.session_state[_SS["ref"]] = ref_model_ui.model_from_json(up_json.getvalue())
                st.success("Referentni model učitan iz JSON-a.")
            except Exception as e:  # noqa: BLE001
                st.error("JSON nije valjan: %s" % e)
    with tab_dxf:
        up_dxf = st.file_uploader("DXF tlocrt", type=["dxf"], key="batch_dxf_up")
        unit_labels = list(wizard_flow.UNIT_OPTIONS.keys())
        unit_label = st.selectbox("Jedinica crteža", unit_labels, index=0,
                                  key="batch_unit_in")
        c1, c2 = st.columns(2)
        n_st = c1.number_input("Broj etaža", 1, 50, 1, key="batch_n_stories")
        h_st = c2.number_input("Visina etaže (m)", 2.0, 6.0, 3.0, 0.1, key="batch_story_h")
        if up_dxf is not None and st.button("Generiraj referentni model",
                                            key="batch_gen_btn"):
            ui = {"n_stories": int(n_st), "story_height": float(h_st)}
            us = wizard_flow.UNIT_OPTIONS.get(unit_label)
            if us is not None:
                ui["unit_scale"] = us
            try:
                st.session_state[_SS["ref"]] = ref_model_ui.build_ref_model_from_bytes(
                    up_dxf.getvalue(), cfg, ui)
                st.success("Referentni model generiran.")
            except Exception as e:  # noqa: BLE001
                st.error("Generiranje nije uspjelo: %s" % e)

    ref_model = st.session_state.get(_SS["ref"])
    if ref_model and ref_model.get("meta", {}).get("ok"):
        src = "JSON" if ref_model.get("meta", {}).get("edited") is None and \
            "scale_to_m" not in ref_model.get("meta", {}) else "DXF tlocrt"
        st.success("Aktivna referenca (izvor: %s)." % src)
        for line in ref_model_ui.model_summary_text(ref_model):
            st.markdown("- " + line)

    st.markdown("---")
    st.markdown("### 2. Studentski modeli (.e2k)")
    ups = st.file_uploader("Više .e2k datoteka", type=["e2k", "$et", "txt"],
                           accept_multiple_files=True, key="batch_e2k_up")

    st.markdown("---")
    st.markdown("### 3. Rezultati")
    if st.button("Pokreni batch provjeru", type="primary", key="batch_run_btn"):
        if not (ref_model and ref_model.get("meta", {}).get("ok")):
            st.error("Prvo učitajte ili generirajte ispravan referentni model.")
        elif not ups:
            st.error("Učitajte barem jednu studentsku .e2k datoteku.")
        else:
            students = [(f.name, f.getvalue()) for f in ups]
            prog = st.progress(0.0)
            status = st.empty()

            def _cb(i, n, name):
                frac = (i / n) if n else 1.0
                try:
                    prog.progress(min(frac, 1.0))
                    if name:
                        status.caption("Obrađujem model %d/%d: %s" % (i + 1, n, name))
                except Exception:  # noqa: BLE001
                    pass

            try:
                df = run_batch(ref_model, students, cfg, progress_cb=_cb)
                st.session_state[_SS["results"]] = df
                status.caption("Gotovo — obrađeno %d modela." % len(students))
            except Exception as e:  # noqa: BLE001
                st.error("Batch provjera nije uspjela: %s" % e)

    df = st.session_state.get(_SS["results"])
    if df is not None and hasattr(df, "empty") and not df.empty:
        stats = batch_statistics(df)
        m1, m2, m3 = st.columns(3)
        m1.metric("Broj modela", stats["n_students"])
        m2.metric("Prosječna ocjena", stats["avg_grade"] if stats["avg_grade"] is not None else "—")
        m3.metric("Prosječna točnost",
                  "%.1f %%" % stats["avg_accuracy"] if stats["avg_accuracy"] is not None else "—")
        # Histogram raspodjele ocjena (B.3)
        dist = stats.get("distribution") or {}
        if dist:
            import pandas as pd
            hist_df = pd.DataFrame(
                {"broj studenata": [dist.get(g, 0) for g in (1, 2, 3, 4, 5)]},
                index=["1", "2", "3", "4", "5"])
            st.caption("Raspodjela ocjena")
            st.bar_chart(hist_df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        try:
            st.download_button("Preuzmi rezultate (CSV)",
                               data=df.to_csv(index=False).encode("utf-8"),
                               file_name="batch_ocjene.csv", mime="text/csv",
                               key="batch_csv_dl")
        except Exception:
            pass
