"""Inferenz gegen numerische Referenz (scipy) und Schnittstellen-Eigenschaften. python3 -I -m unittest discover -s tests"""
import math
import random
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inferenz  # noqa: E402
import metrik  # noqa: E402


def _ziel(x, gruppen, mu_c, tc2, lam, tl2):
    c, a, v = x[0], x[1], x[2:]
    f = (c - mu_c) ** 2 / (2 * tc2) + (a - lam) ** 2 / (2 * tl2)
    for (m, s2, k, n), vg in zip(gruppen, v):
        e = c + a * m + vg
        f += n * np.logaddexp(0, e) - k * e + vg * vg / (2 * s2)
    return f


def _hesse(x, gruppen, mu_c, tc2, lam, tl2):
    G = len(gruppen)
    H = np.zeros((G + 2, G + 2))
    H[0, 0], H[1, 1] = 1 / tc2, 1 / tl2
    c, a, v = x[0], x[1], x[2:]
    for j, ((m, s2, k, n), vg) in enumerate(zip(gruppen, v)):
        p = 1 / (1 + math.exp(-(c + a * m + vg)))
        h = n * p * (1 - p)
        u = np.zeros(G + 2)
        u[0], u[1], u[2 + j] = 1, m, 1
        H += h * np.outer(u, u)
        H[2 + j, 2 + j] += 1 / s2
    return H


class TestPosterior(unittest.TestCase):
    def test_gegen_scipy(self):
        rnd = random.Random(7)
        for fall in range(25):
            G = rnd.randint(0, 6)
            gruppen = []
            for _ in range(G):
                n = rnd.choice([1, 3, 7, 15, 31, 62])
                gruppen.append((rnd.gauss(0, 1.2), rnd.uniform(0.2, 2.0), float(rnd.randint(0, n)), float(n)))
            hyp = (rnd.gauss(0.3, 0.5), rnd.uniform(0.5, 2.0), rnd.uniform(0.2, 1.0), rnd.uniform(0.05, 0.5))
            mu_c, tc2, lam, tl2 = hyp
            post = inferenz.posterior(gruppen, mu_c, tc2, lam, tl2)
            ref = minimize(_ziel, np.zeros(G + 2), args=(gruppen, mu_c, tc2, lam, tl2), method="BFGS",
                           options={"gtol": 1e-10})
            x = np.array([post["c"], post["a"]] + post["v"])
            self.assertLess(np.max(np.abs(x - ref.x)), 1e-4, f"Fall {fall}: Modus")
            Hinv = np.linalg.inv(_hesse(x, gruppen, mu_c, tc2, lam, tl2))
            for idx in [None] + list(range(G)):
                m_t = gruppen[idx][0] if idx is not None else 0.7
                s2_t = gruppen[idx][1] if idx is not None else 0.9
                mittel, var = inferenz.praediktiv(post, idx, m_t, s2_t)
                u = np.zeros(G + 2)
                u[0], u[1] = 1, m_t
                if idx is None:
                    var_ref = u @ Hinv @ u + s2_t
                    mittel_ref = x[0] + x[1] * m_t
                else:
                    u[2 + idx] = 1
                    var_ref = u @ Hinv @ u
                    mittel_ref = x[0] + x[1] * m_t + x[2 + idx]
                self.assertAlmostEqual(mittel, mittel_ref, places=6)
                self.assertAlmostEqual(var, var_ref, places=6, msg=f"Fall {fall}, idx {idx}: Varianz")

    def test_stufe(self):
        self.assertEqual([inferenz.stufe(n) for n in (0, 1, 2, 3, 6, 7, 14, 15, 30, 31, 62)],
                         [0, 1, 1, 3, 3, 7, 7, 15, 15, 31, 31])

    def test_alc_beispiel(self):
        self.assertAlmostEqual(metrik.alc([0.22, 0.18, 0.145, 0.12, 0.1, 0.09]), 0.140, places=3)
        self.assertAlmostEqual(metrik.alc([0.25] * 6), 0.25)

    def test_brier_paar(self):
        rng = np.random.default_rng(0)
        y = (rng.random(1000) < 0.3).astype(float)
        q = 0.42
        self.assertAlmostEqual(float(np.mean((q - y) ** 2)), metrik.brier_paar(q, y.mean()), places=12)


