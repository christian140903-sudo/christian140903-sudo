"""tabellen_v2.py — Tabellen 1–4 des Bericht-v2 (PAIEC 2026) als LaTeX (booktabs) aus JSON/CSV.

Aufruf (aus bericht-v2/): python3 -I tabellen_v2.py --aus tabellen
Fail-closed: fehlende Datei / Feld -> Ausnahme, rc != 0. Nicht evaluierte Teile stehen als "not evaluated" mit Grund.
Zahlen = discovery (Saaten 0-2, Design A, 10 Falten, 2 142 Testpaare, 142 Benchmarks), so beschriftet; Konfirmation aus
hypothesen_tafel.json (Schlussrunde 2026-10-21: alle 10 Hypothesen ausgewertet, Design A + B). Jede Tabelle nennt die Quelle in der Caption.
Die .tex-Dateien enthalten komplette table-Umgebungen (\\input{tabellen/...}); benoetigt \\usepackage{booktabs}.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
DATEN = HIER / "daten"
# Zwei Layouts: Arbeitsbaum (bericht-v2/ neben modell/, ./) oder Repository (report/src/ unter der Repo-Wurzel,
# wo ./{konfirmation,liga,theorie,kuratierung} als konfirmation/, liga/, theorie/, curation/ liegen).
ROOT = HIER.parent
if not (ROOT / "modell-v2").is_dir() and (HIER.parent.parent / "modell").is_dir():
    ROOT = HIER.parent.parent
_REPO = not (ROOT / "modell-v2").is_dir()


def mv2(rel: str) -> Path:
    """Pfad unter ./ im Arbeitsbaum bzw. an der Repo-Wurzel (kuratierung -> curation)."""
    if _REPO:
        return ROOT / rel.replace("kuratierung", "curation", 1)
    return ROOT / "modell-v2" / rel


sys.path.insert(0, str(mv2("theorie")))
import alc_law  # noqa: E402


class Eingabe(Exception):
    pass


# L1 (Feinschliff L): Regime-Anzeigename im Bericht; der Datenschluessel "kompakt10" und der Verzeichnisname bleiben.
ANZEIGE = {"kompakt10": "compact10"}


def lade_json(p: Path):
    if not p.is_file():
        raise Eingabe(f"Eingabe fehlt: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lade_csv(p: Path):
    if not p.is_file():
        raise Eingabe(f"Eingabe fehlt: {p}")
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def feld(d, *pfad):
    for k in pfad:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            raise Eingabe(f"Feld fehlt: {'/'.join(map(str, pfad))} (bei {k!r})")
    return d


def vergleich(ausw, modell, referenz, S, gew="paar"):
    for v in ausw["vergleiche"]:
        if v["modell"] == modell and v["referenz"] == referenz and v["S"] == S and v.get("gewichtung") == gew:
            return v
    raise Eingabe(f"Vergleich fehlt: {modell}-{referenz}/{S}/{gew}")


URTEIL = {"besser": "better", "schlechter": "worse", "kein Unterschied belegt": "no difference shown", "grey_zone": "grey",
          "better": "better", "worse": "worse", "equivalent": "equivalent", "not_evaluated": "not evaluated", "passed": "passed",
          "failed": "failed"}


def u(x):
    return URTEIL.get(x, x)


def buchstabe(d: float, se: float, marge: float = 0.001) -> str:
    """Urteilsbuchstabe nach der praeregistrierten Regel (Bericht Abschnitt 5): b better (d+2SE<0), w worse (d-2SE>0),
    e equivalent (|d|+2SE<marge), sonst g grey zone. Das Feld `urteil` der auswertung.json ('kein Unterschied belegt')
    kennt keine Aequivalenzpruefung und wird deshalb nicht verwendet (REVIEW-v2-A MUSS 9)."""
    if d + 2 * se < 0:
        return "b"
    if d - 2 * se > 0:
        return "w"
    if abs(d) + 2 * se < marge:
        return "e"
    return "g"


def vz(x, n):
    """Zahl mit Vorzeichen; eine auf n Stellen angezeigte Null traegt kein Vorzeichen (Endpruefung N, O2)."""
    s = f"{x:+.{n}f}"
    return s.lstrip("+-") if float(s) == 0 else s


BUCHSTABE_WORT = {"b": "better", "w": "worse", "e": "equivalent", "g": "grey zone"}


def pm(m, se, n=4):
    return f"${vz(m, n)} \\pm {se:.{n}f}$"


def stellen(paare, n=4):
    """n Nachkommastellen, ausser ein Wert oder SE der Zeile wuerde als 0.0000 erscheinen: dann n+1 (O2)."""
    return n + 1 if any(round(abs(m), n) == 0 or round(se, n) == 0 for m, se in paare) else n


# O1: p-Spalten ohne Blocksatz (Wortabstaende); braucht \usepackage{array}
RR = ">{\\raggedright\\arraybackslash}p"


def tex(s: str) -> str:
    return (s.replace("%", "\\%").replace("_", "\\_").replace("&", "\\&").replace("≤", "$\\le$").replace("≥", "$\\ge$")
            .replace("→", "$\\to$ ").replace("−", "$-$").replace("±", "$\\pm$").replace("κ̄", "$\\bar\\kappa$")
            .replace("κ", "$\\kappa$").replace("²", "$^2$").replace("∈", "$\\in$").replace("·", "$\\cdot$")
            .replace("Σ", "$\\Sigma$").replace("×", "$\\times$").replace("θ", "$\\theta$").replace("λ", "$\\lambda$")
            .replace("#", "\\#").replace("–", "--"))


Q = {
    "P2": ROOT / "modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json",
    "P1": ROOT / "modell/ergebnisse/cv_A_S1-S2-S3-S30/auswertung.json",
    "TAFEL": mv2("konfirmation/hypothesen_tafel.json"),
    "LIGA_VGL": mv2("liga/ergebnisse/vergleich_gepaart.csv"),
    "LIGA_RANG": mv2("liga/ergebnisse/rangfolge.csv"),
    "LIGA_META": mv2("liga/ergebnisse/meta.json"),
    "LIGA_JSON": mv2("liga/ergebnisse/liga_vergleich.json"),
    "BEOB": DATEN / "beobachtung_discovery.json",
    "DEX": DATEN / "D_exakt.json",
    "VERLUST": DATEN / "verlust.json",
    "AKQ": DATEN / "akquise_pilot_tabelle.json",
    "HYP": DATEN / "hyperparameter_je_falte_roh.json",
    "STATE": (ROOT / "modell/paket/state_v2core.json") if _REPO else (ROOT / "modell/paket/state_v2core.json"),
}
# R2 (Endpruefung Runde 2, P1): ALC- und Budget-Zellen aus den vollen Werten (liga_vergleich.json, 8 Stellen) einmal runden;
# die auf 5 Stellen gespeicherten Werte der auswertung.json (alc_paare, brier_je_budget) und rangfolge.csv fuehrten zu Doppelrundung
# (S1 BB 0.21315 -> 0.2132 statt 0.2131; S3 BB B15 0.19465 -> 0.1946 statt 0.1947).
LIGA_NAME = {"hier_item": None, "hier_kal": "v1_ohne_itemstufe"}  # Schluessel der auswertung.json -> Schluessel in liga_vergleich.json


def liga_voll(L, S, pred, stufe):
    """Voller Mittelwert (ALC oder Brier bei Budget `stufe` = 'alc' | 'B<b>') von `pred` (Schluessel der auswertung.json bzw. der Liga)."""
    if pred == "hier_item" or pred == "v1_hier_item":
        return float(feld(L, "regime", S, "v1_hier_item", stufe, "mittel"))
    return float(feld(L, "regime", S, "familien", LIGA_NAME.get(pred) or pred, "niveau", stufe, "mittel"))


def liga_alc(L, rang, m, S):
    """ALC der Liga-Zeile m im Regime S aus dem vollen Wert; fail-closed gegen die auf 5 Stellen gespeicherte rangfolge.csv."""
    v = liga_voll(L, S, m, "alc")
    alt = float(next(r for r in rang if r["praediktor"] == m)[S])
    if abs(v - alt) > 0.5e-5 + 1e-12:
        raise Eingabe(f"liga_vergleich.json {S}/{m}/alc = {v} weicht von rangfolge.csv ({alt}) ab")
    return v


def liga_geprueft(L, p2, S, pred, stufe):
    """Voller Wert; fail-closed: muss mit dem auf 5 Stellen gespeicherten Wert der auswertung.json uebereinstimmen (|Diff| <= 0.5e-5)."""
    v = liga_voll(L, S, pred, stufe)
    t = feld(p2, "tabelle_alle", S, pred)
    alt = float(t["alc_paare"] if stufe == "alc" else t["brier_je_budget"][stufe])
    if abs(v - alt) > 0.5e-5 + 1e-12:
        raise Eingabe(f"liga_vergleich.json {S}/{pred}/{stufe} = {v} weicht von auswertung.json ({alt}) ab")
    return v


KOPF = "% erzeugt von tabellen_v2.py aus JSON/CSV — nicht von Hand aendern\n"


def schreibe(aus: Path, name: str, inhalt: str):
    (aus / f"{name}.tex").write_text(KOPF + inhalt, encoding="utf-8")
    print("ok", name)


# ================================================================ Tab. 1 Hauptergebnis je Regime
def tab1(aus):
    p2 = lade_json(Q["P2"])
    L = lade_json(Q["LIGA_JSON"])
    tafel = lade_json(Q["TAFEL"])
    h1 = next(h for h in tafel["hypothesen"] if h["id"] == "H1")
    konfA = feld(h1, "teile", "A")
    konfB = feld(h1, "teile", "B")
    if h1["verdict"] != "passed":
        raise Eingabe(f"H1 verdict {h1['verdict']} – Tab. 1 setzt eine ausgewertete Konfirmation voraus")

    def konf(k, S):
        if S not in k:
            return "---"
        return f"{pm(k[S]['d'], k[S]['se'])} {u(k[S]['verdict'])[:1]}"

    zeilen = []
    for S, bez in (("S1", "S1 (1 subject/benchmark)"), ("S2", "S2"), ("S3", "S3"), ("S30", "S30 (limit)"),
                   ("kompakt10", "compact10 (hypothetical)")):
        em, bb, hk, hi = (liga_geprueft(L, p2, S, p, "alc") for p in ("empirischer_mittelwert", "beta_binomial", "hier_kal", "hier_item"))
        vb = vergleich(p2, "hier_item", "beta_binomial", S)
        ve = vergleich(p2, "hier_item", "empirischer_mittelwert", S)
        zeilen.append(f"{bez} & {em:.4f} & {bb:.4f} & {hk:.4f} & {hi:.4f} & {pm(vb['mittel'], vb['se'])} {buchstabe(vb['mittel'], vb['se'])} & "
                      f"{pm(ve['mittel'], ve['se'])} & {konf(konfA, S)} & {konf(konfB, S)} \\\\")
    n_p = feld(p2, "tabelle_alle", "S1", "hier_item", "n_paare")
    n_b = feld(p2, "tabelle_alle", "S1", "hier_item", "n_benchmarks")
    body = "\n".join(zeilen)
    inhalt = f"""\\begin{{table}}[t]
