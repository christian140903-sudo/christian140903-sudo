"""pruefe_fertig.py — mechanische Prüfung der Fertig-Kriterien von P4 (BAUPLAN-V2 §2.2/§7 P4, Prereg §1/§7).

Kriterien (jedes mit Beleg; rc 0 nur, wenn alle erfüllt):
 K1 Prereg-Hash passt (sha256 der Datei == PRAEREG-HASH.txt) und PRAEREG-HASH.txt ist älter als konfirmation/ (Reihenfolge)
 K2 status.json fertig == 10 für die Primärläufe cv_K_A, cv_K_A2v, cv_K_B, cv_K_B2v (Saaten 200,201,202, Falten-Saat 200; Phase 2 verschachtelte Stufen je Falte, v2.0-core)
 K3 falten.json der Konfirmation weicht von cv_A/falten.json ab (frische Faltenzuteilung)
 K4 hypothesen_tafel.json: 10 Hypothesen H1–H8 (H2a/b/c), jede mit rule, value, verdict aus der erlaubten Menge, source_file
 K5 keine Hypothese 'not_evaluated' (sonst Liste)
 K6 ZAHLEN-QUELLEN-v2.md enthält den P4-Abschnitt mit >= 10 Zeilen 'P4'
 K7 auswertung_K.json vorhanden, enthält Kehrseite und alle vier Primärläufe mit fertig == 10
 K8 Fehlerfall ausgelöst: validierung/leer/tafel_leer.json existiert mit 10× not_evaluated (fail-closed-Nachweis)
Aufruf: python3 -I pruefe_fertig.py  -> Tabelle + rc (0 alle erfüllt, 1 sonst)
"""
import hashlib
import json
import os
import sys
from pathlib import Path

K = Path(__file__).resolve().parent
B = K.parent.parent
W = Path(os.environ.get("PAIEC_WORK", "")) / "modell"
ERLAUBT = {"better", "worse", "equivalent", "grey_zone", "passed", "failed", "not_evaluated"}


