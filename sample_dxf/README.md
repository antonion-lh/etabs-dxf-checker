# Testni DXF primjeri za Fazu B (izrada numeričkog modela iz DXF-a)

Ova mapa sadrži dva DXF primjera koji služe kao ulazni materijal za razvoj i
testiranje pretvorbe vektorskog nacrta u numerički model zgrade.

## 1. `jscad_floorplan.dxf` — stvarni arhitektonski nacrt
- **Izvor:** `jscad/sample-files` (GitHub), datoteka `dxf/dxf-parser/floorplan.dxf`.
- **Licenca:** MIT (dopušta korištenje uz zadržavanje napomene o izvoru).
- **Tip:** jednoetažna obiteljska kuća (arhitektonski + dijelom konstruktivni nacrt).
- **Sadržaj:** ~950 entiteta — 624 LINE, 124 LWPOLYLINE, 89 TEXT, 63 DIMENSION, te
  CIRCLE, ARC, HATCH, INSERT, MTEXT, LEADER. 24 sloja.
- **Slojevi (AIA konvencija):** `A-WALL` (zidovi), `S-STEM-WALL`, `S-FOOTER` (temelji),
  `S-SLAB` (ploča), `R-BEAM` (grede), `R-TRUSS` (krovni nosači), `A-OPENING` (otvori),
  `A-DIMS-1` (kote), `A-TEXT`/`A-NOTE` (tekst) i dr.
- **Jedinice:** milimetri (INSUNITS = 4).
- **Namjena:** dokaz da pipeline radi na *stvarnom, "neurednom"* nacrtu s realnim
  slojevima, kotama, tekstom i blokovima. Nije idealna višeetažna AB zgrada, ali daje
  pravu raznolikost entiteta i konvenciju imenovanja.

## 2. `ab_zgrada.dxf` — sintetski višeetažni AB tlocrt
- **Izvor:** generiran skriptom `generate_ab_zgrada.py` (ovaj repozitorij, ezdxf).
- **Licenca:** vlastito djelo, slobodno za korištenje u projektu.
- **Tip:** pravilna armiranobetonska okvirna zgrada, **4 etaže**, raster stupova.
- **Geometrija:**
  - Raster osi: 5 polja u X (6+6+6+5+6 m) × 4 polja u Y (5+6+6+5 m) → osi A–F × 1–5.
  - Stupovi 400/400 mm na svim sjecištima osi (30 po etaži).
  - Grede 300/500 mm po svim osima (X i Y).
  - Zidovi jezgre (stubište/lift) debljine 250 mm, s otvorom za vrata.
  - Ploča debljine 200 mm (obris etaže).
  - Visina kata 3,20 m; etaže prostorno razmaknute po X (odvojeni tlocrti).
- **Slojevi (jasna konvencija):** `OSI`, `STUP`, `GREDA`, `ZID`, `PLOCA`, `KOTE`, `TEKST`.
- **Kotne oznake:** presjeci stupa (`S 400/400`), grede (`G 300/500`), zida (`Z t=250`).
- **Jedinice:** milimetri (INSUNITS = 4).
- **Sadržaj:** 120 stupova, 196 greda (LINE), 20 segmenata zida, 4 ploče, 88 osi.
- **Namjena:** ciljni tip zgrade za Fazu B — višeetažni AB okvir sa stupovima, gredama,
  jezgrom i pločama. Parametriziran (klasa `Param` u generatoru) pa se lako mijenja broj
  etaža, raspon polja i dimenzije presjeka.

### Ponovno generiranje sintetskog nacrta
```
python3 sample_dxf/generate_ab_zgrada.py
```
Parametri se mijenjaju u klasi `Param` na vrhu skripte (broj etaža, razmaci osi,
dimenzije stupova/greda/zidova/ploča, jezgra).

## Napomena o realnom studentskom nacrtu
Ova dva primjera pokrivaju stvarnu "neurednost" (jscad) i ciljnu strukturu/složenost
(sintetski AB). Kad bude dostupan stvarni studentski DXF (višeetažna zgrada kakvu profesor
tipično prima), pipeline razvijen na ovim primjerima prilagodit će se njemu; slojevi i
konvencija imenovanja u stvarnom nacrtu mogu se razlikovati pa se mapiranje slojeva drži
konfigurabilnim.