\\centering\\footnotesize
\\caption{{\\raggedright Main result per regime. Columns 2--7: \\textbf{{discovery}} (Design A, seeds 0--2, 10 benchmark folds, {n_p:,} test pairs, {n_b} benchmarks;
paired differences $\\pm$ cluster-robust SE over benchmarks; letters = verdict by the rule of Section 5: b better, w worse, e equivalent, g grey zone).
Last two columns: \\textbf{{confirmatory}} runs (seeds 200--202, fold seed 200; H1 of Table~\\ref{{tab:hyp}}), Design A (benchmark-cold, all
regimes) and Design B (benchmark- and subject-cold, S1 and S3). ``ours'' = the submitted predictor; discovery numbers were computed along the v1
path, which differs from the submitted v2.0-core only in the Platt stages 3 and 7 (Appendix~\\ref{{app:prereg}}). Sources: \\texttt{{modell/ergebnisse/cv\\_A\\_p2\\_S1-S2-S3-S30-kompakt10/auswertung.json}},
\\texttt{{liga/ergebnisse/liga\\_vergleich.json}} (ALC columns), \\texttt{{konfirmation/hypothesen\\_tafel.json}}.}}
\\label{{tab:main}}
\\setlength{{\\tabcolsep}}{{3pt}}
\\resizebox{{\\linewidth}}{{!}}{{%
\\begin{{tabular}}{{@{{}}lrrrrrrrr@{{}}}}
\\toprule
 & \\multicolumn{{4}}{{c}}{{Brier ALC (lower is better)}} & \\multicolumn{{2}}{{c}}{{ours $-$ baseline (discovery)}} & \\multicolumn{{2}}{{c}}{{ours $-$ BB (confirmatory)}} \\\\
\\cmidrule(lr){{2-5}}\\cmidrule(lr){{6-7}}\\cmidrule(lr){{8-9}}
regime & EM & BB & pair model & ours & vs BB & vs EM & Design A & Design B \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabular}}}}
\\end{{table}}
"""
    schreibe(aus, "tab1_hauptergebnis", inhalt)


# ================================================================ Tab. 2 Hypothesen-Tafel
def tab2(aus):
    tafel = lade_json(Q["TAFEL"])
    H = {h["id"]: h for h in tafel["hypothesen"]}
    kurz = {
        "H1": ("ALC(ours) $-$ ALC(BB), S1/S2/S3", "S2, S3 better; S1 equivalent or grey zone with power"),
        "H2a": ("relative error of the exact three-term formula vs the BB curve, $B = 1$--$31$, S1, Designs A and B", "all five budgets within $\\pm 10\\,\\%$ in both designs (expectation $\\le 3\\,\\%$)"),
        "H2b": ("(i) pooling steps S1$\\to$S30 at B1, B3; (ii) fixed-$\\kappa$ formula vs pooled model at S3/B1, S30/B1", "(i) 6/6 steps better; (ii) S3/B1 in [+10, +30]\\,\\%, S30/B1 in [+50, +110]\\,\\%"),
        "H2c": ("$\\bar\\kappa$ (BB prior strength per fold) vs $U/V_0$ (S1, B0)", "$|\\bar\\kappa - U/V_0| \\le 2\\,\\mathrm{SE}_{\\mathrm{boot}}$"),
        "H3": ("share of our excess at B0--B3 (cluster bootstrap)", "lower 95\\,\\% bound $> 0.70$ in S1, S2, S3"),
        "H4": ("ALC(ours) $-$ ALC(ours without subject identity), uncalibrated", "equivalent ($|d| + 2\\,$SE $< 0.001$) in S1, S2, S3"),
        "H5": ("mixing / stacking ours with BB; NPEB vs BB", "all nine equivalent, none better"),
        "H6": ("LOBO-$R^2$ of benchmark metadata on $R_b$ and logit $R_b$ (ridge)", "LOBO-$R^2 \\le 0.05$ for both targets"),
        "H7": ("L10 repeat-noise floor: median over benchmarks with $\\ge 100$ repeated cells", "median $\\ge 0.02$; two computation paths within 1\\,\\%"),
        "H8": ("item-stage gain at B31 vs number of evaluation items with foreign labels", "(i) S3 slope $<0$, $R^2 \\ge 0.8$; (ii) S30 saturation"),
    }
    ersetz = {"alle grey zone": "all grey zone", "alle equivalent, keiner better": "all equivalent, none better", "Merkmalsmenge": "feature set",
              "ein Rechenweg": "one computation path", "Sättigung": "saturation", "nicht verglichen": "not compared", "Differenz": "difference",
              "exakt": "exact", "Steigung": "slope", "/Item": "/item", "Benchmarks": "benchmarks", "Median": "median"}

    NACH_TEX = {"(R),": "($R_b$),", "R$^2$": "$R^2$", ">100": "$>$100"}

    def disc(h):
        s = h.get("discovery_value") or "---"
        if h["id"] == "H2c":
            # Rohtext aus der Tafel ("κ̄_ML = ..., U/V0 = ..., Differenz ..., SE_boot ...") als gesetzte Mathematik (Endpruefung M4).
            # Schaetzer laut Tafel (estimand): kappa_ML - U/V0 (Endpruefung N1: Reihenfolge und Vorzeichen). Fail-closed:
            # die in der Tafel gedruckte Differenz muss der Differenz der gedruckten Werte entsprechen.
            m = re.fullmatch(r"κ̄_ML = ([\d.]+), U/V0 = ([\d.]+), Differenz ([+−-]?[\d.]+), SE_boot ([\d.]+)", s)
            if not m:
                raise Eingabe(f"H2c discovery_value hat ein unerwartetes Format: {s!r}")
            dif = f"{float(m.group(1)) - float(m.group(2)):+.3f}"
            if m.group(3).replace("−", "-") != dif:
                raise Eingabe(f"H2c discovery_value: Differenz {m.group(3)} != kappa - U/V0 = {dif} ({s!r})")
            return (f"$\\bar\\kappa_{{\\mathrm{{ML}}}} = {m.group(1)}$, $U/V_0 = {m.group(2)}$, difference ${dif}$, "
                    f"SE$_{{\\mathrm{{boot}}}}$ {m.group(4)}")
        for a, b in ersetz.items():
            s = s.replace(a, b)
        # Platz (Haupttext ≤ 7,5 S.): die Zahlenketten von H2b (i) und H5 stehen vollständig in hypothesen_tafel.json
        if h["id"] == "H2b" and s.startswith("(i) B1 "):
            s = "(i) 6/6 steps better (B1 0.0488→0.0272, B3 0.0327→0.0192 from S1 to S30);" + s[s.index("(ii)") - 1:]
        if h["id"] == "H5" and "— alle equivalent, keiner better" in (h.get("discovery_value") or ""):
            s = "nine comparisons, all equivalent, none better (|d| ≤ 0.00030)"
        # nach tex(): "_" im Mathe-Text wuerde dort zu "\\_" (Endpruefung M4, H6: "(R)," -> "($R_b$),")
        out = tex(s)
        for a, b in NACH_TEX.items():
            out = out.replace(a, b)
        out = re.sub(r"\|d\| \$\\le\$ ([\d.]+)", r"$|d| \\le \1$", out)
        return out

    def rel5(r):
        return "$" + " / ".join(f"{{{100 * r[b]:+.1f}}}" for b in ("1", "3", "7", "15", "31")) + "\\,\\%$"

    def konf(h):
        hid = h["id"]
        if h["verdict"] == "not_evaluated":
            return "not evaluated"
        if hid == "H1":
            A, B = feld(h, "teile", "A"), feld(h, "teile", "B")
            return ("A: " + "; ".join(f"{S} {pm(A[S]['d'], A[S]['se'])} {u(A[S]['verdict'])}" for S in ("S1", "S2", "S3"))
                    + f" (S30 {pm(A['S30']['d'], A['S30']['se'])}); B: "
                    + "; ".join(f"{S} {pm(B[S]['d'], B[S]['se'])} {u(B[S]['verdict'])}" for S in ("S1", "S3")))
        if hid == "H2a":
            out = []
            for dsg in ("A", "B"):
                s = feld(h, "teile", dsg, "S1")
                out.append(f"{dsg}: {rel5(s['rel_fehler_exakt'])}, max {100 * s['max_abs_rel_fehler_exakt']:.1f}\\,\\% "
                           f"(within 10\\,\\%: {'yes' if s['alle_innerhalb_10_prozent'] else 'no'}; within 3\\,\\%: {'yes' if s['alle_innerhalb_3_prozent'] else 'no'})")
            return "; ".join(out)
        if hid == "H2b":
            v = h["value"]
            return (f"(i) {v['i_schritte_better']}/6 steps better; (ii) S3/B1 ${100 * v['ii_S3_B1']:+.1f}\\,\\%$, "
                    f"S30/B1 ${100 * v['ii_S30_B1']:+.1f}\\,\\%$")
        if hid == "H2c":
            v = h["value"]
            return (f"$\\bar\\kappa$ {v['kappa_ML']:.3f}, $U/V_0$ {v['U_durch_V0']:.3f}, difference {v['differenz']:+.3f}, SE$_{{\\mathrm{{boot}}}}$ {h['se']:.3f} "
                    "($\\bar\\kappa$ fitted by moments, as in discovery; Appendix B, deviation 3)")
        if hid == "H3":
            v, ci = h["value"], h["ci95"]
            return "; ".join(f"{S} {v[S]:.3f} [{ci[S][0]:.3f}, {ci[S][1]:.3f}]" for S in ("S1", "S2", "S3")) + f"; S30 {v['S30']:.3f} (reported)"
        if hid == "H4":
            v, se = h["value"], h["se"]
            return "; ".join(f"{S} {pm(v[S], se[S])} {u(feld(h, 'teile', 'A', S, 'verdict'))}" for S in ("S1", "S2", "S3")) + " (none equivalent)"
        if hid == "H5":
            v, se = h["value"], h["se"]
            t = feld(h, "teile")
            mx = max(abs(x) for S in ("S1", "S2", "S3") for x in v[S].values())
            mxse = max(se[S][k] for S in ("S1", "S2", "S3") for k in se[S])
            return (f"{t['n_equivalent_von_9']} of 9 equivalent, {t['n_better_von_9']} better; $|d| \\le {mx:.5f}$, SE $\\le {mxse:.5f}$ "
                    f"(largest: (b) stacking S2/S3 ${v['S3']['b_stack_hk_bb_minus_hk']:+.5f}$; nine values in \\texttt{{hypothesen\\_tafel.json}})")
        if hid == "H6":
            v = h["value"]
            return f"LOBO-$R^2$ ${v['R']:+.3f}$ ($R_b$), ${v['logit_R']:+.3f}$ (logit); feature set B"
        if hid == "H7":
            v = h["value"]
            return f"median {v['median']:.4f}, IQR {v['iqr'][0]:.3f}--{v['iqr'][1]:.3f}, {v['n_benchmarks']} benchmarks; second path median {v['zweitweg_median']:.4f}"
        if hid == "H8":
            v, ci = h["value"], h["ci95"]["S3_paar_steigung"]
            k = v["S30_klassen"]
            return (f"(i) S3 WLS slope ${v['S3_wls_steigung']:+.5f}$/item, $R^2$ {v['S3_r2']:.2f}; pair slope ${v['S3_paar_steigung']:+.5f}$ "
                    f"[${ci[0]:+.5f}$, ${ci[1]:+.5f}$]; (ii) S30: 21--50 ${k['21-50']:+.4f}$, 51--100 ${k['51-100']:+.4f}$, $>$100 ${k['>100']:+.4f}$ (saturation)")
        raise Eingabe(f"Tab. 2: keine Darstellung für {hid}")

    zeilen = []
    for hid in ("H1", "H2a", "H2b", "H2c", "H3", "H4", "H5", "H6", "H7", "H8"):
        h = H[hid]
        est, regel = kurz[hid]
        verdict = u(h["verdict"])
        if verdict == "failed":
            verdict = "\\textbf{FAILED}"
        if hid == "H2a" and verdict == "passed":
            verdict = "passed$^{*}$"  # * = Erwartung <= 3 % bei B31 verfehlt (Zelle 'within 3 %: no')
        zeilen.append(f"\\textbf{{{hid}}} {est} & {regel} & {disc(h)} & {konf(h)} & {verdict} \\\\")
    z = tafel["zusammenfassung"]
    ne = z.get("not_evaluated", 0)
    body = "\n".join(zeilen)
    inhalt = f"""\\begin{{table}}[t]
