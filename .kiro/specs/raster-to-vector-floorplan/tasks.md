# Implementation Plan

> Napomena o ograničenjima alata: sve datoteke u ovom projektu kreiraju se ISKLJUCIVO preko `execute_bash` + Python skripte dekodirane iz base64 na `/tmp` (bez `fs_write`/`str_replace`/`edit`, bez heredoc-a). Skripte pisu izlaz s `open(path, "w", encoding="utf-8")`. Privremene datoteke u `/tmp` ocistiti na kraju. Sav kod je UTF-8.
>
> Okruzenje: Python (numpy, scipy.ndimage, Pillow, PyMuPDF/fitz, ezdxf). BEZ OpenCV. Ciljna platforma Streamlit Cloud s ogranicenjem ~1GB RAM (paziti na DPI cap i maksimalne dimenzije rasterizacije).

- [ ] 1. Kostur modula `raster_vectorize.py`
  - Definiraj tip `Segment` (npr. `namedtuple`/`dataclass` s `x1,y1,x2,y2`) i strukturu `Params` (dataclass ili dict) s poljima: `threshold`, `min_len_px`, `max_gap_px`, `angle_tol_deg`, `denoise_iters`, `dpi_cap`, `px_to_unit`.
  - Napisi prazne potpise svih funkcija s docstringovima: `rasterize_input`, `binarize`, `denoise`, `detect_line_segments`, `merge_collinear`, `segments_to_dxf`, `vectorize_floorplan`.
  - Kreiraj `tests/test_raster_vectorize.py` s import smoke testom modula.
  - _Zahtjevi: 1-8 (kostur)_

- [ ] 2. Rasterizacija i ucitavanje ulaza (`rasterize_input`)
  - [ ] 2.1 Implementiraj PDF granu preko `fitz`: renderiraj zadanu stranicu uz DPI cap i zastitu maksimalnih dimenzija (spusti DPI ako bi rezultat premasio limit da se ne probije ~1GB RAM).
  - [ ] 2.2 Implementiraj slikovnu granu preko Pillow (PNG/JPG) i pretvorbu u grayscale numpy array; jedinstveni izlaz `gray` bez obzira na tip ulaza.
  - [ ] 2.3 Napisi test na sintetskom PNG-u (i po mogucnosti malom PDF-u) da vraca 2D grayscale array ocekivanih dimenzija.
  - _Zahtjevi: 1.1, 1.2, 1.3, 8.2_

- [ ] 3. Binarizacija (`binarize`)
  - Implementiraj Otsu prag preko numpy histograma kada je `threshold=None`; inace koristi zadani podesivi prag (npr. ~174 iz spike-a kao referenca).
  - Vrati binarnu masku (crno = crtez / True) konzistentne orijentacije.
  - Unit test na sintetskoj slici s poznatim brojem crnih piksela (provjeri da Otsu i fiksni prag daju ocekivanu masku).
  - _Zahtjevi: 2.1, 2.2_

- [ ] 4. Ciscenje suma (`denoise`)
  - Implementiraj morfolosko otvaranje/zatvaranje preko `scipy.ndimage` s podesivim brojem iteracija `denoise_iters`.
  - Unit test: izolirani pikseli (sol-papar sum) se uklanjaju, a kontinuirane linije ostaju.
  - _Zahtjevi: 2.3_

- [ ] 5. Detekcija linijskih segmenata (`detect_line_segments`)
  - Implementiraj run-length detekciju ORTOGONALNIH linija (horizontala + vertikala) s pragom `min_len_px`; dijagonale se run-length pristupom prirodno izostavljaju (napomena: dijagonalne "X" oznake time otpadaju).
  - Uredno vrati praznu listu (0 segmenata) kada nema linija dovoljne duljine.
  - Unit test na sintetskoj slici s poznatim brojem/pozicijama linija.
  - _Zahtjevi: 3.1, 3.2, 3.3_

