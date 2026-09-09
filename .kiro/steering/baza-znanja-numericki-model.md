---
inclusion: manual
---
# Baza znanja za izradu i provjeru numeričkog modela zgrade iz DXF nacrta
## Stručna podloga aplikacije

**Verzija:** 2.0 (proširena) · **Jezik:** hrvatski · **Kontekst:** aplikacija automatski
rekonstruira numerički model zgrade iz vektorskog DXF nacrta prema normama i provodi
inženjersku provjeru; u edukacijskom okruženju nastavnik provjerava studentski model.

**Referentne norme:** EN 1990:2002 (osnove projektiranja), EN 1991 (djelovanja),
EN 1992-1-1:2004 (betonske konstrukcije), EN 1993-1-1:2005 (čelične konstrukcije),
EN 1997-1 (geotehnika), EN 1998-1:2004 (potresno projektiranje), sve s pripadnim hrvatskim
nacionalnim dodacima (HRN EN … /NA).

**Struktura razlikovanja tvrdnji:** (1) **normativni zahtjevi** — izravno iz Eurokoda, s
navedenim člankom; (2) **inženjerske smjernice / dobra praksa** — iz priručnika i literature;
(3) **heuristike alata** — pravila prepoznavanja i pretpostavke koje alat koristi i koje uvijek
treba potvrditi. Sve pretpostavke koje alat sam usvoji jasno se označavaju kao takve.

**Granice i odgovornost:** Aplikacija rekonstruira model i provodi kvantitativne provjere prema
normi. Ovlašteni inženjer / nastavnik potvrđuje nalaze i preuzima stručnu odgovornost.
Automatski generiran model je pomoć pri izradi i reviziji, a ne ovjeren proračunski model za
izvedbu. Sve brojčane granice, faktori i vrijednosti provjeriti u važećoj verziji norme i
mjerodavnom nacionalnom dodatku; u tijeku je i druga generacija Eurokodova.

---

## Sadržaj i tijek izrade modela

Baza znanja slijedi logičan tijek kojim aplikacija gradi model iz DXF-a:

1. **Ulazni podaci i geometrijska rekonstrukcija iz DXF-a** — kako se iz slojeva, entiteta i
   geometrije prepoznaju konstruktivni elementi, osi i etaže; kontrola cjelovitosti.
2. **Materijali i presjeci** — klase betona/čelika/armature s vrijednostima i formulama,
   geometrijske karakteristike presjeka, modifikatori krutosti.
3. **Idealizacija konstruktivnih elemenata** — štapni i plošni elementi, kruti krajevi,
   oslobođenja, mreženje, pier/spandrel, dijafragme.
4. **Djelovanja (opterećenja) i kombinacije** — vrste i vrijednosti opterećenja, ψ faktori,
   ULS/SLS/seizmičke kombinacije, masa za seizmiku.
5. **Seizmička analiza i pravilnost** — spektar, faktor ponašanja q, modalni zahtjevi,
   kriteriji pravilnosti u tlocrtu i po visini, meki kat, torzija, granice pomaka, P-Δ.
6. **Rubni uvjeti, temelji i kontrola/verifikacija modela** — oslonci, temelji, sustavna
   kontrola valjanosti, tipične greške, kriteriji prihvatljivosti rezultata.

Svako poglavlje završava popisom korištenih izvora. Poglavlja 1–3 pokrivaju izgradnju modela;
poglavlja 4–5 opterećenja i seizmiku; poglavlje 6 verifikaciju i prihvaćanje.

---

# Poglavlje 1 — Ulazni podaci i geometrijska rekonstrukcija iz DXF-a

> Cilj poglavlja: definirati kako aplikacija iz vektorskog nacrta (DXF) rekonstruira
> geometriju konstrukcije kao temelj numeričkog modela. Pravila su operativna (s pragovima
> i redoslijedom odlučivanja) da budu strojno primjenjiva i provjerljiva.

## 1.1 Pretpostavke o ulazu
- Ulaz je **vektorski DXF** (ne skenirani raster). Sadrži prave entitete i slojeve.
- Jedinice DXF-a moraju biti poznate (mm, cm ili m); ako nisu deklarirane u zaglavlju
  ($INSUNITS), traži se unos. Interna referentna jedinica modela: **duljine u metrima,
  dimenzije presjeka u milimetrima.**
- Ishodište i orijentacija: koordinatni sustav DXF-a preslikava se u globalni X-Y-Z modela;
  Z je vertikala (visina), dodjeljuje se po etažama (poglavlje 1.6).

## 1.2 Slojevi (layers) — primarni izvor klasifikacije
Nazivi slojeva su najpouzdaniji signal tipa elementa. Aplikacija koristi konfigurabilnu
tablicu ključnih riječi (velika/mala slova se zanemaruju, podržani hrvatski i engleski nazivi):

| Tip elementa | Ključne riječi u nazivu sloja |
|---|---|
| Stup (column) | STUP, STUPOVI, COL, COLUMN, S_ |
| Greda (beam) | GREDA, GREDE, BEAM, B_, NADVOJ |
| Zid (wall) | ZID, ZIDOVI, WALL, W_, SW (shear wall) |
| Ploča (slab) | PLOCA, PLOČA, SLAB, FLOOR, DECK |
| Temelj (foundation) | TEMELJ, FOUND, FOOTING, PILE |
| Osi/raster (grid) | OSI, GRID, AXIS, RASTER |
| Kote (dimensions) | KOTA, KOTE, DIM, DIMENSION |
| Tekst/oznake | TEKST, TEXT, OZNAKA, LABEL |

Pravilo: ako naziv sloja jednoznačno pripada jednom tipu → dodijeli taj tip s **visokom
pouzdanošću**. Nejasan/neprepoznat sloj → prelazi se na geometrijsku heuristiku (1.4).

