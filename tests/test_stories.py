import pytest
import pandas as pd
from phase1_e2k import parse_e2k
from phase3_validation import validate, Status
from config import Config

def test_stories_sample_building():
    e2k = parse_e2k("sample_building.e2k")
    assert "stories" in e2k
    assert len(e2k["stories"]) >= 2
    story_names = [s["name"] for s in e2k["stories"]]
    assert "Prizemlje" in story_names
    assert "1. Kat" in story_names

    cols = e2k["columns"]
    assert "story" in cols.columns
    c1 = cols[cols["name"] == "C1"].iloc[0]
    c4 = cols[cols["name"] == "C4_ROOF"].iloc[0]
    assert c1["story"] == "Prizemlje"
    assert c4["story"] == "1. Kat"

def test_stories_demo_skola():
    e2k = parse_e2k("demo_skola.e2k")
    assert "stories" in e2k
    walls = e2k["walls"]
    assert "story" in walls.columns
    assert len(walls["story"].dropna()) > 0
    assert any("story1" in str(w).lower() or "prizemlje" in str(w).lower() for w in walls["story"])
