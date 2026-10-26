"""Baut tabelle_politiken.json aus den Auswertungen der Läufe `voll` (Split je Paar) und `voll_item` (Split je Item)
plus Fehlerfall-Protokoll und wendet die VORAB festgelegte Annahme-Regel für labeling.py an (D-akquise §6.2; BAUPLAN P5):
  1 H4: S1-Entscheidungen bit-identisch (Abweichungen = 0) — Testprotokoll UND Volllauf-Zähler
  2 Nicht-Unterlegenheit abdeckung vs zufall (hier_item): Mittel - 2 SE <= 0 in S1, S3, S30, kompakt10 (alle Ordnungen) und beiden Splits
  3 Überlegenheit kompakt10 (rr, Split je Paar): Mittel + 2 SE < 0
Fail-closed: fehlende Zelle -> Regel "nicht entscheidbar", nie "bestanden".
  python3 -I baue_tabelle.py
"""
import json
import os
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
AUS = Path(os.environ.get("PAIEC_WORK", "work")) / "akquise"


def lade(name):
    p = AUS / name / "tabelle.json"
    if not p.exists():
        raise SystemExit(f"fehlt: {p}")
    return json.loads(p.read_text())


def finde(vgl, S, ordnung, split, praed, pol):
    for v in vgl:
        if (v["S"], v["ordnung"], v["split"], v["praediktor"], v["politik"]) == (S, ordnung, split, praed, pol):
            return v
    return None