## 1.3 Entiteti DXF-a i njihovo značenje
| Entitet | Tipično značenje |
|---|---|
| LINE, LWPOLYLINE (otvorena) | osi, rubovi zidova, osi greda |
| LWPOLYLINE / POLYLINE (zatvorena) | obris stupa, zida, ploče, otvora |
| CIRCLE | kružni stup ili provrt |
| ARC | zaobljeni rub, luk |
| INSERT (blok) | tipski element (stup, temelj, oznaka) — tip po imenu bloka |
| TEXT, MTEXT | oznake presjeka ("40/40", "C30/37"), nazivi |
| DIMENSION | kotne linije (dimenzije) |
| HATCH | ispuna presjeka/zida (pomaže identifikaciji punog presjeka) |

## 1.4 Geometrijske heuristike (kad slojevi nisu dovoljni)
Primjenjuju se redom, s pragovima (svi pragovi konfigurabilni):
1. **Stup** — zatvorena kontura male površine i približno kompaktnog oblika:
   - površina ≤ ~0,50 m² i omjer stranica (aspect) ≤ ~3:1 → kandidat za stup;
   - CIRCLE malog polumjera (≤ ~0,40 m) → kružni stup.
2. **Zid** — par bliskih paralelnih linija (razmak = debljina zida, tipično 0,10–0,40 m)
   koje se protežu znatno dulje od debljine; spajaju se u os zida (centerline).
3. **Greda** — linija/os koja povezuje dva stupa/čvora, duljine reda raspona (2–12 m),
   izvan obrisa ploče ili duž ruba.
4. **Ploča** — velika zatvorena kontura koja omeđuje etažu; otvori = manje zatvorene konture
   unutar nje (stubišta, okna).
Rezultat svake heuristike nosi **razinu pouzdanosti** (visoka/srednja/niska) koja se prenosi
u model i izvještaj (korisnik potvrđuje niske).

## 1.5 Osi i raster (grid)
- Prepoznaju se linije na sloju osi/grid; sjecišta definiraju čvorne točke rastera.
- Oznake osi (A, B, C… / 1, 2, 3…) čitaju se iz pripadnog teksta uz krajeve linija.
- Raster služi za: (a) imenovanje/lokalizaciju elemenata, (b) provjeru poravnanja stupova
  po vertikali (kontinuitet, 1.6), (c) kontrolu pravilnosti tlocrta.

## 1.6 Rekonstrukcija 3D (etaže i visine)
- **Jedan tlocrt = jedna etaža** u ravnini Z = const.
- Ako DXF sadrži više tlocrta (odvojeni po slojevima, blokovima ili prostorno razmaknuti),
  svaki se pridružuje etaži; redoslijed i kote Z rekonstruiraju se iz naziva ("PRIZEMLJE",
  "KAT 1"…) ili iz zadanog broja etaža i visina.
- **Ulazna kontrola kad podaci nedostaju** (obavezno prije 3D modela): broj etaža, visina
  kata (jednolika ili po etaži), pravila ponavljanja (tipski kat). Bez toga model ostaje 2D
  uz jasnu napomenu.
- **Vertikalni kontinuitet:** stup/zid iste tlocrtne pozicije kroz više etaža spaja se u
  kontinuirani vertikalni element; prekid se označava (moguć meki kat ili transfer element,
  poglavlje 5).

## 1.7 Kontrola cjelovitosti geometrije (prije analize)
Provjere koje se rade odmah po rekonstrukciji (dealbreakeri se moraju riješiti):
- **Poklapanje čvorova:** krajevi elemenata koji se trebaju spojiti razmaknuti su ≤ tolerancija
  (npr. 1–5 mm u mjerilu modela) → inače spoji ili prijavi.
- **Nepovezani (viseći) elementi:** element bez ijednog spoja → upozorenje/greška.
- **Preklapanja i duplikati:** dvostruke linije na istom mjestu → sažmi.
- **Zatvorenost kontura** ploča/zidova koje bi trebale biti zatvorene.
- **Realnost dimenzija:** dimenzije presjeka i rasponi unutar fizički razumnih granica
  (npr. stup 20–120 cm, debljina zida 10–40 cm, raspon 2–12 m) — izvan toga upozorenje.

## 1.8 Što se NE može pouzdano izvući iz same geometrije
(→ ulazna kontrola ili buduće čitanje iz ETABS-a): materijali i klase, opterećenja i
kombinacije, rubni uvjeti/oslonci, tip dijafragme, oznake pier/spandrel, momentna oslobođenja.
Ove stavke se u modelu jasno označavaju kao **pretpostavljene/zadane**, ne kao pročitane.

---
### Izvori (poglavlje 1)
- ezdxf dokumentacija (DXF entiteti LINE/LWPOLYLINE/CIRCLE/INSERT/TEXT/HATCH/DIMENSION).
- CAD konvencije imenovanja slojeva (AIA/ISO 13567 kao orijentacija).
- Inženjerska praksa prepoznavanja elemenata iz tlocrta (par paralelnih linija = zid i sl.).
- Postojeći tok aplikacije: detekcija slojeva etaža, rekonstrukcija rastera, izvlačenje
  kotnih tekstova, prikupljanje zatvorenih poligona, klasifikacija po geometriji.

---

# Poglavlje 2 — Materijali i presjeci

> Cilj: definirati materijalna svojstva i geometrijske karakteristike presjeka koje model
> mora imati, s vrijednostima prema EN 1992-1-1 (beton, armatura) i EN 1993-1-1 (čelik).
> Sve vrijednosti provjeriti u važećoj verziji norme i nacionalnom dodatku.

