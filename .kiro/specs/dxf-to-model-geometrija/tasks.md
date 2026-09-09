# Implementation Plan

> Napomene: novi modul `dxf_model.py` + dopune `config.py`; ponovna upotreba `phase2_dxf.py`.
> Ne mijenjati `phase1_e2k.py` ni `phase3_validation.py`. Testovi u `tests/test_dxf_model.py`.
> Testni primjeri: `sample_dxf/ab_zgrada.dxf` i `sample_dxf/jscad_floorplan.dxf`. Sve na
> hrvatskom gdje je tekst; postojeći pytest mora ostati zelen.

- [ ] 1. Konfiguracija: mapiranje slojeva i pragovi heuristika (config.py)
  - [ ] 1.1 Dodaj `dxf_layer_map` (tip → ključne riječi: STUP/COL/COLUMN, GREDA/BEAM, ZID/WALL, PLOCA/SLAB, OSI/GRID, KOTE/DIM) i `dxf_geom_thresholds` (max površina stupa, raspon debljine zida, raspon duljine grede, tolerancija spoja) sa zadanim vrijednostima iz baze znanja (poglavlje 1).
  - [ ] 1.2 Dodaj `dxf_default_story_height`, `dxf_default_n_stories`. Test: Config se instancira i sadrži nova polja s očekivanim defaultima.
  - _Zahtjevi: 2.3, 3.1, 5.2_

- [ ] 2. Kostur modula dxf_model.py + klasifikacija po slojevima
  - [ ] 2.1 Kreiraj `dxf_model.py` s potpisima svih funkcija (docstringovi) i `classify_by_layer(layer_name, cfg) -> Optional[str]`.
  - [ ] 2.2 Testovi: STUP/COL/COLUMN→"column", ZID/WALL→"wall", GREDA/BEAM→"beam", PLOCA/SLAB→"slab", nepoznat→None; velika/mala slova nebitna.
  - _Zahtjevi: 2.1, 2.2, 8.1_

- [ ] 3. Klasifikacija geometrijskom heuristikom + pouzdanost
  - [ ] 3.1 `classify_by_geometry(poly, cfg) -> (tip, pouzdanost)`: mala kompaktna kontura/kružnica→column; velika zatvorena kontura→slab; koristi postojeći `phase2_dxf._classify_polyline` gdje pomaže.
  - [ ] 3.2 `detect_walls_from_lines(lines, cfg) -> list[wall]`: par bliskih paralelnih linija (razmak u rasponu debljine zida) → jedan zid (os + debljina).
  - [ ] 3.3 Testovi: sintetske konture/linije → očekivani tip + pouzdanost; par paralelnih → jedan zid; niska pouzdanost označena.
  - _Zahtjevi: 3.1, 3.2, 3.3_

- [ ] 4. Učitavanje DXF-a, jedinice, raster, kote (reuse phase2_dxf)
  - [ ] 4.1 `_load_dxf(path)`: ezdxf.recover.readfile + čitanje INSUNITS → scale; graceful na nečitljiv/prazan.
  - [ ] 4.2 Poveži postojeće: `reconstruct_grid`, `extract_all_dimension_texts`, `collect_closed_polylines`; pridruži reference osi elementima.
  - [ ] 4.3 Testovi: učitavanje ab_zgrada.dxf vraća raster (6 x-osi, 5 y-osi); nečitljiv ulaz → jasan status bez rušenja.
  - _Zahtjevi: 1.1, 1.2, 1.3, 4.1, 4.2_

- [ ] 5. Rekonstrukcija etaža i 3D (2D → 3D)
  - [ ] 5.1 `reconstruct_stories(doc, msp, cfg, user_input=None)`: iz slojeva/tlocrta ILI iz unosa (broj etaža, visina, ponavljanje tipske etaže) → kote Z; ako nema podataka → 2D + napomena.
  - [ ] 5.2 Testovi: zadani broj/visina → ispravne kote Z; ponavljanje tipske etaže replicira elemente; bez podataka → 2D uz warning; pretpostavke označene u meta.
  - _Zahtjevi: 5.1, 5.2, 5.3, 5.4_

- [ ] 6. Sastavljanje strukturiranog modela (izlaz kcompatibilan s phase1_e2k)
  - [ ] 6.1 `build_model_from_dxf(path, cfg, user_input=None) -> dict`: orkestrira 4→3→5, sastavlja dict (columns/beams/walls/slabs DataFrame + stories + grid + meta); pridružuje presjek iz kotne oznake; svaki element ima source + confidence.
  - [ ] 6.2 Testovi: izlaz ima sve ključeve; kolone poravnate s phase1_e2k (name, story, koordinate, dimenzije, section); presjek "40/40"→400×400 pridružen.
  - _Zahtjevi: 6.1, 6.2, 6.3_

- [ ] 7. Kontrola cjelovitosti geometrije
  - [ ] 7.1 `check_geometry_integrity(model, cfg) -> list[warning]`: spojevi unutar tolerancije, viseći elementi, duplikati, dimenzije izvan granica.
  - [ ] 7.2 Testovi: viseći element/duplikat/dimenzija izvan granica → odgovarajuće upozorenje; čist model → bez upozorenja.
  - _Zahtjevi: 7.1, 7.2, 7.3_

- [ ] 8. Integracijski testovi na stvarnim primjerima + robusnost
  - [ ] 8.1 `ab_zgrada.dxf`: build_model_from_dxf → ~120 stupova (30×4), 4 etaže, zidovi jezgre, ploče, raster 6×5; bez neuhvaćene greške.
  - [ ] 8.2 `jscad_floorplan.dxf`: uspješna rekonstrukcija bez greške; prepoznati barem zidove i ploču; rezultat s pouzdanostima.
  - [ ] 8.3 Robusnost: prazan/nečitljiv DXF → meta.ok False, bez rušenja.
  - _Zahtjevi: 8.1, 8.2, 8.3_

- [ ] 9. (Opcionalno u ovom dijelu) Streamlit ulaz "Model iz DXF-a"
  - [ ] 9.1 Dodaj minimalni tab/ulaz koji poziva build_model_from_dxf i prosljeđuje rezultat postojećem prikazu/validaciji (jer je izlaz kompatibilan). Ako je preopsežno, ostaviti za sljedeći dio Faze B.
  - [ ] 9.2 Smoke test importa; bez regresije.
  - _Zahtjevi: 6.1, 8.3_

- [ ] 10. Checkpoint: puni pytest zeleno + commit/push na main
  - Pokreni cijeli pytest (postojeći + novi test_dxf_model). Commit i push na main.
  - _Zahtjevi: 8.3_
