#!/usr/bin/env python3
"""Zweiter Rechenweg für L10 (irreduzibles Antwortrauschen) und für den L9-Abgleich — P8, BAUPLAN-V2 §2.3.

Unabhängig vom ersten Weg (v2-plan/d-wissenschaft/wiederholung.py, numpy auf agg.parquet):
  * Datenpfad: direkt aus den Roh-Antworten basis/responses/benchmark=<bm>/part-0.parquet (nicht aus agg.parquet);
    Auswahl und Ausschlüsse (binär, public, coverage > 0; Befund 3 bird_sql, Befund 4 swebench_live) hier neu umgesetzt.
  * Schätzer: unverzerrte Zellvarianz p(1-p) als Stichprobenvarianz der n Bernoulli-Antworten mit ddof = 1
    (pandas `var()`), nicht als Formel k(n-k)/(n(n-1)); mathematisch identisch, rechnerisch ein anderer Weg.
  * Nur pandas (Lesen über pandas.read_parquet, Aggregation über groupby); kein numpy im Rechenkern.

Schreibt (im Ordner dieses Skripts):
  noise_floor_by_benchmark.csv   je Benchmark: Zellen, Zellen mit n >= 2, Antworten, L10 (antwort-/zellgewichtet), k/n-Orakel, n-Median/Max
  wiederholung_b.json            Gesamtwerte, Vergleich mit dem ersten Weg (relative Abweichung), L9-Abgleichstabelle
Fail-closed: fehlende Datei, Parse-Fehler, Werte außerhalb {0,1}, oder Kontrollsummen ungleich dem ersten Weg (Population) -> rc != 0.
Aufruf: PAIEC_WORK=... OMP_NUM_THREADS=1 python3 -I wiederholung_b.py [--erstweg PFAD/wiederholung.json] [--toleranz 0.01]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
PROJ = HIER.parents[1]                       # .../paiec-stanford
WORK = Path(os.environ.get("PAIEC_WORK", "work"))
BASIS = WORK / "basis"
LIEFERUNG = PROJ / "audit" / "csv"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def ausschluesse():
    """Dieselben Ausschlussregeln wie modell/daten.py, hier neu aus den Befund-CSVs gelesen (fail-closed)."""
    f3 = pd.read_csv(LIEFERUNG / "F3a_bird_sql_configurations.csv", dtype=str)
    f4 = pd.read_csv(LIEFERUNG / "F4_swebench_live_subjects.csv", dtype=str)
    aus = {("bird_sql", s) for s in f3.loc[f3.all_rows_graded_0 == "True", "subject_id"]}
    aus |= {("swebench_live", s) for s in f4.loc[f4.category.str.startswith("website report subject: only resolved"), "subject_id"]}
    if not aus:
        raise SystemExit("Ausschlusslisten leer – Abbruch (fail-closed)")
    return aus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--erstweg", default=str(PROJ / "v2-plan" / "d-wissenschaft" / "wiederholung.json"))
    ap.add_argument("--toleranz", type=float, default=0.01)
    ap.add_argument("--cv", default=str(WORK / "modell" / "cv_REG2"), help="CV-Sätze für die Testpaar-Menge (L9-Abgleich)")
    a = ap.parse_args()

    bm = pd.read_parquet(BASIS / "benchmarks.parquet")
    wahl = bm[(bm.response_type == "binary") & (bm.release == "public") & (bm.coverage.fillna(0) > 0)].sort_values("b_code")
    sub = pd.read_parquet(BASIS / "subjects.parquet", columns=["s_code", "benchmark_id", "subject_id"])
    aus = ausschluesse()
    s_aus = set(sub.loc[[(b, s) in aus for b, s in zip(sub.benchmark_id, sub.subject_id)], "s_code"])
    log(f"Benchmarks gewählt: {len(wahl)}; Subjekt-Ausschlüsse: {len(s_aus)}")

    je_bm = []
    paare = []           # je (b_code, s_code): Summen für das k/n-Orakel (alle Zellen) und L10 (nur n >= 2)
    for row in wahl.itertuples(index=False):
        f = BASIS / "responses" / f"benchmark={row.folder}" / "part-0.parquet"
        if not f.exists():
            raise SystemExit(f"fehlt: {f} (fail-closed)")
        try:
            r = pd.read_parquet(f, columns=["s_code", "i_code", "response"])
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"Parse-Fehler {f}: {e} (fail-closed)")
        r = r.dropna(subset=["response"])
        if len(r) == 0:
            continue
        if not r.response.isin([0.0, 1.0]).all():
            raise SystemExit(f"{row.folder}: binäre Antworten außerhalb {{0,1}} (fail-closed)")
        if s_aus:
            r = r[~r.s_code.isin(s_aus)]
        z = r.groupby(["s_code", "i_code"], sort=False)["response"].agg(n="count", k="sum", v="var")
        # v = Stichprobenvarianz (ddof=1) = k(n-k)/(n(n-1)) für n >= 2, NaN für n = 1
        rep = z[z.n >= 2]
        kn = (z.k * (z.n - z.k) / z.n)                    # k/n-Orakel je Zelle: n * phat(1-phat)
        je_bm.append({
            "benchmark_id": row.folder, "b_code": int(row.b_code), "direction": row.direction,
            "cells": int(len(z)), "cells_rep": int(len(rep)), "share_cells_rep": float(len(rep) / len(z)),
            "responses": int(z.n.sum()), "responses_rep": int(rep.n.sum()),
            "share_responses_rep": float(rep.n.sum() / z.n.sum()),
            "subjects": int(z.index.get_level_values(0).nunique()), "items": int(z.index.get_level_values(1).nunique()),
            "L10_response_weighted": float((rep.n * rep.v).sum() / rep.n.sum()) if len(rep) else float("nan"),
            "L10_cell_weighted": float(rep.v.mean()) if len(rep) else float("nan"),
            "kn_oracle_response_weighted": float(kn.sum() / z.n.sum()),
            "n_median_rep": float(rep.n.median()) if len(rep) else float("nan"),
            "n_max": int(z.n.max()),
        })
        zp = z.assign(kn=kn, nv=(z.n * z.v).fillna(0.0), nrep=z.n.where(z.n >= 2, 0))
        gp = zp.groupby(level=0).agg(items=("n", "size"), n=("n", "sum"), kn=("kn", "sum"), nv=("nv", "sum"), nrep=("nrep", "sum"))
        gp["b_code"] = int(row.b_code)
        paare.append(gp.reset_index())
        log(f"{row.folder}: Zellen {len(z)}, Wdh-Zellen {len(rep)}, Antworten {int(z.n.sum())}")

    T = pd.DataFrame(je_bm).sort_values("b_code")
    P = pd.concat(paare, ignore_index=True)
    out = {"zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "weg": "B: pandas groupby var(ddof=1) auf Roh-Antworten",
           "benchmarks_mit_daten": int(len(T)),
           "zeilen_gesamt": int(T.cells.sum()), "antworten_gesamt": int(T.responses.sum()),
           "zeilen_mit_wiederholung": int(T.cells_rep.sum()),
           "anteil_zeilen_wdh": float(T.cells_rep.sum() / T.cells.sum()),
           "anteil_antworten_in_wdh_zellen": float(T.responses_rep.sum() / T.responses.sum())}
    # Gesamt-L10 antwortgewichtet: Σ n·v / Σ n über alle Wdh-Zellen = Σ_bm (L10_bm · responses_rep_bm) / Σ responses_rep
    out["schranke_antwortgewichtet_nur_wdh"] = float((T.L10_response_weighted * T.responses_rep).sum() / T.responses_rep.sum())
    out["schranke_zellgewichtet_nur_wdh"] = float((T.L10_cell_weighted * T.cells_rep).sum() / T.cells_rep.sum())
    out["orakel_kn_alle_zellen"] = float((T.kn_oracle_response_weighted * T.responses).sum() / T.responses.sum())
    G = T[T.cells_rep >= 100]
    out["benchmarks_mit_>=100_wdh_zellen"] = int(len(G))
    out["schranke_je_bm_quantile"] = {str(q): float(G.L10_response_weighted.quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    out["schranke_bm_balanciert_mittel"] = float(G.L10_response_weighted.mean())
    ohne_mpl = T[T.benchmark_id != "monkey_power_laws"]
    out["orakel_kn_alle_zellen_ohne_monkey_power_laws"] = float((ohne_mpl.kn_oracle_response_weighted * ohne_mpl.responses).sum() / ohne_mpl.responses.sum())
    out["schranke_antwortgewichtet_ohne_monkey_power_laws"] = float((ohne_mpl.L10_response_weighted * ohne_mpl.responses_rep).sum() / ohne_mpl.responses_rep.sum())
    out["anteil_antworten_monkey_power_laws"] = float(T.loc[T.benchmark_id == "monkey_power_laws", "responses"].sum() / T.responses.sum())

    # ---- L9-Abgleich: dasselbe k/n-Orakel, aber paargewichtet (wie die Wettbewerbsmetrik) auf Paaren >= 80 Items
    P80 = P[P["items"] >= 80].copy()
    P80["kn_pair"] = P80.kn / P80.n                                   # k/n-Orakel je Paar (alle Items), antwortgewichtet innerhalb
    P80["L10_pair"] = P80.nv / P80.nrep.where(P80.nrep > 0)            # unverzerrt, nur Wdh-Zellen des Paares
    out["l9_abgleich"] = {
        "paare_ge80": int(len(P80)), "benchmarks_paare_ge80": int(P80.b_code.nunique()),
        "kn_paargewichtet_alle_paare_ge80": float(P80.kn_pair.mean()),
        "kn_antwortgewichtet_alle_paare_ge80": float(P80.kn.sum() / P80.n.sum()),
        "anteil_paare_mit_wdh_zellen": float((P80.nrep > 0).mean()),
    }
    cvdir = Path(a.cv)
    saetze = sorted(cvdir.glob("saetze_f*.parquet"))
    if saetze:
        cv = pd.concat([pd.read_parquet(f, columns=["saat", "S", "praediktor", "budget", "b_code", "s_code"]) for f in saetze])
        tp = cv[(cv.saat == 0) & (cv.S == "S3") & (cv.praediktor == "hier_item") & (cv.budget == 0)][["b_code", "s_code"]].drop_duplicates()
        M = tp.merge(P80, on=["b_code", "s_code"], how="left")
        if M.kn.isna().any():
            raise SystemExit("Testpaare nicht in der Paartabelle gefunden (fail-closed)")
        out["l9_abgleich"].update({
            "testpaare": int(len(M)), "testpaare_benchmarks": int(M.b_code.nunique()),
            "kn_paargewichtet_testpaare_alle_items": float(M.kn_pair.mean()),
            "kn_antwortgewichtet_testpaare": float(M.kn.sum() / M.n.sum()),
            "L10_paargewichtet_testpaare_nur_wdh": float(M.L10_pair.dropna().mean()),
            "testpaare_mit_wdh_zellen": int((M.nrep > 0).sum()),
            "kn_paargewichtet_testpaare_je_benchmark_balanciert": float(M.groupby("b_code").kn_pair.mean().mean()),
        })
    else:
        out["l9_abgleich"]["testpaare"] = "nicht verfügbar (keine CV-Sätze)"

    # ---- Vergleich mit dem ersten Weg
    verg = {}
    ok = True
    if Path(a.erstweg).exists():
        A = json.loads(Path(a.erstweg).read_text())
        for key in ("zeilen_gesamt", "antworten_gesamt", "zeilen_mit_wiederholung", "benchmarks_mit_>=100_wdh_zellen"):
            verg[key] = {"A": A[key], "B": out[key], "gleich": A[key] == out[key]}
            ok &= A[key] == out[key]
        for key in ("schranke_antwortgewichtet_nur_wdh", "schranke_zellgewichtet_nur_wdh", "orakel_kn_alle_zellen",
                    "schranke_bm_balanciert_mittel"):
            rel = abs(out[key] - A[key]) / abs(A[key])
            verg[key] = {"A": A[key], "B": out[key], "rel_abw": rel, "innerhalb_toleranz": rel <= a.toleranz}
            ok &= rel <= a.toleranz
        for q in ("0.25", "0.5", "0.75"):
            av, bv = A["schranke_je_bm_quantile"][q], out["schranke_je_bm_quantile"][q]
            rel = abs(bv - av) / abs(av)
            verg[f"quantil_{q}"] = {"A": av, "B": bv, "rel_abw": rel, "innerhalb_toleranz": rel <= a.toleranz}
            ok &= rel <= a.toleranz
    else:
        verg["hinweis"] = f"Erstweg-Datei fehlt: {a.erstweg}"
        ok = False
    out["vergleich_mit_erstweg"] = verg
    out["urteil"] = "zwei Rechenwege innerhalb Toleranz" if ok else "ABWEICHUNG – Ursache schriftlich klären"
    out["kehrseite"] = ("Falsch, wenn die Population nicht dieselbe ist (Kontrollsummen oben) oder wenn beide Wege denselben Fehler "
                        "teilen: Wiederholungen gibt es nur, wo Kuratoren Trials erfasst haben (10 % der Zellen, 59 % der Antworten, "
                        "bridging_gap/monkey_power_laws dominieren die Antwortgewichtung); L10 ist eine Schranke auf dieser Teilmenge.")
    T.to_csv(HIER / "noise_floor_by_benchmark.csv", index=False, float_format="%.6g")
    (HIER / "wiederholung_b.json").write_text(json.dumps(out, indent=1, default=str))
    log(json.dumps({k: v for k, v in out.items() if k not in ("l9_abgleich", "vergleich_mit_erstweg")}, indent=1, default=str))
    log("L9-Abgleich:", json.dumps(out["l9_abgleich"], indent=1, default=str))
    log("Vergleich:", json.dumps(verg, indent=1, default=str))
    log("Urteil:", out["urteil"])
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