\\centering\\scriptsize
\\caption{{\\raggedright Hypothesis table as it fell (pre-registration \\texttt{{prereg/PRAEREGISTRIERUNG-v2.md}}, sha256 e5fd821f\\ldots, frozen 2026-10-20 20:26:04Z,
before the confirmatory runs). Discovery = seeds 0--2 (Design A); confirmatory = seeds 200--202, fold seed 200, Design A unless marked B.
Summary of verdicts: {z['passed']} passed, {z['failed']} failed{f', {ne} not evaluated' if ne else ''}. Verdicts are produced by code,
self-attested, no second judge; ``ours'' = the submitted predictor (confirmatory runs: nested Platt-stage choice per fold, Appendix~\\ref{{app:prereg}}).
$^{{*}}$rule met, stated expectation of $\\le 3\\,\\%$ missed at B31. Source: \\texttt{{konfirmation/hypothesen\\_tafel.json}}.}}
\\label{{tab:hyp}}
\\setlength{{\\tabcolsep}}{{2.5pt}}
\\begin{{tabular}}{{@{{}}{RR}{{2.3cm}}{RR}{{2.0cm}}{RR}{{3.3cm}}{RR}{{4.3cm}}{RR}{{1.2cm}}@{{}}}}
\\toprule
id, estimand & rule & discovery value & confirmatory value & verdict \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab2_hypothesen", inhalt)


