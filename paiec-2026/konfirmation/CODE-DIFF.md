# CODE-DIFF — konfirmation/code_v1/ gegenüber modell/ (v1)

Erzeugt 2026-10-20T21:29:44Z mit `diff -u`. Geändert: kreuzvalidierung.py (Parameter `--falten-saat` + fail-closed-Prüfung der Zuteilung; `--platt-stufen` zum Erzwingen der Paket-Stufenmenge in Phase 2; speicherschonender Pfad `--agg-sparsam`: Paartabelle aus Pickle-Cache, agg benchmarkweise aus `agg_je_b/` (agg_split.py), τ_i²-Schätzung benchmarkweise gestreamt per Monkeypatch — **Bitgleichheit belegt**: Falte 9 neu gerechnet, 80 136 Sätze, max|Δq| = max|ΔR| = max|Δbrier| = 0, Zustand kanonisch gleich, τ_i² identisch, logs/bitgleich_sparsam.log) und auswertung.py (--design-logik). Mathematik, Simulator, Prädiktoren, Metrik, Training, Inferenz byteidentisch zu v1. Neu: agg_split.py (nur Datei-Aufteilung).

## kreuzvalidierung.py
```diff
--- ./modell/kreuzvalidierung.py	2026-10-20 17:22:04.205502745 +0000
+++ kreuzvalidierung.py	2026-10-20 21:29:43.828338374 +0000
@@ -21,6 +21,7 @@
 
 import numpy as np
 import pandas as pd
+import pyarrow.parquet as pq
 
 sys.path.insert(0, str(Path(__file__).resolve().parent))
 import baselines  # noqa: E402
@@ -43,13 +44,73 @@
     print(zeile, flush=True)
 
 
-def faltenzuteilung(p, falten):
+def faltenzuteilung(p, falten, saat=1234):
+    """P4 (Prereg §1): Falten-Saat als Parameter; v1 = 1234 (Discovery), Konfirmation = 200."""
     bs = np.array(sorted(p.loc[p["items"] >= 80, "b_code"].unique()))
-    rng = np.random.default_rng(1234)
+    rng = np.random.default_rng(saat)
     perm = rng.permutation(len(bs))
     return {int(b): int(i % falten) for b, i in zip(bs[perm], range(len(bs)))}
 
 
+AGG_JE_B = SCRATCH / "agg_je_b"
+
+
+def agg_benchmark(b, train_s=None):
+    """P4 (speicherschonend): Zeilen des Benchmarks b aus agg_je_b/b<code>.parquet (agg_split.py) in Dateireihenfolge —
+    identisch zu agg.iloc[i0:i1] nach stabiler Sortierung (Werte, Reihenfolge, dtypes); nur der Index ist ein anderer
+    (wird nirgends benutzt). train_s: optional Filter auf Subjekte (wie agg_tr in v1)."""
+    f = AGG_JE_B / f"b{int(b)}.parquet"
+    if not f.exists():
+        raise SystemExit(f"ABBRUCH: {f} fehlt (agg_split.py zuerst ausführen)")
+    df = pq.read_table(f).to_pandas(self_destruct=True)
+    if train_s is not None:
+        df = df[df.s_code.isin(train_s)]
+    return df
+
+
+class AggStreaming:
+    """P4: Platzhalter für agg_tr; trägt nur die Trainingssubjekte. training.trainiere ruft schaetze_tau_i2(agg, ...) auf,
+    das hier (Monkeypatch unten) benchmarkweise aus agg_je_b liest, statt die 25-M-Zeilen-Tabelle zu halten."""
+
+    def __init__(self, train_s):
+        self.train_s = set(int(x) for x in train_s)
+
+
+def schaetze_tau_i2_streaming(agg, b_codes, seed=0, max_s=20, max_i=600):
+    """Zeile für Zeile training.schaetze_tau_i2 (v1) nachgebildet; einziger Unterschied: g je Benchmark aus Datei statt aus
+    sub.groupby('b_code'). Gleiche Iterationsreihenfolge (aufsteigende b_code), gleiche rng-Zugriffe, gleiche Teilmengen."""
+    rng = np.random.default_rng(seed)
+    werte = []
+    for b in sorted(int(x) for x in np.unique(b_codes)):
+        g = agg_benchmark(b, agg.train_s)
+        if g.empty:
+            continue  # Benchmark ohne Zeilen erscheint in v1 nicht in sub.groupby
+        cnt = g.groupby("s_code").size()
+        subj = cnt[cnt >= 80].index.values
+        if len(subj) < 3:
+            continue
+        subj = rng.choice(subj, min(max_s, len(subj)), replace=False)
+        g = g[g.s_code.isin(subj)]
+        items = g.i_code.unique()
+        if len(items) > max_i:
+            g = g[g.i_code.isin(rng.choice(items, max_i, replace=False))]
+        t2 = training.rasch_eb(g)
+        if np.isfinite(t2):
+            werte.append(t2)
+    return float(np.median(werte)) if werte else 0.0, len(werte)
+
+
+def lade_p_cache():
+    """P4: Paartabelle p aus Pickle-Cache (exakter Roundtrip), sonst wie v1 über training.lade_paare() und Cache anlegen."""
+    cache = SCRATCH / "p_cache_v1.pkl"
+    if cache.exists():
+        return pd.read_pickle(cache)
+    p, agg = training.lade_paare()
+    del agg
+    p.to_pickle(cache)
+    return p
+
+
 def praediktoren(state, train):
     kap = training.kappe(train, seed=0)
     raten = [g.rate.tolist() for _, g in kap.groupby("b_code")]
@@ -90,7 +151,11 @@
     if a.design == "B":
         train = train[~((train.name != "") & (train.name.map(namensfalte) == f % 5))]
     if a.phase == 1:
-        agg_tr = agg[agg.b_code.isin(train.b_code.unique()) & agg.s_code.isin(train.s_code.unique())]
+        if a.agg_sparsam:
+            training.schaetze_tau_i2 = schaetze_tau_i2_streaming  # Monkeypatch (training.py bleibt byteidentisch)
+            agg_tr = AggStreaming(train.s_code.unique())
+        else:
+            agg_tr = agg[agg.b_code.isin(train.b_code.unique()) & agg.s_code.isin(train.s_code.unique())]
         state = training.trainiere(train, seed=f, protokoll=lambda s: None, agg=agg_tr)
         del agg_tr
         pr, base = praediktoren(state, train)
@@ -102,6 +167,8 @@
         state = json.loads((von / f"state_f{f}.json").read_text())
         ausw = json.loads((von / "auswertung.json").read_text())
         stufen = set(ausw["platt_paket"].keys())
+        if a.platt_stufen:  # P4: Stufenmenge des eingereichten Pakets erzwingen (v1: {0,1,3,7}); Pipeline-Wahl = Sensitivität
+            stufen = set(x.strip() for x in a.platt_stufen.split(","))
         state["platt"] = {k: v for k, v in ausw["platt_je_falte"][str(f)].items() if k in stufen}
         pr = praediktoren_p2(state)
         regime = [(r, -int(r[7:]) if r.startswith("kompakt") else int(r[1:])) for r in a.regime.split(",")]
@@ -109,8 +176,11 @@
     zeilen = []
     for seed in [int(x) for x in a.saaten.split(",")]:
         for b, tp in testpaare.groupby("b_code"):
-            i0, i1 = starts[b]
-            agg_b = agg.iloc[i0:i1]
+            if a.agg_sparsam:
+                agg_b = agg_benchmark(b)
+            else:
+                i0, i1 = starts[b]
+                agg_b = agg.iloc[i0:i1]
             paare = simulator.baue_paare(agg_b, tp, subj, seed)
             for rname, S in regime:
                 laeufe = (simulator.kompakte_laeufe(agg_b, tp, subj, seed, S=-S) if S < 0
@@ -142,23 +212,42 @@
     ap.add_argument("--phase", type=int, default=1, choices=[1, 2])
     ap.add_argument("--von", default="", help="Phase 2: Ordner der Phase 1 (unter SCRATCH)")
     ap.add_argument("--regime", default="S3,S30,kompakt10", help="Phase 2: Regime, z. B. S1,S2,S3,S30,kompakt10")
+    ap.add_argument("--falten-saat", type=int, default=1234, help="P4: Saat der Faltenzuteilung (v1: 1234)")
+    ap.add_argument("--platt-stufen", default="", help="P4 Phase 2: Platt-Stufenmenge erzwingen, z. B. 0,1,3,7 (leer = Wahl der Phase-1-Auswertung)")
+    ap.add_argument("--agg-sparsam", type=int, default=1, help="P4: 1 = agg nicht im Speicher halten, je Benchmark aus Parquet lesen (OOM-Schutz; bitgleich belegt)")
     a = ap.parse_args()
     a.aus = a.aus or str(SCRATCH / (f"cv_{a.design}" if a.phase == 1 else f"{a.von}_p2"))
     aus = Path(a.aus)
     aus.mkdir(parents=True, exist_ok=True)
-    log(aus, f"Start Phase {a.phase} Design {a.design}, Falten {a.falten}, Saaten {a.saaten}, S {a.S}, regime {a.regime}, von {a.von}")
-    p, agg = training.lade_paare()
-    agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
-    bc = agg.b_code.values
-    starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right")))
-              for b in np.unique(bc)}
+    log(aus, f"Start Phase {a.phase} Design {a.design}, Falten {a.falten}, Saaten {a.saaten}, S {a.S}, regime {a.regime}, von {a.von}, falten_saat {a.falten_saat}, platt_stufen '{a.platt_stufen}'")
+    if a.agg_sparsam:
+        p = lade_p_cache()  # P4: 31 M agg-Zeilen nicht halten; Benchmark-Zeilen werden je Bedarf gelesen
+        agg, starts = None, None
+    else:
+        p, agg = training.lade_paare()
+        agg = agg.sort_values("b_code", kind="stable").reset_index(drop=True)
+        bc = agg.b_code.values
+        starts = {int(b): (int(np.searchsorted(bc, b, "left")), int(np.searchsorted(bc, b, "right")))
+                  for b in np.unique(bc)}
     sub = pd.read_parquet(SCRATCH / "subjekte.parquet")
     subj = {int(r["s_code"]): {f: r[f] for f in ("normalized_name", "provider", "release_date", "access_date",
                                                    "harness", "harness_version", "reasoning_effort",
                                                    "subject_features_extra")}
             for r in sub.to_dict("records")}
-    f_je_b = faltenzuteilung(p, a.falten)
+    f_je_b = faltenzuteilung(p, a.falten, a.falten_saat)
     (aus / "falten.json").write_text(json.dumps({str(k): v for k, v in f_je_b.items()}))
+    # P4 mechanische Prüfung (Prereg §1): bei neuer Falten-Saat MUSS die Zuteilung von cv_A/falten.json abweichen (fail-closed)
+    ref = SCRATCH / "cv_A" / "falten.json"
+    if ref.exists():
+        alt = {int(k): v for k, v in json.loads(ref.read_text()).items()}
+        n_diff = sum(1 for k, v in f_je_b.items() if alt.get(k) != v)
+        log(aus, f"Faltenzuteilung: {n_diff}/{len(f_je_b)} Benchmarks in anderer Falte als cv_A (Saat 1234)")
+        if a.falten_saat != 1234 and n_diff == 0:
+            log(aus, "ABBRUCH: neue Falten-Saat, aber Zuteilung identisch mit cv_A (fail-closed)")
+            raise SystemExit(3)
+        if a.falten_saat == 1234 and n_diff != 0:
+            log(aus, "ABBRUCH: Saat 1234, aber Zuteilung weicht von cv_A ab (Reproduzierbarkeit verletzt, fail-closed)")
+            raise SystemExit(3)
     G.update({"args": a, "p": p, "agg": agg, "starts": starts, "subj": subj, "f_je_b": f_je_b})
     liste = [int(x) for x in a.nur.split(",")] if a.nur else list(range(a.falten))
     fertig = []
@@ -173,7 +262,8 @@
             log(aus, f"Falte {f}: {txt}")
             fertig.append(f)
     n_da = sum(1 for k in range(a.falten) if (aus / f"saetze_f{k}.parquet").exists())
-    (aus / "status.json").write_text(json.dumps({"falten": a.falten, "fertig": n_da,
+    (aus / "status.json").write_text(json.dumps({"falten": a.falten, "fertig": n_da, "saaten": a.saaten,
+                                                 "falten_saat": a.falten_saat, "phase": a.phase, "design": a.design, "platt_stufen": a.platt_stufen,
                                                  "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
     log(aus, f"Ende: {n_da}/{a.falten} Falten vorhanden")
 
```
## auswertung.py
```diff
--- ./modell/auswertung.py	2026-10-20 17:22:04.203481887 +0000
+++ auswertung.py	2026-10-20 20:58:29.580109638 +0000
@@ -145,7 +145,10 @@
     ap.add_argument("--design", default="A")
     ap.add_argument("--primaer-S", default="S3")
     ap.add_argument("--phase", type=int, default=1)
+    ap.add_argument("--design-logik", default="", choices=["", "A", "B"],
+                    help="P4: --design ist nur der Ordnersuffix (cv_<design>); Design-B-Logik (kalt) hier wählen")
     a = ap.parse_args()
+    a.design_logik = a.design_logik or (a.design if a.design in ("A", "B") else "A")
     d, df, n_f = lade(a.design)
     S0 = a.primaer_S
     if a.phase == 1:
@@ -185,7 +188,7 @@
            "tabelle_unbekannt": tabelle(pa, ~pa.bekannt), "vergleiche": vgl,
            "kalibrierung_stufen": stufen_gewinn, "platt_paket": platt_fuer_paket, "platt_alle_stufen": platt_paket,
            "platt_je_falte": {str(f): {str(k): v for k, v in pl.items()} for f, pl in platt_falten.items()}}
-    if a.design == "B":
+    if a.design_logik == "B":
         erg["tabelle_kalt"] = tabelle(pa, pa.kalt)
         erg["vergleiche_kalt"] = [vergleich(pa, S0, "hier", r, maske=pa.kalt) for r in
                                   ("beta_binomial", "empirischer_mittelwert", "hier_ohne_subjekt")]
```
## agg_split.py (neu)
```python
"""agg_split.py (P4) — teilt PAIEC_WORK/modell/agg.parquet streaming in je-Benchmark-Dateien agg_je_b/b<code>.parquet.
agg.parquet ist nach b_code monoton (geprüft) -> Zeilen eines Benchmarks sind zusammenhängend; Reihenfolge und dtypes
bleiben erhalten. Prüft am Ende: Summe der Zeilen = Zeilen der Quelle (fail-closed, rc 3)."""
import os, sys
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

W = Path(os.environ["PAIEC_WORK"]) / "modell"
ziel = W / "agg_je_b"
ziel.mkdir(exist_ok=True)
pf = pq.ParquetFile(W / "agg.parquet")
n_quelle = pf.metadata.num_rows
puffer, aktuell, n_out, dateien = [], None, 0, 0


def schreibe():
    global puffer, n_out, dateien
    if not puffer:
        return
    t = pa.concat_tables(puffer)
    pq.write_table(t, ziel / f"b{aktuell}.parquet")
    n_out += t.num_rows
    dateien += 1
    puffer = []


for batch in pf.iter_batches(batch_size=1_000_000):
    t = pa.Table.from_batches([batch])
    b = t["b_code"].to_numpy()
    start = 0
    for i in range(1, len(b) + 1):
        if i == len(b) or b[i] != b[start]:
            code = int(b[start])
            if aktuell is not None and code != aktuell:
                schreibe()
            aktuell = code
            puffer.append(t.slice(start, i - start))
            start = i
schreibe()
print(f"Quelle {n_quelle} Zeilen, geschrieben {n_out} Zeilen in {dateien} Dateien")
sys.exit(0 if n_out == n_quelle else 3)
```