if __name__ == "__main__":
    unittest.main()


class TestKeinLeck(unittest.TestCase):
    """Fehlerfall vom 2026-10-20: Budget 0 nach einer Label-Menge durfte keine alten Gruppen sehen."""

    def _state(self):
        hyp = {"mu_c": 0.3, "lam": 0.4, "tau_c2": 1.4, "tau_l2": 0.16, "tau_v2": 0.3, "kappa": 3.0, "s2_unk": 0.8}
        return {"theta": {"model a": [1.0, 0.1]}, "meta": {"b0": 0.0, "w": {}}, "hyp": hyp, "hyp_null": hyp}

    def test_budget0_nach_labels(self):
        s = {"normalized_name": "Model A"}
        it = {"item_content": "x", "benchmark_id": "b1"}
        frisch = inferenz.Modell(self._state()).wahrscheinlichkeit([s, it], [])
        m = inferenz.Modell(self._state())
        mit = m.wahrscheinlichkeit([s, it], [[[s, it], 0]] * 20)
        self.assertNotAlmostEqual(mit, frisch, places=3)
        self.assertEqual(m.wahrscheinlichkeit([s, it], []), frisch)
        m.wahrscheinlichkeit([s, it], [[[s, it], 0]] * 20)
        m.leere_cache()
        self.assertEqual(m.wahrscheinlichkeit([s, it], []), frisch)
        m.wahrscheinlichkeit([s, it], [[[s, it], 0]] * 20)
        m._fp = None  # wie der alte Simulator
        self.assertEqual(m.wahrscheinlichkeit([s, it], []), frisch)

    def test_andere_labelmenge_gleicher_umfang(self):
        s, t = {"normalized_name": "Model A"}, {"normalized_name": "Model B"}
        it = {"item_content": "x", "benchmark_id": "b1"}
        m = inferenz.Modell(self._state())
        a = m.wahrscheinlichkeit([s, it], [[[s, it], 1]] * 5)
        b = m.wahrscheinlichkeit([s, it], [[[t, it], 1]] * 5)
        self.assertNotEqual(a, b)
        self.assertEqual(a, inferenz.Modell(self._state()).wahrscheinlichkeit([s, it], [[[s, it], 1]] * 5))


