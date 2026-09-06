# Requirements Document

## Introduction

Modul vektorizacije skeniranih tlocrta (`raster_vectorize.py` + Streamlit tab "Vektorizacija") trenutno od skeniranog PDF-a/slike detektira linije zidova i izvozi ih u DXF (sloj `VEKTOR_ZID`). Rezultat je gruba geometrija koju korisnik zatim dorađuje u CAD-u.

Ovaj dokument opisuje dodavanje **interaktivnog uređivanja unutar aplikacije**, kombinaciju dviju razina:

- **Podešavanje parametara uživo (razina 2):** korisnik mijenja parametre detekcije (prag/Otsu, minimalna duljina linije, spajanje praznina, uklanjanje šuma, DPI, spajanje osi zida) i odmah vidi ažurirani pregled s brojem linija, kako bi našao najbolje postavke prije izvoza.
- **Ručno čišćenje šuma (razina 1):** korisnik na interaktivnom prikazu odabere (lasso/box selekcijom) linije koje su očito šum (kotni lanci, stubište, namještaj) i obriše ih, tako da izostanu iz konačnog DXF-a. Uz to postoji poništavanje/reset koji vraća sve linije.

Cilj je da aplikacija pokrije "grubo do većinom čisto" — automatska detekcija plus brzo interaktivno čišćenje — a da fina, precizna dorada ostane u CAD-u. Aplikacija nije i ne postaje CAD editor.

## Glossary

- **Segment / linija:** ravna dužina detektirana iz slike, definirana dvjema točkama u pikselima.
- **Overlay pregled:** prikaz detektiranih linija preko (ili uz) originalne sive slike radi vizualne kontrole.
- **Lasso/box selekcija:** Plotly mehanizam odabira više točaka/linija povlačenjem okvira ili slobodne petlje.
- **Parametri detekcije:** prag binarizacije (ili Otsu), min. duljina linije, max praznina spajanja, iteracije uklanjanja šuma, DPI, spajanje osi zida.
- **`on_select`:** Streamlit svojstvo (`st.plotly_chart`) koje vraća korisnikov odabir na grafu.
- **Fallback:** rezervno ponašanje kad interaktivna selekcija nije dostupna u okruženju.

## Requirements

### Zahtjev 1 - Interaktivni pregled detektiranih linija

**Korisnička priča:** Kao korisnik želim vidjeti detektirane linije na interaktivnom prikazu preko originalne slike, kako bih mogao pregledati i odabrati pojedine linije.

#### Kriteriji prihvaćanja

1. KADA je vektorizacija uspješna i ima barem jednu liniju, SUSTAV SVAKAKO prikazuje detektirane linije kao Plotly graf preko ili uz originalnu sivu sliku.
2. KADA se prikazuju linije, SUSTAV SVAKAKO prikazuje ih tako da su pojedinačno odabirljive (lasso/box selekcija).
3. KADA vektorizacija ne pronađe nijednu liniju, SUSTAV SVAKAKO prikazuje jasnu poruku umjesto praznog grafa.

### Zahtjev 2 - Podešavanje parametara uživo

**Korisnička priča:** Kao korisnik želim mijenjati parametre detekcije i odmah vidjeti rezultat, kako bih pronašao postavke koje daju najčišći tlocrt.

#### Kriteriji prihvaćanja

1. KADA korisnik promijeni bilo koji parametar detekcije, SUSTAV SVAKAKO ponovno izračunava i ažurira pregled.
2. KADA se pregled ažurira, SUSTAV SVAKAKO prikazuje trenutni broj detektiranih linija.
3. AKO su parametri nepromijenjeni između osvježavanja, ONDA SUSTAV SVAKAKO koristi predmemoriju (cache) da izbjegne nepotrebno ponovno računanje.

### Zahtjev 3 - Odabir i brisanje linija (ručno čišćenje)

**Korisnička priča:** Kao korisnik želim odabrati linije koje su očito šum i obrisati ih, kako bih dobio čišći tlocrt prije izvoza.

#### Kriteriji prihvaćanja

