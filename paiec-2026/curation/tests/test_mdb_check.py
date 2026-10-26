#!/usr/bin/env python3
"""Fehlerfall-Tests für mdb_check.py (BAUPLAN-V2 §2.3 P8): rc 0 auf einer unveränderten Teilbasis, rc != 0 auf absichtlich
verfälschten Kopien. Die Teilbasis wird aus der lokalen Basis (PAIEC_WORK/basis) in ein Scratch-Verzeichnis kopiert;
die Original-Basis wird nie verändert.

Varianten (jede muss den genannten rc liefern, sonst Test rot):
  V0 unverändert                                    -> rc 0
  V1 eine binäre Antwort auf 2.0 gesetzt            -> rc 1 (Integrität)
  V2 Spalte `direction` aus dem Katalog entfernt    -> rc 1 (Schema)
  V3 Parquet-Datei abgeschnitten (Parse-Fehler)     -> rc 2 (fail-closed)
  V4 eine Beobachtungszeile verdoppelt              -> rc 1 (Duplikat + Zeilenzahl)
  V5 responses-Datei eines Benchmarks gelöscht      -> rc 2 (Datei fehlt)
  V6 zweites Subjekt mit identischen acht Feldern   -> rc 0 ohne --streng (Befund), rc 1 mit --streng
  V7 direction gegen response_scale.direction       -> rc 1 (Widerspruch)
Aufruf: PAIEC_WORK=... python3 -I tests/test_mdb_check.py [--fixture DIR] ; Protokoll wird an tests/mdb_check_tests.log angehängt.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
MDB = HIER.parent / "mdb_check.py"
WORK = Path(os.environ.get("PAIEC_WORK", "work"))
BENCHMARKS = ["advprompter", "confagents", "ehrflowbench", "devbench", "live_agent_risk"]  # klein; devbench enthält F8-Gruppe


def baue_fixture(ziel: Path):
    if ziel.exists():
        shutil.rmtree(ziel)
    (ziel / "items").mkdir(parents=True)
    basis = WORK / "basis"
    bm = pd.read_parquet(basis / "benchmarks.parquet")
    bm = bm[bm.folder.isin(BENCHMARKS)]
    bm.to_parquet(ziel / "benchmarks.parquet", index=False)
    sub = pd.read_parquet(basis / "subjects.parquet")
    sub[sub.benchmark_id.isin(BENCHMARKS)].to_parquet(ziel / "subjects.parquet", index=False)
    for b in BENCHMARKS:
        shutil.copy(basis / "items" / f"{b}.parquet", ziel / "items" / f"{b}.parquet")
        d = ziel / "responses" / f"benchmark={b}"
        d.mkdir(parents=True)
        shutil.copy(basis / "responses" / f"benchmark={b}" / "part-0.parquet", d / "part-0.parquet")


def kopie(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def lauf(basis: Path, *extra):
    p = subprocess.run([sys.executable, "-I", str(MDB), "--basis", str(basis), *extra], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip().splitlines()[0] if (p.stdout + p.stderr).strip() else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(WORK.parent / "p8-work" / "fixture"))
    a = ap.parse_args()
    fx = Path(a.fixture)
    log = (HIER / "mdb_check_tests.log").open("a")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ergebnisse = []

    def pruefe(name, basis, soll, *extra):
        rc, zeile = lauf(basis, *extra)
        ok = rc in soll
        ergebnisse.append(ok)
        msg = f"{stamp} {name}: rc={rc} soll={sorted(soll)} {'OK' if ok else 'ROT'} | {zeile}"
        print(msg)
        log.write(msg + "\n")

    baue_fixture(fx / "V0")
    pruefe("V0 unverändert", fx / "V0", {0})
    # V1: Antwort 2.0
    kopie(fx / "V0", fx / "V1")
    f = fx / "V1" / "responses" / "benchmark=advprompter" / "part-0.parquet"
    r = pd.read_parquet(f)
    r.loc[r.index[0], "response"] = 2.0
    r.to_parquet(f, index=False)
    pruefe("V1 Antwort 2.0", fx / "V1", {1})
    # V2: Spalte direction weg
    kopie(fx / "V0", fx / "V2")
    bm = pd.read_parquet(fx / "V2" / "benchmarks.parquet").drop(columns=["direction"])
    bm.to_parquet(fx / "V2" / "benchmarks.parquet", index=False)
    pruefe("V2 Spalte direction fehlt", fx / "V2", {1})
    # V3: abgeschnittene Datei
    kopie(fx / "V0", fx / "V3")
    f = fx / "V3" / "items" / "confagents.parquet"
    daten = f.read_bytes()
    f.write_bytes(daten[: len(daten) // 2])
    pruefe("V3 Parquet abgeschnitten", fx / "V3", {2})
    # V4: doppelte Beobachtungszeile
    kopie(fx / "V0", fx / "V4")
    f = fx / "V4" / "responses" / "benchmark=ehrflowbench" / "part-0.parquet"
    r = pd.read_parquet(f)
    pd.concat([r, r.iloc[[0]]], ignore_index=True).to_parquet(f, index=False)
    pruefe("V4 Beobachtung verdoppelt", fx / "V4", {1})
    # V5: Datei fehlt
    kopie(fx / "V0", fx / "V5")
    (fx / "V5" / "responses" / "benchmark=live_agent_risk" / "part-0.parquet").unlink()
    pruefe("V5 responses fehlt", fx / "V5", {2})
    # V6: Identitäts-Duplikat eingebaut (zweites Subjekt mit denselben acht Feldern, neue subject_id/s_code)
    kopie(fx / "V0", fx / "V6")
    s = pd.read_parquet(fx / "V6" / "subjects.parquet")
    neu = s[s.benchmark_id == "advprompter"].iloc[[0]].copy()
    neu["subject_id"] = "ffffffffffffffff"
    neu["s_code"] = int(s.s_code.max()) + 1
    s2 = pd.concat([s, neu], ignore_index=True)
    s2.to_parquet(fx / "V6" / "subjects.parquet", index=False)
    bm = pd.read_parquet(fx / "V6" / "benchmarks.parquet")
    bm.loc[bm.folder == "advprompter", "rows_subjects"] += 1
    bm.to_parquet(fx / "V6" / "benchmarks.parquet", index=False)
    pruefe("V6 Identitäts-Duplikat ohne --streng", fx / "V6", {0})
    pruefe("V6 Identitäts-Duplikat mit --streng", fx / "V6", {1}, "--streng")
    # V7: Polaritäts-Widerspruch
    kopie(fx / "V0", fx / "V7")
    bm = pd.read_parquet(fx / "V7" / "benchmarks.parquet")
    bm.loc[bm.folder == "advprompter", "direction"] = "higher_is_better"  # response_scale sagt lower_is_better
    bm.to_parquet(fx / "V7" / "benchmarks.parquet", index=False)
    pruefe("V7 direction widerspricht response_scale", fx / "V7", {1})

    gesamt = all(ergebnisse)
    msg = f"{stamp} ERGEBNIS: {sum(ergebnisse)}/{len(ergebnisse)} Varianten wie erwartet -> {'GRÜN' if gesamt else 'ROT'}"
    print(msg)
    log.write(msg + "\n")
    log.close()
    return 0 if gesamt else 1


if __name__ == "__main__":
    sys.exit(main())
