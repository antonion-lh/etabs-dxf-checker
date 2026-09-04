"""Poluautomatska vektorizacija skeniranog tlocrta u DXF linije.

Modul pruza asistenta koji predlaze linijske segmente iz rasterske slike
(skeniranog tlocrta) uz naknadnu rucnu korekciju korisnika; ne koristi OpenCV.
"""

import io
import logging
from math import hypot
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Segment = par tocaka (x, y) u pikselima koji definira jednu duz.
Segment = Tuple[Tuple[float, float], Tuple[float, float]]


@dataclass
class Params:
    """Parametri vektorizacije s razumnim defaultima iz spike-a i dizajna."""

    threshold: Optional[int] = None      # None -> Otsu
    min_len_px: int = 60                  # visi default (spike: sum od kota otpada)
    max_gap_px: int = 12
    angle_tol_deg: float = 5.0
    denoise_iters: int = 1
    dpi: int = 150
    dpi_cap: int = 200
    max_side_px: int = 6000               # zastita od OOM
    px_to_unit: float = 1.0               # px -> CAD jedinica
    layer_name: str = "VEKTOR_ZID"


def _otsu_threshold(gray: "np.ndarray") -> int:
    """Izracunava Otsu prag iz sive slike; vraca cjelobrojni prag [0-255].

    Rubni slucaj konstantne slike (svi pikseli isti intenzitet): between-class
    varijanca je svugdje nula pa nema smislenog razdvajanja; vracamo 127.
    """
    g = np.asarray(gray).ravel()
    hist, _ = np.histogram(g, bins=256, range=(0, 256))
    total = hist.sum()
    if total == 0:
        return 127

    # Kumulativna tezina (broj piksela) i kumulativna suma intenziteta.
    levels = np.arange(256)
    w_cum = np.cumsum(hist).astype(np.float64)
    m_cum = np.cumsum(hist * levels).astype(np.float64)
    total_mean = m_cum[-1]

    best_thr = 0
    best_var = -1.0
    for t in range(256):
        w0 = w_cum[t]
        w1 = total - w0
        if w0 == 0 or w1 == 0:
            continue
        mu0 = m_cum[t] / w0
        mu1 = (total_mean - m_cum[t]) / w1
        between = w0 * w1 * (mu0 - mu1) * (mu0 - mu1)
        if between > best_var:
            best_var = between
            best_thr = t

    if best_var < 0:
        # Konstantna slika: nijedan prag ne razdvaja dvije klase.
        return 127
    # best_thr je zadnji bin klase 0 (pikseli <= best_thr). Buduci da binarize
    # koristi strogo (gray < thr), vracamo best_thr + 1 da prag lezi izmedju
    # dviju populacija (npr. modovi 30 i 220 -> prag 31, a ne 30).
    return int(min(best_thr + 1, 255))


def rasterize_input(
    raw_bytes: bytes,
    filename: str,
    page: int = 0,
    dpi_cap: int = 200,
    max_side_px: int = 6000,
) -> "np.ndarray":
    """Rasterizira ulaz (PDF/slika) u sivu 2D numpy sliku.

    Ulaz su sirovi bajtovi i naziv datoteke; izlaz je 2D array intenziteta.
    """
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        return _rasterize_pdf(raw_bytes, page, dpi_cap, max_side_px)
    if name.endswith((".png", ".jpg", ".jpeg")):
        return _rasterize_image(raw_bytes, max_side_px)

    raise ValueError("Nepodrzan format datoteke: " + (filename or "?"))


