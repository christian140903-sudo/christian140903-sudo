"""Eigene Paketprüfung (ersetzt NICHT check_submission_zip.py der Veranstalter; deren Code wird hier nicht ausgeführt).

Prüft in einem frischen Prozess (python3 -I, leeres Arbeitsverzeichnis, nur das entpackte ZIP auf sys.path):
  1 Struktur: model.py an der Wurzel, kein verschachteltes ZIP, keine subjects.txt, keine Dateizugriffe im Code
  2 Import nur Standardbibliothek (sys.modules nach dem Import gegen sys.stdlib_module_names)
  3 Smoke-Eingabe der Veranstalter (ohne benchmark_id) -> float in [0,1]
  4 Robustheit: leere Strings, fehlende Schlüssel, None, Labels als bool/str/float, riesige Texte
  5 Determinismus und Unabhängigkeit von der Aufrufreihenfolge
  6 Gleichheit mit dem Projektcode (inferenz.Modell) je Item auf einem simulierten Lauf
  7 Laufzeit je Aufruf (Median, p99) bei |labeled| = 0, 93, 930, 100 000 (gleiches Objekt und frische Kopie je Aufruf);
    Kriterium (REVIEW M3): frische Kopie bei 100 000 Labels Median < 2 ms und erster Aufruf < 5 s
  8 großer Lauf (> Modell.VOLL_BIS Labels): Stichproben-Schlüssel gleich dem exakten Pfad des Projektcodes
  9 v2.0-core: Fallback-Zähler nach 1–8 = 0 (kein stilles Durchfallen), Labels true/yes/1.0/None bitgleich zu bool,
    ein absichtlich kaputter labeled-Eintrag -> genau ein Beta-Binomial-Fallback, predict wirft nie
Aufruf: python3 -I paket/pruefe_paket.py <zip> --state <state.json>
"""
import argparse
import ast
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

