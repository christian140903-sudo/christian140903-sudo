"""lernkurve_test.py — H2a (Formel vs. Beta-Binomial-Lernkurve), H2b(ii) (fixed-κ-Formel vs. gepooltes hier_item),
H2c (κ_ML vs. U/V0) nach Prereg v2 §3–4; Formelwerte ausschließlich aus ./theorie/alc_law.py.

Aufruf: python3 -I lernkurve_test.py --p1 cv_K_A --p2 cv_K_A2 --design A --aus ergebnisse/lernkurve_A.json
Schätzrezepte (eingefroren, Prereg §3): U = Mittel R_E(1−R_E) über Testpaare×Saaten (S1, B0); V0 = Mittel (q_0−R_E)²
des jeweiligen Prädiktors (S1, B0); κ = paargewichtetes Mittel von (α_f+β_f) über die Falten des Laufs; D, F aus
agg.parquet für genau die Testpaare des Laufs: D_pair = 4·Var_i(k_i/n_i)/(N−1), F_pair = Var_i/(N//2−1), N = Itemzahl.
Nichts wird an die Kurve gefittet. Fail-closed (Rückgabecode 2 bei fehlender Eingabe).
"""
import argparse
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.compute as pc

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402

sys.path.insert(0, str(ku.HIER.parent / "theorie"))
import alc_law  # noqa: E402  (P2-Werkzeug, nur gelesen/importiert)

PRUEF_BUDGETS = (1, 3, 7, 15, 31)


def kappa_je_falte(p1_dir):
    out = {}
    for f in range(10):
        st = p1_dir / f"state_f{f}.json"
        if not st.exists():
            raise ku.KonfError(f"{st} fehlt")
        b = json.loads(st.read_text())["baselines"]
        out[f] = float(b["beta_alpha"]) + float(b["beta_beta"])
    return out


def _momente_frame(df, keys):
    df = df.merge(keys, on=["b_code", "s_code"], how="inner")
    if df.empty:
        return None
    df["p"] = df.k.astype(float) / df.n.astype(float)
    return df.groupby(["b_code", "s_code"]).p.agg(["var", "size", "mean"])  # var: ddof=1 -> unten umgerechnet


def split_momente(testpaare):
    """D, F je Testpaar aus agg (nur Zeilen der Test-Benchmarks, dann auf die Paare gefiltert).
    Speicherschonend: benchmarkweise aus agg_je_b/ (agg_split.py), sonst pyarrow-Filter auf agg.parquet."""
    keys = testpaare[["b_code", "s_code"]].drop_duplicates()
    bs = sorted(int(b) for b in keys.b_code.unique())
    jb = ku.WORK / "agg_je_b"
    teile = []
    if jb.exists():
        for b in bs:
            f = jb / f"b{b}.parquet"
            if not f.exists():
                raise ku.KonfError(f"{f} fehlt")
            t = pq.read_table(f, columns=["b_code", "s_code", "n", "k"]).to_pandas(self_destruct=True)
            g = _momente_frame(t, keys[keys.b_code == b])
            if g is not None:
                teile.append(g)
    else:
        agg_pfad = ku.WORK / "agg.parquet"
        if not agg_pfad.exists():
            raise ku.KonfError(f"{agg_pfad} fehlt")
        t = pq.read_table(agg_pfad, columns=["b_code", "s_code", "n", "k"], filters=[("b_code", "in", bs)]).to_pandas()
        g = _momente_frame(t, keys)
        if g is not None:
            teile.append(g)
    if not teile:
        raise ku.KonfError("keine agg-Zeilen für die Testpaare")
    g = pd.concat(teile)
    N = g["size"].values.astype(float)
    V = g["var"].fillna(0.0).values * (N - 1) / N  # Populationsvarianz (ddof=0)
    if (N < 4).any():
        raise ku.KonfError("Testpaar mit < 4 Items")
    D_pair = 4.0 * V / (N - 1.0)
    NA = np.floor(N / 2.0)
    F_pair = V / (NA - 1.0)
    m = pd.DataFrame({"b_code": [i[0] for i in g.index], "s_code": [i[1] for i in g.index], "N": N, "V": V,
                      "D_pair": D_pair, "F_pair": F_pair})
    if len(m) != len(keys):
        raise ku.KonfError(f"{len(m)} Paare mit Momenten, {len(keys)} Testpaare")
    return m


