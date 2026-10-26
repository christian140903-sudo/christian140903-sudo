"""Vergleich zweier GEBAUTER Pakete (model.py) in frischen Prozessen auf denselben synthetischen Läufen:
max |dp| gesamt und je Platt-Stufe des Zielpaares (n_eigen -> stufe). Erwartung v2core vs v1: Abweichung NUR in den
Stufen, die v2core nicht mehr kalibriert (3, 7); Stufen 0, 1, 15, 31 bitgleich (max |dp| = 0).

Aufruf: python3 -I vergleiche_v1_paket.py <dir_v2 mit model.py> <dir_v1 mit model.py> [--aus datei.json]
Fail-closed: Kindprozess rc != 0 oder ungleiche Anzahl -> rc 2; Abweichung in einer nicht erwarteten Stufe -> rc 1.
"""
import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIND = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import model
lauf = json.load(open(sys.argv[2]))
out = []
for labeled, ziele in lauf:
    for inp in ziele:
        out.append(model.predict(inp, labeled))
print(json.dumps(out))
'''


def stufe(n):
    s = 0
    for b in (0, 1, 3, 7, 15, 31):
        if n >= b:
            s = b
    return s


def baue_lauf(theta_namen, seed=0):
    rnd = random.Random(seed)
    namen = theta_namen[:6] + ["neu-%d" % j for j in range(4)] + [""]
    lauf, stufen = [], []
    for b in range(40):
        bid = "bm_%08x" % rnd.getrandbits(32)
        S = rnd.choice([1, 2, 3, 5, 12])
        subj = [{"normalized_name": rnd.choice(namen), "provider": "p%d" % rnd.randint(0, 4),
                 "release_date": "202%d-0%d-01" % (rnd.randint(3, 6), rnd.randint(1, 9)), "access_date": "2026-01-01",
                 "harness": "", "harness_version": "", "reasoning_effort": "", "subject_features_extra": ""}
                for _ in range(S)]
        for B in (0, 1, 2, 3, 5, 7, 10, 15, 20, 31):
            labeled = [[[s, {"item_content": "acq %d %d" % (k, j), "item_features": "", "interactors": "",
                             "benchmark_id": bid}], rnd.randint(0, 1)] for k, s in enumerate(subj) for j in range(B)]
            ziele = []
            for k, s in enumerate(subj):
                n_eigen = sum(1 for t in subj if t == s) * B
                for j in range(2):
                    ziele.append([s, {"item_content": ("acq %d %d" % (k, j)) if j == 0 and B > 0 else "eval %d" % j,
                                      "item_features": "", "interactors": "", "benchmark_id": bid}])
                    stufen.append(stufe(n_eigen))
            lauf.append([labeled, ziele])
    return lauf, stufen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("neu")
    ap.add_argument("alt")
    ap.add_argument("--aus", default="")
    ap.add_argument("--erwartete-abweichung", default="3,7", help="Stufen, in denen Abweichung erwartet ist")
    a = ap.parse_args()
    erw = {int(x) for x in a.erwartete_abweichung.split(",") if x}
    st = json.loads((Path(a.neu) / "model.py").read_text().split("_STATE_JSON = r'''", 1)[1].split("'''", 1)[0])
    lauf, stufen = baue_lauf(sorted(st["theta"]))
    erg = {"neu": str(Path(a.neu).resolve()), "alt": str(Path(a.alt).resolve()),
           "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "kind.py").write_text(KIND)
        (td / "lauf.json").write_text(json.dumps(lauf))
        outs = []
        for d in (a.neu, a.alt):
            r = subprocess.run([sys.executable, "-I", str(td / "kind.py"), str(Path(d).resolve()), str(td / "lauf.json")],
                               cwd=td, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                erg.update({"urteil": "FEHLER", "stderr": r.stderr[-800:]})
                print(json.dumps(erg))
                return 2
            outs.append(json.loads(r.stdout))
    n, v = outs
    if len(n) != len(v) or len(n) != len(stufen):
        erg.update({"urteil": "FEHLER", "grund": "Anzahl ungleich", "n": len(n), "v": len(v), "stufen": len(stufen)})
        print(json.dumps(erg))
        return 2
    je_stufe = {}
    for x, y, s in zip(n, v, stufen):
        e = je_stufe.setdefault(s, {"n": 0, "max_dp": 0.0, "n_ungleich": 0})
        e["n"] += 1
        e["max_dp"] = max(e["max_dp"], abs(x - y))
        e["n_ungleich"] += int(x != y)
    unerwartet = {s: e for s, e in je_stufe.items() if e["n_ungleich"] and s not in erw}
    erg.update({"n_vergleiche": len(n), "max_dp_gesamt": max(abs(x - y) for x, y in zip(n, v)),
                "je_stufe": {str(s): je_stufe[s] for s in sorted(je_stufe)}, "erwartete_abweichung_stufen": sorted(erw),
                "unerwartete_abweichung": {str(s): e for s, e in unerwartet.items()},
                "urteil": "ok" if not unerwartet else "FEHLER"})
    txt = json.dumps(erg, indent=1)
    if a.aus:
        Path(a.aus).write_text(txt)
    print(txt)
    return 0 if not unerwartet else 1


if __name__ == "__main__":
    sys.exit(main())
