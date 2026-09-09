"""
wizard_flow.py
--------------
Zaseban vođeni tok ("wizard") za provjeru studentskog modela prema tlocrtu.

Redoslijed koraka (obrnuto od glavne aplikacije — tlocrt je prvi):
  1. STEP_UPLOAD_DXF  — učitaj DXF tlocrt
  2. STEP_GENERATE    — generiraj numerički referentni model iz tlocrta
  3. STEP_REFINE      — dorada / dopuna modela (uređivanje + dodavanje redova)
  4. STEP_CONFIRM     — potvrdi ispravnost generiranog modela (zaključa referentni model)
  5. STEP_UPLOAD_E2K  — učitaj studentski .e2k model
  6. STEP_COMPARE     — usporedba sa studentskim modelom + sažetak razlika

Ovaj modul drži ČISTU logiku (state machine, validacije prijelaza, pomoćnici
za parsiranje) bez importa streamlit u jezgri, pa je testabilan bez UI runtimea.
Funkcija render_wizard(st, cfg) (Zadatak 2) crta korake i poziva ovu logiku.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from config import Config, DEFAULT_CONFIG

# Redoslijed koraka (indeks = redni broj)
STEP_UPLOAD_DXF = 0
STEP_GENERATE = 1
STEP_REFINE = 2
STEP_CONFIRM = 3
STEP_UPLOAD_E2K = 4
STEP_COMPARE = 5

STEP_ORDER = [
    STEP_UPLOAD_DXF, STEP_GENERATE, STEP_REFINE,
    STEP_CONFIRM, STEP_UPLOAD_E2K, STEP_COMPARE,
]

# Naslovi koraka (hrvatski) za prikaz u progress indikatoru
STEP_TITLES = {
    STEP_UPLOAD_DXF: "Učitaj tlocrt (DXF)",
    STEP_GENERATE: "Generiraj model",
    STEP_REFINE: "Doradi model",
    STEP_CONFIRM: "Potvrdi ispravnost",
    STEP_UPLOAD_E2K: "Učitaj studentski model (E2K)",
    STEP_COMPARE: "Usporedba",
}


def initial_state() -> Dict[str, Any]:
    """Početno stanje wizarda."""
    return {
        "step": STEP_UPLOAD_DXF,
        "dxf_bytes": None,
        "ref_model": None,
        "ref_confirmed": False,
        "edited_tables": {},
        "student_e2k": None,
        "compare_result": None,
    }


def can_advance(state: Dict[str, Any]) -> bool:
    """Smije li se s trenutnog koraka naprijed (jesu li ispunjeni uvjeti).

    - UPLOAD_DXF -> treba učitan DXF (dxf_bytes)
    - GENERATE   -> treba uspješno generiran referentni model (meta.ok)
    - REFINE     -> uvijek smije (dorada je opcionalna)
    - CONFIRM    -> treba potvrđena ispravnost (ref_confirmed)
    - UPLOAD_E2K -> treba učitan studentski model (student_e2k)
    - COMPARE    -> zadnji korak, nema dalje
    """
    step = state.get("step", STEP_UPLOAD_DXF)
    if step == STEP_UPLOAD_DXF:
        return bool(state.get("dxf_bytes"))
    if step == STEP_GENERATE:
        rm = state.get("ref_model")
        return bool(rm and rm.get("meta", {}).get("ok"))
    if step == STEP_REFINE:
        return True
    if step == STEP_CONFIRM:
        return bool(state.get("ref_confirmed"))
    if step == STEP_UPLOAD_E2K:
        return bool(state.get("student_e2k"))
    if step == STEP_COMPARE:
        return False
    return False


def next_step(state: Dict[str, Any]) -> int:
    """Vrati indeks sljedećeg koraka ako je prijelaz dopušten, inače isti korak."""
    step = state.get("step", STEP_UPLOAD_DXF)
    if not can_advance(state):
        return step
    idx = STEP_ORDER.index(step)
    if idx + 1 < len(STEP_ORDER):
        return STEP_ORDER[idx + 1]
    return step


def prev_step(state: Dict[str, Any]) -> int:
    """Vrati indeks prethodnog koraka (nikad ispod prvog)."""
    step = state.get("step", STEP_UPLOAD_DXF)
    idx = STEP_ORDER.index(step) if step in STEP_ORDER else 0
    if idx - 1 >= 0:
        return STEP_ORDER[idx - 1]
    return STEP_ORDER[0]


def progress_fraction(step: int) -> float:
    """Udio dovršenosti (0..1) za progress bar."""
    if not STEP_ORDER:
        return 0.0
    idx = STEP_ORDER.index(step) if step in STEP_ORDER else 0
    return (idx + 1) / len(STEP_ORDER)


def parse_e2k_bytes(e2k_bytes: bytes, cfg: Config = DEFAULT_CONFIG) -> Dict[str, Any]:
    """Parsira studentski E2K iz bytes-a (kako Streamlit isporučuje upload).

    Vraća dict kao phase1_e2k.parse_e2k. Diže iznimku na potpuno neispravnom
    ulazu — pozivatelj (render) hvata i prikazuje grešku.
    """
    from phase1_e2k import parse_e2k

    text = e2k_bytes.decode("utf-8", errors="replace") if e2k_bytes else ""
    return parse_e2k(io.StringIO(text), cfg)


def build_reference_model(dxf_bytes: bytes, cfg: Config = DEFAULT_CONFIG,
                          user_input: Optional[dict] = None) -> Dict[str, Any]:
    """Generira referentni model iz DXF bytes-a (omotač oko ref_model_ui)."""
    import ref_model_ui

    return ref_model_ui.build_ref_model_from_bytes(dxf_bytes, cfg, user_input)


def run_comparison(student_e2k: Dict[str, Any], ref_model: Dict[str, Any],
                   cfg: Config = DEFAULT_CONFIG):
    """Usporedi studentski E2K s (potvrđenim) referentnim modelom.

    Vraća (df_res, summary) — kao _cached_compare_models u streamlit_app.
    """
    import model_compare

    df = model_compare.compare_models(student_e2k, ref_model, cfg)
    summary = model_compare.summarize_differences(df)
    return df, summary


# ---------------------------------------------------------------------------
# Render (Streamlit) — prima st kao argument radi testabilnosti/izolacije
# ---------------------------------------------------------------------------

# session_state ključevi wizarda
_SS = {
    "active": "wizard_active",
    "step": "wizard_step",
    "dxf": "wizard_dxf_bytes",
    "dxf_name": "wizard_dxf_name",
    "ref": "wizard_ref_model",
    "confirmed": "wizard_ref_confirmed",
    "edited": "wizard_edited_tables",
    "student": "wizard_student_e2k",
    "student_name": "wizard_student_name",
    "result": "wizard_compare_result",
    "n_stories": "wizard_n_stories",
    "story_h": "wizard_story_h",
}


def reset_wizard(st) -> None:
    """Očisti sve wizard ključeve iz session_state (izlaz/ponovni početak)."""
    for k in _SS.values():
        st.session_state.pop(k, None)


def _get_state(st) -> Dict[str, Any]:
    """Sastavi logičko stanje iz session_state za can_advance/next_step."""
    return {
        "step": st.session_state.get(_SS["step"], STEP_UPLOAD_DXF),
        "dxf_bytes": st.session_state.get(_SS["dxf"]),
        "ref_model": st.session_state.get(_SS["ref"]),
        "ref_confirmed": st.session_state.get(_SS["confirmed"], False),
        "student_e2k": st.session_state.get(_SS["student"]),
    }


def _render_progress(st, step: int) -> None:
    """Progres traka + naslovi koraka."""
    st.progress(progress_fraction(step))
    labels = []
    for i, s in enumerate(STEP_ORDER):
        mark = "✅" if STEP_ORDER.index(step) > i else ("▶️" if s == step else "•")
        labels.append("%s %d. %s" % (mark, i + 1, STEP_TITLES[s]))
    st.caption("  |  ".join(labels))


def _nav_buttons(st, state: Dict[str, Any]) -> None:
    """Gumbi Natrag / Dalje ovisno o mogućnosti prijelaza."""
    c1, c2, _ = st.columns([1, 1, 3])
    step = state["step"]
    if STEP_ORDER.index(step) > 0:
        if c1.button("← Natrag", key="wiz_prev", use_container_width=True):
            st.session_state[_SS["step"]] = prev_step(state)
            st.rerun()
    if step != STEP_COMPARE:
        disabled = not can_advance(state)
        if c2.button("Dalje →", key="wiz_next", type="primary",
                     use_container_width=True, disabled=disabled):
            st.session_state[_SS["step"]] = next_step(state)
            st.rerun()


def _render_compare_result(st, df_cmp, summary) -> None:
    counts = summary["counts"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Podudarni", counts["match"])
    m2.metric("Nedostaje", counts["nedostaje"])
    m3.metric("Višak", counts["visak"])
    m4.metric("Kriva dimenzija", counts["mismatch"])
    if summary["ok"]:
        st.success("Studentski model se u potpunosti podudara s referentnim tlocrtom.")
    else:
        for msg in summary["messages"]:
            st.warning(msg)
    if df_cmp is not None and hasattr(df_cmp, "empty") and not df_cmp.empty:
        try:
            from ui_views import safe_df
            st.dataframe(safe_df(df_cmp), use_container_width=True, hide_index=True)
        except Exception:
            st.dataframe(df_cmp, use_container_width=True)


def render_wizard(st, cfg: Config = DEFAULT_CONFIG) -> None:
    """Nacrta cijeli vođeni tok (6 koraka). Poziva se iz streamlit_app.main()."""
    import ref_model_ui

    st.markdown("## Provjera studentskog modela prema tlocrtu")
    top_l, top_r = st.columns([4, 1])
    with top_r:
        if st.button("Natrag na početak", key="wiz_exit", use_container_width=True):
            reset_wizard(st)
            st.rerun()

    step = st.session_state.get(_SS["step"], STEP_UPLOAD_DXF)
    _render_progress(st, step)
    st.markdown("---")

    # ---- Korak 1: učitaj DXF tlocrt ----
    if step == STEP_UPLOAD_DXF:
        st.markdown("### 1. Učitajte DXF tlocrt")
        st.caption("Isti tlocrt koji profesor daje studentima kao referentni primjer.")
        up = st.file_uploader("DXF datoteka tlocrta", type=["dxf"], key="wiz_dxf_up")
        c1, c2 = st.columns(2)
        n_stories = c1.number_input("Broj etaža", min_value=1, max_value=50,
                                    value=int(st.session_state.get(_SS["n_stories"], 1)),
                                    step=1, key="wiz_n_stories_in")
        story_h = c2.number_input("Visina etaže (m)", min_value=2.0, max_value=6.0,
                                  value=float(st.session_state.get(_SS["story_h"], 3.0)),
                                  step=0.1, key="wiz_story_h_in")
        st.session_state[_SS["n_stories"]] = n_stories
        st.session_state[_SS["story_h"]] = story_h
        if up is not None:
            data = up.getvalue()
            # promjena datoteke -> odbaci prethodni generirani model/potvrdu
            if st.session_state.get(_SS["dxf_name"]) != up.name:
                st.session_state[_SS["dxf_name"]] = up.name
                for k in ("ref", "confirmed", "edited", "result"):
                    st.session_state.pop(_SS[k], None)
            st.session_state[_SS["dxf"]] = data
            st.success("Učitano: %s (%d bajtova)" % (up.name, len(data)))

    # ---- Korak 2: generiraj model ----
    elif step == STEP_GENERATE:
        st.markdown("### 2. Generirajte numerički model iz tlocrta")
        dxf_bytes = st.session_state.get(_SS["dxf"])
        if st.button("Generiraj numerički model iz učitanog tlocrta",
                     type="primary", key="wiz_gen_btn"):
            ui = {"n_stories": int(st.session_state.get(_SS["n_stories"], 1)),
                  "story_height": float(st.session_state.get(_SS["story_h"], 3.0))}
            try:
                rm = build_reference_model(dxf_bytes, cfg, ui)
                st.session_state[_SS["ref"]] = rm
                st.session_state.pop(_SS["edited"], None)
                st.session_state[_SS["confirmed"]] = False
            except Exception as e:  # noqa: BLE001
                st.error("Generiranje nije uspjelo: %s" % e)
        rm = st.session_state.get(_SS["ref"])
        if rm is not None:
            if rm["meta"].get("ok"):
                st.success("Model generiran.")
                for line in ref_model_ui.model_summary_text(rm):
                    st.markdown("- " + line)
            else:
                st.error("Greška: %s" % (rm["meta"].get("error") or "nepoznata"))

    # ---- Korak 3: dorada / dopuna ----
    elif step == STEP_REFINE:
        st.markdown("### 3. Doradite model (opcionalno)")
        st.caption("Ispravite dimenzije/pozicije, obrišite ili DODAJTE retke "
                   "za elemente koji nedostaju. Prazan redak: kliknite '+' u tablici.")
        rm = st.session_state.get(_SS["ref"]) or {}
        tables = ref_model_ui.editable_tables(rm)
        edited = dict(st.session_state.get(_SS["edited"], {}))
        for key, df_tab in tables.items():
            label = ref_model_ui.TYPE_LABELS_HR.get(key, key)
            with st.expander("%s (%d)" % (label, len(df_tab)),
                             expanded=(key == "columns")):
                edited[key] = st.data_editor(
                    df_tab, key="wiz_editor_%s" % key,
                    num_rows="dynamic", use_container_width=True)
        st.session_state[_SS["edited"]] = edited

    # ---- Korak 4: potvrdi ispravnost ----
    elif step == STEP_CONFIRM:
        st.markdown("### 4. Potvrdite ispravnost referentnog modela")
        rm = st.session_state.get(_SS["ref"]) or {}
        edited = st.session_state.get(_SS["edited"], {})
        final_model = ref_model_ui.apply_edits(rm, edited)
        st.session_state[_SS["ref"]] = final_model  # spremi dorađeni kao aktivni
        st.caption("Sažetak modela koji će služiti kao referenca za usporedbu:")
        for line in ref_model_ui.model_summary_text(final_model):
            st.markdown("- " + line)
        confirmed = st.checkbox(
            "Potvrđujem da je generirani referentni model ispravan.",
            value=bool(st.session_state.get(_SS["confirmed"], False)),
            key="wiz_confirm_chk")
        st.session_state[_SS["confirmed"]] = confirmed
        if confirmed:
            st.success("Referentni model je potvrđen. Nastavite na učitavanje "
                       "studentskog modela.")

    # ---- Korak 5: učitaj studentski E2K ----
    elif step == STEP_UPLOAD_E2K:
        st.markdown("### 5. Učitajte studentski ETABS model (.e2k)")
        up = st.file_uploader("E2K datoteka studentskog modela",
                              type=["e2k", "$et", "txt"], key="wiz_e2k_up")
        if up is not None:
            try:
                data = up.getvalue()
                if st.session_state.get(_SS["student_name"]) != up.name:
                    st.session_state[_SS["student_name"]] = up.name
                    st.session_state.pop(_SS["result"], None)
                st.session_state[_SS["student"]] = parse_e2k_bytes(data, cfg)
                st.success("Učitan studentski model: %s" % up.name)
            except Exception as e:  # noqa: BLE001
                st.error("Učitavanje E2K modela nije uspjelo: %s" % e)
                st.session_state.pop(_SS["student"], None)

    # ---- Korak 6: usporedba ----
    elif step == STEP_COMPARE:
        st.markdown("### 6. Usporedba sa studentskim modelom")
        rm = st.session_state.get(_SS["ref"]) or {}
        student = st.session_state.get(_SS["student"]) or {}
        if st.button("Pokreni usporedbu", type="primary", key="wiz_cmp_btn"):
            try:
                df_cmp, summary = run_comparison(student, rm, cfg)
                st.session_state[_SS["result"]] = (df_cmp, summary)
            except Exception as e:  # noqa: BLE001
                st.error("Usporedba nije uspjela: %s" % e)
        res = st.session_state.get(_SS["result"])
        if res is not None:
            df_cmp, summary = res
            _render_compare_result(st, df_cmp, summary)

    st.markdown("---")
    _nav_buttons(st, _get_state(st))
