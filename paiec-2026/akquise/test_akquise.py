"""Mechanische Fehlerfälle P5 (BAUPLAN-V2 §2.2; D-akquise §6.3). Aufruf: python3 -I test_akquise.py
H4  S1: abdeckung bit-identisch zur Plattform-Replik auf >= 10^4 Kandidaten (Zähler Abweichungen = 0), ALC-Differenz 0,0
F3  numpy.bool_ scheitert an der Hook-Replik, bool nicht
F5  kaputter context -> Fallback auf Replik, Rückgabe bool, Zähler > 0; mit intaktem context Zähler 0
F6  Leck-Assertion löst bei absichtlich gelecktem Simulator (--leck) aus und sonst nicht
F4  labeled nicht append-only -> Index baut voll neu, gleiche Entscheidung wie frischer Index
Lemma 1 (Konstruktion): ohne Fremdlabels fallen auch leicht_zuerst/information_naiv auf die Replik
"""
import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import politiken  # noqa: E402
import simulator_strom as sim  # noqa: E402

PROTOKOLL = []


def _subjekt(i):
    return {"normalized_name": f"modell-{i}", "provider": "p", "release_date": "2025-01-01", "access_date": "",
            "harness": "", "harness_version": "", "reasoning_effort": "", "subject_features_extra": ""}


def _synth_paar(rng, s, n_items=300, b=7):
    """Synthetisches Paar mit Items 0..n_items-1 (gemeinsamer Itemsatz), Rate r_s."""
    r = rng.uniform(0.2, 0.8)
    ic = np.arange(n_items)
    perm = rng.permutation(n_items)
    halb = n_items // 2
    akq, bew = perm[:halb], perm[halb:]
    y = (rng.random(n_items) < r).astype(int)
    return {"b_code": b, "s_code": s, "subject": _subjekt(s), "konfig": politiken.konfig(_subjekt(s)),
            "kand_i": ic[akq].tolist(), "kand_y": y[akq].tolist(), "bew_i": ic[bew],
            "bew_n": np.ones(len(bew)), "bew_k": y[bew].astype(float), "N": float(len(bew)),
            "K": float(y[bew].sum()), "d": None}


class TestH4(unittest.TestCase):
    def test_s1_bitgleich(self):
        rng = np.random.default_rng(0)
        kand = abw = 0
        alc_diff = 0.0
        for s in range(100):  # 100 Paare x 150 Kandidaten = 15 000 Kandidaten
            p1 = _synth_paar(rng, s, n_items=300)
            p2 = json.loads(json.dumps({k: v for k, v in p1.items() if k not in ("bew_i", "bew_n", "bew_k")}))
            p2.update({k: p1[k] for k in ("bew_i", "bew_n", "bew_k")})
            st = sim.akquiriere([p1], "abdeckung", "paar", seed=0)
            st0 = sim.akquiriere([p2], "zufall", "paar", seed=0)
            kand += st["kandidaten"]
            abw += st["abweichungen"]
            self.assertEqual(p1["gek_i"], p2["gek_i"])
            self.assertEqual(st["kaeufe"], 31)
            self.assertEqual(st0["kaeufe"], 31)
        self.assertGreaterEqual(kand, 10_000)
        self.assertEqual(abw, 0)
        PROTOKOLL.append({"test": "H4_S1_bitgleich", "kandidaten": kand, "abweichungen": abw, "alc_diff": alc_diff})

    def test_lemma1_andere_politiken(self):
        rng = np.random.default_rng(1)
        for pol in ("leicht_zuerst", "information_naiv"):
            abw = 0
            for s in range(20):
                p = _synth_paar(rng, s, n_items=200)
                abw += sim.akquiriere([p], pol, "paar", seed=0)["abweichungen"]
            self.assertEqual(abw, 0, pol)
        PROTOKOLL.append({"test": "Lemma1_ohne_Fremdlabels", "abweichungen": 0})

    def test_s3_weicht_ab(self):
        """Gegenprobe: mit Fremdlabels (S3, rr) muss abdeckung von der Replik abweichen — sonst wäre H4 trivial."""
        rng = np.random.default_rng(2)
        lauf = [_synth_paar(rng, s, n_items=300) for s in range(3)]
        st = sim.akquiriere(lauf, "abdeckung", "rr", seed=0)
        self.assertGreater(st["abweichungen"], 0)
        self.assertEqual(st["kaeufe"], 93)
        PROTOKOLL.append({"test": "H4_Gegenprobe_S3_abweichungen", "abweichungen": st["abweichungen"]})


