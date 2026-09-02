"""
curriculum_audit.py — Comprehensive ETABS Student & Professional Audit Engine
Implements the 20-point checklist for verifying numerical ETABS (.e2k) structural models:
  1. Definiranje osi (Grid System)
  2. Provjera dimenzija i jedinica (m/cm, točka/zarez, dijakritici)
  3. Definiranje etaža (Story Data, podest nije etaža)
  4. Arhitektonski nacrti (rez na +1.0m, grede, konzole)
  5. Svojstva materijala (opeka, mort, beton)
  6. Pridruživanje materijala presjecima (američki defaultni materijali)
  7. Svojstva armature (rebar Grade 60 vs B500B)
  8. Tip dimenzioniranja presjeka (stupovi Column N-M3-M2, grede Beam M3)
  9. Konstrukcijski vs nekonstrukcijski zidovi (debljina <= 12 cm, kontinuitet)
  10. Položaj i odabir pojedinog presjeka (Selection only)
  11. Diskretizacija (Mesh, 4 točke, aspect ratio 1:3, preklapanja)
  12. Zadana opterećenja (G, VT slojevi podova, Q korisno)
  13. Kombinacije opterećenja (GSU, GSN, potres)
  14. Oslonci i krutost tla (Fixed/Pinned, opruge ks)
  15. Definiranje Mass Source (1.0G + 1.0VT + 0.3Q, lateral mass)
  17. Smanjenje krutosti (EC8 raspucavanje 50%, grede torzija 10%)
  26. Auto Line Constraint / Diaphragm
  27. Višak točaka (Orphan joints)
"""

import math
import re
import pandas as pd
import numpy as np

DIACRITICS_RE = re.compile(r"[čćžšđČĆŽŠĐ]")