def main():
    voll = lade("voll")
    item = lade("voll_item")
    ff = json.loads((HIER / "ergebnisse" / "fehlerfaelle.json").read_text())
    vgl = voll["vergleiche_vs_zufall"] + item["vergleiche_vs_zufall"]
    # H4
    abw_s1 = {k: v["abweichungen"] for k, v in voll["zaehler"].items() if k.startswith("S1|") and k.endswith("|abdeckung")}
    h4_test = [p for p in ff["protokoll"] if p["test"] == "H4_S1_bitgleich"]
    h4 = bool(h4_test) and h4_test[0]["abweichungen"] == 0 and h4_test[0]["kandidaten"] >= 10_000 \
        and bool(abw_s1) and all(v == 0 for v in abw_s1.values())
    s1_diff = finde(vgl, "S1", "paar", "paar", "hier_item", "abdeckung")
    # Nicht-Unterlegenheit
    zellen = []
    for S in ("S1", "S3", "S30", "kompakt10"):
        for o in (("paar",) if S == "S1" else ("rr", "paar", "zufall")):
            zellen.append((S, o, "paar"))
    for S in ("S3", "kompakt10"):
        zellen.append((S, "rr", "item"))
    nu = {}
    for S, o, sp in zellen:
        v = finde(vgl, S, o, sp, "hier_item", "abdeckung")
        if v is None or v.get("se") is None:
            nu[f"{S}|{o}|{sp}"] = None
        else:
            nu[f"{S}|{o}|{sp}"] = {"mittel": v["mittel"], "se": v["se"], "nicht_unterlegen": v["mittel"] - 2 * v["se"] <= 0,
                                   "urteil": v["urteil"]}
    nu_ok = all(x is not None and x["nicht_unterlegen"] for x in nu.values())
    prim = finde(vgl, "kompakt10", "rr", "paar", "hier_item", "abdeckung")
    ueber = prim is not None and prim.get("se") is not None and prim["mittel"] + 2 * prim["se"] < 0
    grau = prim is not None and prim.get("se") is not None and not ueber and prim["mittel"] + 4 * prim["se"] < 0
    regel = {"H4_bitgleich": h4, "H4_abweichungen_S1_volllauf": abw_s1, "H4_test": h4_test,
             "S1_alc_differenz": None if s1_diff is None else s1_diff["mittel"],
             "nicht_unterlegenheit": nu, "nicht_unterlegenheit_ok": nu_ok,
             "ueberlegenheit_kompakt10_rr": None if prim is None else {k: prim[k] for k in ("mittel", "se", "urteil", "n_paare", "n_cluster")},
             "ueberlegen": ueber, "grauzone_bis_4se": grau,
             "simulatorbefund_erfuellt": bool(h4 and nu_ok and ueber),
             "labeling_py_ins_paket": False,
             "begruendung": "Simulatorbefund allein reicht nicht: zusätzlich Veranstalterbestätigung 'Split je Paar' UND Gate Fr 23.10. 18:00Z (BAUPLAN §2.2 P5, §1.3 Nr. 11). Standard: Befund in Bericht §6.8."}
    # Fehlerfälle F1/F2 (Regel: schaden <=> Mittel - 2 SE > 0)
    def schaden(S, o, sp, pr, pol):
        v = finde(vgl, S, o, sp, pr, pol)
        if v is None or v.get("se") is None:
            return None
        return {"mittel": v["mittel"], "se": v["se"], "schadet": v["mittel"] - 2 * v["se"] > 0, "urteil": v["urteil"],
                "n_paare": v["n_paare"], "n_cluster": v["n_cluster"]}
    fehler = {}
    for S in ("S3", "S30", "kompakt10"):
        fehler[S] = {
            "F1_unsicherheit_0.15_mit_EM_praediktor": schaden(S, "rr", "paar", "empirischer_mittelwert", "unsicherheit_0.15"),
            "F1_unsicherheit_0.15_mit_hier_item": schaden(S, "rr", "paar", "hier_item", "unsicherheit_0.15"),
            "unsicherheit_em_mit_EM_praediktor (Lemma 2: erwartet ~0)": schaden(S, "rr", "paar", "empirischer_mittelwert", "unsicherheit_em"),
            "unsicherheit_em_mit_hier_item": schaden(S, "rr", "paar", "hier_item", "unsicherheit_em"),
            "F2_information_naiv_hier_item": schaden(S, "rr", "paar", "hier_item", "information_naiv"),
            "F2_information_naiv_EM": schaden(S, "rr", "paar", "empirischer_mittelwert", "information_naiv"),
            "leicht_zuerst_hier_item": schaden(S, "rr", "paar", "hier_item", "leicht_zuerst"),
            "leicht_zuerst_EM": schaden(S, "rr", "paar", "empirischer_mittelwert", "leicht_zuerst"),
            "orakel_d_politik_mit_hier_item (ohne bedingte Likelihood)": schaden(S, "rr", "paar", "hier_item", "orakel_d"),
            "orakel_d_politik_mit_orakel_praediktor (Obergrenze eigener Hebel)": schaden(S, "rr", "paar", "orakel_d", "orakel_d"),
        }
    erg = {"zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "paketmodell": "v1 modell/ (hier_item; P1 v2.0-core beim Start nicht fertig)",
           "quellen": {"voll": str(AUS / "voll" / "tabelle.json"), "voll_item": str(AUS / "voll_item" / "tabelle.json"),
                       "fehlerfaelle": str(HIER / "ergebnisse" / "fehlerfaelle.json"), "kennlinie": str(HIER / "kennlinie.json")},
           "regel_vorab": "besser <=> Mittel + 2 SE < 0; schlechter <=> Mittel - 2 SE > 0; SE cluster-robust über Benchmarks; Paare gleich gewichtet; Differenz je Paar über Saaten gemittelt; gemeinsame Zufallszahlen",
           "annahme_regel_labeling_py": regel, "fehlerfaelle_F1_F2": fehler,
           "vergleiche_vs_zufall": vgl, "tabelle_alc": {**voll["tabelle"], **item["tabelle"]},
           "abdeckung_bewertungsitems": {**voll["abdeckung_bewertungsitems"], **item["abdeckung_bewertungsitems"]},
           "zaehler": {**voll["zaehler"], **{"ITEM|" + k: v for k, v in item["zaehler"].items()}},
           "fehlerfall_tests": ff,
           "kehrseite": "Falsch, wenn die Plattform den 50/50-Split je Item über alle Subjekte zieht (dann rho = 0, Szenario 'item' ist die gültige Zahl), wenn sie je Benchmark nur ein Subjekt in den Lauf nimmt (S1: exakt 0), wenn `labeled` beim Kauf anders befüllt wird als bei der Bewertung, oder wenn Pools im Summativlauf < 50 Items haben (Auswahl bedeutungslos). Pool-Kappe 200 und Koordinator-Ordnungen sind Annahmen; SE in kompakt10 stützt sich auf ~70 Benchmark-Cluster."}
    (HIER / "tabelle_politiken.json").write_text(json.dumps(erg, indent=1, ensure_ascii=False))
    print(json.dumps({k: regel[k] for k in ("H4_bitgleich", "nicht_unterlegenheit_ok", "ueberlegen", "grauzone_bis_4se", "simulatorbefund_erfuellt")}))
    for S, d in fehler.items():
        for k, v in d.items():
            if v:
                print(f"{S:10s} {k:70s} d={v['mittel']:+.5f} se={v['se']:.5f} {v['urteil']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
