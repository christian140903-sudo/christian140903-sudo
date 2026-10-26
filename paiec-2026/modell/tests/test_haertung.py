"""Härtungs-Fehlerfälle F1–F4 (D-ensemble §7.1) am GEBAUTEN Paket (model.py), nicht am Projektcode.

Aufruf (grün, v2.0-core):   PAIEC_MODEL_DIR=<dir mit model.py> python3 -I -m unittest tests.test_haertung -v
Aufruf (rot, v1-Paket):     PAIEC_MODEL_DIR=<entpacktes paiec_hier.zip> ...   -> F1–F3 müssen scheitern
Aufruf (rot, F4 ohne Sperre): PAIEC_OHNE_SPERRE=1 ... tests.test_haertung.TestF4Threads  -> muss scheitern
Jeder Test lädt model.py frisch (eigener Modulname), damit Zähler und absichtliche Brüche nicht wandern.
"""
import contextlib
import importlib.util
import os
import random
import sys
import threading
import time
import unittest
from pathlib import Path

MODEL_DIR = Path(os.environ.get("PAIEC_MODEL_DIR", str(Path(__file__).resolve().parents[1] / "dist")))
_N = [0]


def lade_model():
    _N[0] += 1
    name = "paiec_model_%d" % _N[0]
    spec = importlib.util.spec_from_file_location(name, MODEL_DIR / "model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def S(name="sample-model", **k):
    d = {"normalized_name": name, "provider": "sample-org", "release_date": "2026-01-01", "access_date": "2026-02-01",
         "harness": "h", "reasoning_effort": "", "harness_version": "1.0", "subject_features_extra": ""}
    d.update(k)
    return d


def I(bid="b1", text="item text", feat="tier=1"):
    return {"item_content": text, "item_features": feat, "interactors": "", "benchmark_id": bid}


def bb_wert(m, k, n):
    return (m._BB_ALPHA + k) / (m._BB_ALPHA + m._BB_BETA + n)


class TestF1Ausnahme(unittest.TestCase):
    """F1: Ausnahme im Kernpfad -> Beta-Binomial-Wert (nicht 0,5), Zähler beta_binomial + 1."""

    def test_injizierte_ausnahme(self):
        m = lade_model()

        def kaputt(*a, **k):
            raise RuntimeError("injiziert")
        m._MODELL.wahrscheinlichkeit = kaputt
        s, it = S(), I("b1")
        labeled = [[[s, I("b1", "a%d" % j)], y] for j, y in enumerate((1, 1, 0))]
        p = m.predict([s, it], labeled)
        self.assertIsInstance(p, float)
        self.assertNotEqual(p, 0.5)
        self.assertAlmostEqual(p, bb_wert(m, 2, 3), places=12)
        z = m.diagnose()
        self.assertEqual((z["aufrufe"], z["hier"], z["beta_binomial"], z["konstant"]), (1, 0, 1, 0))

    def test_kaputtes_item(self):
        m = lade_model()
        s = S()
        p = m.predict([s, "kein dict"], [[[s, I("b1")], 1]])  # item kein Dict -> Kernpfad wirft
        self.assertIsInstance(p, float)
        self.assertAlmostEqual(p, bb_wert(m, 0, 0), places=12)  # Prior-Mittel alpha/(alpha+beta), nicht 0,5
        self.assertNotEqual(p, 0.5)
        self.assertEqual(m.diagnose()["beta_binomial"], 1)

    def test_kette_bis_konstante(self):
        m = lade_model()
        m._MODELL.wahrscheinlichkeit = lambda *a, **k: 1 / 0
        m._BB_ALPHA = None  # Stufe 2 bricht ebenfalls
        p = m.predict([S(), I()], [])
        self.assertEqual(p, 0.5)
        self.assertEqual(m.diagnose()["konstant"], 1)


class TestF2Labelformen(unittest.TestCase):
    """F2: Labels als bool/int/float/"1"/"1.0"/"true"/"yes"/None -> gezählt bzw. übersprungen, bitgleich zu bool."""

    def _lauf(self, m, labels):
        s, t = S("alpha"), S("beta")
        labeled = []
        for j, lab in enumerate(labels):
            labeled.append([[s if j % 2 else t, I("b7", "i%d" % j)], lab])
        return [m.predict([s, I("b7", "ziel")], labeled), m.predict([t, I("b7", "i3")], labeled),
                m.predict([s, I("b7", "i2")], labeled)]

    def test_formen_bitgleich(self):
        m = lade_model()
        basis = [True, False, True, True, False, True, False, False, True, True, False, True]
        ref = self._lauf(m, basis)
        formen = {
            "int": [1 if b else 0 for b in basis],
            "float": [1.0 if b else 0.0 for b in basis],
            "str01": ["1" if b else "0" for b in basis],
            "str_float": ["1.0" if b else "0.0" for b in basis],
            "true_false": ["true" if b else "false" for b in basis],
            "yes_no": ["yes" if b else "no" for b in basis],
            "gemischt": ["True" if b else 0 for b in basis],
        }
        for name, labels in formen.items():
            self.assertEqual(self._lauf(m, labels), ref, name)
        self.assertEqual(m.diagnose()["beta_binomial"], 0)
        self.assertEqual(m.diagnose()["konstant"], 0)

    def test_none_wird_uebersprungen(self):
        m = lade_model()
        basis = [1, 0, 1, 1, 0, 1, 0, 0]
        ref = self._lauf(m, basis)
        mit_none = []
        for j, lab in enumerate(basis):
            mit_none.append(lab)
        # None-Einträge an zusätzlichen Positionen (gleiche Subjekte/Items wie ein weiteres Label) -> ignoriert
        s, t = S("alpha"), S("beta")
        labeled = [[[s if j % 2 else t, I("b7", "i%d" % j)], lab] for j, lab in enumerate(basis)]
        labeled += [[[s, I("b7", "x1")], None], [[t, I("b7", "x2")], "n/a"], [[s, I("b7", "x3")], float("nan")]]
        out = [m.predict([s, I("b7", "ziel")], labeled), m.predict([t, I("b7", "i3")], labeled),
               m.predict([s, I("b7", "i2")], labeled)]
        self.assertEqual(out, ref)
        self.assertEqual(m.diagnose()["beta_binomial"], 0)


def wettbewerbs_eingaben(m, n_ziel=10000, seed=0):
    """Wettbewerbsförmige Läufe: je Benchmark 3 Subjekte (bekannte Namen aus theta + unbekannte), Budgets 0..31,
    Items mit Text/Merkmalen, Labels int 0/1. Liefert genau n_ziel (input, labeled)-Paare."""
    rnd = random.Random(seed)
    namen = sorted(m._STATE["theta"])[:12] + ["unbekannt-%d" % j for j in range(6)] + [""]
    aufgaben = []
    b = 0
    while len(aufgaben) < n_ziel:
        bid = "bm_%08x" % rnd.getrandbits(32)
        subj = [S(rnd.choice(namen), provider="p%d" % rnd.randint(0, 5), release_date="202%d-0%d-01" %
                  (rnd.randint(3, 6), rnd.randint(1, 9))) for _ in range(3)]
        for B in (0, 1, 3, 7, 15, 31):
            labeled = [[[s, I(bid, "acq %d %d" % (k, j), "tier=%d" % (j % 3))], rnd.randint(0, 1)]
                       for k, s in enumerate(subj) for j in range(B)]
            for s in subj:
                for j in range(2):
                    aufgaben.append(([s, I(bid, "eval %d" % j, "tier=%d" % j)], labeled))
                    if len(aufgaben) >= n_ziel:
                        return aufgaben
        b += 1
    return aufgaben


class TestF3Fallbackkette(unittest.TestCase):
    """F3: 10^4 wettbewerbsförmige Eingaben -> 0 Fallbacks; gebrochener Zustand -> 10^4 Fallbacks."""

    def test_null_fallbacks(self):
        m = lade_model()
        aufgaben = wettbewerbs_eingaben(m)
        self.assertEqual(len(aufgaben), 10000)
        for inp, lab in aufgaben:
            p = m.predict(inp, lab)
            self.assertTrue(isinstance(p, float) and p == p and 1e-4 <= p <= 1 - 1e-4)
        z = m.diagnose()
        self.assertEqual((z["aufrufe"], z["hier"], z["beta_binomial"], z["konstant"]), (10000, 10000, 0, 0))

    def test_gebrochener_zustand_beta_binomial(self):
        m = lade_model()
        m._MODELL.tau_c2 = 0.0  # Division durch null im Laplace-Posterior
        aufgaben = wettbewerbs_eingaben(m)
        werte = [m.predict(inp, lab) for inp, lab in aufgaben]
        z = m.diagnose()
        self.assertEqual((z["hier"], z["beta_binomial"], z["konstant"]), (0, 10000, 0))
        self.assertTrue(all(isinstance(p, float) and 1e-4 <= p <= 1 - 1e-4 for p in werte))
        self.assertGreater(len(set(werte)), 10)  # echte Beta-Binomial-Werte, nicht eine Konstante

    def test_gebrochener_zustand_konstante(self):
        m = lade_model()
        m._MODELL.tau_c2 = 0.0
        m._BB_BETA = "kaputt"
        aufgaben = wettbewerbs_eingaben(m, n_ziel=1000)
        werte = [m.predict(inp, lab) for inp, lab in aufgaben]
        z = m.diagnose()
        self.assertEqual((z["hier"], z["beta_binomial"], z["konstant"]), (0, 0, 1000))
        self.assertEqual(set(werte), {0.5})


class TestF4Threads(unittest.TestCase):
    """F4: 8 Threads mit gemischten Label-Mengen -> Ausgaben identisch zur sequenziellen Referenz.
    PAIEC_OHNE_SPERRE=1 entfernt die Sperre und erzwingt Verschränkung in _bereite (roter Fall)."""

    def _aufgaben(self):
        rnd = random.Random(4)
        namen = ["m%d" % j for j in range(40)]
        mengen = []
        for bid, n_s, B in (("bA", 3, 7), ("bB", 10, 31), ("bC", 40, 31), ("bD", 2, 15)):  # 40x31 > VOLL_BIS
            subj = [S(n) for n in namen[:n_s]]
            mengen.append((subj, [[[s, I(bid, "acq %d" % j)], rnd.randint(0, 1)] for s in subj for j in range(B)], bid))
        aufgaben = []
        for k in range(1600):
            subj, lab, bid = mengen[k % 4]
            aufgaben.append(([rnd.choice(subj), I(bid, "acq %d" % rnd.randint(0, 40))], lab))
        return aufgaben

    def test_acht_threads(self):
        aufgaben = self._aufgaben()
        ref_mod = lade_model()
        ref = [ref_mod.predict(inp, lab) for inp, lab in aufgaben]
        m = lade_model()
        if os.environ.get("PAIEC_OHNE_SPERRE"):
            m._SPERRE = contextlib.nullcontext()
            orig = m.Modell._bereite

            def langsam(self, labeled):
                orig(self, labeled)
                time.sleep(0.0002)  # Verschränkung zwischen Gruppierung und Vorhersage erzwingen
            m.Modell._bereite = langsam
            sys.setswitchinterval(1e-5)
        out = [None] * len(aufgaben)
        fehler = []

        def arbeit(t):
            try:
                for k in range(t, len(aufgaben), 8):
                    inp, lab = aufgaben[k]
                    out[k] = m.predict(inp, lab)
            except Exception as e:  # pragma: no cover
                fehler.append(repr(e))
        threads = [threading.Thread(target=arbeit, args=(t,)) for t in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        sys.setswitchinterval(0.005)
        self.assertEqual(fehler, [])
        abw = sum(1 for a, b in zip(out, ref) if a != b)
        self.assertEqual(abw, 0, "%d von %d Ausgaben weichen von der sequenziellen Referenz ab" % (abw, len(ref)))


if __name__ == "__main__":
    unittest.main()
