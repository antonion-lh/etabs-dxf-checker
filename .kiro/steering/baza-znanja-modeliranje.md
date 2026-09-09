---
inclusion: manual
---
# Baza znanja: Modeliranje konstrukcija i provjera numeričkog modela

> Namjena: stručni temelj za provjeru (reviziju) numeričkih modela zgrada, prvenstveno
> armiranobetonskih, u edukacijskom kontekstu (profesor provjerava studentski model iz
> ETABS-a). Dokument definira što čini kvalitetan numerički model i koje se provjere rade.
> Izvori su navedeni na dnu. Referentne norme: **EN 1990:2002** (osnove), **EN 1991**
> (djelovanja), **EN 1992-1-1:2004** (beton), **EN 1998-1:2004** (potres), sve zajedno s
> pripadnim hrvatskim nacionalnim dodacima (HRN EN ... /NA). Ovo NIJE zamjena za normu ni za
> prosudbu ovlaštenog inženjera; brojčane granice i faktori ovise o nacionalnom dodatku i
> važećoj verziji norme (u tijeku je i druga generacija Eurokodova).

## 1. Svrha i granice

Numerički model je **idealizacija** stvarne konstrukcije — pojednostavljenje kojim se
stvarno ponašanje aproksimira konačnim brojem elemenata, čvorova i rubnih uvjeta. Kvaliteta
modela mjeri se time koliko vjerno i sigurno predviđa stvarni odziv, a ne time izgleda li
"uredno". Softver (ETABS) uvijek daje neki rezultat; zadatak revizije je utvrditi je li taj
rezultat posljedica ispravnih pretpostavki.

Ključno načelo: **ako je geometrija ili rubni uvjet pogrešan, svi rezultati nizvodno su
pogrešni, bez obzira koliko analiza izgleda čisto.** (izvor: Santiago, 7 ETABS mistakes)

U dokumentu se razlikuju: (1) **normativni zahtjevi** — izravno iz Eurokoda, navedeni s
člankom; (2) **inženjerske smjernice / dobra praksa** — iz priručnika i literature, mogu
varirati; (3) **heuristike alata** — pravila prepoznavanja i pretpostavke koje alat koristi i
koje uvijek treba potvrditi. Tamo gdje je granica bitna, izvor je naznačen uz tvrdnju.

## 2. Idealizacija konstruktivnih elemenata

### 2.1 Linijski elementi (frame): stupovi, grede
- Modeliraju se kao štapni elementi kroz težište presjeka (centerline).
- **Rigid end offsets (kruti krajevi):** stvarni elementi imaju konačne dimenzije; u čvoru
  se grede i stupovi preklapaju. Rigid end offset skraćuje deformabilnu duljinu na svijetli
  raspon (clear span) umjesto osnog razmaka (centerline). Zanemarivanje precjenjuje
  fleksibilnost i pomake. ETABS može automatski računati offset; faktor krutosti krute zone
  (rigid-zone factor) kreće se od 0 (bez dodatne krutosti u zoni preklapanja, konzervativno)
  do 1 (potpuno kruta zona); izbor je inženjerska odluka. (izvor: End Length Offsets; SAP2000
  tutorial; CSI dokumentacija)
- **Momentna oslobođenja (releases):** greda uklještena vs. zglobno spojena mijenja
  raspodjelu momenata. Pogrešni release je čest izvor krivih rezultata.

### 2.2 Plošni elementi (shell/area): zidovi, ploče
- **Shell vs. membrane:** shell prenosi i savijanje (out-of-plane) i membransko djelovanje;
  membrane samo membransko (u ravnini). Ploča koja nosi savijanjem = shell; ploča koja samo
  raznosi opterećenje na grede kao kruta dijafragma = membrane. Omjer debljine/raspona
  orijentacijski određuje izbor. (izvor: Etabs Notes; ETABS TIPS)
