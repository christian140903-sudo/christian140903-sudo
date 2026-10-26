"""b0lage_K.py — H6 (Prereg v2 §4): sichtbare Nicht-Text-Item-Aggregate sagen die Benchmark-Lage bei B0 nicht vorher.

Merkmalsmenge B (eingefroren in der Prereg): Quantile P10/P25/P50/P75/P90 von log(1+Textlänge), log10 Itemzahl, Anteil
Items mit nicht-leerem item_features, Zahl verschiedener Schlüssel, Shannon-Entropie der Schlüsselverteilung, Anteil
numerisch bewerteter Schlüssel, Indikatoren der 20 häufigsten Schlüsselnamen (Häufigkeit = Zahl der Benchmarks mit dem
Schlüssel). Ziel: mittlere Paarquote R_b je Benchmark (Paare mit >= 80 Items, paare.parquet) und logit(R_b) (geklemmt
0,005–0,995). Ridge mit unpenalisiertem Achsenabschnitt, LOBO-R²; λ ∈ {3, 10, 30, 100, 300} je äußerem Benchmark durch
inneres LOBO (geschlossene Leave-one-out-Formel). Regel: LOBO-R² <= 0.05 für beide Ziele.
Daten: PAIEC_WORK/basis/items/<folder>.parquet (content_len, item_features), PAIEC_WORK/modell/{paare,benchmarks}.parquet.
Aufruf: python3 -I b0lage_K.py --aus ergebnisse/b0lage_K.json
"""
import argparse
import os
import re
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402

LAMBDAS = (3.0, 10.0, 30.0, 100.0, 300.0)
TOP_K = 20
NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def schluessel(feats):
    """-> (Anzahl Schlüssel-Vorkommen je Name, Anzahl numerischer Werte, Anzahl Werte gesamt)."""
    cnt, num, tot = {}, 0, 0
    for s in feats:
        if not s:
            continue
        for part in s.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                cnt[k] = cnt.get(k, 0) + 1
                tot += 1
                if NUM.match(v.strip()):
                    num += 1
    return cnt, num, tot


def merkmale_je_benchmark(bm, items_dir):
    rows, key_presence = [], {}
    for _, b in bm.iterrows():
        p = items_dir / f"{b.folder}.parquet"
        if not p.exists():
            continue
        t = pq.read_table(p, columns=["content_len", "item_features"]).to_pandas()
        L = np.log1p(t.content_len.fillna(0).astype(float).clip(lower=0))
        feats = t.item_features.fillna("").astype(str).tolist()
        cnt, num, tot = schluessel(feats)
        probs = np.array(list(cnt.values()), float)
        ent = float(-(probs / probs.sum() * np.log(probs / probs.sum())).sum()) if probs.size else 0.0
        r = {"b_code": int(b.b_code), "folder": b.folder,
             "len_p10": L.quantile(.10), "len_p25": L.quantile(.25), "len_p50": L.quantile(.50),
             "len_p75": L.quantile(.75), "len_p90": L.quantile(.90), "log10_items": np.log10(max(len(t), 1)),
             "share_feat": float(np.mean([len(s) > 0 for s in feats])) if feats else 0.0,
             "n_keys": len(cnt), "key_entropy": ent, "share_numeric": (num / tot) if tot else 0.0}
        rows.append(r)
        for k in cnt:
            key_presence[k] = key_presence.get(k, 0) + 1
    X = pd.DataFrame(rows).set_index("b_code")
    top = sorted(key_presence, key=lambda k: (-key_presence[k], k))[:TOP_K]
    # Indikatoren nachtragen (zweiter Durchlauf über die gespeicherten Schlüsselmengen wäre teurer; hier aus Datei)
    ind = {k: [] for k in top}
    for _, b in bm.iterrows():
        p = items_dir / f"{b.folder}.parquet"
        if not p.exists() or int(b.b_code) not in X.index:
            continue
        t = pq.read_table(p, columns=["item_features"]).to_pandas()
        cnt, _, _ = schluessel(t.item_features.fillna("").astype(str).tolist())
        for k in top:
            ind[k].append(1.0 if k in cnt else 0.0)
    for k in top:
        X["key:" + k] = ind[k]
    return X, top, key_presence