def momente(df2, p1_dir):
    """U, V0_BB, V0_hi, κ (paargewichtet), D, F für den Lauf — plus Zwischenwerte."""
    b0 = df2[(df2.S == "S1") & (df2.budget == 0)]
    bb = b0[b0.praediktor == "beta_binomial"]
    hi = b0[b0.praediktor == "hier_item"]
    if bb.empty or hi.empty:
        raise ku.KonfError("S1/B0-Zeilen für beta_binomial oder hier_item fehlen")
    U = float((bb.R * (1 - bb.R)).mean())
    V0_bb = float(((bb.q - bb.R) ** 2).mean())
    V0_hi = float(((hi.q - hi.R) ** 2).mean())
    tp = bb[["b_code", "s_code", "falte"]].drop_duplicates()
    kap = kappa_je_falte(p1_dir)
    n_f = tp.groupby("falte").size()
    kappa = float(sum(kap[int(f)] * n for f, n in n_f.items()) / n_f.sum())
    sm = split_momente(tp)
    D, F = float(sm.D_pair.mean()), float(sm.F_pair.mean())
    return {"U": U, "V0_bb": V0_bb, "V0_hi": V0_hi, "kappa": kappa, "kappa_je_falte": kap,
            "paare_je_falte": {int(f): int(n) for f, n in n_f.items()}, "D": D, "F": F,
            "N_median": float(sm.N.median()), "N_min": float(sm.N.min()), "n_testpaare": int(len(tp)),
            "n_zeilen_S1_B0": int(len(bb))}, sm, tp


def beobachtet(df2, praed, S):
    x = df2[(df2.S == S) & (df2.praediktor == praed)]
    if x.empty:
        return None
    return {int(b): float(((g.q - g.R) ** 2).mean()) for b, g in x.groupby("budget")}


def rel(formel, obs):
    return {str(b): (formel[b] - obs[b]) / obs[b] for b in PRUEF_BUDGETS if b in obs}


def h2a(df2, mom):
    out = {}
    obs = beobachtet(df2, "beta_binomial", "S1")
    if obs is None:
        return {"verdict": "not_evaluated", "grund": "S1/beta_binomial fehlt"}
    U, V0, k, D, F = mom["U"], mom["V0_bb"], mom["kappa"], mom["D"], mom["F"]
    ex = alc_law.lernkurve(U, V0, k, D, F, split="exakt")
    qu = alc_law.lernkurve(U, V0, k, D, 0.0, split="quadrat")
    zt = alc_law.lernkurve(U, V0, k, 0.0, 0.0, split="exakt")
    out["S1"] = {"beobachtet": {str(b): obs[b] for b in obs}, "formel_exakt": {str(b): ex[b] for b in ex},
                 "rel_fehler_exakt": rel(ex, obs), "rel_fehler_quadrat": rel(qu, obs), "rel_fehler_zweiterm": rel(zt, obs)}
    maxabs = max(abs(v) for v in out["S1"]["rel_fehler_exakt"].values())
    out["S1"]["max_abs_rel_fehler_exakt"] = maxabs
    out["S1"]["alle_innerhalb_10_prozent"] = bool(maxabs <= 0.10)
    out["S1"]["alle_innerhalb_3_prozent"] = bool(maxabs <= 0.03)
    out["S1"]["alc_formel_exakt"] = alc_law.alc(U, V0, k, D, F, split="exakt")["ALC"]
    bbr = df2[(df2.S == "S1") & (df2.praediktor == "beta_binomial")]
    out["S1"]["alc_beobachtet_bb"] = float(ku.paar_alc(bbr).alc.mean())
    for S in ("S2", "S3", "S30"):
        o = beobachtet(df2, "beta_binomial", S)
        if o is not None:
            out[S] = {"beobachtet": {str(b): o[b] for b in o}, "rel_fehler_exakt": rel(ex, o),
                      "hinweis": "Sensitivität; Abweichung durch Identitätskollision (n_eigen > B), Prereg §0 Nr. 3"}
    out["verdict_dieses_design"] = "passed" if out["S1"]["alle_innerhalb_10_prozent"] else "failed"
    return out


def h2b_ii(df2, mom):
    """Abweichung der fixed-κ-Formel (V0 = hier_item-B0-Überschuss) von der beobachteten hier_item-Kurve."""
    U, V0, k, D, F = mom["U"], mom["V0_hi"], mom["kappa"], mom["D"], mom["F"]
    ex = alc_law.lernkurve(U, V0, k, D, F, split="exakt")
    out = {"formel_exakt_V0_hier_item": {str(b): ex[b] for b in ex}}
    for S in ("S1", "S2", "S3", "S30"):
        o = beobachtet(df2, "hier_item", S)
        if o is not None:
            out[S] = {"beobachtet": {str(b): o[b] for b in o}, "rel_abweichung_formel": rel(ex, o)}
    try:
        d3 = out["S3"]["rel_abweichung_formel"]["1"]
        d30 = out["S30"]["rel_abweichung_formel"]["1"]
    except KeyError:
        return {"verdict": "not_evaluated", "grund": "S3/S30 hier_item fehlt", **out}
    out["S3_B1_abweichung"] = d3
    out["S30_B1_abweichung"] = d30
    out["regel"] = "S3/B1 in [+10 %, +30 %] und S30/B1 in [+50 %, +110 %]"
    out["S3_im_intervall"] = bool(0.10 <= d3 <= 0.30)
    out["S30_im_intervall"] = bool(0.50 <= d30 <= 1.10)
    out["verdict"] = "passed" if out["S3_im_intervall"] and out["S30_im_intervall"] else "failed"
    return out