def _rasterize_pdf(
    raw_bytes: bytes,
    page: int,
    dpi_cap: int,
    max_side_px: int,
) -> "np.ndarray":
    """Rasterizira jednu stranicu PDF-a u sivu 2D numpy sliku."""
    import fitz  # lazy import
    from PIL import Image

    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    try:
        n_pages = len(doc)
        if n_pages == 0:
            raise ValueError("PDF nema stranica")
        pg = page
        if pg < 0 or pg > n_pages - 1:
            clamped = max(0, min(pg, n_pages - 1))
            logger.warning(
                "Stranica %d izvan raspona [0, %d]; koristim %d",
                pg, n_pages - 1, clamped,
            )
            pg = clamped
        p = doc[pg]

        dpi = min(150, dpi_cap)

        rect = p.rect
        pt_max = max(rect.width, rect.height)
        px_max = pt_max * dpi / 72.0
        dpi_eff = dpi
        if px_max > max_side_px and px_max > 0:
            dpi_eff = dpi * max_side_px / px_max
            logger.warning(
                "Smanjujem DPI %d -> %.2f radi granice %d px",
                dpi, dpi_eff, max_side_px,
            )

        pm = p.get_pixmap(dpi=int(round(dpi_eff)) or 1)

        if pm.n >= 3:
            mode = "RGB" if pm.n == 3 else "RGBA"
        else:
            mode = "L"
        img = Image.frombytes(mode, (pm.width, pm.height), pm.samples)
        img = img.convert("L")

        if img.width > max_side_px or img.height > max_side_px:
            img.thumbnail((max_side_px, max_side_px))

        arr = np.asarray(img, dtype=np.uint8)
        return arr
    finally:
        doc.close()


def _rasterize_image(raw_bytes: bytes, max_side_px: int) -> "np.ndarray":
    """Ucitava rastersku sliku i vraca sivu 2D numpy sliku."""
    from PIL import Image  # lazy import

    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("L")
    if img.width > max_side_px or img.height > max_side_px:
        img.thumbnail((max_side_px, max_side_px))
    arr = np.asarray(img, dtype=np.uint8)
    return arr


def binarize(gray: "np.ndarray", threshold: Optional[int] = None) -> "np.ndarray":
    """Pretvara sivu sliku u binarnu masku pragom (None -> Otsu).

    Ulaz je 2D siva slika; izlaz je 2D bool maska gdje True oznacava TAMNI
    piksel (crtez), tj. (gray < thr). Ako je threshold None koristi se Otsu.
    """
    arr = np.asarray(gray)
    if threshold is None:
        thr = _otsu_threshold(arr)
    else:
        thr = int(threshold)
    mask = arr < thr
    return np.asarray(mask, dtype=bool)


def denoise(binary: "np.ndarray", iters: int = 1) -> "np.ndarray":
    """Uklanja sitni sum iz binarne maske u zadanom broju iteracija.

    Ulaz i izlaz su binarne maske iste dimenzije.
    """
    from scipy import ndimage
    b = np.asarray(binary, dtype=bool)
    if iters <= 0:
        return b.copy()
    # 8-susjedstvo: opening uklanja izolirane piksele, closing popuni male rupe.
    structure = np.ones((3, 3), dtype=bool)
    op = ndimage.binary_opening(b, structure=structure, iterations=iters)
    cl = ndimage.binary_closing(op, structure=structure, iterations=iters)
    return np.asarray(cl, dtype=bool)


def _runs_in_row(mask_row: "np.ndarray"):
    """Vraca listu (start, end) indeksa neprekinutih True nizova u 1D bool nizu.

    end je inkluzivni indeks zadnjeg True u nizu. Koristi run-length pristup
    preko np.diff na prosirenom (padded) nizu da nadje pocetke i krajeve.
    """
    row = np.asarray(mask_row, dtype=bool)
    if row.size == 0 or not row.any():
        return []
    # Prosiri s False na oba kraja pa gledaj prijelaze.
    padded = np.concatenate(([False], row, [False]))
    d = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(d == 1)          # indeks prvog True (u koord. row)
    ends = np.flatnonzero(d == -1) - 1       # indeks zadnjeg True (inkluzivno)
    return list(zip(starts.tolist(), ends.tolist()))


