"""v0_eff.py — H2b(i): Pooling über Subjekte als budget- und S-abhängige Senkung des Prior-Fehlers (Prereg v2 §4 H2b).

(i) Mittel (q_B − R_E)² von hier_item bei B = 1 und B = 3; gepaarte Differenzen je Paar (Mittel über Saaten) zwischen
benachbarten Regimen S1→S2, S2→S3, S3→S30 (Design A); Regel: jeder der 6 Schritte *better* (d̂ + 2·SE < 0).
Zusatz (für Anhang/Abb.): effektives V0_eff(S, B) = aus der exakten Formel (alc_law) nach V0 aufgelöst, mit U, κ, D, F des
Laufs — zeigt, wie stark der Prior-Fehler durch Pooling scheinbar sinkt.
Aufruf: python3 -I v0_eff.py --p1 cv_K_A --p2 cv_K_A2 --aus ergebnisse/v0_eff_A.json
"""
import argparse
import sys
import traceback

import numpy as np

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402
import lernkurve_test as lt

SCHRITTE = (("S1", "S2"), ("S2", "S3"), ("S3", "S30"))


def h2b_i(df2):
    x = df2[(df2.praediktor == "hier_item") & (df2.budget.isin([1, 3]))].copy()
    x["sq"] = (x.q - x.R) ** 2
    pp = x.groupby(["S", "budget", "b_code", "s_code"]).sq.mean().reset_index()
    out = {}
    n_better = 0
    for B in (1, 3):
        for s_von, s_nach in SCHRITTE:
            a = pp[(pp.S == s_von) & (pp.budget == B)].set_index(["b_code", "s_code"]).sq
            b = pp[(pp.S == s_nach) & (pp.budget == B)].set_index(["b_code", "s_code"]).sq
            if a.empty or b.empty:
                out[f"B{B}:{s_von}->{s_nach}"] = {"verdict": "not_evaluated", "grund": "Regime fehlt"}
                continue
            j = a.to_frame("a").join(b.to_frame("b"), how="inner")
            d = (j.b - j.a)
            v = ku.metrik.cluster_vergleich(d.tolist(), [i[0] for i in d.index])
            u = ku.urteil(v["mittel"], v["se"])
            u.update({"mse_von": float(j.a.mean()), "mse_nach": float(j.b.mean()), "n_paare": v["n_paare"]})
            n_better += u["verdict"] == "better" or (u.get("zusatz", "").startswith("better"))
            out[f"B{B}:{s_von}->{s_nach}"] = ku.rund(u)
    out["schritte_better"] = int(n_better)
    out["regel"] = "6/6 Schritte better (d + 2 SE < 0, streng fallend mit S)"
    out["verdict"] = "passed" if n_better == 6 else ("not_evaluated" if any(
        isinstance(v, dict) and v.get("verdict") == "not_evaluated" for v in out.values()) else "failed")
    return out


def v0_eff_tabelle(df2, mom):
    """V0_eff(S,B) = ((B+κ)²·(mse − B/(B+κ)·D) − B·(U − (B−1)·F)) / κ²  (exakte Form nach V0 aufgelöst)."""
    U, k, D, F = mom["U"], mom["kappa"], mom["D"], mom["F"]
    out = {"U": U, "kappa": k, "D": D, "F": F, "V0_B0_hier_item": mom["V0_hi"], "V0_B0_beta_binomial": mom["V0_bb"]}
    for praed in ("hier_item", "beta_binomial"):
        out[praed] = {}
        for S in ("S1", "S2", "S3", "S30", "kompakt10"):
            o = lt.beobachtet(df2, praed, S)
            if o is None:
                continue
            row = {}
            for B, mse in o.items():
                if B == 0:
                    row["0"] = mse
                    continue
                frac = B / (B + k)
                row[str(B)] = ((B + k) ** 2 * (mse - frac * D) - B * (U - (B - 1) * F)) / (k * k)
            out[praed][S] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", required=True)
    ap.add_argument("--p2", required=True)
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    erg = {"zeit_utc": ku.jetzt(), "p1": a.p1, "p2": a.p2}
    rc = 0
    try:
        d2, df2, st2 = ku.lade_saetze(a.p2)
        erg["saaten"] = ku.saaten(df2)
        erg["H2b_i"] = h2b_i(df2)
        mom, _, _ = lt.momente(df2, ku.WORK / a.p1)
        erg["V0_eff"] = ku.rund(v0_eff_tabelle(df2, mom), 6)
    except Exception as e:  # noqa: BLE001
        erg["fehler"] = f"{type(e).__name__}: {e}"
        erg["traceback"] = traceback.format_exc()
        erg.setdefault("H2b_i", {"verdict": "not_evaluated", "grund": erg["fehler"]})
        rc = 2
    ku.schreibe_json(a.aus, erg)
    h = erg["H2b_i"]
    print("H2b(i):", h.get("verdict"), {k: (v.get("verdict"), v.get("d"), v.get("se")) for k, v in h.items() if isinstance(v, dict)})
    if "V0_eff" in erg:
        print("V0_eff hier_item:", erg["V0_eff"]["hier_item"])
    if rc:
        print("FEHLER:", erg.get("fehler"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
