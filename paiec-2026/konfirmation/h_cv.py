"""h_cv.py — Hypothesen H1, H3, H4, H8 aus den CV-Sätzen (Prereg v2 §4), Urteile per Regel §2.

Aufruf: python3 -I h_cv.py --p1 cv_K_A --p2 cv_K_A2 --design A --aus ergebnisse/h_cv_A.json
        (Design B: --p1 cv_K_B --p2 cv_K_B2 --design B)
Phase-1-Satz liefert hier / hier_ohne_subjekt (H4); Phase-2-Satz liefert hier_item / beta_binomial (H1, H3, H8).
Fail-closed: jede fehlende Eingabe -> Ausnahme, Rückgabecode 2; Hypothese im JSON dann 'not_evaluated'.
"""
import argparse
import sys
import traceback

import numpy as np
import pandas as pd

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402

H3_REGIME = ("S1", "S2", "S3")
H8_KLASSEN = [(0, 0, "0"), (1, 2, "1-2"), (3, 5, "3-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, 50, "21-50"),
              (51, 100, "51-100"), (101, 10 ** 9, ">100")]


def h1(pa, design):
    """ALC(hier_item) − ALC(beta_binomial), Paare gleich gewichtet, Mittel über Saaten, SE cluster über Benchmarks."""
    regime = ["S1", "S2", "S3", "S30"] if design == "A" else ["S1", "S3"]
    out = {}
    for S in regime:
        if not ((pa.S == S) & (pa.praediktor == "hier_item")).any():
            out[S] = {"verdict": "not_evaluated", "grund": f"Regime {S} fehlt"}
            continue
        v = ku.vergleich(pa, S, "hier_item", "beta_binomial")
        u = ku.urteil(v["mittel"], v["se"])
        u.update({"n_paare": v["n_paare"], "n_cluster": v["n_cluster"]})
        vb = ku.vergleich(pa, S, "hier_item", "beta_binomial", balanciert=True)
        u["benchmark_balanciert"] = {"d": vb["mittel"], "se": vb["se"]}
        # Nebenvergleich: gegen die Veranstalter-Baseline Empirical Mean
        ve = ku.vergleich(pa, S, "hier_item", "empirischer_mittelwert")
        u["gegen_empirischer_mittelwert"] = ku.urteil(ve["mittel"], ve["se"])
        out[S] = ku.rund(u)
    return out


def h4(pa, design):
    regime = ["S1", "S2", "S3"] if design == "A" else ["S1", "S3"]
    out = {}
    for S in regime:
        if not ((pa.S == S) & (pa.praediktor == "hier_ohne_subjekt")).any():
            out[S] = {"verdict": "not_evaluated", "grund": f"Regime {S} / hier_ohne_subjekt fehlt"}
            continue
        v = ku.vergleich(pa, S, "hier", "hier_ohne_subjekt")
        u = ku.urteil(v["mittel"], v["se"])
        u.update({"n_paare": v["n_paare"], "n_cluster": v["n_cluster"]})
        out[S] = ku.rund(u)
    return out


def h3(df):
    """Anteil des ALC-gewichteten Überschusses über R(1−R) bei B0–B3 (hier_item), Cluster-Bootstrap 2000, Saat 200.
    Überschuss je Budget = Mittel über Zeilen (Paar×Saat) von brier_B − R(1−R); brier itemgenau aus dem Simulator."""
    out = {}
    x = df[df.praediktor == "hier_item"].copy()
    x["exc"] = x.brier - x.R * (1 - x.R)
    for S in ("S1", "S2", "S3", "S30"):
        y = x[x.S == S]
        if y.empty:
            out[S] = {"verdict": "not_evaluated", "grund": "Regime fehlt"}
            continue
        # je Benchmark und Budget: Summe exc und Anzahl Zeilen
        g = y.groupby(["b_code", "budget"]).exc.agg(["sum", "size"]).unstack("budget")
        bs = list(g.index)
        summe = g["sum"].reindex(columns=list(ku.BUDGETS)).values  # (G, 6)
        n_z = g["size"].reindex(columns=list(ku.BUDGETS)).values
        if np.isnan(summe).any() or not (n_z == n_z[:, [0]]).all():
            out[S] = {"verdict": "not_evaluated", "grund": "Zeilenzahl je Budget uneinheitlich"}
            continue
        w = np.array([ku.GEW[b] for b in ku.BUDGETS])

        def anteil(idx):
            e = summe[idx].sum(0) / n_z[idx].sum(0)  # Mittel je Budget
            num = (w[:3] * e[:3]).sum()
            den = (w * e).sum()
            return num / den if den != 0 else float("nan")

        wert = anteil(np.arange(len(bs)))
        se, ki, _ = ku.cluster_bootstrap(anteil, bs, n_boot=2000, seed=200)
        exc_mittel = summe.sum(0) / n_z.sum(0)
        r = {"anteil": float(wert), "se_boot": se, "ci95_boot": ki, "n_benchmarks": len(bs), "n_zeilen": int(n_z.sum(0)[0]),
             "ueberschuss_je_budget": {str(b): float(v) for b, v in zip(ku.BUDGETS, exc_mittel)},
             "regel": "untere KI-Grenze > 0.70 (S1, S2, S3)"}
        if S in H3_REGIME:
            r["verdict"] = "passed" if ki[0] > 0.70 else "failed"
        else:
            r["verdict"] = "reported"
        out[S] = ku.rund(r)
    out["gesamt"] = ("passed" if all(out.get(S, {}).get("verdict") == "passed" for S in H3_REGIME)
                     else ("not_evaluated" if any(out.get(S, {}).get("verdict") == "not_evaluated" for S in H3_REGIME)
                           else "failed"))
    return out


def _klasse(c):
    for lo, hi, name in H8_KLASSEN:
        if lo <= c <= hi:
            return name
    return None


def h8(df):
    """Itemgewinn (itemgenauer Brier − paarkonstanter Brier) bei B=31 gegen Zahl der Bewertungsitems mit Fremdlabels.
    Zeilen = Paar×Saat (wie Discovery, h3_h8_kennlinie.log). Klassen mit >= 20 Paaren; WLS der Klassenmittel (Gewicht n);
    R² der Klassenmittel (gewichtet); Paar-Steigung (OLS über Zeilen) mit Cluster-Bootstrap 500, Saat 200."""
    out = {}
    x = df[(df.praediktor == "hier_item") & (df.budget == 31)].copy()
    x["ig"] = x.brier - ((x.q - x.R) ** 2 + x.R * (1 - x.R))
    x["cnt"] = x.n_items_angepasst.astype(float)
    x["k"] = x.cnt.map(_klasse)
    for S in ("S3", "S30", "kompakt10"):
        y = x[x.S == S]
        if y.empty:
            out[S] = {"verdict": "not_evaluated", "grund": "Regime fehlt"}
            continue
        kl = y.groupby("k").agg(n=("ig", "size"), ig=("ig", "mean"), cnt=("cnt", "mean"))
        kl = kl[kl.n >= 20]
        kl = kl.reindex([n for _, _, n in H8_KLASSEN if n in kl.index])
        r = {"klassen": {k: {"n": int(v.n), "itemgewinn_mittel": float(v.ig), "items_mittel": float(v.cnt)}
                         for k, v in kl.iterrows()}}
        if len(kl) >= 2:
            W = kl.n.values.astype(float)
            cx, cy = kl.cnt.values, kl.ig.values
            mx, my = np.average(cx, weights=W), np.average(cy, weights=W)
            b = np.sum(W * (cx - mx) * (cy - my)) / np.sum(W * (cx - mx) ** 2)
            a = my - b * mx
            pred = a + b * cx
            ss_res = np.sum(W * (cy - pred) ** 2)
            ss_tot = np.sum(W * (cy - my) ** 2)
            r["wls_steigung_je_item"] = float(b)
            r["r2_klassenmittel_gewichtet"] = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
            # ungewichtetes R² zur Kontrolle
            b0 = np.polyfit(cx, cy, 1)
            r["r2_klassenmittel_ungewichtet"] = float(1 - np.sum((cy - np.polyval(b0, cx)) ** 2) / np.sum((cy - cy.mean()) ** 2))
        # Paar-Steigung über Zeilen + Cluster-Bootstrap
        bs = sorted(y.b_code.unique())
        bi = {b: i for i, b in enumerate(bs)}
        gi = y.b_code.map(bi).values
        cnt, ig = y.cnt.values, y.ig.values
        # Momente je Benchmark für schnellen Bootstrap
        n_b = np.bincount(gi, minlength=len(bs)).astype(float)
        sx = np.bincount(gi, cnt, len(bs))
        sy = np.bincount(gi, ig, len(bs))
        sxx = np.bincount(gi, cnt * cnt, len(bs))
        sxy = np.bincount(gi, cnt * ig, len(bs))

        def steig(idx):
            n = n_b[idx].sum()
            mx_, my_ = sx[idx].sum() / n, sy[idx].sum() / n
            vx = sxx[idx].sum() / n - mx_ ** 2
            cxy = sxy[idx].sum() / n - mx_ * my_
            return cxy / vx if vx > 0 else float("nan")

        sl = steig(np.arange(len(bs)))
        se, ki, _ = ku.cluster_bootstrap(steig, bs, n_boot=500, seed=200)
        r.update({"paar_steigung_je_item": float(sl), "paar_steigung_se_boot": se, "paar_steigung_ci95_boot": ki,
                  "n_zeilen": int(len(y)), "n_benchmarks": len(bs)})
        if S == "S3":
            ok = (sl < 0) and (ki[1] < 0) and (r.get("r2_klassenmittel_gewichtet", 0) >= 0.8)
            r["regel"] = "(i) Steigung < 0, 95%-KI ohne 0, R² Klassenmittel >= 0.8"
            r["verdict"] = "passed" if ok else "failed"
        elif S == "S30":
            m = {k: v["itemgewinn_mittel"] for k, v in r["klassen"].items()}
            if all(k in m for k in ("21-50", "51-100", ">100")):
                ref = 1.3 * m["21-50"]
                ok = (m["51-100"] >= ref) and (m[">100"] >= ref)
                r["regel"] = "(ii) Sättigung: Mittel 51-100 und >100 nicht negativer als 1.3 × Mittel 21-50"
                r["schwelle_1_3x_21_50"] = float(ref)
                r["verdict"] = "passed" if ok else "failed"
            else:
                r["verdict"] = "not_evaluated"
                r["grund"] = "Klassen 21-50/51-100/>100 nicht alle mit >= 20 Paaren"
        else:
            r["verdict"] = "reported"
        out[S] = ku.rund(r)
    v3, v30 = out.get("S3", {}).get("verdict"), out.get("S30", {}).get("verdict")
    out["gesamt"] = ("passed" if v3 == "passed" and v30 == "passed"
                     else ("not_evaluated" if "not_evaluated" in (v3, v30) else "failed"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", required=True, help="Phase-1-Ordner unter PAIEC_WORK/modell (hier, hier_ohne_subjekt)")
    ap.add_argument("--p2", required=True, help="Phase-2-Ordner (hier_item, beta_binomial)")
    ap.add_argument("--design", required=True, choices=["A", "B"])
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    erg = {"zeit_utc": ku.jetzt(), "design": a.design, "p1": a.p1, "p2": a.p2, "H1": None, "H3": None, "H4": None, "H8": None}
    rc = 0
    try:
        d2, df2, st2 = ku.lade_saetze(a.p2)
        erg["saaten_p2"] = ku.saaten(df2)
        erg["status_p2"] = st2
        pa2 = ku.paar_alc(df2)
        erg["H1"] = h1(pa2, a.design)
        if a.design == "A":
            erg["H3"] = h3(df2)
            erg["H8"] = h8(df2)
        else:
            erg["H3"] = {"gesamt": "not_applicable"}
            erg["H8"] = {"gesamt": "not_applicable"}
    except Exception as e:  # noqa: BLE001
        erg["fehler_p2"] = f"{type(e).__name__}: {e}"
        erg["traceback_p2"] = traceback.format_exc()
        for h in ("H1", "H3", "H8"):
            erg[h] = erg[h] or {"gesamt": "not_evaluated", "grund": erg["fehler_p2"]}
        rc = 2
    try:
        d1, df1, st1 = ku.lade_saetze(a.p1)
        erg["saaten_p1"] = ku.saaten(df1)
        erg["status_p1"] = st1
        pa1 = ku.paar_alc(df1)
        erg["H4"] = h4(pa1, a.design)
    except Exception as e:  # noqa: BLE001
        erg["fehler_p1"] = f"{type(e).__name__}: {e}"
        erg["H4"] = {"gesamt": "not_evaluated", "grund": erg["fehler_p1"]}
        rc = 2
    ku.schreibe_json(a.aus, erg)
    for h in ("H1", "H4"):
        v = erg[h] or {}
        print(h, {k: (x.get("verdict"), x.get("d"), x.get("se")) for k, x in v.items() if isinstance(x, dict)})
    for h in ("H3", "H8"):
        v = erg[h] or {}
        print(h, v.get("gesamt"), {k: x.get("verdict") for k, x in v.items() if isinstance(x, dict)})
    return rc


if __name__ == "__main__":
    sys.exit(main())
