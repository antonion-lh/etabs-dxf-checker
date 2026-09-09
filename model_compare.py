"""
model_compare.py
----------------
Usporedba referentnog modela (rekonstruiranog iz DXF tlocrta preko
dxf_model.build_model_from_dxf) sa studentskim ETABS modelom (phase1_e2k.parse_e2k).

Cilj Faze B: profesor da studentima tlocrt kao referentni primjer; aplikacija iz
istog tlocrta gradi referentni ("ispravan") model, a zatim automatski uspoređuje
studentski E2K model s njime i prijavljuje odstupanja:
  - element nedostaje (student ga nije modelirao),
  - element je višak (student ima nešto što nije na tlocrtu),
  - kriva dimenzija presjeka,
  - pomak pozicije.

Pristup: referentni model iz tlocrta tretiramo kao "istinu" (df_dxf-oblik), a
studentski E2K kao "etabs" u postojećem phase3_validation.validate engineu koji
već radi story-aware greedy KDTree podudaranje. Time izbjegavamo dupliciranje
logike podudaranja.

Statusi (Status enum iz phase3_validation), interpretirani u kontekstu provjere:
  - MATCH             -> student ispravno modelirao element
  - SECTION_MISMATCH  -> element postoji ali kriva dimenzija presjeka
  - ETABS_ONLY        -> student ima element kojeg NEMA na referentnom tlocrtu (VIŠAK)
  - DXF_ONLY          -> referentni tlocrt ima element koji student NIJE modelirao (NEDOSTAJE)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from config import Config, DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Adapter: referentni model (dict) -> df_dxf-oblik tablica za validate()
# ---------------------------------------------------------------------------

# Kolone koje phase3_validation.validate ocekuje na df_dxf strani
_DXF_TABLE_COLUMNS = [
    "element_type", "centroid_x_m", "centroid_y_m",
    "dim1_mm", "dim2_mm", "floor_label", "layer",
]


def _rows_from_frame(df: pd.DataFrame, element_type: str) -> List[dict]:
    """Frame elementi (column/beam): pozicija iz x_start/y_start, dim iz width/height_mm."""
    rows = []
    if df is None or not hasattr(df, "empty") or df.empty:
        return rows
    for _, r in df.iterrows():
        cx = r.get("x_start")
        cy = r.get("y_start")
        # frame greda ima dvije tocke -> centar kao sredina
        if cx is not None and r.get("x_end") is not None:
            try:
                cx = (float(cx) + float(r.get("x_end"))) / 2.0
                cy = (float(cy) + float(r.get("y_end"))) / 2.0
            except (TypeError, ValueError):
                pass
        rows.append({
            "element_type": element_type,
            "centroid_x_m": _as_float(cx),
            "centroid_y_m": _as_float(cy),
            "dim1_mm": _as_float(r.get("width_mm")),
            "dim2_mm": _as_float(r.get("height_mm")),
            "floor_label": r.get("story", ""),
            "layer": r.get("layer", ""),
        })
    return rows


def _rows_from_area(df: pd.DataFrame, element_type: str) -> List[dict]:
    """Area elementi (wall/slab): pozicija iz centroid_x/centroid_y."""
    rows = []
    if df is None or not hasattr(df, "empty") or df.empty:
        return rows
    for _, r in df.iterrows():
        cx = r.get("centroid_x", r.get("x_start"))
        cy = r.get("centroid_y", r.get("y_start"))
        # zid moze imati thickness_mm kao dim1
        rows.append({
            "element_type": element_type,
            "centroid_x_m": _as_float(cx),
            "centroid_y_m": _as_float(cy),
            "dim1_mm": _as_float(r.get("thickness_mm")),
            "dim2_mm": None,
            "floor_label": r.get("story", ""),
            "layer": r.get("layer", ""),
        })
    return rows


def _as_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def ref_model_to_dxf_table(model: Dict[str, Any]) -> pd.DataFrame:
    """Pretvara referentni model (build_model_from_dxf) u df_dxf-oblik tablicu.

    Rezultat je kompatibilan s izlazom phase2_dxf.parse_dxf pa ga
    phase3_validation.validate moze koristiti bez izmjena.
    """
    if not isinstance(model, dict):
        return pd.DataFrame(columns=_DXF_TABLE_COLUMNS)

    rows: List[dict] = []
    rows += _rows_from_frame(model.get("columns"), "column")
    rows += _rows_from_frame(model.get("beams"), "beam")
    rows += _rows_from_area(model.get("walls"), "wall")
    rows += _rows_from_area(model.get("slabs"), "slab")

    if not rows:
        return pd.DataFrame(columns=_DXF_TABLE_COLUMNS)
    return pd.DataFrame(rows, columns=_DXF_TABLE_COLUMNS)


# ---------------------------------------------------------------------------
# Usporedba
# ---------------------------------------------------------------------------

def compare_models(
    student_e2k: Dict[str, pd.DataFrame],
    ref_model: Dict[str, Any],
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Uspoređuje studentski E2K model s referentnim modelom iz tlocrta.

    student_e2k : izlaz phase1_e2k.parse_e2k (dict DataFrame-ova po tipu)
    ref_model   : izlaz dxf_model.build_model_from_dxf (dict)

    Vraća df_res (kao phase3_validation.validate) gdje status znaci:
      MATCH=ispravno, SECTION_MISMATCH=kriva dimenzija,
      ETABS_ONLY=student ima visak, DXF_ONLY=student nije modelirao (nedostaje).
    """
    import phase3_validation as p3

    ref_df = ref_model_to_dxf_table(ref_model)
    return p3.validate(student_e2k, ref_df, cfg)


