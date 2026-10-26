"""K4(b): label_wert() — Wertetabelle und Bitgleichheit mit der v1-Regel float(lab) >= 0.5 auf gültigen Eingaben."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inferenz  # noqa: E402


class TestLabelWert(unittest.TestCase):
    def test_tabelle(self):
        faelle = [(True, 1.0), (False, 0.0), (1, 1.0), (0, 0.0), (1.0, 1.0), (0.3, 0.0), (0.5, 1.0), ("1", 1.0), ("0", 0.0),
                  ("1.0", 1.0), ("0.0", 0.0), ("true", 1.0), ("TRUE", 1.0), (" Yes ", 1.0), ("no", 0.0), ("False", 0.0),
                  (None, None), ("", None), ("abc", None), ("n/a", None), (float("nan"), None), ("nan", None)]
        for lab, soll in faelle:
            self.assertEqual(inferenz.label_wert(lab), soll, repr(lab))

    def test_v1_regel_auf_gueltigen_eingaben(self):
        for lab in (True, False, 0, 1, 2, -1, 0.0, 0.49, 0.5, 0.51, 1.0, "0", "1", "0.2", "0.9", "1e0"):
            self.assertEqual(inferenz.label_wert(lab), 1.0 if float(lab) >= 0.5 else 0.0, repr(lab))

    def test_zeichen(self):
        self.assertEqual([inferenz._label_zeichen(x) for x in (1, 0, None, "yes", "x")], ["1", "0", "x", "1", "x"])

    def test_v1_warf_bei_text(self):
        with self.assertRaises(ValueError):
            float("true")  # Beleg für den alten Fehlerpfad (v1: Ausnahme -> Rückfall 0,5 für den ganzen Aufruf)
        self.assertEqual(inferenz.label_wert("true"), 1.0)


if __name__ == "__main__":
    unittest.main()
