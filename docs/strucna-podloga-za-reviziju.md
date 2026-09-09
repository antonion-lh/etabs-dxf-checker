# Stručna podloga za sustav automatske provjere numeričkih modela zgrada
## Dokument za recenziju

**Namjena dokumenta:** Ovo je stručna podloga (baza znanja) na kojoj se temelji sustav za
poluautomatsku provjeru (reviziju) numeričkih modela zgrada u edukacijskom kontekstu —
nastavnik provjerava studentski model izrađen u programu ETABS. Dokument definira što se
smatra kvalitetnim numeričkim modelom i koje se provjere provode. Molimo recenziju stručne
točnosti, potpunosti i primjerenosti kriterija.

**Referentne norme:** EN 1990:2002 (osnove projektiranja), EN 1991 (djelovanja),
EN 1992-1-1:2004 (betonske konstrukcije), EN 1998-1:2004 (potresno projektiranje), sve zajedno
s pripadnim hrvatskim nacionalnim dodacima (HRN EN … /NA). U tijeku je i druga generacija
Eurokodova; brojčane granice i faktori ovise o nacionalnom dodatku i važećoj verziji norme.

**Ograda:** Sustav predlaže i provjerava; ovlašteni inženjer/nastavnik potvrđuje nalaze i
preuzima stručnu odgovornost. Ovo nije zamjena za normu niti za stručnu prosudbu.

---

# Dio 1 — Načela modeliranja i idealizacije

## 1.1 Svrha i granice
Numerički model je **idealizacija** stvarne konstrukcije — pojednostavljenje kojim se stvarno
ponašanje aproksimira konačnim brojem elemenata, čvorova i rubnih uvjeta. Kvaliteta modela
mjeri se time koliko vjerno i sigurno predviđa stvarni odziv, a ne izgledom "urednosti". Softver
uvijek daje neki rezultat; zadatak revizije je utvrditi je li taj rezultat posljedica ispravnih
pretpostavki. Načelo: ako je geometrija ili rubni uvjet pogrešan, svi rezultati nizvodno su
pogrešni bez obzira koliko analiza izgleda čisto.

U dokumentu se razlikuju: (1) **normativni zahtjevi** — izravno iz Eurokoda, navedeni s člankom;
(2) **inženjerske smjernice / dobra praksa** — iz priručnika i literature, mogu varirati;
(3) **heuristike alata** — pravila prepoznavanja i pretpostavke koje alat koristi i koje uvijek
treba potvrditi.

## 1.2 Linijski elementi (stupovi, grede)
- Modeliraju se kao štapni elementi kroz težište presjeka (osno).
- **Kruti krajevi (rigid end offsets):** stvarni elementi imaju konačne dimenzije te se u čvoru
  preklapaju; offset svodi deformabilnu duljinu na svijetli raspon umjesto osnog razmaka.
  Zanemarivanje precjenjuje fleksibilnost i pomake. Faktor krutosti krute zone kreće se od 0
  (bez dodatne krutosti, konzervativno) do 1 (potpuno kruto); izbor je inženjerska odluka.
- **Momentna oslobođenja (releases):** uklještena vs. zglobno spojena greda bitno mijenja
  raspodjelu momenata; pogrešan release je čest izvor krivih rezultata.

## 1.3 Plošni elementi (zidovi, ploče)
- **Shell vs. membrane:** shell prenosi savijanje i membransko djelovanje; membrane samo
  membransko (u ravnini). Ploča koja nosi savijanjem = shell; ploča koja samo raznosi
  opterećenje kao kruta dijafragma = membrane. Izbor orijentacijski prema omjeru debljine/raspona.
- **Mreženje (mesh):** shell elementi se mreže radi realnog prijenosa opterećenja i
  kompatibilnosti s gredama/zidovima. Membranu se ne mreži jer mreženje precjenjuje momente i
  sile u gredama. Automatsko mreženje mora poštovati rubove greda i zidova.
- **Zidovi — pier/spandrel:** za smisleno dimenzioniranje posmičnih zidova potrebno je označiti
  pier (vertikalni segment) i spandrel (nadvoj/parapet); bez oznaka rezultati sila u zidu nisu
  upotrebljivi za dimenzioniranje.

