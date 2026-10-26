"""Auswertung eines Akquise-Laufs: Paar-ALC je (Regime, Ordnung, Split, Politik, Prädiktor), gepaarte Differenz zur
Replik `zufall` (gleicher Prädiktor, gleiche Zellen, gemeinsame Zufallszahlen), SE cluster-robust über Benchmarks
(metrik.cluster_vergleich, Regel Mittel + 2 SE < 0 = besser, Mittel - 2 SE > 0 = schlechter), Zähler aus akquise_f*.json.

  python3 -I auswertung_akquise.py --name voll [--kennlinie C_voll_S3,C_voll_k10]  -> <lauf>/tabelle.json
Mit --kennlinie: Pilot-Modus, projiziert SE auf die volle Benchmarkzahl (SE_voll = SE_pilot * sqrt(C_pilot / C_voll)), MDE = 2 SE_voll,
und wendet die vorab festgelegte Regel an (MDE kompakt10 > 0,0025 -> 5 Saaten).
Fail-closed: fehlende/inkonsistente Eingaben -> SystemExit != 0.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
MODELL = Path(os.environ.get("PAIEC_MODELL", HIER.parents[1] / "modell"))
sys.path.insert(0, str(MODELL))
import metrik  # noqa: E402

AUS_BASIS = Path(os.environ.get("PAIEC_WORK", "work")) / "akquise"
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))
ZELLE = ["S", "ordnung", "split", "praediktor"]


def lade(name):
    d = AUS_BASIS / name
    teile = sorted(d.glob("saetze_f*.parquet"))
    if not teile:
        raise SystemExit(f"keine Sätze in {d}")
    df = pd.concat([pd.read_parquet(t) for t in teile], ignore_index=True)
    status = json.loads((d / "status.json").read_text())
    if status["fertig"] != status["falten_angefordert"]:
        raise SystemExit(f"Lauf unvollständig: {status}")
    zaehler = []
    for z in sorted(d.glob("akquise_f*.json")):
        zaehler.extend(json.loads(z.read_text()))
    return d, df, pd.DataFrame(zaehler), len(teile)


def paar_alc(df):
    df = df.assign(wb=df.budget.map(GEW) * df.brier)
    keys = ZELLE + ["politik", "b_code", "s_code"]
    g = df.groupby(keys + ["saat"], sort=False).agg(alc=("wb", "sum"), n_b=("budget", "size")).reset_index()
    if (g.n_b != len(metrik.BUDGETS)).any():
        raise SystemExit("Paar ohne alle sechs Budgets")
    pa = g.groupby(keys, sort=False).agg(alc=("alc", "mean"), n_saaten=("saat", "size")).reset_index()
    return pa


def abdeckung(df):
    """Mittel der Bewertungs-Items mit Fremdlabels je Budget (n_items_angepasst), je Zelle x Politik."""
    x = df[df.praediktor == "hier_item"]
    t = x.groupby(["S", "ordnung", "split", "politik", "budget"]).n_items_angepasst.mean().reset_index()
    out = {}
    for (S, o, sp, pol), g in t.groupby(["S", "ordnung", "split", "politik"]):
        out.setdefault(f"{S}|{o}|{sp}", {})[pol] = {f"B{int(b)}": round(float(v), 3)
                                                   for b, v in zip(g.budget, g.n_items_angepasst)}
    return out


def vergleiche(pa):
    out = []
    for zelle, g in pa.groupby(ZELLE, sort=False):
        ref = g[g.politik == "zufall"].set_index(["b_code", "s_code"]).alc
        if ref.empty:
            continue
        for pol, h in g[g.politik != "zufall"].groupby("politik", sort=False):
            m = h.set_index(["b_code", "s_code"]).alc
            j = pd.concat([m, ref], axis=1, keys=["m", "r"]).dropna()
            d = (j.m - j.r)
            cv = metrik.cluster_vergleich(d.tolist(), [i[0] for i in d.index])
            cv.update(dict(zip(ZELLE, zelle)), politik=pol, referenz="zufall",
                      alc_politik=float(j.m.mean()), alc_zufall=float(j.r.mean()),
                      n_identisch=int((d.abs() < 1e-15).sum()))
            out.append({k: (round(v, 7) if isinstance(v, float) else v) for k, v in cv.items()})
    return out


def tabelle(pa):
    out = {}
    for (S, o, sp, pr, pol), g in pa.groupby(ZELLE + ["politik"], sort=False):
        out.setdefault(f"{S}|{o}|{sp}|{pr}", {})[pol] = {
            "alc_paare": round(float(g.alc.mean()), 5), "n_paare": int(len(g)),
            "n_benchmarks": int(g.b_code.nunique()), "n_saaten": int(g.n_saaten.iloc[0])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kennlinie", default="", help="Pilot: C_voll je Regime als S3=142,kompakt10=70")
    a = ap.parse_args()
    d, df, z, n_f = lade(a.name)
    pa = paar_alc(df)
    vgl = vergleiche(pa)
    zs = {}
    if len(z):
        for (S, o, sp, pol), g in z.groupby(["regime", "ordnung", "split", "politik"]):
            zs[f"{S}|{o}|{sp}|{pol}"] = {k: int(g[k].sum()) for k in ("kandidaten", "kaeufe", "abweichungen", "fallbacks", "laeufe")}
    erg = {"lauf": a.name, "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "falten": n_f,
           "konfig": json.loads((d / "konfig.json").read_text()),
           "tabelle": tabelle(pa), "vergleiche_vs_zufall": vgl, "abdeckung_bewertungsitems": abdeckung(df),
           "zaehler": zs}
    if a.kennlinie:
        C_voll = {k: int(v) for k, v in (x.split("=") for x in a.kennlinie.split(","))}
        kl = []
        for v in vgl:
            if v.get("se") is None or v["S"] not in C_voll:
                continue
            se_voll = v["se"] * math.sqrt(v["n_cluster"] / C_voll[v["S"]])
            kl.append({**{k: v[k] for k in ZELLE + ["politik", "n_paare", "n_cluster", "mittel", "se"]},
                       "C_voll": C_voll[v["S"]], "se_voll_projiziert": round(se_voll, 7), "mde_2se_voll": round(2 * se_voll, 7)})
        k10 = [x for x in kl if x["S"] == "kompakt10" and x["politik"] == "abdeckung" and x["praediktor"] == "hier_item"]
        if not k10:
            raise SystemExit("Kennlinie: kompakt10/abdeckung/hier_item fehlt")
        mde = k10[0]["mde_2se_voll"]
        erg["kennlinie"] = {"regel_vorab": "MDE (2 SE, projiziert auf C_voll) kompakt10 > 0,0025 -> 5 Saaten (0-4), sonst 3 (0-2); D-akquise §6.2",
                            "mde_kompakt10": mde, "saaten_volllauf": 5 if mde > 0.0025 else 3, "zeilen": kl,
                            "p_fehlentscheidung_bei_nulleffekt": 0.5 * math.erfc(2 / math.sqrt(2)),
                            "betriebskennlinie": "P(Mittel + 2 SE < 0 | mu = 0) = 1 - Phi(2) = 2,3 %; Grauzone 4 SE"}
    (d / "tabelle.json").write_text(json.dumps(erg, indent=1, ensure_ascii=False))
    for v in vgl:
        print(f"{v['S']:9s} {v['ordnung']:6s} {v['split']:4s} {v['praediktor']:22s} {v['politik']:18s} "
              f"d={v['mittel']:+.5f} se={v.get('se', float('nan')):.5f} n={v['n_paare']} C={v['n_cluster']} {v['urteil']}")
    if a.kennlinie:
        print("Kennlinie:", json.dumps({k: erg["kennlinie"][k] for k in ("mde_kompakt10", "saaten_volllauf")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
