#!/usr/bin/env python3
"""Fallbeispiele (P8): Lernkurven je Benchmark aus den CV-Sätzen (Design A, Phase 2, Regime S1/S3, Saaten 0–2) für ein
gelungenes und ein misslungenes Beispiel; schreibt fallbeispiele.json (Zahlen für bericht-v2/fallbeispiele.md und P7).

Nur lesen: PAIEC_WORK/modell/cv_REG2/saetze_f*.parquet (identisch mit modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10).
Aufruf: PAIEC_WORK=... python3 -I fallbeispiele.py [--benchmarks benger,alpha_sql]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
WORK = Path(os.environ.get("PAIEC_WORK", "work"))
GEW = {0: .1, 1: .2, 3: .2, 7: .2, 15: .2, 31: .1}
PRAED = ["empirischer_mittelwert", "beta_binomial", "hier_kal", "hier_item"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmarks", default="benger,alpha_sql,aegis,nyu_ctf_bench,medhelm_med_qa,mind2web")
    a = ap.parse_args()
    bm = pd.read_parquet(WORK / "basis" / "benchmarks.parquet", columns=["b_code", "folder", "direction", "domain", "n_subjects"])
    cv = pd.concat([pd.read_parquet(f) for f in sorted((WORK / "modell" / "cv_REG2").glob("saetze_f*.parquet"))], ignore_index=True)
    if cv.empty:
        raise SystemExit("keine CV-Sätze (fail-closed)")
    cv = cv.merge(bm[["b_code", "folder"]], on="b_code")
    aus = {}
    for name in a.benchmarks.split(","):
        c = cv[(cv.folder == name) & cv.praediktor.isin(PRAED)]
        if c.empty:
            aus[name] = "nicht in den CV-Sätzen"
            continue
        meta = bm[bm.folder == name].iloc[0]
        e = {"direction": str(meta.direction), "domain": str(list(meta.domain)) if not isinstance(meta.domain, str) else meta.domain,
             "n_subjects_db": int(meta.n_subjects),
             "paare_test": int(c[["b_code", "s_code"]].drop_duplicates().shape[0]), "saaten": sorted(c.saat.unique().tolist())}
        for S in ("S1", "S3"):
            cs = c[c.S == S]
            if cs.empty:
                continue
            kurve = cs.groupby(["praediktor", "budget"]).agg(brier=("brier", "mean"), sq=("q", lambda q: None)).brier.unstack("budget")
            # (q-R)^2 je Budget
            cs = cs.assign(sq=(cs.q - cs.R) ** 2)
            sq = cs.groupby(["praediktor", "budget"]).sq.mean().unstack("budget")
            alc = {p: float(sum(GEW[b] * kurve.loc[p, b] for b in GEW)) for p in kurve.index}
            # gepaarte Differenz hier_item - beta_binomial je Paar×Saat (ALC), Mittel ± SE (Paare als Einheiten, da ein Benchmark)
            piv = cs.pivot_table(index=["saat", "s_code"], columns=["praediktor", "budget"], values="brier")
            alc_p = {p: sum(GEW[b] * piv[(p, b)] for b in GEW) for p in PRAED if (p, 0) in piv.columns}
            d = (alc_p["hier_item"] - alc_p["beta_binomial"])
            d_paar = d.groupby(level="s_code").mean()          # Mittel über Saaten je Paar
            se = float(d_paar.std(ddof=1) / len(d_paar) ** .5) if len(d_paar) > 1 else None
            e[S] = {"brier_je_budget": {p: {str(b): round(float(kurve.loc[p, b]), 5) for b in GEW} for p in kurve.index},
                    "sq_je_budget": {p: {str(b): round(float(sq.loc[p, b]), 5) for b in GEW} for p in sq.index},
                    "alc": {p: round(v, 5) for p, v in alc.items()},
                    "R_mittel": round(float(cs[cs.budget == 0].drop_duplicates(["saat", "s_code"]).R.mean()), 4),
                    "R_sd": round(float(cs[cs.budget == 0].drop_duplicates(["saat", "s_code"]).R.std(ddof=0)), 4),
                    "floor_R(1-R)": round(float((lambda r: (r * (1 - r)).mean())(cs[cs.budget == 0].drop_duplicates(["saat", "s_code"]).R)), 5),
                    "diff_hier_item_minus_bb_alc": round(float(d.mean()), 5),
                    "diff_se_ueber_paare": (round(se, 5) if se is not None else "1 Paar: keine SE"),
                    "n_eigen_mittel_B31": round(float(cs[(cs.budget == 31) & (cs.praediktor == "hier_item")].n_eigen.mean()), 2),
                    "N_items_bew_mittel": round(float(cs[cs.budget == 0].drop_duplicates(["saat", "s_code"]).N.mean()), 1)}
            if len(d_paar) <= 3:
                e[S]["diff_je_paar"] = {str(k): round(float(v), 5) for k, v in d_paar.items()}
                e[S]["R_je_paar"] = {str(k): round(float(v), 4) for k, v in cs[cs.budget == 0].groupby("s_code").R.mean().items()}
        aus[name] = e
    aus["_kehrseite"] = ("Discovery-Saaten 0–2, Auswahl der Benchmarks nach Sicht auf je_benchmark.csv: Illustration des vorregistrierten "
                         "Mechanismus (Pooling, H2b), kein Beleg; Ein-Paar-Benchmarks haben keine SE, der Gruppenbefund über 13 Benchmarks trägt.")
    (HIER / "fallbeispiele.json").write_text(json.dumps(aus, indent=1))
    print(json.dumps(aus, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
