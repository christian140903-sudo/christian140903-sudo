"""Bitgleichheits-Prüfung zweier CV-Ordner (saetze_f*.parquet): max |dq|, max |dbrier|, Zeilenzahlen, Zustände.

Aufruf: python3 -I vergleiche_saetze.py <ordner_neu> <ordner_alt> [--aus datei.json]
Pfade relativ zu $PAIEC_WORK/modell oder absolut. Schlüssel: saat, S, praediktor, budget, b_code, s_code (+ falte).
Fail-closed: fehlende Dateien, ungleiche Zeilenzahl oder nicht deckungsgleiche Schlüssel -> rc 2; max |dq| > 0 -> rc 1.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

SCRATCH = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"
KEYS = ["saat", "S", "praediktor", "budget", "b_code", "s_code"]


def pfad(x):
    p = Path(x)
    return p if p.is_absolute() else SCRATCH / x


def kanon(p, ohne_platt=False):
    d = json.loads(Path(p).read_text())
    d.pop("herkunft", None)
    if ohne_platt:
        d.pop("platt", None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("neu")
    ap.add_argument("alt")
    ap.add_argument("--aus", default="")
    ap.add_argument("--erlaubt", default="", help="Prädiktoren (Komma), bei denen Abweichung erlaubt ist (z. B. Platt-Stufen)")
    a = ap.parse_args()
    erlaubt = set(x for x in a.erlaubt.split(",") if x)
    neu, alt = pfad(a.neu), pfad(a.alt)
    erg = {"neu": str(neu), "alt": str(alt), "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "falten": {}, "urteil": "FEHLER"}
    rc = 0
    n_ges = 0
    maxq = maxb = 0.0
    for k in range(10):
        fn, fa = neu / f"saetze_f{k}.parquet", alt / f"saetze_f{k}.parquet"
        if not fn.exists() or not fa.exists():
            erg["falten"][k] = "fehlt"
            rc = 2
            continue
        dn, da = pd.read_parquet(fn), pd.read_parquet(fa)
        if len(dn) != len(da):
            erg["falten"][k] = {"zeilen_neu": len(dn), "zeilen_alt": len(da), "grund": "Zeilenzahl ungleich"}
            rc = 2
            continue
        j = dn.merge(da, on=KEYS, suffixes=("_n", "_a"), how="outer", indicator=True)
        if (j["_merge"] != "both").any() or len(j) != len(dn):
            erg["falten"][k] = {"grund": "Schlüssel nicht deckungsgleich", "nur_neu": int((j._merge == "left_only").sum()),
                                "nur_alt": int((j._merge == "right_only").sum())}
            rc = 2
            continue
        dq = (j.q_n - j.q_a).abs().max()
        db = (j.brier_n - j.brier_a).abs().max() if "brier_n" in j else 0.0
        dn_adj = int((j.n_items_angepasst_n != j.n_items_angepasst_a).sum()) if "n_items_angepasst_n" in j else 0
        je_pr = {}
        for pr, g in j.groupby("praediktor"):
            je_pr[pr] = {"zeilen": int(len(g)), "max_dq": float((g.q_n - g.q_a).abs().max()),
                         "n_ungleich_q": int((g.q_n != g.q_a).sum())}
        unerlaubt = {pr: v for pr, v in je_pr.items() if v["n_ungleich_q"] and pr not in erlaubt}
        for pr in je_pr:
            e = erg.setdefault("je_praediktor", {}).setdefault(pr, {"zeilen": 0, "max_dq": 0.0, "n_ungleich_q": 0})
            e["zeilen"] += je_pr[pr]["zeilen"]
            e["max_dq"] = max(e["max_dq"], je_pr[pr]["max_dq"])
            e["n_ungleich_q"] += je_pr[pr]["n_ungleich_q"]
        if erlaubt:
            # Abweichung nur in erlaubten Prädiktoren: Falte zählt als konform, wenn kein unerlaubter abweicht
            dq_bewertet = max([v["max_dq"] for pr, v in je_pr.items() if pr not in erlaubt] + [0.0])
        else:
            dq_bewertet = float(dq)
        sn, sa = neu / f"state_f{k}.json", alt / f"state_f{k}.json"
        zustand = (kanon(sn, bool(erlaubt)) == kanon(sa, bool(erlaubt))) if sn.exists() and sa.exists() else None
        erg["falten"][k] = {"zeilen": int(len(j)), "max_dq": float(dq), "max_dbrier": float(db),
                            "n_items_angepasst_ungleich": dn_adj, "zustand_kanonisch_gleich": zustand,
                            "max_dq_ohne_erlaubte": dq_bewertet, "unerlaubt_abweichend": sorted(unerlaubt)}
        n_ges += len(j)
        maxq, maxb = max(maxq, float(dq)), max(maxb, float(db))
        if dq_bewertet > 0 or (not erlaubt and (db > 0 or dn_adj)) or zustand is False or unerlaubt:
            rc = max(rc, 1)
    erg.update({"zeilen_gesamt": n_ges, "max_dq": maxq, "max_dbrier": maxb, "rc": rc, "erlaubt": sorted(erlaubt),
                "urteil": ("bitgleich" if maxq == 0 else "bitgleich außer erlaubten Prädiktoren") if rc == 0 else "FEHLER"})
    txt = json.dumps(erg, indent=1)
    if a.aus:
        Path(a.aus).write_text(txt)
    print(txt)
    return rc


if __name__ == "__main__":
    sys.exit(main())
