---
inclusion: manual
---
# Most prema Fazi B: DXF → numerički model spreman za proračun (plan)

> Ovo je PLAN, ne implementacija. Povezuje bazu znanja (modeliranje + provjere + mapiranje)
> sa stvarnim kodom aplikacije i definira redoslijed rada za Fazu B. Kontekst: profesor
> učitava studentski model (za sada DXF eksport; dugoročno izravna veza na ETABS) i dobiva
> rekonstruiran model + reviziju prema kontrolnoj listi.

## 1. Što već postoji u kodu (temelj)
- `phase2_dxf.py`: `detect_floor_layers` (etaže iz slojeva), `collect_closed_polylines`,
  `_classify_polyline`, `associate_and_classify` (element + presjek + kat), `reconstruct_grid`,
  `extract_all_dimension_texts`, `extract_drawing_annotations` (materijali/opterećenja iz
  bilješki), `parse_dxf` (glavni ulaz, vraća DataFrame elemenata).
- `phase1_e2k.py`: referentni model iz ETABS `.e2k` (stupci, grede, zidovi, ploče, etaže,
  materijali, opterećenja, oslonci) — postojeći "istinski" model za usporedbu.
- `phase3_validation.py`: prostorno poklapanje DXF ↔ ETABS.
- `curriculum_audit.py`: sustav ocjena PASS/WARN/FAIL — prirodno mjesto za nove provjere iz
  kontrolne liste (dokument B, sekcija A).

Zaključak: Faza B nije gradnja od nule — proširuje se postojeći DXF put i audit.

## 2. Što postaje KOD (iz baze znanja)

### 2.1 Rekonstrukcija modela iz DXF-a (proširenje phase2_dxf)
- Pojačati klasifikaciju po slojevima (dokument B, B2): mapiranje naziva slojeva → tip
  (ZID/STUP/GREDA/PLOCA + engleski i varijante). Konfigurabilno (config.py) da profesor može
  dodati vlastite konvencije imenovanja.
- Prepoznavanje stupova iz CIRCLE i INSERT (blokova), ne samo zatvorenih poligona.
- Prepoznavanje zidova iz para paralelnih linija (postojeća heuristika iz raster_vectorize
  `merge_wall_axes` može se ponovno iskoristiti na DXF linijama → os zida).
- Izlaz: strukturirani model (elementi + geometrija + kat + presjek) u istom obliku kao
  `phase1_e2k` output, da ga `phase3_validation` i `curriculum_audit` mogu koristiti.

### 2.2 Provjere modela (proširenje curriculum_audit)
Iz kontrolne liste (dokument B, A) u kod kao pojedinačne provjere sa statusom:
- A1 Geometrija: nepovezani elementi, čvorovi koji se ne poklapaju, viseći elementi,
  oslonci definirani. (dealbreakeri)
- A2 Masa/dinamika: postoji masa; modalna masa ≥ 90%; ekscentricitet ±5%; raspucala krutost —
  ove ovise o podacima iz ETABS-a (rezultati), pa se rade kad su rezultati dostupni.
- A3 Dijafragme: dodijeljena po etaži; tip primjeren (span/depth ≤ 3 → rigid kandidat).
- A4 Presjeci/materijali/opterećenja/kombinacije prisutni.
- A5 Pravilnost: ekscentricitet CM–CS, meki kat, reentrant corners — dijelom već postoji u
  auditu (T31 zidovi, T51 torzija); nadopuniti prema EN 1998-1.

### 2.3 Ponovna upotreba i konzistentnost
- Iste jedinice i konvencije kao postojeći moduli (mm za presjeke, m za koordinate).
- Statusi i ocjene idu kroz postojeći `calculate_audit_score` (ne izmišljati novi sustav).

## 3. Što postaje ULAZNA KONTROLA (profesor upisuje kad DXF nema podatke)
Iz dokumenta B, B3/B4 — podaci koji se ne mogu pouzdano izvući iz geometrije:
- **Broj etaža i visina kata** (jednolika ili po etaži) — kad DXF ne sadrži više tlocrta/kotu
  visine. Bez toga model ostaje 2D uz jasnu napomenu.
- **Materijali** (klasa betona/čelika) ako nisu u tekstu nacrta.
- **Opterećenja i kombinacije** (stalno/uporabno/vjetar/potres) — minimalno G i Q.
- **Oslonci** (tip: uklještenje/zglob) ako nisu na zasebnom sloju.
- **Pravila ponavljanja** po etažama (tipski kat).
UI: forma u novom tabu ("Model iz DXF-a") s poljima koja se popunjavaju samo za ono što
nedostaje; predpopuniti razumnim zadanim vrijednostima uz upozorenje da su pretpostavke.

## 4. Predloženi redoslijed Faze B (inkrementalno, svaki korak testabilan)
1. **DXF → 2D elementi jedne etaže** (proširena klasifikacija po slojevima + geometriji);
   prikaz i potvrda točnosti na stvarnom studentskom DXF-u.
2. **Ulazna kontrola za 2D → 3D** (broj etaža, visine); rekonstrukcija višeetažnog modela.
3. **Provjere A1 (geometrija/povezanost)** kao dealbreaker audit stavke.
4. **Provjere A3/A4/A5** (dijafragme, presjeci, pravilnost) — one izvedive bez rezultata analize.
5. **Provjere A2** (masa/modalna/ekscentricitet) — kad su dostupni ETABS rezultati (Faza 2 /
   buduća izravna veza na ETABS).
6. **Izvještaj** kroz postojeći `report.py` (revizijski elaborat) s nalazima.

## 5. Ograničenja i odgovornost (mora ostati eksplicitno)
- Alat rekonstruira i provjerava; **ovlašteni inženjer/profesor potvrđuje i preuzima
  odgovornost.** Rekonstruirani model je pomoć pri reviziji, ne ovjereni proračunski model.
- Sve pretpostavke (zadano iz ulazne kontrole, heuristička klasifikacija) moraju biti jasno
  označene u izlazu da se ne pomiješaju s pročitanim činjenicama.
- Geometrijska klasifikacija ima nesigurnost; kod dvojbe označiti nisku pouzdanost (kao što
  pdf_dims već radi za dimenzije).

## 6. Otvorena pitanja za korisnika (prije Faze B)
- Postoji li tipičan studentski DXF za razvoj (struktura slojeva, jedna etaža ili više)?
- Radi li se prvo o AB okvirnim zgradama, zidnim, ili oboje?
- Koliko revizija treba oslanjati se na ETABS rezultate (Faza 2) vs. samo na geometriju DXF-a?

---
## Izvori
- Postojeći moduli: phase2_dxf, phase1_e2k, phase3_validation, curriculum_audit, report,
  raster_vectorize (merge_wall_axes), pdf_dims (pouzdanost/status obrazac).
- Baza znanja: baza-znanja-modeliranje.md, baza-znanja-provjere-dxf.md (EN 1990, EN 1998-1,
  ETABS/CSI prakse, tipične greške).