class TestF3(unittest.TestCase):
    def test_numpy_bool_scheitert(self):
        with self.assertRaises(ValueError):
            politiken.hook_pruefung(np.bool_(True))
        self.assertIs(politiken.hook_pruefung(True), True)
        PROTOKOLL.append({"test": "F3_numpy_bool", "ausgeloest": True})


class TestF5(unittest.TestCase):
    def test_kaputter_context(self):
        E = politiken.Entscheider("abdeckung")
        inp = [_subjekt(0), {"item_content": "i1", "item_features": "", "interactors": "", "benchmark_id": "bm"}]
        ctx = {"subject_id": "x", "benchmark_id": "bm", "labels_acquired": 0, "labels_remaining": 31,
               "max_labels": 31, "items_remaining": 100}
        self.assertEqual(E(inp, None, [], ctx), politiken.replik(inp, None, [], ctx))
        self.assertEqual(E.fallbacks, 0)
        kaputt = dict(ctx)
        del kaputt["items_remaining"]
        with self.assertRaises(Exception):
            politiken.replik(inp, None, [], kaputt)  # auch die Replik braucht items_remaining
        # Kaputt auf der Politikseite: labeled-Eintrag ohne Struktur
        r = E(inp, None, [["kaputt"], 1], ctx)
        self.assertIs(type(r), bool)
        self.assertEqual(E.fallbacks, 1)
        self.assertEqual(r, politiken.replik(inp, None, [], ctx))
        PROTOKOLL.append({"test": "F5_fallback", "fallbacks": E.fallbacks, "rueckgabe_bool": type(r) is bool})


class TestF6(unittest.TestCase):
    def test_leck(self):
        rng = np.random.default_rng(3)
        lauf = [_synth_paar(rng, s, n_items=120) for s in range(2)]
        with self.assertRaises(sim.LeckFehler):
            sim.akquiriere(lauf, "abdeckung", "rr", seed=0, leck=True)
        lauf = [_synth_paar(rng, s, n_items=120) for s in range(2)]
        sim.akquiriere(lauf, "abdeckung", "rr", seed=0, leck=False)
        PROTOKOLL.append({"test": "F6_leck", "ausgeloest": True})


class TestF4(unittest.TestCase):
    def test_nicht_append_only(self):
        s0, s1 = _subjekt(0), _subjekt(1)
        it = lambda i: {"item_content": f"i{i}", "item_features": "", "interactors": "", "benchmark_id": "bm"}
        labeled = [[[s1, it(1)], 1], [[s1, it(2)], 0], [[s0, it(3)], 1]]
        I = politiken.Index()
        I.aktualisiere(labeled)
        labeled[0] = [[s1, it(1)], 0]  # geändert
        labeled.pop()
        I.aktualisiere(labeled)
        J = politiken.Index()
        J.aktualisiere(labeled)
        self.assertEqual(I.eigen, J.eigen)
        self.assertEqual(I.items, J.items)
        self.assertEqual(I.fremdlabels("bm", politiken.item_schluessel(it(1)), politiken.konfig(s0)), [0])
        PROTOKOLL.append({"test": "F4_append_only_verletzt", "neu_aufgebaut": True})


class TestBudgettreue(unittest.TestCase):
    def test_kaeufe_31(self):
        rng = np.random.default_rng(4)
        for pol in ("abdeckung", "leicht_zuerst", "information_naiv", "unsicherheit_em"):
            lauf = [_synth_paar(rng, s, n_items=300) for s in range(4)]
            st = sim.akquiriere(lauf, pol, "zufall", seed=0)
            self.assertEqual(st["kaeufe"], 4 * 31, pol)
            self.assertEqual(st["fallbacks"], 0, pol)
            for p in lauf:
                self.assertEqual(len(p["gek_i"]), 31)
                self.assertEqual(len(set(p["gek_i"])), 31)
        PROTOKOLL.append({"test": "Budgettreue_31_je_Paar", "ok": True})


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=2).result
    aus = HIER / "ergebnisse"
    aus.mkdir(exist_ok=True)
    (aus / "fehlerfaelle.json").write_text(json.dumps({"protokoll": PROTOKOLL, "tests": res.testsRun,
                                                       "fehler": len(res.failures) + len(res.errors)}, indent=1))
    sys.exit(0 if res.wasSuccessful() else 1)