def detect_line_segments(
    binary: "np.ndarray",
    min_len_px: int = 60,
    angle_tol_deg: float = 5.0,
) -> List[Segment]:
    """Detektira ravne linijske segmente iz binarne maske.

    Ulaz je binarna maska; izlaz je lista segmenata (par tocaka u pikselima).

    Ortogonalni run-length pristup: trazi neprekinute nizove tamnih (True)
    piksela po recima (horizontalne linije) i po stupcima (vertikalne linije).
    Konvencija: x = stupac, y = redak; segment je ((x0, y0), (x1, y1)).

    Parametar angle_tol_deg u ovoj ortogonalnoj verziji koristi se samo
    konceptualno: detektiraju se iskljucivo linije pod 0 (H) i 90 (V) stupnjeva.
    Kose linije se za sada ne detektiraju.
    """
    b = np.asarray(binary, dtype=bool)
    if b.ndim != 2 or b.size == 0 or not b.any():
        return []

    n_rows, n_cols = b.shape
    segments = []  # type: List[Segment]

    # HORIZONTALNE linije: za svaki redak y nadji nizove po stupcima.
    for y in range(n_rows):
        for (x0, x1) in _runs_in_row(b[y, :]):
            if (x1 - x0 + 1) >= min_len_px:
                segments.append(((int(x0), int(y)), (int(x1), int(y))))

    # VERTIKALNE linije: za svaki stupac x nadji nizove po recima.
    for x in range(n_cols):
        for (y0, y1) in _runs_in_row(b[:, x]):
            if (y1 - y0 + 1) >= min_len_px:
                segments.append(((int(x), int(y0)), (int(x), int(y1))))

    return segments


def merge_collinear(
    segments: List[Segment],
    max_gap_px: int = 12,
    angle_tol_deg: float = 5.0,
) -> List[Segment]:
    """Spaja kolinearne segmente unutar dopustene praznine i kutne tolerancije.

    Ulaz i izlaz su liste segmenata; izlaz sadrzi manje, dulje segmente.

    Fokus je na ORTOGONALNIM segmentima (H: y0==y1, V: x0==x1) jer to
    detect_line_segments iskljucivo proizvodi. Algoritam:
      - Segmenti se razvrstaju na horizontalne, vertikalne i ostale (kose).
      - HORIZONTALNI se grupiraju po istom y (isti pravac), sortiraju po x te
        se lancano spajaju: dva poredana intervala [lo, hi] i [nlo, nhi] spoje
        se ako je praznina (nlo - hi) <= max_gap_px u [lo, max(hi, nhi)].
      - VERTIKALNI analogno: grupiranje po istom x, sortiranje po y, spajanje
        ako je (nlo - hi) <= max_gap_px.
      - KOSI segmenti (ni H ni V) prosljedjuju se nepromijenjeni u izlaz.

    Parametar angle_tol_deg se prihvaca radi buduce tolerancije po pravcu; u
    ovoj MVP verziji grupiranje je po tocnom y (H) odnosno x (V) jer su ulazni
    segmenti egzaktno ortogonalni. Prazan ulaz vraca praznu listu.
    """
    if not segments:
        return []

    horizontals = []  # type: List[Segment]
    verticals = []    # type: List[Segment]
    others = []       # type: List[Segment]
    for seg in segments:
        (x0, y0), (x1, y1) = seg
        if y0 == y1:
            horizontals.append(seg)
        elif x0 == x1:
            verticals.append(seg)
        else:
            others.append(seg)

    result = []  # type: List[Segment]

    # HORIZONTALNI: grupiraj po y, sortiraj po x, lancano spoji uz max_gap_px.
    hgroups = {}  # type: Dict[float, List[Tuple[float, float]]]
    for seg in horizontals:
        (x0, y0), (x1, _y1) = seg
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        hgroups.setdefault(y0, []).append((lo, hi))
    for y in sorted(hgroups):
        intervals = sorted(hgroups[y])
        cur_lo, cur_hi = intervals[0]
        for lo, hi in intervals[1:]:
            if lo - cur_hi <= max_gap_px:
                if hi > cur_hi:
                    cur_hi = hi
            else:
                result.append(((cur_lo, y), (cur_hi, y)))
                cur_lo, cur_hi = lo, hi
        result.append(((cur_lo, y), (cur_hi, y)))

    # VERTIKALNI: grupiraj po x, sortiraj po y, lancano spoji uz max_gap_px.
    vgroups = {}  # type: Dict[float, List[Tuple[float, float]]]
    for seg in verticals:
        (x0, y0), (_x1, y1) = seg
        lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
        vgroups.setdefault(x0, []).append((lo, hi))
    for x in sorted(vgroups):
        intervals = sorted(vgroups[x])
        cur_lo, cur_hi = intervals[0]
        for lo, hi in intervals[1:]:
            if lo - cur_hi <= max_gap_px:
                if hi > cur_hi:
                    cur_hi = hi
            else:
                result.append(((x, cur_lo), (x, cur_hi)))
                cur_lo, cur_hi = lo, hi
        result.append(((x, cur_lo), (x, cur_hi)))

    # KOSI segmenti ostaju nepromijenjeni.
    result.extend(others)
    return result


