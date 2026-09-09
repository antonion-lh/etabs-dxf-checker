---
inclusion: manual
---
# Baza znanja: Kontrolna lista provjere modela + mapiranje DXF → konstruktivni elementi

> Nastavak baze znanja. Prvi dokument (modeliranje) daje principe; ovaj daje (A) praktičnu
> kontrolnu listu za reviziju numeričkog modela i (B) pravila za pretvorbu vektorskog DXF
> tlocrta u konstruktivne elemente numeričkog modela. Kontekst: profesor provjerava studentski
> model; DXF je ulaz iz kojeg rekonstruiramo/uspoređujemo model.

## A. Kontrolna lista provjere numeričkog modela

Grupirano po ozbiljnosti. Svaka stavka: što se provjerava → tipična greška → posljedica.

### A1. Geometrija i povezanost (dealbreakeri)
1. **Povezanost elemenata** — nema nepovezanih (disconnected) linija/ploha; čvorovi se
   poklapaju na spojevima. Greška: preklopljeni ili razmaknuti krajevi. Posljedica: mehanizam,
   "unstable/ill-conditioned". (izvor: ETABS Check Model; sheerforceeng)
2. **Oslonci/temelji definirani** — svaki vertikalni nosivi element ima put do tla. Greška:
   izostavljen restraint. Posljedica: nestabilnost, nema rješenja.
3. **Kontinuitet po visini** — stupovi/zidovi idu od vrha do temelja bez "visećih" elemenata
   (osim namjernih transfer elemenata koji tada moraju biti ispravno modelirani).

### A2. Masa i dinamika (kritično za seizmiku)
4. **Masa definirana** — postoji izvor mase (mass source). Greška: nema mase. Posljedica:
   "no mass, no eigen modes", nema modalne analize. (izvor: eng-tips)
5. **Sudjelujuća modalna masa ≥ 90%** u svakom glavnom smjeru. Greška: premalo modova.
6. **Slučajni ekscentricitet ±5%** primijenjen.
7. **Raspucala krutost** (0.5·EI orijentacijski) za AB pri seizmici, ako se traži.

### A3. Dijafragme i put sila
8. **Dijafragma dodijeljena** svakoj etaži i tipom primjerena ploči (rigid/semi-rigid/flexible).
   Greška: nema dijafragme ili kruta na fleksibilnoj ploči. Posljedica: krivi put sila,
   pogrešna torzija. (izvor: civilera)
9. **Meshiranje** shell elemenata ispravno; membrane NE meshirati.

### A4. Presjeci, materijali, opterećenja
10. **Svi elementi imaju presjek i materijal** (nema "praznih" definicija).
11. **Opterećenja** (stalno, uporabno, vjetar, potres) definirana i dodijeljena.
12. **Kombinacije** (EN 1990: 1.35G+1.5Q; seizmička G+ψ2·Q+E) postoje.

### A5. Pravilnost i inženjerska prosudba
13. **Torzija / ekscentricitet CM–CS** u granicama; upozoriti na velik ekscentricitet.
14. **Meki kat** — provjeriti nagli pad krutosti (tipično prizemlje).
15. **Reentrant corners / tlocrtna nepravilnost**.
16. **Realnost rezultata** — pomaci (drift) unutar granica, reakcije u ravnoteži s
    opterećenjem, faktori (npr. prevrtanje) fizički smisleni.

> Napomena o statusima: revizija označava PASS / UPOZORENJE / GREŠKA (dealbreaker), analogno
> postojećem curriculum_audit sustavu u aplikaciji.

## B. Mapiranje DXF entiteta → konstruktivni elementi

DXF je vektorski i strukturiran — za razliku od skeniranog rastera, čitamo prave entitete i
slojeve. Cilj mapiranja: iz geometrije + slojeva prepoznati konstruktivne elemente.

### B1. Izvori informacije u DXF-u
- **Slojevi (layers):** najjači signal. Nazivi tipa "ZID/WALL", "STUP/COL", "GREDA/BEAM",
  "PLOCA/SLAB", "KOTA/DIM", "TEKST/TEXT". Konvencija imenovanja se koristi za klasifikaciju.
- **Entiteti:** LINE/LWPOLYLINE (osi/rubovi), CIRCLE (kružni stupovi), ARC, INSERT (blokovi —
  stupovi, temelji, tipski elementi), TEXT/MTEXT (oznake presjeka, kote), HATCH (ispune
  zidova/presjeka), DIMENSION (kote).
- **Geometrijski obrasci:** par bliskih paralelnih linija = zid (dvije strane); zatvoreni mali
  pravokutnik/krug = stup; duga linija između stupova = greda/os; velika zatvorena kontura =
  ploča/etaža.

### B2. Pravila klasifikacije (redoslijed pouzdanosti)
1. Ako naziv sloja jednoznačno ukazuje na tip → koristi taj tip (najviša pouzdanost).
2. Inače, blok (INSERT) s imenom koje ukazuje na element → tip po imenu bloka.
3. Inače, geometrijska heuristika (paralelni par → zid; mala zatvorena kontura → stup;
   linija koja spaja dva stupa → greda).
4. Kote (DIMENSION/TEXT) i tekst → NE konstruktivni element; koriste se za dimenzije
   presjeka i provjeru mjera (usp. postojeći pdf_dims pristup po vrijednosti presjeka).

### B3. 2D → 3D (etaže i visine)
- Jedan tlocrt = jedna etaža u ravnini. Za 3D model zgrade treba: broj etaža, visine katova,
  vertikalni kontinuitet (koji se elementi ponavljaju po etažama).
- **Kad DXF sadrži više etaža** (npr. odvojeni tlocrti po slojevima ili blokovima): rekonstruira
  se višeetažni model iz dostupnih podataka.
- **Kad DXF nema te podatke:** ulazna kontrola u kojoj profesor upisuje broj etaža, visinu
  kata (jednoliku ili po etaži), i pravila ponavljanja. Bez tih podataka model ostaje 2D
  (jedna ravnina) uz jasnu napomenu.

### B4. Što se NE može pouzdano izvući samo iz DXF geometrije
- Materijali i klase betona/čelika (osim ako su u tekstu/tablici nacrta).
- Opterećenja i kombinacije (moraju se zadati ili pročitati iz zasebnog izvora).
- Rubni uvjeti/oslonci (osim ako su na zasebnom sloju ili blokovima).
- Pier/spandrel oznake, releases, dijafragma tip — inženjerske odluke.
Ove stavke → ili ulazna kontrola (profesor zadaje) ili se u budućnosti čitaju iz ETABS-a
(direktna veza, kako je korisnik naveo kao dugoročni cilj).

---

## Izvori
- ETABS "Check Model" (overlaps, disconnected lines/areas, base supports) — ETABS Tips.
- sheerforceeng — nestabilna/ill-conditioned konstrukcija.
- eng-tips — nedostatak mase i modalne analize.
- civilera — greške s dijafragmama.
- EN 1990, EN 1998-1 — kombinacije, masa, modalna analiza, ekscentricitet, pravilnost.
- Postojeći moduli aplikacije: curriculum_audit (sustav ocjenjivanja PASS/WARN/FAIL),
  phase2_dxf (DXF parsiranje: LINE/LWPOLYLINE, slojevi, zatvoreni poligoni), pdf_dims
  (usporedba presjeka po vrijednosti).

Napomena: sadržaj parafraziran/sažet radi licencne usklađenosti; brojčane granice provjeriti
u važećoj normi i nacionalnom dodatku. Ovaj dokument je pomoć pri reviziji, ne zamjena za
prosudbu ovlaštenog inženjera.
