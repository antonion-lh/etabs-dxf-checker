# Requirements Document

## Introduction

Ovaj dokument definira zahtjeve za prvi dio Faze B — **geometrijsku rekonstrukciju numeričkog
modela zgrade iz vektorskog DXF nacrta**. Cilj je iz DXF-a (slojevi, entiteti, geometrija)
prepoznati konstruktivne elemente (stupove, grede, zidove, ploče), rekonstruirati raster osi i
etaže te sastaviti strukturirani model spreman za daljnju obradu (materijali, opterećenja,
provjere — kasniji dijelovi Faze B).

Modul se oslanja na postojeći `phase2_dxf.py` (detekcija slojeva, rekonstrukcija rastera,
kotni tekstovi, zatvoreni poligoni, klasifikacija po geometriji) i na bazu znanja u
`.kiro/steering/` (poglavlje 1 — pravila rekonstrukcije, tablice slojeva, geometrijske
heuristike, pragovi). Razvija se i testira na dva primjera u `sample_dxf/`: stvarnom
arhitektonskom nacrtu (`jscad_floorplan.dxf`) i sintetskom višeetažnom AB nacrtu
(`ab_zgrada.dxf`).

Izlaz je strukturirani model istog oblika kakav proizvodi `phase1_e2k.py` (rječnik s
DataFrame-ovima elemenata po tipu + etaže), tako da ga postojeći moduli (validacija, audit,
izvještaj) mogu koristiti. Ovaj dio pokriva isključivo **geometriju i klasifikaciju**;
materijali, opterećenja, rubni uvjeti i provjere prema normi su izvan opsega ovog dokumenta
(dolaze u kasnijim dijelovima Faze B).

## Glossary

- **Konstruktivni element:** stup, greda, zid ili ploča prepoznat iz DXF-a.
- **Sloj (layer):** imenovani DXF sloj; primarni signal za klasifikaciju tipa elementa.
- **Mapiranje slojeva:** konfigurabilna tablica koja naziv sloja pridružuje tipu elementa.
- **Geometrijska heuristika:** pravilo prepoznavanja tipa iz oblika/dimenzija (kad sloj ne pomaže).
- **Raster (grid):** mreža osi (npr. A–F × 1–5) rekonstruirana iz linija osi.
- **Etaža:** skup elemenata na jednoj koti Z; rekonstruira se iz slojeva/tlocrta ili unosa.
- **Razina pouzdanosti:** oznaka (visoka/srednja/niska) koliko je klasifikacija sigurna.
- **Strukturirani model:** izlazni rječnik s elementima po tipu + etaže, oblika kao `phase1_e2k`.

## Requirements

### Zahtjev 1 - Učitavanje i priprema DXF-a

**Korisnička priča:** Kao korisnik želim učitati DXF nacrt i da ga sustav pouzdano otvori i
pripremi, kako bih mogao pokrenuti rekonstrukciju modela.

#### Kriteriji prihvaćanja

1. KADA korisnik učita valjani DXF SUSTAV SVAKAKO otvara datoteku (uz oporavak/recover za blago
   oštećene datoteke) i čita jedinice (INSUNITS) te ih normalizira u interne (m / mm).
2. AKO DXF nije čitljiv ili je prazan ONDA SUSTAV SVAKAKO vraća jasnu poruku i ne ruši se.
3. KADA su jedinice DXF-a nepoznate ONDA SUSTAV SVAKAKO koristi zadanu jedinicu uz jasnu napomenu.

### Zahtjev 2 - Klasifikacija elemenata po slojevima

**Korisnička priča:** Kao korisnik želim da sustav prepozna tip elementa iz naziva sloja, kako
bih dobio točnu klasifikaciju kad je nacrt uredno organiziran.

#### Kriteriji prihvaćanja

1. KADA naziv sloja jednoznačno odgovara tipu (stup/greda/zid/ploča) prema konfigurabilnoj
   tablici SUSTAV SVAKAKO dodjeljuje taj tip s visokom pouzdanošću.
2. SUSTAV SVAKAKO podržava hrvatske i engleske nazive slojeva te varijante (npr. STUP/COL/COLUMN).
3. KADA je mapiranje slojeva konfigurabilno SUSTAV SVAKAKO omogućuje dodavanje/izmjenu naziva
   bez izmjene koda.

### Zahtjev 3 - Klasifikacija geometrijskom heuristikom

**Korisnička priča:** Kao korisnik želim da sustav prepozna elemente i kad slojevi nisu jasni,
kako bih dobio koristan rezultat i na neurednim nacrtima.

#### Kriteriji prihvaćanja

1. KADA sloj ne određuje tip SUSTAV SVAKAKO primjenjuje geometrijske heuristike prema pragovima
   iz baze znanja (stup = mala kompaktna kontura/kružnica; zid = par bliskih paralelnih linija;
   greda = linija između stupova; ploča = velika zatvorena kontura).
2. KADA element klasificira heuristikom SUSTAV SVAKAKO mu dodjeljuje razinu pouzdanosti
   (visoka/srednja/niska).
3. KADA je pouzdanost niska SUSTAV SVAKAKO označava element za korisničku potvrdu.