- **Meshiranje:** shell elementi se moraju mrežiti za realan prijenos opterećenja i
  kompatibilnost s gredama/zidovima. VAŽNO: membrane ploču NE mrežiti — mreženje membrane
  precjenjuje momente i sile u gredama. Auto-mesh mora poštovati rubove greda i zidova.
  (izvor: ETABS TIPS)
- **Zidovi — pier/spandrel:** za smisleno dimenzioniranje posmičnih zidova nužno je označiti
  pier (vertikalni segment zida) i spandrel (nadvoj/parapet). Bez oznaka rezultati sila u
  zidu nisu upotrebljivi za dizajn. (izvor: Pier and Spandrel Labeling)

### 2.3 Dijafragme (katne ploče kao horizontalni element)
- **Kruta (rigid) dijafragma:** nameće jednak bočni pomak svim čvorovima etaže (translacija
  + rotacija kao kruto tijelo). Prema EN 1998-1 (čl. 4.3.1), dijafragma se smije smatrati krutom
  ako pri modeliranju s njezinom stvarnom podatljivošću horizontalni pomaci nigdje ne prelaze
  za više od **10%** pomake dobivene uz pretpostavku krute dijafragme. (Orijentacijski,
  prema ASCE 7/IBC, dijafragma se smatra fleksibilnom kad je omjer raspon/dubina > 3 —
  taj kriterij NIJE dio EN 1998-1 nego se navodi kao praktična smjernica.) (izvori: EN 1998-1
  čl. 4.3.1; Modeling and Analysis on Diaphragms — ASCE 7/IBC)
- **Fleksibilna / polukruta:** za drvene stropove, tanke metalne limove, otvorene tlocrte,
  velike otvore — kruta pretpostavka daje lažne rezultate (krivi put sila, podcijenjena
  torzija). Tada polukruta (semi-rigid) ili eksplicitno modeliranje krutosti. (izvor:
  Diaphragm Considerations; civilera Rigid vs Flexible)
- **Najčešća greška:** dijafragma uopće nije dodijeljena — softver tretira etaže kao
  nepovezane, put sila je pogrešan. (izvor: civilera)
- Oprez kod nelinearnih RC fiber presjeka: kruti constraint (nulta osna deformacija na osi
  elementa) mijenja odziv jer se neutralna os pomiče pri savijanju. (izvor: OpenSees Berkeley)

### 2.4 Oslonci i temelji
- Rubni uvjeti (restraints) definiraju kako konstrukcija prenosi sile u tlo. Uklještenje vs.
  zglob vs. elastični oslonac bitno mijenja rezultate.
- **Najčešća greška:** izostavljeni oslonci ili pogrešno postavljeni — vodi do nestabilne
  konstrukcije. ETABS upozorenje "structure is unstable or ill-conditioned" tipično znači
  nepovezane elemente, mehanizam ili krive oslonce. (izvor: sheerforceeng)

## 3. Masa, krutost i dinamika (EN 1998)

- **Efektivna (raspucala) krutost:** EN 1998-1 (čl. 4.3.1(6)–(7)) dopušta da se za betonske
  i zidane elemente krutost na savijanje i posmik uzme kao **50% odgovarajuće krutosti
  neraspucalih elemenata**, osim ako se detaljnijom analizom odredi drukčije; usvojena krutost
  treba odražavati stanje pri početku tečenja armature. Korištenje pune (bruto) krutosti
  podcjenjuje pomake i produljuje/skraćuje periode na nekonzervativan način. (izvor: EN 1998-1
  čl. 4.3.1)
- **Masa za seizmičku:** kombinacija G + ψ_E·Q, gdje je ψ_Ei = φ·ψ_2i. Model bez definirane
  mase ne može dati vlastite oblike — ETABS javlja "no mass, no eigen modes". (izvor:
  EN 1998-1; eng-tips)
- **Modalna analiza:** EN 1998-1 (čl. 4.3.3.3.1) traži da se uzme dovoljan broj vlastitih
  oblika, i to prema jednom od dva kriterija: (a) zbroj efektivnih modalnih masa iznosi
  najmanje **90% ukupne mase konstrukcije** u svakom razmatranom smjeru, ILI (b) uzmu se svi
  oblici s efektivnom modalnom masom većom od **5% ukupne mase**. Premalo obuhvaćenih oblika
  podcjenjuje odziv. (izvor: EN 1998-1 čl. 4.3.3.3.1)
