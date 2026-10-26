"""Akquise-Lauf über die 10 Falten der v1-Kreuzvalidierung (Design A, gleiche Falten/Testpaare/Zustände wie cv_REG2).

Aufruf (PAIEC_WORK gesetzt, OMP_NUM_THREADS=1):
  python3 -I lauf_akquise.py --name pilot --nur 0 --regime S3,kompakt10 --ordnung rr --politik zufall,abdeckung \
      --praediktor hier_item --saaten 0,1,2
  python3 -I lauf_akquise.py --name voll --regime S1,S3,S30,kompakt10 --ordnung rr,paar,zufall --saaten 0,1,2 --prozesse 4
Schreibt nach $PAIEC_WORK/akquise/<name>/: saetze_f<k>.parquet, akquise_f<k>.json (Zähler je Lauf), status.json, log.txt (>>).
Zustände: $PAIEC_WORK/modell/cv_REG1/state_f<k>.json + Platt (verschachtelt, platt_je_falte ∩ platt_paket aus
cv_REG1/auswertung.json) — exakt wie modell/kreuzvalidierung.py Phase 2 (-> cv_REG2). Paketmodell = hier_item (v1).
Regel S1: nur Ordnung 'paar' (ein Paar je Lauf; Ordnung bedeutungslos). Split 'item' nur, wo --split item.
Fertig-Kriterium mechanisch: status.json fertig == Zahl angeforderter Falten; jede Parquet-Datei existiert.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
MODELL = Path(os.environ.get("PAIEC_MODELL", HIER.parents[1] / "modell"))
sys.path.insert(0, str(MODELL))
sys.path.insert(0, str(HIER))
import baselines  # noqa: E402
import simulator_strom as sim  # noqa: E402
import training  # noqa: E402
from inferenz import Modell  # noqa: E402
from kreuzvalidierung import faltenzuteilung  # noqa: E402

SCRATCH = training.SCRATCH  # $PAIEC_WORK/modell
AUS_BASIS = Path(os.environ.get("PAIEC_WORK", "work")) / "akquise"
G = {}

# Politik -> Prädiktoren in der Bewertung (festgelegt vor dem Lauf, STATUS.md Entwurf)
MATRIX = {
    "zufall": ["hier_item", "empirischer_mittelwert", "beta_binomial", "orakel_d"],
    "abdeckung": ["hier_item", "empirischer_mittelwert", "beta_binomial"],
    "unsicherheit_0.15": ["hier_item", "empirischer_mittelwert"],
    "unsicherheit_em": ["hier_item", "empirischer_mittelwert"],
    "information_naiv": ["hier_item", "empirischer_mittelwert"],
    "leicht_zuerst": ["hier_item", "empirischer_mittelwert"],
    "orakel_d": ["hier_item", "orakel_d"],
}


def log(aus, text):
    zeile = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + text
    with open(aus / "log.txt", "a", encoding="utf-8") as f:
        f.write(zeile + "\n")
    print(zeile, flush=True)


def lade_zustand(f):
    von = SCRATCH / "cv_REG1"
    state = json.loads((von / f"state_f{f}.json").read_text())
    ausw = json.loads((von / "auswertung.json").read_text())
    stufen = set(ausw["platt_paket"].keys())
    state["platt"] = {k: v for k, v in ausw["platt_je_falte"][str(f)].items() if k in stufen}
    return state


def praediktoren(state, wunsch):
    b = state["baselines"]
    alle = {"hier_item": lambda: Modell(state),
            "empirischer_mittelwert": lambda: baselines.EmpirischerMittelwert(),
            "beta_binomial": lambda: baselines.BetaBinomial(b["beta_alpha"], b["beta_beta"]),
            "orakel_d": lambda: "orakel_d"}
    return {k: alle[k]() for k in wunsch}


def falte(f):
    a = G["args"]
    p, agg, starts, subj, f_je_b = G["p"], G["agg"], G["starts"], G["subj"], G["f_je_b"]
    aus = Path(a.aus)
    ziel = aus / f"saetze_f{f}.parquet"
    if ziel.exists():
        return f, "übersprungen (vorhanden)"
    t0 = time.time()
    test_b = sorted(b for b, x in f_je_b.items() if x == f)
    state = lade_zustand(f)
    modell = Modell(state)
    praed_alle = set(sum((MATRIX[pol] for pol in a.politiken), [])) & set(a.praediktoren)
    pr_obj = praediktoren(state, praed_alle)
    testpaare = training.kappe(p[p.b_code.isin(test_b)], seed=0)
    zeilen, zaehler = [], []
    brauche_orakel = "orakel_d" in a.politiken or "orakel_d" in praed_alle
    for seed in a.saaten:
        for b, tp in testpaare.groupby("b_code"):
            i0, i1 = starts[b]
            agg_b = agg.iloc[i0:i1]
            for split in a.splits:
                paare = sim.baue_paare(agg_b, tp, subj, seed, split=split, orakel=brauche_orakel)
                for rname in a.regime:
                    S = -int(rname[7:]) if rname.startswith("kompakt") else int(rname[1:])
                    laeufe = (sim.kompakte_laeufe(agg_b, tp, subj, seed, S=-S, split=split, orakel=brauche_orakel)
                              if S < 0 else sim.gruppiere_laeufe(paare, S, seed))
                    ordnungen = ["paar"] if S == 1 else a.ordnungen
                    for ordnung in ordnungen:
                        for pol in a.politiken:
                            st_sum = {"kandidaten": 0, "kaeufe": 0, "abweichungen": 0, "fallbacks": 0, "laeufe": 0}
                            pr = {k: v for k, v in pr_obj.items() if k in MATRIX[pol]}
                            for lauf in laeufe:
                                st = sim.akquiriere(lauf, pol, ordnung, seed, modell=modell)
                                for k in ("kandidaten", "kaeufe", "abweichungen", "fallbacks"):
                                    st_sum[k] += st[k]
                                st_sum["laeufe"] += 1
                                for r in sim.bewerte_lauf(lauf, pr, seed, orakel_hyp=state["hyp"]):
                                    zeilen.append((seed, rname, ordnung, split, pol) + r)
                            zaehler.append({"saat": seed, "regime": rname, "ordnung": ordnung, "split": split,
                                            "politik": pol, "b_code": int(b), **st_sum})
    df = pd.DataFrame(zeilen, columns=["saat", "S", "ordnung", "split", "politik", "praediktor", "budget", "b_code",
                                       "s_code", "q", "R", "N", "n_eigen", "brier", "n_items_angepasst"])
    df["falte"] = f
    tmp = ziel.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(ziel)
    (aus / f"akquise_f{f}.json").write_text(json.dumps(zaehler))
    return f, f"{len(test_b)} Benchmarks, {len(testpaare)} Paare, {len(df)} Sätze, {time.time() - t0:.0f} s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--falten", type=int, default=10)
    ap.add_argument("--nur", default="")
    ap.add_argument("--saaten", default="0,1,2")
    ap.add_argument("--regime", default="S1,S3,S30,kompakt10")
    ap.add_argument("--ordnung", default="rr,paar,zufall")
    ap.add_argument("--split", default="paar")
    ap.add_argument("--politik", default=",".join(MATRIX))
    ap.add_argument("--praediktor", default="hier_item,empirischer_mittelwert,beta_binomial,orakel_d")
    ap.add_argument("--prozesse", type=int, default=4)
    a = ap.parse_args()
    a.saaten = [int(x) for x in a.saaten.split(",")]
    a.regime = a.regime.split(",")
    a.ordnungen = a.ordnung.split(",")
    a.splits = a.split.split(",")
    a.politiken = a.politik.split(",")
    a.praediktoren = a.praediktor.split(",")
    for pol in a.politiken:
        if pol not in MATRIX:
            raise SystemExit(f"unbekannte Politik {pol}")
    a.aus = str(AUS_BASIS / a.name)
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    log(aus, f"Start {a.name}: Saaten {a.saaten}, Regime {a.regime}, Ordnung {a.ordnungen}, Split {a.splits}, "
             f"Politiken {a.politiken}, Prädiktoren {a.praediktoren}, Pool-Kappe {sim.POOL_KAPPE}, Modell {MODELL}")
    p, agg = training.lade_paare()
    agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
    bc = agg.b_code.values
    starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right")))
              for b in np.unique(bc)}
    sub = pd.read_parquet(SCRATCH / "subjekte.parquet")
    subj = {int(r["s_code"]): {f: r[f] for f in ("normalized_name", "provider", "release_date", "access_date",
                                                   "harness", "harness_version", "reasoning_effort",
                                                   "subject_features_extra")}
            for r in sub.to_dict("records")}
    f_je_b = faltenzuteilung(p, a.falten)
    (aus / "falten.json").write_text(json.dumps({str(k): v for k, v in f_je_b.items()}))
    (aus / "konfig.json").write_text(json.dumps(vars(a), indent=1))
    G.update({"args": a, "p": p, "agg": agg, "starts": starts, "subj": subj, "f_je_b": f_je_b})
    liste = [int(x) for x in a.nur.split(",")] if a.nur else list(range(a.falten))
    if a.prozesse > 1 and len(liste) > 1:
        with mp.get_context("fork").Pool(min(a.prozesse, len(liste))) as pool:
            for f, txt in pool.imap_unordered(falte, liste):
                log(aus, f"Falte {f}: {txt}")
    else:
        for f in liste:
            f, txt = falte(f)
            log(aus, f"Falte {f}: {txt}")
    n_da = sum(1 for k in liste if (aus / f"saetze_f{k}.parquet").exists())
    (aus / "status.json").write_text(json.dumps({"falten_angefordert": len(liste), "fertig": n_da,
                                                 "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    log(aus, f"Ende: {n_da}/{len(liste)} Falten vorhanden")
    return 0 if n_da == len(liste) else 1


if __name__ == "__main__":
    sys.exit(main())