### Zahtjev 4 - Rekonstrukcija rastera osi

**Korisnička priča:** Kao korisnik želim da sustav rekonstruira raster osi, kako bih mogao
lokalizirati elemente i provjeriti poravnanje.

#### Kriteriji prihvaćanja

1. KADA postoje linije osi (sloj osi/grid) SUSTAV SVAKAKO rekonstruira raster i, ako su prisutne,
   pridružuje oznake osi (A, B, C… / 1, 2, 3…).
2. KADA raster postoji SUSTAV SVAKAKO svakom elementu pridružuje najbližu referencu osi.

### Zahtjev 5 - Rekonstrukcija etaža i 3D (2D → 3D)

**Korisnička priča:** Kao korisnik želim da sustav složi etaže u 3D model, kako bih dobio
cjelovitu zgradu, a ne samo jedan tlocrt.

#### Kriteriji prihvaćanja

1. KADA DXF sadrži više tlocrta (odvojenih slojevima, blokovima ili prostorno) SUSTAV SVAKAKO
   pridružuje svaki tlocrt etaži i dodjeljuje kote Z.
2. AKO podaci o etažama/visinama nedostaju ONDA SUSTAV SVAKAKO traži unos (broj etaža, visina
   kata, pravila ponavljanja) i jasno označava te vrijednosti kao pretpostavke.
3. KADA je zadano ponavljanje tipske etaže SUSTAV SVAKAKO replicira elemente po etažama uz
   pripadne kote Z.
4. KADA nema podataka ni unosa za 3D ONDA SUSTAV SVAKAKO gradi 2D model (jedna ravnina) uz
   jasnu napomenu.

### Zahtjev 6 - Izlazni strukturirani model

**Korisnička priča:** Kao korisnik želim da rezultat bude u obliku koji postojeći moduli
razumiju, kako bih ga mogao dalje validirati i prikazati.

#### Kriteriji prihvaćanja

1. KADA je rekonstrukcija gotova SUSTAV SVAKAKO vraća strukturirani model (rječnik s
   DataFrame-ovima po tipu elementa + popis etaža) kompatibilan s oblikom koji daje `phase1_e2k`.
2. SUSTAV SVAKAKO uz svaki element bilježi: tip, geometriju (koordinate/centroid), etažu,
   pripadni presjek ako je očitan, izvor klasifikacije (sloj/heuristika) i razinu pouzdanosti.
3. KADA je presjek očitan iz kotne oznake (npr. "40/40") SUSTAV SVAKAKO ga pridružuje elementu.

### Zahtjev 7 - Kontrola cjelovitosti geometrije

**Korisnička priča:** Kao korisnik želim da me sustav upozori na geometrijske probleme, kako
bih znao je li rekonstrukcija pouzdana prije daljnje obrade.

#### Kriteriji prihvaćanja

1. KADA su krajevi elemenata razmaknuti unutar tolerancije SUSTAV SVAKAKO ih tretira kao spojene;
   izvan tolerancije SVAKAKO prijavljuje potencijalni prekid.
2. KADA postoje viseći (nepovezani) elementi ili duplikati SUSTAV SVAKAKO ih prijavljuje.
3. KADA su dimenzije izvan fizički razumnih granica (iz baze znanja) SUSTAV SVAKAKO prijavljuje
   upozorenje.

### Zahtjev 8 - Robusnost i integracija

**Korisnička priča:** Kao korisnik želim da modul radi pouzdano i da se uklapa u postojeću
aplikaciju, kako bih ga mogao koristiti bez rušenja i bez regresije.

#### Kriteriji prihvaćanja

1. KADA obrada bilo kojeg koraka ne uspije SUSTAV SVAKAKO hvata grešku i vraća jasan status bez
   rušenja aplikacije.
2. KADA se modul testira na `jscad_floorplan.dxf` i `ab_zgrada.dxf` SUSTAV SVAKAKO uspješno
   rekonstruira model bez neuhvaćene greške.
3. KADA se pokrene postojeći skup testova SVAKAKO nastavljaju prolaziti (bez regresije).

## Ne-ciljevi (izvan opsega ovog dijela)

- NE dodjeljuje materijale, opterećenja, kombinacije ni rubne uvjete (kasniji dio Faze B).
- NE provodi normativne provjere modela (pravilnost, drift, masa — kasniji dio).
- NE izvozi u ETABS `.e2k` niti se spaja izravno na ETABS (moguć budući korak).
- NE prepoznaje semantiku iznad geometrije (pier/spandrel, tip dijafragme — inženjerske odluke).
- NE radi vektorizaciju rastera (skenirani nacrti su zaseban, već postojeći modul).

## Tehnička ograničenja

- Python; oslonac na `ezdxf` (već korišten), `pandas`, `numpy`; bez teških novih zavisnosti.
- Oslonac na postojeći `phase2_dxf.py` i bazu znanja u `.kiro/steering/`.
- Izlazni oblik kompatibilan s `phase1_e2k.py` (isti ključevi/kolone gdje je moguće).
- Mapiranje slojeva i pragovi heuristika drže se u `config.py` (konfigurabilno).
- Sve poruke i dokumentacija na hrvatskom; postojećih testova mora ostati zeleno.
