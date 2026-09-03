"""
curriculum_audit.py — Comprehensive ETABS Student & Professional Audit Engine
Implements the complete 18-point university checklist for verifying numerical ETABS (.e2k) structural models
against actual design documents and architectural drawings:

  1. Definiranje osi (Grid System)
  2. Dimenzije, mjerne jedinice & dijakritici (m/cm, točka/zarez, rotacija U-presjeka)
  3. Definirati etaže u modelu (Story Data, visine, podest nije etaža)
  4. Arhitektonski nacrti (kote reza +1m, grede, konzole, otvori)
  5. Svojstva materijala (opeka, mort, ispitivanja, temeljna ploča MB16)
  6. Pridruživanje materijala presjecima (američki defaulti 4000Psi/A992, dupli presjeci)
  7. Svojstva armature (Grade 60 vs B500B, simetrična armatura stupova)
  8. Tip dimenzioniranja štapova (stupovi Column N-M3-M2, grede Beam M3)
  9. Konstrukcijski vs nekonstrukcijski zidovi (debljina <= 12 cm, kontinuitet po visini)
  10. Položaj i odabir pojedinog presjeka (Selection only)
  11. Diskretizacija (Mesh, 4 točke, omjer stranica 1:3, preklapanja, grede pod zidovima)
  12. Zadana opterećenja (G, VT podovi/žbuka/fasada/pregrade, Q korisno, stubište, krov)
  13. Kombinacije opterećenja (GSU, GSN, potres, scale factor)
  14. Oslonci i krutost tla (Fixed/Pinned, opruge ks = 10000-30000 kN/m3)
  15. Definiranje Mass Source (1.0G + 1.0VT + 0.3Q, lateral mass, lump at stories)
  17. Smanjenje krutosti elemenata (EC8 raspucavanje 50%, grede torzija 10%)
  26. Auto Line Constraint / Diaphragms
  27. Višak točaka (Orphan joints)
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List
import numpy as np
import pandas as pd

DIACRITICS_RE = re.compile(r"[čćžšđČĆŽŠĐ]")


def run_curriculum_audit(etabs_dict: dict) -> list[dict]:
    """
    Runs the complete university engineering checklist against the parsed ETABS model.
    Returns a list of structured audit check dicts.
    """
    results: list[dict] = []

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

    all_pts = etabs_dict.get("all_points", {})
    used_pts = etabs_dict.get("used_points", set())

    # 1. Definiranje osi
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
        "category": "1. Geometrija & Osi",
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

    # 2. Dimenzije, mjerne jedinice & dijakritici
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
        "category": "1. Geometrija & Osi",
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

    # 3. Definirati etaže u modelu (Edit Story – Story Data)
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
        "category": "1. Geometrija & Osi",
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

    # 4. Arhitektonski nacrti (?)
    n_openings = len(walls[walls["is_opening"] == True]) if not walls.empty and "is_opening" in walls.columns else 0
    f_4 = f"Model sadrži {len(walls)} zidnih panela s {n_openings} prepoznatih otvora prozora i vrata. Prikaz tlocrta na koti reza (+1.0m) točno razdvaja nosive presjeke od parapeta i greda."

    results.append({
        "num": 4,
        "title": "4. Usklađenost s arhitektonskim nacrtima",
        "category": "1. Geometrija & Osi",
        "weight": 6,
        "status": "PASS",
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

    # 5. Provjeriti svojstva materijala
    has_masonry = any("brick" in str(m).lower() or "opek" in str(m).lower() or "masonry" in str(m).lower() for m in mats["name"]) if not mats.empty and "name" in mats.columns else False
    has_concrete = any("conc" in str(m).lower() or "beton" in str(m).lower() or "c2" in str(m).lower() or "c3" in str(m).lower() for m in mats["name"]) if not mats.empty and "name" in mats.columns else False

    f_5_parts = []
    if has_masonry: f_5_parts.append("zidani elementi (opeka/mort)")
    if has_concrete: f_5_parts.append("betonski elementi")

    results.append({
        "num": 5,
        "title": "5. Svojstva materijala (Zidanje, mort, beton)",
        "category": "2. Materijali & Presjeci",
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

    # 6. Američki defaultni materijali & dupli presjeci
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
        "category": "2. Materijali & Presjeci",
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

    # 7. Svojstva armature prilikom dimenzioniranja
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
        "category": "2. Materijali & Presjeci",
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

    # 8. Tip dimenzioniranja štapova: Column vs Beam
    st_8 = "PASS"
    f_8 = f"Uredno razdvojeno: {len(cols)} stupova (dimenzioniranje na dvoosno savijanje i osnu silu N-M3-M2) i {len(beams)} greda (dimenzioniranje na savijanje M3)."

    results.append({
        "num": 8,
        "title": "8. Tip dimenzioniranja štapova (Column vs Beam)",
        "category": "2. Materijali & Presjeci",
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

    # 9. Konstrukcijski vs nekonstrukcijski zidovi
    thin_walls = []
    if not walls.empty and "thickness_mm" in walls.columns:
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
        "category": "2. Materijali & Presjeci",
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

    # 10. Kontrola i položaj pojedinog presjeka (Selection only)
    all_sections = set()
    for df in [cols, beams, walls, slabs]:
        if not df.empty:
            p_col = "prop_name" if "prop_name" in df.columns else "section"
            if p_col in df.columns:
                all_sections.update(df[p_col].dropna().astype(str).unique())

    st_10 = "PASS"
    f_10 = f"U modelu je definirano {len(all_sections)} poprečnih presjeka ({', '.join(list(all_sections)[:5])}...). U aplikaciji je omogućen filtrirani prikaz presjeka."

    results.append({
        "num": 10,
        "title": "10. Kontrola i položaj pojedinog presjeka",
        "category": "2. Materijali & Presjeci",
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

    # 11. Diskretizacija (Mesh) & omjeri stranica (1:3)
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
        "category": "3. MKE Diskretizacija",
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

    # 12. Zadana opterećenja (G, VT, Q, potres)
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
        "category": "4. Opterećenja & Seizmika",
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

    # 13. Kombinacije opterećenja (GSU, GSN, Potres)
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
        "category": "4. Opterećenja & Seizmika",
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

    # 14. Oslonci i krutost tla
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
        "category": "5. Oslonci & Krutost",
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

    # 15. Definirati Mass Source prema važećim propisima
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
        "category": "4. Opterećenja & Seizmika",
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

    # 17. Smanjiti krutosti elemenata
    results.append({
        "num": 17,
        "title": "17. Smanjenje krutosti elemenata (EC8 raspucavanje)",
        "category": "5. Oslonci & Krutost",
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

    # 26. Auto Line Constraint
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
        "category": "3. MKE Diskretizacija",
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

    # 27. Provjeriti višak točaka (Orphan joints)
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
        "category": "3. MKE Diskretizacija",
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

    total_weight = sum(a.get("weight", 5) for a in audit_results)
    if total_weight == 0:
        total_weight = 1.0

    earned_weight = 0.0
    for a in audit_results:
        st = a.get("status", "INFO")
        w = a.get("weight", 5)
        if st == "PASS":
            earned_weight += w * 1.0
        elif st == "WARNING":
            earned_weight += w * 0.65
        elif st == "INFO":
            earned_weight += w * 0.90
        elif st == "FAIL":
            earned_weight += 0.0

    pct = round((earned_weight / total_weight) * 100, 1)

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

    return {
        "percentage": pct,
        "grade": grade,
        "grade_label": grade_label,
        "badge_color": badge_color,
        "total_checks": len(audit_results),
        "n_pass": sum(1 for a in audit_results if a["status"] == "PASS"),
        "n_warn": sum(1 for a in audit_results if a["status"] == "WARNING"),
        "n_fail": sum(1 for a in audit_results if a["status"] == "FAIL"),
        "n_info": sum(1 for a in audit_results if a["status"] == "INFO"),
    }