# ================================================================ Tab. 3 Ablationen + Liga
def tab3(aus):
    p1 = lade_json(Q["P1"])
    p2 = lade_json(Q["P2"])
    tafel = lade_json(Q["TAFEL"])
    h4 = next(h for h in tafel["hypothesen"] if h["id"] == "H4")
    regime = ("S1", "S2", "S3", "S30")

    def zeile(bez, ausw, m, r, regs=regime):
        z = [bez]
        vs = {}
        for S in regs:
            try:
                vs[S] = vergleich(ausw, m, r, S)
            except Eingabe:
                vs[S] = None
        n = stellen([(v["mittel"], v["se"]) for v in vs.values() if v])  # O2: keine angezeigte Null mit Urteil
        for S in regs:
            v = vs[S]
            z.append("---" if v is None else f"{pm(v['mittel'], v['se'], n)} {buchstabe(v['mittel'], v['se'])}")
        return " & ".join(z) + " \\\\"

    abl = [
        zeile("item stage (ours $-$ pair model)", p2, "hier_item", "hier_kal"),
        zeile("Platt calibration per budget, v1 stage set (calibrated $-$ raw)", p1, "hier_kalibriert", "hier"),
        zeile("subject identity (raw $-$ without subject)", p1, "hier", "hier_ohne_subjekt"),
        zeile("subject identity, calibrated (cal.\\ $-$ cal.\\ without subject)", p1, "hier_kalibriert", "hier_ohne_subjekt"),
        zeile("benchmark slope $a_b$ (raw $-$ without slope)", p1, "hier", "hier_ohne_steigung"),
        zeile("item temperature 1 vs 0.5 (ours $-$ t0.5)", p2, "hier_item", "hier_item_t05"),
        zeile("item temperature 1 vs 2 (ours $-$ t2)", p2, "hier_item", "hier_item_t2"),
    ]
    h4v, h4se = h4["value"], h4["se"]
    abl.append("subject identity, \\textbf{confirmatory} Design A (H4, seeds 200--202) & " + " & ".join(
        f"{pm(h4v[S], h4se[S])} {u(feld(h4, 'teile', 'A', S, 'verdict'))[:1]}" for S in ("S1", "S2", "S3")) + " & --- \\\\")
    abl.append("stratum stage (item-metadata strata) & \\multicolumn{4}{l}{not evaluated: pilot on one fold only, full run aborted; not part of the submission} \\\\")
    abl.append("text-based item prior & \\multicolumn{4}{l}{not evaluated: prepared, no measurement; not part of the submission} \\\\")

    # Liga
    rang = lade_csv(Q["LIGA_RANG"])
    vgl = lade_csv(Q["LIGA_VGL"])
    meta = lade_json(Q["LIGA_META"])
    LJ = lade_json(Q["LIGA_JSON"])
    namen = {"v1_hier_item": "ours (v1 path)", "irt2pl": "IRT 2PL", "irt1pl": "IRT 1PL (Rasch)", "mf": "matrix factorisation (rank 1--8)",
             "stack": "stacking (2PL, MF, kNN, BB)", "knn": "kNN over subjects", "gb": "gradient boosting (20 features)",
             "beta_binomial": "beta-binomial", "v1_ohne_itemstufe": "ours without item stage", "empirischer_mittelwert": "empirical mean",
             "konstant_0.5": "constant 0.5"}
    liga = []
    for r in rang:
        m = r["praediktor"]
        if m == "v1_hier_item":
            liga.append(f"{namen[m]} & {liga_alc(LJ, rang, m, 'S1'):.4f} & {liga_alc(LJ, rang, m, 'S3'):.4f} & {float(r['rang_mittel']):.1f} & reference & reference \\\\")
            continue
        vv = []
        for S in ("S1", "S3"):
            v = next((x for x in vgl if x["modell"] == m and x["referenz"] == "v1_hier_item" and x["S"] == S), None)
            if v is None:
                raise Eingabe(f"Liga {m}/{S} fehlt")
            vv.append((float(v["mittel"]), float(v["se"])))
        nn = stellen(vv)  # O2
        cells = [f"{pm(d, s, nn)} {buchstabe(d, s)}" for d, s in vv]
        liga.append(f"{namen[m]} & {liga_alc(LJ, rang, m, 'S1'):.4f} & {liga_alc(LJ, rang, m, 'S3'):.4f} & {float(r['rang_mittel']):.1f} & {cells[0]} & {cells[1]} \\\\")
    falten = feld(meta, "falten")
    if len(falten) == 10:
        stand = f"all {len(falten)}/10 folds"
        kurzstand = f"{len(falten)}/10 folds"
    else:
        stand = f"\\textbf{{PRELIMINARY}}: {len(falten)}/10 folds {falten}"
        kurzstand = f"preliminary, {len(falten)}/10 folds"
    # D3 (Schlussrunde): kein \\resizebox. Liga (b) bleibt als Tab. 3 im Haupttext in \\scriptsize (7 pt), Ablationen (a) = Anhang D.
    inhalt_a = f"""\\begin{{table}}[H]
\\centering\\scriptsize
\\caption{{\\raggedright Ablations, discovery (Design A, seeds 0--2): paired ALC difference $\\pm$ cluster-robust SE; letter = verdict by the pre-stated rule
(b better, w worse, e equivalent, g grey zone; Section 5). The confirmatory H4 row (seeds 200--202) failed the equivalence hypothesis.
Rows with a difference or SE below 0.00005 are given to five decimals. Sources: \\texttt{{modell/ergebnisse/cv\\_A\\_S1-S2-S3-S30/auswertung.json}} (v1 stage set: Platt calibration, subject identity, benchmark slope),
\\texttt{{modell/ergebnisse/cv\\_A\\_p2\\_S1-S2-S3-S30-kompakt10/auswertung.json}} (item stage and item temperature),
\\texttt{{konfirmation/hypothesen\\_tafel.json}} (H4).}}
\\label{{tab:ablations}}
\\setlength{{\\tabcolsep}}{{2.5pt}}
\\begin{{tabular}}{{@{{}}{RR}{{2.7cm}}llll@{{}}}}
\\toprule
component (paired difference) & S1 & S2 & S3 & S30 \\\\
\\midrule
{chr(10).join(abl)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab3a_ablationen", inhalt_a)
    inhalt = f"""\\begin{{table}}[t]
