"""Tests fuer alc_law.py. Aufruf: python3 -I test_alc_law.py  (Rueckgabecode 0 = alle gruen).

T1  Reproduktion der Discovery-Rechnung (v2-plan/d-wissenschaft/split.json, alc_terme.json) im Modus 'quadrat' auf 1e-6.
T2  Monte-Carlo-Pruefung der exakten Formel (Herleitung Anhang A §A.2) auf einer synthetischen Paar-Population mit
    Ziehen ohne Zuruecklegen, Bernoulli-Antworten und zufaelliger Halbierung; die Naeherung 'quadrat' muss dort
    schlechter liegen als 'exakt' (Beleg, dass Koeffizient B/(B+kappa) und Endlichkeitskorrektur real sind).
T3  Fail-closed: kappa <= 0, N < 2*B, negative Varianzen, NaN, falsche Gewichte, zu grosse Endlichkeitskorrektur.
T4  kappa* geschlossen = U/V0 bei D = F = 0; numerisch identisch; mit Split-Term groesser als U/V0.
T5  Kommandozeile: ungueltige Eingabe -> Rueckgabecode 2 und kein JSON auf stdout (Fehlerfall einmal ausgeloest).
"""
import json
import math
import os
import random
import subprocess
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import alc_law as L  # noqa: E402

DW = os.path.join(HIER, "referenz")


class T1Reproduktion(unittest.TestCase):
    def test_split_json_tabelle(self):
        sj = json.load(open(os.path.join(DW, "split.json")))
        kurve = L.lernkurve(0.1833, 0.0673, 2.73, sj["D_cap30"], F=0.0, split="quadrat")
        for b, soll in sj["BB_vorhersage_mit_split_kappa2.73"].items():
            self.assertLessEqual(abs(round(kurve[int(b)], 4) - soll), 1e-6, f"B{b}")

    def test_alc_terme_json(self):
        # alc_terme.json wurde mit D = 0.00073 (gerundet) gerechnet; damit Reproduktion auf 1e-9
        at = json.load(open(os.path.join(DW, "alc_terme.json")))
        r = L.alc(0.1833, 0.0673, 2.73, 0.00073, F=0.0, split="quadrat")
        for key, mine in (("stichprobenterm", r["stichprobe"]), ("splitterm", r["split"]), ("priorterm", r["prior"]),
                          ("ALC_BB_formel_mit_split", r["ALC"]), ("ALC_min_paarebene_V0_0", r["paar_boden_V0_0"])):
            self.assertLessEqual(abs(mine - at[key]), 1e-6, key)
        # und mit dem ungerundeten D_cap30 aus split.json bleibt es unter 1e-6 (Plan-Kriterium)
        sj = json.load(open(os.path.join(DW, "split.json")))
        r2 = L.alc(0.1833, 0.0673, 2.73, sj["D_cap30"], F=0.0, split="quadrat")
        self.assertLessEqual(abs(r2["ALC"] - at["ALC_BB_formel_mit_split"]), 1e-6)


