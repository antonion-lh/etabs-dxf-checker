# Requirements Document

## Introduction

Ovaj dokument opisuje NOVI modul unutar ETABS Model Checkera koji od SKENIRANOG (raster) tlocrta priprema POLUAUTOMATSKI vektorski tlocrt. Modul iz slike ili PDF-a izvlači geometriju linija (kandidate za zidove) i izvozi ih u DXF datoteku koja se zatim učitava u postojeći DXF tok usporedbe (phase2_dxf). Svrha modula je oživjeti stare skenirane nacrte kako bi postali iskoristivi u vektorskom toku provjere modela.

Ovo je izričito PRVI korak i ASISTENT, a ne zamjena za ručni rad. Rezultat vektorizacije OBAVEZNO traži ručnu korekciju u CAD alatu prije daljnje upotrebe. Modul ne razlikuje semantiku (ne zna što je zid, kota, tekst ili namještaj), ne zatvara prostorije i ne radi nikakvu 3D rekonstrukciju. Cilj je smanjiti količinu ručnog precrtavanja, a ne postići savršenu automatsku vektorizaciju.

Realno očekivanje: na čistim, kontrastnim skenovima modul da dobru osnovu linija; na lošim, šumnim ili blijedim skenovima rezultat je slabiji i zahtijeva više ručne korekcije. Modul namjerno ne koristi OCR ni strojno učenje u ovom koraku te se oslanja isključivo na klasičnu obradu slike.

## Glossary

- **Rasterizacija**: pretvaranje PDF stranice u sliku (piksele).
- **Binarizacija**: pretvaranje slike u crno-bijelu prema pragu.
- **Morfologija**: operacije čišćenja šuma (scipy.ndimage) — erozija/dilatacija.
- **Hough-style detekcija**: pronalazak ravnih linija iz binarne slike bez OpenCV-a.
- **Kolinearni segmenti**: segmenti na približno istom pravcu koji se mogu spojiti.
- **DXF sloj (layer)**: imenovani sloj u DXF datoteci na koji se smještaju vektorizirane linije.
- **Deskew**: ispravljanje nagiba skeniranog nacrta.

## Requirements

### Zahtjev 1 - Učitavanje ulaza

**Korisnička priča:** Kao korisnik želim učitati skenirani tlocrt kao PDF ili sliku kako bih ga pripremio za vektorizaciju.

#### Kriteriji prihvaćanja

1. KADA korisnik učita PDF datoteku SUSTAV SVAKAKO rasterizira odabranu stranicu koristeći PyMuPDF (fitz).
2. KADA korisnik učita sliku u formatu JPG, JPEG ili PNG SUSTAV SVAKAKO učitava sliku koristeći Pillow.
3. AKO učitani PDF ima više stranica ONDA SUSTAV SVAKAKO omogućuje korisniku odabir stranice za obradu.
4. AKO je učitana datoteka neispravnog ili nepodržanog formata ONDA SUSTAV SVAKAKO prikazuje jasnu poruku i ne nastavlja obradu.

### Zahtjev 2 - Pretprocesiranje slike

**Korisnička priča:** Kao korisnik želim pretprocesirati sliku kako bih dobio čistu binarnu podlogu pogodnu za detekciju linija.

#### Kriteriji prihvaćanja

1. KADA je slika učitana SUSTAV SVAKAKO pretvara sliku u grayscale i primjenjuje binarizaciju s podesivim pragom.
2. KADA korisnik promijeni prag binarizacije SUSTAV SVAKAKO ponovno izračunava binarnu sliku prema novom pragu.
3. KADA je binarizacija gotova SUSTAV SVAKAKO primjenjuje čišćenje šuma morfološkim operacijama preko scipy.ndimage.
4. AKO je deskew (ispravljanje nagiba) jednostavno izvediv ONDA SUSTAV SVAKAKO opcijski ispravlja nagib slike prije detekcije.

### Zahtjev 3 - Detekcija linijskih segmenata

**Korisnička priča:** Kao korisnik želim da sustav detektira ravne linijske segmente kako bih dobio kandidate za zidove.

#### Kriteriji prihvaćanja

1. KADA je binarna slika spremna SUSTAV SVAKAKO detektira linijske segmente Hough-style pristupom implementiranim preko numpy i scipy, bez OpenCV.
2. KADA korisnik postavi minimalnu duljinu linije SUSTAV SVAKAKO odbacuje segmente kraće od zadane minimalne duljine.
3. AKO detekcija ne pronađe niti jedan segment ONDA SUSTAV SVAKAKO to jasno prijavljuje korisniku.

### Zahtjev 4 - Spajanje segmenata u linije

**Korisnička priča:** Kao korisnik želim da se kratki i isprekidani segmenti spoje u dulje linije kako bih dobio čitljivije kandidate za zidove.

#### Kriteriji prihvaćanja

