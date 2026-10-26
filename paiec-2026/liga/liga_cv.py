"""Methoden-Liga: je Falte (1) Hyperparameter-Suche NUR auf den Trainingsbenchmarks (innere 75/25-Aufteilung, Simulation
Saat 100), (2) Fit auf allen Trainingsbenchmarks, (3) identisches Protokoll wie cv_REG2 (Saaten 0,1,2; Regime
S1,S2,S3,S30,kompakt10; Budgets 0..31; itemgenauer Brier) auf den Testbenchmarks der Falte.

Aufruf: PAIEC_WORK=.../paiec-data python3 -I liga_cv.py --aus .../liga-work/cv_LIGA [--nur 2] [--prozesse 4]
Schreibt je Falte: saetze_f<k>.parquet (Schema wie cv_REG2 + Liga-Methoden), hyper_f<k>.csv (Gitter), wahl_f<k>.json,
zeiten_f<k>.json (Laufzeit je 1000 Aufrufe), log_f<k>.txt (nur anhängen).
Falten/Kappung/Saaten: exakt kreuzvalidierung.py (falten.json aus cv_A übernommen, training.kappe Saat 0).
"""
import argparse
import hashlib
import itertools
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parents[1] / "modell"))
sys.path.insert(0, str(HIER))
import baselines  # noqa: E402
import metrik  # noqa: E402
import simulator  # noqa: E402
import training  # noqa: E402
import liga_methoden as lm  # noqa: E402

SCRATCH = training.SCRATCH
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))
REGIME_AUSSEN = ["S1", "S2", "S3", "S30", "kompakt10"]
REGIME_INNEN = ["S1", "S3", "S30", "kompakt10"]
SAATEN_AUSSEN = [0, 1, 2]
SAATEN_INNEN = [100]
G = {}


def _regime(name):
    return -int(name[7:]) if name.startswith("kompakt") else int(name[1:])


def log(aus, f, text):
    zeile = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + f" [f{f}] " + text
    with open(aus / f"log_f{f}.txt", "a", encoding="utf-8") as fh:
        fh.write(zeile + "\n")
    print(zeile, flush=True)


def simuliere(testpaare, praed, saaten, regime, seed_offset=0):
    """Identisch zur Schleife in kreuzvalidierung.falte. -> DataFrame (saat, S, praediktor, budget, b_code, s_code, q, R, N,
    n_eigen, brier, n_items_angepasst)"""
    agg, starts, subj = G["agg"], G["starts"], G["subj"]
    zeilen = []
    for seed in saaten:
        for b, tp in testpaare.groupby("b_code"):
            i0, i1 = starts[b]
            agg_b = agg.iloc[i0:i1]
            paare = simulator.baue_paare(agg_b, tp, subj, seed)
            for rname in regime:
                S = _regime(rname)
                laeufe = (simulator.kompakte_laeufe(agg_b, tp, subj, seed, S=-S) if S < 0
                          else simulator.gruppiere_laeufe(paare, S, seed))
                for lauf in laeufe:
                    for r in simulator.bewerte_lauf(lauf, praed, seed):
                        zeilen.append((seed, rname) + r)
    return pd.DataFrame(zeilen, columns=["saat", "S", "praediktor", "budget", "b_code", "s_code", "q", "R", "N",
                                         "n_eigen", "brier", "n_items_angepasst"])


def alc_tabelle(df):
    """-> DataFrame praediktor x S: Paar-ALC (Paare gleich gewichtet, Mittel über Saaten)"""
    d = df.assign(wb=df.budget.map(GEW) * df.brier)
    g = d.groupby(["praediktor", "S", "saat", "b_code", "s_code"]).wb.sum().reset_index()
    return g.groupby(["praediktor", "S"]).wb.mean().unstack("S")


def gitter(**raum):
    schl = list(raum)
    for werte in itertools.product(*[raum[k] for k in schl]):
        yield dict(zip(schl, werte))


def kurz(cfg):
    return ",".join(f"{k}={v}" for k, v in cfg.items())