def _mc_population(rng, n_paare=400, N=120, alpha=1.4, beta=1.35):
    """Synthetische Paare: Paarquote r ~ Beta(alpha, beta); Items p_i in {0, 1} mit P(p_i = 1) = r (wie n = 1-Zellen),
    plus ein Drittel Items mit p_i = r (gemischt), damit W > 0. Rueckgabe: Liste von Item-Listen."""
    paare = []
    for _ in range(n_paare):
        r = rng.betavariate(alpha, beta)
        p = [1.0 if rng.random() < r else 0.0 for _ in range(2 * N // 3)] + [r] * (N - 2 * N // 3)
        paare.append(p)
    return paare


class T2MonteCarlo(unittest.TestCase):
    def test_exakt_trifft_simulation(self):
        rng = random.Random(20261020)
        alpha, beta = 1.4, 1.35
        kappa, mu = alpha + beta, alpha / (alpha + beta)
        N = 120
        paare = _mc_population(rng, n_paare=600, N=N, alpha=alpha, beta=beta)
        budgets = (1, 3, 7, 15, 31)
        # Momente der Population (wie sie aus Daten geschaetzt wuerden): U, V0, D, F aus denselben Paaren
        U = V0 = D = F = 0.0
        for p in paare:
            m = sum(p) / N
            var = sum((x - m) ** 2 for x in p) / N
            U += m * (1 - m)                 # R(1-R) des ganzen Paares (Naeherung fuer E R_E(1-R_E))
            V0 += (mu - m) ** 2              # Prior-Fehler gegen die Paarquote (Naeherung fuer E(mu-R_E)^2)
            D += L.D_aus_varianz(var, N)
            F += L.F_aus_varianz(var, N)
        U, V0, D, F = (x / len(paare) for x in (U, V0, D, F))
        # Simulation: viele Wiederholungen je Paar (Split, Ziehen, Antworten)
        wied = 60
        summe = {b: 0.0 for b in budgets}
        summe2 = {b: 0.0 for b in budgets}
        n = 0
        for p in paare:
            for _ in range(wied):
                idx = list(range(N))
                rng.shuffle(idx)
                A, E = idx[:N // 2], idx[N // 2:]
                RE = sum(p[i] for i in E) / len(E)
                k = 0
                for j, i in enumerate(A[:max(budgets)], start=1):
                    k += 1 if rng.random() < p[i] else 0
                    if j in summe:
                        q = (k + kappa * mu) / (j + kappa)
                        e = (q - RE) ** 2
                        summe[j] += e
                        summe2[j] += e * e
                n += 1
        mc = {b: summe[b] / n for b in budgets}
        se = {b: math.sqrt(max(summe2[b] / n - mc[b] ** 2, 0.0) / n) for b in budgets}
        # Hinweis: V0 oben ist E(mu - R)^2 mit R = Paarquote; die Formel erwartet E(mu - R_E)^2 = E(mu-R)^2 + D/4
        V0E = V0 + D / 4
        ex = L.lernkurve(U, V0E, kappa, D, F, split="exakt", budgets=budgets)
        qu = L.lernkurve(U, V0E, kappa, D, 0.0, split="quadrat", budgets=budgets)
        fehler_ex = fehler_qu = 0.0
        for b in budgets:
            # Simulation und exakte Formel stimmen innerhalb von 3 MC-Standardfehlern + 0.2 % Rundungsreserve ueberein
            tol = 3 * se[b] + 0.002 * mc[b]
            self.assertLessEqual(abs(ex[b] - mc[b]), tol, f"B{b}: exakt {ex[b]:.6f} MC {mc[b]:.6f} +- {se[b]:.6f}")
            fehler_ex += abs(ex[b] - mc[b]) / mc[b]
            fehler_qu += abs(qu[b] - mc[b]) / mc[b]
        self.assertLess(fehler_ex, fehler_qu, "die exakte Form muss die Simulation besser treffen als die 'quadrat'-Naeherung")
        print(f"\n[T2] MC-Vergleich (N={N}, {len(paare)} Paare x {wied}): summierter rel. Fehler exakt {fehler_ex:.4f}, quadrat {fehler_qu:.4f}; "
              f"B31: MC {mc[31]:.6f} +- {se[31]:.6f}, exakt {ex[31]:.6f}, quadrat {qu[31]:.6f}")


class T3FailClosed(unittest.TestCase):
    def test_kappa_null_oder_negativ(self):
        for k in (0.0, -1.0):
            with self.assertRaises(L.ALCLawError):
                L.lernkurve(0.18, 0.07, k, 0.001)

    def test_N_kleiner_2B(self):
        with self.assertRaises(L.ALCLawError):
            L.lernkurve(0.18, 0.07, 2.7, 0.001, N=61)   # N//2 = 30 < 31
        L.lernkurve(0.18, 0.07, 2.7, 0.001, N=62)       # Grenzfall erlaubt

    def test_negative_varianzen_und_nan(self):
        for args in ((0.18, -0.01, 2.7, 0.001), (0.18, 0.07, 2.7, -0.001), (0.3, 0.07, 2.7, 0.001),
                     (float("nan"), 0.07, 2.7, 0.001), (0.18, 0.07, float("inf"), 0.001)):
            with self.assertRaises(L.ALCLawError):
                L.lernkurve(*args)
        with self.assertRaises(L.ALCLawError):
            L.lernkurve(0.18, 0.07, 2.7, 0.001, F=0.01)  # U - 30*F < 0

    def test_gewichte_und_split(self):
        with self.assertRaises(L.ALCLawError):
            L.alc(0.18, 0.07, 2.7, gewichte=(0.5, 0.5, 0, 0, 0, 0.1))
        with self.assertRaises(L.ALCLawError):
            L.lernkurve(0.18, 0.07, 2.7, split="linear")
        with self.assertRaises(L.ALCLawError):
            L.D_aus_varianz(0.1, 1)


class T4KappaOpt(unittest.TestCase):
    def test_geschlossen_gleich_numerisch(self):
        U, V0 = 0.1833, 0.0673
        g = L.kappa_opt(U, V0)
        self.assertAlmostEqual(g["kappa_opt"], U / V0, places=12)
        # numerisch mit winzigem D ~ geschlossen
        n = L.kappa_opt(U, V0, D=1e-12, split="quadrat")
        self.assertAlmostEqual(n["kappa_opt"], U / V0, places=4)
        # je Budget einzeln ist U/V0 optimal (Ableitung = 0)
        for B in (1, 3, 7, 15, 31):
            f = lambda k: L.terme_budget(B, U, V0, k)["mse"]
            k0 = U / V0
            self.assertLess(f(k0), min(f(k0 * 0.9), f(k0 * 1.1)))

    def test_split_term_erhoeht_kappa_opt(self):
        U, V0 = 0.1833, 0.0673
        m = L.kappa_opt(U, V0, D=0.00138, split="exakt")
        self.assertGreater(m["kappa_opt"], U / V0)
        self.assertLess(m["kappa_opt"], U / V0 + 0.1)


class T5Kommandozeile(unittest.TestCase):
    def test_fail_closed_rc2(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "alc_law.py"), "--U", "0.1833", "--V0", "0.0673",
                            "--kappa", "0"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), "")
        self.assertIn("fail-closed", r.stderr)
        r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "alc_law.py"), "--U", "0.1833", "--V0", "0.0673",
                            "--kappa", "2.73", "--N", "40"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, "N = 40 < 2*31 muss abbrechen")

    def test_gueltig_rc0(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "alc_law.py"), "--U", "0.1833", "--V0", "0.0673",
                            "--kappa", "2.73", "--D", "0.00138"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertIn("ALC", out)
        self.assertAlmostEqual(out["kurve"]["0"], 0.0673, places=12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