def reduce_noise(
    segments: List[Segment],
    min_len_px: int = 60,
    dense_parallel_thresh: int = 8,
    dense_window_px: int = 24,
) -> List[Segment]:
    """Uklanja kratke i guste paralelne segmente koji predstavljaju sum.

    Ulaz i izlaz su liste segmenata; izlaz je procisceni skup (zadatak 7).

    Dva filtra, kalibrirana iz spike-a na stvarnom skeniranom nacrtu:

    1. Filtar kratkih segmenata: uklanja segmente cija je euklidska duljina
       (hypot(dx, dy) + 1, +1 jer su krajnje tocke inkluzivne u px) manja od
       min_len_px. Kratki segmenti uglavnom dolaze od kota, brojeva i sitnog
       suma na skenu.

    2. Filtar gustih paralelnih nizova (stubiste / srafura): preostali
       ortogonalni segmenti grupiraju se po orijentaciji. Za HORIZONTALNE se
       klizni prozor visine dense_window_px pomice po y; ako u prozor padne
       >= dense_parallel_thresh segmenata koji se uz to X-preklapaju s baznim
       segmentom prozora, cijeli taj gusti snop se uklanja. Za VERTIKALNE
       analogno po x-pojasu uz Y-preklapanje. Kosi segmenti se ne diraju ovim
       filtrom.

    Filtar je namjerno konzervativan: default dense_parallel_thresh=8 znaci da
    tek 8+ bliskih paralelnih segmenata (unutar uskih dense_window_px=24 px)
    pada kao sum, dok par-nekoliko normalnih paralelnih zidova prezivi. Prazan
    ulaz vraca praznu listu.
    """
    if not segments:
        return []

    def _seg_len(seg):
        (x0, y0), (x1, y1) = seg
        return hypot(x1 - x0, y1 - y0) + 1.0

    # Filtar 1: ukloni prekratke segmente.
    long_segs = [s for s in segments if _seg_len(s) >= min_len_px]
    if not long_segs:
        return []

    def _x_overlap(a, b):
        (ax0, _ay0), (ax1, _ay1) = a
        (bx0, _by0), (bx1, _by1) = b
        alo, ahi = (ax0, ax1) if ax0 <= ax1 else (ax1, ax0)
        blo, bhi = (bx0, bx1) if bx0 <= bx1 else (bx1, bx0)
        return min(ahi, bhi) >= max(alo, blo)

    def _y_overlap(a, b):
        (_ax0, ay0), (_ax1, ay1) = a
        (_bx0, by0), (_bx1, by1) = b
        alo, ahi = (ay0, ay1) if ay0 <= ay1 else (ay1, ay0)
        blo, bhi = (by0, by1) if by0 <= by1 else (by1, by0)
        return min(ahi, bhi) >= max(alo, blo)

    horizontals = []  # type: List[Segment]
    verticals = []    # type: List[Segment]
    for s in long_segs:
        (x0, y0), (x1, y1) = s
        if y0 == y1:
            horizontals.append(s)
        elif x0 == x1:
            verticals.append(s)

    dense_ids = set()

    def _mark_dense(group, pos_key, overlap_fn):
        # Sortiraj po poziciji okomitoj na orijentaciju (y za H, x za V) pa
        # klizni prozor visine dense_window_px trazi guste snopove.
        order = sorted(range(len(group)), key=lambda i: pos_key(group[i]))
        n = len(order)
        for a in range(n):
            base = group[order[a]]
            base_pos = pos_key(base)
            overlapping = []
            b = a
            while b < n and pos_key(group[order[b]]) - base_pos <= dense_window_px:
                cand = group[order[b]]
                if overlap_fn(base, cand):
                    overlapping.append(order[b])
                b += 1
            if len(overlapping) >= dense_parallel_thresh:
                for j in overlapping:
                    dense_ids.add(id(group[j]))

    # Filtar 2: guste paralelne nizove ukloni (H po y-pojasu, V po x-pojasu).
    _mark_dense(horizontals, lambda s: min(s[0][1], s[1][1]), _x_overlap)
    _mark_dense(verticals, lambda s: min(s[0][0], s[1][0]), _y_overlap)

    return [s for s in long_segs if id(s) not in dense_ids]


