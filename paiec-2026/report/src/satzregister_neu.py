#!/usr/bin/env python3 -I
"""satzregister_neu.py -- schreibt die Hashes des Satzregisters (pruefe_zahlen.SATZREGISTER) fuer die AKTUELLEN Saetze mit Allwort neu.

Aufruf NUR nach manueller Pruefung der geaenderten/neuen Saetze gegen die Quellzahlen (Feinschliff N, Klasse (e)):
  python3 -I satzregister_neu.py [--notiz "Kopf=Notiz" ...] [--notizen datei.py]
Ein neuer Satz braucht eine Notiz (womit er belegt ist); ein geaenderter behaelt die alte Notiz und wird ausgegeben.
R2: --notizen datei.py: Liste N = [(Satzanfang, Notiz), ...]; die Notiz gilt fuer den Satz, der mit dem Satzanfang beginnt (auch fuer geaenderte Saetze).
Das Register umfasst das ganze Dokument (Abstract bis \\end{document}) und die Allwoerter aus pruefe_zahlen.ALLWORT; veraltete Eintraege entfallen.
"""
import importlib.util
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pz", HIER / "pruefe_zahlen.py")
pz = importlib.util.module_from_spec(spec)
_argv_orig = sys.argv[:]
sys.argv = ["x"]
spec.loader.exec_module(pz)
sys.argv = _argv_orig
tex = (HIER / "paiec_report_v2.tex").read_text(encoding="utf-8")
tex = re.sub(r"\\mbox\{(\$[^$]*\$)\}", r"\1", tex)
_args = sys.argv[1:]
neu_notizen = dict(a.split("=", 1) for a in _args if "=" in a and not a.startswith("--"))
_nd = {}
if "--notizen" in _args:
    _ns = {}
    exec(Path(_args[_args.index("--notizen") + 1]).read_text(encoding="utf-8"), _ns)
    _nd = dict(_ns["N"])
alt = pz.SATZREGISTER
eintraege = {}
for kopf, hsh, s in pz.allwort_saetze(tex):
    old = alt.get(kopf)
    note = neu_notizen.get(kopf) or next((n for sn, n in _nd.items() if s.startswith(sn)), None) or (old[1] if isinstance(old, tuple) else old)
    if note is None:
        sys.exit(f"NEUER Satz ohne Notiz (Kopf {kopf!r}): {s[:120]}")
    if isinstance(old, tuple) and old[0] != hsh:
        print(f"GEAENDERT (alte Notiz bleibt, bitte pruefen): {s[:120]}")
    eintraege[kopf] = (hsh, note)
src = (HIER / "pruefe_zahlen.py").read_text(encoding="utf-8")
i = src.index("SATZREGISTER = {")
j = src.index("\n}\n", i) + 3
neu = "SATZREGISTER = {\n" + "".join(f"    {k!r}: ({h!r}, {n!r}),\n" for k, (h, n) in eintraege.items()) + "}\n"
(HIER / "pruefe_zahlen.py").write_text(src[:i] + neu + src[j:], encoding="utf-8")
print(f"{len(eintraege)} Eintraege geschrieben")