\\centering\\scriptsize
\\caption{{\\raggedright Method league, {stand}, discovery seeds, test pairs capped at 30 per benchmark, hyperparameters chosen on the training benchmarks of each fold
(inner 75/25 split). ALC at one (S1) and three (S3) subjects per benchmark; $\\Delta$ = paired difference method $-$ ours (negative = method better; ``ours'' along the
v1 path, Appendix~\\ref{{app:prereg}}) $\\pm$ cluster-robust SE; letter = verdict by the pre-stated rule (b better, w worse, e equivalent, g grey zone; Section 5).
The ablations are in Table~\\ref{{tab:ablations}} (Appendix~\\ref{{app:tables}}). Sources: \\texttt{{liga/ergebnisse/liga\\_vergleich.json}} (ALC, full values rounded once), \\texttt{{liga/ergebnisse/rangfolge.csv}} (mean rank), \\texttt{{liga/ergebnisse/vergleich\\_gepaart.csv}} ($\\Delta$).}}
\\label{{tab:abl}}
\\setlength{{\\tabcolsep}}{{3pt}}
\\begin{{tabular}}{{@{{}}{RR}{{3.5cm}}lllll@{{}}}}
\\toprule
method & ALC S1 & ALC S3 & mean rank & $\\Delta$ vs ours, S1 & $\\Delta$ vs ours, S3 \\\\
\\midrule
{chr(10).join(liga)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab3_ablationen_liga", inhalt)


# ================================================================ Tab. 4 Protokoll-Sensitivitaet
def tab4(aus):
    p2 = lade_json(Q["P2"])
    LJ = lade_json(Q["LIGA_JSON"])
    beob = lade_json(Q["BEOB"])
    dex = lade_json(Q["DEX"])
    verl = lade_json(Q["VERLUST"])
    akq = lade_json(Q["AKQ"])
    U = float(feld(beob, "U_E"))
    V0 = float(feld(beob, "S1/beta_binomial", "(q-R)^2", "0"))
    kappa = float(feld(beob, "kappa_mittel_ueber_testpaare"))
    D = float(feld(dex, "D_exakt = E 4V/(N-1)"))
    F = float(feld(dex, "E[V/(NA-1)]"))
    kurve = alc_law.lernkurve(U, V0, kappa, D, F)
    terme = alc_law.alc(U, V0, kappa, D, F)

    def rel31(S):
        o = float(feld(beob, f"{S}/beta_binomial", "(q-R)^2", "31"))
        return 100 * (kurve[31] - o) / o

    zeilen = []
    # S
    for S in ("S1", "S2", "S3", "S30"):
        v = vergleich(p2, "hier_item", "beta_binomial", S)
        bb = liga_geprueft(LJ, p2, S, "beta_binomial", "alc")
        wirkung = ("one subject: nothing to pool; v1 gains at B0--B1 only" if S == "S1" else "pooling gain mainly at B1--B7")
        zeilen.append(f"subjects per benchmark & {S} & BB ALC {bb:.4f}; v1 $-$ BB {pm(v['mittel'], v['se'])} & {wirkung}; BB unchanged & P2, league \\\\")
    # Item-Ueberlappung
    for S in ("S3", "S30", "kompakt10"):
        v = vergleich(p2, "hier_item", "hier_kal", S)
        zeilen.append(f"item overlap (foreign labels on evaluation items) & {ANZEIGE.get(S, S)} & item-stage gain {pm(v['mittel'], v['se'])} & grows with overlap; compact10 is hypothetical & P2 \\\\")
    # Split-Term
    zeilen.append(f"50/50 item split (split term $D$) & all & $D = {D:.5f}$ (exact), {float(feld(dex, 'D_splitpy_formel = E 2 r(1-r)/N')):.5f} (first approximation); ALC contribution of the split term {terme['split']:.5f} & protocol quantity, not model error & D\\_exakt, alc\\_law \\\\")
    zeilen.append(f"items per pair $N$ (finite-population term $F$) & all & $F = {F:.5f}$; $N$ median {float(feld(dex, 'N_median')):.0f}, min {int(feld(dex, 'N_min'))} & second order in $1/N$ & D\\_exakt \\\\")
    # Identitaetskollision
    zeilen.append("identity collision (surplus labels from indistinguishable subjects of other pairs) & S1 / S3 / S30 & formula error for BB at B31: "
                  + " / ".join(f"${rel31(S):+.1f}\\,\\%$" for S in ("S1", "S3", "S30")) + " & clean only in S1; grows with S & obs., alc\\_law \\\\")
    # bekannt/unbekannt
    bk = feld(verl, "bekannt_hier_item")
    zeilen.append(f"subject known in training (name) vs unknown & S3, B0 / B3 & excess known {bk['True|0']['excess']:.4f} / {bk['True|3']['excess']:.4f}; unknown {bk['False|0']['excess']:.4f} / {bk['False|3']['excess']:.4f} & B0 identical; B3 gap mostly benchmark composition & loss \\\\")
    # Akquise
    vgl = feld(akq, "vergleiche_vs_zufall")
    for r in vgl:
        zeilen.append(f"label acquisition policy (coverage vs random), pilot & {ANZEIGE.get(r['S'], r['S'])} & {pm(r['mittel'], r['se'], 5)} {BUCHSTABE_WORT[buchstabe(r['mittel'], r['se'])]} ({r['n_paare']} pairs, {r['n_cluster']} clusters) & pilot only (fold 0); full run not evaluated (aborted) & P5 pilot \\\\")
    zeilen.append("split per item instead of per pair & --- & not evaluated (scenario aborted with the acquisition full run) & --- & P5 pilot \\\\")
    inhalt = f"""\\begin{{table}}[H]
\\centering\\scriptsize
\\caption{{\\raggedright Protocol sensitivity: what moves the error besides the model. Discovery (Design A, seeds 0--2) unless stated; paired differences
$\\pm$ cluster-robust SE. Formula rows use the three-term learning curve with moments from the S1 test pairs ($U={U:.4f}$, $V_0={V0:.4f}$,
$\\kappa={kappa:.2f}$, $D={D:.5f}$, $F={F:.5f}$; nothing fitted). Sources: P2 = \\texttt{{modell/ergebnisse/cv\\_A\\_p2\\_S1-S2-S3-S30-kompakt10/auswertung.json}};
league = \\texttt{{liga/ergebnisse/liga\\_vergleich.json}} (BB ALC, full value rounded once); D\\_exakt = \\texttt{{daten/D\\_exakt.json}}; obs.\\ = \\texttt{{daten/beobachtung\\_discovery.json}}; alc\\_law = \\texttt{{theorie/alc\\_law.py}};
loss = \\texttt{{daten/verlust.json}}; P5 pilot = \\texttt{{daten/akquise\\_pilot\\_tabelle.json}}; \\texttt{{daten/}} = \\texttt{{report/src/daten/}}.}}
\\label{{tab:protocol}}
\\setlength{{\\tabcolsep}}{{3pt}}
\\begin{{tabular}}{{@{{}}{RR}{{2.7cm}}{RR}{{1.2cm}}{RR}{{4.1cm}}{RR}{{2.7cm}}l@{{}}}}
\\toprule
protocol quantity & regime & effect (ALC unless stated) & reading & src \\\\
\\midrule
{chr(10).join(zeilen)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab4_protokoll", inhalt)


# ================================================================ Tab. 6/7 (Anhang D): vorher von Hand im tex, jetzt aus der Quelle (Endpruefung N, Klasse (b))
def tab6(aus):
    p2 = lade_json(Q["P2"])
    L = lade_json(Q["LIGA_JSON"])
    namen = (("hier_item", "ours"), ("beta_binomial", "\\BB"), ("empirischer_mittelwert", "\\EM"))
    zeilen = []
    for k, S in enumerate(("S1", "S2", "S3")):
        if k:
            zeilen.append("    \\midrule")
        for j, (key, bez) in enumerate(namen):
            werte = " & ".join(f"{liga_geprueft(L, p2, S, key, f'B{b}'):.4f}" for b in (0, 1, 3, 7, 15, 31))
            reg = f"$S={S[1:]}$" if j == 0 else ""
            zeilen.append(f"    {reg:<6}& {bez:<8} & {werte} \\\\")
    body = "\n".join(zeilen)
    inhalt = f"""\\begin{{table}}[H]
  \\caption{{\\raggedright Brier score per label budget, discovery set (Design A, seeds 0--2; same runs as Table~\\ref{{tab:main}}).
  Source: \\texttt{{modell/ergebnisse/cv\\_A\\_p2\\_S1-S2-S3-S30-kompakt10/auswertung.json}}, \\texttt{{tabelle\\_alle[S][pred].brier\\_je\\_budget}} (five decimals, cross-check only); cells are the full values in
  \\texttt{{liga/ergebnisse/liga\\_vergleich.json}} (\\texttt{{regime[S].familien[pred].niveau[B$b$].mittel}}), rounded once here.}}
  \\label{{tab:budgets}}
  \\centering\\small
  \\begin{{tabular}}{{llrrrrrr}}
    \\toprule
    Regime & Predictor & $B_0$ & $B_1$ & $B_3$ & $B_7$ & $B_{{15}}$ & $B_{{31}}$ \\\\
    \\midrule
{body}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab6_budgets", inhalt)


def tab7(aus):
    roh = lade_json(Q["HYP"])
    st = lade_json(Q["STATE"])
    spalten = ("mu_c", "lam", "tau_c2", "tau_l2", "tau_v2", "kappa", "s2_unk", "tau_i2")
    falten = feld(roh, "falten")
    if sorted(falten, key=int) != [str(i) for i in range(10)]:
        raise Eingabe(f"hyperparameter_je_falte_roh.json: Falten {sorted(falten)} != 0..9")
    zeilen = []
    for f in range(10):
        v = falten[str(f)]
        zeilen.append(f"    {f} & " + " & ".join(f"{v[k]:.3f}" for k in spalten) + f" & {int(v['n_namen'])} \\\\")
    h = feld(st, "hyp")
    sub = "    submitted & " + " & ".join(f"{h[k]:.3f}" for k in spalten) + f" & {len(feld(st, 'theta'))} \\\\"
    body = "\n".join(zeilen)
    inhalt = f"""\\begin{{table}}[H]
  \\caption{{\\raggedright Test-time hyperparameters per fold of Design A (discovery) and of the submitted state (trained on all
  benchmarks). $\\mu_c, \\tau_c^2$ and $\\lambda, \\tau_\\lambda^2$: mean and variance of the priors of $c_b$ and $a_b$ (Section~\\ref{{sec:method}});
  the pair deviation $v_{{sb}}$ has variance $s_s^2 = \\tau_v^2 + \\kappa V_s$ for a subject whose name is known from training ($V_s$ = uncertainty of
  its ability $m_s$; this $\\kappa$ is the coefficient of that term, unrelated to the prior strength $\\kappa$ of Eq.~\\ref{{eq:curve}}) and
  $s^2_{{\\mathrm{{unk}}}}$ for an unknown name; $\\tau_i^2$ = variance of the item offset; names = number of subject names with an ability estimate
  in the state. $\\tau_\\lambda^2$ and $\\kappa$ vary strongly between folds, i.e.\\ they are weakly identified.
  Sources: \\texttt{{daten/hyperparameter\\_je\\_falte\\_roh.json}} (full-precision \\texttt{{hyp}} entries of the ten fold states, rounded once here),
  \\texttt{{modell/paket/state\\_v2core.json}} (submitted row).}}
  \\label{{tab:hyper}}
  \\centering\\small
  \\begin{{tabular}}{{lrrrrrrrrr}}
    \\toprule
    Fold & $\\mu_c$ & $\\lambda$ & $\\tau_c^2$ & $\\tau_\\lambda^2$ & $\\tau_v^2$ & $\\kappa$ & $s^2_{{\\text{{unk}}}}$ &
      $\\tau_i^2$ & names \\\\
    \\midrule
{body}
    \\midrule
{sub}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    schreibe(aus, "tab7_hyper", inhalt)


ALLE = [tab1, tab2, tab3, tab4, tab6, tab7]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", default=str(HIER / "tabellen"))
    a = ap.parse_args(argv)
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    fehler = 0
    for f in ALLE:
        try:
            f(aus)
        except Exception as e:
            fehler += 1
            print(f"FEHLER {f.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