KIND = r'''
import json, sys, time, random, statistics
sys.path.insert(0, sys.argv[1])
vorher = set(sys.modules)
import model
neu = sorted(m.split(".")[0] for m in set(sys.modules) - vorher)
fremd = sorted(set(m for m in neu if m not in sys.stdlib_module_names and m != "model"))
out = {"fremde_module": fremd}
S = {"normalized_name": "sample-model", "provider": "sample-org", "release_date": "2026-01-01",
     "access_date": "2026-02-01", "harness": "sample-harness", "reasoning_effort": "medium",
     "harness_version": "1.0", "subject_features_extra": ""}
I = {"item_content": "A sample yes/no evaluation item.", "item_features": "tier=near-term", "interactors": ""}
p = model.predict([dict(S), dict(I)], [])
out["smoke"] = p
def ok(v):
    return isinstance(v, float) and v == v and 0.0 <= v <= 1.0
faelle = []
E = {k: "" for k in S}
faelle.append(model.predict([E, {"item_content": "", "item_features": "", "interactors": "", "benchmark_id": ""}], []))
faelle.append(model.predict([{}, {}], None))
faelle.append(model.predict([dict(S), dict(I, benchmark_id="b1")], [[[dict(S), dict(I, benchmark_id="b1")], True]]))
faelle.append(model.predict([dict(S), dict(I, benchmark_id="b1")], [[[dict(S), dict(I, benchmark_id="b1")], "1"]]))
faelle.append(model.predict([dict(S), dict(I, benchmark_id="b1")], [[[dict(S), dict(I, benchmark_id="b1")], 0.0]]))
faelle.append(model.predict([dict(S, normalized_name="OpenAI GPT-4o"), dict(I, item_content="x" * 200000,
                             benchmark_id="b2")], [[[dict(S), dict(I, benchmark_id="b2")], 1]] * 31))
faelle.append(model.predict([dict(S, release_date="unknown"), dict(I, benchmark_id="b3")], []))
out["robust_alle_ok"] = all(ok(v) for v in faelle)
out["robust_werte"] = faelle
# Lauf aus Datei: je Item gleiche Vorhersage wie Projektcode
lauf = json.load(open(sys.argv[2]))
erg = []
for B, labeled, ziele in lauf:
    for inp in ziele:
        erg.append(model.predict(inp, labeled))
out["lauf"] = erg
# Reihenfolge: rückwärts erneut
erg2 = []
for B, labeled, ziele in reversed(lauf):
    for inp in reversed(ziele):
        erg2.append(model.predict(inp, labeled))
out["lauf_rueckwaerts"] = list(reversed(erg2))
# Laufzeit
zeiten = {}
rnd = random.Random(0)
for L in (0, 93, 930, 100000):
    lab = [[[dict(S, normalized_name="m%d" % (j % 30)), dict(I, item_content="a%d" % j, benchmark_id="bz")],
            rnd.randint(0, 1)] for j in range(L)]
    t0 = time.perf_counter()
    model.predict([dict(S), dict(I, benchmark_id="bz")], lab)
    erst = time.perf_counter() - t0
    t = []
    for j in range(300 if L < 10 ** 5 else 100):
        inp = [dict(S, normalized_name="m%d" % (j % 30)), dict(I, item_content="q%d" % j, benchmark_id="bz")]
        t0 = time.perf_counter()
        model.predict(inp, lab)
        t.append(time.perf_counter() - t0)
    t.sort()
    zeiten[str(L)] = {"median_ms": 1000 * statistics.median(t), "p99_ms": 1000 * t[int(0.99 * len(t)) - 1],
                      "erster_aufruf_ms": 1000 * erst}
    if L:
        t = []
        for j in range(100 if L < 10 ** 5 else 15):
            inp = [dict(S, normalized_name="m%d" % (j % 30)), dict(I, item_content="q%d" % j, benchmark_id="bz")]
            kopie = json.loads(json.dumps(lab))
            t0 = time.perf_counter()
            model.predict(inp, kopie)
            t.append(time.perf_counter() - t0)
        t.sort()
        zeiten[str(L) + "_frische_kopie_je_aufruf"] = {"median_ms": 1000 * statistics.median(t),
                                                       "p99_ms": 1000 * t[int(0.99 * len(t)) - 1]}
out["laufzeit"] = zeiten
# 9 v2.0-core: Zähler und Robustheit der Rückfallkette
z0 = model.diagnose()
out["zaehler_nach_normalbetrieb"] = z0
s2, t2 = dict(S, normalized_name="alpha"), dict(S, normalized_name="beta")
basis = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
def lab_mit(labels):
    return [[[s2 if j % 2 else t2, dict(I, item_content="i%d" % j, benchmark_id="b9")], l] for j, l in enumerate(labels)]
ref = [model.predict([s2, dict(I, benchmark_id="b9")], lab_mit(basis)), model.predict([t2, dict(I, item_content="i2", benchmark_id="b9")], lab_mit(basis))]
formen = {"bool": [bool(x) for x in basis], "str": ["1" if x else "0" for x in basis], "float_str": ["1.0" if x else "0.0" for x in basis],
          "true_false": ["true" if x else "false" for x in basis], "yes_no": ["YES" if x else "no" for x in basis]}
out["labelformen_bitgleich"] = all([model.predict([s2, dict(I, benchmark_id="b9")], lab_mit(v)),
                                    model.predict([t2, dict(I, item_content="i2", benchmark_id="b9")], lab_mit(v))] == ref for v in formen.values())
mit_none = lab_mit(basis) + [[[s2, dict(I, item_content="x", benchmark_id="b9")], None]]
out["none_uebersprungen"] = [model.predict([s2, dict(I, benchmark_id="b9")], mit_none), model.predict([t2, dict(I, item_content="i2", benchmark_id="b9")], mit_none)] == ref
z1 = model.diagnose()
out["zaehler_nach_labelformen"] = z1
kaputt = lab_mit(basis) + [None]  # ein kaputter Eintrag -> Kernpfad wirft -> Beta-Binomial
pk = model.predict([s2, dict(I, benchmark_id="b9")], kaputt)
z2 = model.diagnose()
out["kaputter_eintrag"] = {"p": pk, "ok_float": isinstance(pk, float) and 0.0 <= pk <= 1.0,
                           "bb_fallbacks_plus": z2["beta_binomial"] - z1["beta_binomial"], "konstant_plus": z2["konstant"] - z1["konstant"]}
print(json.dumps(out))
'''


def statisch(zp):
    befunde = []
    with zipfile.ZipFile(zp) as z:
        namen = [n for n in z.namelist() if not n.endswith("/")]
        if "model.py" not in namen:
            befunde.append("model.py fehlt an der Wurzel")
        if any(n.lower().endswith(".zip") for n in namen) or any(Path(n).name == "subjects.txt" for n in namen):
            befunde.append("verbotene Datei")
        code = z.read("model.py").decode("utf-8")
    baum = ast.parse(code)
    for node in ast.walk(baum):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name in ("open", "read_text", "read_bytes", "load", "read_csv", "read_parquet", "urlopen"):
                if not (name == "load" and isinstance(f, ast.Attribute) and getattr(f.value, "id", "") == "json"):
                    befunde.append(f"Dateizugriff/Netz im Code: {name} Z. {node.lineno}")
    return namen, befunde