def ridge_loo_mse(X, y, lam):
    """LOO-MSE einer Ridge mit unpenalisiertem Achsenabschnitt (geschlossene Form e_i/(1−h_ii))."""
    n, p = X.shape
    Xa = np.hstack([np.ones((n, 1)), X])
    P = lam * np.eye(p + 1)
    P[0, 0] = 0.0
    A = np.linalg.solve(Xa.T @ Xa + P, Xa.T)
    H = Xa @ A
    beta = A @ y
    res = y - Xa @ beta
    h = np.diag(H)
    loo = res / (1 - h)
    return float(np.mean(loo ** 2)), beta


def lobo_r2(X, y):
    n = len(y)
    pred = np.zeros(n)
    lam_wahl = []
    for i in range(n):
        m = np.ones(n, bool)
        m[i] = False
        Xt, yt = X[m], y[m]
        best = min(LAMBDAS, key=lambda l: ridge_loo_mse(Xt, yt, l)[0])
        _, beta = ridge_loo_mse(Xt, yt, best)
        pred[i] = beta[0] + X[i] @ beta[1:]
        lam_wahl.append(best)
    mse = float(np.mean((y - pred) ** 2))
    return 1.0 - mse / float(np.var(y)), pred, lam_wahl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    erg = {"zeit_utc": ku.jetzt(), "merkmalsmenge": "B (Prereg §4 H6)"}
    rc = 0
    try:
        ku.pruefe_work()
        basis = Path(os.environ["PAIEC_WORK"]) / "basis"
        paare = pd.read_parquet(ku.WORK / "paare.parquet")
        paare = paare[paare["items"] >= 80]
        bm = pd.read_parquet(ku.WORK / "benchmarks.parquet")
        bm = bm[bm.b_code.isin(paare.b_code.unique())][["b_code", "folder"]]
        tgt = paare.groupby("b_code").agg(R=("r", "mean"), n_paare=("r", "size"))
        tgt["logit_R"] = np.log(tgt.R.clip(0.005, 0.995) / (1 - tgt.R.clip(0.005, 0.995)))
        X, top, kp = merkmale_je_benchmark(bm, basis / "items")
        X = X.join(tgt, how="inner")
        if len(X) < 100:
            raise ku.KonfError(f"nur {len(X)} Benchmarks mit Merkmalen")
        feat_cols = [c for c in X.columns if c not in ("folder", "R", "n_paare", "logit_R")]
        A = X[feat_cols].values.astype(float)
        A = (A - A.mean(0)) / (A.std(0) + 1e-9)
        erg["n_benchmarks"] = int(len(X))
        erg["n_merkmale"] = len(feat_cols)
        erg["top20_schluessel"] = {k: kp[k] for k in top}
        res = {}
        for ziel in ("R", "logit_R"):
            y = X[ziel].values.astype(float)
            r2, pred, lam = lobo_r2(A, y)
            res[ziel] = {"r2_lobo": float(r2), "var_y": float(np.var(y)), "mse_lobo": float(np.mean((y - pred) ** 2)),
                         "lambda_wahl_haeufigkeit": {str(l): int(sum(1 for x in lam if x == l)) for l in LAMBDAS}}
            X["pred_" + ziel] = pred
        erg["ergebnis"] = res
        erg["regel"] = "LOBO-R² <= 0.05 für R_b und logit(R_b)"
        erg["verdict"] = "passed" if all(res[z]["r2_lobo"] <= 0.05 for z in res) else "failed"
        X.drop(columns=[c for c in X.columns if c.startswith("key:")]).to_csv(Path(a.aus).with_suffix(".csv"))
    except Exception as e:  # noqa: BLE001
        erg["fehler"] = f"{type(e).__name__}: {e}"
        erg["traceback"] = traceback.format_exc()
        erg["verdict"] = "not_evaluated"
        rc = 2
    ku.schreibe_json(a.aus, erg)
    print("H6:", erg.get("verdict"), erg.get("ergebnis"), "n_bm", erg.get("n_benchmarks"), "n_merk", erg.get("n_merkmale"))
    if rc:
        print("FEHLER:", erg.get("fehler"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
