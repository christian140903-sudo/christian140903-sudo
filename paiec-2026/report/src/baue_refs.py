#!/usr/bin/env python3 -I
"""baue_refs.py — erzeugt bericht-v2/refs.bib und tabellen/tabG_bibliografie.tex (P10, BAUPLAN-V2 §2.4).

Quelle: v2-plan/BIBLIOGRAFIE.bib (alle Eintraege geprueft 2026-10-20, Pruefweg im note-Feld) plus die im Plan genannten
Zusatzeintraege (rubin1976, wolpert1992: Crossref-geprueft 2026-10-21 07:27:57Z durch P10; paiec2026, paiecbase2026,
mdb2026 als @misc mit URL, Zugriffsdatum, Revision/Commit). Das deutsche note-Feld wird in refs.bib zu `annote`
(plainnat druckt es nicht); Anhang G listet je Schluessel Pruefweg und Datum aus genau diesem Feld.
Fail-closed: fehlt die Quelle oder ist ein Eintrag ohne note, rc 1.

Feinschliff N, Runde 1 (Endpruefung N/O): (O12) Titel der Zusatzeintraege gross nach dem Doppelpunkt; eine im howpublished-Text stehende
DOI ('..., DOI 10.x/y') wird in das Feld doi verschoben (url = doi.org-Link; plainnat druckt doi bei @misc nicht, der Link bleibt sichtbar);
(O13) Anhang-Tabelle 'Reference check' in der Reihenfolge der gedruckten Zitation (Autor, Jahr, Titel wie plainnat), pruefe_zahlen.py
vergleicht sie mit der .bbl; (O1) Spalten linksbuendig statt Blocksatz (Paket array).

Letzter Schliff (2026-10-21, FREIGABE Schlussrunde D1/D2/K6): Was im PDF erscheint, ist englisch und frei von Uhrzeiten,
Agentennamen und internen Dateinamen. (1) howpublished wird bereinigt (Uhrzeiten, deutsche Zusaetze, 'lt. arXiv-Kommentar'
-> 'per arXiv comment', 'arXiv-Preprint' -> 'arXiv preprint'); (2) das Jahr folgt dem Erscheinungsjahr der genannten Venue
(DOI-/arXiv-Angabe), jede Aenderung wird protokolliert; (3) Anhang G ist eine kurze englische Tabelle NUR der zitierten
Schluessel (Art der Pruefung, kein Datum je Zeile, keine Uhrzeit); (4) die Zusatzeintraege tragen englische annote ohne
Uhrzeit/Agentennamen. Was die Schicht darunter schon tut: plainnat druckt annote nicht; howpublished wird gedruckt.
"""
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
QUELLE = HIER.parent / "v2-plan" / "BIBLIOGRAFIE.bib"
ZIEL = HIER / "refs.bib"
TAB = HIER / "tabellen" / "tabG_bibliografie.tex"

ZUSATZ = r"""
@article{rubin1976,
  author = {Donald B. Rubin},
  title = {Inference and missing data},
  journal = {Biometrika},
  volume = {63},
  number = {3},
  pages = {581--592},
  year = {1976},
  doi = {10.1093/biomet/63.3.581},
  url = {https://doi.org/10.1093/biomet/63.3.581},
  annote = {Checked 2026-10-21 via Crossref (api.crossref.org/works/10.1093/biomet/63.3.581: title, journal, volume 63(3), pages 581-592, year 1976 match). Use: ignorability of the label selection (Lemma 2, Appendix A.7).}
}

@article{wolpert1992,
  author = {David H. Wolpert},
  title = {Stacked generalization},
  journal = {Neural Networks},
  volume = {5},
  number = {2},
  pages = {241--259},
  year = {1992},
  doi = {10.1016/S0893-6080(05)80023-1},
  url = {https://doi.org/10.1016/S0893-6080(05)80023-1},
  annote = {Checked 2026-10-21 via Crossref (api.crossref.org/works/10.1016/S0893-6080(05)80023-1: title, journal, volume 5(2), pages 241-259, year 1992 match). Use: stacking in the method league and H5.}
}

@misc{paiec2026,
  author = {{Stanford AIMS}},
  title = {{NeurIPS} 2026 {Predictive AI Evaluation Competition} ({PAIEC}): Competition description and rules},
  year = {2026},
  howpublished = {Codabench competition page and starter kit},
  url = {https://aims.stanford.edu/competition},
  annote = {Page accessed 2026-10-20 (competition text, including the report format). Use: protocol, metric, rules.}
}

@misc{paiecbase2026,
  author = {{Stanford AIMS}},
  title = {paiec\_baseline: Starter kit and baselines for {PAIEC} 2026},
  year = {2026},
  howpublished = {GitHub repository aims-foundations/paiec\_baseline, commit cc88a959 (2026-10-15)},
  url = {https://github.com/aims-foundations/paiec_baseline},
  annote = {Repository accessed 2026-10-20, commit cc88a959c1e5e7462f31a9215baba066ce6d6e2b (read, not executed). Use: streaming\_ingestion.py (protocol replica), baselines Empirical Mean and BLE, tools/prepare\_data.py (audit finding 1).}
}

@misc{mdb2026,
  author = {{Stanford AIMS}},
  title = {{Measurement Data Bank} (aims-foundations/measurement-db)},
  year = {2026},
  howpublished = {Hugging Face dataset, revision 54074453 (2026-10-07); curation CC BY-SA 4.0, benchmarks under their upstream licences},
  url = {https://huggingface.co/datasets/aims-foundations/measurement-db},
  annote = {Dataset accessed 2026-10-20, revision 54074453da7b9911be0f48e4c560be547bc84d21 (formatted\_tables; GitHub measurement-db 652474f). Use: sole training source; subject of the data audit.}
}
"""


