"""Auswertung der Kreuzvalidierung: Tabellen, gepaarte Vergleiche, verschachtelte Platt-Kalibrierung, Zuverlässigkeit.

Aufruf: python3 -I auswertung.py --design A [--primaer-S 3]
Liest  $PAIEC_WORK/modell/cv_<design>/saetze_f*.parquet
Schreibt cv_<design>/auswertung.json, zuverlaessigkeit.csv, paar_alc.parquet

Kalibrierung (verschachtelt): je Falte f werden Platt-Parameter (A, B) je Budget-Stufe auf den Sätzen ALLER ANDEREN
Falten (primäres S) gefittet — Kriterium Brier: Summe (sigma(A logit q + B) - R)^2 über Paare — und auf Falte f
angewandt (Prädiktor "hier_kalibriert"). Ins Paket gehen sie nur, wenn die kreuzangepasste Fassung den Brier der
Stufe senkt (Vorbau-Regel). Die Paket-Parameter werden auf allen Falten gefittet.
v2.0-core (K4f): zusätzlich verschachtelte STUFENWAHL je Falte (stufenwahl_verschachtelt) und Paketregel
„Stufe nur, wenn in v1-Gesamtwahl UND in jeder Falten-Wahl" (KERN-DIFF.md §0); Phase 2 liest die Falten-Wahl.
"""
import argparse
import json
import os
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrik  # noqa: E402
from inferenz import stufe  # noqa: E402

SCRATCH = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))


def _lg(q):
    q = np.clip(q, 1e-6, 1 - 1e-6)
    return np.log(q / (1 - q))


def fit_platt(q, R):
    x = _lg(q)

    def f(ab):
        p = 1 / (1 + np.exp(-(ab[0] * x + ab[1])))
        return float(np.mean((p - R) ** 2))
    res = minimize(f, [1.0, 0.0], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-10})
    return [float(res.x[0]), float(res.x[1])]


def wende_platt(q, st, platt):
    out = q.copy()
    for s, ab in platt.items():
        m = st == s
        out[m] = 1 / (1 + np.exp(-(ab[0] * _lg(q[m]) + ab[1])))
    return np.clip(out, 1e-4, 1 - 1e-4)


def lade(design):
    d = SCRATCH / f"cv_{design}"
    teile = sorted(d.glob("saetze_f*.parquet"))
    if not teile:
        raise SystemExit("keine Sätze")
    df = pd.concat([pd.read_parquet(t) for t in teile], ignore_index=True)
    df["stufe"] = [stufe(int(n)) for n in df.n_eigen]
    return d, df, len(teile)


def stufenwahl_verschachtelt(h, primaer_S, falten):
    """v2.0-core (K4f, REVIEW SOLL S1): Platt-STUFENWAHL verschachtelt. Je äußerer Falte f: innere Leave-one-fold-out-
    Platt auf den anderen Falten (Parameter aus den übrigen, angewandt auf die innere Testfalte); Stufe behalten, wenn
    der innere kreuzangepasste Brier der Stufe den unkalibrierten um > 1e-6 unterschreitet (Schwelle wie v1).
    -> {f: [stufen]}, {f: {stufe: {"hier":..., "hier_kalibriert":...}}}"""
    h = h[h.S == primaer_S]
    wahl, detail = {}, {}
    for f in falten:
        innen = [g for g in falten if g != f]
        teile = []
        for g in innen:
            tr = h[h.falte.isin([x for x in innen if x != g])]
            platt = {int(s): fit_platt(gg.q.values, gg.R.values) for s, gg in tr.groupby("stufe")}
            te = h[h.falte == g]
            teile.append(pd.DataFrame({"stufe": te.stufe.values, "R": te.R.values, "q": te.q.values,
                                       "q_kal": wende_platt(te.q.values, te.stufe.values, platt)}))
        x = pd.concat(teile, ignore_index=True)
        roh = ((x.q - x.R) ** 2 + x.R * (1 - x.R)).groupby(x.stufe).mean()
        kal = ((x.q_kal - x.R) ** 2 + x.R * (1 - x.R)).groupby(x.stufe).mean()
        wahl[int(f)] = sorted(int(s) for s in roh.index if kal[s] < roh[s] - 1e-6)
        detail[int(f)] = {int(s): {"hier": float(roh[s]), "hier_kalibriert": float(kal[s])} for s in roh.index}
    return wahl, detail


def kalibriere_verschachtelt(df, primaer_S):
    h = df[df.praediktor == "hier"]
    neu = []
    platt_je_falte = {}
    for f in sorted(df.falte.unique()):
        tr = h[(h.falte != f) & (h.S == primaer_S)]
        platt = {int(s): fit_platt(g.q.values, g.R.values) for s, g in tr.groupby("stufe")}
        platt_je_falte[int(f)] = platt
        te = h[h.falte == f].copy()
        te["q"] = wende_platt(te.q.values, te.stufe.values, platt)
        te["praediktor"] = "hier_kalibriert"
        neu.append(te)
    h_all = h[h.S == primaer_S]
    platt_paket = {int(s): fit_platt(g.q.values, g.R.values) for s, g in h_all.groupby("stufe")}
    return pd.concat([df] + neu, ignore_index=True), platt_je_falte, platt_paket