# ---------------------------------------------------------------------------
# Sazetak razlika (hrvatski)
# ---------------------------------------------------------------------------

def summarize_differences(df_res: pd.DataFrame) -> Dict[str, Any]:
    """Sažima rezultat usporedbe u brojače + hrvatske poruke po tipu elementa.

    Vraća dict:
      {
        "counts": {"match":N,"mismatch":N,"nedostaje":N,"visak":N,"ukupno":N},
        "by_type": {"column": {...}, ...},
        "messages": [str, ...],   # citljive poruke za korisnika
        "ok": bool,               # True ako nema odstupanja
      }
    """
    counts = {"match": 0, "mismatch": 0, "nedostaje": 0, "visak": 0, "ukupno": 0}
    by_type: Dict[str, Dict[str, int]] = {}
    messages: List[str] = []

    if df_res is None or not hasattr(df_res, "empty") or df_res.empty:
        return {"counts": counts, "by_type": by_type, "messages": [], "ok": True}

    # (jednina, množina) za hrvatsku gramatiku poruka
    _HR = {
        "column": ("stup", "stupova"), "beam": ("greda", "greda"),
        "wall": ("zid", "zidova"), "slab": ("ploča", "ploča"),
        "brace": ("spreg", "sprega"),
    }

    def _naziv(et, n):
        pair = _HR.get(et)
        if not pair:
            return et
        return pair[0] if n == 1 else pair[1]

    for _, r in df_res.iterrows():
        status = str(r.get("status", "")).upper()
        et = str(r.get("element_type", ""))
        bt = by_type.setdefault(et, {"match": 0, "mismatch": 0, "nedostaje": 0, "visak": 0})
        counts["ukupno"] += 1
        if "SECTION_MISMATCH" in status:
            counts["mismatch"] += 1
            bt["mismatch"] += 1
        elif "MATCH" in status:
            counts["match"] += 1
            bt["match"] += 1
        elif "DXF_ONLY" in status:
            counts["nedostaje"] += 1
            bt["nedostaje"] += 1
        elif "ETABS_ONLY" in status:
            counts["visak"] += 1
            bt["visak"] += 1

    for et, bt in sorted(by_type.items()):
        if bt["nedostaje"]:
            messages.append("Nedostaje %d %s (na tlocrtu, ali student nije modelirao)."
                            % (bt["nedostaje"], _naziv(et, bt["nedostaje"])))
        if bt["visak"]:
            messages.append("Višak %d %s (student modelirao, nema na tlocrtu)."
                            % (bt["visak"], _naziv(et, bt["visak"])))
        if bt["mismatch"]:
            messages.append("Kriva dimenzija na %d %s (presjek ne odgovara tlocrtu)."
                            % (bt["mismatch"], _naziv(et, bt["mismatch"])))

    ok = (counts["nedostaje"] == 0 and counts["visak"] == 0 and counts["mismatch"] == 0)
    if ok and counts["ukupno"] > 0:
        messages.append("Model se u potpunosti podudara s referentnim tlocrtom.")

    return {"counts": counts, "by_type": by_type, "messages": messages, "ok": ok}