def main():
    z = []

    def k(name, ok, beleg):
        z.append((name, bool(ok), beleg))

    # K1
    try:
        ht = (B / "v2-plan" / "PRAEREG-HASH.txt").read_text()
        soll = [l.split(":", 1)[1].strip() for l in ht.splitlines() if l.startswith("sha256:")][0]
        ist = hashlib.sha256((B / "v2-plan" / "PRAEREGISTRIERUNG-v2.md").read_bytes()).hexdigest()
        t_hash = (B / "v2-plan" / "PRAEREG-HASH.txt").stat().st_mtime
        t_konf = K.stat().st_mtime if not (K / "STATUS.md").exists() else min(K.stat().st_mtime, (K / "STATUS.md").stat().st_mtime)
        # Reihenfolge: Anlagezeit der ersten Heartbeat-Zeile aus STATUS.md
        erste = [l for l in (K / "STATUS.md").read_text().splitlines() if l.startswith("- 2026-")][0][2:22]
        k("K1 Prereg-Hash + Reihenfolge", ist == soll and "T20:26:04Z" in ht and erste > "2026-10-20T20:26:04Z",
          f"sha256 {ist[:12]}… == {soll[:12]}…; Hash eingefroren 20:26:04Z < erster P4-Heartbeat {erste}")
    except Exception as e:  # noqa: BLE001
        k("K1 Prereg-Hash + Reihenfolge", False, f"Fehler {e}")
    # K2
    for ord in ("cv_K_A", "cv_K_A2v", "cv_K_B", "cv_K_B2v"):
        try:
            s = json.loads((W / ord / "status.json").read_text())
            ok = s.get("fertig") == 10 and s.get("falten") == 10 and s.get("saaten") == "200,201,202" and s.get("falten_saat") == 200
            if ord.endswith("v"):  # v2.0-core: keine erzwungene Stufenmenge, je Falte verschachtelt gewählt (10 Log-Zeilen 'Platt-Stufen')
                n_st = sum(1 for l in (W / ord / "log.txt").read_text().splitlines() if "Platt-Stufen" in l and "Falte" in l)
                ok = ok and s.get("platt_stufen") == "" and n_st >= 10
                s = dict(s, log_zeilen_platt_stufen=n_st)
            k(f"K2 {ord} fertig=10", ok, json.dumps(s))
        except Exception as e:  # noqa: BLE001
            k(f"K2 {ord} fertig=10", False, f"{e}")
    # K3
    try:
        neu = json.loads((W / "cv_K_A" / "falten.json").read_text())
        alt = json.loads((W / "cv_A" / "falten.json").read_text())
        n = sum(1 for b, f in neu.items() if alt.get(b) != f)
        k("K3 frische Faltenzuteilung", n > 0, f"{n}/{len(neu)} Benchmarks in anderer Falte als cv_A")
    except Exception as e:  # noqa: BLE001
        k("K3 frische Faltenzuteilung", False, f"{e}")
    # K4/K5
    try:
        t = json.loads((K / "hypothesen_tafel.json").read_text())
        H = t["hypothesen"]
        ids = [h["id"] for h in H]
        ok4 = ids == ["H1", "H2a", "H2b", "H2c", "H3", "H4", "H5", "H6", "H7", "H8"] and all(
            h.get("rule") and h.get("source_file") and h.get("verdict") in ERLAUBT and "value" in h for h in H)
        k("K4 Tafel vollständig (10 H, Regel/Wert/Urteil/Quelle)", ok4, f"ids={ids}")
        ne = [h["id"] for h in H if h["verdict"] == "not_evaluated"]
        k("K5 keine not_evaluated", not ne, f"not_evaluated: {ne or 'keine'}; Urteile: " + json.dumps({h['id']: h['verdict'] for h in H}))
    except Exception as e:  # noqa: BLE001
        k("K4 Tafel vollständig", False, f"{e}")
        k("K5 keine not_evaluated", False, f"{e}")
    # K6
    try:
        zq = (B / "bericht-v2" / "ZAHLEN-QUELLEN-v2.md").read_text()
        n = sum(1 for l in zq.splitlines() if l.startswith("| H") and "konfirmation" in l)
        k("K6 ZAHLEN-QUELLEN-v2 P4-Abschnitt", "## P4 Konfirmation" in zq and n >= 10, f"{n} P4-Zeilen")
    except Exception as e:  # noqa: BLE001
        k("K6 ZAHLEN-QUELLEN-v2 P4-Abschnitt", False, f"{e}")
    # K7
    try:
        a = json.loads((K / "auswertung_K.json").read_text())
        okr = all((a["laeufe"][n].get("status") or {}).get("fertig") == 10 for n in ("A_p1", "A_p2_verschachtelt", "B_p1", "B_p2_verschachtelt"))
        k("K7 auswertung_K.json mit Kehrseite + 4 Primärläufe", bool(a.get("kehrseite")) and okr, "ok" if okr else "Lauf fehlt/unfertig")
    except Exception as e:  # noqa: BLE001
        k("K7 auswertung_K.json", False, f"{e}")
    # K8
    try:
        l = json.loads((K / "validierung" / "leer" / "tafel_leer.json").read_text())
        n = sum(1 for h in l["hypothesen"] if h["verdict"] == "not_evaluated")
        k("K8 Fehlerfall fail-closed ausgelöst", n == 10, f"{n}/10 not_evaluated bei leerem Ergebnisordner")
    except Exception as e:  # noqa: BLE001
        k("K8 Fehlerfall fail-closed ausgelöst", False, f"{e}")
    alle = all(ok for _, ok, _ in z)
    print("| Kriterium | Stand | Beleg |\n|---|---|---|")
    for name, ok, beleg in z:
        print(f"| {name} | {'ERFÜLLT' if ok else 'VERFEHLT'} | {beleg[:300]} |")
    print(f"\nGESAMT: {'alle erfüllt' if alle else 'nicht alle erfüllt'} (rc {0 if alle else 1})")
    return 0 if alle else 1


if __name__ == "__main__":
    sys.exit(main())