## 2.1 Beton — klase i svojstva (EN 1992-1-1, Tablica 3.1)
Oznaka klase C fck/fck,cube (npr. C30/37): fck = karakteristična tlačna čvrstoća valjka [MPa],
fck,cube = kocke. Ključne projektne vrijednosti:

| Klasa | fck [MPa] | fcm = fck+8 [MPa] | fctm [MPa] | Ecm [GPa] |
|---|---|---|---|---|
| C20/25 | 20 | 28 | 2,2 | 30 |
| C25/30 | 25 | 33 | 2,6 | 31 |
| C30/37 | 30 | 38 | 2,9 | 33 |
| C35/45 | 35 | 43 | 3,2 | 34 |
| C40/50 | 40 | 48 | 3,5 | 35 |
| C45/55 | 45 | 53 | 3,8 | 36 |
| C50/60 | 50 | 58 | 4,1 | 37 |

Formule (EN 1992-1-1, čl. 3.1):
- Srednja tlačna: fcm = fck + 8 MPa.
- Srednja vlačna: fctm = 0,30·fck^(2/3) za ≤ C50/60.
- Sekantni modul elastičnosti: **Ecm = 22·(fcm/10)^0,3 [GPa]** (fcm u MPa).
- Projektna tlačna: fcd = αcc·fck/γc; uobičajeno αcc = 0,85–1,0 (nac. dodatak), γc = 1,5.
- Poissonov koeficijent ν = 0,2 (neraspucali beton) / 0 (raspucali); ρ ≈ 2500 kg/m³ (AB).

## 2.2 Armatura (EN 1992-1-1, čl. 3.2)
- Razred B500 (najčešće B500B): fyk = 500 MPa; Es = 200 GPa; γs = 1,15; fyd = fyk/γs ≈ 435 MPa.
- Duktilnost: razredi A, B, C prema εuk i ft/fyk.

## 2.3 Konstrukcijski čelik (EN 1993-1-1, čl. 3.2)
| Razred | fy [MPa] (t ≤ 40 mm) | fu [MPa] |
|---|---|---|
| S235 | 235 | 360 |
| S275 | 275 | 430 |
| S355 | 355 | 490 |
- E = 210 GPa; G = 81 GPa; ν = 0,3; ρ ≈ 7850 kg/m³; γM0 = 1,0.

## 2.4 Zidano (ako se pojavi u modelu, EN 1996)
- Karakteristična tlačna čvrstoća zida fk ovisi o bloku i mortu; modul E ≈ 1000·fk (orijentacijski).
- Zidane zgrade tretiraju se posebno (EN 1996 / EN 1998-1 pogl. 9); u modelu često plošni elementi.

## 2.5 Geometrijske karakteristike presjeka
Iz prepoznatih dimenzija (poglavlje 1) računaju se karakteristike koje idu u model:
- **Pravokutni (b×h):** A = b·h; Iy = b·h³/12; Iz = h·b³/12; torzijska konstanta J
  (za b×h aproksimacija po tablicama); posmične površine Avy, Avz.
- **Kružni (d):** A = πd²/4; I = πd⁴/64.
- **Čelični profili (IPE, HEA/B, RHS…):** iz kataloga (aplikacija već ima bazu EN profila).
- Presjek se u modelu zadaje s materijalom; nedostajuća dimenzija = greška (element bez presjeka).

## 2.6 Modifikatori krutosti (raspucala krutost) — za AB
EN 1998-1 (čl. 4.3.1(6)–(7)) dopušta 50% krutosti neraspucalih elemenata (savijanje i posmik)
za seizmičku analizu. Uobičajeni modifikatori (I_eff/I_gross), kao smjernica (potvrditi):

| Element | Modifikator momenta tromosti (I) |
|---|---|
| Grede (T ili pravokutne) | ~0,35 · I_gross |
| Stupovi | ~0,70 · I_gross |
| Zidovi (neraspucali/raspucali) | ~0,70 / ~0,50 · I_gross |
| Ploče (kao ravni element) | ~0,25 · I_gross |

Napomena: gornje vrijednosti (0,35/0,70…) uobičajene su iz ACI 318 / prakse i često se koriste
kao praktična razrada EN načela "50%"; točan izbor je inženjerska odluka i ovisi o razini
naprezanja. Za elastičnu (neseizmičku) analizu SLS koristi se bruto ili efektivna krutost prema
potrebi (npr. za progibe ploča uzeti u obzir raspucalost i puzanje).

## 2.7 Pravila za aplikaciju
- Ako materijal nije zadan u DXF-u/tekstu → ulazna kontrola (zadana klasa npr. C30/37, B500B),
  jasno označeno kao pretpostavka.
- Presjek se preuzima iz kotne oznake ("40/40" → 400×400 mm) ili iz geometrije obrisa;
  pouzdanost se bilježi.
- Svi elementi u finalnom modelu moraju imati: tip, presjek (dimenzije), materijal, i pripadne
  modifikatore krutosti ako je seizmička analiza tražena.

---
### Izvori (poglavlje 2)
- EN 1992-1-1:2004, Tablica 3.1 i čl. 3.1–3.2 (beton, armatura, Ecm = 22·(fcm/10)^0,3).
- EN 1993-1-1:2005, čl. 3.2 (konstrukcijski čelik S235/S275/S355, E = 210 GPa).
- EN 1996 (zidano, orijentacijski).
- EN 1998-1:2004, čl. 4.3.1 (raspucala krutost 50%).
- ACI 318 / inženjerska praksa (razrada modifikatora krutosti po tipu elementa — smjernica).
- eurocodeapplied.com (exposure klase, pokrovni sloj — EN 206/EN 1992 Tablica 4.1).

---

# Poglavlje 3 — Idealizacija konstruktivnih elemenata

> Cilj: pravila kako se prepoznati elementi (poglavlje 1) pretvaraju u elemente numeričkog
> modela (štapni/plošni), s konkretnim parametrima mreženja, krutih krajeva, oslobođenja,
> dijafragmi i oznaka za dimenzioniranje.

