# Upute za postavljanje na Streamlit Community Cloud (1-Click za kolegicu)

GitHub repozitorij je već kreiran i sav kôd je uspješno poslan:
🔗 **GitHub Repozitorij:** https://github.com/antonion-lh/etabs-dxf-checker

---

## 🚀 Korak 1 (i jedini): Klikni Deploy na Streamlitu

Otvori ovaj pripremljeni izravni link u svom pregledniku:
👉 **[Klikni ovdje za 1-Click Streamlit Deploy](https://share.streamlit.io/deploy?repository=antonion-lh/etabs-dxf-checker&branch=main&mainModule=streamlit_app.py)**

*(Sva polja — repozitorij `antonion-lh/etabs-dxf-checker`, grana `main` i glavna datoteka `streamlit_app.py` — automatski su već popunjena!)*

Samo klikni plavi gumb **"Deploy"**!

Za ~1 minutu tvoja aplikacija bit će aktivna na trajnoj web adresi:
👉 `https://etabs-dxf-checker.streamlit.app`

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