def lies_eintraege(text):
    """Zerlegt eine .bib-Datei in (typ, key, body)-Tupel (Klammerzaehlung, kommentarfest)."""
    eintraege = []
    i = 0
    while True:
        m = re.search(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text[i:])
        if not m:
            break
        start = i + m.start()
        j = i + m.end()
        tiefe = 1
        k = j
        while k < len(text) and tiefe > 0:
            if text[k] == "{":
                tiefe += 1
            elif text[k] == "}":
                tiefe -= 1
            k += 1
        eintraege.append((m.group(1), m.group(2), text[start:k]))
        i = k
    return eintraege


def feld(body, name):
    m = re.search(r"\b" + name + r"\s*=\s*\{", body)
    if not m:
        return None
    j = m.end()
    tiefe = 1
    k = j
    while k < len(body) and tiefe > 0:
        if body[k] == "{":
            tiefe += 1
        elif body[k] == "}":
            tiefe -= 1
        k += 1
    return body[j:k - 1]


def tex_escape(s):
    s = s.replace("\\%", "%").replace("\\_", "_")
    s = s.replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")
    return s


HOW_REGELN = [
    (r"\s*\(Crossref(?: \d{1,2}:\d{2} UTC)?\)", ""),
    (r",? \d{1,2}:\d{2} UTC", ""),
    (r";?\s*Autoren = AIMS-Veranstalter", ""),
    (r";\s*Koyejo-Gruppe", ""),
    (r"\s*\(lt\. arXiv-Kommentar\)", " (per arXiv comment)"),
    (r", Websuche\)", ")"),
    (r"arXiv-Preprint", "arXiv preprint"),
    (r"(arXiv preprint) \((?:Kensho/MIT|Epoch|Anthropic|EleutherAI)\)", r"\1"),
    (r"(arXiv preprint) \(BEA 2024\)", r"\1; BEA 2024"),
]
# Eintraege, deren Venue-Angabe nur als Websuche/ohne Jahr vorlag (arXiv-Kommentar geprueft 2026-10-21: 'Accepted to AAAI 2026')
HOW_EXPLIZIT = {"zhou2025psnirt": "AAAI 2026 (per arXiv comment)"}
# Verbotsmuster fuer Felder, die ins PDF gehen (howpublished)
HOW_VERBOT = re.compile(r"\d{1,2}:\d{2}|UTC|Crossref \d|Websuche|Autoren|Veranstalter|Gruppe|lt\.|Kommentar|Preprint")


