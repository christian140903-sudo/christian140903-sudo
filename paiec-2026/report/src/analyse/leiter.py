"""C.2/C.3 Orakel-Leiter bei B0, Varianzzerlegung, Orakel-Schwierigkeit je Budget, C.4 Akquise-Simulation.
Testpaare und Bewertungs-Split exakt wie die CV (training.kappe, simulator._paar). python3 -I.
Schreibt c-fehleranalyse/leiter.{json,md}.
"""
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import os
M = next(p / "modell" for p in Path(__file__).resolve().parents if (p / "modell" / "simulator.py").is_file())  # Code des Repos
sys.path.insert(0, str(M))
import simulator  # noqa: E402
import training  # noqa: E402

MOD = Path(os.environ["PAIEC_WORK"]) / "modell"  # lokale Datenbasis (README, Schritt 0)
OUT = Path(__file__).resolve().parent
BUD = [0, 1, 3, 7, 15, 31]
GEW = dict(zip(BUD, [0.1, 0.2, 0.2, 0.2, 0.2, 0.1]))
t0 = time.time()


def log(*a):
    print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)


def sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def brier_items(p, n, k):
    return float(np.sum(n * p * p - 2 * p * k + k) / n.sum())


def match_mean(d, n, ziel, it=30):
    """b mit sum(n sig(b+d))/sum(n) = ziel (Newton)."""
    ziel = min(max(ziel, 1e-3), 1 - 1e-3)
    b = math.log(ziel / (1 - ziel)) - float(np.average(d, weights=n))
    N = n.sum()
    for _ in range(it):
        p = sig(b + d)
        f = float(np.sum(n * p)) / N - ziel
        g = float(np.sum(n * p * (1 - p))) / N
        if g < 1e-12:
            break
        step = f / g
        b -= max(min(step, 2.0), -2.0)
        if abs(step) < 1e-9:
            break
    return b


# ---------------------------------------------------------------- Daten
p, agg = training.lade_paare()
agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
f_je_b = {int(k): v for k, v in json.loads((MOD / "cv_A/falten.json").read_text()).items()}
test_b = sorted(f_je_b)
testpaare = pd.concat([training.kappe(p[p.b_code.isin([b for b, x in f_je_b.items() if x == f])], seed=0)
                       for f in range(10)], ignore_index=True)  # je Falte wie kreuzvalidierung.falte()
log("Testpaare", len(testpaare), "Benchmarks", testpaare.b_code.nunique())
agg = agg[agg.b_code.isin(test_b)]
bc = agg.b_code.values
starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right"))) for b in np.unique(bc)}
# Item-Summen je Benchmark (alle Subjekte der Datenbank im Aggregat)
isum = agg.groupby(["b_code", "i_code"], sort=False).agg(K=("k", "sum"), N=("n", "sum"), S=("s_code", "size"))
log("Item-Summen", len(isum))
subjekte = defaultdict(dict)

# Honeste Fähigkeit je Falte (theta aus state_f) und In-Sample-ALS auf allen Paaren
theta_fold = {f: json.loads((MOD / f"cv_A/state_f{f}.json").read_text())["theta"] for f in range(10)}
hyp_all = json.loads((MOD / "state_alle.json").read_text())["hyp"]
fit = training.als(p)
units_named = fit["n_bench"][[not str(u).startswith("s:") for u in fit["n_bench"].index]]
multi = set(units_named[units_named >= 2].index)
log("ALS in-sample: Benchmarks", len(fit["c"]), "Einheiten", len(fit["theta"]), "Namen in >=2 Bm", len(multi),
    "sig2", round(fit["sig2"], 3), "lam", round(fit["lam"], 3))

# CV-Sätze für q (hier_kal paarkonstant, hier_item) S3
cv = pd.concat([pd.read_parquet(t) for t in sorted((MOD / "cv_REG2").glob("saetze_f*.parquet"))], ignore_index=True)
cv = cv[(cv.S == "S3") & cv.praediktor.isin(["hier_kal", "hier_item", "beta_binomial"])]
q_kal = cv[cv.praediktor == "hier_kal"].set_index(["saat", "b_code", "s_code", "budget"]).q.to_dict()
R_cv = cv[(cv.praediktor == "hier_kal") & (cv.budget == 0)].set_index(["saat", "b_code", "s_code"]).R.to_dict()