def paar_alc(df):
    """brier: itemgenau aus dem Simulator, falls vorhanden; für die kalibrierten Phase-1-Sätze paarkonstant."""
    paarb = (df.q - df.R) ** 2 + df.R * (1 - df.R)
    br = df["brier"].where(df["brier"].notna(), paarb) if "brier" in df.columns else paarb
    if "brier" in df.columns:
        br = br.where(df.praediktor != "hier_kalibriert", paarb)
    df = df.assign(brier=br, absf=(df.q - df.R).abs())
    df["wb"] = df.budget.map(GEW) * df.brier
    df["we"] = df.budget.map(GEW) * df.absf
    keys = ["S", "praediktor", "b_code", "s_code"]
    g = df.groupby(keys + ["saat"]).agg(alc=("wb", "sum"), ece=("we", "sum")).reset_index()
    pa = g.groupby(keys).agg(alc=("alc", "mean"), ece=("ece", "mean")).reset_index()
    extra = df.groupby(keys).agg(bekannt=("bekannt", "first"), kalt=("kalt", "first"),
                                 falte=("falte", "first")).reset_index()
    pb = df.groupby(keys + ["budget"]).brier.mean().unstack("budget")
    pb.columns = [f"B{c}" for c in pb.columns]
    return pa.merge(extra, on=keys).merge(pb.reset_index(), on=keys)


def tabelle(pa, maske=None):
    x = pa if maske is None else pa[maske]
    out = {}
    for (S, pr), g in x.groupby(["S", "praediktor"]):
        bb = g.groupby("b_code").alc.mean()
        out.setdefault(str(S), {})[pr] = {
            "alc_paare": round(float(g.alc.mean()), 5), "alc_benchmark_balanciert": round(float(bb.mean()), 5),
            "ece_paare": round(float(g.ece.mean()), 5),
            "brier_je_budget": {c: round(float(g[c].mean()), 5) for c in g.columns if c.startswith("B")},
            "n_paare": int(len(g)), "n_benchmarks": int(g.b_code.nunique())}
    return out


def vergleich(pa, S, modell, referenz, maske=None, balanciert=False):
    x = pa if maske is None else pa[maske]
    x = x[x.S == S]
    a = x[x.praediktor == modell].set_index(["b_code", "s_code"]).alc
    b = x[x.praediktor == referenz].set_index(["b_code", "s_code"]).alc
    j = pd.concat([a, b], axis=1, keys=["m", "r"]).dropna()
    d = (j.m - j.r)
    if balanciert:
        d = d.groupby(level=0).mean()
        cl = list(d.index)
    else:
        cl = [i[0] for i in d.index]
    out = metrik.cluster_vergleich(d.tolist(), cl)
    out.update({"modell": modell, "referenz": referenz, "S": str(S), "gewichtung": "benchmark" if balanciert else "paar"})
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in out.items()}