def bereinige_eintrag(key, body, protokoll):
    """howpublished englisch/ohne Uhrzeit; Jahr = Erscheinungsjahr der genannten Venue (DOI-/arXiv-Angabe)."""
    how = feld(body, "howpublished")
    if how is None:
        return body
    neu = HOW_EXPLIZIT.get(key)
    if neu is None:
        neu = how
        for rx, ers in HOW_REGELN:
            neu = re.sub(rx, ers, neu)
        neu = neu.strip()
    # O12: DOI aus dem howpublished-Text in das Feld doi (url = doi.org-Link); howpublished behaelt nur die Venue
    md = re.search(r",?\s*DOI (10\.[^\s,;)}]+)", neu)
    if md:
        doi = md.group(1)
        neu = (neu[:md.start()] + neu[md.end():]).strip(" ,;")
        if re.search(r"\bdoi\s*=", body):
            raise SystemExit(f"{key}: DOI im howpublished UND Feld doi")
        body = re.sub(r"(\burl\s*=\s*\{)[^}]*\}", lambda m_: m_.group(1) + "https://doi.org/" + doi + "},\n  doi = {" + doi + "}", body, count=1)
    if HOW_VERBOT.search(neu):
        raise SystemExit(f"howpublished {key} nach Bereinigung noch verdaechtig: {neu!r}")
    m = re.search(r"\b(19|20)\d\d\b", neu)
    jahr = feld(body, "year")
    if m and jahr is not None and m.group(0) != jahr.strip():
        protokoll.append((key, jahr.strip(), m.group(0), neu))
        body = re.sub(r"(\byear\s*=\s*\{)" + re.escape(jahr) + r"\}", r"\g<1>" + m.group(0) + "}", body, count=1)
    # R2 (Q9): plainnat haengt ", <Jahr>" an howpublished; steht das Jahr schon im Venue-Text ("NAACL 2025, 2025"), faellt es dort weg
    jahr = feld(body, "year")
    if jahr is not None:
        neu = re.sub(r"(?:(?<=[A-Za-z]) |,\s+)" + re.escape(jahr.strip()) + r"\b", "", neu, count=1)
    body = body.replace("howpublished = {" + how + "}", "howpublished = {" + neu + "}", 1)
    return body


def zitierte_schluessel():
    """Alle \\cite-Schluessel aus tex + tabellen/ + abbildungen/ (ohne die erzeugte Anhang-G-Tabelle) -- wie pruefe_zahlen.py."""
    quellen = [HIER / "paiec_report_v2.tex"] + sorted((HIER / "tabellen").glob("tab[0-9]*.tex")) + sorted((HIER / "abbildungen").glob("*.tex"))
    alles = "\n".join(q.read_text(encoding="utf-8") for q in quellen if q.is_file())
    used = set()
    for m in re.finditer(r"\\cite[tp]?(?:alp)?\*?(?:\[[^\]]*\])*\{([^}]*)\}", alles):
        used |= {k.strip() for k in m.group(1).split(",")}
    return used


def _tokens(s):
    """Wortzerlegung eines BibTeX-Namens auf Klammerebene 0 (eine {..}-Gruppe ist ein Wort)."""
    out, cur, tiefe = [], "", 0
    for ch in s:
        if ch == "{":
            tiefe += 1
        elif ch == "}":
            tiefe -= 1
        if ch.isspace() and tiefe == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def sortschluessel(body):
    """Sortierschluessel wie plainnat: alle Autoren als 'von Last' (klein, ohne Klammern), dann Jahr, dann Titel ohne fuehrenden Artikel."""
    def rein(x):
        return re.sub(r"[{}\\]", "", x).lower()
    autor = feld(body, "author") or ""
    namen = []
    for a in re.split(r"\s+and\s+", autor):
        tk = _tokens(a.strip())
        if not tk:
            continue
        last = tk[-1]
        von = []
        for w in tk[:-1][::-1]:
            if w[0].islower():
                von.insert(0, w)
            else:
                break
        namen.append(rein(" ".join(von + [last])))
    titel = rein(feld(body, "title") or "")
    titel = re.sub(r"^(the|a|an) ", "", titel)
    return ("   ".join(namen), (feld(body, "year") or "").strip(), titel)


def art_der_pruefung(annote, how_roh):
    """Englische Kurzform aus dem (internen) annote und dem Roh-howpublished; kein Datum, keine Uhrzeit."""
    a = annote.lower()
    teile = []
    if "arxiv-api" in a:
        teile.append("arXiv record")
    if "crossref" in a or "crossref" in how_roh.lower():
        teile.append("DOI record")
    if "proceedings.mlr.press" in how_roh:
        teile.append("proceedings page")
    if not teile:
        return "page or repository accessed"
    if "edited-book" in a:
        return "DOI record of the edited volume checked"
    return " + ".join(teile) + " checked"


