"""Testovi za batch_flow.py — batch provjera više studentskih modela."""
import os

import pandas as pd

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_dxf")
AB_ZGRADA = os.path.join(SAMPLE_DIR, "ab_zgrada.dxf")
ROOT = os.path.dirname(os.path.dirname(__file__))


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def test_exposes_api():
    import batch_flow as bf
    for fn in ("run_batch", "batch_statistics", "load_reference", "render_batch",
               "reset_batch"):
        assert hasattr(bf, fn)


def test_load_reference_from_dxf():
    import batch_flow as bf
    from config import Config
    rm = bf.load_reference(dxf_bytes=_read(AB_ZGRADA), cfg=Config(),
                           user_input={"n_stories": 1})
    assert rm["meta"]["ok"] is True
    assert len(rm["columns"]) == 120


def test_load_reference_none():
    import batch_flow as bf
    from config import Config
    rm = bf.load_reference(cfg=Config())
    assert rm["meta"]["ok"] is False


def test_run_batch_with_e2k():
    import batch_flow as bf
    from config import Config
    cfg = Config()
    ref = bf.load_reference(dxf_bytes=_read(AB_ZGRADA), cfg=cfg,
                            user_input={"n_stories": 1})
    e2k = _read(os.path.join(ROOT, "sample_building.e2k"))
    df = bf.run_batch(ref, [("student1.e2k", e2k), ("student2.e2k", e2k)], cfg)
    assert len(df) == 2
    assert "ocjena" in df.columns
    assert set(df["student"]) == {"student1.e2k", "student2.e2k"}


def test_run_batch_bad_e2k_graceful():
    import batch_flow as bf
    from config import Config
    ref = bf.load_reference(dxf_bytes=_read(AB_ZGRADA), cfg=Config(),
                            user_input={"n_stories": 1})
    df = bf.run_batch(ref, [("smece.e2k", b"nije e2k sadrzaj")], Config())
    assert len(df) == 1  # ne ruši se


def test_batch_statistics():
    import batch_flow as bf
    df = pd.DataFrame([
        {"student": "A", "ocjena": 5, "tocnost_%": 95.0},
        {"student": "B", "ocjena": 3, "tocnost_%": 65.0},
        {"student": "C", "ocjena": None, "tocnost_%": None},
    ])
    stats = bf.batch_statistics(df)
    assert stats["n_students"] == 3
    assert stats["avg_grade"] == 4.0            # (5+3)/2
    assert stats["avg_accuracy"] == 80.0        # (95+65)/2
    assert stats["distribution"] == {3: 1, 5: 1}
    assert stats["n_failed"] == 1


def test_batch_statistics_empty():
    import batch_flow as bf
    stats = bf.batch_statistics(pd.DataFrame())
    assert stats["n_students"] == 0
    assert stats["avg_grade"] is None


# --------------------------------------------------------------------------
# Zadatak 2: render_batch s lažnim st
# --------------------------------------------------------------------------
class _FakeCol:
    def __init__(self, store): self._store = store
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def button(self, *a, **k): return False
    def number_input(self, *a, **k): return k.get("value", a[3] if len(a) > 3 else 1)
    def selectbox(self, label, options, **k): return options[k.get("index", 0)] if options else None
    def segmented_control(self, label, options, **k): return k.get("default", options[0] if options else None)
    def metric(self, *a, **k): pass
    def file_uploader(self, *a, **k): return None


class FakeSt:
    def __init__(self, session_state=None):
        self.session_state = session_state or {}
        self.calls = []

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeCol(self.session_state) for _ in range(n)]

    def markdown(self, *a, **k): self.calls.append(("markdown", a))
    def caption(self, *a, **k): pass
    def success(self, *a, **k): self.calls.append(("success", a))
    def error(self, *a, **k): self.calls.append(("error", a))
    def warning(self, *a, **k): pass
    def dataframe(self, *a, **k): self.calls.append(("dataframe", a))
    def metric(self, *a, **k): pass
    def button(self, *a, **k): return False
    def number_input(self, *a, **k): return k.get("value", 1)
    def selectbox(self, label, options, **k): return options[k.get("index", 0)] if options else None
    def segmented_control(self, label, options, **k): return k.get("default", options[0] if options else None)
    def file_uploader(self, *a, **k): return None
    def download_button(self, *a, **k): self.calls.append(("download_button", a))
    def bar_chart(self, *a, **k): self.calls.append(("bar_chart", a))
    def caption(self, *a, **k): pass
    def info(self, *a, **k): self.calls.append(("info", a))
    def success(self, *a, **k): self.calls.append(("success", a))

    def progress(self, *a, **k):
        class _P:
            def progress(self_, *pa, **pk): pass
        return _P()

    def empty(self):
        outer = self
        class _E:
            def caption(self_, *a, **k): pass
            def progress(self_, *a, **k): pass
        return _E()

    def rerun(self): pass


