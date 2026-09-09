---
inclusion: manual
---
# Baza znanja: Modeliranje konstrukcija i provjera numeričkog modela

> Namjena: stručni temelj za provjeru (reviziju) numeričkih modela zgrada, prvenstveno
> armiranobetonskih, u edukacijskom kontekstu (profesor provjerava studentski model iz
> ETABS-a). Dokument definira što čini kvalitetan numerički model i koje se provjere rade.
> Izvori su navedeni na dnu. Ovo NIJE zamjena za normu ni za prosudbu ovlaštenog inženjera.

## 1. Svrha i granice

Numerički model je **idealizacija** stvarne konstrukcije — pojednostavljenje kojim se
stvarno ponašanje aproksimira konačnim brojem elemenata, čvorova i rubnih uvjeta. Kvaliteta
modela mjeri se time koliko vjerno i sigurno predviđa stvarni odziv, a ne time izgleda li
"uredno". Softver (ETABS) uvijek daje neki rezultat; zadatak revizije je utvrditi je li taj
rezultat posljedica ispravnih pretpostavki.

Ključno načelo: **ako je geometrija ili rubni uvjet pogrešan, svi rezultati nizvodno su
pogrešni, bez obzira koliko analiza izgleda čisto.** (izvor: Santiago, 7 ETABS mistakes)

## 2. Idealizacija konstruktivnih elemenata

### 2.1 Linijski elementi (frame): stupovi, grede
- Modeliraju se kao štapni elementi kroz težište presjeka (centerline).
- **Rigid end offsets (kruti krajevi):** stvarni elementi imaju konačne dimenzije; u čvoru
  se grede i stupovi preklapaju. Rigid end offset skraćuje deformabilnu duljinu na svijetli
  raspon (clear span) umjesto osnog razmaka (centerline). Zanemarivanje precjenjuje
  fleksibilnost i pomake. ETABS može automatski računati offset (faktor krutosti tipično
  0.5–1.0). (izvor: End Length Offsets; SAP2000 tutorial)
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
  + rotacija kao kruto tijelo). Primjenjiva kad je ploča dovoljno kruta u svojoj ravnini —
  orijentacijski span/depth <= 3 i bez izraženih tlocrtnih nepravilnosti. (izvor: Modeling
  and Analysis on Diaphragms)
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

- **Efektivna (raspucala) krutost:** za AB elemente pri seizmičkoj analizi uzeti smanjenu
  krutost napukloga presjeka — orijentacijski 50% krutosti neraspucalog (0.5·Ec·I), osim ako
  se detaljnijom analizom dokaže drukčije. Korištenje pune (bruto) krutosti podcjenjuje
  pomake i periode. (izvor: EN 1998-1)
- **Masa za seizmičku:** kombinacija G + ψ_E·Q, gdje je ψ_Ei = φ·ψ_2i. Model bez definirane
  mase ne može dati vlastite oblike — ETABS javlja "no mass, no eigen modes". (izvor:
  EN 1998-1; eng-tips)
- **Modalna analiza:** zbroj efektivnih modalnih masa mora doseći ≥ 90% ukupne mase u svakom
  glavnom smjeru (ili uključiti sve modove s > 5% efektivne mase). Premalo modova = podcijenjen
  odziv. (izvor: EN 1998-1)
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
- EN 1990 — Osnove projektiranja konstrukcija (kombinacije). JRC Eurocodes portal:
  https://eurocodes.jrc.ec.europa.eu/en-eurocodes
- EN 1998-1 — Projektiranje konstrukcija otpornih na potres (pravilnost, masa, modalna analiza,
  ekscentricitet, raspucala krutost).
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
