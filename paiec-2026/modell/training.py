"""Training des Paarebenen-Modells (numpy/scipy; läuft NICHT im Paket).

1. Paartabelle: je (Benchmark, Subjekt) mit >= MIN_ITEMS Items: empirischer Logit l = log((k+.5)/(n-k+.5)) und
   Messvarianz vl = 1/(Items * r(1-r)) (Items, nicht Antworten: Wiederholungen eines Items sind korreliert).
2. Einheiten: normalized_name (casefold) = übertragbare Einheit; leerer Name -> eigene Einheit je Subjekt (nur für die
   Schätzung von c_b, a_b; wird nicht exportiert).
3. ALS: l = c_b + a_b * theta_u + e, e ~ N(0, sigma_e2 + vl); theta ~ N(0, 1) (Skala), a_b ~ N(lam, 1) (Ridge).
4. Metadaten-Regression theta_u ~ Merkmale (merkmale.meta_merkmale), gewichteter Ridge, alpha per 5-fach-CV.
5. Hyperparameter der Testzeit (mu_c, tau_c2, lam, tau_l2, tau_v2, kappa, s2_unk) per Marginal-Likelihood auf
   INNEREN Benchmark-Falten: theta/Regression ohne den jeweiligen Benchmark geschätzt, dann
   l_b ~ N(mu_c 1 + lam m, tau_c2 11' + tau_l2 m m' + diag(s2_j + vl_j)), s2_j = tau_v2 + kappa V_j (bekannt) / s2_unk.
   Je Benchmark höchstens CAP_PAARE Paare (gleiche Kappung wie in der Auswertung).
"""
import json
import os
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merkmale import meta_merkmale, name_schluessel  # noqa: E402

MIN_ITEMS = 20
CAP_PAARE = 30
SCRATCH = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"


# ---------------------------------------------------------------- Daten
def baue_paartabelle(agg, sub):
    p = agg.groupby(["b_code", "s_code"], sort=False).agg(items=("i_code", "size"), n=("n", "sum"),
                                                          k=("k", "sum")).reset_index()
    s = sub.set_index("s_code")
    p["subject"] = [s.loc[c, ["normalized_name", "provider", "release_date", "access_date", "harness",
                              "harness_version", "reasoning_effort", "subject_features_extra"]].to_dict()
                    for c in p.s_code]
    p["konfig"] = s.loc[p.s_code, "konfig"].values
    nk = [name_schluessel(x) for x in p.subject]
    p["name"] = [x if x else "" for x in nk]
    p["einheit"] = [x if x else "s:%d" % c for x, c in zip(nk, p.s_code)]
    r = (p.k + 0.5) / (p.n + 1.0)
    p["l"] = np.log((p.k + 0.5) / (p.n - p.k + 0.5))
    p["vl"] = 1.0 / (p["items"] * r * (1 - r))
    p["rate"] = p.k / p.n
    return p


def kappe(p, cap=CAP_PAARE, seed=0, min_items=80):
    """Je Benchmark höchstens cap Paare mit >= min_items (fest per Saat) — wie in der Auswertung."""
    rng = np.random.default_rng(seed)
    teile = []
    for b, g in p[p["items"] >= min_items].groupby("b_code"):
        if len(g) > cap:
            g = g.iloc[np.sort(rng.choice(len(g), cap, replace=False))]
        teile.append(g)
    return pd.concat(teile) if teile else p.iloc[:0]