## 3.1 Štapni (frame) elementi: stupovi i grede
- Modeliraju se linijom kroz težište presjeka; lokalne osi orijentirati konzistentno
  (jaka os grede vodoravno, stup po visini).
- **Kruti krajevi (rigid end offsets):** duljina offseta = polovica dimenzije spojnog
  elementa u čvoru (npr. greda uz stup širine 0,50 m → offset ≈ 0,25 m). Rigid-zone factor
  (0–1): 0 = konzervativno (bez krute zone), 1 = potpuno kruto; preporuka za AB okvire
  koristiti umjeren faktor (npr. 0,5) ili prepustiti automatskom izračunu programa, uz
  svjesnost učinka na periode i pomake.
- **Momentna oslobođenja (releases):**
  - Kontinuirane AB grede/stupovi: bez oslobođenja (monolitni spoj).
  - Sekundarne grede zglobno oslonjene na glavne: oslobođenje momenta savijanja na krajevima
    (M3 = 0) po potrebi.
  - Rešetkasti/čelični elementi: prema stvarnom spoju (zglob vs. kruto).
  - Pogrešno oslobođenje je čest izvor nestabilnosti ili krive raspodjele momenata.
- **Podjela štapa (meshing frame):** stup/greda dijeli se u čvorovima gdje se spajaju drugi
  elementi; dodatna podjela za opterećenje/rezultate po duljini (npr. 4–8 segmenata po rasponu
  za glatku ovojnicu sila), ali ne pretjerivati.

## 3.2 Plošni (shell/area) elementi: zidovi i ploče
- **Shell vs. membrane:**
  - **Shell** (nosi savijanje + membransko): posmični zidovi, ploče koje nose savijanjem,
    temeljne ploče. Zadano za nosive plohe.
  - **Membrane** (samo u ravnini): kad ploča služi samo za raznos opterećenja i djeluje kao
    kruta dijafragma bez vlastite savojne nosivosti u modelu.
  - Orijentacijski: tanke ploče (h/L malen) mogu se modelirati kao ploče s savijanjem (thin
    shell, Kirchhoff); deblje (h/L > ~1/10) kao debele ploče (thick shell, Mindlin, uzima
    posmičnu deformaciju).
- **Veličina mreže (mesh):**
  - Cilj: element mreže dovoljno malen da uhvati gradijente naprezanja i da se čvorovi
    poklope s gredama/stupovima/rubovima otvora.
  - Praktična preporuka: veličina mreže reda **0,5–1,0 m** za zidove/ploče uobičajenih zgrada,
    ILI 8–12 elemenata po rasponu/visini etaže, što god daje finiju mrežu.
  - **Kompatibilnost:** mreža mora imati čvorove ondje gdje se spajaju grede i rubovi otvora
    (inače nema prijenosa sila). Auto-mesh mora poštovati rubove.
  - **Membranu NE meshirati** za prijenos gravitacijskog opterećenja na grede — mreženje
    membrane precjenjuje momente/sile u gredama.
- **Aspect ratio elemenata mreže:** težiti ≤ 4:1 (idealno ~1:1); jako izdužení elementi
  degradiraju rezultate.

## 3.3 Zidovi — pier i spandrel (za dimenzioniranje)
- **Pier** = vertikalni segment zida (stupac zida između otvora); nosi vertikalu i savijanje
  u ravnini. **Spandrel** = horizontalni segment (nadvoj/parapet iznad/ispod otvora).
- Bez oznaka pier/spandrel, program integrira naprezanja po plohi, ali NE daje rezultantne
  sile (M, V, N) po segmentu zida potrebne za dimenzioniranje armature. Stoga: svaki nosivi
  zid dobiva pier oznake po etaži; nadvoji/parapeti spandrel oznake.
- Kod zidova s otvorima: pier lijevo/desno od otvora + spandrel iznad = ispravna idealizacija
  okvirastog djelovanja zida.

## 3.4 Dijafragme (katne ploče kao horizontalni element)
- **Kruta dijafragma:** svi čvorovi etaže dijele istu krutu ravninu (2 translacije + rotacija).
  EN 1998-1 (čl. 4.3.1): pretpostavka prihvatljiva ako pomaci uz stvarnu podatljivost ploče
  nigdje ne prelaze za **> 10%** pomake uz krutu pretpostavku. Praktična ASCE/IBC smjernica
  (nije EN): fleksibilna ako raspon/dubina > 3.
- **Polukruta (semi-rigid):** ploča modelirana shell elementima s vlastitom krutošću — koristi
  se kod velikih otvora, izduženih tlocrta, uvučenih kutova, ili kad je kriterij 10% prekoračen.
- **Fleksibilna:** drveni stropovi, tanki metalni limovi — eksplicitno modelirati krutost.
- **Obavezno:** svakoj etaži dodijeliti dijafragmu; nedodijeljena dijafragma → etaže nepovezane,
  pogrešan put sila i torzija.
- Oprez kod nelinearne analize s vlaknastim (fiber) presjecima: kruti constraint mijenja odziv
  (pomak neutralne osi), pa se tada preferira polukruta/eksplicitna ploča.

## 3.5 Otvori (vrata, prozori, stubišta, okna)
- Otvori u zidovima/pločama modeliraju se izostavljanjem plohe (rupa u mreži) ili definiranjem
  otvora; utječu na krutost dijafragme i na pier/spandrel podjelu.
- Veliki otvori mogu diafragmu učiniti polukrutom (vidi 3.4) i uzrokovati tlocrtnu nepravilnost.

## 3.6 Pravila za aplikaciju (sažetak odluka)
1. Stup/greda → frame element, presjek+materijal, kruti krajevi (faktor konfigurabilan),
   oslobođenja prema pravilima 3.1.
