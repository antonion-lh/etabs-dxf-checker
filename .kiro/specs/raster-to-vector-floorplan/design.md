# Design Document

## Overview

Ovaj modul (radni naziv: Vektorizacija tlocrta) omogucuje pretvaranje rasterskog arhitektonskog tlocrta (skenirani PDF ili slika) u editabilan vektorski DXF s linijama zidova. Pipeline u jednoj recenici: ulazni PDF/slika se rasterizira, pretvara u sivu skalu, binarizira, morfoloski cisti, iz binarne slike se detektiraju ravni segmenti (linije), kolinearni segmenti se spajaju te izvoze kao LINE entiteti u DXF spremni za preuzimanje.

Kljucno je da je ovo ASISTENT za crtanje, a NE potpuno automatska rekonstrukcija modela. Alat ubrzava prvi korak (dobivanje geometrije iz slike), a korisnik u CAD-u dovrsava i zatvara poligone. Rezultat MVP-a je VALJAN, editabilan DXF s linijama zidova na zasebnom sloju, a ne gotov, klasificiran ETABS-usporediv model.

Vazna posljedica za integraciju (posteno navedeno): postojeci parser phase2_dxf.py klasificira elemente iskljucivo iz ZATVORENIH poligona (collect_closed_polylines), kota-tekstova i grid linija. Nas vektorizator proizvodi OTVORENE linije (LINE entiteti). Zbog toga se DXF izvezen iz ovog modula NECE automatski klasificirati u ETABS-usporedive elemente u prvom koraku. Puna auto-integracija u phase2 tok (automatsko zatvaranje poligona, prepoznavanje zidova/ploca) je BUDUCI korak, ne dio MVP-a.

## Glossary

- Rasterizacija: pretvaranje PDF stranice ili vektorskog sadrzaja u mrezu piksela (bitmap).
- Grayscale (siva skala): slika s jednim kanalom intenziteta (0-255), bez boje.
- Binarizacija: pretvaranje sive slike u dvije vrijednosti (crno/bijelo, tj. bool) prema pragu.
- Otsu prag: automatski izracunat prag koji maksimizira razdvojenost dviju klasa piksela (pozadina/crtez).
- Morfologija (opening/closing): operacije nad binarnom slikom koje uklanjaju sum (opening) ili popunjavaju male rupe i spajaju prekide (closing).
- Segment: ravna duzina definirana s dvije tocke u pikselima, ((x0,y0),(x1,y1)).
- Kolinearno spajanje: povezivanje vise segmenata koji leze na priblizno istom pravcu i blizu su jedan drugome, u jedan duzi segment.
- LINE entitet: osnovni ravni entitet u DXF-u definiran pocetnom i zavrsnom tockom.
- px_to_unit: faktor skaliranja iz piksela u stvarne CAD jedinice (npr. mm ili m).
- DPI cap: gornja granica rezolucije rasterizacije radi zastite memorije.

## Architecture

Modul se dodaje kao nova datoteka raster_vectorize.py i novi tab u streamlit_app.py (npr. "Vektorizacija"), pored postojecih tabova ["Model","Revizija","Elementi","Izvjestaj"]. Ne dira postojeci phase2_dxf tok; radi kao zaseban, samostalan ulaz.

Tekstualni dijagram toka podataka:

    Ulaz (PDF ili slika: PNG/JPG, raw bytes)
        |
        v
    Rasterizacija
        - PDF: PyMuPDF (fitz) render stranice u pixmap uz DPI cap (npr. 150)
        - slika: Pillow ucitavanje
        - zastita: ogranicenje maksimalnih dimenzija (npr. max stranica px)
        |
        v
    Grayscale (Pillow convert("L") ili numpy luminance)
        |
        v
    Binarizacija (podesiv prag)
        - threshold=None -> automatski Otsu (numpy histogram implementacija)
        - inace fiksni prag (0-255)
        - rezultat: bool array (True = crtez/crno)
        |
        v
    Morfolosko ciscenje (scipy.ndimage)
        - binary_opening (uklanja sitni sum)
        - binary_closing (spaja male prekide u linijama)
        - broj iteracija podesiv
        |
        v
    Detekcija ravnih segmenata (bez OpenCV)
        - pragmatican pristup za pretezno ortogonalne zidove:
          projekcijski/run-length pristup po recima i stupcima nalazi
          horizontalne i vertikalne nizove True piksela duljine >= min_len_px
        - opcionalno: numpy Hough-style akumulator (kut, razmak) preko
          rubnih piksela za kose linije; MVP prioritizira ortogonalno
        |
        v
    Spajanje kolinearnih segmenata
        - segmenti na istom pravcu (unutar angle_tol) i unutar max_gap_px
          se spajaju u jedan duzi segment
        |
        v
    Pretvorba u LINE entitete + skaliranje px_to_unit
        |
        v
    ezdxf DXF (modelspace, sloj VEKTOR_ZID) -> bytes (BytesIO/temp)
        |
        v
    Download (Streamlit download_button) + Overlay prikaz
        - overlay: originalna slika + detektirane linije (Pillow crtanje
          ili plotly Scatter preko slike) radi vizualne kontrole

