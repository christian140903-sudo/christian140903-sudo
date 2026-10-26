"""Trainingsdaten aus der lokalen Basis (measurement-db, HF-Revision 54074453, nur formatted_tables).

Erzeugt (unter --aus, Standard $PAIEC_WORK/modell/):
  agg.parquet       je (b_code, s_code, i_code): n = Zahl benoteter Antworten, k = Summe der Antworten (binär)
  subjekte.parquet  je s_code: die 8 Testzeit-Felder als Strings ("" = fehlt), Schlüssel konfig/name, Ausschlussgrund
  benchmarks.parquet  Auswahl + Gründe
Auswahl: response_type == binary, release == public, coverage > 0. Antworten roh (keine Drehung), NULL verworfen.
Ausschlüsse aus der eigenen Datenprüfung (daten/lieferung/csv, Befunde 3 und 4), weil sie Labels verfälschen:
  bird_sql: Konfigurationen mit all_rows_graded_0 == True (Befund 3, 64 von 120)
  swebench_live: Subjekte der Kategorie "website report subject: only resolved list graded" (Befund 4)
Befunde 5/6 (zwei Konfigurationen in einem subject_id) bleiben drin: das ist für den Prädiktor eine Mischung, kein
falsches Label; sie werden im Bericht als Rauschquelle genannt.
Aufruf: python3 -I daten.py [--aus DIR]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

SCRATCH = Path(os.environ.get("PAIEC_WORK", "work"))
BASIS = SCRATCH / "basis"
LIEFERUNG = Path(__file__).resolve().parents[1] / "daten" / "lieferung" / "csv"
FELDER = ("normalized_name", "provider", "release_date", "access_date", "harness", "harness_version",
          "reasoning_effort", "subject_features_extra")


def als_text(x):
    """Wert -> Testzeit-String. Datumswerte als JJJJ-MM-TT (Annahme, offen: Format der Plattform)."""
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
        return ""
    if isinstance(x, pd.Timestamp):
        return x.strftime("%Y-%m-%d")
    if hasattr(x, "isoformat") and not isinstance(x, str):
        return x.isoformat()[:10]
    if isinstance(x, (dict, list)):
        return json.dumps(x, sort_keys=True, ensure_ascii=False)
    return str(x)


def lade_ausschluesse():
    aus = {}
    f3 = pd.read_csv(LIEFERUNG / "F3a_bird_sql_configurations.csv")
    for sid in f3.loc[f3.all_rows_graded_0.astype(str) == "True", "subject_id"]:
        aus[("bird_sql", sid)] = "befund3_bird_sql_alle_0"
    f4 = pd.read_csv(LIEFERUNG / "F4_swebench_live_subjects.csv")
    for sid in f4.loc[f4.category.str.startswith("website report subject: only resolved"), "subject_id"]:
        aus[("swebench_live", sid)] = "befund4_swebench_live_nur_1"
    return aus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", default=str(SCRATCH / "modell"))
    a = ap.parse_args()
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    bm = pd.read_parquet(BASIS / "benchmarks.parquet")
    wahl = bm[(bm.response_type == "binary") & (bm.release == "public")].copy()
    wahl["grund"] = np.where(wahl.coverage.fillna(0) <= 0, "coverage_0", "")
    sub = pd.read_parquet(BASIS / "subjects.parquet")
    for f in FELDER:
        sub[f] = [als_text(x) for x in sub[f]]
    sub["konfig"] = [json.dumps([r[f] for f in FELDER], ensure_ascii=False) for r in sub[list(FELDER)].to_dict("records")]
    ausschl = lade_ausschluesse()
    sub["ausschluss"] = [ausschl.get((b, s), "") for b, s in zip(sub.benchmark_id, sub.subject_id)]
    n_aus = (sub.ausschluss != "").sum()
    print(f"Subjekt-Ausschlüsse: {n_aus} ({sub.ausschluss.value_counts().to_dict()})", flush=True)
    s_aus = set(sub.loc[sub.ausschluss != "", "s_code"].tolist())

    resp = ds.dataset(str(BASIS / "responses"), format="parquet", partitioning="hive")
    teile = []
    for _, b in wahl[wahl.grund == ""].sort_values("b_code").iterrows():
        t = resp.to_table(filter=(ds.field("b_code") == int(b.b_code)) & ds.field("response").is_valid(),
                          columns=["s_code", "i_code", "response"]).to_pandas()
        if len(t) == 0:
            continue
        if s_aus:
            t = t[~t.s_code.isin(s_aus)]
        g = t.groupby(["s_code", "i_code"], sort=False)["response"].agg(["size", "sum"]).reset_index()
        g.columns = ["s_code", "i_code", "n", "k"]
        g["b_code"] = np.int16(b.b_code)
        teile.append(g.astype({"s_code": "int32", "i_code": "int32", "n": "int32", "k": "float32"}))
    agg = pd.concat(teile, ignore_index=True)
    assert np.all((agg.k >= 0) & (agg.k <= agg.n)), "binäre Werte außerhalb {0,1}"
    agg["k"] = agg.k.round().astype("int32")
    agg = agg[["b_code", "s_code", "i_code", "n", "k"]]
    agg.to_parquet(aus / "agg.parquet", index=False)
    sub.to_parquet(aus / "subjekte.parquet", index=False)
    wahl.drop(columns=["description"], errors="ignore").to_parquet(aus / "benchmarks.parquet", index=False)
    zus = {"zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "revision": "54074453",
           "benchmarks_binaer_public": int(len(wahl)), "benchmarks_coverage_0": int((wahl.grund != "").sum()),
           "benchmarks_mit_daten": int(agg.b_code.nunique()), "zeilen_subjekt_item": int(len(agg)),
           "antworten": int(agg.n.sum()), "erfolge": int(agg.k.sum()), "subjekt_ausschluesse": int(n_aus),
           "dauer_s": round(time.time() - t0, 1)}
    (aus / "daten_zusammenfassung.json").write_text(json.dumps(zus, indent=1))
    print(json.dumps(zus, indent=1))


if __name__ == "__main__":
    sys.exit(main())