2. Zid → shell (thin/thick po debljini), pier/spandrel oznake, mesh 0,5–1,0 m usklađen s
   gredama i otvorima.
3. Ploča → shell (nosiva) ili membrane (samo dijafragma) — izbor je pretpostavka koja se
   označava i može se korisniku ponuditi na potvrdu.
4. Svaka etaža → dijafragma; tip (rigid/semi/flex) prema kriteriju 10% i geometriji, uz
   zadani rigid za pravilne kompaktne ploče + upozorenje za nepravilne.

---
### Izvori (poglavlje 3)
- EN 1998-1:2004, čl. 4.3.1 (kruta dijafragma, kriterij 10%; raspucala krutost).
- CSI/ETABS dokumentacija i priručnici: rigid end offsets, mesh, membrane vs shell,
  pier/spandrel labeling, thin/thick shell (Kirchhoff/Mindlin).
- ASCE 7 / IBC (klasifikacija dijafragmi, praktični kriterij raspon/dubina > 3).
- Inženjerska praksa mreženja (aspect ratio ≤ 4:1, 8–12 elemenata po rasponu).
- OpenSees/UC Berkeley (utjecaj krutog constrainta na nelinearne fiber presjeke).

---

# Poglavlje 4 — Djelovanja (opterećenja) i kombinacije

> Cilj: definirati koja djelovanja model mora sadržavati, tipične vrijednosti (EN 1991) i
> pravila kombinacija (EN 1990) za granična stanja nosivosti (GSN/ULS), uporabljivosti
> (GSU/SLS) i seizmičku situaciju. Sve vrijednosti provjeriti u nacionalnom dodatku.

## 4.1 Vrste djelovanja (EN 1991)
- **Stalno (G):** vlastita težina konstrukcije (računa se iz geometrije + ρ, npr. AB 25 kN/m³)
  + stalni dodatni tereti (podovi, žbuka, pregrade, instalacije).
- **Promjenjivo — uporabno (Q):** korisno opterećenje etaža prema kategoriji uporabe (EN 1991-1-1).
- **Snijeg (S):** EN 1991-1-3, ovisi o zoni, nadmorskoj visini, obliku krova.
- **Vjetar (W):** EN 1991-1-4, ovisi o osnovnoj brzini vjetra, terenu, visini, obliku.
- **Potres (A_Ed):** EN 1998 (poglavlje 5 ove baze).

## 4.2 Tipične vrijednosti uporabnog opterećenja (EN 1991-1-1, Tablica 6.2 — orijentacijski)
| Kategorija | Namjena | qk [kN/m²] | Qk [kN] (koncentr.) |
|---|---|---|---|
| A | Stambeni prostori | 1,5–2,0 | 2,0 |
| B | Uredi | 2,0–3,0 | 2,0–4,5 |
| C (C1–C5) | Prostori okupljanja (škole, dvorane…) | 2,0–5,0(+) | 3,0–7,0 |
| D | Trgovine | 4,0–5,0 | 3,5–7,0 |
| — | Stepeništa, balkoni | prema kategoriji, često 2,5–4,0 | — |
Krov (kategorija H, neprohodni): tipično 0,4 kN/m². Točne vrijednosti iz nacionalnog dodatka.

## 4.3 Tipični dodatni stalni tereti (orijentacijski, za kontrolu realnosti)
- Podna obrada (estrih + obloga): 1,0–2,0 kN/m².
- Spušteni strop + instalacije: 0,3–0,8 kN/m².
- Pregradni zidovi (kao ekvivalentno površinsko): 0,8–1,2 kN/m² (lagane pregrade).
- Vlastita težina AB ploče d=20 cm: 0,20·25 = 5,0 kN/m².

## 4.4 Parcijalni faktori i kombinacijski koeficijenti (EN 1990)
**Parcijalni faktori (GSN, tipično):** γG = 1,35 (nepovoljno) / 1,0 (povoljno); γQ = 1,5
(nepovoljno) / 0 (povoljno).

**Kombinacijski koeficijenti ψ (EN 1990, Tablica A1.1 — orijentacijski):**
| Djelovanje | ψ0 | ψ1 | ψ2 |
|---|---|---|---|
| Uporabno kat. A, B (stan, ured) | 0,7 | 0,5 | 0,3 |
| Uporabno kat. C, D (okupljanje, trgovina) | 0,7 | 0,7 | 0,6 |
| Uporabno kat. E (skladišta) | 1,0 | 0,9 | 0,8 |
| Snijeg (H ≤ 1000 m n.m.) | 0,5 | 0,2 | 0 |
| Vjetar | 0,6 | 0,2 | 0 |

## 4.5 Kombinacije za granično stanje nosivosti (GSN/ULS)
Osnovna kombinacija (EN 1990, izraz 6.10):
- Σ γG,j·Gk,j + γQ,1·Qk,1 + Σ γQ,i·ψ0,i·Qk,i
- Primjer (jedno uporabno, bez vjetra): **1,35·G + 1,5·Q**.
- Primjer (uporabno vodeće + vjetar sporedni): 1,35·G + 1,5·Q + 1,5·0,6·W.
- Primjer (vjetar vodeći + uporabno sporedno): 1,35·G + 1,5·W + 1,5·ψ0,Q·Q.
(Alternativno izrazi 6.10a/6.10b gdje ih nacionalni dodatak propisuje.)

## 4.6 Kombinacije za uporabljivost (GSU/SLS)
- **Karakteristična:** Gk + Qk,1 + Σ ψ0,i·Qk,i (npr. za progibe, EN 1992 granica L/250).
- **Česta:** Gk + ψ1,1·Qk,1 + Σ ψ2,i·Qk,i.
- **Kvazi-stalna:** Gk + Σ ψ2,i·Qk,i (za dugotrajne učinke, puzanje, pukotine).

