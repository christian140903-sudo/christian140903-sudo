"""Gruppierte Kreuzvalidierung (Benchmark-kalt = Design A; Benchmark- und Subjekt-kalt = Design B).

Aufruf: python3 -I kreuzvalidierung.py --design A [--falten 10] [--saaten 0,1,2] [--S 1,3,30] [--prozesse 4]
        python3 -I kreuzvalidierung.py --phase 2 --von cv_A   (Zustände + verschachtelte Platt-Parameter aus Phase 1,
        Item-Stufe, Regime S3 / S30 / kompakt10; schreibt nach cv_A_p2)
Schreibt nach $PAIEC_WORK/modell/cv_<design>/:
  saetze_f<k>.parquet  je (Saat, S, Prädiktor, Budget, Paar): q, R, N, n_eigen, bekannt, kalt
  state_f<k>.json      trainierter Zustand der Falte
  status.json, log.txt (nur anhängen)
Regeln (MODELL.md §4, vor dem ersten Lauf festgelegt): Falten über Benchmarks mit Testpaaren, feste Saat 1234;
Testpaare je Benchmark gekappt auf 30 (kappe, Saat 0); Design B: Namen in 5 Falten (sha256 des Namens),
Falte f schließt Namen der Namensfalte f mod 5 aus dem Training aus.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baselines  # noqa: E402
import simulator  # noqa: E402
import training  # noqa: E402
from inferenz import Modell  # noqa: E402

SCRATCH = training.SCRATCH
G = {}


def namensfalte(name):
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big") % 5


def log(aus, text):
    zeile = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + text
    with open(aus / "log.txt", "a", encoding="utf-8") as f:
        f.write(zeile + "\n")
    print(zeile, flush=True)


def faltenzuteilung(p, falten, saat=1234):
    """P4 (Prereg §1): Falten-Saat als Parameter; v1 = 1234 (Discovery), Konfirmation = 200."""
    bs = np.array(sorted(p.loc[p["items"] >= 80, "b_code"].unique()))
    rng = np.random.default_rng(saat)
    perm = rng.permutation(len(bs))
    return {int(b): int(i % falten) for b, i in zip(bs[perm], range(len(bs)))}


AGG_JE_B = SCRATCH / "agg_je_b"


def agg_benchmark(b, train_s=None):
    """P4 (speicherschonend): Zeilen des Benchmarks b aus agg_je_b/b<code>.parquet (agg_split.py) in Dateireihenfolge —
    identisch zu agg.iloc[i0:i1] nach stabiler Sortierung (Werte, Reihenfolge, dtypes); nur der Index ist ein anderer
    (wird nirgends benutzt). train_s: optional Filter auf Subjekte (wie agg_tr in v1)."""
    f = AGG_JE_B / f"b{int(b)}.parquet"
    if not f.exists():
        raise SystemExit(f"ABBRUCH: {f} fehlt (agg_split.py zuerst ausführen)")
    df = pq.read_table(f).to_pandas(self_destruct=True)
    if train_s is not None:
        df = df[df.s_code.isin(train_s)]
    return df


class AggStreaming:
    """P4: Platzhalter für agg_tr; trägt nur die Trainingssubjekte. training.trainiere ruft schaetze_tau_i2(agg, ...) auf,
    das hier (Monkeypatch unten) benchmarkweise aus agg_je_b liest, statt die 25-M-Zeilen-Tabelle zu halten."""

    def __init__(self, train_s):
        self.train_s = set(int(x) for x in train_s)


def schaetze_tau_i2_streaming(agg, b_codes, seed=0, max_s=20, max_i=600):
    """Zeile für Zeile training.schaetze_tau_i2 (v1) nachgebildet; einziger Unterschied: g je Benchmark aus Datei statt aus
    sub.groupby('b_code'). Gleiche Iterationsreihenfolge (aufsteigende b_code), gleiche rng-Zugriffe, gleiche Teilmengen."""
    rng = np.random.default_rng(seed)
    werte = []
    for b in sorted(int(x) for x in np.unique(b_codes)):
        g = agg_benchmark(b, agg.train_s)
        if g.empty:
            continue  # Benchmark ohne Zeilen erscheint in v1 nicht in sub.groupby
        cnt = g.groupby("s_code").size()
        subj = cnt[cnt >= 80].index.values
        if len(subj) < 3:
            continue
        subj = rng.choice(subj, min(max_s, len(subj)), replace=False)
        g = g[g.s_code.isin(subj)]
        items = g.i_code.unique()
        if len(items) > max_i:
            g = g[g.i_code.isin(rng.choice(items, max_i, replace=False))]
        t2 = training.rasch_eb(g)
        if np.isfinite(t2):
            werte.append(t2)
    return float(np.median(werte)) if werte else 0.0, len(werte)


def lade_p_cache():
    """P4: Paartabelle p aus Pickle-Cache (exakter Roundtrip), sonst wie v1 über training.lade_paare() und Cache anlegen."""
    cache = SCRATCH / "p_cache_v1.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    p, agg = training.lade_paare()
    del agg
    p.to_pickle(cache)
    return p


def praediktoren(state, train):
    kap = training.kappe(train, seed=0)
    raten = [g.rate.tolist() for _, g in kap.groupby("b_code")]
    al, be, mu = baselines.beta_prior(raten)
    return {
        "konstant_0.5": baselines.Konstant(0.5),
        "empirischer_mittelwert": baselines.EmpirischerMittelwert(),
        "globale_quote": baselines.Konstant(mu),
        "beta_binomial": baselines.BetaBinomial(al, be),
        "hier_ohne_subjekt": Modell(state, subjektwissen=False, kalibrierung=False, item_effekt=False),
        "hier_ohne_steigung": Modell(state, steigung=False, kalibrierung=False, item_effekt=False),
        "hier": Modell(state, kalibrierung=False, item_effekt=False),
    }, {"beta_alpha": al, "beta_beta": be, "globale_quote": mu}


def praediktoren_p2(state):
    b = state["baselines"]
    out = {"konstant_0.5": baselines.Konstant(0.5), "empirischer_mittelwert": baselines.EmpirischerMittelwert(),
           "beta_binomial": baselines.BetaBinomial(b["beta_alpha"], b["beta_beta"]),
           "hier_kal": Modell(state, item_effekt=False), "hier_item": Modell(state)}
    for name, f in (("hier_item_t05", 0.5), ("hier_item_t2", 2.0)):
        st = json.loads(json.dumps(state))
        st["hyp"]["tau_i2"] = state["hyp"]["tau_i2"] * f
        out[name] = Modell(st)
    return out


def falte(f):
    a = G["args"]
    p, agg, starts, subj, f_je_b = G["p"], G["agg"], G["starts"], G["subj"], G["f_je_b"]
    aus = Path(a.aus)
    ziel = aus / f"saetze_f{f}.parquet"
    if ziel.exists():
        return f, "übersprungen (vorhanden)"
    t0 = time.time()
    test_b = sorted(b for b, x in f_je_b.items() if x == f)
    train = p[~p.b_code.isin(test_b)]
    if a.design == "B":
        train = train[~((train.name != "") & (train.name.map(namensfalte) == f % 5))]
    if a.phase == 1:
        if a.agg_sparsam:
            training.schaetze_tau_i2 = schaetze_tau_i2_streaming  # Monkeypatch (training.py bleibt byteidentisch)
            agg_tr = AggStreaming(train.s_code.unique())
        else:
            agg_tr = agg[agg.b_code.isin(train.b_code.unique()) & agg.s_code.isin(train.s_code.unique())]
        state = training.trainiere(train, seed=f, protokoll=lambda s: None, agg=agg_tr)
        del agg_tr
        pr, base = praediktoren(state, train)
        state["baselines"] = base
        (aus / f"state_f{f}.json").write_text(json.dumps(state))
        regime = [("S%d" % int(x), int(x)) for x in a.S.split(",")]
    else:
        von = SCRATCH / a.von
        state = json.loads((von / f"state_f{f}.json").read_text())
        ausw = json.loads((von / "auswertung.json").read_text())
        stufen = set(ausw["platt_paket"].keys())
        if a.platt_stufen:  # P4: Stufenmenge des eingereichten Pakets erzwingen (v1: {0,1,3,7}); Pipeline-Wahl = Sensitivität
            stufen = set(x.strip() for x in a.platt_stufen.split(","))
        else:  # P4 für v2.0-core (kern K4f, identische drei Zeilen): je Falte die verschachtelt gewählte Stufenmenge,
            # falls die Phase-1-Auswertung (kern/auswertung.py) sie liefert; sonst v1-Gesamtwahl (platt_paket)
            vw = (ausw.get("platt_stufenwahl_verschachtelt") or {}).get("verschachtelt_je_falte")
            if vw is not None:
                stufen = set(str(s) for s in vw[str(f)])
        state["platt"] = {k: v for k, v in ausw["platt_je_falte"][str(f)].items() if k in stufen}
        pr = praediktoren_p2(state)
        regime = [(r, -int(r[7:]) if r.startswith("kompakt") else int(r[1:])) for r in a.regime.split(",")]
    testpaare = training.kappe(p[p.b_code.isin(test_b)], seed=0)
    zeilen = []
    for seed in [int(x) for x in a.saaten.split(",")]:
        for b, tp in testpaare.groupby("b_code"):
            if a.agg_sparsam:
                agg_b = agg_benchmark(b)
            else:
                i0, i1 = starts[b]
                agg_b = agg.iloc[i0:i1]
            paare = simulator.baue_paare(agg_b, tp, subj, seed)
            for rname, S in regime:
                laeufe = (simulator.kompakte_laeufe(agg_b, tp, subj, seed, S=-S) if S < 0
                          else simulator.gruppiere_laeufe(paare, S, seed))
                for lauf in laeufe:
                    for r in simulator.bewerte_lauf(lauf, pr, seed):
                        zeilen.append((seed, rname) + r)
    df = pd.DataFrame(zeilen, columns=["saat", "S", "praediktor", "budget", "b_code", "s_code", "q", "R", "N",
                                       "n_eigen", "brier", "n_items_angepasst"])
    meta = testpaare.set_index("s_code")[["name"]]
    df["bekannt"] = df.s_code.map(meta.name).map(lambda n: bool(n) and n in state["theta"])
    df["kalt"] = df.s_code.map(meta.name).map(lambda n: bool(n) and a.design == "B" and namensfalte(n) == f % 5)
    df["falte"] = f
    tmp = ziel.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(ziel)
    stufen_txt = ("Platt-Stufen " + ",".join(sorted(state["platt"], key=int))) if a.phase == 2 else ""  # P4: Stufenmenge je Falte ins Log
    return f, f"{len(test_b)} Benchmarks, {len(testpaare)} Paare, {len(df)} Sätze, {time.time() - t0:.0f} s {stufen_txt}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="A", choices=["A", "B"])
    ap.add_argument("--falten", type=int, default=10)
    ap.add_argument("--saaten", default="0,1,2")
    ap.add_argument("--S", default="1,3,30")
    ap.add_argument("--prozesse", type=int, default=4)
    ap.add_argument("--nur", default="", help="nur diese Falten, z. B. 0,1")
    ap.add_argument("--aus", default="")
    ap.add_argument("--phase", type=int, default=1, choices=[1, 2])
    ap.add_argument("--von", default="", help="Phase 2: Ordner der Phase 1 (unter SCRATCH)")
    ap.add_argument("--regime", default="S3,S30,kompakt10", help="Phase 2: Regime, z. B. S1,S2,S3,S30,kompakt10")
    ap.add_argument("--falten-saat", type=int, default=1234, help="P4: Saat der Faltenzuteilung (v1: 1234)")
    ap.add_argument("--platt-stufen", default="", help="P4 Phase 2: Platt-Stufenmenge erzwingen, z. B. 0,1,3,7 (leer = Wahl der Phase-1-Auswertung)")
    ap.add_argument("--agg-sparsam", type=int, default=1, help="P4: 1 = agg nicht im Speicher halten, je Benchmark aus Parquet lesen (OOM-Schutz; bitgleich belegt)")
    a = ap.parse_args()
    a.aus = a.aus or str(SCRATCH / (f"cv_{a.design}" if a.phase == 1 else f"{a.von}_p2"))
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    log(aus, f"Start Phase {a.phase} Design {a.design}, Falten {a.falten}, Saaten {a.saaten}, S {a.S}, regime {a.regime}, von {a.von}, falten_saat {a.falten_saat}, platt_stufen '{a.platt_stufen}'")
    if a.agg_sparsam:
        p = lade_p_cache()  # P4: 31 M agg-Zeilen nicht halten; Benchmark-Zeilen werden je Bedarf gelesen
        agg, starts = None, None
    else:
        p, agg = training.lade_paare()
        agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
        bc = agg.b_code.values
        starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right")))
                  for b in np.unique(bc)}
    sub = pd.read_parquet(SCRATCH / "subjekte.parquet")
    subj = {int(r["s_code"]): {f: r[f] for f in ("normalized_name", "provider", "release_date", "access_date",
                                                   "harness", "harness_version", "reasoning_effort",
                                                   "subject_features_extra")}
            for r in sub.to_dict("records")}
    f_je_b = faltenzuteilung(p, a.falten, a.falten_saat)
    (aus / "falten.json").write_text(json.dumps({str(k): v for k, v in f_je_b.items()}))
    # P4 mechanische Prüfung (Prereg §1): bei neuer Falten-Saat MUSS die Zuteilung von cv_A/falten.json abweichen (fail-closed)
    ref = SCRATCH / "cv_A" / "falten.json"
    if ref.exists():
        alt = {int(k): v for k, v in json.loads(ref.read_text()).items()}
        n_diff = sum(1 for k, v in f_je_b.items() if alt.get(k) != v)
        log(aus, f"Faltenzuteilung: {n_diff}/{len(f_je_b)} Benchmarks in anderer Falte als cv_A (Saat 1234)")
        if a.falten_saat != 1234 and n_diff == 0:
            log(aus, "ABBRUCH: neue Falten-Saat, aber Zuteilung identisch mit cv_A (fail-closed)")
            raise SystemExit(3)
        if a.falten_saat == 1234 and n_diff != 0:
            log(aus, "ABBRUCH: Saat 1234, aber Zuteilung weicht von cv_A ab (Reproduzierbarkeit verletzt, fail-closed)")
            raise SystemExit(3)
    G.update({"args": a, "p": p, "agg": agg, "starts": starts, "subj": subj, "f_je_b": f_je_b})
    liste = [int(x) for x in a.nur.split(",")] if a.nur else list(range(a.falten))
    fertig = []
    if a.prozesse > 1:
        with mp.get_context("fork").Pool(a.prozesse) as pool:
            for f, txt in pool.imap_unordered(falte, liste):
                log(aus, f"Falte {f}: {txt}")
                fertig.append(f)
    else:
        for f in liste:
            f, txt = falte(f)
            log(aus, f"Falte {f}: {txt}")
            fertig.append(f)
    n_da = sum(1 for k in range(a.falten) if (aus / f"saetze_f{k}.parquet").exists())
    (aus / "status.json").write_text(json.dumps({"falten": a.falten, "fertig": n_da, "saaten": a.saaten,
                                                 "falten_saat": a.falten_saat, "phase": a.phase, "design": a.design, "platt_stufen": a.platt_stufen,
                                                 "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    log(aus, f"Ende: {n_da}/{a.falten} Falten vorhanden")


if __name__ == "__main__":
    main()
