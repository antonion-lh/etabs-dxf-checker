# Design Document

## Overview

Ovaj dizajn opisuje modul za **geometrijsku rekonstrukciju numeričkog modela zgrade iz DXF-a**
(Faza B, Dio 1). Modul čita DXF, prepoznaje konstruktivne elemente (stup/greda/zid/ploča),
rekonstruira raster i etaže te vraća strukturirani model kompatibilan s izlazom `phase1_e2k.py`.
Ne mijenja postojeće module; nadograđuje `phase2_dxf.py` i uvodi novi orkestracijski modul
`dxf_model.py`.

Ključna razlika u odnosu na postojeći `phase2_dxf.parse_dxf`: on daje ravni DataFrame elemenata
za prostornu usporedbu s ETABS-om (validacija). Ovdje je cilj **rekonstruirati model** (elementi
po tipu + etaže + raster + pouzdanost) kao samostalni izvor, oblika kao `phase1_e2k` output, da
ga validacija/audit/izvještaj mogu koristiti i bez ETABS `.e2k` datoteke.

## Glossary

- **`dxf_model.py`:** novi modul, orkestrira rekonstrukciju i vraća strukturirani model.
- **Strukturirani model:** `dict` s ključevima `columns`, `beams`, `walls`, `slabs` (DataFrame)
  + `stories` (list) + `grid` + `meta` (pouzdanost, upozorenja) — kao `phase1_e2k`.
- **Mapiranje slojeva:** `config.py` tablica `dxf_layer_map` (regex/ključne riječi → tip).
- **Razina pouzdanosti:** polje `confidence` po elementu (visoka/srednja/niska).

## Architecture

Tok podataka:

    DXF datoteka
        |
        v
    učitavanje (ezdxf.recover.readfile) + jedinice (INSUNITS -> scale)     [Zahtjev 1]
        |
        v
    detekcija slojeva etaža (phase2_dxf.detect_floor_layers, prošireno)     [Zahtjev 5]
    rekonstrukcija rastera (phase2_dxf.reconstruct_grid)                    [Zahtjev 4]
    kotni tekstovi (phase2_dxf.extract_all_dimension_texts)
    zatvoreni poligoni (phase2_dxf.collect_closed_polylines)
        |
        v
    KLASIFIKACIJA elemenata:                                               [Zahtjevi 2,3]
      1) po sloju (dxf_layer_map) -> tip + visoka pouzdanost
      2) inače geometrijska heuristika (_classify_polyline + nova pravila
         za zid=par paralelnih linija, greda=linija stup-stup) -> pouzdanost
        |
        v
    pridruživanje presjeka iz kotnih oznaka + reference osi                 [Zahtjev 6]
        |
        v
    rekonstrukcija etaža i 3D (kote Z; ponavljanje tipske etaže; unos)      [Zahtjev 5]
        |
        v
    kontrola cjelovitosti (spojevi, viseći, duplikati, realnost dimenzija)  [Zahtjev 7]
        |
        v
    strukturirani model (dict kao phase1_e2k) + meta (upozorenja/pouzdanost) [Zahtjev 6]

Novi modul `dxf_model.py` poziva postojeće funkcije iz `phase2_dxf.py` gdje god je moguće
(ponovna upotreba), a dodaje: mapiranje slojeva, heuristiku za zid/gredu, rekonstrukciju etaža
u 3D, i sastavljanje izlaza u `phase1_e2k` oblik.

## Components and Interfaces

### config.py (dopuna)
- `dxf_layer_map: dict[str, list[str]]` — tip → ključne riječi (STUP: [STUP, COL, COLUMN], …).
- `dxf_geom_thresholds: dict` — pragovi heuristika (max površina stupa, raspon debljine zida,
  raspon duljine grede, tolerancija spoja) — zadane vrijednosti iz baze znanja (poglavlje 1).
- `dxf_default_story_height`, `dxf_default_n_stories` — za slučaj kad podaci nedostaju.

### dxf_model.py (novi modul)
- `classify_by_layer(layer_name, cfg) -> Optional[str]`
  Vraća tip elementa iz naziva sloja prema `dxf_layer_map`, ili None.
- `classify_by_geometry(entity_or_poly, cfg) -> tuple[str, str]`
  Vraća (tip, pouzdanost) iz geometrije; koristi postojeći `_classify_polyline` + nova pravila
  (par paralelnih linija → zid; linija između dva stupa → greda).
- `detect_walls_from_lines(lines, cfg) -> list[wall]`
  Prepoznaje zidove iz parova bliskih paralelnih linija (reuse ideje `merge_wall_axes`).