def tune(aus, f, familie, bauer, raum, testpaare, hyper_zeilen, stufe):
    """Alle Konfigurationen eines Gitters in EINEM Simulationsdurchlauf (gleiche Labels). -> (beste cfg, Tabelle)"""
    praed = {}
    cfgs = {}
    for cfg in gitter(**raum):
        name = f"{familie}|{kurz(cfg)}"
        praed[name] = bauer(cfg)
        cfgs[name] = cfg
    t0 = time.time()
    df = simuliere(testpaare, praed, SAATEN_INNEN, REGIME_INNEN)
    tab = alc_tabelle(df)
    tab["mittel"] = tab[REGIME_INNEN].mean(axis=1)
    for name, row in tab.iterrows():
        z = {"falte": f, "familie": familie, "stufe": stufe, "konfig": kurz(cfgs[name]), "alc_mittel": row["mittel"]}
        z.update({f"alc_{r}": row[r] for r in REGIME_INNEN})
        hyper_zeilen.append(z)
    best = tab["mittel"].idxmin()
    log(aus, f, f"tune {familie}/{stufe}: {len(praed)} Konfig., {time.time() - t0:.0f} s, beste {best} "
               f"ALC {tab.loc[best, 'mittel']:.5f} (schlechteste {tab['mittel'].max():.5f})")
    return cfgs[best], tab


# ------------------------------------------------------------------ GB-Trainingszeilen
def gb_zeilen(p_train_test, info, saaten=(100,), regime=REGIME_INNEN, M=4, seed=7):
    """Simulierte Läufe auf Trainingsbenchmarks (gekappt wie Testpaare) -> Merkmalszeilen mit Item-Ziel y ~ Bern(k_i/n_i)."""
    agg, starts, subj = G["agg"], G["starts"], G["subj"]
    mk = lm.GBMerkmale(info)
    rng = np.random.default_rng(seed)
    X, Y, grp = [], [], []
    for seed_s in saaten:
        for b, tp in p_train_test.groupby("b_code"):
            i0, i1 = starts[b]
            agg_b = agg.iloc[i0:i1]
            paare = simulator.baue_paare(agg_b, tp, subj, seed_s)
            anon = "bm_%016x" % simulator._saat(seed_s, "anon", b)
            for rname in regime:
                S = _regime(rname)
                laeufe = (simulator.kompakte_laeufe(agg_b, tp, subj, seed_s, S=-S) if S < 0
                          else simulator.gruppiere_laeufe(paare, S, seed_s))
                for lauf in laeufe:
                    for B in metrik.BUDGETS:
                        labeled = []
                        for pp in lauf:
                            for y, ic in zip(pp["y"][:B], pp["lab_i"][:B]):
                                labeled.append([[pp["subject"], simulator._item(anon, ic)], int(y)])
                        gr, items = lm.gruppiere(labeled)
                        g_bid = gr.get(anon, {})
                        it_bid = items.get(anon, {})
                        for pp in lauf:
                            kf = lm.konfig(pp["subject"])
                            wahl = rng.choice(len(pp["bew_i"]), min(M, len(pp["bew_i"])), replace=False)
                            for j in wahl:
                                ic = int(pp["bew_i"][j])
                                ik = lm.Modell.item_schluessel(simulator._item(anon, ic))
                                X.append(mk.zeile(pp["subject"], g_bid, kf, it_bid.get(ik)))
                                Y.append(1 if rng.random() < pp["bew_k"][j] / pp["bew_n"][j] else 0)
                                grp.append(b)
    return np.array(X, dtype=float), np.array(Y, dtype=int), np.array(grp)


def gb_tune_fit(aus, f, X, Y, grp, hyper_zeilen):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold
    raum = {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [7, 15, 63], "max_iter": [60, 200], "min_samples_leaf": [20, 200]}
    best = None
    t0 = time.time()
    for cfg in gitter(**raum):
        bs = []
        for tr, te in GroupKFold(3).split(X, Y, grp):
            m = HistGradientBoostingClassifier(early_stopping=False, random_state=0, **cfg).fit(X[tr], Y[tr])
            q = m.predict_proba(X[te])[:, 1]
            bs.append(float(np.mean((q - Y[te]) ** 2)))
        score = float(np.mean(bs))
        hyper_zeilen.append({"falte": f, "familie": "gb", "stufe": "gruppen-cv-3", "konfig": kurz(cfg),
                             "alc_mittel": score, "n_zeilen": int(len(Y))})
        if best is None or score < best[0]:
            best = (score, cfg)
    m = HistGradientBoostingClassifier(early_stopping=False, random_state=0, **best[1]).fit(X, Y)
    log(aus, f, f"tune gb: 24 Konfig. x 3 Gruppenfalten auf {len(Y)} Zeilen, {time.time() - t0:.0f} s, beste {kurz(best[1])} "
               f"Brier {best[0]:.5f}")
    return m, best[1]


