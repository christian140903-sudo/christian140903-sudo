"""Auswertung der Methoden-Liga: Tabellen (CSV), gepaarte Vergleiche gegen v1, Lernkurven (PNG), Laufzeiten, Gitter.

Aufruf: PAIEC_WORK=... python3 -I liga_auswertung.py --liga <ordner mit saetze_f*.parquet> --aus <ergebnisse-ordner>
Liest zusätzlich PAIEC_WORK/modell/cv_REG2/saetze_f*.parquet (v1 = hier_item, hier_kal, beta_binomial,
empirischer_mittelwert, konstant_0.5; identisches Protokoll) und beschränkt sich auf die Falten/Saaten der Liga-Sätze.
Primärmetrik: Paar-ALC (Paare gleich gewichtet, Mittel über Saaten je Paar). Gepaarte Differenz zu v1 je Paar, SE
cluster-robust über Benchmarks (metrik.cluster_vergleich, Regel mittel + 2 SE < 0) und zusätzlich SE über die 10 Falten.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parents[1] / "modell"))
import metrik  # noqa: E402
from inferenz import stufe  # noqa: E402

WORK = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))
V1 = "v1_hier_item"
UMBENENNEN = {"hier_item": V1, "hier_kal": "v1_ohne_itemstufe"}
REIHENFOLGE = [V1, "v1_ohne_itemstufe", "stack", "mf", "irt2pl", "irt1pl", "knn", "gb", "beta_binomial",
               "empirischer_mittelwert", "konstant_0.5"]
REGIME = ["S1", "S2", "S3", "S30", "kompakt10"]
# Kategorische Farben (dataviz-Palette, feste Reihenfolge, nie zyklisch); Referenzlinien grau
FARBEN = {V1: "#2a78d6", "mf": "#eb6834", "irt2pl": "#1baf7a", "irt1pl": "#eda100", "knn": "#e87ba4", "gb": "#008300",
          "stack": "#6250d6", "beta_binomial": "#e34948", "empirischer_mittelwert": "#6b6b6b", "v1_ohne_itemstufe": "#2a78d6"}
STIL = {"v1_ohne_itemstufe": ":", "empirischer_mittelwert": "--"}


def lade(liga):
    teile = sorted(Path(liga).glob("saetze_f*.parquet"))
    if not teile:
        raise SystemExit("keine Liga-Sätze")
    li = pd.concat([pd.read_parquet(t) for t in teile], ignore_index=True)
    falten = sorted(li.falte.unique())
    saaten = sorted(li.saat.unique())
    reg = pd.concat([pd.read_parquet(WORK / "cv_REG2" / f"saetze_f{f}.parquet") for f in falten], ignore_index=True)
    reg = reg[reg.saat.isin(saaten) & reg.S.isin(li.S.unique())]
    return li, reg, falten, saaten


def identitaet(li, reg):
    keys = ["saat", "S", "praediktor", "budget", "b_code", "s_code"]
    zeilen = []
    for pr in ("beta_binomial", "empirischer_mittelwert"):
        m = li[li.praediktor == pr].merge(reg[reg.praediktor == pr], on=keys, suffixes=("_l", "_r"), how="outer",
                                          indicator=True)
        zeilen.append({"praediktor": pr, "saetze_liga": int((li.praediktor == pr).sum()),
                       "saetze_reg2": int((reg.praediktor == pr).sum()), "nur_einseitig": int((m._merge != "both").sum()),
                       "max_abs_dq": float((m.q_l - m.q_r).abs().max()), "max_abs_dbrier": float((m.brier_l - m.brier_r).abs().max()),
                       "max_abs_dR": float((m.R_l - m.R_r).abs().max())})
    return pd.DataFrame(zeilen)


def paar_alc(df):
    d = df.assign(wb=df.budget.map(GEW) * df.brier)
    keys = ["S", "praediktor", "b_code", "s_code"]
    g = d.groupby(keys + ["saat"]).wb.sum().reset_index()
    pa = g.groupby(keys).wb.mean().rename("alc").reset_index()
    pb = df.groupby(keys + ["budget"]).brier.mean().unstack("budget")
    pb.columns = [f"B{c}" for c in pb.columns]
    extra = df.groupby(keys).agg(falte=("falte", "first"), bekannt=("bekannt", "first")).reset_index()
    return pa.merge(pb.reset_index(), on=keys).merge(extra, on=keys)


def tabelle_brier(pa):
    zeilen = []
    for (S, pr), g in pa.groupby(["S", "praediktor"]):
        z = {"S": S, "praediktor": pr, "alc": g.alc.mean(), "alc_benchmark_balanciert": g.groupby("b_code").alc.mean().mean(),
             "n_paare": len(g), "n_benchmarks": g.b_code.nunique()}
        z.update({c: g[c].mean() for c in g.columns if c.startswith("B")})
        zeilen.append(z)
    t = pd.DataFrame(zeilen)
    t["rang"] = t.groupby("S").alc.rank(method="min").astype(int)
    return t.sort_values(["S", "alc"])


def vergleich(pa, S, modell, referenz):
    x = pa[pa.S == S]
    a = x[x.praediktor == modell].set_index(["b_code", "s_code"])
    b = x[x.praediktor == referenz].set_index(["b_code", "s_code"])
    j = a[["alc", "falte"]].join(b[["alc"]], rsuffix="_r", how="inner")
    d = j.alc - j.alc_r
    out = metrik.cluster_vergleich(d.tolist(), [i[0] for i in d.index])
    je_f = d.groupby(j.falte).mean()
    out.update({"S": S, "modell": modell, "referenz": referenz, "n_falten": int(len(je_f)),
                "se_falten": float(je_f.std(ddof=1) / np.sqrt(len(je_f))) if len(je_f) > 1 else None,
                "falten_mit_vorteil": int((je_f < 0).sum()),
                "diff_benchmark_balanciert": float(d.groupby(level=0).mean().mean())})
    if "ki95" in out:
        out["ki95_unten"], out["ki95_oben"] = out.pop("ki95")
    out.pop("schwelle", None)
    return out


def laufzeiten(liga, falten):
    zeilen = []
    for f in falten:
        pfad = Path(liga) / f"zeiten_f{f}.json"
        if pfad.exists():
            for pr, v in json.loads(pfad.read_text()).items():
                zeilen.append(dict(falte=f, praediktor=pr, **v))
    if not zeilen:
        return pd.DataFrame()
    z = pd.DataFrame(zeilen)
    return z.groupby("praediktor").agg(ms_je_1000_paar_median=("ms_je_1000_paar", "median"),
                                       ms_je_1000_item_median=("ms_je_1000_item", "median"),
                                       n_paar=("n_paar", "sum"), n_item=("n_item", "sum")).reset_index()


def gitter(liga, falten):
    hy = [pd.read_csv(Path(liga) / f"hyper_f{f}.csv") for f in falten if (Path(liga) / f"hyper_f{f}.csv").exists()]
    wa = []
    for f in falten:
        p = Path(liga) / f"wahl_f{f}.json"
        if p.exists():
            w = json.loads(p.read_text())
            for fam, cfg in w.items():
                if fam == "stack":
                    wa.append({"falte": f, "familie": fam, "wahl": json.dumps(cfg["gewichte"])})
                else:
                    wa.append({"falte": f, "familie": fam, "wahl": ",".join(f"{k}={v}" for k, v in cfg.items())})
    return (pd.concat(hy, ignore_index=True) if hy else pd.DataFrame()), pd.DataFrame(wa)


def platt_verschachtelt(df, basis="S3"):
    """Sekundär: Platt je Budget-Stufe, je Falte auf den anderen Falten gefittet (wie v1), Brier paarkonstant."""
    from scipy.optimize import minimize

    def lg(q):
        q = np.clip(q, 1e-6, 1 - 1e-6)
        return np.log(q / (1 - q))

    def fit(q, R):
        x = lg(q)

        def f(ab):
            p = 1 / (1 + np.exp(-(ab[0] * x + ab[1])))
            return float(np.mean((p - R) ** 2))
        return minimize(f, [1.0, 0.0], method="Nelder-Mead").x

    df = df.assign(stufe=[stufe(int(n)) for n in df.n_eigen])
    neu = []
    for pr, h in df.groupby("praediktor"):
        for f in sorted(h.falte.unique()):
            tr = h[(h.falte != f) & (h.S == basis)]
            pl = {s: fit(g.q.values, g.R.values) for s, g in tr.groupby("stufe")}
            te = h[h.falte == f].copy()
            q = te.q.values.copy()
            for s, ab in pl.items():
                m = te.stufe.values == s
                q[m] = 1 / (1 + np.exp(-(ab[0] * lg(q[m]) + ab[1])))
            q = np.clip(q, 1e-4, 1 - 1e-4)
            te["q"] = q
            te["brier"] = (q - te.R.values) ** 2 + te.R.values * (1 - te.R.values)
            te["praediktor"] = pr + "_platt"
            neu.append(te)
    return pd.concat(neu, ignore_index=True)


def lernkurven(tab, aus, methoden):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bud = list(metrik.BUDGETS)
    for S in REGIME:
        t = tab[tab.S == S].set_index("praediktor")
        if t.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4.4), dpi=150)
        for pr in methoden:
            if pr not in t.index:
                continue
            y = [t.loc[pr, f"B{b}"] for b in bud]
            ax.plot(range(len(bud)), y, marker="o", ms=3.5, lw=1.6, ls=STIL.get(pr, "-"), color=FARBEN.get(pr, "#444"),
                    label=f"{pr} (ALC {t.loc[pr, 'alc']:.4f})")
        ax.set_xticks(range(len(bud)))
        ax.set_xticklabels([str(b) for b in bud])
        ax.set_xlabel("Label-Budget je Paar")
        ax.set_ylabel("Brier (Mittel über Paare, itemgenau)")
        ax.set_title(f"Lernkurven, Regime {S}")
        lo = min(t.loc[pr, f"B{b}"] for pr in methoden if pr in t.index for b in bud)
        ax.set_ylim(max(0.1, lo - 0.01), 0.27)
        ax.grid(alpha=0.25, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(fontsize=7, frameon=False, ncol=2, loc="lower left")
        fig.tight_layout()
        fig.savefig(aus / f"lernkurven_{S}.png")
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", required=True)
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    abb = aus.parent / "abbildungen"
    abb.mkdir(parents=True, exist_ok=True)
    li, reg, falten, saaten = lade(a.liga)
    ident = identitaet(li, reg)
    ident.to_csv(aus / "identitaet_protokoll.csv", index=False)
    print(ident.to_string())
    reg = reg.assign(praediktor=reg.praediktor.map(lambda p: UMBENENNEN.get(p, p)))
    reg = reg[reg.praediktor.isin([V1, "v1_ohne_itemstufe", "beta_binomial", "empirischer_mittelwert", "konstant_0.5"])]
    li = li[~li.praediktor.isin(["beta_binomial", "empirischer_mittelwert"])]
    df = pd.concat([li, reg[li.columns]], ignore_index=True)
    pa = paar_alc(df)
    pa.to_parquet(aus / "paar_alc.parquet", index=False)
    tab = tabelle_brier(pa)
    tab.to_csv(aus / "brier_je_budget.csv", index=False, float_format="%.5f")
    # bekannt / unbekannt
    tabelle_brier(pa[pa.bekannt]).to_csv(aus / "brier_je_budget_bekannte_subjekte.csv", index=False, float_format="%.5f")
    tabelle_brier(pa[~pa.bekannt]).to_csv(aus / "brier_je_budget_unbekannte_subjekte.csv", index=False, float_format="%.5f")
    vgl = []
    for S in REGIME:
        for pr in sorted(pa.praediktor.unique()):
            if pr != V1:
                vgl.append(vergleich(pa, S, pr, V1))
        for pr in sorted(pa.praediktor.unique()):
            if pr not in (V1, "beta_binomial"):
                vgl.append(vergleich(pa, S, pr, "beta_binomial"))
    v = pd.DataFrame(vgl)
    v.to_csv(aus / "vergleich_gepaart.csv", index=False, float_format="%.6f")
    # Rangfolge je Regime
    rang = tab.pivot(index="praediktor", columns="S", values="alc").reindex(columns=REGIME)
    rang["rang_mittel"] = tab.pivot(index="praediktor", columns="S", values="rang").reindex(columns=REGIME).mean(axis=1)
    rang.sort_values("rang_mittel").to_csv(aus / "rangfolge.csv", float_format="%.5f")
    lz = laufzeiten(a.liga, falten)
    lz.to_csv(aus / "laufzeit.csv", index=False, float_format="%.3f")
    hy, wa = gitter(a.liga, falten)
    hy.to_csv(aus / "hyper_gitter.csv", index=False, float_format="%.5f")
    wa.to_csv(aus / "hyper_wahl.csv", index=False)
    # Sekundär: Platt-kalibrierte Varianten (paarkonstant), nur Paarebene vergleichbar
    pl = platt_verschachtelt(df[df.praediktor.isin(["irt2pl", "irt1pl", "mf", "knn", "gb", "stack", "beta_binomial"])])
    basis_pk = df.copy()
    basis_pk["brier"] = (basis_pk.q - basis_pk.R) ** 2 + basis_pk.R * (1 - basis_pk.R)
    basis_pk["praediktor"] = basis_pk.praediktor + "_paarkonstant"
    pa_pl = paar_alc(pd.concat([pl, basis_pk], ignore_index=True))
    tabelle_brier(pa_pl).to_csv(aus / "sekundaer_platt_paarkonstant.csv", index=False, float_format="%.5f")
    lernkurven(tab, abb, [p for p in REIHENFOLGE if p not in ("konstant_0.5",)])
    meta = {"falten": [int(f) for f in falten], "saaten": [int(s) for s in saaten], "n_saetze_liga": int(len(li)),
            "n_saetze_reg2": int(len(reg)), "methoden": sorted(pa.praediktor.unique().tolist())}
    (aus / "meta.json").write_text(json.dumps(meta, indent=1))
    print(rang.sort_values("rang_mittel").round(5).to_string())
    for S in ("S1", "S3", "S30"):
        print(f"--- {S}: Differenz zu {V1} (mittel, SE cluster, Urteil, SE Falten)")
        for _, r in v[(v.S == S) & (v.referenz == V1)].sort_values("mittel").iterrows():
            print(f"  {r.modell:24s} {r.mittel:+.5f}  SE {r.se:.5f}  {r.urteil:24s} SE_f {r.se_falten}")


if __name__ == "__main__":
    main()