## 1.4 Dijafragme
- **Kruta dijafragma:** nameće jednak bočni pomak svim čvorovima etaže (translacija + rotacija
  kao kruto tijelo). Prema EN 1998-1 (čl. 4.3.1), pretpostavka krute dijafragme prihvatljiva je
  ako horizontalni pomaci uz stvarnu podatljivost nigdje ne prelaze za više od 10% pomake uz
  krutu pretpostavku. (Orijentacijski, prema ASCE 7/IBC, dijafragma se smatra fleksibilnom kad
  je omjer raspon/dubina > 3; taj kriterij nije dio EN 1998-1 nego praktična smjernica.)
- **Fleksibilna / polukruta:** za drvene stropove, tanke limove, otvorene tlocrte i velike
  otvore kruta pretpostavka daje lažne rezultate (krivi put sila, podcijenjena torzija) — tada
  polukruta ili eksplicitno modeliranje krutosti.
- Česta greška: dijafragma uopće nije dodijeljena, pa se etaže tretiraju kao nepovezane.

## 1.5 Oslonci i temelji
- Rubni uvjeti definiraju prijenos sila u tlo; uklještenje / zglob / elastični oslonac bitno
  mijenjaju rezultate. Izostavljeni ili pogrešni oslonci vode do nestabilne konstrukcije
  ("structure is unstable / ill-conditioned").

## 1.6 Masa, krutost i dinamika (EN 1998-1)
- **Efektivna (raspucala) krutost:** EN 1998-1 (čl. 4.3.1(6)–(7)) dopušta da se za betonske i
  zidane elemente krutost na savijanje i posmik uzme kao 50% odgovarajuće krutosti neraspucalih
  elemenata, osim ako se detaljnijom analizom odredi drukčije; usvojena krutost treba odražavati
  stanje pri početku tečenja armature. Puna (bruto) krutost podcjenjuje pomake i nekonzervativno
  utječe na periode.
- **Masa za seizmičku analizu:** kombinacija G + ψ_E·Q, uz ψ_Ei = φ·ψ_2i. Bez definirane mase
  nema vlastitih oblika vibracija.
- **Modalna analiza (čl. 4.3.3.3.1):** uzeti dovoljan broj vlastitih oblika prema jednom od dva
  kriterija — (a) zbroj efektivnih modalnih masa ≥ 90% ukupne mase u svakom razmatranom smjeru,
  ILI (b) uzeti sve oblike s efektivnom modalnom masom > 5% ukupne mase.
- **Slučajni ekscentricitet:** ± 5% dimenzije etaže okomito na smjer potresa.

## 1.7 Pravilnost konstrukcije (EN 1998-1, čl. 4.2.3)
**U tlocrtu:** približna simetrija mase i krutosti u odnosu na dvije ortogonalne osi; kompaktan
tlocrt; ograničeni uvučeni kutovi; dovoljna torzijska krutost (mali ekscentricitet centra mase
CM naspram centra krutosti CS). Tri glavna kriterija tlocrtne nepravilnosti: torzija, uvučeni
kutovi, fleksibilnost ploče.
**Po visini:** kontinuitet nosivih sustava od vrha do temelja; postupna (ne nagla) promjena
mase i krutosti; poseban oprez na meki kat (naglo smanjenje bočne krutosti jedne etaže, tipično
prizemlja).

## 1.8 Kombinacije opterećenja (EN 1990)
- Osnovna granična nosivost (ULS): 1,35·G + 1,5·Q (s pripadnim ψ za više promjenjivih djelovanja).
- Seizmička kombinacija: G + ψ_2·Q + A_Ed.
- Model mora imati definirane uzorke opterećenja i ispravne kombinacije.

---

# Dio 2 — Kontrolna lista provjere modela

Provjere su grupirane po ozbiljnosti. Predloženi statusi: **U redu / Upozorenje / Greška**
(pri čemu je "Greška" onemogućavajuća — model bez toga nije valjan za analizu).

## 2.1 Geometrija i povezanost (onemogućavajuće)
1. **Povezanost elemenata** — nema nepovezanih linija/ploha; čvorovi se poklapaju na spojevima.
2. **Oslonci/temelji definirani** — svaki vertikalni nosivi element ima put do tla.
3. **Kontinuitet po visini** — stupovi/zidovi idu do temelja bez neopravdano "visećih" elemenata
   (osim ispravno modeliranih transfer elemenata).