# ---------------------------------------------------------------- ALS
def als(p, iter_n=60, tau_a2=1.0):
    bi, b_codes = pd.factorize(p.b_code)
    ui, units = pd.factorize(p.einheit)
    l, vl = p.l.values, p.vl.values
    B, U = len(b_codes), len(units)
    c = np.bincount(bi, l, B) / np.bincount(bi, minlength=B)
    a = np.ones(B)
    th = np.zeros(U)
    sig2 = 1.0
    lam = 1.0
    namen = np.array([not str(u).startswith("s:") for u in units])
    n_b_je_u = np.bincount(ui, minlength=U)
    for _ in range(iter_n):
        w = 1.0 / (sig2 + vl)
        ab = a[bi]
        th = np.bincount(ui, w * ab * (l - c[bi]), U) / (np.bincount(ui, w * ab * ab, U) + 1.0)
        t = th[ui]
        S0, S1, S2 = (np.bincount(bi, w, B), np.bincount(bi, w * t, B), np.bincount(bi, w * t * t, B) + 1 / tau_a2)
        T0, T1 = np.bincount(bi, w * l, B), np.bincount(bi, w * t * l, B) + lam / tau_a2
        det = S0 * S2 - S1 * S1
        c = (S2 * T0 - S1 * T1) / det
        a = (S0 * T1 - S1 * T0) / det
        res = l - c[bi] - a[bi] * t
        je_b = np.bincount(bi, res * res - vl, B) / np.bincount(bi, minlength=B)
        sig2 = max(0.05, float(np.mean(je_b)))
        sel = namen & (n_b_je_u >= 2)
        sd = float(np.std(th[sel])) if sel.sum() > 5 else float(np.std(th))
        if sd > 0:
            th /= sd
            a *= sd
        lam = float(np.mean(a))
    w = 1.0 / (sig2 + vl)
    V = 1.0 / (np.bincount(ui, w * a[bi] ** 2, U) + 1.0)
    return {"c": pd.Series(c, index=b_codes), "a": pd.Series(a, index=b_codes),
            "theta": pd.Series(th, index=units), "V": pd.Series(V, index=units), "sig2": sig2, "lam": lam,
            "n_bench": pd.Series(n_b_je_u, index=units)}


# ---------------------------------------------------------------- Metadaten-Regression
def einheiten_merkmale(p):
    """Je Einheit: Merkmale des häufigsten Subjektdatensatzes, Hauptbenchmark."""
    out = {}
    for u, g in p.groupby("einheit", sort=False):
        out[u] = (meta_merkmale(g.subject.iloc[0]), int(g.b_code.mode().iloc[0]))
    return out


def fit_meta(fit, merk, min_count=3, seed=0):
    units = [u for u in fit["theta"].index if u in merk]
    zaehl = {}
    for u in units:
        for f in merk[u][0]:
            zaehl[f] = zaehl.get(f, 0) + 1
    vok = sorted(f for f, n in zaehl.items() if n >= min_count)
    fi = {f: j for j, f in enumerate(vok)}
    X = np.zeros((len(units), len(vok)))
    for r, u in enumerate(units):
        for f, v in merk[u][0].items():
            if f in fi:
                X[r, fi[f]] = v
    y = fit["theta"].loc[units].values
    hb = pd.Series([merk[u][1] for u in units])
    bal = 1.0 / np.sqrt(hb.map(hb.value_counts()).values)
    w = bal / (fit["V"].loc[units].values + 0.25)

    def ridge(Xt, yt, wt, alpha):
        mu = np.average(yt, weights=wt)
        xm = np.average(Xt, axis=0, weights=wt)
        Xc = Xt - xm
        A = Xc.T @ (Xc * wt[:, None]) + alpha * np.eye(Xt.shape[1])
        beta = np.linalg.solve(A, Xc.T @ (wt * (yt - mu)))
        return mu - xm @ beta, beta

    rng = np.random.default_rng(seed)
    falte = rng.integers(0, 5, len(units))
    best = None
    for alpha in (0.3, 1, 3, 10, 30, 100, 300):
        se = 0.0
        for f in range(5):
            tr, te = falte != f, falte == f
            b0, beta = ridge(X[tr], y[tr], w[tr], alpha)
            se += float(np.sum(w[te] * (y[te] - b0 - X[te] @ beta) ** 2))
        if best is None or se < best[0]:
            best = (se, alpha)
    b0, beta = ridge(X, y, w, best[1])
    return {"b0": float(b0), "w": {f: float(beta[j]) for f, j in fi.items() if abs(beta[j]) > 1e-9},
            "alpha": best[1], "n_einheiten": len(units), "n_merkmale": len(vok)}


def meta_vorhersage(meta, x):
    return meta["b0"] + sum(meta["w"].get(f, 0.0) * v for f, v in x.items())