def main():
    if not QUELLE.is_file():
        print(f"FEHLT: {QUELLE}", file=sys.stderr)
        return 1
    quelle = QUELLE.read_text(encoding="utf-8")
    eintraege = lies_eintraege(quelle)
    if len(eintraege) < 80:
        print(f"zu wenige Eintraege in {QUELLE}: {len(eintraege)}", file=sys.stderr)
        return 1
    aus = ["% refs.bib — erzeugt von bericht-v2/baue_refs.py aus v2-plan/BIBLIOGRAFIE.bib (+ 5 Zusatzeintraege); nicht von Hand aendern.",
           "% note -> annote (plainnat druckt annote nicht); Pruefweg und Datum je Schluessel in Anhang G des Berichts.", ""]
    zeilen_g = []
    jahr_aenderungen = []
    keys = set()
    for typ, key, body in eintraege:
        note = feld(body, "note")
        if note is None:
            print(f"Eintrag ohne note: {key}", file=sys.stderr)
            return 1
        how_roh = feld(body, "howpublished") or ""
        body2 = re.sub(r"\bnote\s*=", "annote =", body, count=1)
        body2 = bereinige_eintrag(key, body2, jahr_aenderungen)
        aus.append(body2.strip())
        aus.append("")
        keys.add(key)
        zeilen_g.append((key, art_der_pruefung(note, how_roh), sortschluessel(body2)))
    for typ, key, body in lies_eintraege(ZUSATZ):
        if key in keys:
            print(f"doppelter Schluessel: {key}", file=sys.stderr)
            return 1
        how_roh = feld(body, "howpublished") or ""
        body = bereinige_eintrag(key, body, jahr_aenderungen)
        aus.append(body.strip())
        aus.append("")
        keys.add(key)
        zeilen_g.append((key, art_der_pruefung(feld(body, "annote"), how_roh), sortschluessel(body)))
    text = "\n".join(aus)
    # Crossref liefert brier1950 in Versalien; Schreibweise normalisiert (Inhalt unveraendert, geprueft 2026-10-20)
    text = text.replace("author = {GLENN W. BRIER}", "author = {Glenn W. Brier}")
    text = text.replace("title = {{VERIFICATION} {OF} {FORECASTS} {EXPRESSED} {IN} {TERMS} {OF} {PROBABILITY}}",
                        "title = {Verification of forecasts expressed in terms of probability}")
    ZIEL.write_text(text, encoding="utf-8")
    TAB.parent.mkdir(exist_ok=True)
    zit = zitierte_schluessel()
    fehlend = sorted(zit - keys)
    if fehlend:
        print(f"zitierte Schluessel nicht in refs.bib: {fehlend}", file=sys.stderr)
        return 1
    # O13: nach gedruckter Zitation (Autor, Jahr, Titel), nicht nach BibTeX-Schluessel
    zeilen = [(k, p) for k, p, _ in sorted((z for z in zeilen_g if z[0] in zit), key=lambda z: z[2])]
    n = len(zeilen)
    hälfte = (n + 1) // 2
    links, rechts = zeilen[:hälfte], zeilen[hälfte:]
    g = ["% erzeugt von bericht-v2/baue_refs.py (nur zitierte Schluessel) -- nicht von Hand aendern",
         "\\begin{table}[H]",
         f"  \\caption{{Reference check. Of the {n} references cited in this report, the bibliographic record (authors, title, year, venue) was checked "
         "against the arXiv record or the DOI record, or the page or repository was accessed, on 20--21 October 2026. "
         "The checks were carried out by AI agents under the author's direction (Section ``Use of AI assistants'') and cover the record, not the full text. "
         "A venue given ``per arXiv comment'' is the one stated in the arXiv record and was not checked at the publisher.}",
         "  \\label{tab:bibcheck}",
         "  \\centering\\scriptsize",
         "  \\setlength{\\tabcolsep}{3pt}",
         "  \\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{3.3cm}>{\\raggedright\\arraybackslash}p{3.1cm}@{\\hspace{10pt}}>{\\raggedright\\arraybackslash}p{3.3cm}>{\\raggedright\\arraybackslash}p{3.1cm}@{}}",
         "    \\toprule",
         "    key & check & key & check \\\\",
         "    \\midrule"]
    for i in range(hälfte):
        l = links[i]
        r = rechts[i] if i < len(rechts) else None
        zl = f"\\citet{{{l[0]}}} & {l[1]}"
        zr = f"\\citet{{{r[0]}}} & {r[1]}" if r else " & "
        g.append(f"    {zl} & {zr} \\\\")
    g += ["    \\bottomrule", "  \\end{tabular}", "\\end{table}"]
    TAB.write_text("\n".join(g) + "\n", encoding="utf-8")
    for key, alt, neu_j, how in jahr_aenderungen:
        print(f"Jahr {key}: {alt} -> {neu_j} (Venue: {how})")
    print(f"refs.bib: {len(keys)} Eintraege; {TAB.name}: {n} zitierte Schluessel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