def zuverlaessigkeit(df, S, praediktoren, budgets=(0, 1, 7, 31), bins=10):
    zeilen = []
    x = df[(df.S == S) & df.praediktor.isin(praediktoren) & df.budget.isin(budgets)]
    for (pr, B), g in x.groupby(["praediktor", "budget"]):
        k = np.minimum((g.q.values * bins).astype(int), bins - 1)
        for b in range(bins):
            m = k == b
            if m.sum():
                zeilen.append({"praediktor": pr, "budget": int(B), "bin": b, "n": int(m.sum()),
                               "q_mittel": float(g.q.values[m].mean()), "R_mittel": float(g.R.values[m].mean())})
    return pd.DataFrame(zeilen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="A")
    ap.add_argument("--primaer-S", default="S3")
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--design-logik", default="", choices=["", "A", "B"],
                    help="P4: --design ist nur der Ordnersuffix (cv_<design>); Design-B-Logik (kalt) hier wählen")
    a = ap.parse_args()
    a.design_logik = a.design_logik or (a.design if a.design in ("A", "B") else "A")
    d, df, n_f = lade(a.design)
    S0 = a.primaer_S
    if a.phase == 1:
        df, platt_falten, platt_paket = kalibriere_verschachtelt(df, S0)
        modelle = ("hier", "hier_kalibriert")
        refs = ("beta_binomial", "empirischer_mittelwert", "konstant_0.5", "hier_ohne_subjekt", "hier")
    else:
        platt_falten, platt_paket = {}, {}
        modelle = ("hier_item", "hier_kal")
        refs = ("beta_binomial", "empirischer_mittelwert", "konstant_0.5", "hier_kal", "hier_item_t05",
                "hier_item_t2")
    pa = paar_alc(df)
    pa.to_parquet(d / "paar_alc.parquet", index=False)
    vgl = []
    for ref in refs:
        for mod in modelle:
            if mod == ref:
                continue
            for S in sorted(pa.S.unique()):
                vgl.append(vergleich(pa, S, mod, ref))
            vgl.append(vergleich(pa, S0, mod, ref, balanciert=True))
    if a.phase == 1:
        vgl.append(vergleich(pa, S0, "hier", "hier_ohne_steigung"))
        for S in sorted(pa.S.unique()):
            vgl.append(vergleich(pa, S, "beta_binomial", "empirischer_mittelwert"))
    # Kalibrierungsgewinn je Stufe (kreuzangepasst)
    stufen_gewinn, platt_fuer_paket, stufenwahl = {}, {}, {}
    if a.phase == 1:
        h = df[(df.S == S0) & df.praediktor.isin(["hier", "hier_kalibriert"])]
        h = h.assign(brier=(h.q - h.R) ** 2 + h.R * (1 - h.R))
        st = h.pivot_table(index="stufe", columns="praediktor", values="brier", aggfunc="mean")
        stufen_gewinn = {int(s): {"hier": float(r["hier"]), "hier_kalibriert": float(r["hier_kalibriert"]),
                                  "senkt": bool(r["hier_kalibriert"] < r["hier"] - 1e-6)} for s, r in st.iterrows()}
        platt_fuer_paket = {s: platt_paket[s] for s, v in stufen_gewinn.items() if v["senkt"] and s in platt_paket}
        # v2.0-core: verschachtelte Stufenwahl je Falte + Paketregel (Schnitt über Falten; KERN-DIFF.md §0)
        stufen_je_falte, stufen_detail = stufenwahl_verschachtelt(df[df.praediktor == "hier"], S0,
                                                                   sorted(int(f) for f in df.falte.unique()))
        gesamt = sorted(platt_fuer_paket)
        schnitt = sorted(s for s in gesamt if all(s in w for w in stufen_je_falte.values()))
        mehrheit = sorted(s for s in range(64) if sum(s in w for w in stufen_je_falte.values()) * 2 > len(stufen_je_falte))
        stufenwahl = {"verschachtelt_je_falte": {str(f): w for f, w in stufen_je_falte.items()},
                      "detail_je_falte": {str(f): {str(s): v for s, v in d.items()} for f, d in stufen_detail.items()},
                      "gesamt_v1_regel": gesamt, "paket_schnittregel": schnitt, "mehrheit_je_stufe": mehrheit,
                      "abweichung_je_falte": {str(f): sorted(set(w) ^ set(gesamt)) for f, w in stufen_je_falte.items()},
                      "paket_gleich_v1": schnitt == gesamt}
        if not stufenwahl["paket_gleich_v1"]:
            platt_fuer_paket = {s: platt_paket[s] for s in schnitt}
    erg = {"design": a.design, "falten_gelesen": n_f, "primaer_S": S0,
           "tabelle_alle": tabelle(pa), "tabelle_bekannt": tabelle(pa, pa.bekannt),
           "tabelle_unbekannt": tabelle(pa, ~pa.bekannt), "vergleiche": vgl,
           "kalibrierung_stufen": stufen_gewinn, "platt_paket": platt_fuer_paket, "platt_alle_stufen": platt_paket,
           "platt_stufenwahl_verschachtelt": stufenwahl,
           "platt_je_falte": {str(f): {str(k): v for k, v in pl.items()} for f, pl in platt_falten.items()}}
    if a.design_logik == "B":
        erg["tabelle_kalt"] = tabelle(pa, pa.kalt)
        erg["vergleiche_kalt"] = [vergleich(pa, S0, "hier", r, maske=pa.kalt) for r in
                                  ("beta_binomial", "empirischer_mittelwert", "hier_ohne_subjekt")]
    (d / "auswertung.json").write_text(json.dumps(erg, indent=1, ensure_ascii=False))
    zuverlaessigkeit(df, S0, ["hier", "hier_kalibriert", "hier_kal", "beta_binomial", "empirischer_mittelwert"]
                     ).to_csv(d / "zuverlaessigkeit.csv", index=False)
    t = erg["tabelle_alle"][S0]
    for pr in sorted(t, key=lambda k: t[k]["alc_paare"]):
        v = t[pr]
        print(f"{pr:24s} ALC {v['alc_paare']:.4f} (bal {v['alc_benchmark_balanciert']:.4f})  "
              + " ".join(f"{k}={x:.4f}" for k, x in v["brier_je_budget"].items()) + f"  n={v['n_paare']}")
    for v in vgl:
        if v["S"] == S0 or v["referenz"] in ("beta_binomial", "hier_kal"):
            print(f"{v['modell']} vs {v['referenz']} S={v['S']} {v['gewichtung']}: mittel {v.get('mittel')} "
                  f"SE {v.get('se')} -> {v['urteil']}")
    print("Kalibrierung je Stufe:", {s: (round(v["hier"], 4), round(v["hier_kalibriert"], 4)) for s, v in
                                     stufen_gewinn.items()})
    if stufenwahl:
        print("Platt-Stufenwahl verschachtelt je Falte:", stufenwahl["verschachtelt_je_falte"])
        print("gesamt (v1-Regel):", stufenwahl["gesamt_v1_regel"], "Paket (Schnittregel):",
              stufenwahl["paket_schnittregel"], "gleich v1:", stufenwahl["paket_gleich_v1"])


if __name__ == "__main__":
    main()