# ---------------------------------------------------------------- Hyperparameter (Marginal-Likelihood)
def innere_bloecke(p, falten=5, seed=0):
    """-> Liste je Benchmark: (l, vl, m, V, bekannt) mit theta/Regression OHNE diesen Benchmark."""
    bs = np.array(sorted(p.b_code.unique()))
    rng = np.random.default_rng(seed)
    f_je_b = dict(zip(bs, rng.permutation(len(bs)) % falten))
    p = p.assign(falte=p.b_code.map(f_je_b))
    bloecke = []
    for f in range(falten):
        tr = p[p.falte != f]
        fit = als(tr)
        merk = einheiten_merkmale(tr)
        meta = fit_meta(fit, merk)
        te = kappe(p[p.falte == f], seed=seed)
        for b, g in te.groupby("b_code"):
            bek = g.einheit.isin(fit["theta"].index).values & (g.name.values != "")
            m = np.where(bek, g.einheit.map(fit["theta"]).fillna(0).values,
                         [meta_vorhersage(meta, meta_merkmale(s)) for s in g.subject])
            V = np.where(bek, g.einheit.map(fit["V"]).fillna(1).values, 0.0)
            bloecke.append((g.l.values, g.vl.values, m, V, bek))
    return bloecke


def _nll_block(l, d, m, mu_c, lam, tc2, tl2):
    """-log N(l; mu_c + lam m, tc2 11' + tl2 m m' + diag(d)) über Woodbury (Rang 2)."""
    r = l - mu_c - lam * m
    U = np.stack([np.ones_like(m), m], axis=1)
    Di = 1.0 / d
    Pinv = np.diag([1.0 / tc2, 1.0 / tl2])
    M = Pinv + U.T @ (U * Di[:, None])
    UtDr = U.T @ (Di * r)
    sign, logdetM = np.linalg.slogdet(M)
    quad = float(r @ (Di * r) - UtDr @ np.linalg.solve(M, UtDr))
    logdet = float(np.sum(np.log(d)) + logdetM + math.log(tc2) + math.log(tl2))
    return 0.5 * (quad + logdet + len(l) * math.log(2 * math.pi))


def fit_hyper(bloecke, null=False):
    """Benchmark-balanciert: jeder Block mit Gewicht 1/len (=> Mittel der Paar-NLL je Benchmark)."""
    def unpack(x):
        x = [x[0]] + [min(max(v, -12.0), 6.0) for v in x[1:]]  # exp() nie 0/inf (Absturz Falte 8, 2026-10-20)
        if null:
            mu_c, ltc, ls = x
            return mu_c, 0.0, math.exp(ltc), 1e-8, 0.0, 0.0, math.exp(ls)
        mu_c, lam, ltc, ltl, ltv, lk, ls = x
        return mu_c, lam, math.exp(ltc), math.exp(ltl), math.exp(ltv), math.exp(lk), math.exp(ls)

    def f(x):
        mu_c, lam, tc2, tl2, tv2, kap, s2u = unpack(x)
        tot = 0.0
        for l, vl, m, V, bek in bloecke:
            if null:
                mm = np.zeros_like(m)
                d = s2u + vl
            else:
                mm = m
                d = np.where(bek, tv2 + kap * V, s2u) + vl
            tot += _nll_block(l, d, mm, mu_c, lam, tc2, tl2) / len(l)
        return tot / len(bloecke)

    x0 = [0.0, math.log(1.5), math.log(1.0)] if null else [0.0, 1.0, math.log(1.5), math.log(0.2), math.log(1.0),
                                                          0.0, math.log(1.5)]
    res = minimize(f, x0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-7})
    res = minimize(f, res.x, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-9})
    mu_c, lam, tc2, tl2, tv2, kap, s2u = unpack(res.x)
    out = {"mu_c": mu_c, "lam": lam, "tau_c2": tc2, "tau_l2": tl2, "tau_v2": tv2, "kappa": kap, "s2_unk": s2u,
           "nll_je_paar": float(res.fun), "n_bloecke": len(bloecke)}
    if null:
        out.update({"lam": 0.0, "tau_l2": 1e-8, "tau_v2": s2u, "kappa": 0.0})
    return out