## 4.7 Seizmička kombinacija i masa (EN 1990 izraz 6.12 + EN 1998-1)
- **Kombinacija učinaka:** Σ Gk,j + A_Ed + Σ ψ2,i·Qk,i (potresna proračunska situacija).
- **Masa za seizmičku analizu:** Σ Gk,j + Σ ψ_E,i·Qk,i, gdje **ψ_E,i = φ·ψ2,i**
  (EN 1998-1 čl. 3.2.4). Faktor φ ovisi o kategoriji i o tome jesu li etaže neovisno
  zauzete (npr. φ = 0,5–1,0; za krov φ = 1,0).
- Model mora imati definiran izvor mase koji odgovara ovoj kombinaciji (ne samo vlastita težina
  ako je uporabno relevantno).

## 4.8 Pravila za aplikaciju
- Vlastita težina računa se automatski iz geometrije i gustoće materijala.
- Uporabno, snijeg, vjetar → ulazna kontrola (zadane vrijednosti po kategoriji uporabe koju
  odabere korisnik), jasno označeno kao pretpostavka.
- Aplikacija generira standardni skup kombinacija (ULS 6.10, SLS karakteristična/česta/kvazi-
  stalna, seizmička) i provjerava jesu li u modelu prisutne odgovarajuće kombinacije.
- Kontrola realnosti: ukupno stalno + uporabno po m² etaže unutar razumnih granica (npr.
  stambena ploča ~8–12 kN/m² ukupno kvazi-stalno); veliko odstupanje → upozorenje.

---
### Izvori (poglavlje 4)
- EN 1990:2002, Tablica A1.1 (ψ faktori), Tablica A1.2(B) (γ faktori), izrazi 6.10/6.10a/6.10b,
  6.12 (seizmička situacija).
- EN 1991-1-1 (vlastita težina i uporabna opterećenja, Tablica 6.2), EN 1991-1-3 (snijeg),
  EN 1991-1-4 (vjetar).
- EN 1998-1:2004, čl. 3.2.4 (masa za seizmiku, ψ_E = φ·ψ2).
- EN 1992-1-1 (granice progiba, npr. L/250).
Napomena: sve brojčane vrijednosti orijentacijske; mjerodavan je hrvatski nacionalni dodatak.

---

# Poglavlje 5 — Seizmička analiza i pravilnost konstrukcije (EN 1998-1)

> Cilj: pravila i kvantitativni kriteriji za seizmički dio modela — proračunski spektar,
> faktor ponašanja q, metoda analize, masa i modalni zahtjevi, ekscentricitet, kriteriji
> pravilnosti u tlocrtu i po visini, meki kat, torzija i granice pomaka. Vrijednosti ovise o
> nacionalnom dodatku (za HR: potresne karte, a_gR po lokaciji).

## 5.1 Seizmičko djelovanje i proračunski spektar
- Referentno ubrzanje tla a_gR (iz nacionalne karte, po lokaciji) × faktor važnosti γ_I
  (razredi važnosti I–IV; γ_I = 0,8 / 1,0 / 1,2 / 1,4).
- Tip tla A–E (i S1, S2) određuje parametre spektra (S, T_B, T_C, T_D).
- Za linearnu analizu koristi se **proračunski spektar Sd(T)** koji uključuje faktor
  ponašanja q (EN 1998-1, čl. 3.2.2.5).

## 5.2 Faktor ponašanja q (EN 1998-1, čl. 5.2.2.2 za beton)
q = q0 · kw, gdje je q0 osnovna vrijednost ovisna o tipu sustava i razredu duktilnosti:

| Sustav (beton) | DCM (srednja duktilnost) | DCH (visoka duktilnost) |
|---|---|---|
| Okvirni / mješoviti / spojeni zidovi | q0 ≈ 3,0·αu/α1 | q0 ≈ 4,5·αu/α1 |
| Nespojeni (samostalni) zidovi | q0 ≈ 3,0 | q0 ≈ 4,0·αu/α1 |
| Torzijski podatljiv sustav | 2,0 | 3,0 |
| Sustav obrnutog njihala | 1,5 | 2,0 |
- αu/α1 tipično 1,0–1,3 (ovisi o redundanciji); kw za zidne sustave < 1,0.
- **DCL (niska duktilnost):** q ≤ 1,5 (samo za nisku seizmičnost); dimenzioniranje po EN 1992.
- Za NEpravilne po visini: q se smanjuje (množi s 0,8).

## 5.3 Metoda analize (EN 1998-1, čl. 4.3.3)
- **Modalna analiza spektrom odziva** — referentna metoda, primjenjiva uvijek.
- **Metoda ekvivalentnih bočnih sila** — dopuštena samo ako je zgrada pravilna po visini i
  T1 ≤ min(4·T_C; 2,0 s) (dominira 1. ton).
- Kombiniranje modalnih odziva: SRSS ako su tonovi nezavisni; **CQC** ako su bliski
  (T_j/T_i > 0,9).

## 5.4 Masa i modalni zahtjevi (čl. 4.3.3.3.1)
- Masa iz kombinacije Σ Gk + Σ ψ_E·Qk (poglavlje 4.7).
- Broj tonova: (a) Σ efektivnih modalnih masa ≥ **90%** u svakom smjeru, ILI (b) svi tonovi s
  efektivnom masom > **5%**.
- **Slučajni ekscentricitet:** e_ai = ± 0,05·L_i (5% dimenzije etaže okomite na potres),
  primijeniti u oba smjera.