def test_render_batch_no_crash():
    import batch_flow as bf
    from config import Config
    st = FakeSt()
    bf.render_batch(st, Config())
    assert any(c[0] == "markdown" for c in st.calls)


def test_render_batch_shows_results():
    import batch_flow as bf
    from config import Config
    df = pd.DataFrame([{"student": "A", "ocjena": 4, "tocnost_%": 80.0,
                        "podudarni": 4, "nedostaje": 1, "visak": 0, "kriva_dimenzija": 0}])
    st = FakeSt({bf._SS["results"]: df})
    bf.render_batch(st, Config())
    assert any(c[0] == "dataframe" for c in st.calls)
    assert any(c[0] == "download_button" for c in st.calls)


def test_reset_batch():
    import batch_flow as bf
    st = FakeSt({bf._SS["active"]: True, bf._SS["ref"]: {"x": 1},
                 bf._SS["results"]: "y"})
    bf.reset_batch(st)
    for k in bf._SS.values():
        assert k not in st.session_state


# --------------------------------------------------------------------------
# UX popravci: progress_cb u run_batch + histogram render
# --------------------------------------------------------------------------
def test_run_batch_progress_callback():
    import batch_flow as bf
    from config import Config
    ref = bf.load_reference(dxf_bytes=_read(AB_ZGRADA), cfg=Config(),
                            user_input={"n_stories": 1})
    e2k = _read(os.path.join(ROOT, "sample_building.e2k"))
    calls = []
    bf.run_batch(ref, [("a.e2k", e2k), ("b.e2k", e2k)], Config(),
                 progress_cb=lambda i, n, name: calls.append((i, n, name)))
    assert len(calls) >= 2   # pozvan za svaki student + završni


def test_render_batch_histogram():
    import batch_flow as bf
    from config import Config
    df = pd.DataFrame([
        {"student": "A", "ocjena": 5, "tocnost_%": 95.0, "podudarni": 5,
         "nedostaje": 0, "visak": 0, "kriva_dimenzija": 0},
        {"student": "B", "ocjena": 3, "tocnost_%": 65.0, "podudarni": 3,
         "nedostaje": 1, "visak": 0, "kriva_dimenzija": 0},
    ])
    st = FakeSt({bf._SS["results"]: df})
    bf.render_batch(st, Config())
    assert any(c[0] == "bar_chart" for c in st.calls)


# --------------------------------------------------------------------------
# UX popravak 2: batch potvrda izlaza (ne briše odmah)
# --------------------------------------------------------------------------
def test_batch_exit_needs_confirmation():
    import batch_flow as bf
    from config import Config

    class ClickExitSt(FakeSt):
        def button(self, *a, **k):
            return k.get("key") == "batch_exit"

    st = ClickExitSt({bf._SS["ref"]: {"meta": {"ok": True, "source": "dxf"}}})
    bf.render_batch(st, Config())
    # prvi klik samo postavlja potvrdu, referenca NIJE obrisana
    assert st.session_state.get("batch_confirm_exit") is True
    assert bf._SS["ref"] in st.session_state


# --------------------------------------------------------------------------
# UX popravak 3: upozorenje o trajanju za velike batcheve
# --------------------------------------------------------------------------
def test_batch_large_upload_warning():
    import batch_flow as bf
    from config import Config

    class _Up:
        def __init__(self, name): self.name = name
        def getvalue(self): return b"x"

    class ManyUploadsSt(FakeSt):
        def file_uploader(self, *a, **k):
            if k.get("key") == "batch_e2k_up":
                return [_Up("s%d.e2k" % i) for i in range(12)]  # 12 datoteka
            return None

    st = ManyUploadsSt({bf._SS["ref"]: {"meta": {"ok": True, "source": "dxf"}}})
    bf.render_batch(st, Config())
    # info poruka o trajanju prikazana
    assert any(c[0] == "info" for c in st.calls)
