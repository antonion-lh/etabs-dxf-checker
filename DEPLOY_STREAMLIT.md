# Upute za postavljanje na Streamlit Community Cloud (1-Click za kolegicu)

Ove upute objašnjavaju kako u **2 minute** podići web aplikaciju na **Streamlit Community Cloud** (besplatno), tako da kolegici pošalješ samo običan web link.

---

## Korak 1: Povezivanje na tvoj GitHub račun

1. Na svom računalu otvori terminal u mapi projekta:
   ```bash
   cd "/Users/antonionovak/Documents/Claude projekti/etabs_dxf_checker"
   ```
2. Inicijaliziraj Git (ako već nisi) i kreiraj novi repozitorij na svom GitHubu (npr. `etabs-dxf-validator`):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: ETABS DXF Web Validator"
   git branch -M main
   git remote add origin https://github.com/TVOJ-GITHUB-USERNAME/etabs-dxf-validator.git
   git push -u origin main
   ```
   *(Možeš odabrati da repozitorij bude Private ili Public).*

---

## Korak 2: Deploy na Streamlit Community Cloud

1. Idi na [share.streamlit.io](https://share.streamlit.io/) i prijavi se sa svojim Streamlit računom.
2. Klikni gumb **"New app"** (ili **"Create app"**).
3. Ispuni 3 polja:
   - **Repository**: `TVOJ-GITHUB-USERNAME/etabs-dxf-validator`
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
4. Klikni **"Deploy!"**.

Za ~1 minutu tvoja aplikacija bit će aktivna na trajnoj web adresi, npr.:
👉 `https://etabs-dxf-validator.streamlit.app`

---

## Korak 3: Kako kolegica koristi aplikaciju (Nula instalacija)

Pošalji kolegici taj link. Njen radni postupak je minimalan i jednostavan:

1. **U programu ETABS v23**:
   - Otvori numerički model zgrade.
   - Klikne: `File -> Export -> ETABS .e2k Text File...` i spremi datoteku (npr. `model.e2k`).
2. **U web pregledniku (Chrome / Edge / Firefox)**:
   - Otvori link aplikacije.
   - U lijevom izborniku:
     - Uvuče svoj CAD nacrt (`.dxf`).
     - Uvuče izvezeni ETABS model (`.e2k`).
   - Sve kontrole su automatski uključene (*Geometrija, Poprečni presjeci, Materijali, Opterećenja, Oslonci, Plastični zglobovi*).
3. **Rezultati na ekranu**:
   - **📊 Sažetak**: Kartice s točnim brojem usklađenih elemenata, odstupanja u presjecima i elemenata viška.
   - **⚠️ Upozorenja statike**: Upozorava ako je vlastita težina dvostruko zadana, ako neka ploča nema opterećenje ili ako stup u bazi nema ležaj.
   - **🗺️ Interaktivni tlocrt (2D Model View)**: Može zumirati, klikati na stupove i vidjeti dimenzije u modelu i nacrtu.
   - **📥 Preuzmi PDF elaborat**: Jednim klikom preuzima službeni landscape A4 PDF izvještaj.

---

## Lokalno pokretanje (za tebe na Macu)

Ako želiš sam pregledavati ili testirati web aplikaciju lokalno na svom Macu:
```bash
cd "/Users/antonionovak/Documents/Claude projekti/etabs_dxf_checker"
source .venv/bin/activate
streamlit run streamlit_app.py
```
Aplikacija će se automatski otvoriti u tvom zadanom web pregledniku na adresi `http://localhost:8501`.