## 5.5 Kriteriji pravilnosti u tlocrtu (čl. 4.2.3.2) — kvantitativno
Zgrada je pravilna u tlocrtu ako su ispunjeni (orijentacijski) svi uvjeti:
1. Približno simetrična razdioba mase i krutosti oko dvije ortogonalne osi.
2. Kompaktan tlocrt; uvučeni/izbočeni dijelovi ne prelaze ~5% površine tlocrta.
3. Krutost katne ploče u ravnini dovoljna (dijafragma; vidi poglavlje 3.4).
4. Vitkost tlocrta λ = L_max/L_min ≤ 4.
5. Na svakoj etaži i za svaki smjer: **ekscentricitet e0 ≤ 0,30·r** i **radijus tromosti
   krutosti r ≥ radijus tromosti mase l_s**, gdje je e0 udaljenost centra krutosti od centra
   mase, r torzijski radijus, l_s polumjer inercije mase.

## 5.6 Kriteriji pravilnosti po visini (čl. 4.2.3.3)
1. Svi nosivi vertikalni sustavi (okviri, zidovi) kontinuirani od temelja do vrha.
2. Bočna krutost i masa etaža konstantne ili se postupno smanjuju prema vrhu (bez naglih skokova).
3. Kod okvira: omjer stvarne i proračunom tražene nosivosti etaže ne varira nesrazmjerno
   između susjednih etaža (izbjeći "meki/slabi kat").
4. Uvlačenja (setbacks) ograničena: pojedinačno ≤ 20% prethodne dimenzije (uz dodatne uvjete
   za simetrična/nesimetrična uvlačenja).

## 5.7 Meki kat i slab kat (soft/weak storey)
- **Meki kat:** bočna krutost etaže < ~70% krutosti etaže iznad, ILI < ~80% prosjeka tri etaže
  iznad (kriterij analogan ASCE 7; EN kroz pravilnost po visini). Tipično prizemlje s velikim
  otvorima / bez ispune.
- **Slab kat:** nosivost etaže osjetno manja od susjedne.
- Posljedica: koncentracija plastičnih deformacija, rizik od urušavanja — kritično upozorenje.

## 5.8 Ograničenje pomaka (EN 1998-1, čl. 4.4.3 — granično stanje ograničenja oštećenja)
Katni pomak (interstorey drift) dr, reduciran faktorom ν (ovisno o razredu važnosti), ograničava se:
- **dr·ν ≤ 0,005·h** — za nekonstrukcijske elemente od krhkih materijala vezane na konstrukciju;
- **dr·ν ≤ 0,0075·h** — za duktilne nekonstrukcijske elemente;
- **dr·ν ≤ 0,010·h** — za nekonstrukcijske elemente koji ne smetaju deformaciji ili ih nema;
gdje je h katna visina, ν ≈ 0,4–0,5 (ovisno o razredu važnosti).

## 5.9 Učinci drugog reda (P-Δ) (čl. 4.4.2.2)
- Koeficijent osjetljivosti θ = (P_tot·d_r)/(V_tot·h).
- θ ≤ 0,10 → P-Δ se može zanemariti;
- 0,10 < θ ≤ 0,20 → uzeti približno (faktor 1/(1−θ));
- 0,20 < θ ≤ 0,30 → eksplicitno; θ > 0,30 nije dopušteno.

## 5.10 Pravila za aplikaciju (provjere seizmičkog modela)
- Provjeri: definiran spektar/masa, dovoljan broj tonova (≥90%), primijenjen ekscentricitet ±5%,
  raspucala krutost (pogl. 2.6), dijafragme (pogl. 3.4).
- Izračunaj i prijavi: pravilnost u tlocrtu (e0/r, λ), pravilnost po visini (skok krutosti/mase),
  meki kat (<70%), katne pomake (drift vs. granice 0,5/0,75/1,0%), P-Δ (θ).
- Rezultat: status po svakom kriteriju (U redu / Upozorenje / Greška) uz brojčanu vrijednost i
  granicu, da profesor odmah vidi gdje i koliko model odstupa.

---
### Izvori (poglavlje 5)
- EN 1998-1:2004: čl. 3.2.2.5 (proračunski spektar), čl. 4.2.3.2–4.2.3.3 (pravilnost tlocrt/
  visina, e0 ≤ 0,30r, λ ≤ 4, uvlačenja), čl. 4.3.3 (metode analize, EBS uvjeti T1),
  čl. 4.3.3.3.1 (modalna masa 90%/5%, ekscentricitet 5%), čl. 4.4.2.2 (P-Δ, θ),
  čl. 4.4.3 (ograničenje pomaka 0,005/0,0075/0,010·h), čl. 5.2.2.2 (faktor q, DCM/DCH).
- IStructE — Manual/Examples for seismic design to Eurocode 8 (praktične vrijednosti q, DCM/DCH).
- ASCE 7 (analogni kriterij mekog kata < 70%/80%) — kao praktična smjernica, nije EN.
Napomena: brojčane granice i a_gR ovise o hrvatskom nacionalnom dodatku i potresnim kartama.

---

# Poglavlje 6 — Rubni uvjeti, temelji i kontrola/verifikacija modela

> Cilj: pravila za oslonce i temelje te sustavna kontrola valjanosti gotovog modela prije
> prihvaćanja rezultata. Ovo poglavlje objedinjuje provjere u operativnu listu koju aplikacija
> primjenjuje i po kojoj profesor ocjenjuje studentski model.

## 6.1 Rubni uvjeti (oslonci)
- Svaki vertikalni nosivi element (stup, zid) mora imati definiran put opterećenja do tla.
- Tipovi oslonaca:
  - **Uklještenje (fixed):** spriječene 3 translacije + 3 rotacije — tipično za temelje samce/
    trakaste kad se pretpostavlja krut spoj s temeljem.
  - **Zglob (pinned):** spriječene translacije, slobodne rotacije — rjeđe za AB, češće za čelik.
  - **Elastični oslonac (spring):** modul reakcije tla k_s [kN/m³] × utjecajna površina;
    koristi se za temeljne ploče na tlu (Winklerov model).
