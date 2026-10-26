"""F7 — Prüfung der Platt-Stufenwahl: verschachtelt belegt? Abweichung je Falte gegen die Gesamtwahl; Paket-Stufen
konsistent mit der Schnittregel (KERN-DIFF.md §0)?

Aufruf: python3 -I pruefe_platt_wahl.py <auswertung.json> [--state <state.json>]
rc 1 (fail-closed): Feld platt_stufenwahl_verschachtelt fehlt (= Stufenwahl auf allen Falten, v1-Verfahren) oder der
Zustand trägt andere Platt-Stufen als die Schnittregel. rc 0: Tabelle je Falte, Abweichungen dokumentiert.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("auswertung")
    ap.add_argument("--state", default="")
    a = ap.parse_args()
    d = json.loads(Path(a.auswertung).read_text())
    w = d.get("platt_stufenwahl_verschachtelt")
    if not w or "verschachtelt_je_falte" not in w:
        print(json.dumps({"urteil": "FEHLER", "grund": "Stufenwahl nicht verschachtelt belegt (Feld fehlt): v1-Verfahren, "
                          "Stufenmenge auf allen Falten gewählt", "platt_paket": sorted(d.get("platt_paket", {}))}))
        return 1
    gesamt = w["gesamt_v1_regel"]
    zeilen = []
    for f, stufen in sorted(w["verschachtelt_je_falte"].items(), key=lambda x: int(x[0])):
        abw = w["abweichung_je_falte"][f]
        zeilen.append({"falte": int(f), "stufen": stufen, "abweichung_zu_gesamt": abw})
    erg = {"urteil": "ok", "gesamt_v1_regel": gesamt, "paket_schnittregel": w["paket_schnittregel"],
           "mehrheit_je_stufe": w["mehrheit_je_stufe"], "paket_gleich_v1": w["paket_gleich_v1"],
           "falten_mit_abweichung": sum(1 for z in zeilen if z["abweichung_zu_gesamt"]), "je_falte": zeilen}
    if a.state:
        st = json.loads(Path(a.state).read_text())
        stufen_state = sorted(int(k) for k in (st.get("platt") or {}))
        erg["state_platt_stufen"] = stufen_state
        if stufen_state != sorted(w["paket_schnittregel"]):
            erg["urteil"] = "FEHLER"
            erg["grund"] = "Zustand trägt andere Platt-Stufen als die Schnittregel"
    print(json.dumps(erg, indent=1))
    return 0 if erg["urteil"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
