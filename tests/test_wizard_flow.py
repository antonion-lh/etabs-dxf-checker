"""Testovi za wizard_flow.py — čista logika vođenog toka (koraci + prijelazi)."""
import os

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_dxf")
AB_ZGRADA = os.path.join(SAMPLE_DIR, "ab_zgrada.dxf")


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_exposes_api():
    import wizard_flow as wf
    for fn in ("initial_state", "can_advance", "next_step", "prev_step",
               "progress_fraction", "parse_e2k_bytes", "build_reference_model",
               "run_comparison"):
        assert hasattr(wf, fn)


def test_initial_state():
    import wizard_flow as wf
    s = wf.initial_state()
    assert s["step"] == wf.STEP_UPLOAD_DXF
    assert s["ref_confirmed"] is False
    assert s["ref_model"] is None


def test_cannot_advance_without_dxf():
    import wizard_flow as wf
    s = wf.initial_state()
    assert wf.can_advance(s) is False        # nema DXF-a
    assert wf.next_step(s) == wf.STEP_UPLOAD_DXF  # ostaje na istom


def test_advance_after_dxf_uploaded():
    import wizard_flow as wf
    s = wf.initial_state()
    s["dxf_bytes"] = b"nesto"
    assert wf.can_advance(s) is True
    assert wf.next_step(s) == wf.STEP_GENERATE


def test_generate_requires_ok_model():
    import wizard_flow as wf
    s = wf.initial_state()
    s["step"] = wf.STEP_GENERATE
    s["ref_model"] = {"meta": {"ok": False, "error": "x"}}
    assert wf.can_advance(s) is False
    s["ref_model"] = {"meta": {"ok": True}}
    assert wf.can_advance(s) is True
    assert wf.next_step(s) == wf.STEP_REFINE


def test_refine_always_advances():
    import wizard_flow as wf
    s = wf.initial_state()
    s["step"] = wf.STEP_REFINE
    assert wf.can_advance(s) is True
    assert wf.next_step(s) == wf.STEP_CONFIRM


def test_confirm_requires_confirmation():
    import wizard_flow as wf
    s = wf.initial_state()
    s["step"] = wf.STEP_CONFIRM
    assert wf.can_advance(s) is False
    s["ref_confirmed"] = True
    assert wf.next_step(s) == wf.STEP_UPLOAD_E2K


def test_e2k_step_requires_student_model():
    import wizard_flow as wf
    s = wf.initial_state()
    s["step"] = wf.STEP_UPLOAD_E2K
    assert wf.can_advance(s) is False
    s["student_e2k"] = {"columns": []}
    assert wf.can_advance(s) is True
    assert wf.next_step(s) == wf.STEP_COMPARE


def test_compare_is_last():
    import wizard_flow as wf
    s = wf.initial_state()
    s["step"] = wf.STEP_COMPARE
    assert wf.can_advance(s) is False
    assert wf.next_step(s) == wf.STEP_COMPARE  # nema dalje


def test_prev_step_never_below_zero():
    import wizard_flow as wf
    s = wf.initial_state()
    assert wf.prev_step(s) == wf.STEP_UPLOAD_DXF
    s["step"] = wf.STEP_REFINE
    assert wf.prev_step(s) == wf.STEP_GENERATE


def test_progress_fraction_increases():
    import wizard_flow as wf
    assert wf.progress_fraction(wf.STEP_UPLOAD_DXF) < wf.progress_fraction(wf.STEP_COMPARE)
    assert wf.progress_fraction(wf.STEP_COMPARE) == 1.0


def test_build_reference_model_real():
    import wizard_flow as wf
    from config import Config
    rm = wf.build_reference_model(_read_bytes(AB_ZGRADA), Config(),
                                  {"n_stories": 4, "story_height": 3.2})
    assert rm["meta"]["ok"] is True
    assert len(rm["columns"]) == 120


