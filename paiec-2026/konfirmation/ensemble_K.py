"""ensemble_K.py — H5 (Prereg v2 §4): konvexe Mischung, Logit-Stacking, NPEB auf den Konfirmations-Sätzen.

Abgeleitet aus v2-plan/d-ensemble/ensemble.py (2026-10-20 19:08Z, dort nur gelesen); identische Schätzer:
  (a) mix_hk_bb  = w·hier_kal + (1−w)·beta_binomial, w je (Regime, Stufe, Falte) Brier-minimal aus den anderen 9 Falten
  (b) stack_hk_bb = σ(a·logit hier_kal + b·logit BB + c), Nelder-Mead, je (Regime, Stufe, Falte) aus den anderen 9 Falten
  (c) q_np       = NPEB-Posterior-Mittel mit benchmark-balanciertem Gitter-Prior der Trainings-Benchmarks (Falte ≠ f),
                   2 % Glättung; eigene Labels (k, n) exakt aus q_BB zurückgerechnet
Abweichung zu ensemble.py (vorab, Laufzeit): nur Regime S1, S2, S3 (die H5-Regime) und nur die drei H5-Schätzer plus
mix_hk_np; stack_pool und R-Klassen entfallen. Urteile nach Prereg §2 (equivalent: |d| + 2 SE < 0.001; none better).
Aufruf: python3 -I ensemble_K.py --p1 cv_K_A --p2 cv_K_A2 --aus ergebnisse/ensemble_A.json
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402

STUFEN = (0, 1, 3, 7, 15, 31)
GRID = (np.arange(200) + 0.5) / 200.0
REGIME = ("S1", "S2", "S3")


def lg(q):
    q = np.clip(q, 1e-6, 1 - 1e-6)
    return np.log(q / (1 - q))


def sig(x):
    return 1 / (1 + np.exp(-x))


def lade(p1, p2):
    _, df, _ = ku.lade_saetze(p2)
    df = df[df.S.isin(REGIME)]
    ab = {}
    for f in range(10):
        st = json.loads((ku.WORK / p1 / f"state_f{f}.json").read_text())
        ab[f] = (st["baselines"]["beta_alpha"], st["baselines"]["beta_beta"])
    falten = {int(k): v for k, v in json.loads((ku.WORK / p1 / "falten.json").read_text()).items()}
    paare = pd.read_parquet(ku.WORK / "paare.parquet")
    return df, ab, falten, paare


def breit(df, ab):
    keys = ["saat", "S", "budget", "b_code", "s_code", "falte"]
    base = df[df.praediktor == "beta_binomial"][keys + ["q", "R", "N", "n_eigen"]].rename(columns={"q": "q_bb"})
    a = base.falte.map(lambda f: ab[f][0]).values
    b = base.falte.map(lambda f: ab[f][1]).values
    n = base.n_eigen.values.astype(float)
    k = base.q_bb.values * (a + b + n) - a
    kr = np.rint(k)
    if np.abs(k - kr).max() >= 1e-6:
        raise ku.KonfError(f"k-Rekonstruktion ungenau: {np.abs(k - kr).max()}")
    if not ((kr >= -1e-9).all() and (kr <= n + 1e-9).all()):
        raise ku.KonfError("k außerhalb [0, n]")
    base["k"] = kr.astype(int)
    for pr, col in (("hier_kal", "q_hk"), ("hier_item", "q_hi")):
        x = df[df.praediktor == pr][keys + ["q", "brier"]].rename(columns={"q": col, "brier": "brier_" + col[2:]})
        base = base.merge(x, on=keys, how="inner")
    if base.empty:
        raise ku.KonfError("keine gemeinsamen Zeilen")
    return base


def npeb_prior(paare, falten, f):
    tr = paare[paare.b_code.map(lambda b: falten.get(int(b), -1) != f)]
    w = 1.0 / tr.groupby("b_code").b_code.transform("size").values
    idx = np.minimum((tr.r.values * 200).astype(int), 199)
    g = np.bincount(idx, weights=w, minlength=200)
    g = g / g.sum()
    return 0.98 * g + 0.02 / 200


def npeb_q(g, k, n):
    lp, lq = np.log(GRID), np.log(1 - GRID)
    ll = k * lp + (n - k) * lq
    w = g * np.exp(ll - ll.max())
    return float((w * GRID).sum() / w.sum())


def fit_mix(qa, qb, R):
    d = qa - qb
    den = float((d * d).sum())
    if den <= 0:
        return 1.0
    return min(max(float(((R - qb) * d).sum() / den), 0.0), 1.0)


def fit_stack(qa, qb, R):
    xa, xb = lg(qa), lg(qb)

    def f(t):
        p = sig(t[0] * xa + t[1] * xb + t[2])
        return float(np.mean((p - R) ** 2))
    r = minimize(f, [1.0, 0.0, 0.0], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 4000})
    return [float(v) for v in r.x]


def paar_alc(base, cols):
    rows = []
    for c in cols:
        br = base["brier_" + c] if ("brier_" + c) in base.columns else (base[c] - base.R) ** 2 + base.R * (1 - base.R)
        t = base[["saat", "S", "budget", "b_code", "s_code"]].copy()
        t["wb"] = t.budget.map(ku.GEW) * br.values
        t["pr"] = c
        rows.append(t)
    t = pd.concat(rows, ignore_index=True)
    g = t.groupby(["S", "pr", "b_code", "s_code", "saat"]).wb.sum().reset_index()
    return g.groupby(["S", "pr", "b_code", "s_code"]).wb.mean().reset_index().rename(columns={"wb": "alc"})


def vergleich(pa, S, m, r):
    x = pa[pa.S == S]
    a = x[x.pr == m].set_index(["b_code", "s_code"]).alc
    b = x[x.pr == r].set_index(["b_code", "s_code"]).alc
    j = pd.concat([a, b], axis=1, keys=["m", "r"]).dropna()
    d = j.m - j.r
    v = ku.metrik.cluster_vergleich(d.tolist(), [i[0] for i in d.index])
    u = ku.urteil(v["mittel"], v["se"])
    u.update({"modell": m, "referenz": r, "S": S, "n_paare": v["n_paare"]})
    return ku.rund(u)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", required=True)
    ap.add_argument("--p2", required=True)
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    t0 = time.time()
    erg = {"zeit_utc": ku.jetzt(), "p1": a.p1, "p2": a.p2}
    rc = 0
    try:
        df, ab, falten, paare = lade(a.p1, a.p2)
        erg["saaten"] = ku.saaten(df)
        base = breit(df, ab)
        base["stufe"] = base.n_eigen.map(lambda n: max(s for s in STUFEN if n >= s))
        q_np = np.zeros(len(base))
        for f in range(10):
            g = npeb_prior(paare, falten, f)
            m = base.falte.values == f
            tab = {}
            for k, n in zip(base.k.values[m], base.n_eigen.values[m]):
                key = (int(k), int(n))
                if key not in tab:
                    tab[key] = npeb_q(g, *key)
            q_np[m] = [tab[(int(k), int(n))] for k, n in zip(base.k.values[m], base.n_eigen.values[m])]
        base["q_np"] = np.clip(q_np, 1e-4, 1 - 1e-4)
        for name, (ca, cb) in {"mix_hk_bb": ("q_hk", "q_bb"), "mix_hk_np": ("q_hk", "q_np")}.items():
            q = np.zeros(len(base))
            for S in REGIME:
                for st in STUFEN:
                    for f in range(10):
                        tr = base[(base.S == S) & (base.stufe == st) & (base.falte != f)]
                        te = (base.S == S) & (base.stufe == st) & (base.falte == f)
                        if te.sum() == 0:
                            continue
                        w = fit_mix(tr[ca].values, tr[cb].values, tr.R.values) if len(tr) else 1.0
                        q[te.values] = w * base.loc[te, ca].values + (1 - w) * base.loc[te, cb].values
            base[name] = np.clip(q, 1e-4, 1 - 1e-4)
        gewichte = {}
        q = np.zeros(len(base))
        for S in REGIME:
            for st in STUFEN:
                for f in range(10):
                    tr = base[(base.S == S) & (base.stufe == st) & (base.falte != f)]
                    te = (base.S == S) & (base.stufe == st) & (base.falte == f)
                    if te.sum() == 0:
                        continue
                    t = fit_stack(tr.q_hk.values, tr.q_bb.values, tr.R.values)
                    gewichte.setdefault(S, {}).setdefault(str(st), []).append([round(v, 3) for v in t])
                    q[te.values] = sig(t[0] * lg(base.loc[te, "q_hk"].values) + t[1] * lg(base.loc[te, "q_bb"].values) + t[2])
        base["stack_hk_bb"] = np.clip(q, 1e-4, 1 - 1e-4)
        cols = ["q_bb", "q_hk", "q_hi", "q_np", "mix_hk_bb", "mix_hk_np", "stack_hk_bb"]
        pa = paar_alc(base, cols)
        erg["tabelle_alc"] = {S: row.dropna().round(5).to_dict() for S, row in pa.groupby(["S", "pr"]).alc.mean().unstack("pr").iterrows()}
        h5 = {}
        for S in REGIME:
            h5[S] = {"a_mix_hk_bb_minus_hk": vergleich(pa, S, "mix_hk_bb", "q_hk"),
                     "b_stack_hk_bb_minus_hk": vergleich(pa, S, "stack_hk_bb", "q_hk"),
                     "c_npeb_minus_bb": vergleich(pa, S, "q_np", "q_bb"),
                     "zusatz_mix_hk_np_minus_hk": vergleich(pa, S, "mix_hk_np", "q_hk")}
        neun = [h5[S][k] for S in REGIME for k in ("a_mix_hk_bb_minus_hk", "b_stack_hk_bb_minus_hk", "c_npeb_minus_bb")]
        n_eq = sum(v["verdict"] == "equivalent" for v in neun)
        n_better = sum(v["better"] for v in neun)
        h5["n_equivalent_von_9"] = n_eq
        h5["n_better_von_9"] = n_better
        h5["regel"] = "9/9 equivalent und keiner better (better auch unterhalb der Marge zählt als better)"
        h5["verdict"] = "passed" if (n_eq == 9 and n_better == 0) else "failed"
        erg["H5"] = h5
        erg["stack_gewichte"] = gewichte
        erg["dauer_s"] = round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001
        erg["fehler"] = f"{type(e).__name__}: {e}"
        erg["traceback"] = traceback.format_exc()
        erg.setdefault("H5", {"verdict": "not_evaluated", "grund": erg["fehler"]})
        rc = 2
    ku.schreibe_json(a.aus, erg)
    h = erg["H5"]
    print("H5:", h.get("verdict"), "equivalent", h.get("n_equivalent_von_9"), "better", h.get("n_better_von_9"))
    for S in REGIME:
        if S in h:
            print(S, {k: (v["verdict"], v["d"], v["se"]) for k, v in h[S].items()})
    if rc:
        print("FEHLER:", erg.get("fehler"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