## 2.2 Masa i dinamika (kritično za seizmiku)
4. **Masa definirana** (postoji izvor mase).
5. **Sudjelujuća modalna masa ≥ 90%** u svakom glavnom smjeru (ili kriterij oblika > 5%).
6. **Slučajni ekscentricitet ± 5%** primijenjen.
7. **Raspucala krutost** (50% neraspucalih, savijanje i posmik) za AB/zidano pri seizmici, ako
   se traži.

## 2.3 Dijafragme i put sila
8. **Dijafragma dodijeljena** svakoj etaži i tip primjeren ploči (EN 1998-1 kriterij 10%).
9. **Mreženje** shell elemenata ispravno; membranu ne mrežiti.

## 2.4 Presjeci, materijali, opterećenja
10. **Svi elementi imaju presjek i materijal.**
11. **Opterećenja** (stalno, uporabno, vjetar, potres) definirana i dodijeljena.
12. **Kombinacije** (EN 1990) postoje.

## 2.5 Pravilnost i inženjerska prosudba
13. **Torzija / ekscentricitet CM–CS** u granicama.
14. **Meki kat** — provjera naglog pada krutosti.
15. **Uvučeni kutovi / tlocrtna nepravilnost.**
16. **Realnost rezultata** — pomaci (drift) u granicama, reakcije u ravnoteži s opterećenjem,
    faktori (npr. prevrtanje) fizički smisleni.

---

# Dio 3 — Pretvorba nacrta (DXF) u elemente modela (načelno)

Sustav kao ulaz koristi vektorski nacrt (DXF), iz kojeg prepoznaje konstruktivne elemente na
temelju: **slojeva (layers)** kao najjačeg signala (npr. ZID, STUP, GREDA, PLOČA), **vrste
entiteta** (linije/polilinije za osi i rubove, kružnice za kružne stupove, blokovi za tipske
elemente, tekst i kote za dimenzije), te **geometrijskih obrazaca** (par bliskih paralelnih
linija = zid; mala zatvorena kontura = stup; linija između stupova = greda).

Redoslijed pouzdanosti klasifikacije: (1) naziv sloja; (2) naziv bloka; (3) geometrijska
heuristika; kote i tekst se ne tretiraju kao konstruktivni elementi nego kao izvor dimenzija.

**Iz jednog tlocrta ne može se izvesti puni 3D model** (nedostaju visine i broj etaža). Kada ti
podaci nisu u nacrtu, sustav traži unos (broj etaža, visine, pravila ponavljanja). Također se iz
same geometrije ne mogu pouzdano izvući: materijali, opterećenja i kombinacije, rubni uvjeti,
te oznake pier/spandrel i tip dijafragme — to su unosi/inženjerske odluke.

---

# Pitanja za recenzenta
1. Jesu li navedeni normativni kriteriji (raspucala krutost, modalna masa, ekscentricitet,
   dijafragma, pravilnost) ispravno interpretirani i primjereno formulirani za edukacijsku
   provjeru?
2. Nedostaje li koja bitna provjera koju u praksi radite pri pregledu studentskih modela?
3. Koje biste granične vrijednosti (npr. za torziju, meki kat, ekscentricitet CM–CS) smatrali
   prihvatljivima kao prag "upozorenje" odnosno "greška"?
4. Ima li kriterija specifičnih za hrvatski nacionalni dodatak koje treba izrijekom uključiti?
5. Je li razdioba na "onemogućavajuće" naspram "upozorenje" prikladna, ili biste je drukčije
   posložili?

---

## Korišteni izvori i literatura
- EN 1990:2002 — Osnove projektiranja konstrukcija.
- EN 1991 — Djelovanja na konstrukcije.
- EN 1992-1-1:2004 — Betonske konstrukcije, opća pravila.
- EN 1998-1:2004 — Potresno projektiranje (čl. 4.2.3 pravilnost; čl. 4.3.1 raspucala krutost i
  kruta dijafragma; čl. 4.3.3.3.1 modalna analiza; masa i slučajni ekscentricitet).
- ASCE 7 / IBC — klasifikacija dijafragmi (rigid/semi-rigid/flexible), praktični kriterij
  raspon/dubina.
- CSI / ETABS dokumentacija i priručnici — modeliranje, mreženje, kruti krajevi, pier/spandrel,
  provjera modela (Check Model).
- Stručna literatura i praksa o čestim greškama u modeliranju (dijafragme, oslonci, masa,
  modalna analiza).

Napomena: normativni sadržaj je parafraziran i sažet; sve brojčane granice i faktore provjeriti
u važećoj verziji norme i pripadnom nacionalnom dodatku.