# ------------------------------------------------------------------ Falte
def falte(f):
    a = G["args"]
    p, agg, sub, f_je_b = G["p"], G["agg"], G["sub"], G["f_je_b"]
    aus = Path(a.aus)
    ziel = aus / f"saetze_f{f}.parquet"
    if ziel.exists() and not a.neu:
        return f, "übersprungen (vorhanden)"
    t_start = time.time()
    test_b = sorted(b for b, x in f_je_b.items() if x == f)
    train = p[~p.b_code.isin(test_b)]
    train_b = sorted(train.b_code.unique())
    testpaare = training.kappe(p[p.b_code.isin(test_b)], seed=0)
    log(aus, f, f"Start: {len(test_b)} Testbenchmarks, {len(testpaare)} Testpaare, {len(train_b)} Trainingsbenchmarks")
    hyper_zeilen = []
    wahl = {}

    # ---- innere Aufteilung der Trainingsbenchmarks (75/25, deterministisch je Falte)
    def innen(b):
        return int.from_bytes(hashlib.sha256(f"{f}|{b}".encode()).digest()[:4], "big") % 4 == 0
    innen_test_b = [b for b in train_b if innen(b)]
    innen_train = train[~train.b_code.isin(innen_test_b)]
    innen_testpaare = training.kappe(train[train.b_code.isin(innen_test_b)], seed=0)
    if a.schnell:
        innen_testpaare = innen_testpaare[innen_testpaare.b_code.isin(sorted(innen_testpaare.b_code.unique())[:8])]
    sub_names_in = innen_train[innen_train.name != ""].drop_duplicates("s_code").set_index("s_code").name
    log(aus, f, f"innen: {len(innen_test_b)} Testbenchmarks ({len(innen_testpaare)} Paare), "
               f"{innen_train.b_code.nunique()} Trainingsbenchmarks")

    # ---- IRT (innen)
    t0 = time.time()
    fit1_in = lm.irt_fit(agg, sub_names_in, innen_train.b_code.unique(), zweipl=False)
    fit2_in = lm.irt_fit(agg, sub_names_in, innen_train.b_code.unique(), zweipl=True)
    log(aus, f, f"irt innen gefittet: {fit1_in['n_units']} Namen, {fit1_in['n_items']} Items, mu_c {fit1_in['mu_c']:.3f}, "
               f"{time.time() - t0:.0f} s")
    raum_irt = {"tau_c2": [0.5, 1.5, 4.0], "s2_unk": [0.1, 0.3, 1.0, 3.0], "kappa": [4.0, 16.0, 64.0], "laplace": [False, True]}
    b1, _ = tune(aus, f, "irt1pl", lambda c: lm.IRT(fit1_in, **c), raum_irt, innen_testpaare, hyper_zeilen, "paar")
    raum2 = dict(raum_irt, tau_a2=[0.05, 0.3, 1.0])
    b2, _ = tune(aus, f, "irt2pl", lambda c: lm.IRT(fit2_in, zweipl=True, **c), raum2, innen_testpaare, hyper_zeilen, "paar")

    # ---- MF (innen)
    t0 = time.time()
    fits_mf_in = {r: lm.mf_fit(innen_train, rang=r) for r in (1, 2, 4, 8)}
    log(aus, f, f"mf innen gefittet (Rang 1,2,4,8), {time.time() - t0:.0f} s; sig2 " +
        " ".join(f"r{r}={v['sig2']:.3f}" for r, v in fits_mf_in.items()))
    raum_mf = {"rang": [1, 2, 4, 8], "tau_a2": [0.5, 2.0, 8.0], "s2_v": [0.05, 0.2, 0.6], "s2_unk": [0.1, 0.5, 1.5]}
    bm, _ = tune(aus, f, "mf", lambda c: lm.MF(fits_mf_in[c["rang"]], **{k: v for k, v in c.items() if k != "rang"}),
                 raum_mf, innen_testpaare, hyper_zeilen, "paar")

    # ---- kNN (innen)
    knn_in = lm.knn_fit(innen_train)
    raum_knn = {"alpha": [2.0, 4.0, 8.0, 16.0], "h": [0.25, 0.5, 1.0, 2.0], "w0": [0.05, 0.2, 0.5], "gamma": [0.0, 1.0]}
    bk, _ = tune(aus, f, "knn", lambda c: lm.KNN(knn_in, item=False, **c), raum_knn, innen_testpaare, hyper_zeilen, "paar")

    # ---- Item-Stufe (innen): sigma_i2 für IRT/MF, beta für kNN
    raum_i = {"sigma_i2": [1.0, 2.5, 5.0]}
    bi1, _ = tune(aus, f, "irt1pl", lambda c: lm.IRT(fit1_in, **b1, **c), raum_i, innen_testpaare, hyper_zeilen, "item")
    bi2, _ = tune(aus, f, "irt2pl", lambda c: lm.IRT(fit2_in, zweipl=True, **b2, **c), raum_i, innen_testpaare,
                  hyper_zeilen, "item")
    bim, _ = tune(aus, f, "mf", lambda c: lm.MF(fits_mf_in[bm["rang"]], **{k: v for k, v in bm.items() if k != "rang"}, **c),
                  raum_i, innen_testpaare, hyper_zeilen, "item")
    bik, _ = tune(aus, f, "knn", lambda c: lm.KNN(knn_in, item=True, **bk, **c), {"beta": [0.1, 0.25, 0.5, 1.0, 2.0]},
                  innen_testpaare, hyper_zeilen, "item")
    wahl.update({"irt1pl": dict(b1, **bi1), "irt2pl": dict(b2, **bi2), "mf": dict(bm, **bim), "knn": dict(bk, **bik)})
    # Stacking-Gewichte der Gegenmethoden (ohne GB: dessen innere Vorhersagen wären in-sample) aus den inneren Testsätzen
    t0 = time.time()
    basen_in = {"irt2pl": lm.IRT(fit2_in, zweipl=True, **wahl["irt2pl"]),
                "mf": lm.MF(fits_mf_in[bm["rang"]], **{k: v for k, v in wahl["mf"].items() if k != "rang"}),
                "knn": lm.KNN(knn_in, item=True, **wahl["knn"]),
                "beta_binomial": baselines.BetaBinomial(*baselines.beta_prior(
                    [g.rate.tolist() for _, g in training.kappe(innen_train, seed=0).groupby("b_code")])[:2])}
    df_in = simuliere(innen_testpaare, basen_in, SAATEN_INNEN, REGIME_INNEN)
    stack_gew = lm.stack_fit(df_in, list(basen_in))
    wahl["stack"] = {"basen": list(basen_in), "gewichte": {str(k): v for k, v in stack_gew.items()}}
    tab_in = alc_tabelle(df_in)
    log(aus, f, f"stack innen: {time.time() - t0:.0f} s, Basen-ALC " + " ".join(f"{k}={tab_in.loc[k].mean():.5f}" for k in basen_in)
               + "; Gewichte Stufe 7: " + ",".join(f"{v:.2f}" for v in stack_gew[7]))
    del fit1_in, fit2_in, fits_mf_in, knn_in, basen_in, df_in

    # ---- GB: Zeilen aus simulierten Läufen auf ALLEN Trainingsbenchmarks, Gitter per Gruppen-CV (Benchmark-Gruppen)
    t0 = time.time()
    info = lm.gb_info(train, sub)
    train_test = training.kappe(train, seed=0)
    if a.schnell:
        train_test = train_test[train_test.b_code.isin(sorted(train_test.b_code.unique())[:30])]
    X, Y, grp = gb_zeilen(train_test, info)
    log(aus, f, f"gb Zeilen: {X.shape} aus {len(np.unique(grp))} Benchmarks, {time.time() - t0:.0f} s")
    gb_modell, bg = gb_tune_fit(aus, f, X, Y, grp, hyper_zeilen)
    wahl["gb"] = bg
    del X, Y, grp
    pd.DataFrame(hyper_zeilen).to_csv(aus / f"hyper_f{f}.csv", index=False)
    (aus / f"wahl_f{f}.json").write_text(json.dumps(wahl, indent=1))

    # ---- Fit auf allen Trainingsbenchmarks mit den gewählten Hyperparametern
    t0 = time.time()
    sub_names = train[train.name != ""].drop_duplicates("s_code").set_index("s_code").name
    fit1 = lm.irt_fit(agg, sub_names, train_b, zweipl=False)
    fit2 = lm.irt_fit(agg, sub_names, train_b, zweipl=True)
    fit_mf = lm.mf_fit(train, rang=wahl["mf"]["rang"])
    knn_fit = lm.knn_fit(train)
    st = json.loads((SCRATCH / "cv_A" / f"state_f{f}.json").read_text())["baselines"]
    log(aus, f, f"außen gefittet: irt {fit1['n_units']} Namen/{fit1['n_items']} Items, mf r{fit_mf['rang']}, "
               f"{time.time() - t0:.0f} s")
    praed = {
        "empirischer_mittelwert": baselines.EmpirischerMittelwert(),
        "beta_binomial": baselines.BetaBinomial(st["beta_alpha"], st["beta_beta"]),
        "irt1pl": lm.IRT(fit1, **wahl["irt1pl"]),
        "irt2pl": lm.IRT(fit2, zweipl=True, **wahl["irt2pl"]),
        "mf": lm.MF(fit_mf, **{k: v for k, v in wahl["mf"].items() if k != "rang"}),
        "knn": lm.KNN(knn_fit, item=True, **wahl["knn"]),
        "gb": lm.GB(gb_modell, info, item=True),
    }
    praed["stack"] = lm.Stack({k: praed[k] for k in wahl["stack"]["basen"]}, wahl["stack"]["gewichte"])
    praed = {k: lm.Zeit(v) for k, v in praed.items()}
    t0 = time.time()
    saaten = SAATEN_AUSSEN[:1] if a.schnell else SAATEN_AUSSEN
    df = simuliere(testpaare, praed, saaten, REGIME_AUSSEN)
    namen = set(train.name.unique()) - {""}
    meta = testpaare.set_index("s_code")[["name"]]
    df["bekannt"] = df.s_code.map(meta.name).map(lambda n: bool(n) and n in namen)
    df["kalt"] = False
    df["falte"] = f
    tmp = ziel.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(ziel)
    zeiten = {k: v.stat() for k, v in praed.items()}
    (aus / f"zeiten_f{f}.json").write_text(json.dumps(zeiten, indent=1))
    log(aus, f, f"außen: {len(df)} Sätze, {time.time() - t0:.0f} s; gesamt {time.time() - t_start:.0f} s")
    return f, f"{len(test_b)} Benchmarks, {len(testpaare)} Paare, {len(df)} Sätze, {time.time() - t_start:.0f} s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", required=True)
    ap.add_argument("--prozesse", type=int, default=4)
    ap.add_argument("--nur", default="")
    ap.add_argument("--schnell", action="store_true", help="1 Saat außen, kleinere innere Mengen (Probelauf)")
    ap.add_argument("--neu", action="store_true")
    a = ap.parse_args()
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    p, agg = training.lade_paare()
    agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
    bc = agg.b_code.values
    starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right"))) for b in np.unique(bc)}
    sub = pd.read_parquet(SCRATCH / "subjekte.parquet")
    subj = {int(r["s_code"]): {f: r[f] for f in ("normalized_name", "provider", "release_date", "access_date", "harness",
                                                   "harness_version", "reasoning_effort", "subject_features_extra")}
            for r in sub.to_dict("records")}
    f_je_b = {int(k): v for k, v in json.loads((SCRATCH / "cv_A" / "falten.json").read_text()).items()}
    (aus / "falten.json").write_text(json.dumps({str(k): v for k, v in f_je_b.items()}))
    G.update({"args": a, "p": p, "agg": agg, "sub": sub, "starts": starts, "subj": subj, "f_je_b": f_je_b})
    liste = [int(x) for x in a.nur.split(",")] if a.nur else list(range(10))
    if a.prozesse > 1 and len(liste) > 1:
        with mp.get_context("fork").Pool(a.prozesse) as pool:
            for f, txt in pool.imap_unordered(falte, liste):
                log(aus, "x", f"Falte {f}: {txt}")
    else:
        for f in liste:
            f, txt = falte(f)
            log(aus, "x", f"Falte {f}: {txt}")
    n_da = sum(1 for k in range(10) if (aus / f"saetze_f{k}.parquet").exists())
    (aus / "status.json").write_text(json.dumps({"falten": 10, "fertig": n_da,
                                                 "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))


if __name__ == "__main__":
    main()