Orkestracija cijelog toka je funkcija vectorize_floorplan(...), koja vraca dict sa svim medurezultatima za prikaz i cache (@st.cache_data na razini Streamlit poziva).

## Components and Interfaces

Sve nove funkcije zive u novoj datoteci raster_vectorize.py. Segment je definiran kao par tocaka u pikselima: Segment = ((x0, y0), (x1, y1)), koordinate su int ili float u pikselima.

### rasterize_input(raw_bytes, filename, page=0, dpi_cap=150) -> np.ndarray

- Parametri: raw_bytes (bytes) sadrzaj datoteke; filename (str) za detekciju tipa po ekstenziji; page (int) indeks PDF stranice; dpi_cap (int) gornja granica DPI-a.
- Ponasanje: ako je PDF -> fitz.open(stream=raw_bytes, filetype="pdf"), render stranice u pixmap uz ograniceni DPI; ako je slika -> Pillow Image.open(BytesIO(raw_bytes)). Pretvara u grayscale.
- Povrat: np.ndarray dtype uint8, oblik (H, W), vrijednosti 0-255.
- Zastita: ako bi dimenzije premasile max (npr. 6000 px po strani), smanjuje DPI/skalira.

### binarize(gray, threshold=None) -> np.ndarray

- Parametri: gray (np.ndarray uint8); threshold (int|None). Ako je None -> Otsu prag racunat iz numpy histograma.
- Povrat: np.ndarray dtype bool, oblik (H, W), True znaci tamni piksel (crtez).

### denoise(binary, iters=1) -> np.ndarray

- Parametri: binary (bool ndarray); iters (int) broj iteracija.
- Ponasanje: scipy.ndimage.binary_opening zatim binary_closing (structure 3x3), iters puta.
- Povrat: ocisceni bool ndarray istog oblika.

### detect_line_segments(binary, min_len_px, angle_tol_deg) -> list[Segment]

- Parametri: binary (bool ndarray); min_len_px (int) najmanja duljina linije; angle_tol_deg (float) tolerancija kuta oko 0/90 stupnjeva za ortogonalnu klasifikaciju.
- Ponasanje: run-length skeniranje redaka (horizontalne linije) i stupaca (vertikalne linije) nalazi neprekinute nizove True duljine >= min_len_px. Opcionalno numpy Hough akumulator za kose segmente.
- Povrat: list[Segment] u pikselima.

### merge_collinear(segments, max_gap_px, angle_tol_deg) -> list[Segment]

- Parametri: segments (list[Segment]); max_gap_px (int) najveci dopusteni razmak za spajanje; angle_tol_deg (float) tolerancija kolinearnosti.
- Ponasanje: grupira segmente po pravcu (kut + okomiti odmak) i spaja one koji su unutar max_gap_px u jedan duzi segment.
- Povrat: list[Segment] (reducirani skup).

### segments_to_dxf(segments, px_to_unit, layer="VEKTOR_ZID") -> bytes

- Parametri: segments (list[Segment]); px_to_unit (float) faktor px u CAD jedinice; layer (str) ime sloja.
- Ponasanje: ezdxf.new(), dodaje sloj VEKTOR_ZID, za svaki segment msp.add_line skalirano s px_to_unit (uz obrtanje Y osi jer slika ima ishodiste gore-lijevo). Zapisuje u BytesIO/privremeni file.
- Povrat: bytes valjanog DXF-a.

### vectorize_floorplan(raw_bytes, filename, params) -> dict

- Parametri: raw_bytes (bytes); filename (str); params (Params ili dict) svi parametri pipelinea.
- Ponasanje: orkestrira rasterize_input -> binarize -> denoise -> detect_line_segments -> merge_collinear -> segments_to_dxf, gradi overlay PNG. Namijenjeno da bude omotano @st.cache_data u Streamlit sloju.
- Povrat: dict {"gray": np.ndarray, "binary": np.ndarray, "segments": list[Segment], "dxf_bytes": bytes, "overlay_png": bytes}.

