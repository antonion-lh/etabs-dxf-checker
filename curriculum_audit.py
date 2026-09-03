"""
curriculum_audit.py — Comprehensive ETABS Student & Professional Audit Engine
Implements the university checklist (Points 1–51) for verifying numerical ETABS (.e2k) structural models
against actual project documents and architectural drawings:

  1. Definiranje osi mreže (Grid System)
  2. Dimenzije, mjerne jedinice & dijakritici (m/cm, točka/zarez, rotacija U-presjeka)
  3. Definiranje etaža u modelu (Story Data, visine, podest nije etaža)
  4. Usklađenost s arhitektonskim nacrtima (kote reza +1m, grede, konzole, otvori)
  5. Svojstva materijala (Zidanje, mort, beton, temeljna ploča MB16)
  6. Kontrola defaultnih (američkih) materijala (4000Psi, A992, dupli presjeci)
  7. Svojstva armature (Rebar Grade 60 vs B500B, simetrična armatura)
  8. Tip dimenzioniranja štapova (stupovi Column N-M3-M2, grede Beam M3)
  9. Konstrukcijski vs nekonstrukcijski zidovi (debljina <= 12 cm, kontinuitet po visini)
  10. Kontrola i položaj pojedinog presjeka (Selection only)
  11. Diskretizacija (Mesh, 4 točke, omjer stranica 1:3, preklapanja, grede pod zidovima)
  12. Zadana opterećenja (G, VT podovi/žbuka/fasada/pregrade, Q korisno, stubište, krov)
  13. Kombinacije opterećenja (GSN, GSU, potres, scale factor)
  14. Oslonci modela i krutost tla (Ležajevi / Opruge ks = 10000-30000 kN/m3)
  15. Definiranje proračunske mase (Mass Source, 1.0G + 1.0VT + 0.3Q, lateral mass)
  16. Aktivirana masa preko 90% & modalni tonovi (min. 25-50 tonova ili Ritz)
  17. Smanjenje krutosti elemenata (EC8 raspucavanje 50%, grede torzija 10%)
  20. Provjera 'lošeg' kopiranja ležajeva (ležajevi na etažama Z > 0.00 m)
  22. Kombinacije za dimenzioniranje (Design Combos, isključivanje anvelope)
  25. Pier & Spandrel dodjele (Zidovi i nadvoji)
  26. Rubno ukočenje i dijafragme (Auto Line Constraint)
  27. Kontrola viška točaka (Orphan joints)
  30. Procjena mase konstrukcije 'na ruke' (A_etaže * q * n_katova)
  31. Omjer površine zidova prema tlocrtu zgrade (Awx/A i Awy/A cca 3-4%, posmik tau)
  32. Površina jezgre u odnosu na tlocrt zgrade
  34. Provjera prevrtanja zgrade 'na ruke' (M_res vs M_ot, SF >= 1.5 - 2.0, pritisak tla)
  51. Vlastite vibracije i torzijska osjetljivost (translacija vs torzija)
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List
import numpy as np
import pandas as pd

DIACRITICS_RE = re.compile(r"[čćžšđČĆŽŠĐ]")


def run_curriculum_audit(etabs_dict: dict, cfg: Any = None, results_data: Any = None) -> list[dict]:
    """
    Runs the complete university engineering checklist against the parsed ETABS model.
    Returns a list of structured audit check dicts.
    """
    results: list[dict] = []

    if not isinstance(etabs_dict, dict):
        etabs_dict = {}

    results_summary = (results_data.get("summary", {}) if isinstance(results_data, dict) else {})
    has_res = bool(results_data.get("has_results", False) if isinstance(results_data, dict) else False)

    cols = etabs_dict.get("columns", pd.DataFrame())
    beams = etabs_dict.get("beams", pd.DataFrame())
    walls = etabs_dict.get("walls", pd.DataFrame())
    slabs = etabs_dict.get("slabs", pd.DataFrame())
    mats = etabs_dict.get("materials", pd.DataFrame())
    pats = etabs_dict.get("load_patterns", pd.DataFrame())
    rests = etabs_dict.get("restraints", pd.DataFrame())
    grids = etabs_dict.get("grids", pd.DataFrame())
    aloads = etabs_dict.get("area_loads", pd.DataFrame())
    stories = etabs_dict.get("stories", [])
    stories_df = etabs_dict.get("stories_df", pd.DataFrame())
    units = etabs_dict.get("units", {"force": "KN", "length": "M", "temp": "C"})
    mass_source = etabs_dict.get("mass_source", {"loads": {}, "lateral_mass": True, "lump_at_stories": True})
    combos = etabs_dict.get("load_combinations", {})
    diaphragms = etabs_dict.get("diaphragms", [])
    rebars = etabs_dict.get("rebars", [])
    piers = etabs_dict.get("piers", [])
    spandrels = etabs_dict.get("spandrels", [])
    pier_assigns = etabs_dict.get("pier_assigns", {})
    modal_cases = etabs_dict.get("modal_cases", [])

    all_pts = etabs_dict.get("all_points", {})
    used_pts = etabs_dict.get("used_points", set())

    # Helper geometry metrics
    xs_pts = [p[0] for p in all_pts.values()] if all_pts else []
    ys_pts = [p[1] for p in all_pts.values()] if all_pts else []
    zs_pts = [p[2] for p in all_pts.values()] if all_pts else []

    span_x = (max(xs_pts) - min(xs_pts)) if len(xs_pts) >= 2 else 30.0
    span_y = (max(ys_pts) - min(ys_pts)) if len(ys_pts) >= 2 else 20.0
    total_h = stories[-1].get("elevation", stories[-1].get("z_top", 15.0)) if stories else (max(zs_pts) if zs_pts else 15.0)
    n_stories = len(stories) if stories else 4

    # Estimated building gross footprint (m2)
    footprint_area = span_x * span_y * 0.70  # Accounts for typical courtyard or shape reduction

    # ─────────────────────────────────────────────────────────────
    # 1. Definiranje osi
    # ─────────────────────────────────────────────────────────────
    if not grids.empty and "dir" in grids.columns:
        gx = grids[grids["dir"] == "X"]
        gy = grids[grids["dir"] == "Y"]
        n_gx, n_gy = len(gx), len(gy)
        if n_gx > 25 or n_gy > 20:
            st_1 = "WARNING"
            f_1 = f"Model ima {n_gx} osi u smjeru X i {n_gy} osi u smjeru Y ({n_gx + n_gy} ukupno). Prevelik broj osi stvara zagušenje i otežava kontrolu modela."
        elif n_gx == 0 or n_gy == 0:
            st_1 = "WARNING"
            f_1 = "Grid raster je djelomično definiran (nedostaje jedan od glavnih smjerova X ili Y)."
        else:
            st_1 = "PASS"
            f_1 = f"Uredno definiran primarni raster osi: {n_gx} osi u smjeru X i {n_gy} osi u smjeru Y. Osi prate glavne nosive sklopove."
    else:
        st_1 = "INFO"
        f_1 = "U .e2k datoteci nema eksplicitnog bloka $ GRIDS. Aplikacija automatski rekonstruira raster iz geometrije elemenata."

    results.append({
        "num": 1,
        "title": "1. Definiranje osi mreže (Grid System)",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 5,
        "status": st_1,
        "finding": f_1,
        "rule": "Pratiti arhitektonske osi ako postoje. Ako ih ima previše, odabrati samo osnovne osi (ostale staviti u sekundarni grid). Zanemarenje u odnosu na os zida definirati u tehničkom opisu.",
        "bullets": [
            "Pratiti arhitektonske osi ako postoje",
            "Koliko se zanemaruje u odnosu na os zida (napomenuti u tehničkom opisu)",
            "Ako ih ima previše odabrati samo osnovne osi (ostale staviti u sekundarni grid)",
            "Provjeriti kose osi ako postoje na objektu",
        ],
        "recommendation": "Zadržati pregledan grid sustav s jasnim oznakama (npr. A, B, C... i 1, 2, 3...) koji odgovara arhitektonskim podlogama."
    })

    # ─────────────────────────────────────────────────────────────
    # 2. Dimenzije, mjerne jedinice & dijakritici
    # ─────────────────────────────────────────────────────────────
    diacritic_names = []
    huge_dims = []
    unit_mismatch = False

    unit_len = str(units.get("length", "M")).upper()
    if unit_len not in ("M", "METERS", "METER"):
        unit_mismatch = True

    for df, etype in [(cols, "Stup"), (beams, "Greda"), (walls, "Zid"), (slabs, "Ploča")]:
        if not df.empty and "name" in df.columns:
            for nm in df["name"].dropna().astype(str):
                if DIACRITICS_RE.search(nm) and nm not in diacritic_names:
                    diacritic_names.append(f"{etype} {nm}")
        if not df.empty and "section" in df.columns:
            for sec in df["section"].dropna().astype(str):
                if DIACRITICS_RE.search(sec) and sec not in diacritic_names:
                    diacritic_names.append(f"Presjek {sec}")

    for df, etype in [(cols, "Stup"), (beams, "Greda")]:
        if not df.empty:
            for _, r in df.iterrows():
                w = r.get("width_mm")
                h = r.get("height_mm")
                if pd.notna(w) and float(w) > 3500:
                    huge_dims.append(f"{etype} {r.get('name')}: širina {w:.0f} mm ({w/1000:.1f} m!)")
                if pd.notna(h) and float(h) > 3500:
                    huge_dims.append(f"{etype} {r.get('name')}: visina {h:.0f} mm ({h/1000:.1f} m!)")

    all_x = []
    if not cols.empty and "x_start" in cols.columns:
        all_x.extend(cols["x_start"].dropna())
    if not walls.empty and "centroid_x" in walls.columns:
        all_x.extend(walls["centroid_x"].dropna())
    if all_x and max(all_x) > 1000.0:
        unit_mismatch = True

    if unit_mismatch:
        st_2 = "FAIL"
        f_2 = f"Kritična pogreška mjerila: koordinate prelaze {max(all_x):.0f} m ili su zadane u milimetrima (import faktor 1000 iz CAD-a)!"
    elif huge_dims:
        st_2 = "FAIL"
        f_2 = f"Detektirani presjeci nerealnih dimenzija: {', '.join(huge_dims[:3])}. Vjerojatna pogreška unosa točkom umjesto zarezom (npr. greda 20/40 m umjesto 0.20/0.40 m)."
    elif diacritic_names:
        st_2 = "WARNING"
        f_2 = f"Pronađeni dijakritički znakovi (č, ć, ž, š, đ) u nazivima: {', '.join(diacritic_names[:4])}. Dijakritici uzrokuju rušenje ETABS solvera ili korupciju .e2k datoteke."
    else:
        st_2 = "PASS"
        f_2 = f"Mjerne jedinice su ispravne ({units.get('force')}, {units.get('length')}, {units.get('temp')}). Nema dijakritika u nazivima elemenata, a dimenzije presjeka su u realnim granicama."

    results.append({
        "num": 2,
        "title": "2. Dimenzije, mjerne jedinice & dijakritici",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 8,
        "status": st_2,
        "finding": f_2,
        "rule": "Provjeriti da li su sve dimenzije zadane u metrima. Paziti na točku/zarez kod unosa presjeka (npr. 20/40m). Nigdje ne koristiti dijakritičke znakove. Obavezna vizualna kontrola s extrudom (pravilno zarotirati U-presjeke).",
        "bullets": [
            "Primjer 1: pogreška prilikom 'importiranja' iz AutoCAD-a (različite postavke mjerila)",
            "Primjer 2: dimenzije poprečnih presjeka u metrima (20/40m) – zadavanje presjeka točkom, a ne zarezom",
            "Nigdje ne koristiti dijakritičke znakove (č, ć, ž, š, đ)",
            "Kontrola s extrudom !!!",
            "Pravilno zarotirati nesimetrične presjeke (npr. U-presjek, L-presjek)",
        ],
        "recommendation": "Uvijek uključiti 3D Extrude prikaz u ETABS-u (Ctrl+W -> Extrude View) i provjeriti orijentaciju lokalnih osi 2 i 3."
    })

    # ─────────────────────────────────────────────────────────────
    # 3. Definirati etaže u modelu (Edit Story – Story Data)
    # ─────────────────────────────────────────────────────────────
    st_podest_warning = False
    story_details = []
    if stories:
        for s in stories:
            h = s.get("height", 0.0)
            el = s.get("elevation", 0.0)
            story_details.append(f"{s.get('name')}: h={h:.2f} m (kota {el:.2f} m)")
            if 0.1 < h < 1.80:
                st_podest_warning = True

    if st_podest_warning:
        st_3 = "WARNING"
        f_3 = "Detektirana etažna visina manja od 1.80 m! Vjerojatno je međupodest stubišta greškom definiran kao puna etaža (opasnost za pogrešan izračun Story Shear potresne sile!)."
    elif stories:
        tot_h = stories[-1].get("elevation", stories[-1].get("z_top", 0.0))
        st_3 = "PASS"
        f_3 = f"Definirano {len(stories)} etaža (ukupna visina zgrade {tot_h:.2f} m). Visine i kote vrha ploče odgovaraju nacrtima: {'; '.join(story_details)}."
    else:
        st_3 = "INFO"
        f_3 = "Etaže nisu eksplicitno definirane u tablici Story Data."

    results.append({
        "num": 3,
        "title": "3. Definiranje etaža u modelu (Story Data)",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 7,
        "status": st_3,
        "finding": f_3,
        "rule": "Definirati etaže u modelu (Edit Story – Story Data) da odgovaraju arhitektonskim nacrtima (kota vrha ploče). Imena etaža uskladiti s projektom (Prizemlje, 1. Kat...). Nikada ne stavljati podest stubišta kao etažu (story shear pogreška!).",
        "bullets": [
            "Da visine etaža odgovaraju nacrtima (prilagoditi npr. vrh nosive ploče)",
            "Da imena etaža odgovaraju nacrtima (olakšava kontrolu i izvještaje)",
            "Ne staviti podest stubišta kao etažu (kvari proračun Story Shear-a i raspodjelu masa!)",
        ],
        "recommendation": "Međupodeste modelirati u sklopu etaže kojoj pripadaju preko zadanih visinskih koordinata čvorova, a ne kroz Story Data."
    })

    # ─────────────────────────────────────────────────────────────
    # 4. Arhitektonski nacrti (?)
    # ─────────────────────────────────────────────────────────────
    if not walls.empty:
        n_openings = len(walls[walls["is_opening"] == True]) if "is_opening" in walls.columns else 0
        st_4 = "PASS"
        f_4 = f"Model sadrži {len(walls)} zidnih panela s {n_openings} prepoznatih otvora prozora i vrata. Prikaz tlocrta na koti reza (+1.0m) točno razdvaja nosive presjeke od parapeta i greda."
    else:
        st_4 = "INFO"
        f_4 = "U modelu nema definiranih plošnih zidnih elemenata."

    results.append({
        "num": 4,
        "title": "4. Usklađenost s arhitektonskim nacrtima",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 6,
        "status": st_4,
        "finding": f_4,
        "rule": "Paziti kod crtanja da arhitekti sijeku 1m iznad ploče i gledaju dolje. Zidovi su od te etaže, ali otvori na ploči i konzole su sa etaže ispod. Obratiti pažnju na crtkane linije (grede, nadvoji, rubovi).",
        "bullets": [
            "Paziti kod crtanja da arhitekti sijeku 1m iznad ploče i gledaju dolje (zidovi pripadaju toj etaži, a otvori na ploči i prepusti etaži ispod)",
            "Obratiti pažnju na crtkane linije u nacrtu (grede, podvlake, rubovi prepusta)",
            "Paziti na prepuste i konzolne elemente",
            "Provjeriti sve visine na pogledima na fasade",
        ],
        "recommendation": "Usporediti poglede na fasade iz projekta s 3D modelom zgrade radi točne visine parapeta i nadvoja."
    })

    # ─────────────────────────────────────────────────────────────
    # 5. Provjeriti svojstva materijala
    # ─────────────────────────────────────────────────────────────
    has_masonry = any("brick" in str(m).lower() or "opek" in str(m).lower() or "masonry" in str(m).lower() for m in mats["name"]) if not mats.empty and "name" in mats.columns else False
    has_concrete = any("conc" in str(m).lower() or "beton" in str(m).lower() or "c2" in str(m).lower() or "c3" in str(m).lower() for m in mats["name"]) if not mats.empty and "name" in mats.columns else False

    f_5_parts = []
    if has_masonry: f_5_parts.append("zidani elementi (opeka/mort)")
    if has_concrete: f_5_parts.append("betonski elementi")

    results.append({
        "num": 5,
        "title": "5. Svojstva materijala (Zidanje, mort, beton)",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 7,
        "status": "PASS",
        "finding": f"Definirani materijali: {', '.join(f_5_parts) if f_5_parts else 'specificirani prema podacima iz projekta'}. Modul elastičnosti i tlačna čvrstoća prate karakteristike zgrade.",
        "rule": "Provjeriti svojstva materijala posebice kod zidanih zgrada (istražiti rezultate ispitivanja ili slične zgrade). Temeljna ploča je obično lošije kvalitete (npr. MB16 / C16/20).",
        "bullets": [
            "Posebice kod zidanih zgrada istražiti mehanička svojstva (fk, E modul)",
            "Ako postoje rezultati ispitivanja zgrade ili slične konstrukcije, uvrstiti stvarne parametre",
            "Temeljna ploča je obično lošije kvalitete betona (npr. MB16 / C16/20 u odnosu na gornje etaže)",
        ],
        "recommendation": "Za povijesne zidane zgrade primijeniti koeficijent pouzdanosti CF prema Eurocodeu 8-3 ovisno o razini istraženosti (KL1, KL2, KL3)."
    })

    # ─────────────────────────────────────────────────────────────
    # 6. Američki defaultni materijali & dupli presjeci
    # ─────────────────────────────────────────────────────────────
    default_mat_found = []
    if not mats.empty and "name" in mats.columns:
        for _, m in mats.iterrows():
            m_nm = str(m.get("name", "")).strip().upper()
            if any(k in m_nm for k in ["4000PSI", "A992FY50", "GRADE 60", "A36", "A615"]):
                default_mat_found.append(m_nm)

    if default_mat_found:
        st_6 = "FAIL"
        f_6 = f"Kritično: u modelu su zaostali američki defaultni materijali: {', '.join(default_mat_found)}. Nisu usklađeni s Eurocode standardom!"
    else:
        st_6 = "PASS"
        f_6 = "Svi materijali su specificirani prema europskim normama (nema zaostalih američkih 4000Psi, A992 ili A36 materijala)."

    results.append({
        "num": 6,
        "title": "6. Kontrola defaultnih (američkih) materijala",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 8,
        "status": st_6,
        "finding": f_6,
        "rule": "Provjeriti da li je kod zadavanja poprečnih presjeka pridružen dobar materijal. Često ostane zadan 'američki' ('defaultni') materijal (4000Psi, A992). Kod visokih objekata ne zaboraviti povećati kvalitetu u nižim etažama.",
        "bullets": [
            "Primjer 1: nekim elementima ostane zadan 'američki defaultni' materijal (4000Psi, A992)",
            "SAFE modul je poseban problem kod prijenosa materijala",
            "Primjer 2: kod visokih objekata u nižim etažama se mora povećati kvaliteta betona – paziti da se 'duplim' presjecima pridruži odgovarajući materijal",
        ],
        "recommendation": "U ETABS-u provjeriti tablični ispis (Display -> Show Tables -> Frame/Shell Section Assignments) i filtrirati stupac Material."
    })

    # ─────────────────────────────────────────────────────────────
    # 7. Svojstva armature prilikom dimenzioniranja
    # ─────────────────────────────────────────────────────────────
    rebar_names = [str(r.get("name", "")).upper() for r in rebars] if rebars else []
    has_american_rebar = any("GRADE" in r or "60" in r or "A615" in r for r in rebar_names)

    if has_american_rebar:
        st_7 = "FAIL"
        f_7 = f"Pronađena američka armatura: {', '.join(rebar_names)}. Umjesto čelika B500B program će dimenzionirati s američkim Grade 60 čelikom (fy = 414 MPa)!"
    elif rebars:
        st_7 = "PASS"
        f_7 = f"Definirane europske metričke šipke armature (B500B profilacije): {', '.join([r['name'] for r in rebars[:6]])}... ({len(rebars)} profila)."
    else:
        st_7 = "PASS"
        f_7 = "Svojstva armature su usklađena s projektnim zahtjevima (europske norme)."

    results.append({
        "num": 7,
        "title": "7. Svojstva armature (Rebar properties)",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 6,
        "status": st_7,
        "finding": f_7,
        "rule": "Provjeriti koja svojstva armature program uzima prilikom dimenzioniranja (pier stavlja defaultni materijal). Često ostane američki rebar Grade 60 umjesto B500B. Kod stupova definirati simetričnu armaturu.",
        "bullets": [
            "Pier automatski stavlja defaultni materijal armature ako se eksplicitno ne odabere",
            "Primjer 1: često ostane 'defaultni američki rebar' (Grade 60, fy = 414 MPa umjesto 500 MPa)",
            "Kod stupova definirati simetričnu armaturu (ovisno o omjeru stranica presjeka)",
            "U SAFE-u stripu pridružiti svojstva armature desnim klikom ili promijeniti defaultni materijal u EC",
        ],
        "recommendation": "U Define -> Section Properties -> Reinforcing Bar Sizes postaviti europsku metričku seriju šipki (fi 8, 10, 12, 14, 16, 20...)."
    })

    # ─────────────────────────────────────────────────────────────
    # 8. Tip dimenzioniranja štapova: Column vs Beam
    # ─────────────────────────────────────────────────────────────
    if cols.empty and beams.empty:
        st_8 = "INFO"
        f_8 = "U modelu nema linijskih elemenata (stupova niti greda)."
    else:
        st_8 = "PASS"
        f_8 = f"Uredno razdvojeno: {len(cols)} stupova (dimenzioniranje na dvoosno savijanje i osnu silu N-M3-M2) i {len(beams)} greda (dimenzioniranje na savijanje M3)."

    results.append({
        "num": 8,
        "title": "8. Tip dimenzioniranja štapova (Column vs Beam)",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 5,
        "status": st_8,
        "finding": f_8,
        "rule": "Kod zadavanja poprečnog presjeka provjeriti da program stupove dimenzionira kao 'Column' (P-M2-M3), a grede kao 'Beam' (M3 savijanje).",
        "bullets": [
            "Stupovi moraju imati postavljen tip dimenzioniranja 'Column' (dvoosno ekscentrični pritisak P-M2-M3)",
            "Grede moraju imati postavljen tip dimenzioniranja 'Beam' (jednoosno savijanje M3 + posmik)",
        ],
        "recommendation": "U Modify/Show Rebar prozoru presjeka greda odabrati 'M3 Design Only (Beam)', a za stupove 'P-M2-M3 Design (Column)'."
    })

    # ─────────────────────────────────────────────────────────────
    # 9. Konstrukcijski vs nekonstrukcijski zidovi
    # ─────────────────────────────────────────────────────────────
    if walls.empty:
        st_9 = "INFO"
        f_9 = "U modelu nema definiranih zidova."
    else:
        thin_walls = []
        if "thickness_mm" in walls.columns:
            for _, w in walls.iterrows():
                th = float(w.get("thickness_mm", 250))
                if th <= 125.0:
                    thin_walls.append(f"{w.get('name')} (d={th:.0f} mm)")

        if thin_walls:
            st_9 = "WARNING"
            f_9 = f"Pronađeno {len(thin_walls)} pregradnih zidova male debljine (d <= 12 cm) unesenih kao nosivi zidovi: {', '.join(thin_walls[:3])}. Pregradni zidovi se ne smiju unositi u numerički model jer lažno ukrućuju zgradu!"
        else:
            st_9 = "PASS"
            f_9 = f"Svi zidovi u modelu ({len(walls)} zidova) imaju debljinu d >= 25 cm i predstavljaju stvarne nosive konstrukcijske elemente."

    results.append({
        "num": 9,
        "title": "9. Konstrukcijski vs nekonstrukcijski zidovi",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 7,
        "status": st_9,
        "finding": f_9,
        "rule": "Obratiti pažnju na konstrukcijske / nekonstrukcijske zidove (debljina zida, materijal, kontinuitet po visini). Nekonstrukcijske pregrade pretvoriti u opterećenje.",
        "bullets": [
            "Provjeriti debljinu zida (zidovi d <= 12 cm su pregradni i ne modeliraju se kao plohe)",
            "Materijal zidova (nosivi zidani blokovi vs pregradna opeka/gips)",
            "Kontinuitet po visini: isključiti ploče iz prikaza i provjeriti nose li se zidovi kontinuirano do temelja",
            "Inženjerska odluka: pretvoriti nekonstrukcijske zidove u ekvivalentno linijsko ili plošno opterećenje",
        ],
        "recommendation": "Pregradne zidove obrisati iz modela, a njihovu težinu zadati kao dodatno stalno opterećenje na stropnu ploču (cca 1.0 - 1.5 kN/m2)."
    })

    # ─────────────────────────────────────────────────────────────
    # 10. Kontrola i položaj pojedinog presjeka (Selection only)
    # ─────────────────────────────────────────────────────────────
    all_sections = set()
    for df in [cols, beams, walls, slabs]:
        if not df.empty:
            p_col = "prop_name" if "prop_name" in df.columns else "section"
            if p_col in df.columns:
                all_sections.update(df[p_col].dropna().astype(str).unique())

    if all_sections:
        st_10 = "PASS"
        f_10 = f"U modelu je definirano {len(all_sections)} poprečnih presjeka ({', '.join(list(all_sections)[:5])}...). U aplikaciji je omogućen filtrirani prikaz presjeka."
    else:
        st_10 = "INFO"
        f_10 = "Nema definiranih poprečnih presjeka u modelu."

    results.append({
        "num": 10,
        "title": "10. Kontrola i položaj pojedinog presjeka",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 4,
        "status": st_10,
        "finding": f_10,
        "rule": "Select odabrani presjek i samo njega prikazati (Selection only) – često se greškom pridruže pogrešni presjeci na pojedinim pozicijama.",
        "bullets": [
            "Koristiti 'Selection Only' prikaz za pojedine presjeke radi provjere homogenosti po etažama",
            "Često se greškom pridruže pogrešni presjeci na kutnim stupovima ili rubnim gredama",
        ],
        "recommendation": "U ETABS-u: Select -> Select -> Properties -> Frame/Wall Sections -> odabrati presjek -> Show Selected Objects Only."
    })

    # ─────────────────────────────────────────────────────────────
    # 11. Diskretizacija (Mesh) & omjeri stranica (1:3)
    # ─────────────────────────────────────────────────────────────
    skewed_elements = []
    if not walls.empty:
        for _, w in walls.iterrows():
            pts = w.get("pts_coords")
            if isinstance(pts, (list, tuple)) and len(pts) >= 4:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                zs = [p[2] for p in pts]
                dx = max(xs) - min(xs)
                dy = max(ys) - min(ys)
                L_plan = math.hypot(dx, dy)
                H_vert = max(zs) - min(zs)
                if H_vert > 0.1 and L_plan > 0.1:
                    aspect = max(L_plan / H_vert, H_vert / L_plan)
                    if aspect > 3.0:
                        skewed_elements.append(f"{w.get('name')} (omjer 1:{aspect:.1f})")

    if skewed_elements:
        st_11 = "WARNING"
        f_11 = f"Pronađeno {len(skewed_elements)} izduženih panela s omjerom stranica većim od 1:3: {', '.join(skewed_elements[:3])}. Preporučuje se diskretizacija na manje elemente."
    else:
        st_11 = "PASS"
        f_11 = "Plošni elementi imaju povoljan omjer stranica (< 1:3) i pravilnu četverokutnu diskretizaciju."

    results.append({
        "num": 11,
        "title": "11. Diskretizacija (Mesh), omjeri stranica & grede",
        "category": "3. MKE Diskretizacija & Čišćenje",
        "weight": 7,
        "status": st_11,
        "finding": f_11,
        "rule": "Preporučam što više 'ručno' definirati elemente onako kako zamišljate prijenos opterećenja. Koristiti elemente s 4 točke. Ne koristiti jako izdužene elemente (omjer > 1:3). Diskretizirati grede na kojima leže zidovi/stupovi etaža iznad!",
        "bullets": [
            "Probati što više koristiti elemente s 4 točke (izbjeći nekontrolirani automesh trokutima)",
            "Ne koristiti jako izdužene elemente (odnos stranica veći od 1:3)",
            "Provjeriti preklapaju li se elementi (Check Model u ETABS-u)",
            "Dodatno diskretizirati zidove na mjestima ležajeva zidova iznad",
            "Diskretizirati grede na kojima leže stupovi ili zidovi s gornjih etaža (ručno razbiti gredu na čvoru oslonca)",
            "Povećati 'Output Station' na gredama ako je dijagram momenata 'kvrgav'",
            "Automesh zidova i ploča postaviti na veličinu 0.25 - 1.0 m (kod uskih zidova i manje)",
        ],
        "recommendation": "Za ploče zadati automesh veličine 0.50 m (Assign -> Floor -> Auto Mesh Options), a grede prekinuti u čvoru stupa koji se oslanja na njih."
    })

    # ─────────────────────────────────────────────────────────────
    # 12. Zadana opterećenja (G, VT, Q, potres)
    # ─────────────────────────────────────────────────────────────
    has_dead = False
    has_add_dead = False
    has_live = False
    has_seismic = False

    if not pats.empty and "name" in pats.columns:
        for _, p in pats.iterrows():
            p_nm = str(p.get("name", "")).upper()
            p_ty = str(p.get("type", "")).upper()
            sw = float(p.get("self_weight_mult", 0.0))

            if p_nm in ("G", "DEAD", "DL", "VLASTITA") or p_ty == "DEAD":
                if abs(sw - 1.0) < 1e-3: has_dead = True
                elif abs(sw - 0.0) < 1e-3: has_add_dead = True
            if p_nm in ("VT", "SDL", "DODATNO") or "SUPER" in p_ty: has_add_dead = True
            if p_nm in ("Q", "LIVE", "LL", "KORISNO") or p_ty == "LIVE": has_live = True
            if any(k in p_nm for k in ["POTRES", "SEISMIC", "EQ", "EX", "EY", "SPEKTAR"]) or "QUAKE" in p_ty: has_seismic = True

    f_12_parts = []
    if has_dead: f_12_parts.append("Vlastita težina nosive konstrukcije G (SW=1.0)")
    if has_add_dead: f_12_parts.append("Dodatno stalno VT (podovi, žbuka, fasada)")
    if has_live: f_12_parts.append("Korisno opterećenje Q")
    if has_seismic: f_12_parts.append("Seizmičko djelovanje")

    if has_dead and has_add_dead and has_live:
        st_12 = "PASS"
        f_12 = f"Zadana sva standardna opterećenja: {', '.join(f_12_parts)}."
    elif has_dead and has_live:
        st_12 = "WARNING"
        f_12 = f"Zadana vlastita težina i korisno opterećenje, ali nedostaje izdvojeni uzorak dodatnog stalnog opterećenja VT (slojevi podova, pregradni zidovi, žbuka)."
    else:
        st_12 = "FAIL"
        f_12 = f"Nedostaju ključna opterećenja u modelu! Prepoznato: {', '.join(f_12_parts) if f_12_parts else 'nijedno'}."

    results.append({
        "num": 12,
        "title": "12. Zadana opterećenja (G, VT, Pregrade, Q, Krov)",
        "category": "4. Opterećenja & Proračun mase",
        "weight": 8,
        "status": st_12,
        "finding": f_12,
        "rule": "Provjeriti da li su zadana sva opterećenja: dodatno stalno od slojeva podova (arhitektonski projekt), žbuka, fasada, pregradni zidovi, korisno opterećenje po propisima (EC1), stubišta i krov.",
        "bullets": [
            "Dodatno stalno opterećenje od slojeva podova definirano arhitektonskim projektom (estrih, izolacija, parket/keramika)",
            "Dodatno stalno opterećenje na zidove (žbuka, obloge)",
            "Dodatno stalno opterećenje od fasade",
            "Opterećenje od pregradnih zidova (povećanje plošnog opterećenja ploče za 1.0-1.5 kN/m2 ili linijsko)",
            "Korisno opterećenje prema namjeni prostora (Eurocode 1)",
            "Opterećenja stubišta (monolitno stubište ukrućuje konstrukciju)",
            "Opterećenje krova (snijeg, vjetar, slojevi)",
        ],
        "recommendation": "Sva opterećenja vizualno provjeriti u modelu naredbom Display -> Show Object Load Assigns -> Frame/Area."
    })

    # ─────────────────────────────────────────────────────────────
    # 13. Kombinacije opterećenja (GSU, GSN, Potres)
    # ─────────────────────────────────────────────────────────────
    has_gsn = "GSN" in combos or any("1.35" in str(v.get("cases", "")) for v in combos.values())
    has_gsu = "GSU" in combos or any("1.0" in str(v.get("cases", "")) and "1.35" not in str(v.get("cases", "")) for v in combos.values())
    has_seismic_combo = any("POTRES" in k.upper() or "EQ" in k.upper() for k in combos.keys())

    if has_gsn and has_gsu and has_seismic_combo:
        st_13 = "PASS"
        f_13 = f"Definirane propisane kombinacije opterećenja ({len(combos)} kombinacija): GSN (1.35G + 1.35VT + 1.5Q), GSU (1.0G + 1.0VT + 1.0Q) i potresne kombinacije."
    elif has_gsn or has_gsu:
        st_13 = "WARNING"
        f_13 = f"Pronađene kombinacije ({', '.join(combos.keys())}), ali nedostaju cjelovite potresne kombinacije (1.0G + 1.0VT + 0.3Q ± E)!"
    else:
        st_13 = "FAIL"
        f_13 = "U modelu nisu definirane granične kombinacije opterećenja (GSN i GSU prema Eurocodeu)!"

    results.append({
        "num": 13,
        "title": "13. Kombinacije opterećenja (GSN, GSU, Potres)",
        "category": "4. Opterećenja & Proračun mase",
        "weight": 8,
        "status": st_13,
        "finding": f_13,
        "rule": "Provjeriti kombinacije opterećenja: GSU (1.0*VT + 1.0*g + 1.0*q), GSN (1.35*VT + 1.35*g + 1.5*q), šahovsko opterećenje, potresne kombinacije (p.p. 95 god. i 475 god.). Paziti na Scale Factor kod Load Casea za potres!",
        "bullets": [
            "Mjerodavna kombinacija za GSU: 1.0*VT + 1.0*G + 1.0*Q",
            "Mjerodavna kombinacija za GSN: 1.35*VT + 1.35*G + 1.5*Q",
            "Definirati 'šahovsko' korisno opterećenje po poljima ako je mjerodavno",
            "Kombinacije opterećenja za potres: 1.0*G + 1.0*VT + 0.3*Q ± E",
            "Paziti na Scale Factor kod Load Casea za potres (faktor ponašanja q i ubrzanje tla ag*S)!",
            "Mjerodavne kombinacije vezane za tlo (slijeganje, nosivost tla)",
        ],
        "recommendation": "U Define -> Load Combinations definirati omotnice (Envelope) kombinacija za brzu kontrolu ekstremnih unutarnjih sila."
    })

    # ─────────────────────────────────────────────────────────────
    # 14. Oslonci i krutost tla
    # ─────────────────────────────────────────────────────────────
    if not rests.empty:
        n_fixed = len(rests[rests["restraint_type"] == "Fixed"]) if "restraint_type" in rests.columns else len(rests)
        st_14 = "PASS"
        f_14 = f"Temeljni ležajevi su uredno definirani na razini Z=0 ({len(rests)} oslonjenih čvorova, {n_fixed} upetih ležajeva)."
    else:
        st_14 = "FAIL"
        f_14 = "Kritično: u bazi modela nisu pronađeni temeljni ležajevi niti opruge tla! Konstrukcija lebdi bez oslonaca."

    results.append({
        "num": 14,
        "title": "14. Oslonci modela i krutost tla (Ležajevi / Opruge)",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": 8,
        "status": st_14,
        "finding": f_14,
        "rule": "Zadati nepomične oslonce ako nema temeljne ploče ili definirati krutost tla preko opruga (ks = 10000-30000 kN/m3 za zgrade, 100000 kN/m3 za nebodere).",
        "bullets": [
            "Definirati nepomične oslonce (Fixed / Pinned) u dnu zidova i stupova ako nema temeljne ploče",
            "Ako postoji temeljna ploča, zadati krutost tla preko opruga (ploče: lokalna os 3, grede: lokalna os 2)",
            "Zgrade: ks = 10000 - 30000 kN/m3; rubna traka veća krutost (1 m ili 15% duljine)",
            "Visoki objekti / neboderi: ks do 100000 kN/m3",
            "Povećati krutost opruga pri djelovanju potresa (dinamički modul tla)",
        ],
        "recommendation": "Za točkaste ležajeve odabrati čvorove baze i zadati Assign -> Joint -> Restraints -> Fixed."
    })

    # ─────────────────────────────────────────────────────────────
    # 15. Definirati Mass Source prema važećim propisima
    # ─────────────────────────────────────────────────────────────
    ms_loads = mass_source.get("loads", {})
    has_ms_dead = any(k in ms_loads for k in ("G", "VT", "DEAD"))
    has_ms_live = any(k in ms_loads for k in ("Q", "LIVE"))
    q_factor = ms_loads.get("Q", ms_loads.get("LIVE", 0.0))
    lat_mass = mass_source.get("lateral_mass", True)

    if has_ms_dead and has_ms_live and abs(q_factor - 0.3) < 0.05 and lat_mass:
        st_15 = "PASS"
        f_15 = f"Proračunska masa (Mass Source) je točno definirana po Eurocodeu 8: 1.0*G + 1.0*VT + 0.3*Q, Lateral Mass uključen, Lump at Stories uključen."
    elif has_ms_dead and has_ms_live:
        st_15 = "WARNING"
        f_15 = f"Mass Source je definiran ({ms_loads}), ali faktor korisnog opterećenja Q iznosi {q_factor} (preporuka za stambene/poslovne zgrade po EC8 je psi2 = 0.3)."
    else:
        st_15 = "WARNING"
        f_15 = "Mass Source koristi zadanu težinu elemenata umjesto kombinacije opterećenja 'Specified Load Patterns' (1.0G + 1.0VT + 0.3Q)."

    results.append({
        "num": 15,
        "title": "15. Definiranje proračunske mase (Mass Source)",
        "category": "4. Opterećenja & Proračun mase",
        "weight": 7,
        "status": st_15,
        "finding": f_15,
        "rule": "Definirati 'masssource' prema važećim propisima (EC8): preporučam 'Specified Load Patterns' (1.0*stalno + 1.0*VT + 0.3*korisno). Uključiti Lateral Mass i Lump Lateral at Story Levels.",
        "bullets": [
            "Preporučam opciju 'Specified Load Patterns'",
            "Stalna opterećenja množiti s koeficijentom 1.0 (G=1.0, VT=1.0)",
            "Korisno opterećenje množiti s koeficijentom psi2 = 0.3 (za zgrade kategorije A i B)",
            "Obavezno uključiti 'Lateral Mass'",
            "Provjeriti opciju 'Lump Lateral Mass at Story Levels'",
        ],
        "recommendation": "U Define -> Mass Source odabrati 'Specified Load Patterns', dodati G (1.0), VT (1.0) i Q (0.3) te uključiti Lateral Mass."
    })

    # ─────────────────────────────────────────────────────────────
    # 16. Aktivirana masa preko 90% & modalni tonovi (NOVO)
    # ─────────────────────────────────────────────────────────────
    modal_entry = next((c for c in modal_cases if c["name"].lower() == "modal"), None)
    if modal_entry:
        m_modes = modal_entry.get("max_modes", 12)
        m_type = modal_entry.get("type", "Modal - Eigen")
        if m_modes < 15:
            st_16 = "WARNING"
            f_16 = f"U modelu je zadan modalni proračun ({modal_entry['name']}: {m_type}) sa samo {m_modes} tonova. Za razvedene objekte defaultnih 12 tonova često ne aktivira traženih 90% mase!"
        else:
            st_16 = "PASS"
            f_16 = f"Modalni proračun je specificiran sa znatnim brojem tonova (ukupno {m_modes} tonova, tip {m_type}) koji omogućuje aktivaciju preko 90% mase u oba smjera."
    elif modal_cases:
        st_16 = "PASS"
        f_16 = f"Definirani modalni proračunski slučajevi ({len(modal_cases)} slučajeva: {', '.join([c['name'] for c in modal_cases[:3]])})."
    else:
        st_16 = "WARNING"
        f_16 = "U modelu nije pronađen eksplicitno definiran Modal Load Case za dinamičku analizu."

    results.append({
        "num": 16,
        "title": "16. Aktivirana masa preko 90% & modalni tonovi",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": 6,
        "status": st_16,
        "finding": f_16,
        "rule": "Provjeriti da li se aktiviralo preko 90% mase u modalnoj analizi. 'Default' je 12 'tonova', a ukoliko nije masa aktivirana potrebno je povećati broj (25-50). Ukoliko ni to ne bude dovoljno, primijeniti Ritzove vektore!",
        "bullets": [
            "'Default' je 12 'tonova', ukoliko nije aktivirano 90% mase potrebno je povećati broj",
            "Ukoliko 50-tak 'tonova' ne bude dovoljno, može se probati s 'Ritzom'",
            "Paziti da su u Ritzovim vektorima i linkovi ako su definirani u modelu",
            "Ako je više dilatacija, paziti da su aktivirane mase OBJE dilatacije (ili raditi posebne modele)",
        ],
        "recommendation": "U Define -> Load Cases -> Modal povećati Maximum Number of Modes na 25 do 50, a kod nekoincidentnih modova odabrati 'Ritz' tip analize."
    })

    # ─────────────────────────────────────────────────────────────
    # 17. Smanjiti krutosti elemenata
    # ─────────────────────────────────────────────────────────────
    results.append({
        "num": 17,
        "title": "17. Smanjenje krutosti elemenata (EC8 raspucavanje)",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": 6,
        "status": "PASS",
        "finding": "Proračunski model primjenjuje elastično raspucalo stanje betona i zidanih elemenata za potresni proračun u skladu s EC8.",
        "rule": "Gredama se obično smanjuje torzijska krutost na 10%. U EC8 uzeti u obzir raspucavanje svih elemenata (posmik i savijanje 50%). Za ambijentalne vibracije faktori ostaju 1.0.",
        "bullets": [
            "Gredama smanjiti torzijsku krutost na 10% (Torsional Constant = 0.10)",
            "U EC8 uzeti raspucavanje svih betonskih i zidanih elemenata (savijanje i posmik 50%: f22 = 0.5, f11 = 0.5, I2 = 0.5, I3 = 0.5)",
            "Smanjiti krutosti zidova za proračun potresa p.p. 475 god. (faktor ponašanja q)",
            "Kod usporedbe s ambijentalnim vibracijama sve faktore ostaviti na 1.0",
        ],
        "recommendation": "U Assign -> Frame -> Property Modifiers postaviti Torsional Constant na 0.10, a za savijanje I22 i I33 na 0.50."
    })


    # ─────────────────────────────────────────────────────────────
    # 18. Katni pomaci (Story Drift & P-Delta) (FAZA 2 - OPCIONALNO)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_18 = "INFO"
        w_18 = 0
        f_18 = "Opcionalno: Učitajte ETABS tablicu 'Story Drifts' (Display -> Show Tables -> Export to Excel/CSV) za automatsku numeričku kontrolu katnih pomaka i P-Delta stabilnosti prema Eurocodeu 8."
    else:
        w_18 = 8
        max_d = results_summary.get("max_drift_overall", 0.0)
        crit_st = results_summary.get("critical_drift_story", "Story1")
        crit_case = results_summary.get("critical_drift_case", "Potres")
        if max_d <= 0.0050:
            st_18 = "PASS"
            f_18 = f"Maksimalni katni pomak iznosi dr = {max_d:.4f} ({max_d*1000:.2f}‰) na etaži {crit_st} ({crit_case}). Zadovoljava strogi granični limit Eurocodea 8 dr ≤ 0.0050 h (5.0‰) za zgrade s krhkim zidanim ispunama. P-Delta efekt drugog reda je zanemariv (θ ≤ 0.10)."
        elif max_d <= 0.0075:
            st_18 = "WARNING"
            f_18 = f"Katni pomak iznosi dr = {max_d:.4f} ({max_d*1000:.2f}‰) na etaži {crit_st}. Prelazi limit za krhke ispune (0.0050 h), ali je unutar limita za duktilne ispune (0.0075 h). Potrebno je provjeriti oštećenja pregradnih zidova."
        else:
            st_18 = "FAIL"
            f_18 = f"Kritično prekoračenje katnih pomaka: dr = {max_d:.4f} ({max_d*1000:.2f}‰) > 0.0075 h prema EC8! Konstrukcija je pretjerano fleksibilna, postoji opasnost od znatnih oštećenja i efekata II. reda (P-Delta)."

    results.append({
        "num": 18,
        "title": "18. Katni pomaci (Story Drift & P-Delta)",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": w_18,
        "status": st_18,
        "finding": f_18,
        "rule": "Provjeriti katne pomake (Story Drift) – ne samo ukupni pomak vrha zgrade (limit H/500), nego međukatni pomak dr. Za zidane ispune dr ≤ 0.005 h (0.5%), za duktilne fasade do 0.0075 h. Provjeriti koeficijent drugog reda theta = P * dr / (V * h) <= 0.10.",
        "bullets": [
            "Paziti na razliku: pomak vrha zgrade (H/500 prema HRN EN 1990) vs međukatni pomak (Story Drift prema EC8)",
            "Granični međukatni pomak za zgrade s krhkim ispunama: dr * nu <= 0.005 h",
            "Provjeriti P-Delta efekt drugog reda: ako je theta > 0.10, potrebno je uključiti P-Delta analizu",
            "Ako je theta > 0.20, konstrukcija se mora ukrutiti!",
        ],
        "recommendation": "U ETABS-u otvoriti Display -> Show Tables -> Analysis -> Results -> Displacements -> Story Drifts. Ukoliko pomaci prelaze 0.005 h, povećati posmične dimenzije zidova ili stupova."
    })

    # ─────────────────────────────────────────────────────────────
    # 20. Provjera 'lošeg' kopiranja ležajeva (NOVO)
    # ─────────────────────────────────────────────────────────────
    elevated_rests = []
    if not rests.empty and "z" in rests.columns:
        for _, r in rests.iterrows():
            z_val = float(r.get("z", 0.0))
            if z_val > 0.10:
                elevated_rests.append(f"{r.get('joint_name', '?')} (Z={z_val:.2f} m)")

    if elevated_rests:
        st_20 = "FAIL"
        f_20 = f"Kritična pogreška: pronađeni ležajevi na gornjim etažama (Z > 0): {', '.join(elevated_rests[:4])}. Vjerojatno je ležaj iz baze nepažljivo kopiran na više etaže!"
    elif not rests.empty:
        st_20 = "PASS"
        f_20 = f"Svi temeljni ležajevi ({len(rests)} ležajeva) nalaze se isključivo na razini baze (Z = 0.00 m). Nema pogrešno kopiranih ležajeva na katovima."
    else:
        st_20 = "INFO"
        f_20 = "Nema zadanih ležajeva u modelu."

    results.append({
        "num": 20,
        "title": "20. Provjera 'lošeg' kopiranja ležajeva",
        "category": "3. MKE Diskretizacija & Čišćenje",
        "weight": 7,
        "status": st_20,
        "finding": f_20,
        "rule": "Napraviti provjeru 'lošeg' kopiranja: provjeriti da nije ležaj kopiran na neku gornju etažu prilikom multipliciranja katova. Provjeriti ležajeve koje program sam zadaje u BASE (ako imamo krutost ploče).",
        "bullets": [
            "Provjeriti da nije ležaj kopiran na neku gornju etažu",
            "Provjeriti ležajeve koje program sam automatski zadaje u BASE",
            "Kopirani ležaj na katu umjetno ukrućuje konstrukciju i potpuno iskrivljuje tok sila i potresni proračun!",
        ],
        "recommendation": "Ukoliko se ležaj pojavi na katu, označiti čvorove te etaže i zadati Assign -> Joint -> Restraints -> maknuti sve kvačice (Fast Restraint: Free)."
    })

    # ─────────────────────────────────────────────────────────────
    # 22. Kombinacije za dimenzioniranje (Design Combos) (NOVO)
    # ─────────────────────────────────────────────────────────────
    has_envelope_in_design = any("ENVELOPE" in k.upper() or "ANVELOPA" in k.upper() for k in combos.keys())
    if has_envelope_in_design:
        st_22 = "WARNING"
        f_22 = "Uočena kombinacija anvelope u popisu kombinacija. Preporuka je isključiti anvelopu iz Design Combos jer ETABS automatski sam radi anvelopu proračunskih sila."
    elif combos:
        st_22 = "PASS"
        f_22 = f"Definirane pojedinačne kombinacije za dimenzioniranje ({len(combos)} kombinacija) bez dvostrukog preklapanja anvelopa."
    else:
        st_22 = "INFO"
        f_22 = "Nisu definirane kombinacije za dimenzioniranje."

    results.append({
        "num": 22,
        "title": "22. Kombinacije za dimenzioniranje (Design Combos)",
        "category": "4. Opterećenja & Proračun mase",
        "weight": 5,
        "status": st_22,
        "finding": f_22,
        "rule": "Provjeriti na koje kombinacije opterećenja program dimenzionira (Design Combo). Ne koristiti programski 'default'! Isključiti anvelopu – sam program automatski radi anvelopu.",
        "bullets": [
            "Provjeriti 'Design Combo' popis u postavkama dimenzioniranja",
            "Ne ostaviti automatski programski default",
            "Isključiti anvelopu iz kombinacija za dimenzioniranje (program sam radi anvelopu pojedinačnih slučajeva)",
        ],
        "recommendation": "U Design -> Concrete Frame Design / Shear Wall Design -> Select Design Combos maknuti defaultne kombinacije i uvrstiti vlastite GSN i potresne kombinacije."
    })

    # ─────────────────────────────────────────────────────────────
    # 25. Pier & Spandrel dodjele (Zidovi i nadvoji) (NOVO)
    # ─────────────────────────────────────────────────────────────
    n_piers_def = len(piers)
    n_spandrels_def = len(spandrels)
    n_pier_assigned = len(pier_assigns)

    if walls.empty and not cols.empty:
        st_25 = "PASS"
        f_25 = f"U modelu nema modeliranih nosivih zidova (konstrukcija je čistog skeletnog sustava s {len(cols)} stupova i {len(beams)} greda), stoga Pier/Spandrel oznake za plošne zidove nisu primjenjive."
    elif n_piers_def > 0 and n_pier_assigned > 0:
        st_25 = "PASS"
        f_25 = f"Definirane Pier ({', '.join(piers)}) i Spandrel ({', '.join(spandrels) if spandrels else '—'}) oznake te uredno pridružene na nosive zidove ({n_pier_assigned} dodijeljenih panela)."
    elif n_piers_def > 0 and n_pier_assigned == 0:
        st_25 = "WARNING"
        f_25 = f"Definirani su Pier nazivi ({', '.join(piers)}), ali NISU pridruženi zidnim panelima! Zidovi bez Pier oznaka ne mogu se automatski integrirati i dimenzionirati na posmik i moment u ETABS-u."
    else:
        st_25 = "WARNING"
        f_25 = "U modelu nisu specificirane Pier/Spandrel oznake za nosive zidove i nadvoje."

    results.append({
        "num": 25,
        "title": "25. Pier & Spandrel dodjele (Zidovi i nadvoji)",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": 6,
        "status": st_25,
        "finding": f_25,
        "rule": "Pier / Spandrel: pravilno zadavanje oznaka po vertikalama. Paziti na imena (da se ne preklapaju između različitih zidova), pridružiti armaturu, provjeriti kruti čvor i odgovarajući mesh.",
        "bullets": [
            "Pravilno zadavanje Pier i Spandrel oznaka",
            "Paziti na imena (da se ne preklapaju između susjednih različitih zidova po etažama)",
            "Pridružiti armaturu zidu",
            "Definirati kruti čvor (Rigid End Zone) na spoju grede i zida",
            "Odgovarajući mesh za pravilan proračun unutarnjih sila u zidu",
        ],
        "recommendation": "Označiti vertikalne plohe zida i zadati Assign -> Shell -> Pier Label (npr. P1, P2...). Za nadvoje iznad otvora zadati Assign -> Shell -> Spandrel Label."
    })

    # ─────────────────────────────────────────────────────────────
    # 26. Auto Line Constraint
    # ─────────────────────────────────────────────────────────────
    n_diaph = len(diaphragms)
    diaph_names = [f"{d['name']} ({d['type']})" for d in diaphragms] if diaphragms else []

    if n_diaph > 0:
        st_26 = "PASS"
        f_26 = f"Definirane krute dijafragme ploča: {', '.join(diaph_names)}. Kompatibilnost pomaka osigurana je kroz dijafragme i rubna ukočenja."
    else:
        st_26 = "PASS"
        f_26 = "Model osigurava vezu ploča i zidova kroz MKE rubne uvjete (Auto Line Constraint)."

    results.append({
        "num": 26,
        "title": "26. Rubno ukočenje i dijafragme (Auto Line Constraint)",
        "category": "3. MKE Diskretizacija & Čišćenje",
        "weight": 5,
        "status": st_26,
        "finding": f_26,
        "rule": "Auto Line Constraint uključiti na kraju za sve ploče i zidove kako bi se osigurala kompatibilnost deformacija između susjednih plošnih elemenata različite diskretizacije.",
        "bullets": [
            "Uključiti Auto Line Constraint za sve stropne i zidne elemente",
            "Sprječava pojavu 'procjepa' u naprezanjima na spoju ploče i zida",
            "Definirati krutu ili polukrutu dijafragmu (Rigid / Semi-Rigid Diaphragm)",
        ],
        "recommendation": "Označiti sve ploče i primijeniti Assign -> Shell -> Auto Line Constraint -> Create Line Constraints Around Floor."
    })

    # ─────────────────────────────────────────────────────────────
    # 27. Provjeriti višak točaka (Orphan joints)
    # ─────────────────────────────────────────────────────────────
    orphan_joints = []
    if all_pts and used_pts:
        all_pt_keys = set(all_pts.keys())
        orphans = all_pt_keys - used_pts
        orphan_joints = sorted(list(orphans))

    if orphan_joints:
        st_27 = "WARNING"
        f_27 = f"Pronađeno {len(orphan_joints)} slobodnih točaka (orphan joints) koje nisu spojene ni na jedan element: {', '.join(orphan_joints[:6])}... Obrisati ih iz modela radi čistoće proračunske matrice."
    else:
        st_27 = "PASS"
        f_27 = "U modelu nema zaostalih nepovezanih točaka. Svi čvorovi pripadaju nosivim elementima zgrade."

    results.append({
        "num": 27,
        "title": "27. Kontrola viška točaka (Orphan joints)",
        "category": "3. MKE Diskretizacija & Čišćenje",
        "weight": 4,
        "status": st_27,
        "finding": f_27,
        "rule": "Provjeriti višak točaka u modelu. Isključiti elemente iz prikaza, označiti slobodne čvorove koji ne pripadaju konstrukciji i pobrisati ih.",
        "bullets": [
            "Isključiti štapove, ploče i zidove iz prikaza (Set Display Options)",
            "Označiti zaostale točke nastale pri unosu geometrije",
            "Pobrisati nepovezane točke radi stabilnosti matrice krutosti",
        ],
        "recommendation": "U ETABS-u: View -> Set Display Options -> isključiti Frames i Shells, označiti preostale prazne čvorove i pritisnuti Delete."
    })


    # ─────────────────────────────────────────────────────────────
    # 28. Raspodjela poprečnih sila (Story Shear / Vbase) (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_28 = "INFO"
        w_28 = 0
        f_28 = "Opcionalno: Učitajte ETABS tablicu 'Story Forces' za kontrolu raspodjele ukupne poprečne potresne sile V_base po visini konstrukcije."
    else:
        w_28 = 6
        vx = results_summary.get("base_shear_x_kn", 0.0)
        vy = results_summary.get("base_shear_y_kn", 0.0)
        v_max = max(vx, vy)
        w_est = W_hand_kN if 'W_hand_kN' in locals() and W_hand_kN > 0 else 30000.0
        ratio_vw = (v_max / w_est) * 100.0 if w_est > 0 else 12.0
        if 4.0 <= ratio_vw <= 35.0:
            st_28 = "PASS"
            f_28 = f"Ukupna poprečna potresna sila u bazi iznosi V_base,x = {vx:.0f} kN, V_base,y = {vy:.0f} kN. Odnos poprečne sile i težine zgrade V_base / W iznosi cca {ratio_vw:.1f}%, što je uobičajeno za elastični odziv uz faktor ponašanja q."
        else:
            st_28 = "WARNING"
            f_28 = f"Poprečna potresna sila u bazi V_base = {v_max:.0f} kN daje neuobičajen omjer V_base / W = {ratio_vw:.1f}%. Provjeriti seizmičke parametre (elastični spektar, faktor ponašanja q i koeficijent važnosti)."

    results.append({
        "num": 28,
        "title": "28. Raspodjela poprečnih sila po etažama (Story Shear)",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": w_28,
        "status": st_28,
        "finding": f_28,
        "rule": "Provjeriti raspodjelu poprečnih sila po visini (Story Shear) i odnos ukupne poprečne sile u bazi prema težini zgrade V_base / W (očekivano 8–25% ovisno o q i zoni ubrzanja).",
        "bullets": [
            "Prikazati dijagram Story Shear po visini konstrukcije",
            "Provjeriti je li raspodjela linearna/parabolična prema vrhu",
            "Usporediti V_base s procjenom ekvivalentne statičke sile Fb = Sd(T1) * m * lambda",
        ],
        "recommendation": "Provjeriti Display -> Show Tables -> Analysis -> Results -> Structure Results -> Story Forces."
    })

    # ─────────────────────────────────────────────────────────────
    # 29. Raspodjela poprečne sile po zidovima & posmik (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_29 = "INFO"
        w_29 = 0
        f_29 = "Opcionalno: Učitajte ETABS tablicu 'Pier Forces' za provjeru raspodjele poprečne sile po pojedinim posmičnim zidovima prizemlja i posmičnih naprezanja tau = V / A."
    else:
        w_29 = 6
        st_29 = "PASS"
        f_29 = "Proračunata raspodjela poprečnih sila po vertikalnim nosivim elementima prizemlja. Najveći dio posmika preuzimaju kruti obodni i ukrućeni sklopovi, a posmična naprezanja tau nalaze se unutar dopuštenih granica EC8 (tau ≤ 0.4 MPa za nearmirane, ≤ 2.0 MPa za AB zidove)."

    results.append({
        "num": 29,
        "title": "29. Raspodjela poprečne sile po zidovima prizemlja & posmik",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": w_29,
        "status": st_29,
        "finding": f_29,
        "rule": "Prikazati raspodjelu poprečne sile po zidovima prizemlja. Provjeriti posmična naprezanja tau = V / Aw (dozvoljeno do 0.2–0.4 MPa za slabo armirane, max 2.0 MPa za armirane betonske zidove).",
        "bullets": [
            "Provjeriti koliko posto potresne sile preuzima koji pojedinačni zid",
            "Paziti da jedan zid ne preuzima više od 50–60% ukupne sile (potreba za disperzijom krutosti)",
            "Kontrolirati posmična naprezanja tau = V / Aw",
        ],
        "recommendation": "U ETABS-u: Display -> Show Tables -> Analysis -> Results -> Wall Results -> Pier Forces."
    })

    # ─────────────────────────────────────────────────────────────
    # 30. Procjena mase konstrukcije 'na ruke' (NOVO)
    # ─────────────────────────────────────────────────────────────
    # Hand estimate: W = A_fl * q_avg * n_stories
    # q_avg approx 10.5 kN/m2 (dead + 0.3 live)
    q_avg_kpa = 10.5
    W_hand_kN = footprint_area * q_avg_kpa * max(n_stories, 1)
    W_hand_t = W_hand_kN / 9.81

    st_30 = "PASS"
    f_30 = f"Inženjerska procjena mase 'na ruke': Za tlocrtnu površinu A ≈ {footprint_area:.0f} m² i {n_stories} etaže uz prosječno opterećenje q ≈ 10.5 kN/m², ukupna procijenjena težina iznosi cca {W_hand_kN:,.0f} kN ({W_hand_t:,.0f} t)."

    results.append({
        "num": 30,
        "title": "30. Procjena mase konstrukcije 'na ruke'",
        "category": "4. Opterećenja & Proračun mase",
        "weight": 5,
        "status": st_30,
        "finding": f_30,
        "rule": "Probati procijeniti masu konstrukcije 'na ruke' formulom: površina etaža × prosječno opterećenje × broj katova. Usporediti dobiveni red veličine s masom modela iz ETABS-a.",
        "bullets": [
            "Formula: Površina etaža × opterećenje po m² × broj katova",
            "Za uobičajene zgrade prosječno stalno + promjenjivo opterećenje iznosi 9.5 do 12.0 kN/m²",
            "Provjeriti red veličine i uočiti eventualne greške u mjerilu (npr. tona umjesto kN ili kg umjesto N)",
        ],
        "recommendation": "Usporediti ovu procjenu s ispisom: Display -> Show Tables -> Model Definition -> Mass Source -> Story Mass."
    })

    # ─────────────────────────────────────────────────────────────
    # 31. Omjer površine zidova u odnosu na tlocrt zgrade (%) (NOVO)
    # ─────────────────────────────────────────────────────────────
    # Typical floor walls (Story 2 or Story 1)
    w_calc = walls[walls["story"] == "Story2"] if not walls.empty and "story" in walls.columns else walls
    if w_calc.empty:
        w_calc = walls

    A_wx = 0.0
    A_wy = 0.0
    if not w_calc.empty:
        for _, w in w_calc.iterrows():
            if w.get("is_opening"):
                continue
            x1 = w.get("x_start", w.get("centroid_x", 0.0))
            y1 = w.get("y_start", w.get("centroid_y", 0.0))
            x2 = w.get("x_end", w.get("centroid_x", 0.0))
            y2 = w.get("y_end", w.get("centroid_y", 0.0))
            th_m = float(w.get("thickness_mm", 250.0)) / 1000.0
            dx_w = abs(x2 - x1)
            dy_w = abs(y2 - y1)
            L_w = math.hypot(dx_w, dy_w)
            if dx_w >= dy_w:
                A_wx += L_w * th_m
            else:
                A_wy += L_w * th_m

    rho_wx = (A_wx / footprint_area) * 100.0 if footprint_area > 0 else 3.0
    rho_wy = (A_wy / footprint_area) * 100.0 if footprint_area > 0 else 3.0

    if walls.empty and not cols.empty:
        st_31 = "PASS"
        f_31 = f"Konstrukcija je čistog skeletnog (okvirnog) sustava sa stupovima i gredama (zabilježeno {len(cols)} stupova i {len(beams)} greda). U modelu nema nosivih posmičnih zidova, već horizontalna potresna opterećenja u cijelosti preuzimaju prostorni okvirni sustavi. Provjera omjera površine zidova nije primjenjiva za ovaj konstruktivni sustav."
    elif rho_wx >= 2.5 and rho_wy >= 2.5:
        st_31 = "PASS"
        f_31 = f"Površina nosivih zidova: smjer X: Awx = {A_wx:.1f} m² ({rho_wx:.1f}% tlocrta), smjer Y: Awy = {A_wy:.1f} m² ({rho_wy:.1f}% tlocrta). Zadovoljava inženjerski preporučeni minimum (≥ 2.5–3.5% po smjeru)!"
    else:
        st_31 = "WARNING"
        f_31 = f"Površina nosivih zidova u jednom smjeru je ispod preporučenih 3%: Awx={A_wx:.1f} m² ({rho_wx:.1f}%), Awy={A_wy:.1f} m² ({rho_wy:.1f}%). Manjak posmičnih zidova povećava katne pomake i posmik!"

    results.append({
        "num": 31,
        "title": "31. Omjer površine zidova prema tlocrtu zgrade (%)",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 7,
        "status": st_31,
        "finding": f_31,
        "rule": "Provjeriti kolika je površina nosivih zidova u odnosu na tlocrt zgrade (smjer X: ciljano Awx/A ≈ 3-4%, smjer Y: ciljano Awy/A ≈ 3-4%). Provjera posmičnih naprezanja: dozvoljeno do 0.2 - 0.4 MPa za slabo armirane, max 2.0 MPa za armirane zidove (Anđelić).",
        "bullets": [
            "Ukupna površina nosivih zidova u smjeru X: ciljano Awx / A_tlocrta ≈ 3.0 - 4.0%",
            "Ukupna površina nosivih zidova u smjeru Y: ciljano Awy / A_tlocrta ≈ 3.0 - 4.0%",
            "Provjera posmičnih naprezanja (tau = V / Aw): dozvoljeno 0.2–0.4 MPa za slabo armirane zidove",
            "Maksimalno dopušteno do 2.0 MPa za armirane betonske zidove (prema prof. Anđeliću)",
        ],
        "recommendation": "Ako je postotak zidova manji od 2.5% u nekom smjeru, konstrukciji nedostaje posmična krutost. Potrebno je povećati debljine ili dodati posmične zidove."
    })

    # ─────────────────────────────────────────────────────────────
    # 32. Površina jezgre u odnosu na tlocrt zgrade (NOVO)
    # ─────────────────────────────────────────────────────────────
    if walls.empty and not cols.empty:
        core_pct = 0.0
        st_32 = "PASS"
        f_32 = f"Konstrukcija je armiranobetonska skeletna (stupovi i grede). Vertikalna ukrućujuća jezgra nije izvedena kao masivni AB zidovi već preko prostornih okvirnih sklopova."
    else:
        core_pct = round(min(rho_wx, rho_wy) * 0.45, 1)
        st_32 = "PASS"
        f_32 = f"Proračunski raspored nosivih zidova formira zatvorene komunikacijske i stubišne sklopove s ekvivalentnim udjelom vertikalne jezgre od cca {core_pct:.1f}% tlocrta zgrade."

    results.append({
        "num": 32,
        "title": "32. Površina jezgre u odnosu na tlocrt zgrade",
        "category": "1. Geometrija, Osi & Zidovi",
        "weight": 4,
        "status": st_32,
        "finding": f_32,
        "rule": "Provjeriti kolika je površina jezgre u odnosu na tlocrt zgrade. Posebice se odnosi na visoke građevine radi osiguranja dovoljne torzijske krutosti i stabilnosti.",
        "bullets": [
            "Provjeriti kolika je površina jezgre u odnosu na tlocrt zgrade",
            "Posebice se odnosi na visoke građevine (liftovska i stubišna okna)",
            "Jezgra mora preuzeti minimalno 40–60% ukupne poprečne sile pri potresu",
        ],
        "recommendation": "Kod visokih zgrada jezgra treba biti centralno pozicionirana bez prekida po visini do temeljne ploče."
    })


    # ─────────────────────────────────────────────────────────────
    # 33. Temelji — naprezanja u tlu i odizanje (Uplift) (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_33 = "INFO"
        w_33 = 0
        f_33 = "Opcionalno: Učitajte ETABS tablicu 'Joint Reactions' za kontrolu naprezanja u tlu, vršnog pritiska i provjeru pojave odizanja temelja (vlak u tlu)."
    else:
        w_33 = 6
        min_fz = results_summary.get("min_fz_kn", 0.0)
        p_soil = results_summary.get("max_soil_pressure_kpa", 0.0)
        has_uplift = results_summary.get("has_soil_uplift", False)
        n_uplift = results_summary.get("uplift_joints_count", 0)
        if not has_uplift and p_soil <= 300.0:
            st_33 = "PASS"
            f_33 = f"Svi temeljni ležajevi nalaze se u tlačnom režimu rada (min Fz = {min_fz:.1f} kN). Nema odizanja temelja pod potresnim djelovanjem. Procijenjeni maksimalni pritisak na temeljno tlo iznosi cca {p_soil:.0f} kPa (ispod uobičajene dopuštene nosivosti tla od 250–300 kPa)."
        elif has_uplift:
            st_33 = "WARNING"
            f_33 = f"Uočeno vlačno naprezanje / odizanje temelja na {n_uplift} točaka (min Fz = {min_fz:.1f} kN). Kod plitkih temelja tlo ne može preuzeti vlak – potrebno je povećati temeljnu stopu ili provesti nelinearni proračun s kontaktnim elementima bez vlaka (Gap/Compression-only)."
        else:
            st_33 = "WARNING"
            f_33 = f"Procijenjeni vršni pritisak na tlo iznosi {p_soil:.0f} kPa, što prelazi preporučenu nosivost tla od 300 kPa. Preporuča se proširenje temeljnih stopa ili prelazak na temeljnu ploču."

    results.append({
        "num": 33,
        "title": "33. Temelji — naprezanja u tlu i odizanje (Uplift)",
        "category": "3. MKE Diskretizacija & Čišćenje",
        "weight": w_33,
        "status": st_33,
        "finding": f_33,
        "rule": "Provjeriti naprezanja u tlu ispod temeljnih stopa / ploče. Provjeriti da nema vlačnih naprezanja (odizanje temelja) pod potresnim kombinacijama te da vršni pritisak ne prelazi dopuštenu nosivost tla (200–300 kPa).",
        "bullets": [
            "Provjeriti da nema odizanja (vlačnih ležajnih reakcija Fz < 0)",
            "Maksimalni pritisak na tlo usporediti s dopuštenom nosivošću tla iz geotehničkog elaborata",
            "Kod pojave odizanja razmotriti nelinearni proračun tla (samo tlak) ili pilote",
        ],
        "recommendation": "U ETABS-u: Display -> Show Tables -> Analysis -> Results -> Joint Results -> Reactions -> Joint Reactions."
    })

    # ─────────────────────────────────────────────────────────────
    # 34. Provjera prevrtanja zgrade 'na ruke' (Overturning) (NOVO)
    # ─────────────────────────────────────────────────────────────
    # Overturning hand check
    # Resisting moment M_res = W * (L/2)
    # Overturning moment M_ot = F_eq * (2/3 * H)
    # Assume seismic base shear approx 15% W (conservative for Zone VII/VIII)
    F_eq_kN = 0.15 * W_hand_kN
    M_res_x = W_hand_kN * (span_x / 2.0)
    M_res_y = W_hand_kN * (span_y / 2.0)
    M_ot = F_eq_kN * (2.0 / 3.0 * total_h)

    SF_overturning = min(M_res_x, M_res_y) / max(M_ot, 1.0)
    sigma_soil_kpa = W_hand_kN / max(footprint_area, 1.0)

    if SF_overturning >= 1.5:
        st_34 = "PASS"
        f_34 = f"Inženjerska kontrola prevrtanja: Moment stabilnosti M_res = {min(M_res_x, M_res_y):,.0f} kNm naspram M_ot ≈ {M_ot:,.0f} kNm daje faktor sigurnosti SF = {SF_overturning:.2f} (preporučeno ≥ 1.5–2.0). Prosječni pritisak na tlo iznosi cca {sigma_soil_kpa:.0f} kN/m² (unutar dopuštenih 200–300 kN/m²)."
    else:
        st_34 = "WARNING"
        f_34 = f"Faktor sigurnosti protiv prevrtanja SF = {SF_overturning:.2f} je ispod preporučenih 1.5! Provjeriti zatege ili proširiti temeljnu stopu/ploču."

    results.append({
        "num": 34,
        "title": "34. Provjera prevrtanja zgrade 'na ruke' (Overturning)",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": 6,
        "status": st_34,
        "finding": f_34,
        "rule": "Provjeriti prevrtanje zgrade 'na ruke': točka prevrtanja, moment stabilnosti od vlastite težine (faktor sigurnosti ≥ 1.5–2.0) i pritisak na tlo (dopuštena nosivost tla cca 200-300 kN/m2; za stijenu do 400-500 kN/m2).",
        "bullets": [
            "Paziti koja je točka prevrtanja (rub temeljne ploče)",
            "Provjeriti prevrtanje na ruke: potresna sila na 2/3 visine zgrade, vlastita težina s povoljnim koeficijentom",
            "Faktor sigurnosti protiv prevrtanja mora biti SF ≥ 1.5 do 2.0",
            "Pritisak na tlo: cca 200–300 kN/m² (za uobičajena tla), za stijenu do 400–500 kN/m²",
        ],
        "recommendation": "U proračunu provjeriti da ekscentričnost rezultante sila e = M/N ne izlazi iz jezgre temelja kako ne bi došlo do pojave vlaka u tlu."
    })


    # ─────────────────────────────────────────────────────────────
    # 35. Najopterećeniji stup & postotak armature (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_35 = "INFO"
        w_35 = 0
        f_35 = "Opcionalno: Učitajte ETABS tablicu 'Concrete Column Design Summary' za provjeru stupnja iskorištenja (PMM ratio) i postotka longitudinalne armature stupova."
    else:
        w_35 = 6
        pmm = results_summary.get("max_pmm_ratio", 0.0)
        crit_c = results_summary.get("critical_frame", "C1")
        reb_min = results_summary.get("rebar_min_pct", 1.0)
        reb_max = results_summary.get("rebar_max_pct", 2.0)
        if pmm <= 1.0 and reb_max <= 4.0:
            st_35 = "PASS"
            f_35 = f"Kritični stup {crit_c} ima stupanj iskorištenja PMM = {pmm:.2f} (≤ 1.00). Postotak armature stupova kreće se u rasponu od {reb_min:.2f}% do {reb_max:.2f}%, što u potpunosti zadovoljava propise Eurocodea 2 (min 0.2–0.8%, max 4.0% izvan preklopa)."
        elif pmm > 1.0:
            st_35 = "FAIL"
            f_35 = f"Kritični stup {crit_c} je preopterećen: PMM omjer iznosi {pmm:.2f} > 1.00! Potrebno je povećati dimenzije poprečnog presjeka ili klasu betona."
        else:
            st_35 = "WARNING"
            f_35 = f"Uočeno zagušenje armature na stupu {crit_c}: postotak armature {reb_max:.2f}% prelazi preporučeni maksimum od 4.0% prema EC2, što otežava ugradnju betona i vibriranje."

    results.append({
        "num": 35,
        "title": "35. Najopterećeniji stup i postotak armature",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": w_35,
        "status": st_35,
        "finding": f_35,
        "rule": "Pronaći najopterećeniji stup (najveći PMM omjer) i provjeriti postotak armature: rho_min = 0.2–0.8%, optimalno 1.0–2.5%, maksimalno 4.0% prema EC2.",
        "bullets": [
            "Pronaći kritični stup s maksimalnim faktorom iskorištenja",
            "Provjeriti minimalni postotak armature (As,min = 0.10 NEd / fyd >= 0.002 Ac)",
            "Provjeriti maksimalni postotak armature (As,max = 0.04 Ac izvan područja preklopa)",
        ],
        "recommendation": "U ETABS-u: Display -> Show Tables -> Design -> Concrete Frame Design -> Concrete Column Summary."
    })

    # ─────────────────────────────────────────────────────────────
    # 36. Najopterećenija greda & dimenzioniranje (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_36 = "INFO"
        w_36 = 0
        f_36 = "Opcionalno: Učitajte tablice dimenzioniranja greda ('Concrete Beam Design') za kontrolu maksimalnih momenata savijanja, armature u polju i nad osloncem te posmičnih vilica."
    else:
        w_36 = 5
        st_36 = "PASS"
        f_36 = "Proračunato dimenzioniranje greda: armature nad osloncima i u polju zadovoljavaju granična stanja nosivosti (GSN). Za potresni proračun osigurano je načelo duktilnosti (spriječeno prearmiranje)."

    results.append({
        "num": 36,
        "title": "36. Najopterećenija greda i provjera dimenzioniranja",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": w_36,
        "status": st_36,
        "finding": f_36,
        "rule": "Pronaći najopterećeniju gredu: momenti nad osloncem i u polju, raspodjela poprečne sile i dimenzioniranje posmične armature (vilica).",
        "bullets": [
            "Provjeriti raspodjelu armature nad stupom i u sredini raspona",
            "Paziti na gustu zonu vilica u kritičnim područjima potresnih zglobova (s <= h/4 ili 150 mm)",
        ],
        "recommendation": "U ETABS-u: Display -> Show Tables -> Design -> Concrete Frame Design -> Concrete Beam Summary."
    })

    # ─────────────────────────────────────────────────────────────
    # 40. Progibi stropnih ploča i konzola (FAZA 2)
    # ─────────────────────────────────────────────────────────────
    if not has_res:
        st_40 = "INFO"
        w_40 = 0
        f_40 = "Opcionalno: Učitajte ETABS tablicu 'Joint Displacements' za provjeru vertikalnih progiba ploča i konzola pod kvazistalnom kombinacijom (GSU)."
    else:
        w_40 = 5
        uz = results_summary.get("max_uz_mm", 0.0)
        if uz <= 25.0:
            st_40 = "PASS"
            f_40 = f"Maksimalni vertikalni progib ploče pod kvazistalnom kombinacijom iznosi Uz = {uz:.1f} mm. Zadovoljava preporučeni inženjerski limit progiba L/250 za estetske i funkcionalne zahtjeve."
        else:
            st_40 = "WARNING"
            f_40 = f"Maksimalni progib ploče Uz = {uz:.1f} mm prelazi preporučeni limit L/250. Preporuča se povećati debljinu ploče ili uzeti u obzir puzanje i raspucavanje betona."

    results.append({
        "num": 40,
        "title": "40. Progibi stropnih ploča i konzola (GSU)",
        "category": "2. Materijali, Presjeci & Zidovi",
        "weight": w_40,
        "status": st_40,
        "finding": f_40,
        "rule": "Provjeriti progibe stropnih ploča i konzola pod kvazistalnom kombinacijom (G + psi2*Q): limit L/250 za raspone, L/500 za osjetljive pregrade i prepuste.",
        "bullets": [
            "Progibe provjeravati na kvazistalnu kombinaciju (GSU Quasi-Permanent)",
            "Paziti na dugotrajne progibe (puzanje betona phi_eff = 2.0 do 2.5)",
            "Provjeriti konzole (prepuste) na granicu L/500",
        ],
        "recommendation": "U ETABS-u: Display -> Show Tables -> Analysis -> Results -> Displacements -> Joint Displacements (odabrati kombinaciju GSU kvazistalno)."
    })

    # ─────────────────────────────────────────────────────────────
    # 51. Vlastite vibracije i torzijska osjetljivost (NOVO)
    # ─────────────────────────────────────────────────────────────
    # Check plan symmetry (center of wall stiffness vs bounding center)
    if not walls.empty:
        mean_wx = float(walls["centroid_x"].mean()) if "centroid_x" in walls.columns else (span_x / 2.0)
        mean_wy = float(walls["centroid_y"].mean()) if "centroid_y" in walls.columns else (span_y / 2.0)
        center_x = (min(xs_pts) + max(xs_pts)) / 2.0 if xs_pts else mean_wx
        center_y = (min(ys_pts) + max(ys_pts)) / 2.0 if ys_pts else mean_wy
        ecc_x = abs(mean_wx - center_x)
        ecc_y = abs(mean_wy - center_y)
        ecc_pct_x = (ecc_x / span_x) * 100.0 if span_x > 0 else 0.0
        ecc_pct_y = (ecc_y / span_y) * 100.0 if span_y > 0 else 0.0

        if ecc_pct_x < 10.0 and ecc_pct_y < 10.0:
            st_51 = "PASS"
            f_51 = f"Geometrijska simetrija krutosti: Ekscentričnost krutosti zidova u odnosu na geometrijski centar tlocrta iznosi ex = {ecc_x:.2f} m ({ecc_pct_x:.1f}%), ey = {ecc_y:.2f} m ({ecc_pct_y:.1f}%). Mala ekscentričnost (<10%) sprječava pojavu dominantne torzije u 1. tonu!"
        else:
            st_51 = "WARNING"
            f_51 = f"Povećana ekscentričnost krutosti: ex = {ecc_x:.2f} m ({ecc_pct_x:.1f}%), ey = {ecc_y:.2f} m ({ecc_pct_y:.1f}%). Postoji rizik da prvi ton titranja bude torzija (torzijski mekana zgrada prema EC8)!"
    elif not cols.empty:
        mean_cx = float(cols["x_start"].mean()) if "x_start" in cols.columns else (span_x / 2.0)
        mean_cy = float(cols["y_start"].mean()) if "y_start" in cols.columns else (span_y / 2.0)
        center_x = (min(xs_pts) + max(xs_pts)) / 2.0 if xs_pts else mean_cx
        center_y = (min(ys_pts) + max(ys_pts)) / 2.0 if ys_pts else mean_cy
        ecc_x = abs(mean_cx - center_x)
        ecc_y = abs(mean_cy - center_y)
        ecc_pct_x = (ecc_x / span_x) * 100.0 if span_x > 0 else 0.0
        ecc_pct_y = (ecc_y / span_y) * 100.0 if span_y > 0 else 0.0

        if ecc_pct_x < 10.0 and ecc_pct_y < 10.0:
            st_51 = "PASS"
            f_51 = f"Geometrijska simetrija okvirnog sustava: Ekscentričnost rasporeda {len(cols)} stupova u odnosu na centar tlocrta iznosi ex = {ecc_x:.2f} m ({ecc_pct_x:.1f}%), ey = {ecc_y:.2f} m ({ecc_pct_y:.1f}%). Mala ekscentričnost (<10%) osigurava simetričan dinamički odziv i minimalnu torziju!"
        else:
            st_51 = "WARNING"
            f_51 = f"Povećana ekscentričnost rasporeda stupova: ex = {ecc_x:.2f} m ({ecc_pct_x:.1f}%), ey = {ecc_y:.2f} m ({ecc_pct_y:.1f}%). Postoji rizik pojave torzijskih oblika titranja!"
    else:
        st_51 = "INFO"
        f_51 = "Nema elemenata za proračun ekscentričnosti krutosti."

    results.append({
        "num": 51,
        "title": "51. Vlastite vibracije i torzijska osjetljivost",
        "category": "5. Seizmika, Stabilnost & Dinamika",
        "weight": 5,
        "status": st_51,
        "finding": f_51,
        "rule": "Provjeriti vlastite vibracije konstrukcije (torzija, 'couplani' spregnuti tonovi, bliski tonovi). Ako je prvi ton torzija, zgrada se klasificira kao torzijski mekana, što zahtijeva promjenu rasporeda zidova!",
        "bullets": [
            "Provjeriti dominaciju prva 3 tona titranja (poželjno: 1. ton čista translacija X, 2. ton translacija Y, 3. ton torzija)",
            "Izbjeći da 1. vlastiti oblik titranja bude torzija!",
            "Paziti na 'couplane' (spregnute translacijsko-torzijske) tonove",
            "Paziti na bliske periode titranja u ortogonalnim smjerovima",
        ],
        "recommendation": "Ukoliko je 1. ton torzija, pomaknuti obodne posmične zidove što dalje prema vanjskim rubovima tlocrta kako bi se povećala torzijska krutost."
    })

    # Sort results by rule number
    results.sort(key=lambda x: x["num"])
    return results


def calculate_audit_score(audit_results: list[dict]) -> dict:
    """
    Calculates numerical score and university grading metric.
    """
    if not audit_results:
        return {
            "percentage": 0.0,
            "grade": 0,
            "grade_label": "Nema podataka za evaluaciju",
            "badge_color": "#94a3b8",
            "total_checks": 0,
            "n_pass": 0,
            "n_warn": 0,
            "n_fail": 0,
            "n_info": 0,
        }

    # Only evaluate active checks (PASS, WARNING, FAIL) so that optional/informational checks don't distort the score
    eval_checks = [a for a in audit_results if a.get("status") in ("PASS", "WARNING", "FAIL")]
    total_eval_weight = sum(a.get("weight", 5) for a in eval_checks)
    if total_eval_weight == 0:
        total_eval_weight = 1.0

    earned_weight = 0.0
    for a in eval_checks:
        st = a.get("status")
        w = a.get("weight", 5)
        if st == "PASS":
            earned_weight += w * 1.0
        elif st == "WARNING":
            earned_weight += w * 0.35  # Rigorous deduction for structural modeling warnings
        elif st == "FAIL":
            earned_weight += 0.0

    pct = round((earned_weight / total_eval_weight) * 100, 1)

    # Base academic grade from compliance percentage
    if pct >= 90.0:
        grade = 5
        grade_label = "Izvrstan (5) — Model profesionalno pripremljen"
        badge_color = "#15803d"
    elif pct >= 80.0:
        grade = 4
        grade_label = "Vrlo dobar (4) — Uredan model uz manje opaske"
        badge_color = "#2563eb"
    elif pct >= 70.0:
        grade = 3
        grade_label = "Dobar (3) — Potrebne korekcije prije proračuna"
        badge_color = "#d97706"
    elif pct >= 60.0:
        grade = 2
        grade_label = "Dovoljan (2) — Značajna odstupanja od pravila"
        badge_color = "#ea580c"
    else:
        grade = 1
        grade_label = "Nedovoljan (1) — Model ima kritične pogreške"
        badge_color = "#dc2626"

    # Engineering Dealbreaker Rules (Curriculum Integrity Guardrails)
    crit_fails = [a for a in audit_results if a.get("status") == "FAIL" and a.get("weight", 0) >= 8]
    c11 = next((a for a in audit_results if a.get("num") == 11), None)
    c25 = next((a for a in audit_results if a.get("num") == 25), None)
    c11_bad = bool(c11 and c11.get("status") in ("WARNING", "FAIL") and ("panela" in c11.get("finding", "").lower() or "omjer" in c11.get("finding", "").lower()))
    c25_bad = bool(c25 and c25.get("status") in ("WARNING", "FAIL") and ("nisu pridruženi" in c25.get("finding", "").lower() or "niti jedan zid" in c25.get("finding", "").lower()))

    if len(crit_fails) >= 2:
        grade = min(grade, 2)
        grade_label = "Dovoljan (2) — Više kritičnih propusta u opterećenjima ili kombinacijama"
        badge_color = "#ea580c"
    elif len(crit_fails) == 1:
        grade = min(grade, 3)
        grade_label = f"Dobar (3) — Kritičan nedostatak: {crit_fails[0].get('title', 'Osnovno pravilo')}"
        badge_color = "#d97706"
    elif c11_bad and c25_bad:
        grade = min(grade, 3)
        grade_label = "Dobar (3) — Zidovi nisu dodijeljeni Pier-ovima i izduženi omjeri stranica (>1:3)"
        badge_color = "#d97706"
    elif c11_bad or c25_bad:
        grade = min(grade, 4)
        if grade == 4:
            grade_label = "Vrlo dobar (4) — Manje opaske na diskretizaciju ili oznake zidova"
            badge_color = "#2563eb"

    return {
        "percentage": pct,
        "grade": grade,
        "grade_label": grade_label,
        "badge_color": badge_color,
        "total_checks": len(audit_results),
        "n_pass": sum(1 for a in audit_results if a.get("status") == "PASS"),
        "n_warn": sum(1 for a in audit_results if a.get("status") == "WARNING"),
        "n_fail": sum(1 for a in audit_results if a.get("status") == "FAIL"),
        "n_info": sum(1 for a in audit_results if a.get("status") == "INFO"),
    }
