"""liga_vergleich.json aus paar_alc.parquet (Ausgabe von liga_auswertung.py).

Aufruf: PAIEC_WORK=... python3 -I liga_vergleich.py --aus <ergebnisse-ordner>
Je Regime und Familie: Brier-ALC (Mittel über Paare) mit 95-%-KI (SE cluster-robust über Benchmarks), gepaarte
Differenz zu v1 (hier_item) als ALC und je Budget B0..B31, jeweils ± Cluster-SE und 95-%-KI; Urteil nach
metrik.cluster_vergleich (mittel + 2 SE < 0 → „besser"). Alles discovery (Saaten 0–2, Testpaare je Benchmark auf 30
gekappt); fehlende Familien/Falten werden als "not evaluated" eingetragen, nie geschätzt.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parents[1] / "modell"))
import metrik  # noqa: E402

V1 = "v1_hier_item"
REGIME = ["S1", "S2", "S3", "S30", "kompakt10"]
FAMILIEN = ["empirischer_mittelwert", "beta_binomial", "irt1pl", "irt2pl", "mf", "knn", "gb", "stack",
            "v1_ohne_itemstufe", "konstant_0.5"]
SPALTEN = ["alc"] + [f"B{b}" for b in metrik.BUDGETS]


def ki_mittel(werte, cluster):
    """Mittel ± cluster-robuste SE (Benchmarks) für eine Spalte (kein Vergleich, nur Niveau)."""
    out = metrik.cluster_vergleich(list(werte), list(cluster))
    return {"mittel": out.get("mittel"), "se": out.get("se"), "ki95": out.get("ki95"), "n_paare": out["n_paare"],
            "n_benchmarks": out.get("n_cluster")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    aus = Path(a.aus)
    pa = pd.read_parquet(aus / "paar_alc.parquet")
    meta = json.loads((aus / "meta.json").read_text())
    falten = meta["falten"]
    erg = {"erzeugt_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "final (10/10 Falten)" if len(falten) == 10 else f"VORLÄUFIG ({len(falten)}/10 Falten: {falten})",
           "kennzeichnung": "discovery — Saaten 0,1,2; Testpaare je Benchmark auf 30 gekappt; Hyperparameter nur auf "
                            "Trainingsbenchmarks der Falte (innere 75/25, Saat 100); v1-Sätze aus cv_REG2 übernommen",
           "metrik": "Brier itemgenau je Paar, ALC-Gewichte 0.1/0.2/0.2/0.2/0.2/0.1 über Budgets 0,1,3,7,15,31; "
                     "Differenz = Familie − v1 (negativ = Familie besser); SE cluster-robust über Benchmarks; "
                     "Urteil: mittel + 2·SE < 0 → besser, mittel − 2·SE > 0 → schlechter (P(Fehlurteil|Nulleffekt) = 2,3 %)",
           "falten": falten, "saaten": meta["saaten"], "referenz": V1, "regime": {}}
    for S in REGIME:
        x = pa[pa.S == S]
        if x.empty:
            erg["regime"][S] = "not evaluated"
            continue
        v1 = x[x.praediktor == V1].set_index(["b_code", "s_code"])
        blk = {"n_paare": int(len(v1)), "n_benchmarks": int(v1.b_code.nunique() if "b_code" in v1 else len(set(i[0] for i in v1.index))),
               "v1_hier_item": {c: ki_mittel(v1[c], [i[0] for i in v1.index]) for c in SPALTEN}, "familien": {}}
        for fam in FAMILIEN:
            f = x[x.praediktor == fam].set_index(["b_code", "s_code"])
            if f.empty:
                blk["familien"][fam] = "not evaluated"
                continue
            j = f[SPALTEN + ["falte"]].join(v1[SPALTEN], rsuffix="_v1", how="inner")
            cl = [i[0] for i in j.index]
            fb = {"niveau": {c: ki_mittel(j[c], cl) for c in SPALTEN}, "differenz_zu_v1": {}}
            for c in SPALTEN:
                d = (j[c] - j[f"{c}_v1"])
                out = metrik.cluster_vergleich(d.tolist(), cl)
                out.pop("schwelle", None)
                je_f = d.groupby(j.falte).mean()
                out["se_falten"] = float(je_f.std(ddof=1) / math.sqrt(len(je_f))) if len(je_f) > 1 else None
                out["falten_mit_vorteil"] = int((je_f < 0).sum())
                out["n_falten"] = int(len(je_f))
                fb["differenz_zu_v1"][c] = out
            blk["familien"][fam] = fb
        erg["regime"][S] = blk
    (aus / "liga_vergleich.json").write_text(json.dumps(erg, indent=1, ensure_ascii=False))
    # Kurzausgabe
    print(erg["status"])
    for S in ("S1", "S3", "S30"):
        b = erg["regime"][S]
        if b == "not evaluated":
            continue
        print(f"--- {S}: ALC-Differenz zu v1 (mittel [KI95], Urteil) | Differenz bei B1 und B31")
        for fam, fb in b["familien"].items():
            if fb == "not evaluated":
                print(f"  {fam:24s} not evaluated")
                continue
            d = fb["differenz_zu_v1"]
            k = d["alc"]["ki95"]
            print(f"  {fam:24s} {d['alc']['mittel']:+.5f} [{k[0]:+.5f}, {k[1]:+.5f}] {d['alc']['urteil']:24s} "
                  f"B1 {d['B1']['mittel']:+.5f}±{d['B1']['se']:.5f}  B31 {d['B31']['mittel']:+.5f}±{d['B31']['se']:.5f}")


if __name__ == "__main__":
    main()
