"""F6 — Speicher des Paketmodells bei |labeled| = 300 000 (Standard): tracemalloc-Spitze der Modellallokationen
(Import + erster predict + 50 weitere Aufrufe) und RSS-Spitze des Prozesses (resource.ru_maxrss).

Aufruf: python3 -I messungen/speicher.py --model-dir <dir mit model.py> [--labels 300000] [--limit-mb 500]
        [--aus messungen/speicher.json]
Kriterium: tracemalloc-Spitze (Modell) < --limit-mb UND RSS-Zuwachs durch das Modell < --limit-mb, sonst rc 1
(fail-closed; mit --limit-mb 1 wird der Fehlerfall ausgelöst).
"""
import argparse
import importlib.util
import json
import resource
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frischer_prozess import baue_labels  # noqa: E402


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--labels", type=int, default=300000)
    ap.add_argument("--limit-mb", type=float, default=500.0)
    ap.add_argument("--aus", default=str(Path(__file__).resolve().parent / "speicher.json"))
    a = ap.parse_args()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        pfad = Path(td) / "labels.json"
        n = baue_labels(a.labels, pfad)
        labeled = json.loads(pfad.read_text())
    rss_vor = rss_mb()
    tracemalloc.start()
    t0 = time.perf_counter()
    spec = importlib.util.spec_from_file_location("paiec_model_mem", Path(a.model_dir) / "model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    t1 = time.perf_counter()
    nach_import = tracemalloc.get_traced_memory()
    S = labeled[0][0][0]
    I = dict(labeled[0][0][1], item_content="zielitem")
    p = mod.predict([S, I], labeled)
    t2 = time.perf_counter()
    for k in range(50):
        mod.predict([labeled[k * 97 % n][0][0], dict(I, item_content="ziel %d" % k)], labeled)
    t3 = time.perf_counter()
    aktuell, spitze = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_nach = rss_mb()
    erg = {"model_dir": str(Path(a.model_dir).resolve()), "n_labels": n, "limit_mb": a.limit_mb,
           "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "tracemalloc_mb": {"nach_import": nach_import[1] / 2 ** 20, "spitze_gesamt": spitze / 2 ** 20,
                              "aktuell_ende": aktuell / 2 ** 20},
           "rss_mb": {"vor_modell_mit_labels": rss_vor, "nach": rss_nach, "zuwachs": rss_nach - rss_vor},
           "zeiten_s": {"import": t1 - t0, "erster_predict": t2 - t1, "50_weitere_predict": t3 - t2},
           "p_erster": p, "zaehler": mod.diagnose() if hasattr(mod, "diagnose") else None}
    ok = erg["tracemalloc_mb"]["spitze_gesamt"] < a.limit_mb and erg["rss_mb"]["zuwachs"] < a.limit_mb
    erg["urteil"] = "ok" if ok else "FEHLER"
    erg["kehrseite"] = ("Falsch, wenn die Plattform labeled als etwas anderes als eine Liste von [[subject, item], label] "
                        "übergibt oder weit mehr als 3e5 Labels je Checkpoint anfallen (hier: 100 Paare x 31 je "
                        "Benchmark-Lauf wäre 3 100; 3e5 entspricht ~9 700 Paaren). Die RSS-Spitze enthält auch "
                        "Interpreter und Label-Liste; der Modellanteil ist die tracemalloc-Zahl.")
    Path(a.aus).write_text(json.dumps(erg, indent=1))
    print(json.dumps({k: erg[k] for k in ("n_labels", "tracemalloc_mb", "rss_mb", "zeiten_s", "urteil")}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