class TestItemStufe(unittest.TestCase):
    def _state(self, tau_i2):
        hyp = {"mu_c": 0.3, "lam": 0.4, "tau_c2": 1.4, "tau_l2": 0.16, "tau_v2": 0.3, "kappa": 3.0, "s2_unk": 0.8,
               "tau_i2": tau_i2}
        return {"theta": {"model a": [1.0, 0.1], "model b": [-0.5, 0.2]}, "meta": {"b0": 0.0, "w": {}},
                "hyp": hyp, "hyp_null": hyp, "platt": {"1": [1.1, -0.1]}}

    def test_ohne_itemlabels_identisch(self):
        s, t = {"normalized_name": "Model A"}, {"normalized_name": "Model B"}
        lab = [[[t, {"item_content": "q%d" % j, "benchmark_id": "b"}], j % 2] for j in range(7)]
        lab += [[[s, {"item_content": "r%d" % j, "benchmark_id": "b"}], 1] for j in range(3)]
        ziel = [s, {"item_content": "neu", "benchmark_id": "b"}]
        a = inferenz.Modell(self._state(2.6)).wahrscheinlichkeit(ziel, lab)
        b = inferenz.Modell(self._state(0.0)).wahrscheinlichkeit(ziel, lab)
        self.assertEqual(a, b)

    def test_fremdlabels_wirken(self):
        s, t = {"normalized_name": "Model A"}, {"normalized_name": "Model B"}
        it = {"item_content": "gemeinsam", "benchmark_id": "b"}
        lab0 = [[[t, {"item_content": "q%d" % j, "benchmark_id": "b"}], j % 2] for j in range(7)]
        m = inferenz.Modell(self._state(2.6))
        basis = m.wahrscheinlichkeit([s, {"item_content": "anders", "benchmark_id": "b"}], lab0 + [[[t, it], 1]])
        hoch = m.wahrscheinlichkeit([s, it], lab0 + [[[t, it], 1]])
        tief = inferenz.Modell(self._state(2.6)).wahrscheinlichkeit([s, it], lab0 + [[[t, it], 0]])
        self.assertGreater(hoch, basis)
        self.assertLess(tief, basis)

    def test_item_posterior_gegen_scipy(self):
        from scipy.optimize import minimize_scalar
        s, t = {"normalized_name": "Model A"}, {"normalized_name": "Model B"}
        it = {"item_content": "gemeinsam", "benchmark_id": "b"}
        lab = [[[t, {"item_content": "q%d" % j, "benchmark_id": "b"}], j % 2] for j in range(5)]
        lab += [[[t, it], 1], [[s, it], 0], [[t, it], 1]]
        m = inferenz.Modell(self._state(2.6))
        m.wahrscheinlichkeit([s, it], lab)
        d, v, c = m._ipost[("b", m.item_schluessel(it))]
        obs = [(inferenz.logit(m._p_gruppe("b", inferenz.konfig(x))) * c, y) for x, y in ((t, 1), (s, 0), (t, 1))]
        f = lambda z: sum(np.logaddexp(0, b + z) - y * (b + z) for b, y in obs) + z * z / (2 * 2.6)
        ref = minimize_scalar(f, bounds=(-10, 10), method="bounded", options={"xatol": 1e-10})
        self.assertAlmostEqual(d, ref.x, places=5)


class TestSchnellpfad(unittest.TestCase):
    def test_gleich_langsam(self):
        hyp = {"mu_c": 0.3, "lam": 0.4, "tau_c2": 1.4, "tau_l2": 0.16, "tau_v2": 0.3, "kappa": 3.0, "s2_unk": 0.8,
               "tau_i2": 2.6}
        st = {"theta": {"model a": [1.0, 0.1]}, "meta": {"b0": 0.0, "w": {}}, "hyp": hyp, "hyp_null": hyp}
        rnd = random.Random(3)
        subj = [{"normalized_name": n} for n in ("Model A", "x", "y")]
        lab = [[[rnd.choice(subj), {"item_content": "i%d" % rnd.randint(0, 20), "benchmark_id": "b"}],
                rnd.randint(0, 1)] for _ in range(40)]
        ziele = [[s, {"item_content": "i%d" % j, "benchmark_id": "b"}] for s in subj for j in range(25)]
        schnell = inferenz.Modell(st)
        a = [schnell.wahrscheinlichkeit(z, lab) for z in ziele]
        b = []
        for z in ziele:
            m = inferenz.Modell(st)
            b.append(m.wahrscheinlichkeit(z, json_kopie(lab)))
        self.assertEqual(a, b)
        # Liste in place verändert (gleiche Länge, Mitte geändert): Schnellpfad darf nicht greifen
        lab2 = lab
        alt = lab2[20][1]
        lab2[20][1] = 1 - alt
        neu = schnell.wahrscheinlichkeit(ziele[0], lab2)
        ref = inferenz.Modell(st).wahrscheinlichkeit(ziele[0], json_kopie(lab2))
        self.assertEqual(neu, ref)


def json_kopie(x):
    import json
    return json.loads(json.dumps(x))