- `reconstruct_stories(doc, msp, cfg, user_input=None) -> list[story]`
  Rekonstruira etaže iz slojeva/tlocrta ili iz korisničkog unosa (broj/visina/ponavljanje).
- `check_geometry_integrity(model, cfg) -> list[warning]`
  Provjere spojeva, visećih elemenata, duplikata, realnosti dimenzija.
- `build_model_from_dxf(path, cfg, user_input=None) -> dict`
  Glavni ulaz; orkestrira sve, vraća strukturirani model + `meta`.

### Integracija
- Streamlit: novi izvor modela "iz DXF-a" koji poziva `build_model_from_dxf` i dalje koristi
  postojeći prikaz/validaciju/audit (jer je izlaz kompatibilan s `phase1_e2k`).
- Ne mijenja `phase1_e2k` ni `phase3_validation`; samo im daje kompatibilan ulaz.

## Data Models

### Strukturirani model (izlaz `build_model_from_dxf`)
```
{
  "columns": DataFrame[name, story, x, y, width_mm, height_mm, section,
                       layer, source, confidence],
  "beams":   DataFrame[name, story, x_start, y_start, x_end, y_end,
                       width_mm, height_mm, section, layer, source, confidence],
  "walls":   DataFrame[name, story, x_start, y_start, x_end, y_end,
                       thickness_mm, section, layer, source, confidence],
  "slabs":   DataFrame[name, story, centroid_x, centroid_y, area_m2,
                       thickness_mm, layer, source, confidence],
  "stories": [ {name, z_bottom, z_top, height}, ... ],
  "grid":    { "x_axes": [...], "y_axes": [...], "labels": {...} },
  "meta":    { "units": "mm", "warnings": [...], "assumptions": [...],
               "n_elements": N, "confidence_summary": {...} },
}
```
Kolone se drže poravnate s `phase1_e2k` gdje postoje (name, story, koordinate, dimenzije,
section, material) da postojeći moduli rade bez izmjena. `material` se ne postavlja u ovom
dijelu (prazno/None) — dolazi u kasnijem dijelu Faze B.

### source i confidence
- `source ∈ {"layer", "geometry"}` — odakle klasifikacija.
- `confidence ∈ {"visoka", "srednja", "niska"}` — koliko je sigurna.

## Error Handling

- Nečitljiv/prazan DXF → `build_model_from_dxf` vraća `{"meta": {"ok": False, "error": ...}}`,
  bez rušenja (analogno postojećem `vectorize_floorplan` obrascu).
- Nepoznate jedinice → zadana jedinica + `meta.assumptions`.
- Nema podataka za 3D → 2D model + `meta.warnings`.
- Svaki korak u try/except; djelomičan uspjeh vraća ono što je rekonstruirano + upozorenja.
- Nula prepoznatih elemenata → jasan status i prijedlog (provjeri slojeve/mapiranje).

## Testing Strategy

### Jedinični testovi (tests/test_dxf_model.py)
- `classify_by_layer`: STUP/COL/COLUMN → "column"; ZID/WALL → "wall"; nepoznat → None.
- `classify_by_geometry`: mala kompaktna kontura → column (visoka); par paralelnih → wall;
  velika kontura → slab; s pripadnom pouzdanošću.
- `detect_walls_from_lines`: dvije paralelne linije na razmaku = debljina → jedan zid.
- `reconstruct_stories`: iz zadanog broja/visina gradi ispravne kote Z; ponavljanje tipske etaže.
- `check_geometry_integrity`: viseći element, duplikat, dimenzija izvan granica → upozorenja.
- Izlazni oblik: `build_model_from_dxf` vraća sve ključeve; kolone poravnate s phase1_e2k.

### Integracijski testovi (na stvarnim primjerima iz sample_dxf/)
- `ab_zgrada.dxf`: očekivati ~120 stupova (30/etaža × 4), 4 etaže, zidovi jezgre, ploče;
  raster 6×5; bez neuhvaćene greške.
- `jscad_floorplan.dxf`: uspješna rekonstrukcija bez greške; prepoznati barem zidove (A-WALL)
  i ploču (S-SLAB); rezultat s pouzdanostima (očekivano više "srednja/niska" jer je arhitektonski).

### Regresija
- Postojeći pytest paket mora ostati zelen; novi testovi u `tests/test_dxf_model.py`.
- `phase2_dxf` i `phase1_e2k` se ne mijenjaju (samo se koriste/čitaju).