1. KADA postoje detektirani segmenti SUSTAV SVAKAKO spaja kolinearne i prostorno bliske segmente u dulje linije.
2. KADA korisnik postavi najveći razmak za spajanje SUSTAV SVAKAKO spaja samo segmente unutar tog razmaka.
3. AKO su dva segmenta približno kolinearna i unutar dozvoljenog razmaka ONDA SUSTAV SVAKAKO ih spaja u jednu liniju.

### Zahtjev 5 - Izvoz u DXF

**Korisnička priča:** Kao korisnik želim izvesti vektorizirane linije u DXF kako bih ih učitao u postojeći DXF tok usporedbe.

#### Kriteriji prihvaćanja

1. KADA korisnik zatraži izvoz SUSTAV SVAKAKO zapisuje linije u DXF datoteku koristeći ezdxf.
2. KADA se DXF generira SUSTAV SVAKAKO smješta vektorizirane linije na zaseban sloj.
3. KADA je DXF spreman SUSTAV SVAKAKO omogućuje korisniku preuzimanje .dxf datoteke.
4. AKO se DXF učitava u postojeći phase2_dxf parser ONDA SUSTAV SVAKAKO proizvodi entitete tipa LINE ili LWPOLYLINE koje taj parser podržava.

### Zahtjev 6 - Korisničko sučelje

**Korisnička priča:** Kao korisnik želim jednostavno sučelje s pregledom i parametrima kako bih interaktivno podešavao rezultat.

#### Kriteriji prihvaćanja

1. KADA korisnik otvori modul SUSTAV SVAKAKO prikazuje novi tab ili pod-tab unutar aplikacije.
2. KADA je slika obrađena SUSTAV SVAKAKO prikazuje original uz vektorizirani overlay.
3. KADA korisnik mijenja parametre (prag binarizacije, minimalna duljina linije, najveći razmak za spajanje) SUSTAV SVAKAKO ažurira prikaz rezultata.
4. KADA je rezultat spreman SUSTAV SVAKAKO prikazuje gumb za preuzimanje DXF datoteke.

### Zahtjev 7 - Robusnost

**Korisnička priča:** Kao korisnik želim da se modul ne ruši na lošem ulazu kako bih dobio jasnu povratnu informaciju umjesto pogreške.

#### Kriteriji prihvaćanja

1. AKO je ulaz prazan, oštećen ili neispravan ONDA SUSTAV SVAKAKO prikazuje jasnu poruku i ne prekida se s neuhvaćenom greškom.
2. AKO detekcija linija vrati nula rezultata ONDA SUSTAV SVAKAKO jasno navodi da linije nisu pronađene i predlaže podešavanje parametara.
3. KADA obrada ne uspije SUSTAV SVAKAKO zadržava aplikaciju u upotrebljivom stanju.

### Zahtjev 8 - Performanse i ograničenja

**Korisnička priča:** Kao korisnik želim da modul radi unutar ograničenih resursa kako bih ga mogao koristiti na Streamlit Cloudu.

#### Kriteriji prihvaćanja

1. KADA modul radi na Streamlit Cloudu SUSTAV SVAKAKO ostaje unutar ograničenja od 1 GB RAM-a.
2. KADA se PDF rasterizira SUSTAV SVAKAKO ograničava rezoluciju (DPI cap) kako bi se izbjeglo prekoračenje memorije (OOM).
3. KADA korisnik obrađuje jednu stranicu SUSTAV SVAKAKO završava obradu u razumnom vremenu.

## Ne-ciljevi (izvan opsega MVP-a)

- Modul NE razlikuje semantiku: ne razlikuje zid, kotu, tekst niti namještaj.
- Modul NE zatvara prostorije niti gradi topologiju prostora.
- Modul NE prepoznaje vrata ni prozore.
- Modul NE radi 3D rekonstrukciju.
- Modul NE jamči točnost rezultata bez ručne korekcije.
- Modul NE koristi OCR ni strojno učenje (ML) u ovom koraku.
- Modul NE dodaje OpenCV kao ovisnost.

## Tehnička ograničenja

- Dostupne biblioteke: numpy, scipy (ponajprije scipy.ndimage), Pillow, PyMuPDF (fitz), ezdxf i svglib.
- OpenCV NIJE dostupan i NE dodaje se u projekt.
- Radno okruženje je Streamlit Cloud s ograničenjem od 1 GB RAM-a.
- Sve izmjene koda u projektu izvode se preko execute_bash Python skripti; nema alata za izravno uređivanje datoteka.
- Hrvatski znakovi zapisuju se kao UTF-8 (po potrebi \uXXXX escape u izvornom kodu).
- Ne koristi se heredoc pri zapisivanju datoteka.
- Izlazni DXF mora biti kompatibilan s postojećim phase2_dxf parserom (entiteti LINE / LWPOLYLINE).