def baue_lauf(state_pfad, pfad):
    """Kleiner synthetischer Lauf in der Wettbewerbsform (KEINE Messung, nur Gleichheitsprüfung)."""
    import random
    rnd = random.Random(1)
    th = json.loads(Path(state_pfad).read_text())["theta"]
    namen = sorted(th)[:2] + ["unbekanntes-modell-xyz", ""]
    subj = [{"normalized_name": n, "provider": "p%d" % i, "release_date": "2025-0%d-01" % (i + 1),
             "access_date": "2025-09-01", "harness": "", "harness_version": "", "reasoning_effort": "",
             "subject_features_extra": ""} for i, n in enumerate(namen)]
    lauf = []
    for B in (0, 1, 3, 7, 15, 31):
        labeled = []
        for bid in ("bA", "bB"):
            for s in subj:
                for j in range(B):
                    labeled.append([[s, {"item_content": "acq %s %d" % (bid, j), "item_features": "",
                                         "interactors": "", "benchmark_id": bid}], rnd.randint(0, 1)])
        ziele = [[s, {"item_content": "eval %s %d" % (bid, j), "item_features": "", "interactors": "",
                      "benchmark_id": bid}] for bid in ("bA", "bB", "") for s in subj for j in range(3)]
        lauf.append([B, labeled, ziele])
    # großer Lauf: 2 Benchmarks x 34 Subjekte x 31 Labels = 2 108 > Modell.VOLL_BIS (Stichproben-Schlüssel)
    gross = [dict(subj[i % len(subj)], normalized_name=(namen[i % 2] if i < 2 else "g%d" % i)) for i in range(34)]
    labeled = [[[s, {"item_content": "acq %s %d" % (bid, j % 40), "item_features": "", "interactors": "",
                     "benchmark_id": bid}], rnd.randint(0, 1)] for bid in ("bA", "bB") for s in gross for j in range(31)]
    ziele = [[s, {"item_content": "acq %s %d" % (bid, j), "item_features": "", "interactors": "", "benchmark_id": bid}]
             for bid in ("bA", "bB") for s in gross[:5] for j in range(36, 44)]
    lauf.append([31, labeled, ziele])
    Path(pfad).write_text(json.dumps(lauf))
    return lauf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--state", required=True)
    a = ap.parse_args()
    namen, befunde = statisch(a.zip)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from inferenz import Modell
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with zipfile.ZipFile(a.zip) as z:
            z.extractall(td / "sub")
        lauf = baue_lauf(a.state, td / "lauf.json")
        (td / "kind.py").write_text(KIND)
        r = subprocess.run([sys.executable, "-I", str(td / "kind.py"), str(td / "sub"), str(td / "lauf.json")],
                           cwd=td, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print(json.dumps({"urteil": "FEHLER", "stderr": r.stderr[-2000:]}))
            return 1
        out = json.loads(r.stdout)
    ref = Modell(json.loads(Path(a.state).read_text()))
    soll = [ref.wahrscheinlichkeit(inp, labeled) for B, labeled, ziele in lauf for inp in ziele]
    max_abw = max(abs(x - y) for x, y in zip(soll, out["lauf"]))
    max_abw_r = max(abs(x - y) for x, y in zip(out["lauf"], out["lauf_rueckwaerts"]))
    exakt = Modell(json.loads(Path(a.state).read_text()))
    exakt.VOLL_BIS = 10 ** 9  # exakter Vollscan als Referenz für den Stichprobenpfad
    soll_e = [exakt.wahrscheinlichkeit(inp, labeled) for B, labeled, ziele in lauf for inp in ziele]
    max_abw_e = max(abs(x - y) for x, y in zip(soll_e, out["lauf"]))
    gross = max(len(labeled) for _, labeled, _ in lauf)
    lz = out["laufzeit"]
    lz_ok = lz["100000_frische_kopie_je_aufruf"]["median_ms"] < 2.0 and lz["100000"]["erster_aufruf_ms"] < 5000
    z0, z1, ke = out["zaehler_nach_normalbetrieb"], out["zaehler_nach_labelformen"], out["kaputter_eintrag"]
    haertung_ok = (z0["beta_binomial"] == 0 and z0["konstant"] == 0 and z0["hier"] == z0["aufrufe"] > 0
                   and z1["beta_binomial"] == 0 and z1["konstant"] == 0 and out["labelformen_bitgleich"]
                   and out["none_uebersprungen"] and ke["ok_float"] and ke["bb_fallbacks_plus"] == 1 and ke["konstant_plus"] == 0)
    urteil = ("ok" if not befunde and not out["fremde_module"] and out["robust_alle_ok"]
              and 0 <= out["smoke"] <= 1 and max_abw < 1e-12 and max_abw_r < 1e-12 and max_abw_e < 1e-12
              and gross > Modell.VOLL_BIS and lz_ok and haertung_ok else "FEHLER")
    bericht = {"urteil": urteil, "dateien": namen, "statische_befunde": befunde,
               "fremde_module": out["fremde_module"], "smoke": out["smoke"], "robust_alle_ok": out["robust_alle_ok"],
               "max_abweichung_zu_projektcode": max_abw, "max_abweichung_reihenfolge": max_abw_r,
               "max_abweichung_zu_exaktpfad": max_abw_e, "groesster_lauf_labels": gross, "voll_bis": Modell.VOLL_BIS,
               "n_vergleiche": len(soll), "laufzeit_kriterium_ok": lz_ok, "haertung_ok": haertung_ok,
               "zaehler_nach_normalbetrieb": z0, "labelformen_bitgleich": out["labelformen_bitgleich"],
               "none_uebersprungen": out["none_uebersprungen"], "kaputter_eintrag": ke,
               "hochrechnung_150000_aufrufe_100000_labels_kopie_s":
                   150000 * lz["100000_frische_kopie_je_aufruf"]["median_ms"] / 1000, "laufzeit": out["laufzeit"]}
    print(json.dumps(bericht, indent=1))
    return 0 if urteil == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
