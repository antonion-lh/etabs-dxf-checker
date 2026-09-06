# Implementation Plan

> Napomena o ograničenjima alata: sve izmjene u projektu `etabs_dxf_checker` rade se ISKLJUČIVO preko `execute_bash` + Python skripti (nema `fs_write`/`str_replace`/`edit`), UTF-8, bez heredoc-a. Testovi u `tests/test_vektor_edit.py`. Ciljna platforma Streamlit Cloud (Python 3.14, moguće druge verzije) — potreban graceful fallback za `on_select`.

- [ ] 1. Čista logika odabira i aktivnog skupa (bez Streamlita) + testovi
  - [ ] 1.1 Dodaj u streamlit_app.py pomoćnu funkciju `_vektor_selected_indices(selection) -> set` koja iz Plotly `on_select` strukture (dict/objekt s `points`, svaka točka ima `curve_number`) izvlači skup indeksa linija; robusna na None/prazno/različite oblike.
  - [ ] 1.2 Dodaj `_vektor_active_segments(segments, deleted) -> list` koja vraća linije čiji indeks nije u `deleted` (redoslijed očuvan).
  - [ ] 1.3 Testovi u tests/test_vektor_edit.py: `_vektor_selected_indices` (dict s points, prazno, None), `_vektor_active_segments` (komplement, prazan deleted, svi obrisani). _Zahtjevi: 3.1, 4.1_

- [ ] 2. Izgradnja Plotly figure iz linija + testovi
  - [ ] 2.1 Dodaj `_vektor_build_figure(gray, segments)` koja gradi go.Figure: pozadinska slika (go.Image ili layout image), svaka linija zaseban Scatter trag (2 točke, mode="lines"), y-os obrnuta, osi skalirane na dimenzije slike; vraća figuru.
  - [ ] 2.2 Test: `_vektor_build_figure` vraća Figure s brojem Scatter tragova == broj linija (pozadinu prebroji zasebno); ne zahtijeva Streamlit runtime. _Zahtjevi: 1.1, 1.2_

- [ ] 3. Integracija u tab "Vektorizacija" (session state, odabir, brisanje, reset)
  - [ ] 3.1 Uvedi set-potpis (sig) iz (ime datoteke + svi parametri + page + merge_axes); spremi u st.session_state["vektor_sig"]; na promjenu sig resetiraj st.session_state["vektor_deleted"]=set().
  - [ ] 3.2 Izračunaj aktivne segmente (`_vektor_active_segments`); prikaži `st.plotly_chart(fig, on_select="rerun", selection_mode=("box","lasso"), key=...)`; iz rezultata `_vektor_selected_indices`.
  - [ ] 3.3 Gumbi: "Obriši odabrane" (dodaj odabrane indekse u deleted; ako prazno -> st.warning), "Poništi sve (reset)" (deleted=set()). Prikaži broj aktivnih/obrisanih linija.
  - [ ] 3.4 Fallback: cijeli interaktivni blok u try/except; ako `on_select` nije podržan (TypeError) ili padne, prikaži postojeći statični `overlay_png` + st.info da ručno brisanje nije dostupno; parametri i izvoz i dalje rade. _Zahtjevi: 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 6.1, 6.2_

- [ ] 4. Izvoz DXF-a iz aktivnog skupa + test
  - [ ] 4.1 Download DXF gradi se iz aktivnih segmenata: `segments_to_dxf(active, px_to_unit, layer, img_height_px=H)`. Ako je aktivni skup prazan, i dalje valjan (prazan) DXF.
  - [ ] 4.2 Test: za segments + deleted skup, DXF iz aktivnih učita se natrag preko ezdxf i ima točno len(active) LINE entiteta (koristi postojeće _read_dxf_bytes/_lines helpere iz test_raster_vectorize ili replicira). _Zahtjevi: 5.1, 5.2_

- [ ] 5. Smoke i regresija
  - [ ] 5.1 Smoke: import streamlit_app bez pada; izloženi `_vektor_build_figure`, `_vektor_selected_indices`, `_vektor_active_segments`.
  - [ ] 5.2 Pokreni puni pytest (182 postojeća + novi) — sve zeleno. _Zahtjevi: 7.1, 7.2_

- [ ] 6. Checkpoint: commit/push na main (Streamlit Cloud auto-deploy)
  - Stageaj relevantne datoteke po imenu; commit s jasnom porukom; push na main.
