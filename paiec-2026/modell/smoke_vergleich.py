"""Smoke-Vergleich: frisch gerechnete Falte 0 (Phase 1, Saat 0) gegen die mitgelieferte Referenz.

Aufruf: python3 -I smoke_vergleich.py <saetze_f0.parquet neu> <referenz.parquet> [--tol 1e-9]
Schluessel: saat, S, praediktor, budget, b_code, s_code. Verglichen werden q und brier (Betrag der Differenz <= tol).
Fail-closed: fehlende Datei, ungleiche Zeilenzahl, nicht deckungsgleiche Schluessel, NaN/inf -> rc 2; Abweichung > tol -> rc 1; sonst rc 0.
Die Referenz (reference/saetze_f0_saat0.parquet) stammt aus dem CV-Lauf der Phase 1 (Falte 0, Saat 0) und ist bitgleich zu v1.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KEYS = ["saat", "S", "praediktor", "budget", "b_code", "s_code"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("neu")
    ap.add_argument("ref")
    ap.add_argument("--tol", type=float, default=1e-9)
    a = ap.parse_args()
    erg = {"neu": a.neu, "ref": a.ref, "tol": a.tol, "urteil": "FEHLER"}
    try:
        for p in (a.neu, a.ref):
            if not Path(p).is_file():
                raise FileNotFoundError(p)
        dn = pd.read_parquet(a.neu)
        dr = pd.read_parquet(a.ref)
        dn = dn[dn.saat == 0]
        dn = dn.assign(S=dn.S.astype(str), praediktor=dn.praediktor.astype(str))
        dr = dr.assign(S=dr.S.astype(str), praediktor=dr.praediktor.astype(str))
        erg["zeilen_neu"], erg["zeilen_ref"] = int(len(dn)), int(len(dr))
        if len(dn) != len(dr) or len(dr) == 0:
            raise ValueError("Zeilenzahl ungleich oder leer")
        j = dn.merge(dr, on=KEYS, suffixes=("_n", "_r"), how="outer", indicator=True)
        if len(j) != len(dr) or (j["_merge"] != "both").any():
            raise ValueError("Schluessel nicht deckungsgleich")
        dq = (j.q_n - j.q_r).abs().to_numpy()
        db = (j.brier_n - j.brier_r).abs().to_numpy()
        if not (np.isfinite(dq).all() and np.isfinite(db).all()):
            raise ValueError("NaN/inf in q oder brier")
        erg["max_abs_dq"], erg["max_abs_dbrier"] = float(dq.max()), float(db.max())
        ok = erg["max_abs_dq"] <= a.tol and erg["max_abs_dbrier"] <= a.tol
        erg["urteil"] = "ok" if ok else "ABWEICHUNG"
        print(json.dumps(erg))
        return 0 if ok else 1
    except Exception as e:  # fail-closed
        erg["fehler"] = f"{type(e).__name__}: {e}"
        print(json.dumps(erg))
        return 2


if __name__ == "__main__":
    sys.exit(main())