def segments_to_dxf(
    segments: List[Segment],
    px_to_unit: float = 1.0,
    layer: str = "VEKTOR_ZID",
    img_height_px: Optional[int] = None,
) -> bytes:
    """Zapisuje segmente kao DXF LINE entitete i vraca DXF sadrzaj kao bajtove.

    Ulaz je lista segmenata u pikselima; izlaz su bajtovi DXF datoteke.

    Pikselski Y raste prema DOLJE (ishodiste gore-lijevo), a CAD Y prema
    GORE. Zato se radi Y-flip: y_cad = (H - y_px) * px_to_unit, gdje je
    H = img_height_px ako je zadan, inace max y u segmentima (fallback).
    X se samo skalira: x_cad = x_px * px_to_unit. Prazan ulaz vraca valjan
    (prazan) DXF s definiranim slojem.
    """
    import ezdxf  # lazy import

    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()

    # Dodaj sloj ako jos ne postoji (dupli add baca DXFTableEntryError).
    if not doc.layers.has_entry(layer):
        doc.layers.add(name=layer)

    # Odredi visinu H za Y-flip. Ako img_height_px nije zadan, uzmi max y
    # iz segmenata kao fallback (relativni obrat); prazan ulaz -> H = 0.
    if img_height_px is not None:
        H = float(img_height_px)
    elif segments:
        H = float(max(max(y0, y1) for ((_x0, y0), (_x1, y1)) in segments))
    else:
        H = 0.0

    for (x0, y0), (x1, y1) in segments:
        p0 = (x0 * px_to_unit, (H - y0) * px_to_unit)
        p1 = (x1 * px_to_unit, (H - y1) * px_to_unit)
        msp.add_line(p0, p1, dxfattribs={"layer": layer})

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def _make_overlay(gray: "np.ndarray", segments: List[Segment]) -> bytes:
    """Crta detektirane segmente preko sive slike i vraca PNG bajtove.

    Sivu sliku (mode L) pretvara u RGB pa preko nje crvenom bojom (width 2)
    iscrtava svaki segment radi vizualne provjere. Rezultat se serijalizira u
    PNG i vraca kao bajtovi.
    """
    from PIL import Image, ImageDraw

    base = Image.fromarray(np.asarray(gray, dtype=np.uint8), mode="L").convert("RGB")
    draw = ImageDraw.Draw(base)
    for (x0, y0), (x1, y1) in segments:
        draw.line([(x0, y0), (x1, y1)], fill=(255, 0, 0), width=2)
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    return buf.getvalue()


