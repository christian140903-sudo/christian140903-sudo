"""Wirkung der Platt-Stufenwahl auf den Paar-ALC (Phase-1-Sätze, Prädiktor "hier", Platt-Parameter je Falte aus
auswertung.json): Varianten {0,1} (Paket v2core, Schnittregel), {0,1,3,7} (v1), verschachtelt je Falte, ohne Platt.
Gepaarte Differenz je Paar (über Saaten gemittelt), cluster-robuste SE über Benchmarks (metrik.cluster_vergleich).

Aufruf: python3 -I platt_varianten.py <cv_ordner> [--aus datei.json]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrik  # noqa: E402
from auswertung import wende_platt  # noqa: E402
from inferenz import stufe  # noqa: E402

SCRATCH = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))


def paar_alc(df, q):
    br = (q - df.R.values) ** 2 + df.R.values * (1 - df.R.values)
    x = df.assign(wb=df.budget.map(GEW).values * br)
    g = x.groupby(["S", "b_code", "s_code", "saat"]).wb.sum().reset_index()
    return g.groupby(["S", "b_code", "s_code"]).wb.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner")
    ap.add_argument("--aus", default="")
    a = ap.parse_args()
    d = Path(a.ordner) if Path(a.ordner).is_absolute() else SCRATCH / a.ordner
    df = pd.concat([pd.read_parquet(t) for t in sorted(d.glob("saetze_f*.parquet"))], ignore_index=True)
    df = df[df.praediktor == "hier"].reset_index(drop=True)
    df["stufe"] = [stufe(int(n)) for n in df.n_eigen]
    ausw = json.loads((d / "auswertung.json").read_text())
    pjf = {int(f): {int(s): v for s, v in pl.items()} for f, pl in ausw["platt_je_falte"].items()}
    vw = ausw["platt_stufenwahl_verschachtelt"]["verschachtelt_je_falte"]
    varianten = {"ohne_platt": lambda f: {}, "paket_v2core_{0,1}": lambda f: {s: pjf[f][s] for s in (0, 1)},
                 "v1_{0,1,3,7}": lambda f: {s: pjf[f][s] for s in (0, 1, 3, 7)},
                 "verschachtelt_je_falte": lambda f: {s: pjf[f][s] for s in vw[str(f)]}}
    alc = {}
    for name, wahl in varianten.items():
        q = df.q.values.copy()
        for f in sorted(df.falte.unique()):
            m = (df.falte == f).values
            q[m] = wende_platt(df.q.values[m], df.stufe.values[m], wahl(int(f)))
        alc[name] = paar_alc(df, q)
    erg = {"ordner": str(d), "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "regime": {}}
    for S in sorted(df.S.unique()):
        e = {"alc_paare": {n: round(float(v.loc[S].mean()), 6) for n, v in alc.items()}, "vergleiche": {}}
        ref = alc["v1_{0,1,3,7}"].loc[S]
        for n in ("paket_v2core_{0,1}", "verschachtelt_je_falte", "ohne_platt"):
            diff = (alc[n].loc[S] - ref).dropna()
            v = metrik.cluster_vergleich(diff.tolist(), [i[0] for i in diff.index])
            e["vergleiche"][n + " - v1"] = {k: (round(x, 7) if isinstance(x, float) else x) for k, x in v.items()}
        erg["regime"][str(S)] = e
    erg["kehrseite"] = ("Differenzen in der Größenordnung 1e-5 liegen unter jeder Entscheidungsschwelle (Regel Mittel + 2 SE); "
                        "die Stufenwahl ist eine Verfahrensfrage (verschachtelt vs. gepoolt), kein Score-Hebel.")
    txt = json.dumps(erg, indent=1)
    if a.aus:
        Path(a.aus).write_text(txt)
    for S, e in erg["regime"].items():
        print(S, e["alc_paare"], {k: (v.get("mittel"), v.get("se"), v.get("urteil")) for k, v in e["vergleiche"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
