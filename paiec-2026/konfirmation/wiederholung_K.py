"""wiederholung_K.py — H7 (Prereg v2 §4): irreduzible Antwortrausch-Schranke L10 je Benchmark.

L10_b = Σ n·k(n−k)/(n(n−1)) / Σ n über Zellen (Subjekt, Item) mit n >= 2 (antwortgewichtet, unverzerrter Schätzer der
Zellvarianz); Median und IQR über Benchmarks mit >= 100 solchen Zellen. Regel: Median >= 0.02; zweiter Rechenweg (P8,
curation/noise_floor_by_benchmark.csv, anderer Code/Autor) innerhalb 1 % (Median) — sonst beide Werte berichten.
Nicht saatabhängig (reine Datenstatistik); Rechenweg wie v2-plan/d-wissenschaft/wiederholung.py (gelesen).
Aufruf: python3 -I wiederholung_K.py --aus ergebnisse/wiederholung_K.json [--zweitweg ../kuratierung/noise_floor_by_benchmark.csv]
"""
import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402


def l10_je_benchmark():
    t = pq.read_table(ku.WORK / "agg.parquet", columns=["b_code", "n", "k"])
    n = t["n"].to_numpy().astype(np.float64)
    k = t["k"].to_numpy().astype(np.float64)
    b = t["b_code"].to_numpy()
    rep = n >= 2
    v = np.zeros_like(n)
    v[rep] = k[rep] * (n[rep] - k[rep]) / (n[rep] * (n[rep] - 1))
    df = pd.DataFrame({"b": b[rep], "n": n[rep], "nv": n[rep] * v[rep]})
    g = df.groupby("b").agg(zellen=("n", "size"), antworten=("n", "sum"), nv=("nv", "sum"))
    g["L10"] = g.nv / g.antworten
    gesamt = {"zeilen_gesamt": int(len(n)), "antworten_gesamt": int(n.sum()), "zellen_wdh": int(rep.sum()),
              "anteil_antworten_in_wdh_zellen": float(n[rep].sum() / n.sum()),
              "schranke_antwortgewichtet_nur_wdh": float((n[rep] * v[rep]).sum() / n[rep].sum())}
    return g, gesamt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", required=True)
    ap.add_argument("--zweitweg", default=str(ku.HIER.parent / "kuratierung" / "noise_floor_by_benchmark.csv"))
    a = ap.parse_args()
    erg = {"zeit_utc": ku.jetzt()}
    rc = 0
    try:
        ku.pruefe_work()
        g, gesamt = l10_je_benchmark()
        erg.update(gesamt)
        sel = g[g.zellen >= 100]
        q = sel.L10.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
        erg["benchmarks_mit_>=100_wdh_zellen"] = int(len(sel))
        erg["L10_median"] = float(q[0.5])
        erg["L10_iqr"] = [float(q[0.25]), float(q[0.75])]
        erg["L10_quantile"] = {str(k): float(v) for k, v in q.items()}
        erg["L10_bm_balanciert_mittel"] = float(sel.L10.mean())
        erg["regel"] = "Median >= 0.02 über Benchmarks mit >= 100 Wiederholungszellen; Zweitweg innerhalb 1 %"
        erg["median_ge_0_02"] = bool(q[0.5] >= 0.02)
        sel.reset_index().rename(columns={"b": "b_code"}).to_csv(Path(a.aus).with_suffix(".csv"), index=False)
        # Zweitweg (P8), nur lesen
        zw = Path(a.zweitweg)
        if zw.exists():
            z = pd.read_csv(zw)
            if {"b_code", "cells_rep", "L10_response_weighted"} <= set(z.columns):
                z = z[z.cells_rep >= 100].set_index("b_code")
                med_z = float(z.L10_response_weighted.median())
                j = sel.join(z[["L10_response_weighted"]], how="inner")
                erg["zweitweg"] = {"datei": str(zw), "n_benchmarks": int(len(z)), "median": med_z,
                                   "rel_abweichung_median": float(abs(med_z - q[0.5]) / q[0.5]),
                                   "max_abs_abweichung_je_benchmark": float((j.L10 - j.L10_response_weighted).abs().max()),
                                   "n_gemeinsam": int(len(j))}
                erg["zweitweg_innerhalb_1_prozent"] = bool(erg["zweitweg"]["rel_abweichung_median"] <= 0.01
                                                           and len(z) == len(sel))
            else:
                erg["zweitweg"] = {"datei": str(zw), "grund": "Spalten unbekannt", "spalten": list(z.columns)}
                erg["zweitweg_innerhalb_1_prozent"] = None
        else:
            erg["zweitweg"] = {"datei": str(zw), "grund": "fehlt"}
            erg["zweitweg_innerhalb_1_prozent"] = None
        if not erg["median_ge_0_02"]:
            erg["verdict"] = "failed"
        elif erg["zweitweg_innerhalb_1_prozent"] is None:
            erg["verdict"] = "passed_zweitweg_offen"
        else:
            erg["verdict"] = "passed" if erg["zweitweg_innerhalb_1_prozent"] else "passed_zweitweg_abweichend"
    except Exception as e:  # noqa: BLE001
        erg["fehler"] = f"{type(e).__name__}: {e}"
        erg["traceback"] = traceback.format_exc()
        erg["verdict"] = "not_evaluated"
        rc = 2
    ku.schreibe_json(a.aus, erg)
    print("H7:", erg.get("verdict"), "Median", erg.get("L10_median"), "IQR", erg.get("L10_iqr"), "n", erg.get("benchmarks_mit_>=100_wdh_zellen"),
          "Zweitweg", erg.get("zweitweg", {}).get("median"))
    if rc:
        print("FEHLER:", erg.get("fehler"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