# ---------------------------------------------------------------------------
# Automatska ocjena studentskog modela
# ---------------------------------------------------------------------------

def grade_comparison(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Iz sažetka razlika računa postotak točnosti i prijedlog ocjene (1-5).

    Bodovanje: referentni model ima N_ref = match + mismatch + nedostaje elemenata
    (elementi koje student TREBA imati). Točni su samo 'match'. Kazna i za višak
    (student modelirao nepostojeće) jer to je pogreška modeliranja.

    accuracy = match / (N_ref + visak)   (0..1)

    Ocjena (hrvatski sustav 1-5):
      >= 0.90 -> 5 (Izvrstan)
      >= 0.75 -> 4 (Vrlo dobar)
      >= 0.60 -> 3 (Dobar)
      >= 0.45 -> 2 (Dovoljan)
      inače   -> 1 (Nedovoljan)
    """
    counts = (summary or {}).get("counts", {}) or {}
    match = int(counts.get("match", 0))
    mismatch = int(counts.get("mismatch", 0))
    nedostaje = int(counts.get("nedostaje", 0))
    visak = int(counts.get("visak", 0))

    n_ref = match + mismatch + nedostaje
    denom = n_ref + visak
    if denom <= 0:
        # nema s čime usporediti -> neodređeno
        return {"accuracy": None, "grade": None, "grade_label": "Nije moguće ocijeniti",
                "n_reference": 0, "n_correct": 0}

    accuracy = match / denom

    if accuracy >= 0.90:
        grade, label = 5, "Izvrstan"
    elif accuracy >= 0.75:
        grade, label = 4, "Vrlo dobar"
    elif accuracy >= 0.60:
        grade, label = 3, "Dobar"
    elif accuracy >= 0.45:
        grade, label = 2, "Dovoljan"
    else:
        grade, label = 1, "Nedovoljan"

    return {
        "accuracy": round(accuracy, 4),
        "accuracy_pct": round(accuracy * 100, 1),
        "grade": grade,
        "grade_label": label,
        "n_reference": n_ref,
        "n_correct": match,
    }


# ---------------------------------------------------------------------------
# Izvještaj o usporedbi (HTML) — za profesora
# ---------------------------------------------------------------------------

def _esc(s) -> str:
    import html
    return html.escape(str(s if s is not None else ""))


def comparison_report_html(df_res, summary: Dict[str, Any],
                           grade: Optional[Dict[str, Any]] = None,
                           project_name: str = "Provjera modela prema tlocrtu") -> str:
    """Generira samostalni HTML izvještaj o usporedbi (bez vanjskih ovisnosti)."""
    from datetime import datetime

    if grade is None:
        grade = grade_comparison(summary)
    counts = (summary or {}).get("counts", {}) or {}

    grade_txt = ("%s (%s)" % (grade.get("grade"), grade.get("grade_label"))
                 if grade.get("grade") is not None else grade.get("grade_label", "—"))
    acc_txt = ("%.1f %%" % grade["accuracy_pct"]) if grade.get("accuracy_pct") is not None else "—"

    rows_html = ""
    if df_res is not None and hasattr(df_res, "empty") and not df_res.empty:
        cols = [c for c in ("element_type", "status", "etabs_name", "story", "notes")
                if c in df_res.columns]
        head = "".join("<th>%s</th>" % _esc(c) for c in cols)
        body = ""
        for _, r in df_res.iterrows():
            body += "<tr>" + "".join("<td>%s</td>" % _esc(r.get(c)) for c in cols) + "</tr>"
        rows_html = "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body)

    msgs = "".join("<li>%s</li>" % _esc(m) for m in (summary or {}).get("messages", []))

    return """<!DOCTYPE html><html lang="hr"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:Arial,sans-serif;margin:24px;color:#1e293b}}
h1{{font-size:20px}} h2{{font-size:15px;margin-top:24px}}
.cards{{display:flex;gap:12px;margin:16px 0}}
.card{{border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;min-width:110px}}
.card .n{{font-size:22px;font-weight:700}} .card .l{{font-size:12px;color:#64748b}}
.grade{{font-size:26px;font-weight:800;color:#0f766e}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px}}
th,td{{border:1px solid #e2e8f0;padding:5px 8px;text-align:left}}
th{{background:#f1f5f9}}
ul{{font-size:13px}}
.small{{color:#64748b;font-size:12px}}
</style></head><body>
<h1>{title}</h1>
<div class="small">Generirano: {ts}</div>
<h2>Ocjena studentskog modela</h2>
<div class="grade">{grade_txt} &nbsp;·&nbsp; točnost {acc_txt}</div>
<div class="small">Točno modelirano {n_correct} od {n_ref} referentnih elemenata.</div>
<div class="cards">
  <div class="card"><div class="n">{c_match}</div><div class="l">Podudarni</div></div>
  <div class="card"><div class="n">{c_ned}</div><div class="l">Nedostaje</div></div>
  <div class="card"><div class="n">{c_vis}</div><div class="l">Višak</div></div>
  <div class="card"><div class="n">{c_mis}</div><div class="l">Kriva dimenzija</div></div>
</div>
<h2>Sažetak razlika</h2>
<ul>{msgs}</ul>
<h2>Detaljna tablica</h2>
{rows}
</body></html>""".format(
        title=_esc(project_name), ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grade_txt=_esc(grade_txt), acc_txt=acc_txt,
        n_correct=grade.get("n_correct", 0), n_ref=grade.get("n_reference", 0),
        c_match=counts.get("match", 0), c_ned=counts.get("nedostaje", 0),
        c_vis=counts.get("visak", 0), c_mis=counts.get("mismatch", 0),
        msgs=msgs or "<li>Nema odstupanja.</li>", rows=rows_html or "<p>Nema podataka.</p>")


# ---------------------------------------------------------------------------
# Vizualni prikaz razlika na tlocrtu (Plotly)
# ---------------------------------------------------------------------------

# boje i hrvatski naziv po statusu
_STATUS_STYLE = {
    "MATCH": ("#16A34A", "Podudarno"),
    "SECTION_MISMATCH": ("#EAB308", "Kriva dimenzija"),
    "ETABS_ONLY": ("#EA580C", "Višak (samo u modelu)"),
    "DXF_ONLY": ("#DC2626", "Nedostaje (samo na tlocrtu)"),
}


def _status_key(status) -> str:
    s = str(status).upper()
    for k in ("SECTION_MISMATCH", "ETABS_ONLY", "DXF_ONLY", "MATCH"):
        if k in s:
            return k
    return "MATCH"


def _row_xy(row):
    """Koordinata elementa za prikaz: preferira postojecu stranu (student ili tlocrt)."""
    for kx, ky in (("etabs_x", "etabs_y"), ("dxf_x", "dxf_y")):
        x = row.get(kx)
        y = row.get(ky)
        try:
            if x is not None and y is not None:
                fx, fy = float(x), float(y)
                if fx == fx and fy == fy:  # ne-NaN
                    return fx, fy
        except (TypeError, ValueError):
            continue
    return None, None


def _beam_segments_from_ref(ref_model):
    """Indeks linijskih segmenata greda/zidova iz ref modela po zaokruženom centru.

    Vraća {(tip, round(cx,2), round(cy,2)): (x1,y1,x2,y2)} samo za elemente koji
    imaju stvarnu duljinu (x_start != x_end ili y_start != y_end).
    """
    idx = {}
    if not isinstance(ref_model, dict):
        return idx
    for key, et in (("beams", "beam"), ("walls", "wall")):
        df = ref_model.get(key)
        if df is None or not hasattr(df, "iterrows"):
            continue
        for _, r in df.iterrows():
            try:
                x1 = float(r.get("x_start")); y1 = float(r.get("y_start"))
                x2 = float(r.get("x_end")); y2 = float(r.get("y_end"))
            except (TypeError, ValueError):
                continue
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                continue  # nema duljine -> ostaje točka
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            idx[(et, round(cx, 2), round(cy, 2))] = (x1, y1, x2, y2)
    return idx


def compare_figure(df_res, ref_model=None):
    """Gradi Plotly figuru tlocrta s elementima obojanima po statusu usporedbe.

    Zeleno=podudarno, žuto=kriva dimenzija, narančasto=višak, crveno=nedostaje.
    Ako je zadan ref_model, linijske grede/zidovi (koji imaju stvarnu duljinu)
    iscrtavaju se kao linije; ostalo (stupovi/ploče) kao oblici-markeri.
    Vraća plotly.graph_objects.Figure (prazna figura ako nema podataka).
    """
    import plotly.graph_objects as go

    fig = go.Figure()
    if df_res is None or not hasattr(df_res, "empty") or df_res.empty:
        fig.update_layout(title="Nema podataka za prikaz")
        return fig

    # oblik markera po tipu elementa (boja nosi status, oblik nosi tip)
    type_symbol = {"column": "square", "beam": "diamond",
                   "wall": "x", "slab": "circle"}
    type_hr = {"column": "stup", "beam": "greda", "wall": "zid", "slab": "ploča"}
    seg_idx = _beam_segments_from_ref(ref_model)

    # grupiraj markere po (status, tip); linije crtamo zasebno da zadrže boju
    groups: Dict[tuple, Dict[str, list]] = {}
    line_added_legend = set()
    order = ("MATCH", "SECTION_MISMATCH", "ETABS_ONLY", "DXF_ONLY")

    for _, r in df_res.iterrows():
        key = _status_key(r.get("status"))
        et = str(r.get("element_type", ""))
        x, y = _row_xy(r)
        if x is None:
            continue
        seg = seg_idx.get((et, round(x, 2), round(y, 2))) if seg_idx else None
        if seg is not None:
            # linijski element (greda/zid s duljinom) -> linija u boji statusa
            color, status_name = _STATUS_STYLE.get(key, ("#64748b", key))
            legend_key = (key, et)
            show_legend = legend_key not in line_added_legend
            line_added_legend.add(legend_key)
            fig.add_trace(go.Scatter(
                x=[seg[0], seg[2]], y=[seg[1], seg[3]], mode="lines",
                name="%s — %s" % (status_name, type_hr.get(et, et)),
                legendgroup="%s-%s" % (key, et), showlegend=show_legend,
                line=dict(color=color, width=4),
                hovertemplate="%s %s<extra></extra>" % (type_hr.get(et, et),
                                                        r.get("etabs_name", "") or ""),
            ))
        else:
            g = groups.setdefault((key, et), {"x": [], "y": [], "text": []})
            g["x"].append(x)
            g["y"].append(y)
            label = "%s %s" % (type_hr.get(et, et), r.get("etabs_name", "") or "")
            g["text"].append(label.strip())

    for (key, et), g in sorted(groups.items(),
                               key=lambda kv: order.index(kv[0][0]) if kv[0][0] in order else 9):
        color, status_name = _STATUS_STYLE.get(key, ("#64748b", key))
        trace_name = "%s — %s" % (status_name, type_hr.get(et, et))
        fig.add_trace(go.Scatter(
            x=g["x"], y=g["y"], mode="markers", name=trace_name,
            marker=dict(size=12, color=color, symbol=type_symbol.get(et, "circle"),
                        line=dict(width=1, color="#334155")),
            text=g["text"], hovertemplate="%{text}<br>(%{x:.2f}, %{y:.2f})<extra></extra>",
        ))

    fig.update_layout(
        title="Usporedba modela s tlocrtom (boja = status, oblik = vrsta elementa)",
        xaxis_title="X (m)", yaxis_title="Y (m)",
        legend_title="Status — vrsta", height=560,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)  # jednako mjerilo osi
    return fig


def status_hr(status) -> str:
    """Pretvara Status enum / string u čitljiv hrvatski naziv za prikaz."""
    key = _status_key(status)
    names = {
        "MATCH": "Usklađeno",
        "SECTION_MISMATCH": "Razlika u presjeku",
        "ETABS_ONLY": "Samo u modelu (višak)",
        "DXF_ONLY": "Samo na tlocrtu (nedostaje)",
    }
    return names.get(key, str(status))


# ---------------------------------------------------------------------------
# Batch usporedba: vise studentskih modela protiv istog referentnog
# ---------------------------------------------------------------------------

def compare_batch(students, ref_model: Dict[str, Any],
                  cfg: Config = DEFAULT_CONFIG):
    """Uspoređuje više studentskih E2K modela protiv istog referentnog modela.

    students : lista (naziv, student_e2k_dict) parova.
    Vraća DataFrame s jednim redom po studentu: naziv, ocjena, ocjena_opis,
    tocnost_%, podudarni, nedostaje, visak, kriva_dimenzija.
    Model koji padne pri usporedbi dobiva red s greskom (ocjena None).
    """
    import pandas as pd

    rows = []
    for name, student in (students or []):
        try:
            df = compare_models(student, ref_model, cfg)
            summary = summarize_differences(df)
            grade = grade_comparison(summary)
            c = summary["counts"]
            rows.append({
                "student": name,
                "ocjena": grade.get("grade"),
                "ocjena_opis": grade.get("grade_label"),
                "tocnost_%": grade.get("accuracy_pct"),
                "podudarni": c.get("match", 0),
                "nedostaje": c.get("nedostaje", 0),
                "visak": c.get("visak", 0),
                "kriva_dimenzija": c.get("mismatch", 0),
            })
        except Exception as e:  # noqa: BLE001
            rows.append({"student": name, "ocjena": None,
                         "ocjena_opis": "Greška: %s" % e, "tocnost_%": None,
                         "podudarni": 0, "nedostaje": 0, "visak": 0,
                         "kriva_dimenzija": 0})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Usporedba rastera / osi (pomak grida)
# ---------------------------------------------------------------------------

def _axis_values(grid: Dict[str, Any], key: str) -> List[float]:
    """Izvlaci sortirane koordinate osi iz grid dicta (x_axes/y_axes ili raw)."""
    vals = []
    if not isinstance(grid, dict):
        return vals
    raw = grid.get(key)
    if raw:
        for a in raw:
            if isinstance(a, dict):
                v = a.get("coord", a.get("value", a.get("pos")))
            else:
                v = a
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
    return sorted(vals)


def compare_grids(ref_grid: Dict[str, Any], student_grid: Dict[str, Any],
                  tol: float = 0.10) -> Dict[str, Any]:
    """Usporedjuje rasterske osi dvaju modela i detektira sistematski pomak.

    Vraća dict: {n_ref_x, n_ref_y, n_student_x, n_student_y, shift_x, shift_y,
    aligned (bool), messages}. Pomak = medijan razlika poravnatih osi (po redu).
    aligned=True ako je broj osi jednak i pomak unutar tolerancije.
    """
    rx = _axis_values(ref_grid, "x_axes")
    ry = _axis_values(ref_grid, "y_axes")
    sx = _axis_values(student_grid, "x_axes")
    sy = _axis_values(student_grid, "y_axes")

    def _shift(a, b):
        n = min(len(a), len(b))
        if n == 0:
            return None
        diffs = sorted(b[i] - a[i] for i in range(n))
        return diffs[n // 2]  # medijan

    shift_x = _shift(rx, sx)
    shift_y = _shift(ry, sy)
    messages: List[str] = []
    aligned = True

    if len(rx) != len(sx) or len(ry) != len(sy):
        aligned = False
        messages.append("Broj osi se razlikuje (X: ref %d / student %d, "
                        "Y: ref %d / student %d)." % (len(rx), len(sx), len(ry), len(sy)))
    for axis, sh in (("X", shift_x), ("Y", shift_y)):
        if sh is not None and abs(sh) > tol:
            aligned = False
            messages.append("Sistematski pomak osi %s za %.3f m." % (axis, sh))
    if aligned and (rx or ry):
        messages.append("Raster osi se poklapa s referentnim.")

    return {
        "n_ref_x": len(rx), "n_ref_y": len(ry),
        "n_student_x": len(sx), "n_student_y": len(sy),
        "shift_x": shift_x, "shift_y": shift_y,
        "aligned": aligned, "messages": messages,
    }
