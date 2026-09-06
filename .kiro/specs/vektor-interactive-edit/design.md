# Design Document

## Overview

Ovaj dizajn opisuje interaktivno uređivanje vektoriziranog tlocrta unutar Streamlit taba "Vektorizacija", bez uvođenja novih teških biblioteka. Radi se o dvije povezane mogućnosti: (1) podešavanje parametara detekcije uz pregled uživo i (2) ručno brisanje odabranih linija prije izvoza DXF-a. Osnovna vektorizacija (`raster_vectorize.vectorize_floorplan`) ostaje nepromijenjena; dodaje se sloj interakcije u UI-ju plus mala pomoćna funkcija za izvoz proizvoljnog podskupa linija u DXF.

Ključni tehnički element je prikaz linija kao Plotly graf s omogućenim odabirom (`st.plotly_chart(on_select="rerun")`) i mapiranje korisnikova odabira natrag na indekse linija. Aktivni skup linija i ručno obrisani indeksi čuvaju se u `st.session_state` da prežive Streamlit rerun. Predviđen je graceful fallback: ako okruženje ne podržava `on_select`, tab i dalje nudi parametre i izvoz, samo bez ručnog brisanja.

## Glossary

- **Aktivni skup:** lista trenutno prikazanih/izvezivih linija (nakon ručnih brisanja).
- **Set-potpis (signature):** hash ulaza + parametara koji identificira konkretan rezultat vektorizacije; kad se promijeni, aktivni skup se gradi iznova.
- **Točka-linija mapiranje:** svaka linija se u Plotly grafu crta kao zasebni trag s dvije točke; `curveNumber` iz odabira daje indeks linije.
- **`on_select="rerun"`:** Plotly odabir okida Streamlit rerun i vraća odabrane točke.

## Architecture

Tok podataka i interakcije u tabu "Vektorizacija":

    Upload (PDF/slika) + parametri (sliders/checkbox)
        |
        v
    _cached_vectorize(bytes, filename, params..., page, merge_axes)  ->  rezultat (segments, gray, ...)
        |
        v
    Izracun set-potpisa (sig) iz (ime datoteke + svi parametri + page)
        |
        v
    st.session_state:
        - "vektor_sig"           : zadnji set-potpis
        - "vektor_deleted"       : set indeksa rucno obrisanih linija
      Ako se sig promijenio -> resetiraj "vektor_deleted" = set()   (novi skup linija)
        |
        v
    Aktivni segmenti = [s for i,s in enumerate(segments) if i not in deleted]
        |
        v
    Plotly figura:
        - pozadina: originalna siva slika (go.Image ili layout.images)
        - svaka aktivna linija = zaseban Scatter trag (2 tocke), mode="lines"
        - y os obrnuta (autorange="reversed") da odgovara rasterskoj slici
        st.plotly_chart(fig, on_select="rerun", selection_mode=("box","lasso"))
        |
        v
    on_select rezultat -> skup odabranih curveNumber -> indeksi linija
        |
        v
    Gumbi: "Obrisi odabrane" (dodaj u deleted), "Ponisti sve (reset)" (deleted=set())
        |
        v
    Izvoz: segments_to_dxf(aktivni_segmenti, ...) -> download_button

Fallback grana: ako `st.plotly_chart` u okruzenju ne podrzava `on_select` (stariji Streamlit),
uhvati TypeError/izuzetak i prikazi staticni overlay (postojeci `overlay_png`) + poruku da rucno
brisanje nije dostupno; parametri i izvoz svih linija i dalje rade.

## Components and Interfaces

### raster_vectorize.py (mala dopuna)

Postojeci `segments_to_dxf(segments, px_to_unit, layer, img_height_px)` vec prima proizvoljnu
listu segmenata, pa se izvoz podskupa radi bez izmjene modula. Nije nuzna nova funkcija u modulu.
Opcionalno se moze dodati helper za figuru, ali se drzi u UI sloju (streamlit_app.py) da modul
ostane bez ovisnosti o Plotly/Streamlit.