## Byteidentisch zu modell/
- baselines.py sha256 11b588b73c028e47
- baue_final.py sha256 d04f44c4574b8110
- daten.py sha256 131a470576ca712e
- inferenz.py sha256 54967c9666d8b5f4
- merkmale.py sha256 b409255fde66a886
- metrik.py sha256 fc61716aa318148d
- plots.py sha256 cb321aafad9d0b77
- simulator.py sha256 84e564bcee1b9b8a
- training.py sha256 643c8ddf172a09a5

## Nachtrag 2026-10-21 (Paketwechsel v1 → v2.0-core, Regel R1) — Phase-2-Logik des kern übernommen
Grund: P1 FERTIG 06:41Z ⇒ Paket = v2.0-core; dessen einzige Zahlenabweichung zu v1 ist die **verschachtelte Platt-Stufenwahl je Falte**
(kern K4f). `kern/kreuzvalidierung.py` kennt keine Falten-Saat (Falten würden mit Saat 1234 gebildet) und hält `agg` im Speicher
(OOM-Risiko) — darum werden die drei kern-Zeilen in `code_v1/kreuzvalidierung.py` übernommen statt umgekehrt.
1. `code_v1/kreuzvalidierung.py`, Phase 2: wenn `--platt-stufen` leer ist und `auswertung.json` des `--von`-Ordners
   `platt_stufenwahl_verschachtelt.verschachtelt_je_falte` enthält, wird je Falte diese Stufenmenge genommen (wörtlich kern Z. 105–108);
   sonst wie bisher `platt_paket` (v1-Gesamtwahl). Zusätzlich schreibt die Falten-Logzeile die benutzte Stufenmenge („Platt-Stufen 0,1,3").
2. `code_v1/auswertung_v2.py` = Kopie von `kern/auswertung.py` (liefert `platt_stufenwahl_verschachtelt`), einzige Änderung derselbe
   `--design-logik`-Patch wie bei `auswertung.py` (Ordnersuffix ≠ Design). Läuft nur auf den Spiegelordnern `cv_K_Av`/`cv_K_Bv`
   (Symlinks auf die Phase-1-Sätze/Zustände von `cv_K_A`/`cv_K_B`), damit die v1-Auswertung der Originalordner unberührt bleibt.
   Mechanische Prüfung (06:49Z): `platt_je_falte`, `tabelle_alle`, `vergleiche` in `cv_K_Av` (kern) und `cv_K_A` (v1) identisch — ebenso B.
   Stufenwahl je Falte: A {0,1,3,7} in F0–F2,F4,F7, +15 in F5,F6,F8, +15,31 in F3,F9 (Schnitt {0,1,3,7} = v1-Paket); B {0,1,3} in F0–F2,F8,F9,
   {0,1,3,7} in F4,F5,F7, +15 in F3,F6 (Schnitt {0,1,3}).
3. Neue Läufer/Skripte: `lauf_P4v.sh` (B2v → A2v, 1 Prozess), `auswerte_alles_v2.sh` (Primär = *2v; frühere Primärergebnisse gegen *2p
   nach `ergebnisse/sensitivitaet_stufen_0137/`), `pruefe_fertig.py` K2/K7 auf *2v umgestellt, `tafel.py` Paketmodell-Text.
Prüfsummen (sha256, erste 16): siehe `ergebnisse/code_v1_sha256.txt` (wird am Ende geschrieben).

### Nachtrag S1 (2026-10-21T08:56:31Z): Auswertung nach Abschluss von cv_K_A2v
4. `tafel.py` erweitert, nur Darstellung (Urteilslogik und Regeln unverändert, Prereg §2/§4/§7): Spalte „Hinweis / Grund" (Teil-Urteile aus den Skripten,
   bei not_evaluated der Eingabefehler), H2a-Hinweis wenn die vorab erwartete ≤ 3 %-Marke verfehlt ist (Regel ±10 % bleibt), H4-Grund im Scheiterfall
   (|d|+2SE je Regime, Anteil am H1-Gewinn), Abschnitt „Sensitivität der Phase-2-Platt-Stufenwahl" (primär vs. *2p vs. *2, Stufen je Falte aus
   pruefe_stufen_*2v.json), Markdown-Pipes entschärft. Fehlerfall erneut ausgelöst: leerer Ordner → rc 1, 10× not_evaluated (validierung/leer/, logs/tafel_leer_S1.log).
   Erster Versuch hatte einen SyntaxError (ASCII-Anführungszeichen); der war im STATUS zunächst fälschlich als ausgelöster Fehlerfall verbucht und ist dort korrigiert.
5. `bericht-v2/ZAHLEN-QUELLEN-v2.md`: P4-Abschnitt (07:02:40Z, fail-closed-Zwischenstand) durch den vollständigen ersetzt statt angehängt (Sicherung *.vor-S1.bak).
Prüfsummen: `ergebnisse/code_v1_sha256.txt` (code_v1/*.py + tafel.py, pruefe_fertig.py, auswerte_alles_v2.sh).