def vectorize_floorplan(
    raw_bytes: bytes,
    filename: str,
    params: Optional[Params] = None,
) -> Dict[str, Any]:
    """Orkestrira cijeli tok vektorizacije od ulaza do rezultata.

    Ulaz su sirovi bajtovi i naziv; izlaz je rjecnik s DXF-om i metapodacima.

    Redoslijed koraka:
      1. rasterize_input -> siva 2D slika (gray)
      2. binarize -> binarna maska tamnih piksela (binary)
      3. denoise -> ocisceni binary (clean)
      4. detect_line_segments na clean; FALLBACK: ako denoise (3x3 opening iz
         zadatka 4) pojede pretanke linije pa clean nema detekcija, ponovno se
         detektira na neociscenom binary. Time orkestracija ostaje robusna i za
         tanke zidove koje bi morfoloski opening inace uklonio.
      5. merge_collinear -> spoj kolinearnih segmenata
      6. reduce_noise -> uklanjanje kratkih i gustih paralelnih segmenata
      7. segments_to_dxf -> DXF bajtovi (uz Y-flip po visini slike)
      8. _make_overlay -> PNG s iscrtanim segmentima radi vizualne kontrole
    """
    if params is None:
        params = Params()

    # Rezultat uvijek sadrzi ove kljuceve. Novi: "ok" (bool) i "warning"
    # (Optional[str]). Kod losih ulaza modul se NE rusi nego vraca dict s
    # ok=False i porukom u warning; kod uspjeha bez linija ok=True uz prijedlog.
    def _empty_result(ok, warning):
        return {
            "gray": None,
            "binary": None,
            "segments": [],
            "dxf_bytes": segments_to_dxf(
                [], params.px_to_unit, params.layer_name
            ),
            "overlay_png": None,
            "n_segments": 0,
            "ok": ok,
            "warning": warning,
        }

    # Prazan ulaz: nema podataka -> ne bacaj, vrati prazan valjan rezultat.
    if raw_bytes is None or len(raw_bytes) == 0:
        return _empty_result(False, "Prazan ulaz (nema podataka).")

    # Rasterizacija moze baciti (nepodrzan format, ostecen PDF, PIL/fitz
    # greska). Uhvati i vrati ok=False s porukom; NE propagiraj iznimku.
    try:
        gray = rasterize_input(
            raw_bytes,
            filename,
            page=0,
            dpi_cap=params.dpi_cap,
            max_side_px=params.max_side_px,
        )
    except Exception as e:  # noqa: BLE001 - namjerno siroko radi robusnosti
        return _empty_result(False, "Greska pri obradi ulaza: " + str(e))

    binary = binarize(gray, params.threshold)
    clean = denoise(binary, params.denoise_iters)

    raw_segments = detect_line_segments(
        clean, params.min_len_px, params.angle_tol_deg
    )
    if not raw_segments:
        # Fallback: denoise je vjerojatno pojeo pretanke linije -> koristi binary.
        raw_segments = detect_line_segments(
            binary, params.min_len_px, params.angle_tol_deg
        )

    merged = merge_collinear(raw_segments, params.max_gap_px, params.angle_tol_deg)
    segments = reduce_noise(merged, params.min_len_px, dense_parallel_thresh=8)

    H = gray.shape[0]
    dxf_bytes = segments_to_dxf(
        segments, params.px_to_unit, params.layer_name, img_height_px=H
    )
    # gray je uvijek validan ovdje; overlay bez linija prikazuje samo original.
    overlay_png = _make_overlay(gray, segments)

    if not segments:
        # Obrada je uspjela ali nijedna linija nije nadjena: ok=True uz prijedlog.
        warning = (
            "Nije pronadjena nijedna linija. Predlazemo: smanjite min_len_px, "
            "promijenite prag (threshold) ili povecajte DPI."
        )
    else:
        warning = None

    return {
        "gray": gray,
        "binary": clean,
        "segments": segments,
        "dxf_bytes": dxf_bytes,
        "overlay_png": overlay_png,
        "n_segments": len(segments),
        "ok": True,
        "warning": warning,
    }