def h2c(df2, mom):
    """κ̄_ML (paargewichtet) vs. U/V0 gepoolt (S1, B0, beta_binomial, Saaten gemittelt), Cluster-Bootstrap 2000, Saat 200."""
    b0 = df2[(df2.S == "S1") & (df2.budget == 0) & (df2.praediktor == "beta_binomial")].copy()
    b0["u"] = b0.R * (1 - b0.R)
    b0["v"] = (b0.q - b0.R) ** 2
    pp = b0.groupby(["b_code", "s_code"]).agg(u=("u", "mean"), v=("v", "mean"), falte=("falte", "first")).reset_index()
    gb = pp.groupby("b_code").agg(su=("u", "sum"), sv=("v", "sum"), n=("u", "size"))
    su, sv = gb.su.values, gb.sv.values
    bs = list(gb.index)

    def ratio(idx):
        return su[idx].sum() / sv[idx].sum()

    uv = ratio(np.arange(len(bs)))
    se, ki, _ = ku.cluster_bootstrap(ratio, bs, n_boot=2000, seed=200)
    kap = mom["kappa"]
    diff = kap - uv
    je_falte = {}
    for f, g in pp.groupby("falte"):
        je_falte[str(int(f))] = {"kappa_ML": mom["kappa_je_falte"][int(f)], "U_f": float(g.u.mean()), "V0_f": float(g.v.mean()),
                                 "U_durch_V0_f": float(g.u.mean() / g.v.mean()), "n_paare": int(len(g))}
    bal = float((gb.su / gb.n).mean() / (gb.sv / gb.n).mean())
    out = {"kappa_ML_paargewichtet": kap, "U_durch_V0_gepoolt": float(uv), "differenz": float(diff), "se_boot": se,
           "ci95_boot_U_durch_V0": ki, "U_durch_V0_benchmark_balanciert": bal, "je_falte": je_falte,
           "regel": "|kappa_ML - U/V0| <= 2*SE_boot", "verdict": "passed" if abs(diff) <= 2 * se else "failed",
           "hinweis": "v1 fittet die Beta-Prior per Momentenmethode (baselines.beta_prior), nicht per Marginal-Likelihood; "
                      "kappa_f = alpha_f + beta_f aus state_f.json wie in der Discovery-Rechnung (p2work/h2c_discovery.json)"}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", required=True)
    ap.add_argument("--p2", required=True)
    ap.add_argument("--design", required=True, choices=["A", "B"])
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    erg = {"zeit_utc": ku.jetzt(), "design": a.design, "p1": a.p1, "p2": a.p2}
    rc = 0
    try:
        d2, df2, st2 = ku.lade_saetze(a.p2)
        p1_dir = ku.WORK / a.p1
        erg["saaten"] = ku.saaten(df2)
        mom, sm, tp = momente(df2, p1_dir)
        erg["momente"] = ku.rund({k: v for k, v in mom.items()}, 8)
        erg["H2a"] = ku.rund(h2a(df2, mom), 6)
        erg["H2b_ii"] = ku.rund(h2b_ii(df2, mom), 6)
        erg["H2c"] = ku.rund(h2c(df2, mom), 6) if a.design == "A" else {"verdict": "not_applicable"}
        sm.to_parquet(Path(a.aus).with_name(Path(a.aus).stem + "_testpaare_momente.parquet"), index=False)
    except Exception as e:  # noqa: BLE001
        erg["fehler"] = f"{type(e).__name__}: {e}"
        erg["traceback"] = traceback.format_exc()
        for h in ("H2a", "H2b_ii", "H2c"):
            erg.setdefault(h, {"verdict": "not_evaluated", "grund": erg["fehler"]})
        rc = 2
    ku.schreibe_json(a.aus, erg)
    m = erg.get("momente", {})
    print("Momente:", {k: m.get(k) for k in ("U", "V0_bb", "V0_hi", "kappa", "D", "F", "n_testpaare")})
    if "S1" in erg.get("H2a", {}):
        print("H2a S1 rel. Fehler exakt:", erg["H2a"]["S1"]["rel_fehler_exakt"], "->", erg["H2a"]["verdict_dieses_design"])
    print("H2b(ii):", erg["H2b_ii"].get("S3_B1_abweichung"), erg["H2b_ii"].get("S30_B1_abweichung"), erg["H2b_ii"].get("verdict"))
    print("H2c:", {k: erg["H2c"].get(k) for k in ("kappa_ML_paargewichtet", "U_durch_V0_gepoolt", "se_boot", "verdict")})
    if rc:
        print("FEHLER:", erg.get("fehler"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
