"""F5 — schlechtester Fall „frischer Prozess je Aufruf": Python-Start + Import model.py (Zustand parsen) + erster
predict() (Gruppierung von |labeled| Labels) in einem NEUEN Prozess je Aufruf, gemessen mit subprocess.

Aufruf: python3 -I messungen/frischer_prozess.py --model-dir <dir mit model.py> [--labels 100000,300000]
        [--aufrufe 20] [--max-s 5] [--aus messungen/frischer_prozess.json]
Fail-closed: Kind-Prozess mit rc != 0 oder unlesbarer Ausgabe -> rc 2. Kriterium: Median des ersten predict() je
Label-Zahl < --max-s Sekunden, sonst rc 1. Die Label-Datei (JSON) wird im Kind geladen; diese Ladezeit ist Plattform-
Kosten und wird getrennt ausgewiesen. Rohe Mess-JSONs werden in --aus geschrieben (Kehrseite-Zeile am Ende).
"""
import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIND = r'''
import json, sys, time
t0 = time.perf_counter()
sys.path.insert(0, sys.argv[1])
import model
t1 = time.perf_counter()
labeled = json.load(open(sys.argv[2]))
t2 = time.perf_counter()
S = labeled[0][0][0]
I = dict(labeled[0][0][1], item_content="zielitem frisch")
p = model.predict([S, I], labeled)
t3 = time.perf_counter()
p2 = model.predict([labeled[-1][0][0], dict(I, item_content="zweites ziel")], labeled)
t4 = time.perf_counter()
print(json.dumps({"import_s": t1 - t0, "labels_laden_s": t2 - t1, "erster_predict_s": t3 - t2,
                  "zweiter_predict_s": t4 - t3, "p": p, "p2": p2, "n": len(labeled)}))
'''


def baue_labels(n, pfad, seed=0):
    rnd = random.Random(seed)
    subj = [{"normalized_name": "modell-%d" % j, "provider": "p%d" % (j % 7), "release_date": "2025-0%d-01" % (j % 9 + 1),
             "access_date": "2025-09-01", "harness": "h", "harness_version": "1", "reasoning_effort": "",
             "subject_features_extra": ""} for j in range(30)]
    out = []
    b = 0
    while len(out) < n:
        bid = "bm_%08x" % rnd.getrandbits(32)
        for s in subj[:rnd.randint(1, 5)]:
            for j in range(31):
                out.append([[s, {"item_content": "acquisition item %d of benchmark %d with some text" % (j, b),
                                 "item_features": "tier=%d" % (j % 3), "interactors": "", "benchmark_id": bid}],
                            rnd.randint(0, 1)])
                if len(out) >= n:
                    break
            if len(out) >= n:
                break
        b += 1
    Path(pfad).write_text(json.dumps(out))
    return len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--labels", default="100000,300000")
    ap.add_argument("--aufrufe", type=int, default=20)
    ap.add_argument("--max-s", type=float, default=5.0)
    ap.add_argument("--aus", default=str(Path(__file__).resolve().parent / "frischer_prozess.json"))
    a = ap.parse_args()
    a.model_dir = str(Path(a.model_dir).resolve())
    erg = {"model_dir": a.model_dir, "python": sys.version.split()[0], "aufrufe_je_groesse": a.aufrufe,
           "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "messungen": {}, "urteil": "FEHLER"}
    rc = 0
    with tempfile.TemporaryDirectory() as td:
        kind = Path(td) / "kind.py"
        kind.write_text(KIND)
        for n in [int(x) for x in a.labels.split(",")]:
            lab = Path(td) / f"labels_{n}.json"
            n_ist = baue_labels(n, lab)
            werte = []
            for k in range(a.aufrufe):
                t0 = time.perf_counter()
                r = subprocess.run([sys.executable, "-I", str(kind), a.model_dir, str(lab)], cwd=td,
                                   capture_output=True, text=True, timeout=600,
                                   env={"PATH": os.environ.get("PATH", ""), "OMP_NUM_THREADS": "1"})
                wand = time.perf_counter() - t0
                if r.returncode != 0:
                    erg["fehler"] = {"n": n, "aufruf": k, "rc": r.returncode, "stderr": r.stderr[-800:]}
                    Path(a.aus).write_text(json.dumps(erg, indent=1))
                    print(json.dumps(erg["fehler"]))
                    return 2
                try:
                    d = json.loads(r.stdout.strip().splitlines()[-1])
                except (ValueError, IndexError):
                    erg["fehler"] = {"n": n, "aufruf": k, "rc": r.returncode, "stdout": r.stdout[-800:]}
                    Path(a.aus).write_text(json.dumps(erg, indent=1))
                    print(json.dumps(erg["fehler"]))
                    return 2
                d["prozess_gesamt_s"] = wand
                werte.append(d)
            if len({round(w["p"], 12) for w in werte}) != 1:
                erg["fehler"] = {"n": n, "grund": "Vorhersage nicht deterministisch über Prozesse"}
                rc = 2
            zus = {}
            for f in ("prozess_gesamt_s", "import_s", "labels_laden_s", "erster_predict_s", "zweiter_predict_s"):
                xs = sorted(w[f] for w in werte)
                zus[f] = {"median": statistics.median(xs), "min": xs[0], "max": xs[-1]}
            zus["n_labels"] = n_ist
            zus["modell_ohne_labelladen_median_s"] = zus["import_s"]["median"] + zus["erster_predict_s"]["median"]
            zus["kriterium_erster_predict_median_lt_max_s"] = zus["erster_predict_s"]["median"] < a.max_s
            if not zus["kriterium_erster_predict_median_lt_max_s"]:
                rc = max(rc, 1)
            erg["messungen"][str(n)] = zus
            print(n, json.dumps({k: (round(v["median"], 4) if isinstance(v, dict) and "median" in v else v)
                                 for k, v in zus.items()}))
    erg["max_s"] = a.max_s
    erg["urteil"] = "ok" if rc == 0 else "FEHLER"
    erg["lesart"] = ("Schlechtester Fall, falls die Plattform je predict-Aufruf einen neuen Prozess startet: Kosten je "
                     "Aufruf = Python-Start + Import (Zustand parsen) + Gruppierung von |labeled| (O(n)). Bei 150 000 "
                     "Aufrufen je Checkpoint wäre das nicht einzuhalten — trifft aber jede Einreichung gleich (auch die "
                     "Veranstalter-Baseline zählt labeled je Aufruf). Innerhalb eines Prozesses gilt der O(64)-Pfad.")
    erg["kehrseite"] = ("Falsch, wenn die Plattform labeled je Aufruf anders übergibt (Generator, anderes Objekt je "
                        "Aufruf ohne Prozessneustart): dann gilt weder dieser Fall noch der O(64)-Schnellpfad, sondern "
                        "der Stichprobenschlüssel je Aufruf (~0,2 ms) plus einmalige Gruppierung je Checkpoint.")
    Path(a.aus).write_text(json.dumps(erg, indent=1))
    print("urteil", erg["urteil"], "rc", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
