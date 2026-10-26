"""Endzustand für das Paket: Training auf ALLEN 156 Benchmarks, Platt-Parameter aus der CV (nur Stufen mit
kreuzangepasstem Gewinn), tau_i2 aus dem Training. Schreibt paket/state_final.json und dist/<name>.zip.
Aufruf: python3 -I baue_final.py [--cv cv_A]
"""
import argparse
import json
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "paket"))
import training  # noqa: E402
import baselines  # noqa: E402
from baue_paket import baue  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", default="cv_A")
    a = ap.parse_args()
    t0 = time.time()
    p, agg = training.lade_paare()
    state = training.trainiere(p, seed=0, agg=agg)
    ausw = json.loads((training.SCRATCH / a.cv / "auswertung.json").read_text())
    state["platt"] = ausw["platt_paket"]
    kap = training.kappe(p, seed=0)
    al, be, mu = baselines.beta_prior([g.rate.tolist() for _, g in kap.groupby("b_code")])
    state["baselines"] = {"beta_alpha": al, "beta_beta": be, "globale_quote": mu}
    state["rueckfall"] = 0.5
    state["herkunft"] = {"revision": "54074453da7b9911be0f48e4c560be547bc84d21", "benchmarks": int(p.b_code.nunique()),
                         "paare": int(len(p)), "cv": a.cv, "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    ziel = HIER / "paket" / "state_final.json"
    ziel.write_text(json.dumps(state, indent=0))
    zp, sha = baue(ziel, HIER / "dist", "paiec_hier", state["herkunft"]["zeit_utc"])
    print(json.dumps({"state": str(ziel), "zip": str(zp), "sha_state": sha, "bytes": zp.stat().st_size,
                      "hyp": {k: v for k, v in state["hyp"].items()}, "platt": state["platt"],
                      "dauer_s": round(time.time() - t0, 1)}, indent=1))