# ---------------------------------------------------------------- Je Paar
zeilen = []
akq = []
rng_a = np.random.default_rng(7)
for row in testpaare.itertuples(index=False):
    b, s = int(row.b_code), int(row.s_code)
    i0, i1 = starts[b]
    agg_b = agg.iloc[i0:i1]
    g = agg_b[agg_b.s_code == s]
    sumb = isum.loc[b]
    for seed in (0, 1, 2):
        pr = simulator._paar(g, row, subjekte, seed)
        bew_i, bew_n, bew_k = pr["bew_i"], pr["bew_n"], pr["bew_k"]
        R = pr["K"] / pr["N"]
        assert abs(R - R_cv[(seed, b, s)]) < 1e-9, (b, s, seed, R, R_cv[(seed, b, s)])
        # LOO-Schwierigkeit der Bewertungs-Items
        KI = sumb.K.reindex(bew_i).values.astype(float)
        NI = sumb.N.reindex(bew_i).values.astype(float)
        NI_o, KI_o = NI - bew_n, KI - bew_k
        hat = NI_o > 0
        d = np.zeros(len(bew_i))
        d[hat] = np.log((KI_o[hat] + 0.5) / (NI_o[hat] - KI_o[hat] + 0.5))
        if hat.any():
            d[hat] -= d[hat].mean()
        floor = R * (1 - R)
        trial_floor = brier_items(bew_k / bew_n, bew_n, bew_k)
        # Orakel Rate + LOO-Schwierigkeit
        bst = match_mean(d, bew_n, R)
        p_or = sig(bst + d)
        br_or = brier_items(p_or, bew_n, bew_k)
        item_expl = float(np.average((p_or - R) ** 2, weights=bew_n))
        z = {"b_code": b, "s_code": s, "seed": seed, "R": R, "floor": floor, "trial_floor": trial_floor,
             "N": float(pr["N"]), "items_bew": len(bew_i), "anteil_items_mit_loo": float(hat.mean()),
             "n_subj_bm": int(agg_b.s_code.nunique()), "br_orakel_rate_loo": br_or, "item_erklaert": item_expl,
             "falte": f_je_b[b], "name": row.name}
        # v1 (hier_kal q) + LOO-Schwierigkeit je Budget
        for B in BUD:
            q = q_kal[(seed, b, s, B)]
            bq = match_mean(d, bew_n, q)
            z[f"br_v1_loo_B{B}"] = brier_items(sig(bq + d), bew_n, bew_k)
            z[f"q_B{B}"] = q
        zeilen.append(z)
        # ---- Akquise-Simulation (nur Saat 0): bekannte d (LOO) auf Akquise-Items, echte Labels
        if seed == 0:
            n_all, k_all, ic_all = g.n.values.astype(float), g.k.values.astype(float), g.i_code.values
            rng = np.random.default_rng(simulator._saat(seed, "paar", "", b, s))
            perm = rng.permutation(len(g))
            halb = len(g) // 2
            akq_idx = perm[:halb]
            KIa = sumb.K.reindex(ic_all[akq_idx]).values.astype(float)
            NIa = sumb.N.reindex(ic_all[akq_idx]).values.astype(float)
            NIa_o, KIa_o = NIa - n_all[akq_idx], KIa - k_all[akq_idx]
            hata = NIa_o > 0
            da = np.zeros(len(akq_idx))
            da[hata] = np.log((KIa_o[hata] + 0.5) / (NIa_o[hata] - KIa_o[hata] + 0.5))
            if hata.any():
                da[hata] -= da[hata].mean()
            pa = k_all[akq_idx] / n_all[akq_idx]
            # Labels: zufällig, wie Simulator (eine Antwort je Item), feste Zufallsfolge je Item
            u = rng_a.random(len(akq_idx))
            y_all = (u < pa).astype(float)
            mu0, v0 = hyp_all["mu_c"], hyp_all["tau_c2"] + hyp_all["s2_unk"]

            def post(idx):
                """Laplace-Posterior von b bei bekannten d: Prior N(mu0, v0)."""
                bb = mu0
                for _ in range(40):
                    pp = sig(bb + da[idx])
                    gr = (bb - mu0) / v0 + np.sum(pp - y_all[idx])
                    hs = 1 / v0 + np.sum(pp * (1 - pp))
                    st = gr / hs
                    bb -= max(min(st, 2.0), -2.0)
                    if abs(st) < 1e-9:
                        break
                pp = sig(bb + da[idx])
                return bb, 1.0 / (1 / v0 + np.sum(pp * (1 - pp)))

            def vorhersage(bb, var, mit_d=True):
                eta = (bb + d) if mit_d else np.full(len(d), bb)
                return sig(eta / math.sqrt(1 + math.pi * var / 8))

            res_a = {"b_code": b, "s_code": s}
            # zufällige Reihenfolge = ersten B der Permutation (wie Simulator); adaptiv = Item mit d nächst -b_hat
            ordnung_rand = np.arange(len(akq_idx))
            gew = []
            bb, var = mu0, v0
            frei = np.ones(len(akq_idx), bool)
            for B in BUD:
                if B > 0:
                    while len(gew) < B and frei.any():
                        j = int(np.argmin(np.where(frei, np.abs(da + bb), np.inf)))
                        frei[j] = False
                        gew.append(j)
                        bb, var = post(np.array(gew))
                    bb_r, var_r = post(ordnung_rand[:B])
                else:
                    bb_r, var_r = mu0, v0
                res_a[f"rand_d_B{B}"] = brier_items(vorhersage(bb_r, var_r, True), bew_n, bew_k)
                res_a[f"rand_od_B{B}"] = brier_items(vorhersage(bb_r, var_r, False), bew_n, bew_k)
                res_a[f"adapt_d_B{B}"] = brier_items(vorhersage(bb, var, True), bew_n, bew_k)
            akq.append(res_a)
    if len(zeilen) % 300 == 0:
        log("Paare", len(zeilen) // 3)

Z = pd.DataFrame(zeilen)
A = pd.DataFrame(akq)
Z.to_parquet(OUT / "leiter_paare.parquet", index=False)
A.to_parquet(OUT / "akquise_paare.parquet", index=False)
log("fertig Paare", len(Z))

# ---------------------------------------------------------------- Leiter B0 (Saat 0..2, Mittel)
md, res = [], {}
Z0 = Z.copy()
# Prädiktoren bei B0
mu_c, lam = hyp_all["mu_c"], hyp_all["lam"]
th_all = fit["theta"]
c_b, a_b = fit["c"], fit["a"]
R_mean = Z0.R.mean()


def th_fold(r):
    th = theta_fold[r.falte]
    return th[r.name][0] if r.name and r.name in th else 0.0


def th_insample(r, nur_multi=True):
    u = r.name if r.name else "s:%d" % r.s_code
    if nur_multi and u not in multi:
        return 0.0
    return float(th_all.get(u, 0.0))


# Orakel Benchmark-Lage: Mittel der Rate r aller ANDEREN Paare (>= 80 Items) des Benchmarks aus paare (LOO), sonst globales Mittel
p80 = p[p["items"] >= 80]
bsum = p80.groupby("b_code").agg(sr=("rate", "sum"), n=("rate", "size"))
rate_sb = p80.set_index(["b_code", "s_code"]).rate.to_dict()


def q_loc(r):
    sr, n = bsum.loc[r.b_code, "sr"], bsum.loc[r.b_code, "n"]
    eig = rate_sb[(r.b_code, r.s_code)]
    return (sr - eig) / (n - 1) if n > 1 else R_mean


Z0["q_konst"] = 0.5
Z0["q_v1"] = Z0.q_B0
Z0["q_lage"] = Z0.apply(q_loc, axis=1)
Z0["q_faeh_fold"] = [sig(mu_c + lam * th_fold(r)) for r in Z0.itertuples(index=False)]
Z0["q_faeh_in"] = [sig(mu_c + lam * th_insample(r)) for r in Z0.itertuples(index=False)]
Z0["q_lage_faeh_fold"] = [sig(c_b[r.b_code] + a_b[r.b_code] * th_fold(r)) for r in Z0.itertuples(index=False)]
Z0["q_lage_faeh_in"] = [sig(c_b[r.b_code] + a_b[r.b_code] * th_insample(r)) for r in Z0.itertuples(index=False)]
Z0["q_als_voll"] = [sig(c_b[r.b_code] + a_b[r.b_code] * th_insample(r, nur_multi=False)) for r in Z0.itertuples(index=False)]
stufen = [("L0 konstant 0,5", "q_konst"), ("L1 v1 hier_item B0", "q_v1"),
          ("L2 Orakel Benchmark-Lage (LOO-Mittel der anderen Paare)", "q_lage"),
          ("L3a Fähigkeit, ehrlich (Falten-θ, Name) + μ_c", "q_faeh_fold"),
          ("L3b Fähigkeit in-sample (θ aus allen Bm, Namen in ≥2 Bm) + μ_c", "q_faeh_in"),
          ("L4 Orakel Lage+Steigung (c_b, a_b in-sample) + ehrliches θ", "q_lage_faeh_fold"),
          ("L5 Orakel Lage+Steigung + in-sample θ (Namen ≥2 Bm)", "q_lage_faeh_in"),
          ("L6 ALS voll in-sample (auch Einzel-Einheiten; enthält geschrumpftes Paarresiduum)", "q_als_voll")]
rows = []
for name, col in stufen:
    sq = ((Z0[col] - Z0.R) ** 2)
    rows.append({"Stufe": name, "Brier_B0": float((sq + Z0.floor).mean()), "(q-R)^2": float(sq.mean()),
                 "Aufloesung_R2": float(1 - sq.mean() / ((Z0.R - Z0.R.mean()) ** 2).mean()),
                 "bekannt (q-R)^2": float(sq[Z0.name != ""].mean()), "unbekannt (q-R)^2": float(sq[Z0.name == ""].mean())})
rows.append({"Stufe": "L7 Orakel Paarrate R", "Brier_B0": float(Z0.floor.mean()), "(q-R)^2": 0.0, "Aufloesung_R2": 1.0})
rows.append({"Stufe": "L8 Orakel Rate + LOO-Item-Schwierigkeit (Slope 1, mittelwert-angepasst)",
             "Brier_B0": float(Z0.br_orakel_rate_loo.mean())})
rows.append({"Stufe": "L9 Orakel Item-Wahrscheinlichkeit k/n (nur Wiederholungsrauschen)", "Brier_B0": float(Z0.trial_floor.mean())})
L = pd.DataFrame(rows)
md.append("\n### Orakel-Leiter bei Budget 0 (2 142 Testpaare x 3 Saaten, Bewertungs-Items)\n")
md.append(L.round(5).to_string(index=False))
res["leiter_B0"] = L.round(6).to_dict("records")
res["anteil_paare_name_leer"] = float((Z0.name == "").mean())
res["anteil_paare_name_multi"] = float(Z0.name.isin(multi).mean())

# ---------------------------------------------------------------- Varianzzerlegung
# Logit-Skala (ALS in-sample, alle 12 918 Paare)
pm = p.copy()
pm["c"] = pm.b_code.map(fit["c"])
pm["a"] = pm.b_code.map(fit["a"])
pm["th"] = pm.einheit.map(fit["theta"])
pm["fit"] = pm.c + pm.a * pm.th
pm["res"] = pm.l - pm.fit
named_multi = pm.einheit.isin(multi)
vz = {"var_l_gesamt": float(pm.l.var()), "var_c_b (zwischen Benchmarks, paargewichtet)": float(pm.c.var()),
      "var_a_theta (Namen in >=2 Bm, innerhalb Bm)": float((pm.a * pm.th)[named_multi].var()),
      "var_residuum_gesamt (inkl. Einzel-Einheiten als Residuum)": float((pm.l - pm.c)[~named_multi].var()),
      "sigma_e2_ALS": fit["sig2"], "mittel_messvarianz_vl": float(pm.vl.mean()),
      "hyp_state_alle": {k: hyp_all.get(k) for k in ("mu_c", "lam", "tau_c2", "tau_l2", "tau_v2", "kappa", "s2_unk", "tau_i2")}}
# benchmark-balanciert: Var(c_b) über Benchmarks, Var innerhalb je Benchmark gemittelt
vz["var_c_b_benchmarkbalanciert"] = float(fit["c"].var())
within = pm.groupby("b_code").apply(lambda g: float(g.l.var()) if len(g) > 1 else np.nan, include_groups=False)
vz["mittel_var_l_innerhalb_benchmark"] = float(within.mean())
expl = pm[named_multi].groupby("b_code").apply(
    lambda g: 1 - float(g.res.var() / g.l.var()) if len(g) > 2 and g.l.var() > 0 else np.nan, include_groups=False)
vz["R2_faehigkeit_innerhalb_benchmark_median(Namen>=2Bm, Bm mit >2 solchen Paaren)"] = float(expl.median())
vz["R2_faehigkeit_innerhalb_benchmark_mittel"] = float(expl.mean())
vz["n_benchmarks_R2"] = int(expl.notna().sum())
res["varianz_logit"] = vz
md.append("\n### Varianzzerlegung Logit-Skala (ALS in-sample, 12 918 Paare)\n" + json.dumps(vz, indent=1))

# Brier-Skala auf den Testpaaren (Bewertungs-Items, Saat 0)
Zs = Z[Z.seed == 0]
ybar = float((Zs.R * Zs.N).sum() / Zs.N.sum())
Rb = Zs.groupby("b_code").R.transform("mean")
bz = {"Var(y) gesamt = ybar(1-ybar)": ybar * (1 - ybar), "ybar": ybar,
      "zwischen Benchmarks Var(R_b)": float(((Rb - Zs.R.mean()) ** 2).mean()),
      "zwischen Paaren innerhalb Benchmark E(R_sb-R_b)^2": float(((Zs.R - Rb) ** 2).mean()),
      "innerhalb Paar E R(1-R)": float(Zs.floor.mean()),
      "  davon durch LOO-Item-Schwierigkeit erklärt E Var_i(p_i)": float(Zs.item_erklaert.mean()),
      "  davon Rest (Brier Orakel Rate + LOO-Schwierigkeit)": float(Zs.br_orakel_rate_loo.mean()),
      "  davon Wiederholungsrauschen (Brier bei Orakel k/n)": float(Zs.trial_floor.mean()),
      "anteil_bewertungsitems_mit_LOO_info": float(Zs.anteil_items_mit_loo.mean()),
      "paare_mit_LOO_info_>0.9": float((Zs.anteil_items_mit_loo > 0.9).mean())}
res["varianz_brier"] = bz
md.append("\n### Varianzzerlegung Brier-Skala (Testpaare, Saat 0, paargewichtet)\n" + json.dumps(bz, indent=1))

# ---------------------------------------------------------------- Orakel-Schwierigkeit je Budget
rows = []
for B in BUD:
    rows.append({"budget": B, "v1_hier_kal_paarkonstant": float(((Z[f"q_B{B}"] - Z.R) ** 2 + Z.floor).mean()),
                 "v1 + LOO-Schwierigkeit": float(Z[f"br_v1_loo_B{B}"].mean()),
                 "Orakel Rate": float(Z.floor.mean()), "Orakel Rate + LOO-Schwierigkeit": float(Z.br_orakel_rate_loo.mean())})
T = pd.DataFrame(rows).set_index("budget")
alc = {c: float(sum(GEW[B] * T.loc[B, c] for B in BUD)) for c in T.columns}
md.append("\n### Orakel-Schwierigkeit je Budget (S3, 3 Saaten)\n" + T.round(5).to_string() + "\nALC: " + json.dumps({k: round(v, 5) for k, v in alc.items()}))
res["orakel_schwierigkeit_budget"] = {int(B): r.to_dict() for B, r in T.iterrows()}
res["orakel_schwierigkeit_alc"] = alc
# nur Paare mit LOO-Info für > 90 % der Items
m = Z.anteil_items_mit_loo > 0.9
res["orakel_schwierigkeit_alc_nur_LOO>0.9"] = {
    "n_paare": int(m.sum() // 3), "v1": float(sum(GEW[B] * ((Z[m][f"q_B{B}"] - Z[m].R) ** 2 + Z[m].floor).mean() for B in BUD)),
    "v1+LOO": float(sum(GEW[B] * Z[m][f"br_v1_loo_B{B}"].mean() for B in BUD)), "orakel_rate": float(Z[m].floor.mean()),
    "orakel_rate+LOO": float(Z[m].br_orakel_rate_loo.mean())}
md.append("Nur Paare mit LOO-Info > 90 % der Items: " + json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in res["orakel_schwierigkeit_alc_nur_LOO>0.9"].items()}))
# nach Zahl anderer Subjekte im Benchmark
Z["subj_kl"] = pd.cut(Z.n_subj_bm, [0, 1, 2, 4, 9, 29, 10 ** 6], labels=["1", "2", "3-4", "5-9", "10-29", ">=30"])
g = Z.groupby("subj_kl", observed=True).agg(n=("R", "size"), floor=("floor", "mean"), orakel_loo=("br_orakel_rate_loo", "mean"),
                                            trial=("trial_floor", "mean"), loo_anteil=("anteil_items_mit_loo", "mean"))
