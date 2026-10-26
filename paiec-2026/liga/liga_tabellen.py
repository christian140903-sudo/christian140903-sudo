"""Markdown-Tabellen für LIGA.md §4 aus ergebnisse/ (liga_vergleich.json, rangfolge.csv, brier_je_budget*.csv, laufzeit.csv).

Aufruf: python3 -I liga_tabellen.py --aus <ergebnisse-ordner>   → schreibt <aus>/tabellen_liga.md und druckt es.
Rein mechanisch, keine Interpretation; „not evaluated" wird durchgereicht.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

FAM = ["irt2pl", "irt1pl", "mf", "stack", "knn", "gb", "beta_binomial", "empirischer_mittelwert", "v1_ohne_itemstufe",
       "konstant_0.5"]
NAME = {"irt2pl": "IRT 2PL", "irt1pl": "IRT 1PL (Rasch)", "mf": "Matrixfaktorisierung (Rang 1–8, je Falte gewählt)",
        "stack": "Stacking (irt2pl, mf, knn, BB)", "knn": "kNN über Subjekte", "gb": "Gradient Boosting (20 Merkmale)",
        "beta_binomial": "Beta-Binomial", "empirischer_mittelwert": "Empirical Mean (Veranstalter-Baseline 1)",
        "v1_ohne_itemstufe": "v1 ohne Item-Stufe (hier_kal)", "konstant_0.5": "konstant 0,5"}


def fmt_d(d):
    if d == "not evaluated" or d is None:
        return "not evaluated"
    k = d.get("ki95")
    if k is None:
        return f"{d['mittel']:+.4f} (SE n/a)"
    return f"{d['mittel']:+.4f} [{k[0]:+.4f}, {k[1]:+.4f}] {d['urteil']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    aus = Path(a.aus)
    v = json.loads((aus / "liga_vergleich.json").read_text())
    rang = pd.read_csv(aus / "rangfolge.csv").set_index("praediktor")
    lz = pd.read_csv(aus / "laufzeit.csv").set_index("praediktor")
    out = [f"Stand: {v['status']}, erzeugt {v['erzeugt_utc']}; Falten {v['falten']}, Saaten {v['saaten']} (discovery).", ""]
    out.append("**Tabelle 4.1 — Brier-ALC je Regime (Mittel über Paare, Paare gleich gewichtet) und mittlerer Rang.**")
    out.append("")
    out.append("| Methode | S1 | S2 | S3 | S30 | kompakt10 | Rang Ø |")
    out.append("|---|---|---|---|---|---|---|")
    for pr in ["v1_hier_item"] + FAM:
        if pr in rang.index:
            r = rang.loc[pr]
            out.append(f"| {NAME.get(pr, pr)} | {r.S1:.4f} | {r.S2:.4f} | {r.S3:.4f} | {r.S30:.4f} | {r.kompakt10:.4f} | {r.rang_mittel:.1f} |")
        else:
            out.append(f"| {NAME.get(pr, pr)} | not evaluated | | | | | |")
    out.append("")
    for S in ["S1", "S3", "S30"]:
        b = v["regime"][S]
        if b == "not evaluated":
            out.append(f"**Tabelle 4.2-{S}:** not evaluated")
            continue
        n = b["n_paare"]
        out.append(f"**Tabelle 4.2-{S} — gepaarte Differenz zu v1 (Familie − v1, negativ = Familie besser), Regime {S}, "
                   f"{n} Paare, {b['n_benchmarks']} Benchmark-Cluster.** ALC: Mittel [95-%-KI, Cluster-SE] Urteil (Regel mittel ± 2·SE); "
                   f"je Budget: Mittel ± Cluster-SE.")
        out.append("")
        out.append("| Methode | ΔALC | B0 | B1 | B3 | B7 | B15 | B31 | Falten mit Vorteil |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for pr in FAM:
            fb = b["familien"].get(pr, "not evaluated")
            if fb == "not evaluated":
                out.append(f"| {NAME.get(pr, pr)} | not evaluated | | | | | | | |")
                continue
            d = fb["differenz_zu_v1"]
            zellen = [fmt_d(d["alc"])]
            for c in ["B0", "B1", "B3", "B7", "B15", "B31"]:
                x = d[c]
                zellen.append(f"{x['mittel']:+.4f} ± {x['se']:.4f}" if x.get("se") is not None else f"{x['mittel']:+.4f}")
            zellen.append(f"{d['alc']['falten_mit_vorteil']}/{d['alc']['n_falten']}")
            out.append(f"| {NAME.get(pr, pr)} | " + " | ".join(zellen) + " |")
        out.append("")
    out.append("**Tabelle 4.3 — Laufzeit zur Testzeit (Median über Falten, ms je 1 000 Aufrufe, 1 Thread).**")
    out.append("")
    out.append("| Methode | Paar-Aufrufe | Item-Aufrufe |")
    out.append("|---|---|---|")
    for pr in FAM:
        if pr in lz.index:
            out.append(f"| {NAME.get(pr, pr)} | {lz.loc[pr].ms_je_1000_paar_median:.0f} | {lz.loc[pr].ms_je_1000_item_median:.0f} |")
    txt = "\n".join(out) + "\n"
    (aus / "tabellen_liga.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