# ---------------------------------------------------------------- Item-Streuung
def rasch_eb(g, iter_n=60):
    """Empirical-Bayes-Rasch auf (s_code, i_code, n, k): d_i ~ N(0, tau2), EM-Update tau2 = mittel(d^2 + 1/h)."""
    si, s_codes = pd.factorize(g.s_code)
    ii, i_codes = pd.factorize(g.i_code)
    n, k = g.n.values.astype(float), g.k.values.astype(float)
    S, I = len(s_codes), len(i_codes)
    r = (np.bincount(si, k, S) + .5) / (np.bincount(si, n, S) + 1)
    beta, d, t2 = np.log(r / (1 - r)), np.zeros(I), 1.0
    for _ in range(iter_n):
        p = 1 / (1 + np.exp(-np.clip(beta[si] + d[ii], -30, 30)))
        hi = np.bincount(ii, n * p * (1 - p), I) + 1 / t2
        d = np.clip(d - (np.bincount(ii, n * p - k, I) + d / t2) / hi, -15, 15)
        p = 1 / (1 + np.exp(-np.clip(beta[si] + d[ii], -30, 30)))
        hs = np.bincount(si, n * p * (1 - p), S) + 1e-3
        beta = np.clip(beta - np.clip(np.bincount(si, n * p - k, S) / hs, -2, 2), -15, 15)
        m = d.mean()
        d, beta = d - m, beta + m
        t2 = max(1e-3, float(np.mean(d * d + 1 / hi)))
    return t2


def schaetze_tau_i2(agg, b_codes, seed=0, max_s=20, max_i=600):
    """Median der Item-Streuung über Trainingsbenchmarks mit >= 3 Subjekten (je >= 80 Items)."""
    rng = np.random.default_rng(seed)
    werte = []
    sub = agg[agg.b_code.isin(b_codes)]
    for b, g in sub.groupby("b_code"):
        cnt = g.groupby("s_code").size()
        subj = cnt[cnt >= 80].index.values
        if len(subj) < 3:
            continue
        subj = rng.choice(subj, min(max_s, len(subj)), replace=False)
        g = g[g.s_code.isin(subj)]
        items = g.i_code.unique()
        if len(items) > max_i:
            g = g[g.i_code.isin(rng.choice(items, max_i, replace=False))]
        t2 = rasch_eb(g)
        if np.isfinite(t2):
            werte.append(t2)
    return float(np.median(werte)) if werte else 0.0, len(werte)


# ---------------------------------------------------------------- Gesamt
def trainiere(p, seed=0, protokoll=print, agg=None):
    """p: Paartabelle (nur Trainingsbenchmarks); agg: Item-Aggregat (für tau_i2, optional).
    -> state (JSON-fähig) für inferenz.Modell."""
    fit = als(p)
    merk = einheiten_merkmale(p)
    meta = fit_meta(fit, merk)
    bloecke = innere_bloecke(p, seed=seed)
    hyp = fit_hyper(bloecke)
    hyp_null = fit_hyper(bloecke, null=True)
    if agg is not None:
        hyp["tau_i2"], n_ti = schaetze_tau_i2(agg, p.b_code.unique(), seed=seed)
        hyp_null["tau_i2"] = hyp["tau_i2"]
        hyp["tau_i2_benchmarks"] = n_ti
    namen = [u for u in fit["theta"].index if not str(u).startswith("s:")]
    theta = {u: [float(fit["theta"][u]), float(fit["V"][u])] for u in namen}
    protokoll(f"  trainiert: {p.b_code.nunique()} Benchmarks, {len(p)} Paare, {len(theta)} Namen, "
              f"sigma_e2={fit['sig2']:.3f}, meta alpha={meta['alpha']} ({meta['n_merkmale']} Merkmale), "
              f"hyp={ {k: round(v, 3) for k, v in hyp.items() if isinstance(v, float)} }")
    return {"version": 1, "theta": theta, "meta": {"b0": meta["b0"], "w": meta["w"]}, "hyp": hyp,
            "hyp_null": hyp_null, "als": {"sigma_e2": fit["sig2"], "lam": fit["lam"]},
            "meta_info": {k: meta[k] for k in ("alpha", "n_einheiten", "n_merkmale")}, "platt": {}, "clip": 1e-4}


def lade_paare(min_items=MIN_ITEMS):
    agg = pd.read_parquet(SCRATCH / "agg.parquet")
    sub = pd.read_parquet(SCRATCH / "subjekte.parquet")
    p = baue_paartabelle(agg, sub)
    return p[p["items"] >= min_items].reset_index(drop=True), agg


if __name__ == "__main__":
    import time
    t0 = time.time()
    p, _ = lade_paare()
    print(len(p), "Paare (>= %d Items)" % MIN_ITEMS, round(time.time() - t0, 1), "s")
    st = trainiere(p, agg=_)
    (SCRATCH / "state_alle.json").write_text(json.dumps(st))
    print("fertig", round(time.time() - t0, 1), "s")