1. KADA korisnik lasso/box selekcijom odabere jednu ili više linija i potvrdi brisanje, SUSTAV SVAKAKO uklanja odabrane linije iz aktivnog skupa i ažurira pregled.
2. KADA su linije obrisane, SUSTAV SVAKAKO prikazuje koliko je linija preostalo.
3. AKO korisnik ne odabere nijednu liniju pa zatraži brisanje, ONDA SUSTAV SVAKAKO ne mijenja skup i o tome obavještava korisnika.

### Zahtjev 4 - Poništavanje i reset

**Korisnička priča:** Kao korisnik želim moći vratiti obrisane linije, kako bih ispravio pogrešno brisanje.

#### Kriteriji prihvaćanja

1. KADA korisnik zatraži reset, SUSTAV SVAKAKO vraća sve linije iz zadnje vektorizacije (poništava sva ručna brisanja).
2. KADA korisnik promijeni parametre detekcije, SUSTAV SVAKAKO ponovno gradi skup linija (ručna brisanja prethodnog skupa se poništavaju jer je skup nov).

### Zahtjev 5 - Izvoz DXF-a odražava ručne izmjene

**Korisnička priča:** Kao korisnik želim da preuzeti DXF sadrži samo linije koje su ostale nakon čišćenja, kako bih u CAD-u nastavio s čistim skupom.

#### Kriteriji prihvaćanja

1. KADA korisnik preuzme DXF, SUSTAV SVAKAKO uključuje samo trenutno aktivne (nepobrisane) linije na sloju `VEKTOR_ZID`.
2. KADA su sve linije obrisane, SUSTAV SVAKAKO svejedno proizvodi valjan (prazan) DXF bez rušenja.

### Zahtjev 6 - Robusnost i fallback

**Korisnička priča:** Kao korisnik želim da tab radi i kad interaktivni odabir nije dostupan, kako bih barem mogao podešavati parametre i izvesti DXF.

#### Kriteriji prihvaćanja

1. AKO interaktivna selekcija (`on_select`) nije podržana u okruženju, ONDA SUSTAV SVAKAKO i dalje omogućuje podešavanje parametara i izvoz DXF-a, uz jasnu poruku da ručno brisanje nije dostupno.
2. KADA obrada ili prikaz ne uspije, SUSTAV SVAKAKO zadržava aplikaciju u upotrebljivom stanju (bez neuhvaćene greške).

### Zahtjev 7 - Performanse

**Korisnička priča:** Kao korisnik želim da pregled i osvježavanje rade dovoljno brzo, kako bih interaktivno radio bez dugih zastoja.

#### Kriteriji prihvaćanja

1. KADA korisnik podešava parametre ili briše linije, SUSTAV SVAKAKO ažurira pregled u razumnom vremenu za tipičan tlocrt.
2. KADA se skup linija prikazuje, SUSTAV SVAKAKO radi unutar ograničenja Streamlit Cloud okruženja (1 GB RAM) bez teških dodatnih biblioteka.

## Ne-ciljevi (izvan opsega)

- Aplikacija NIJE puni CAD editor: bez snappinga, preciznog unosa koordinata, slojeva, mjerenja i naprednog crtanja.
- NE podržava crtanje novih linija od nule niti precizno pomicanje pojedinih točaka (samo brisanje postojećih detektiranih linija).
- NE mijenja činjenicu da je finalna, precizna dorada tlocrta u CAD-u.
- NE uvodi teške biblioteke ni OpenCV.
- NE dodaje semantiku (razlikovanje zid/kota/tekst) — brisanje je ručna prosudba korisnika.

## Tehnička ograničenja

- Streamlit 1.50 (`st.plotly_chart(on_select=...)`) i Plotly 7; bez dodatnih komponenti za crtanje.
- Ciljna platforma je Streamlit Cloud (moguće druge verzije i Python 3.14) — potreban graceful fallback ako `on_select` nije dostupan.
- Ograničenje 1 GB RAM; bez OpenCV i teških zavisnosti.
- Sve izmjene koda rade se preko `execute_bash` Python skripti (nema alata za izravno uređivanje); hrvatski tekst u UTF-8.
- Aktivni skup linija i ručna brisanja čuvaju se u `st.session_state` da prežive Streamlit rerun.
