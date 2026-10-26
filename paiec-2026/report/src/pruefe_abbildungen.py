"""pruefe_abbildungen.py — Druckfaehigkeit aller eingebetteten Abbildungen (S3, FREIGABE-EINREICHUNG.md).

Fuer jede \\includegraphics-Abbildung des Berichts:
  Einbaubreite (aus dem tex, \\linewidth = textwidth aus neurips_2026.sty)  /  PDF-Seitenbreite der Abbildung  = Skalierung
  effektive Schriftgroesse im Druck = Tf-Schriftgroesse im Abbildungs-PDF * Textmatrix-Faktor * Skalierung   (pypdf, je Textlauf)
Fehler (rc 1), fail-closed:
  * effektive Schrift < 6,0 pt irgendwo in der Abbildung;           * Skalierung < 0,95 (nachtraegliche Verkleinerung);
  * Abbildung fehlt / unlesbar / keine Textlaeufe gefunden (nicht pruefbar = Fehler, nie "ok");
  * eine eingebettete Abbildung ist in der Pruefliste nicht erfasst (Parser findet 0 Abbildungen = Fehler).
Hinweise (kein Fehler): Skalierung > 1,05; kleinste Schrift < 6,5 pt (Soll: Achsen >= 7, Annotationen/Legenden >= 6,5).
Aufruf (aus bericht-v2/):  python3 -I pruefe_abbildungen.py [--tex paiec_report_v2.tex] [--abb abbildungen] [--sty neurips_2026.sty]
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
MIN_FEHLER, MIN_SOLL, SKAL_MIN, SKAL_MAX = 6.0, 6.5, 0.95, 1.05
EINHEIT_BP = {"in": 72.0, "pt": 72.0 / 72.27, "bp": 1.0, "cm": 72.0 / 2.54, "mm": 72.0 / 25.4}


def fehl(msg):
    print(f"FEHLER: {msg}")
    return 1


def textbreite_bp(sty: Path) -> float:
    if not sty.is_file():
        raise SystemExit(f"FEHLER: {sty} fehlt (Textbreite unbekannt)")
    m = re.search(r"textwidth\s*=\s*([0-9.]+)\s*(in|pt|cm|mm|bp)", sty.read_text(encoding="utf-8", errors="replace"))
    if not m:
        raise SystemExit("FEHLER: textwidth in neurips_2026.sty nicht gefunden")
    return float(m.group(1)) * EINHEIT_BP[m.group(2)]


def einbauten(tex: Path, tw: float):
    """[(Dateiname, Einbaubreite in bp)] aus allen \\includegraphics mit width=..."""
    s = tex.read_text(encoding="utf-8", errors="replace")
    s = "\n".join(z for z in s.splitlines() if not z.lstrip().startswith("%"))
    out = []
    for m in re.finditer(r"\\includegraphics\[([^\]]*)\]\{([^}]+)\}", s):
        w = re.search(r"width\s*=\s*([0-9.]*)\s*(\\linewidth|\\textwidth|\\columnwidth|in|pt|bp|cm|mm)", m.group(1))
        if not w:
            raise SystemExit(f"FEHLER: \\includegraphics ohne lesbare width: {m.group(0)}")
        f = float(w.group(1)) if w.group(1) else 1.0
        bp = f * tw if w.group(2).startswith("\\") else f * EINHEIT_BP[w.group(2)]
        out.append((m.group(2), bp))
    return out


def det(m):
    return abs(m[0] * m[3] - m[1] * m[2])


def schriftgroessen(pdf: Path):
    """(Seitenbreite bp, [(effektive Groesse im Abbildungs-PDF, Text)]) je Textlauf."""
    from pypdf import PdfReader
    r = PdfReader(str(pdf))
    if len(r.pages) != 1:
        raise ValueError(f"{len(r.pages)} Seiten (erwartet 1)")
    pg = r.pages[0]
    breite = float(pg.mediabox.width)
    laeufe = []

    def besuch(text, cm, tm, fd, fs):
        if text and text.strip():
            laeufe.append((abs(fs) * math.sqrt(det(tm)) * math.sqrt(det(cm)), text.strip()))

    pg.extract_text(visitor_text=besuch)
    return breite, laeufe


def pruefe(tex: Path, abb: Path, sty: Path) -> int:
    tw = textbreite_bp(sty)
    ein = einbauten(tex, tw)
    if not ein:
        return fehl("keine \\includegraphics-Abbildung im tex gefunden (nicht pruefbar)")
    rc = 0
    print(f"Textbreite {tw:.1f} bp; {len(ein)} eingebettete Abbildungen\n")
    print(f"{'Abbildung':30s} {'PDF bp':>7s} {'Einbau bp':>9s} {'Skal.':>6s} {'min pt':>7s}  Bewertung")
    for name, ebp in ein:
        p = abb / name
        try:
            pb, laeufe = schriftgroessen(p)
        except Exception as e:  # Datei fehlt/unlesbar -> Fehler
            rc |= fehl(f"{name}: {type(e).__name__}: {e}")
            continue
        if not laeufe:
            rc |= fehl(f"{name}: keine Textlaeufe gefunden (nicht pruefbar)")
            continue
        skal = ebp / pb
        eff = [(g * skal, t) for g, t in laeufe]
        klein = min(eff)
        bew = []
        if klein[0] < MIN_FEHLER:
            n = sum(1 for g, _ in eff if g < MIN_FEHLER)
            bew.append(f"FEHLER {n} Textlaeufe < {MIN_FEHLER} pt (kleinster: {klein[0]:.1f} pt, '{klein[1][:30]}')")
            rc = 1
        if skal < SKAL_MIN:
            bew.append(f"FEHLER Skalierung {skal:.2f} < {SKAL_MIN}")
            rc = 1
        if klein[0] >= MIN_FEHLER and klein[0] < MIN_SOLL:
            bew.append(f"Hinweis: kleinste Schrift {klein[0]:.1f} pt < Soll {MIN_SOLL}")
        if skal > SKAL_MAX:
            bew.append(f"Hinweis: Skalierung {skal:.2f} > {SKAL_MAX}")
        print(f"{name:30s} {pb:7.1f} {ebp:9.1f} {skal:6.2f} {klein[0]:7.2f}  {'; '.join(bew) or 'ok'}")
    print("\nrc", rc, "(0 = alle Abbildungen druckfaehig)")
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=str(HIER / "paiec_report_v2.tex"))
    ap.add_argument("--abb", default=str(HIER / "abbildungen"))
    ap.add_argument("--sty", default=str(HIER / "neurips_2026.sty"))
    a = ap.parse_args(argv)
    return pruefe(Path(a.tex), Path(a.abb), Path(a.sty))


if __name__ == "__main__":
    sys.exit(main())