- **Pravilo aplikacije:** ako oslonci nisu u DXF-u (zaseban sloj/blok), ulazna kontrola —
  zadano uklještenje na koti temelja, jasno označeno kao pretpostavka.

## 6.2 Temelji (načelno)
- **Temelji samci / trakasti:** modeliraju se kao točkasti/linijski oslonci (uklještenje ili
  opruga); provjera nosivosti tla (σ ≤ σ_dop) i ekscentriciteta.
- **Temeljna ploča:** shell element na elastičnoj podlozi (opruge po čvorovima, k_s iz
  geotehnike); kontrola tlaka na tlo i mogućeg odizanja (uplift).
- **Piloti:** vertikalne opruge/oslonci s krutošću iz nosivosti pilota.
- Kontrola: nema neopravdanog odizanja (vlačne reakcije) pod gravitacijskim kombinacijama;
  tlak na tlo unutar dopuštenog.

## 6.3 Kontrola valjanosti modela (obavezno prije rezultata)
Sistematska lista; **dealbreakeri** moraju biti riješeni, ostalo su upozorenja.

### 6.3.1 Stabilnost i povezanost (dealbreaker)
- Nema poruke "structure is unstable / ill-conditioned".
- Nema nepovezanih (disconnected) čvorova/elemenata; svi spojevi imaju zajednički čvor.
- Nema mehanizma (nedovoljno oslonaca/veza).
- Provjera "Check Model" (preklapanja, dvostruki elementi, mali razmaci).

### 6.3.2 Ravnoteža (obavezno)
- **Σ vertikalnih reakcija = ukupno vertikalno opterećenje** (G+Q) unutar tolerancije
  (npr. < 1–2%). Veliko odstupanje → izgubljeno/dvostruko opterećenje ili loš put sila.
- Bazni posmik iz analize odgovara očekivanom (npr. seizmički V_b ≈ Sd(T1)·M·λ).

### 6.3.3 Masa i dinamika
- Ukupna masa modela ≈ ručna procjena (površina × broj etaža × prosječno opterećenje/g).
- Sudjelujuća modalna masa ≥ 90% (poglavlje 5.4).
- Prvi period T1 fizički realan: gruba provjera T1 ≈ 0,05–0,10·H^0,75 ili ~0,1·n (n = broj
  etaža) kao red veličine; jako odstupanje → kriva masa/krutost.

### 6.3.4 Deformacije i sile
- Pomaci (drift) unutar granica (poglavlje 5.8); nerealno veliki pomak → premala krutost
  (npr. zaboravljena dijafragma ili offset).
- Nema nerealnih koncentracija sila (singulariteti na osloncima/uglovima mreže).
- Predznaci i redoslijed veličina sila fizički smisleni.

### 6.3.5 Cjelovitost definicija
- Svi elementi imaju presjek + materijal.
- Sve etaže imaju dijafragmu odgovarajućeg tipa.
- Definirana opterećenja i kombinacije (ULS/SLS/seizmičke).
- Za seizmiku: spektar, masa (ψ_E), raspucala krutost, ekscentricitet ±5%.

## 6.4 Tipične greške u studentskim modelima (checklist za prepoznavanje)
| Greška | Simptom u modelu | Posljedica |
|---|---|---|
| Izostavljeni oslonci | unstable/ill-conditioned | nema rješenja |
| Nepovezani elementi | viseći čvorovi, mehanizam | krivi put sila / nestabilnost |
| Nema definirane mase | "no mass, no eigen modes" | nema modalne analize |
| Dijafragma nedodijeljena | prevelik/neujednačen drift | krivi put sila, torzija |
| Kruta dijafragma na fleksibilnoj ploči | podcijenjena torzija | nesigurni rezultati |
| Membrana meshirana | precijenjeni momenti u gredama | pogrešno dimenzioniranje |
| Puna (bruto) krutost pri seizmici | prekratki periodi, podcijenjeni pomaci | nekonzervativno |
| Premalo modova (< 90%) | podcijenjen odziv | nesigurno |
| Krivi release | nestabilnost ili kriva raspodjela M | pogrešne sile |
| Nerealna opterećenja | Σ reakcija ne odgovara | pogrešan proračun |

## 6.5 Izlaz aplikacije (za profesora)
Za svaku stavku iz 6.3–6.4 aplikacija daje: **status (U redu / Upozorenje / Greška)**,
izmjerenu vrijednost, referentnu granicu i članak norme/izvor. Sažetak: ukupna ocjena
prihvatljivosti modela + popis dealbreakera koji ga čine nevaljanim. Sve pretpostavke
(zadano iz ulazne kontrole, heurističke klasifikacije) jasno su označene kao pretpostavke,
ne kao pročitane činjenice.

## 6.6 Granice i odgovornost
Aplikacija rekonstruira model i provodi kvantitativne provjere prema normi, ali **ovlašteni
inženjer / nastavnik potvrđuje nalaze i preuzima stručnu odgovornost.** Automatski generiran
model je pomoć pri izradi i reviziji, ne ovjeren proračunski model za izvedbu.

---
### Izvori (poglavlje 6)
- EN 1997-1 (geotehnika, nosivost tla, temelji — načelno).
- EN 1998-1:2004 (masa, modalna masa, pomaci — kako je referirano u pogl. 5).
- CSI/ETABS "Check Model", analiza log, provjere stabilnosti i mase.
- Stručna literatura o čestim greškama u modeliranju (dijafragme, oslonci, masa, releases).
- Inženjerska praksa provjere ravnoteže (Σ reakcija = Σ opterećenja) i realnosti perioda.
