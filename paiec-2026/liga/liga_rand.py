"""Randprüfung der Gitter (nachträglich, nur innere Trainings-/Testmengen einer Falte): liegt das gewählte Optimum am
Gitterrand (κ = 64, τ_a² = 1), wird das Gitter in diese Richtung verlängert und geprüft, wie viel ALC noch gewinnbar wäre.
Aufruf: PAIEC_WORK=... python3 -I liga_rand.py --falte 2 --aus <ordner>  -> hyper_rand_f<k>.csv
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parents[1] / "modell"))
sys.path.insert(0, str(HIER))
import training  # noqa: E402
import liga_cv  # noqa: E402
import liga_methoden as lm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--falte", type=int, required=True)
    ap.add_argument("--aus", required=True)
    ap.add_argument("--nachtrag", action="store_true",
                    help="nur die UNTEREN Gitterränder (kNN-alpha 0.5/1.0, MF tau_a2 0.1-0.5 und s2_v 0.01-0.2; Hauptlauf prüft nur nach oben) -> hyper_rand2_f<k>.csv")
    a = ap.parse_args()
    aus = Path(a.aus)
    f = a.falte
    p, agg = training.lade_paare()
    agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
    bc = agg.b_code.values
    starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right"))) for b in np.unique(bc)}
    sub = pd.read_parquet(training.SCRATCH / "subjekte.parquet")
    subj = {int(r["s_code"]): {k: r[k] for k in ("normalized_name", "provider", "release_date", "access_date", "harness",
                                                   "harness_version", "reasoning_effort", "subject_features_extra")}
            for r in sub.to_dict("records")}
    f_je_b = {int(k): v for k, v in json.loads((training.SCRATCH / "cv_A" / "falten.json").read_text()).items()}
    liga_cv.G.update({"agg": agg, "starts": starts, "subj": subj})
    test_b = sorted(b for b, x in f_je_b.items() if x == f)
    train = p[~p.b_code.isin(test_b)]
    train_b = sorted(train.b_code.unique())
    innen_test_b = [b for b in train_b if int.from_bytes(hashlib.sha256(f"{f}|{b}".encode()).digest()[:4], "big") % 4 == 0]
    innen_train = train[~train.b_code.isin(innen_test_b)]
    innen_testpaare = training.kappe(train[train.b_code.isin(innen_test_b)], seed=0)
    sub_names_in = innen_train[innen_train.name != ""].drop_duplicates("s_code").set_index("s_code").name
    wahl = json.loads((aus / f"wahl_f{f}.json").read_text())
    zeilen = []
    t0 = time.time()
    if a.nachtrag:
        knn = lm.knn_fit(innen_train)
        wk = {k: v for k, v in wahl["knn"].items() if k not in ("h", "beta", "alpha")}
        liga_cv.tune(aus, f, "knn", lambda c: lm.KNN(knn, item=False, **wk, **c),
                     {"h": [0.5, 1.0], "alpha": [0.5, 1.0, 2.0]}, innen_testpaare, zeilen, "rand-alpha-unten")
        fit_mf = lm.mf_fit(innen_train, rang=wahl["mf"]["rang"])
        wm = {k: v for k, v in wahl["mf"].items() if k not in ("rang", "tau_a2", "s2_v", "sigma_i2")}
        liga_cv.tune(aus, f, "mf", lambda c: lm.MF(fit_mf, **wm, **c),
                     {"tau_a2": [0.1, 0.2, 0.5], "s2_v": [0.01, 0.05, 0.2]}, innen_testpaare, zeilen, "rand-tau_a2-s2_v-unten")
        pd.DataFrame(zeilen).to_csv(aus / f"hyper_rand2_f{f}.csv", index=False)
        liga_cv.log(aus, f, f"Randprüfung-Nachtrag (untere Ränder kNN, MF) fertig, {time.time() - t0:.0f} s")
        return
    fit1 = lm.irt_fit(agg, sub_names_in, innen_train.b_code.unique(), zweipl=False)
    fit2 = lm.irt_fit(agg, sub_names_in, innen_train.b_code.unique(), zweipl=True)
    w1 = {k: v for k, v in wahl["irt1pl"].items() if k not in ("kappa", "sigma_i2")}
    liga_cv.tune(aus, f, "irt1pl", lambda c: lm.IRT(fit1, **w1, **c), {"kappa": [16.0, 64.0, 256.0, 1024.0]},
                 innen_testpaare, zeilen, "rand-kappa")
    w2 = {k: v for k, v in wahl["irt2pl"].items() if k not in ("kappa", "tau_a2", "sigma_i2")}
    liga_cv.tune(aus, f, "irt2pl", lambda c: lm.IRT(fit2, zweipl=True, **w2, **c),
                 {"kappa": [64.0, 256.0, 1024.0], "tau_a2": [1.0, 3.0, 10.0]}, innen_testpaare, zeilen, "rand-kappa-tau_a2")
    fit_mf = lm.mf_fit(innen_train, rang=wahl["mf"]["rang"])
    wm = {k: v for k, v in wahl["mf"].items() if k not in ("rang", "tau_a2", "s2_v", "sigma_i2")}
    liga_cv.tune(aus, f, "mf", lambda c: lm.MF(fit_mf, **wm, **c), {"tau_a2": [2.0, 8.0, 32.0], "s2_v": [0.2, 0.6, 1.5]},
                 innen_testpaare, zeilen, "rand-tau_a2-s2_v")
    knn = lm.knn_fit(innen_train)
    wk = {k: v for k, v in wahl["knn"].items() if k not in ("h", "beta", "alpha")}
    liga_cv.tune(aus, f, "knn", lambda c: lm.KNN(knn, item=False, **wk, **c),
                 {"h": [0.1, 0.25, 0.5], "alpha": [8.0, 16.0, 32.0]}, innen_testpaare, zeilen, "rand-h-alpha")
    pd.DataFrame(zeilen).to_csv(aus / f"hyper_rand_f{f}.csv", index=False)
    liga_cv.log(aus, f, f"Randprüfung fertig, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