class TestGrosseLabelmenge(unittest.TestCase):
    """REVIEW M3 (2026-10-20): über Modell.VOLL_BIS Labels Stichproben-Schlüssel statt Vollscan."""

    def _state(self):
        hyp = {"mu_c": 0.3, "lam": 0.4, "tau_c2": 1.4, "tau_l2": 0.16, "tau_v2": 0.3, "kappa": 3.0, "s2_unk": 0.8,
               "tau_i2": 2.6}
        return {"theta": {"m1": [1.0, 0.1], "m2": [-0.5, 0.2]}, "meta": {"b0": 0.0, "w": {}}, "hyp": hyp,
                "hyp_null": hyp, "platt": {"1": [1.1, -0.1], "31": [1.05, 0.02]}}

    def _lauf(self, n_subj=40, B=31, seed=5):
        rnd = random.Random(seed)
        subj = [{"normalized_name": "m%d" % i} for i in range(n_subj)]
        lab = [[[s, {"item_content": "i%d" % rnd.randint(0, 60), "benchmark_id": "b%d" % (k % 2)}],
                rnd.randint(0, 1)] for k, s in enumerate(subj) for _ in range(B)]
        ziele = [[s, {"item_content": "i%d" % j, "benchmark_id": "b%d" % (j % 2)}] for s in subj[:6] for j in range(20)]
        return lab, ziele

    def test_stichprobe_gleich_exakt(self):
        lab, ziele = self._lauf()
        self.assertGreater(len(lab), inferenz.Modell.VOLL_BIS)
        st = self._state()
        stich = inferenz.Modell(st)
        exakt = inferenz.Modell(st)
        exakt.VOLL_BIS = 10 ** 9
        a = [stich.wahrscheinlichkeit(z, json_kopie(lab)) for z in ziele]
        b = [exakt.wahrscheinlichkeit(z, lab) for z in ziele]
        c = [inferenz.Modell(st).wahrscheinlichkeit(z, json_kopie(lab)) for z in ziele]
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertTrue(stich._fp.startswith("s"))

    def test_laenge_und_stichprobenposition_erkannt(self):
        lab, ziele = self._lauf()
        st = self._state()
        m = inferenz.Modell(st)
        m.wahrscheinlichkeit(ziele[0], lab)
        kurz = lab[:-31]  # wie ein Checkpoint mit einem Paar weniger
        self.assertEqual(m.wahrscheinlichkeit(ziele[0], kurz), inferenz.Modell(st).wahrscheinlichkeit(ziele[0], kurz))
        m.wahrscheinlichkeit(ziele[0], lab)
        gedreht = json_kopie(lab)
        gedreht[0][1] = 1 - gedreht[0][1]  # Position 0 liegt immer in der Stichprobe
        self.assertEqual(m.wahrscheinlichkeit(ziele[0], gedreht),
                         inferenz.Modell(st).wahrscheinlichkeit(ziele[0], gedreht))

    def test_bekannte_grenze_ausgeloest(self):
        """Fehlerfall der Mechanik einmal auslösen: gleiche Länge, Änderung nur außerhalb der Stichprobe, dasselbe
        Modell ohne leere_cache() -> veraltete Gruppen. Auf der Plattform ausgeschlossen (|labeled| wächst je
        Checkpoint); leere_cache() behebt es."""
        lab, ziele = self._lauf()
        st = self._state()
        n = len(lab)
        k = inferenz.Modell.STICHPROBE
        pos = {(j * (n - 1)) // (k - 1) for j in range(k)}
        frei = [i for i in range(n) if i not in pos and lab[i][0][0]["normalized_name"] == "m0"]
        anders = json_kopie(lab)
        for i in frei:
            anders[i][1] = 1 - anders[i][1]
        ziel = [{"normalized_name": "m0"}, {"item_content": "neu", "benchmark_id": lab[frei[0]][0][1]["benchmark_id"]}]
        m = inferenz.Modell(st)
        alt = m.wahrscheinlichkeit(ziel, lab)
        richtig = inferenz.Modell(st).wahrscheinlichkeit(ziel, anders)
        self.assertNotAlmostEqual(alt, richtig, places=3)
        self.assertEqual(m.wahrscheinlichkeit(ziel, anders), alt)  # veraltet: die bekannte Grenze
        m.leere_cache()
        self.assertEqual(m.wahrscheinlichkeit(ziel, anders), richtig)
