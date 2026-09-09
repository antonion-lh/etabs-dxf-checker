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
    def file_uploader(self, *a, **k): return None
    def download_button(self, *a, **k): self.calls.append(("download_button", a))
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