- **Slučajni ekscentricitet:** ± 5% dimenzije etaže okomito na smjer potresa, za obuhvat
  nesigurnosti u raspodjeli mase i torzije. (izvor: EN 1998-1)

## 4. Pravilnost konstrukcije (EN 1998-1)

### 4.1 Pravilnost u tlocrtu
- Približna simetrija mase i krutosti u odnosu na dvije ortogonalne osi.
- Kompaktan tlocrt; uvučeni kutovi (reentrant corners) ograničeni.
- Dovoljna torzijska krutost: mali ekscentricitet između centra mase (CM) i centra krutosti
  (CS); dovoljan radijus tromosti. Velika CM–CS udaljenost = velika torzija. (izvor: EN 1998-1;
  ulisboa CS analiza)
- Tri glavna kriterija tlocrtne nepravilnosti: **torzija, uvučeni kutovi, fleksibilnost
  ploče.** (izvor: ASCE 7 / EN 1998)

### 4.2 Pravilnost po visini
- Kontinuitet nosivih sustava od vrha do temelja (stupovi i zidovi ne smiju "visjeti").
- Postupna (ne nagla) promjena mase i krutosti po visini.
- **Meki kat (soft storey):** naglo smanjenje bočne krutosti jedne etaže (tipično prizemlje
  s velikim otvorima/bez zidova) — kritična seizmička ranjivost. (izvor: EN 1998-1; jetir)

## 5. Kombinacije opterećenja (EN 1990)
- Osnovna ULS kombinacija (stalno + promjenjivo): 1.35·G + 1.5·Q (s pripadnim ψ za više
  promjenjivih djelovanja).
- Seizmička kombinacija: G + ψ_2·Q + A_Ed (potresno djelovanje).
- Model mora imati definirane uzorke opterećenja (dead, live, wind, seismic) i ispravne
  kombinacije; izostanak = nepotpun proračun.

---

## Izvori
- EN 1990:2002 — Osnove projektiranja konstrukcija (kombinacije djelovanja). JRC Eurocodes
  portal: https://eurocodes.jrc.ec.europa.eu/en-eurocodes
- EN 1991 — Djelovanja na konstrukcije (vlastita težina, uporabno, vjetar, snijeg).
- EN 1992-1-1:2004 — Betonske konstrukcije (opća pravila).
- EN 1998-1:2004 — Projektiranje konstrukcija otpornih na potres (čl. 4.3.1 raspucala krutost i
  kruta dijafragma; čl. 4.3.3.3.1 modalna analiza; čl. 4.2.3 pravilnost; masa i ekscentricitet).
- Modeling and Analysis on Diaphragms (span/depth ≤ 3, klasifikacija dijafragmi).
- Diaphragm Considerations for Structural Engineers (ASCE 7 / IBC klasifikacija).
- End Length Offsets (rigid end offsets, clear span vs centerline).
- ETABS TIPS (mesh, membrane vs shell, moment release).
- Etabs Notes (shell vs membrane po omjeru debljine/raspona).
- Pier and Spandrel Labeling for ETABS Shear Wall Design.
- OpenSees / UC Berkeley — Diaphragm modeling (rigid constraint i nelinearni RC presjeci).
- Santiago, "7 ETABS mistakes junior engineers make".
- civilera — Rigid vs Flexible Diaphragm Mistakes; How to Model Irregular Buildings.
- sheerforceeng — "Structure is unstable or ill-conditioned" fix.
- eng-tips — "no mass, no eigen modes".

Napomena: sadržaj je parafraziran i sažet iz navedenih izvora radi usklađenosti s licencnim
ograničenjima; brojčane vrijednosti provjeriti u važećoj verziji norme i nacionalnom dodatku.