- [ ] 6. Spajanje kolinearnih segmenata (`merge_collinear`)
  - Spoji segmente na istom pravcu unutar `angle_tol_deg` i s razmakom manjim od `max_gap_px`.
  - Unit test: dva kolinearna segmenta u toleranciji se spoje u jedan; segmenti izvan tolerancije/gapa ostaju odvojeni.
  - _Zahtjevi: 4.1, 4.2, 4.3_

- [ ] 7. Redukcija suma (nauceno iz spike-a)
  - Postavi visi default `min_len_px` da otpadnu kratki kotni segmenti uz rub nacrta.
  - Dodaj opciju filtriranja pregustih paralelnih nizova (tipicno stubiste) preko praga gustoce/regije, te uklanjanja vrlo kratkih segmenata kotnih linija; dijagonalne "X" oznake vec izostaju iz ortogonalne detekcije.
  - Test: na sintetskoj slici sa "sumom" (gusti paralelni nizovi + kratke crtice) broj segmenata mjerljivo pada, a glavni zidovi ostaju.
  - _Zahtjevi: 3.2, 4.1_

- [ ] 8. Izvoz u DXF (`segments_to_dxf`)
  - Generiraj DXF preko `ezdxf`: sloj `VEKTOR_ZID`, svaki segment kao `LINE` entitet, primijeni `px_to_unit` skaliranje i obrat Y osi (piksel-koordinate imaju Y prema dolje).
  - Vrati `bytes`.
  - Unit test: DXF ucitaj natrag preko `ezdxf.recover`, provjeri N `LINE` entiteta na sloju `VEKTOR_ZID` i tocnost koordinata nakon skaliranja/obrata Y.
  - _Zahtjevi: 5.1, 5.2, 5.3, 5.4_

- [ ] 9. Orkestracija (`vectorize_floorplan`)
  - Spoji cijeli pipeline: `rasterize_input` -> `binarize` -> `denoise` -> `detect_line_segments` -> `merge_collinear` -> redukcija suma -> `segments_to_dxf`.
  - Vrati dict `{gray, binary, segments, dxf_bytes, overlay_png}`; `overlay_png` generiraj preko Pillow (segmenti iscrtani preko originalne slike).
  - Integracijski test na sintetskom PNG-u: provjeri prisutnost svih kljuceva i da `segments`/`dxf_bytes` nisu prazni.
  - _Zahtjevi: 3, 4, 5, 6.2_

- [ ] 10. Robusnost i rubni slucajevi
  - Neispravan ili prazan ulaz -> jasna poruka o gresci (bez rusenja).
  - 0 detektiranih segmenata -> prijedlog prilagodbe parametara (npr. snizi `min_len_px`/prag).
  - `try/except` oko rasterizacije i parsiranja; postuj DPI cap i limit dimenzija.
  - Testovi rubnih slucajeva: prazan bytes, neispravan format, potpuno bijela slika (0 segmenata), prevelik ulaz (DPI cap se aktivira).
  - _Zahtjevi: 7.1, 7.2, 7.3, 8.1, 8.2, 8.3_

- [ ] 11. Streamlit tab "Vektorizacija" u `streamlit_app.py`
  - Dodaj novi tab s uploaderom (PDF/PNG/JPG) i sidebar parametrima: `threshold`, `min_len_px`, `max_gap_px`, `dpi`.
  - Prikazi original i overlay rezultat rame uz rame; ponudi download DXF-a.
  - Omotaj skupu obradu u `@st.cache_data` radi performansi.
  - Import smoke test da se modul/tab ucitava bez pada.
  - _Zahtjevi: 1.4, 6.1, 6.2, 6.3, 6.4_

- [ ] 12. Checkpoint: puni test suite + deploy
  - Pokreni cijeli `pytest` (134 postojeca testa + novi `tests/test_raster_vectorize.py`) i osiguraj da je sve zeleno.
  - Commit i push na `main` (Streamlit Cloud auto-deploy).
  - _Zahtjevi: 1-8 (integracija)_