### Streamlit integracija

- Novi tab "Vektorizacija" u streamlit_app.main() poziva vectorize_floorplan, prikazuje gray/binary/overlay preko st.image ili plotly, nudi st.download_button za dxf_bytes te sidebar kontrole za sve parametre.

## Data Models

### Segment

Ravna duzina u pikselima:

    Segment = ((x0, y0), (x1, y1))

- x0, y0, x1, y1: koordinate u pikselima (int ili float), ishodiste gore-lijevo (rasterska konvencija).

### Params

Skup parametara pipelinea (dataclass ili dict):

- threshold: int | None  (prag binarizacije; None -> Otsu)
- min_len_px: int         (najmanja duljina detektirane linije)
- max_gap_px: int         (najveci razmak za spajanje kolinearnih)
- angle_tol_deg: float    (tolerancija kuta za klasifikaciju/spajanje)
- dpi: int                (DPI rasterizacije, ogranicen dpi_cap)
- px_to_unit: float       (faktor px -> CAD jedinice)

### Rezultat (dict)

- gray: np.ndarray uint8 (H, W)
- binary: np.ndarray bool (H, W)
- segments: list[Segment]
- dxf_bytes: bytes
- overlay_png: bytes

### DXF model

- Sloj: VEKTOR_ZID (svi elementi na zasebnom, jasno imenovanom sloju).
- Entiteti: LINE (otvorene linije, ne zatvoreni poligoni).
- Jedinice: definirane px_to_unit; preporuka postaviti $INSUNITS/header prema dogovorenoj jedinici (npr. mm). Y os se obrce da odgovara CAD orijentaciji.

## Error Handling

- Neispravan ili prazan ulaz: ako raw_bytes prazan, nepodrzana ekstenzija ili fitz/Pillow ne moze otvoriti sadrzaj -> uhvatiti iznimku i vratiti jasnu korisnicku poruku (npr. "Datoteka nije valjan PDF ili slika."). Ne rusi aplikaciju.
- Nula detektiranih segmenata: ako detect_line_segments/merge_collinear vrate prazno -> prikazati poruku i prijedlog parametara (smanjiti min_len_px, promijeniti threshold, povecati broj iteracija denoise ili DPI).
- Zastita memorije (OOM): dpi_cap i ogranicenje maksimalnih dimenzija slike; ako ulaz premasuje granice, automatski smanjiti rezoluciju i obavijestiti korisnika.
- Robusnost UI-a: cijeli vectorize_floorplan poziv u Streamlit sloju omotan try/except tako da aplikacija ostane aktivna i prikaze gresku umjesto pada.
- ezdxf greske: ako zapisivanje DXF-a padne -> fallback (npr. jednostavniji zapis / poruka korisniku) i uredno vracanje greske umjesto iznimke koja rusi tok.

## Testing Strategy

Testovi koriste SINTETSKU sliku generiranu numpyjem (npr. bijela pozadina 255, na nju nacrtane crne linije poznatih koordinata i duljina), cime su ocekivani rezultati unaprijed poznati i deterministicki.

### Unit testovi (tests/test_raster_vectorize.py)

- binarize: na sintetskoj slici s poznatim brojem crnih piksela, rezultat bool array sadrzi ocekivan broj True vrijednosti; Otsu grana ispravno razdvaja pozadinu i crtez.
- detect_line_segments: na slici s poznatim linijama (npr. jedna horizontalna i jedna vertikalna zadanih duljina), funkcija nalazi te linije s ispravnom orijentacijom i duljinom >= min_len_px.
- merge_collinear: dva kolinearna segmenta razdvojena malim razmakom (< max_gap_px) spajaju se u jedan; segmenti izvan tolerancije se ne spajaju.
- segments_to_dxf: proizvedeni DXF se ucita natrag preko ezdxf.recover i sadrzi tocno N LINE entiteta na sloju VEKTOR_ZID; koordinate odgovaraju ulazu skaliranom s px_to_unit.

### Integracijski test

- vectorize_floorplan na sintetskom PNG-u (spremljenom u bytes): vraca dict s ne-praznim gray, binary, segments, dxf_bytes i overlay_png; broj segmenata odgovara ocekivanju; dxf_bytes se moze ucitati natrag preko ezdxf.

### Regresija

- Postojeci pytest paket (trenutno 134 testa) mora ostati zelen; novi tests/test_raster_vectorize.py dodaje se bez lomljenja postojecih testova. Test suite se pokrece kroz postojeci pytest.ini.