g["alc_v1"] = [float(sum(GEW[B] * ((Z[Z.subj_kl == k][f"q_B{B}"] - Z[Z.subj_kl == k].R) ** 2 + Z[Z.subj_kl == k].floor).mean() for B in BUD)) for k in g.index]
g["alc_v1_loo"] = [float(sum(GEW[B] * Z[Z.subj_kl == k][f"br_v1_loo_B{B}"].mean() for B in BUD)) for k in g.index]
md.append("\n### Orakel-Schwierigkeit nach Zahl der Subjekte im Benchmark (Datenbank)\n" + g.round(5).to_string())
res["orakel_schwierigkeit_je_subjektzahl"] = {str(k): r.to_dict() for k, r in g.iterrows()}

# ---------------------------------------------------------------- Akquise
rows = []
for B in BUD:
    rows.append({"budget": B, "zufall ohne d (nur Rate)": float(A[f"rand_od_B{B}"].mean()),
                 "zufall mit Orakel-d": float(A[f"rand_d_B{B}"].mean()), "adaptiv mit Orakel-d": float(A[f"adapt_d_B{B}"].mean())})
TA = pd.DataFrame(rows).set_index("budget")
alc_a = {c: float(sum(GEW[B] * TA.loc[B, c] for B in BUD)) for c in TA.columns}
md.append("\n### Akquise-Simulation (Saat 0, 2 142 Paare; Prior N(mu_c, tau_c2+s2_unk), bekannte LOO-Schwierigkeit)\n"
          + TA.round(5).to_string() + "\nALC: " + json.dumps({k: round(v, 5) for k, v in alc_a.items()}))
res["akquise_budget"] = {int(B): r.to_dict() for B, r in TA.iterrows()}
res["akquise_alc"] = alc_a
# Budget-Äquivalenz: bei welchem Zufalls-Budget wird der adaptive Brier erreicht (lineare Interpolation in log B)
xs = np.array(BUD[1:], float)
yr = np.array([TA.loc[B, "zufall mit Orakel-d"] for B in BUD[1:]])
eq = {}
for B in BUD[1:]:
    ya = TA.loc[B, "adaptiv mit Orakel-d"]
    eq[int(B)] = float(np.interp(-ya, -yr, np.log(xs))) if yr.min() <= ya else None
res["akquise_budget_aequivalenz_logB"] = {k: (round(math.exp(v), 2) if v is not None else "> 31") for k, v in eq.items()}
md.append("Budget-Äquivalenz adaptiv -> zufällig (Orakel-d): " + json.dumps(res["akquise_budget_aequivalenz_logB"]))

(OUT / "leiter.json").write_text(json.dumps(res, indent=1, default=float))
(OUT / "leiter.md").write_text("\n".join(md))
print("\n".join(md))
log("Ende")
