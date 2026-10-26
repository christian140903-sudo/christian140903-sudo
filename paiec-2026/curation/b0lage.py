#!/usr/bin/env python3
"""B0-Negativbefund, zweiter Rechenweg (P8): Lässt sich die Benchmark-Lage (mittlere Erfolgsquote R_b der Paare) ohne Labels
aus zur Testzeit sichtbaren, text-freien Item-Aggregaten vorhersagen? Leave-one-benchmark-out (LOBO) über 142 Benchmarks.

Unabhängig von v2-plan/d-merkmale/b0lage.py (anderer Autor): eigene Merkmalsdefinition (Längen-Quantile, Itemzahl,
Schlüsselindikatoren der 20 häufigsten item_features-Schlüssel, Werteanzahl je Schlüssel, Anteil Items mit Merkmalen),
λ der Ridge-Regression **verschachtelt** (inneres LOO auf den 141 Trainingsbenchmarks) statt nachträglich nach LOBO-R²
gewählt, zusätzlich zwei Referenzen ohne Regression: Konstante und k-nächste-Benchmarks (k = 5, euklidisch im Merkmalsraum).
Keine Item-Texte werden gelesen; nur content_len und item_features (Schlüssel/Werte der Kuratoren).

Ausgabe: b0lage_b.json (R² LOBO, Quadratfehler B0 benchmark-balanciert, Extrembenchmarks), b0lage_b.csv (je Benchmark:
b_code, benchmark_id, R_b, Vorhersagen). Fail-closed bei fehlender Datei. rc 0 = gelaufen (der Befund selbst ist keine
Bedingung: er wird berichtet, wie er fällt).
Aufruf: PAIEC_WORK=... OMP_NUM_THREADS=1 python3 -I b0lage.py
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
WORK = Path(os.environ.get("PAIEC_WORK", "work"))
BASIS = WORK / "basis"
LAMBDAS = (1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
TOP_KEYS = 20
T0 = time.time()


def schluessel_werte(feats: pd.Series):
    """item_features 'k=v;k=v' -> dict Schlüssel -> Menge der Werte (Stichprobe bis 20 000 Items)."""
    kv = {}
    for s in feats.head(20000):
        if not s:
            continue
        for teil in s.split(";"):
            if "=" in teil:
                k, v = teil.split("=", 1)
                kv.setdefault(k.strip(), set()).add(v.strip())
    return kv


def ridge_fit(X, y, lam):
    mu_x, sd_x = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu_x) / sd_x
    mu_y = y.mean()
    beta = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - mu_y))
    return mu_x, sd_x, mu_y, beta


def ridge_pred(fit, x):
    mu_x, sd_x, mu_y, beta = fit
    return mu_y + ((x - mu_x) / sd_x) @ beta


def lobo_nested(X, y):
    """Äußeres LOBO; inneres LOO wählt λ nur auf den Trainingsbenchmarks."""
    n = len(y)
    pred = np.zeros(n)
    lam_gewaehlt = []
    for i in range(n):
        m = np.ones(n, bool)
        m[i] = False
        Xt, yt = X[m], y[m]
        best = None
        for lam in LAMBDAS:
            se = 0.0
            for j in range(len(yt)):
                mm = np.ones(len(yt), bool)
                mm[j] = False
                f = ridge_fit(Xt[mm], yt[mm], lam)
                se += (ridge_pred(f, Xt[j]) - yt[j]) ** 2
            if best is None or se < best[0]:
                best = (se, lam)
        lam_gewaehlt.append(best[1])
        f = ridge_fit(Xt, yt, best[1])
        pred[i] = ridge_pred(f, X[i])
    return pred, lam_gewaehlt


def lobo_knn(X, y, k=5):
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    n = len(y)
    pred = np.zeros(n)
    for i in range(n):
        d = np.sqrt(((Z - Z[i]) ** 2).sum(1))
        d[i] = np.inf
        nn = np.argsort(d)[:k]
        pred[i] = y[nn].mean()
    return pred


def main():
    paare = pd.read_parquet(WORK / "modell" / "paare.parquet", columns=["b_code", "r"])
    bm = pd.read_parquet(BASIS / "benchmarks.parquet", columns=["b_code", "folder", "direction"])
    ziel = paare.groupby("b_code").agg(R=("r", "mean"), n_paare=("r", "size")).join(bm.set_index("b_code"), how="inner")
    rows, kv_alle = [], []
    for b, z in ziel.iterrows():
        p = BASIS / "items" / f"{z.folder}.parquet"
        if not p.exists():
            raise SystemExit(f"fehlt: {p} (fail-closed)")
        it = pd.read_parquet(p, columns=["content_len", "item_features"])
        L = np.log1p(it.content_len.fillna(0).astype(float).values)
        feats = it.item_features.fillna("").astype(str)
        kv = schluessel_werte(feats)
        kv_alle.append(kv)
        rows.append({"b_code": int(b), "benchmark_id": z.folder, "R": float(z.R), "n_paare": int(z.n_paare), "direction": z.direction,
                     "len_q10": np.quantile(L, .1), "len_q25": np.quantile(L, .25), "len_q50": np.quantile(L, .5),
                     "len_q75": np.quantile(L, .75), "len_q90": np.quantile(L, .9), "len_sd": L.std(),
                     "log_n_items": np.log10(len(it)), "anteil_mit_features": float((feats.str.len() > 0).mean()),
                     "n_keys": len(kv), "max_werte_je_key": max([len(v) for v in kv.values()], default=0),
                     "_kv": kv})
    D = pd.DataFrame(rows)
    # Schlüsselindikatoren: die TOP_KEYS häufigsten Schlüssel über alle 142 Benchmarks (Vorhandensein + log Werteanzahl)
    haeufig = pd.Series([k for kv in kv_alle for k in kv]).value_counts().head(TOP_KEYS).index.tolist()
    for k in haeufig:
        D[f"hat:{k}"] = [float(k in kv) for kv in D._kv]
        D[f"nwerte:{k}"] = [np.log1p(len(kv.get(k, ()))) for kv in D._kv]
    merk = [c for c in D.columns if c not in ("b_code", "benchmark_id", "R", "n_paare", "direction", "_kv")]
    X = D[merk].values.astype(float)
    y = D.R.values.astype(float)
    pred_r, lams = lobo_nested(X, y)
    pred_knn = lobo_knn(X, y, 5)
    pred_const = np.array([np.delete(y, i).mean() for i in range(len(y))])   # LOBO-Konstante (ehrlich)
    def r2(p):
        return float(1 - ((y - p) ** 2).mean() / y.var())
    ext = (y < 0.15) | (y > 0.85)
    res = {"zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_benchmarks": int(len(y)), "n_merkmale": len(merk),
           "var_R": float(y.var()),
           "r2_lobo_ridge_nested": r2(pred_r), "r2_lobo_knn5": r2(pred_knn), "r2_lobo_konstante": r2(pred_const),
           "lambda_gewaehlt_haeufigkeit": {str(k): int(v) for k, v in pd.Series(lams).value_counts().items()},
           "B0_sq_konstante_lobo": float(((y - pred_const) ** 2).mean()),
           "B0_sq_ridge": float(((y - pred_r) ** 2).mean()), "B0_sq_knn5": float(((y - pred_knn) ** 2).mean()),
           "n_extrem": int(ext.sum()),
           "extrem_mittlerer_abs_fehler_ridge": float(np.abs(y - pred_r)[ext].mean()),
           "extrem_mittlerer_abs_fehler_konstante": float(np.abs(y - pred_const)[ext].mean()),
           "lower_is_better": [{"benchmark_id": r.benchmark_id, "R": round(r.R, 3), "pred_ridge": round(pr, 3), "pred_knn5": round(pk, 3)}
                               for r, pr, pk in zip(D.itertuples(), pred_r, pred_knn) if r.direction == "lower_is_better"],
           "merkmale": merk}
    res["urteil"] = ("Negativbefund bestätigt: kein LOBO-R² > 0 für Ridge (verschachtelt) oder kNN"
                     if res["r2_lobo_ridge_nested"] <= 0 and res["r2_lobo_knn5"] <= 0 else
                     "ABWEICHUNG vom Erstweg: positives LOBO-R² – schriftlich klären")
    res["kehrseite"] = ("Falsch, wenn semantischer Item-Text (Embedding/LLM) die Lage trägt – das ist hier nicht geprüft, weil kein Text "
                        "geladen ist; der Befund gilt nur für Längen- und Schlüssel-Aggregate. Falsch auch, wenn die Plattform "
                        "Testbenchmarks mit anderen Schlüsselkonventionen ausliefert.")
    D.drop(columns=["_kv"]).assign(pred_ridge=pred_r, pred_knn5=pred_knn, pred_konstante=pred_const).to_csv(HIER / "b0lage_b.csv", index=False, float_format="%.5g")
    (HIER / "b0lage_b.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "merkmale"}, indent=1))
    print(f"[{time.time() - T0:.0f}s] fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
