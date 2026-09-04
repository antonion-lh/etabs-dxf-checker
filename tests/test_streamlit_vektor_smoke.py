"""Smoke test for the Vektorizacija tab wiring in streamlit_app (Task 11)."""
import warnings


def test_raster_vectorize_public_api_present():
    """Core vectorize entrypoint and Params dataclass must exist."""
    from raster_vectorize import vectorize_floorplan, Params
    assert callable(vectorize_floorplan)
    p = Params()
    assert p.layer_name == "VEKTOR_ZID"


def test_streamlit_app_exposes_cached_vectorize():
    """streamlit_app must import cleanly and expose the cache wrapper."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import streamlit_app
    assert hasattr(streamlit_app, "_cached_vectorize")
    assert callable(streamlit_app._cached_vectorize)