def test_end_to_end_logic():
    """Puni logički prolaz kroz sve korake bez UI-a."""
    import wizard_flow as wf
    from config import Config
    cfg = Config()
    s = wf.initial_state()

    # 1) DXF
    s["dxf_bytes"] = _read_bytes(AB_ZGRADA)
    s["step"] = wf.next_step(s)
    assert s["step"] == wf.STEP_GENERATE

    # 2) generiraj
    s["ref_model"] = wf.build_reference_model(s["dxf_bytes"], cfg,
                                              {"n_stories": 4, "story_height": 3.2})
    s["step"] = wf.next_step(s)
    assert s["step"] == wf.STEP_REFINE

    # 3) dorada (preskoči) -> 4) potvrdi
    s["step"] = wf.next_step(s)
    assert s["step"] == wf.STEP_CONFIRM
    s["ref_confirmed"] = True
    s["step"] = wf.next_step(s)
    assert s["step"] == wf.STEP_UPLOAD_E2K

    # 5) studentski E2K = sam referentni model (savršeno podudaranje očekivano visoko)
    #    ovdje samo potvrđujemo da run_comparison radi bez greške
    student = {"columns": __import__("pandas").DataFrame([
        {"name": "SC1", "element_type": "column", "x_match": 0.0, "y_match": 0.0,
         "centroid_x": 0.0, "centroid_y": 0.0, "width_mm": 400, "height_mm": 400,
         "story": "PRIZEMLJE", "section": "40/40"}])}
    s["student_e2k"] = student
    s["step"] = wf.next_step(s)
    assert s["step"] == wf.STEP_COMPARE

    # 6) usporedba
    df, summary = wf.run_comparison(s["student_e2k"], s["ref_model"], cfg)
    assert "counts" in summary
    assert summary["counts"]["ukupno"] >= 1


# --------------------------------------------------------------------------
# Zadatak 2: render_wizard s lažnim (fake) st — bez Streamlit runtimea
# --------------------------------------------------------------------------
class _FakeCol:
    def __init__(self, store):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def button(self, *a, **k):
        return False

    def number_input(self, *a, **k):
        return k.get("value", 0)

    def selectbox(self, label, options, **k):
        idx = k.get("index", 0)
        return options[idx] if options else None

    def metric(self, *a, **k):
        pass


class _FakeExpander(_FakeCol):
    def data_editor(self, df, *a, **k):
        return df


class FakeSt:
    """Minimalni lažni Streamlit koji bilježi pozive; ne crta ništa stvarno."""
    def __init__(self, session_state=None):
        self.session_state = session_state or {}
        self.calls = []

    # kontejneri
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeCol(self.session_state) for _ in range(n)]

    def expander(self, *a, **k):
        return _FakeExpander(self.session_state)

    # widgeti / prikaz
    def markdown(self, *a, **k): self.calls.append(("markdown", a))
    def caption(self, *a, **k): self.calls.append(("caption", a))
    def progress(self, *a, **k): self.calls.append(("progress", a))
    def success(self, *a, **k): self.calls.append(("success", a))
    def warning(self, *a, **k): self.calls.append(("warning", a))
    def error(self, *a, **k): self.calls.append(("error", a))
    def dataframe(self, *a, **k): self.calls.append(("dataframe", a))
    def metric(self, *a, **k): pass

    def button(self, *a, **k): return False
    def checkbox(self, *a, **k): return k.get("value", False)
    def number_input(self, *a, **k): return k.get("value", 0)
    def selectbox(self, label, options, **k): return options[k.get("index", 0)] if options else None
    def file_uploader(self, *a, **k): return None
    def data_editor(self, df, *a, **k): return df

    def rerun(self): self.calls.append(("rerun", ()))


def _render_at_step(step, session_extra=None):
    import wizard_flow as wf
    from config import Config
    ss = {wf._SS["step"]: step}
    if session_extra:
        ss.update(session_extra)
    st = FakeSt(ss)
    wf.render_wizard(st, Config())
    return st


def test_render_step1_no_crash():
    import wizard_flow as wf
    st = _render_at_step(wf.STEP_UPLOAD_DXF)
    assert any(c[0] == "markdown" for c in st.calls)


def test_render_each_step_no_crash():
    import wizard_flow as wf
    for step in wf.STEP_ORDER:
        st = _render_at_step(step)
        assert any(c[0] == "progress" for c in st.calls)


def test_render_compare_shows_result():
    import wizard_flow as wf
    import pandas as pd
    summary = {"counts": {"match": 2, "mismatch": 0, "nedostaje": 1, "visak": 0,
                          "ukupno": 3}, "messages": ["Nedostaje 1 stup."], "ok": False}
    df = pd.DataFrame([{"element_type": "column", "status": "Status.DXF_ONLY"}])
    st = _render_at_step(wf.STEP_COMPARE, {wf._SS["result"]: (df, summary)})
    # rezultat prikazan: barem jedno upozorenje iz poruka
    assert any(c[0] == "warning" for c in st.calls)


def test_reset_wizard_clears_state():
    import wizard_flow as wf
    ss = {wf._SS["step"]: wf.STEP_COMPARE, wf._SS["dxf"]: b"x",
          wf._SS["ref"]: {"meta": {"ok": True}}, wf._SS["confirmed"]: True}
    st = FakeSt(ss)
    wf.reset_wizard(st)
    for k in wf._SS.values():
        assert k not in st.session_state