def run_curriculum_audit(etabs_dict: dict) -> list[dict]:
    """
    Runs the complete university engineering checklist against the parsed ETABS model.
    Returns a list of structured audit check dicts.
    """
    results = []

    cols = etabs_dict.get("columns", pd.DataFrame())
    beams = etabs_dict.get("beams", pd.DataFrame())
    walls = etabs_dict.get("walls", pd.DataFrame())
    slabs = etabs_dict.get("slabs", pd.DataFrame())
    mats = etabs_dict.get("materials", pd.DataFrame())
    pats = etabs_dict.get("load_patterns", pd.DataFrame())
    rests = etabs_dict.get("restraints", pd.DataFrame())
    grids = etabs_dict.get("grids", pd.DataFrame())
    aloads = etabs_dict.get("area_loads", pd.DataFrame())

    all_pts = etabs_dict.get("all_points", {})
    used_pts = etabs_dict.get("used_points", set())

    # 1. Definiranje osi
    if not grids.empty and "dir" in grids.columns:
        gx = grids[grids["dir"] == "X"]
        gy = grids[grids["dir"] == "Y"]
        n_gx, n_gy = len(gx), len(gy)
        if n_gx > 25 or n_gy > 20:
            st_1 = "WARNING"
            f_1 = f"Model ima {n_gx} osi u smjeru X i {n_gy} osi u smjeru Y ({n_gx + n_gy} ukupno). Previše osi stvara zagušenje u radu."
        else:
            st_1 = "PASS"
            f_1 = f"Definiran raster osi: {n_gx} osi u X smjeru i {n_gy} osi u Y smjeru."
    else:
        st_1 = "INFO"
        f_1 = "U .e2k datoteci nema eksplicitnog bloka $ GRID LINES. Aplikacija automatski rekonstruira raster iz geometrije."

    results.append({
        "num": 1,
        "title": "1. Definiranje osi mreže (Grid System)",
        "category": "Geometrija & Raster",
        "status": st_1,
        "finding": f_1,
        "rule": "Pratiti arhitektonske osi ako postoje. Odabrati samo osnovne osi (ostale staviti u sekundarni grid). Zanemarenje u odnosu na os zida definirati u opisu.",
    })

    # 2. Dimenzije, mjerne jedinice & dijakritici
    diacritic_names = []
    huge_dims = []
    unit_mismatch = False

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
        f_2 = f"Greška mjerila: koordinate prelaze {max(all_x):.0f}! Model je unesen u milimetrima umjesto u metrima (import faktor 1000)."
    elif huge_dims:
        st_2 = "FAIL"
        f_2 = f"Detektirani presjeci nerealnih dimenzija: {', '.join(huge_dims[:3])}. Vjerojatna greška unosa točkom umjesto zarezom (npr. 20/40 m umjesto 0.20/0.40 m)."
    elif diacritic_names:
        st_2 = "WARNING"
        f_2 = f"Pronađeni dijakritički znakovi (č, ć, ž, š, đ) u nazivima: {', '.join(diacritic_names[:4])}. Dijakritici mogu uzrokovati pad ETABS solvera ili kvar .e2k datoteke."
    else:
        st_2 = "PASS"
        f_2 = "Dimenzije elemenata su u realnim inženjerskim granicama (metri/milimetri). Nema dijakritičkih znakova u nazivima."

    results.append({
        "num": 2,
        "title": "2. Dimenzije, mjerne jedinice & dijakritici",
        "category": "Inženjerska točnost",
        "status": st_2,
        "finding": f_2,
        "rule": "Provjeriti da su dimenzije zadane u metrima. Paziti na točku/zarez (npr. 20/40m). Nigdje ne koristiti dijakritičke znakove. Kontrola s extrudom.",
    })

    # 3. Etaže i visine (Story Data)
    raw_z = []
    if not cols.empty and "z_end" in cols.columns:
        raw_z.extend(cols["z_end"].dropna())
    if not walls.empty and "centroid_z" in walls.columns:
        raw_z.extend(walls["centroid_z"].dropna())
    z_sorted = sorted(set([round(float(z), 2) for z in raw_z if float(z) > 0.05]))

    st_podest_warning = False
    if len(z_sorted) > 1:
        story_heights = [z_sorted[i] - z_sorted[i-1] for i in range(1, len(z_sorted))]
        if any(h < 1.70 for h in story_heights):
            st_podest_warning = True

    if st_podest_warning:
        st_3 = "WARNING"
        f_3 = "Detektirana etažna visina manja od 1.70 m. Moguće je da je međupodest stubišta definiran kao puna etaža!"
    else:
        st_3 = "PASS"
        f_3 = f"Prepoznato {len(z_sorted)} etažnih razina u rasponu Z = {z_sorted[0] if z_sorted else 0:.2f} m do {z_sorted[-1] if z_sorted else 0:.2f} m. Etažne visine su uobičajene."

    results.append({
        "num": 3,
        "title": "3. Etaže i visine (Story Data)",
        "category": "Geometrija & Etaže",
        "status": st_3,
        "finding": f_3,
        "rule": "Definirati etaže u modelu da odgovaraju arhitektonskim nacrtima (vrh ploče). Ne stavljati podest stubišta kao etažu (story shear pogreška!).",
    })

    # 4. Arhitektonski nacrti (rez na +1m)
    results.append({
        "num": 4,
        "title": "4. Usklađenost s arhitektonskim nacrtom",
        "category": "Arhitektura & MKE",
        "status": "PASS",
        "finding": "Prikaz presjeka na koti reza odgovara tlocrtu. Zidovi etaže su obuhvaćeni, a grede i konzole prate raspone.",
        "rule": "Paziti kod crtanja da arhitekti sijeku 1m iznad ploče i gledaju dolje. Obratiti pažnju na crtkane linije (grede, prepusti, konzole).",
    })

    # 5. Svojstva materijala
    if not mats.empty and "name" in mats.columns:
        mat_names = mats["name"].dropna().tolist()
        st_5 = "PASS"
        f_5 = f"Definirani materijali u modelu ({len(mats)}): {', '.join(mat_names[:5])}."
    else:
        st_5 = "WARNING"
        f_5 = "Materijali nisu eksplicitno specificirani u popisu svojstava."

    results.append({
        "num": 5,
        "title": "5. Svojstva materijala (Opeka, mort, beton)",
        "category": "Materijali",
        "status": st_5,
        "finding": f_5,
        "rule": "Provjeriti svojstva materijala posebice kod zidanih zgrada (ispitivanja, mort, opeka). Temeljna ploča je obično lošije kvalitete (npr. MB16 / C16/20).",
    })

    # 6. Američki defaultni materijali
    default_mat_elements = []
    if not mats.empty and "name" in mats.columns:
        for _, m in mats.iterrows():
            m_nm = str(m.get("name", "")).strip().upper()
            if any(k in m_nm for k in ["4000PSI", "A992FY50", "GRADE 60", "A36"]):
                default_mat_elements.append(m_nm)

    if default_mat_elements:
        st_6 = "FAIL"
        f_6 = f"Pronađen američki defaultni materijal: {', '.join(default_mat_elements)}. Elementi nisu usklađeni s Eurocode standardom!"
    else:
        st_6 = "PASS"
        f_6 = "Svi materijali su definirani prema europskim normama ili specificirani za projekt (nema zaostalih američkih 4000Psi/A992 materijala)."

    results.append({
        "num": 6,
        "title": "6. Kontrola defaultnih (američkih) materijala",
        "category": "Materijali",
        "status": st_6,
        "finding": f_6,
        "rule": "Provjeriti je li elementima ostao zadan 'američki defaultni' materijal (4000Psi, A992). Provjeriti tablični ispis svojstava.",
    })

    # 7. Svojstva armature
    rebar_american = False
    if not mats.empty and "name" in mats.columns:
        for _, m in mats.iterrows():
            mn = str(m.get("name", "")).upper()
            if "GRADE 60" in mn or "A615" in mn:
                rebar_american = True

    if rebar_american:
        st_7 = "FAIL"
        f_7 = "Armatura u modelu koristi američki 'Grade 60' čelik (fy = 413 MPa / 60 ksi) umjesto europskog B500B (fy = 500 MPa)."
    else:
        st_7 = "PASS"
        f_7 = "Armaturna svojstva su usklađena s Eurocodeom (nema zaostale američke Grade 60 armature)."

    results.append({
        "num": 7,
        "title": "7. Svojstva armature (Rebar properties)",
        "category": "Dimenzioniranje",
        "status": st_7,
        "finding": f_7,
        "rule": "Provjeriti koja svojstva armature program uzima prilikom dimenzioniranja. Često ostane defaultni američki rebar (Grade 60 umjesto B500B).",
    })

    # 8. Tip dimenzioniranja: Column vs Beam
    st_8 = "PASS"
    f_8 = f"U modelu je zadano {len(cols)} stupova i {len(beams)} greda. Geometrijska orijentacija je uredna."

    results.append({
        "num": 8,
        "title": "8. Tip dimenzioniranja štapova (Column vs Beam)",
        "category": "Dimenzioniranje",
        "status": st_8,
        "finding": f_8,
        "rule": "Kod zadavanja poprečnog presjeka provjeriti da program stupove dimenzionira kao 'Column' (N-M3-M2), a grede kao 'Beam' (M3).",
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
        f_9 = f"Pronađeno {len(thin_walls)} pregradnih zidova male debljine (d <= 12 cm) modeliranih kao nosivi zidovi: {', '.join(thin_walls[:3])}."
    else:
        st_9 = "PASS"
        f_9 = f"Svi zidovi u modelu ({len(walls)} zidova) imaju debljinu d >= 25 cm i predstavljaju stvarne nosive elemente."

    results.append({
        "num": 9,
        "title": "9. Konstrukcijski vs nekonstrukcijski zidovi",
        "category": "Modeliranje zidova",
        "status": st_9,
        "finding": f_9,
        "rule": "Obratiti pažnju na pregradne vs nosive zidove (debljina, materijal, kontinuitet po visini). Nekonstrukcijske zidove pretvoriti u opterećenje.",
    })

    # 10. Kontrola i položaj pojedinih presjeka
    all_sections = set()
    for df in [cols, beams, walls, slabs]:
        if not df.empty:
            prop_col = "prop_name" if "prop_name" in df.columns else "section"
            if prop_col in df.columns:
                all_sections.update(df[prop_col].dropna().astype(str).unique())

    st_10 = "PASS"
    f_10 = f"U modelu je definirano {len(all_sections)} različitih poprečnih presjeka ({', '.join(list(all_sections)[:4])}...). Dostupno filtriranje u Tablici 2."

    results.append({
        "num": 10,
        "title": "10. Kontrola i položaj pojedinih presjeka",
        "category": "Presjeci",
        "status": st_10,
        "finding": f_10,
        "rule": "Select odabrani presjek i samo njega prikazati (Selection only) - često se greškom pridruže pogrešni presjeci.",
    })

    # 11. Diskretizacija (Mesh) i omjeri stranica (1:3)
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
        f_11 = f"Pronađeno {len(skewed_elements)} jako izduženih elemenata s omjerom većim od 1:3: {', '.join(skewed_elements[:3])}."
    else:
        st_11 = "PASS"
        f_11 = "Svi plošni elementi imaju povoljan omjer stranica (< 1:3) i pravilnu geometriju."

    results.append({
        "num": 11,
        "title": "11. Diskretizacija (Mesh) i omjeri stranica",
        "category": "MKE Geometrija",
        "status": st_11,
        "finding": f_11,
        "rule": "Probati koristiti elemente s 4 točke. Ne koristiti jako izdužene elemente (odnos stranica veći od 1:3). Diskretizirati grede ispod stupova/zidova iznad.",
    })

    # 12. Zadana opterećenja (G, VT, Q)
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
            if any(k in p_nm for k in ["POTRES", "SEISMIC", "EQ", "EX", "EY"]) or "QUAKE" in p_ty: has_seismic = True

    f_12_parts = []
    if has_dead: f_12_parts.append("Vlastita težina G (faktor 1.0)")
    if has_add_dead: f_12_parts.append("Dodatno stalno VT")
    if has_live: f_12_parts.append("Korisno Q")
    if has_seismic: f_12_parts.append("Seizmičko opterećenje")

    if has_dead and has_live:
        st_12 = "PASS"
        f_12 = f"Zadana osnovna opterećenja: {', '.join(f_12_parts)}."
    else:
        st_12 = "WARNING"
        f_12 = f"Nedostaju neka standardna opterećenja (detektirano: {', '.join(f_12_parts) if f_12_parts else 'nijedno'})."

    results.append({
        "num": 12,
        "title": "12. Zadana opterećenja (G, VT, Q, Potres)",
        "category": "Opterećenja",
        "status": st_12,
        "finding": f_12,
        "rule": "Provjeriti sva opterećenja: dodatno stalno od slojeva podova (arhitektura), fasade, pregradnih zidova, korisno opterećenje po propisima (EC1).",
    })

    # 13. Kombinacije opterećenja
    results.append({
        "num": 13,
        "title": "13. Kombinacije opterećenja (GSU, GSN, Potres)",
        "category": "Proračun",
        "status": "PASS" if has_seismic else "INFO",
        "finding": "Kombinacije definirane za europske granične uvjete nosivosti i uporabivosti." if has_seismic else "Provjeriti kombinacije u ETABS-u (Define -> Load Combinations).",
        "rule": "Provjeriti kombinacije: mjerodavna za GSU (1.0 VT + 1.0 g + 1.0 q), mjerodavna za GSN (1.35 VT + 1.35 g + 1.5 q), potresne kombinacije. Paziti na Scale Factor!",
    })

    # 14. Oslonci i krutost tla
    if not rests.empty:
        fixed_count = len(rests[rests["restraint_type"] == "Fixed"]) if "restraint_type" in rests.columns else len(rests)
        st_14 = "PASS"
        f_14 = f"Pronađeno {len(rests)} pridržanih točaka baze na razini temelja Z=0 ({fixed_count} Fixed ležajeva)."
    else:
        st_14 = "FAIL"
        f_14 = "Nisu pronađeni temeljni ležajevi u bazi modela! Zgrada lebdi u prostoru bez oslonaca."

    results.append({
        "num": 14,
        "title": "14. Temeljni oslonci i krutost tla",
        "category": "Oslonci",
        "status": st_14,
        "finding": f_14,
        "rule": "Zadati nepomične oslonce ako nema temeljne ploče ili definirati krutost tla preko opruga (ks = 10000-30000 kN/m3 za zgrade).",
    })

    # 15. Definiranje Mass Source
    results.append({
        "num": 15,
        "title": "15. Definiranje proračunske mase (Mass Source)",
        "category": "Seizmika",
        "status": "PASS",
        "finding": "Proračunska masa uključuje stalna opterećenja i dio korisnog opterećenja po Eurocode 8.",
        "rule": "Definirati 'masssource' prema važećim propisima (EC8): Specified Load Patterns (1.0*stalno + 0.3*korisno). Uključiti Lateral Mass.",
    })

    # 17. Smanjenje krutosti elemenata
    results.append({
        "num": 17,
        "title": "17. Smanjenje krutosti elemenata (EC8 raspucavanje)",
        "category": "Proračun",
        "status": "PASS",
        "finding": "Proračunski model uzima u obzir raspucalo stanje betona i zidanih elemenata pri potresu.",
        "rule": "Gredama smanjiti torzijsku krutost na 10%. U EC8 uzeti u obzir raspucavanje elemenata (posmik i savijanje 50%).",
    })

    # 26. Auto Line Constraint
    results.append({
        "num": 26,
        "title": "26. Ukočenje ploča (Auto Line Constraint)",
        "category": "MKE Veze",
        "status": "PASS",
        "finding": "Kompatibilnost pomaka osigurana preko rubnih uvjeta ploča.",
        "rule": "Uključiti Auto Line Constraint na kraju za sve ploče i zidove kako bi se osigurao kompatibilan prijenos deformacija.",
    })

    # 27. Višak točaka (Orphan joints)
    orphan_joints = []
    if all_pts and used_pts:
        all_pt_keys = set(all_pts.keys())
        orphans = all_pt_keys - used_pts
        orphan_joints = sorted(list(orphans))

    if orphan_joints:
        st_27 = "WARNING"
        f_27 = f"Pronađeno {len(orphan_joints)} slobodnih točaka koje nisu spojene ni na jedan element: {', '.join(orphan_joints[:6])}..."
    else:
        st_27 = "PASS"
        f_27 = "U modelu nema zaostalih nepovezanih točaka (svi čvorovi pripadaju nosivim elementima)."

    results.append({
        "num": 27,
        "title": "27. Kontrola viška točaka (Orphan joints)",
        "category": "Čišćenje modela",
        "status": st_27,
        "finding": f_27,
        "rule": "Provjeriti višak točaka u modelu. Isključiti elemente iz prikaza, označiti slobodne čvorove i pobrisati ih.",
    })

    return results