### streamlit_app.py

- `_cached_vectorize(...)` — nepromijenjen (vec vraca segments + gray + dxf metapodatke).
- Novi helper (u streamlit_app.py, ne u modulu):
  - `_vektor_build_figure(gray, segments) -> plotly.graph_objects.Figure`
    Gradi figuru: pozadinska slika + po jedan Scatter trag za svaku liniju; osi skalirane na
    dimenzije slike, y obrnut. Vraca figuru spremnu za `st.plotly_chart`.
  - `_vektor_selected_indices(selection) -> set[int]`
    Iz `on_select` rezultata izvlaci skup `curveNumber` vrijednosti (indeksi linija). Robusno na
    razlicite oblike (dict/objekt), vraca prazan set ako nema odabira.
- Session state kljucevi: `vektor_sig`, `vektor_deleted` (set indeksa).
- Tab logika: izracun sig; reset deleted na promjenu sig; izgradnja aktivnih segmenata; prikaz
  figure s on_select; gumbi Obrisi/Reset; izvoz DXF-a iz aktivnih segmenata; fallback grana.

## Data Models

- **Segment:** `((x0, y0), (x1, y1))` u pikselima (kao u modulu).
- **st.session_state["vektor_deleted"]:** `set[int]` — indeksi linija u izvornom `segments` skupu koji su ruceno obrisani.
- **st.session_state["vektor_sig"]:** `str` — potpis (npr. hash) trenutnih ulaza+parametara; promjena okida reset brisanja.
- **selection (on_select):** Streamlit vraca strukturu s `selection.points`; svaka tocka nosi `curve_number` (indeks traga = indeks linije).

## Error Handling

- **on_select nepodrzan / izuzetak pri interaktivnom grafu:** uhvatiti (try/except), postaviti zastavicu `interactive=False`, prikazati staticni `overlay_png` + `st.info` da rucno brisanje nije dostupno u ovom okruzenju. Parametri i izvoz rade dalje.
- **Prazan odabir pri "Obrisi odabrane":** ne mijenjati skup, `st.warning` da nista nije odabrano.
- **Sve linije obrisane:** izvoz svejedno daje valjan (prazan) DXF; pregled prikazuje poruku da nema aktivnih linija.
- **Velik broj linija (npr. > ~1500 tragova):** radi performansi ograniciti interaktivni prikaz (npr. upozorenje i/ili crtanje kao manji broj tragova); tipican tlocrt (~100-300 linija) je bez problema.
- **Neuspjeh vektorizacije (ok=False):** postojeca logika (warning/stop) ostaje.

## Testing Strategy

Interaktivni dio (Plotly odabir, Streamlit rerun) tesko je testirati u pytestu bez pokrenute
Streamlit runtime, pa se testovi fokusiraju na CISTU logiku izdvojenu iz UI-ja:

### Unit testovi (tests/)

- `_vektor_selected_indices`: za razne oblike selection strukture (dict s points koji imaju curve_number; prazno; None) vraca ispravan set indeksa.
- Filtriranje aktivnih segmenata: za dani segments + deleted set, aktivni skup je tocno komplement (redoslijed ocuvan).
- Izvoz podskupa: `segments_to_dxf(active_segments, ...)` -> ucita se natrag preko ezdxf i ima tocno len(active) LINE entiteta (koristi postojece _read_dxf_bytes helpere).
- Reset semantika: promjena set-potpisa ponistava deleted (testira se cista funkcija koja racuna novi state, ne Streamlit).

### Smoke / integracija

- streamlit_app importa se bez pada i izlaze nove helpere (`_vektor_build_figure`, `_vektor_selected_indices`).
- `_vektor_build_figure(gray, segments)` vraca Plotly Figure s brojem tragova = broj linija (+1 za pozadinsku sliku ako se koristi trag), bez pokrenute runtime.

### Regresija

- Postojeci pytest paket (182 testa) mora ostati zelen; novi testovi u tests/test_vektor_edit.py.
