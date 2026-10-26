"""plots_v2.py — Abbildungen des Bericht-v2 (PAIEC 2026) aus JSON/CSV, nichts wird gerechnet außer Mittelwerten/Formel.

Aufruf (aus bericht-v2/):  python3 -I plots_v2.py --aus abbildungen
Fail-closed: fehlende Datei / fehlendes Feld -> Ausnahme, Rueckgabecode != 0; kein Platzhalter aus dem Nichts.
Bekannt NICHT evaluierte Teile (Stratum, Text-Prior, Akquise-Volllauf, Item-Stufen-Zuverlaessigkeit, Konfirmation Design A)
werden ausdruecklich als "not evaluated" in die Abbildung geschrieben (BAUPLAN-V2 §2.3 P7 Abbruch-Regel).

Zahlen = discovery (Saaten 0-2, Design A, 10 Falten), so beschriftet. Konfirmation nur, wo P4 sie geliefert hat (Design B H1/H2a).
S3-Druckregel (2026-10-21): jede Abbildung wird in genau der Groesse erzeugt, in der sie im PDF steht
(figsize in Zoll = Einbaubreite/72; Volltextbreite 5,5 in = 396 pt; Faktor f -> 5,5*f in), OHNE bbox_inches="tight" und ohne
nachtraegliche Skalierung. Schrift im Druck: Achsen/Ticks >= 7 pt, Annotationen/Legenden >= 6,5 pt. Kein Quelltext in der
Grafik: Quellen stehen in abbildungen/quellen_abbildungen.tex (Anhang F). pruefe_abbildungen.py prueft das mechanisch.
Palette: dataviz-Referenzpalette, 4 Slots (blau, orange, aqua, gelb) adjacent validiert (validate_palette.js, light, PASS;
Kontrast-WARN aqua/gelb -> Legende + direkte Beschriftung + Tabellen im Anhang). Farbe folgt der Entitaet, Markerform ist
zweite Kodierung. Ein-Achsen-Regel: keine Doppelachsen.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.text  # noqa: F401
import matplotlib.ticker  # noqa: F401

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HIER = Path(__file__).resolve().parent            # bericht-v2/ (Arbeitsbaum) oder report/src/ (Repository)
DATEN = HIER / "daten"
# Zwei Layouts: Arbeitsbaum (bericht-v2/ neben modell/, ) oder Repository (report/src/ unter der Repo-Wurzel,
# wo {konfirmation,liga,theorie,kuratierung} als konfirmation/, liga/, theorie/, curation/ liegen).
ROOT = HIER.parent                                # paiec-stanford/
if not (ROOT / "modell-v2").is_dir() and (HIER.parent.parent / "modell").is_dir():
    ROOT = HIER.parent.parent
_REPO = not (ROOT / "modell-v2").is_dir()


def mv2(rel):
    """Pfad unter  im Arbeitsbaum bzw. an der Repo-Wurzel (kuratierung -> curation)."""
    return ROOT / rel.replace("kuratierung", "curation", 1) if _REPO else ROOT / "modell-v2" / rel


sys.path.insert(0, str(mv2("theorie")))
import alc_law  # noqa: E402  (Standardbibliothek, fail-closed)

# ---------------------------------------------------------------- Palette / Stil (dataviz-Referenz, light)
FLAECHE, TEXT1, TEXT2, MUTED, RASTER, ACHSE = "#ffffff", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLAU, ORANGE, AQUA, GELB = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
BLAU_RAMPE = ["#86b6ef", "#6da7ec", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]  # Schritte 250..650
SERIE = {  # Entitaet -> (Farbe, Marker, Beschriftung)
    "hier_item": (BLAU, "o", "v1 (ours)"),
    "hier_kal": (GELB, "D", "v1 pair model only"),
    "beta_binomial": (ORANGE, "s", "beta-binomial"),
    "empirischer_mittelwert": (AQUA, "^", "empirical mean"),
}
BUDGETS = [0, 1, 3, 7, 15, 31]
GEW = dict(zip(BUDGETS, (0.1, 0.2, 0.2, 0.2, 0.2, 0.1)))
X = [math.log2(1 + b) for b in BUDGETS]

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.8, "legend.title_fontsize": 6.8, "pdf.fonttype": 42,
    "figure.constrained_layout.use": False,
    "axes.edgecolor": ACHSE, "axes.labelcolor": TEXT2, "xtick.color": TEXT2, "ytick.color": TEXT2,
    "text.color": TEXT1, "figure.facecolor": FLAECHE, "axes.facecolor": FLAECHE, "savefig.facecolor": FLAECHE,
})


def stil(ax, raster_y=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_linewidth(0.7)
    ax.tick_params(length=2.5, width=0.6)
    if raster_y:
        ax.grid(True, axis="y", color=RASTER, linewidth=0.5)
    ax.set_axisbelow(True)


def log_klartext(achse, labels_minor=(2, 3, 4, 6)):
    """Logarithmische Achse mit Klartext-Beschriftung (1, 10, 100 / 0.02, 0.04): matplotlib setzt sonst 10^x per mathtext mit
    70 % der Schriftgroesse (Exponent 4,9 pt) -> im Druck zu klein (von pruefe_abbildungen.py gefunden)."""
    def maj(v, _):
        return f"{v:g}"

    def mino(v, _):
        if v <= 0:
            return ""
        lead = round(v / 10 ** math.floor(math.log10(v)))
        return f"{v:g}" if lead in labels_minor else ""
    achse.set_major_formatter(matplotlib.ticker.FuncFormatter(maj))
    achse.set_minor_formatter(matplotlib.ticker.FuncFormatter(mino))


def budget_achse(ax, label=True):
    ax.set_xticks(X)
    ax.set_xticklabels([str(b) for b in BUDGETS])
    if label:
        ax.set_xlabel("label budget per pair (log2(1+B) spacing)")


# ---------------------------------------------------------------- Laden (fail-closed)
class Eingabe(Exception):
    pass


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


def saaten_text(liste):
    """[0, 1, 2] -> '0–2' (zusammenhaengend), sonst '0, 2, 5'."""
    z = sorted(int(x) for x in liste)
    if len(z) > 2 and z == list(range(z[0], z[0] + len(z))):
        return f"{z[0]}–{z[-1]}"
    return ", ".join(str(x) for x in z)


def feld(d, *pfad):
    for k in pfad:
        if isinstance(d, list):
            d = d[int(k)]
        elif k in d:
            d = d[k]
        else:
            raise Eingabe(f"Feld fehlt: {'/'.join(map(str, pfad))} (bei {k!r})")
    return d


BUCHSTABE_WORT = {"b": "better", "w": "worse", "e": "equivalent", "g": "grey zone"}


def buchstabe(d: float, se: float, marge: float = 0.001) -> str:
    """Urteilsbuchstabe nach der praeregistrierten Regel (Bericht Abschnitt 5), wie in tabellen_v2.py: b better, w worse,
    e equivalent (|d|+2SE < marge), sonst g grey zone. Das Feld `urteil` der Pilot-Tabelle kennt keine Aequivalenzpruefung."""
    if d + 2 * se < 0:
        return "b"
    if d - 2 * se > 0:
        return "w"
    if abs(d) + 2 * se < marge:
        return "e"
    return "g"


def vergleich(ausw, modell, referenz, S, gew="paar"):
    for v in ausw["vergleiche"]:
        if v["modell"] == modell and v["referenz"] == referenz and v["S"] == S and v.get("gewichtung") == gew:
            return v
    raise Eingabe(f"Vergleich fehlt: {modell}-{referenz}/{S}/{gew}")


Q = {
    "P2": ROOT / "modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json",
    "P1": ROOT / "modell/ergebnisse/cv_A_S1-S2-S3-S30/auswertung.json",
    "ZUV": ROOT / "modell/ergebnisse/cv_A_p2/zuverlaessigkeit.csv",
    "ZUV_A": ROOT / "modell/ergebnisse/cv_A_p2/auswertung.json",
    "TAFEL": mv2("konfirmation/hypothesen_tafel.json"),
    "WDH": mv2("kuratierung/wiederholung_b.json"),
    "NF": mv2("kuratierung/noise_floor_by_benchmark.csv"),
    "FALL": mv2("kuratierung/fallbeispiele.json"),
    "LIGA_VGL": mv2("liga/ergebnisse/vergleich_gepaart.csv"),
    "LIGA_META": mv2("liga/ergebnisse/meta.json"),
    "E3": DATEN / "e3.json",
    "BEOB": DATEN / "beobachtung_discovery.json",
    "DEX": DATEN / "D_exakt.json",
    "VERLUST": DATEN / "verlust.json",
    "LEITER": DATEN / "leiter.json",
    "LEITER2": DATEN / "leiter_ergaenzung.json",
    "JEBM": DATEN / "je_benchmark.csv",
    "AKQ": DATEN / "akquise_pilot_tabelle.json",
}


def momente():
    """U, V0(BB), kappa, D, F der discovery-Testpaare (Anhang A §A.2; nichts gefittet)."""
    beob = lade_json(Q["BEOB"])
    dex = lade_json(Q["DEX"])
    U = float(feld(beob, "U_E"))
    V0 = float(feld(beob, "S1/beta_binomial", "(q-R)^2", "0"))
    kappa = float(feld(beob, "kappa_mittel_ueber_testpaare"))
    D = float(feld(dex, "D_exakt = E 4V/(N-1)"))
    F = float(feld(dex, "E[V/(NA-1)]"))
    return U, V0, kappa, D, F, beob


def urteil(hid):
    """Urteil der Hypothese hid aus konfirmation/hypothesen_tafel.json (passed/failed/not evaluated), nie hart codiert."""
    h = next((h for h in lade_json(Q["TAFEL"])["hypothesen"] if h["id"] == hid), None)
    if h is None:
        raise Eingabe(f"Hypothese {hid} fehlt in der Tafel")
    v = h.get("verdict") or h.get("urteil")
    if not v:
        raise Eingabe(f"Hypothese {hid}: kein Urteil in der Tafel")
    return str(v).replace("_", " ")


QUELLEN: dict = {}
BREITE_IN = 5.5          # Textbreite des NeurIPS-Stils (neurips_2026.sty: textwidth=5.5in) = \\linewidth


def vz(x, n):
    """Zahl mit Vorzeichen; wuerde sie auf n Stellen als Null erscheinen, n+1 Stellen und eine echte Null ohne Vorzeichen (Endpruefung N, O2)."""
    s = f"{x:+.{n}f}"
    if float(s) == 0:
        s = f"{x:+.{n + 1}f}"
        if float(s) == 0:
            s = s.lstrip("+-")
    return s


def quelle(fig, text):
    """Quellenangabe NICHT in die Grafik (S3): wird in abbildungen/quellen_abbildungen.tex (Anhang F) geschrieben."""
    fig._quelle = text


def pruefe_rand(fig, name):
    """Fail-closed: kein sichtbarer Text darf ueber den Figurenrand hinausragen (ohne bbox tight wuerde er abgeschnitten)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    w, h = fig.bbox.width, fig.bbox.height
    # Tick-Beschriftungen ausserhalb des Achsenbereichs werden nicht gezeichnet -> nicht pruefen
    stumm = set()
    for ax in fig.axes:
        for achse in (ax.xaxis, ax.yaxis):
            sichtbar = {id(tk.label1) for tk in achse._update_ticks()} | {id(tk.label2) for tk in achse._update_ticks()}
            for tk in achse.get_major_ticks() + achse.get_minor_ticks():
                for lab in (tk.label1, tk.label2):
                    if id(lab) not in sichtbar:
                        stumm.add(id(lab))
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text().strip() or id(t) in stumm:
            continue
        bb = t.get_window_extent(r)
        if bb.width < 1 or bb.height < 1:
            continue
        if bb.x0 < -0.5 or bb.y0 < -0.5 or bb.x1 > w + 0.5 or bb.y1 > h + 0.5:
            raise Eingabe(f"{name}: Text ragt ueber den Rand ({t.get_text()[:40]!r}: x {bb.x0:.1f}..{bb.x1:.1f} von {w:.1f}, "
                          f"y {bb.y0:.1f}..{bb.y1:.1f} von {h:.1f} px)")


def speichern(fig, aus: Path, name: str):
    pruefe_rand(fig, name)
    # exakte Figurengroesse = Einbaugroesse: KEIN bbox_inches="tight"
    fig.savefig(aus / f"{name}.pdf")
    (aus / "preview").mkdir(exist_ok=True)
    fig.savefig(aus / "preview" / f"{name}.png", dpi=170)
    QUELLEN[name] = getattr(fig, "_quelle", "")
    plt.close(fig)
    print("ok", name, f"{fig.get_figwidth():.3f} x {fig.get_figheight():.3f} in")


def fmt_pm(m, se):
    return f"{m:+.4f} ± {se:.4f}"


# ================================================================ Abb. 1 Lernkurven S1/S2/S3 + Schranken + Formel
def abb1(aus):
    p2 = lade_json(Q["P2"])
    U, V0, kappa, D, F, _ = momente()
    kurve = alc_law.lernkurve(U, V0, kappa, D, F)
    L8 = next(r["Brier_B0"] for r in lade_json(Q["LEITER"])["leiter_B0"] if r["Stufe"].startswith("L8"))
    wdh = lade_json(Q["WDH"])
    q = feld(wdh, "schranke_je_bm_quantile")
    l10_med, l10_lo, l10_hi = float(q["0.5"]), float(q["0.25"]), float(q["0.75"])
    n_bm_l10 = feld(wdh, "benchmarks_mit_>=100_wdh_zellen")

    fig, axs = plt.subplots(1, 3, figsize=(BREITE_IN, 2.4), sharey=True)
    for ax, S in zip(axs, ("S1", "S2", "S3")):
        stil(ax)
        t = feld(p2, "tabelle_alle", S)
        # Schranken
        ax.axhspan(l10_lo, l10_hi, color=RASTER, alpha=0.9, lw=0, zorder=0)
        ax.axhline(l10_med, color=MUTED, lw=0.7, zorder=1)
        ax.axhline(L8, color=MUTED, lw=0.7, ls=(0, (1.5, 1.5)), zorder=1)
        ax.axhline(U, color=TEXT2, lw=0.8, ls=(0, (4, 2)), zorder=1)
        ax.axhline(U + D, color=TEXT2, lw=0.5, zorder=1)
        # Formel (Entitaet BB -> orange, gestrichelt duenn)
        ax.plot(X, [U + kurve[b] for b in BUDGETS], color=ORANGE, lw=1.0, ls=(0, (3, 2)), zorder=2)
        for pr in ("empirischer_mittelwert", "beta_binomial", "hier_kal", "hier_item"):
            farbe, marker, _ = SERIE[pr]
            y = [t[pr]["brier_je_budget"][f"B{b}"] for b in BUDGETS]
            ax.plot(X, y, color=farbe, lw=1.6, marker=marker, ms=4.2, mec=FLAECHE, mew=0.9, zorder=3,
                    clip_on=True)
        em_b1 = t["empirischer_mittelwert"]["brier_je_budget"]["B1"]
        # EM bei B=1 liegt ausserhalb der Achse: Hinweis rechts oben, wo keine Kurve laeuft
        ax.text(X[3] + 0.05, 0.266, f"EM at B=1:\n{em_b1:.3f} ↑", fontsize=6.5, color=TEXT2, ha="left", va="top", linespacing=1.1)
        v = vergleich(p2, "hier_item", "beta_binomial", S)
        ax.set_title(f"{S}: v1−BB {v['mittel']:+.4f}±{v['se']:.4f}".replace("-0", "−0"), loc="left", color=TEXT1, pad=3, fontsize=7)
        ax.set_ylim(0.0, 0.27)
        ax.set_xlim(-0.2, X[-1] + 0.25)
        budget_achse(ax, label=(S == "S2"))
    axs[0].set_ylabel("Brier score (pairs weighted equally)")
    # Beschriftung der Schranken im ersten Panel: kurze Direktlabels (Definition in der Caption)
    ax = axs[0]
    xr = X[-1] + 0.2
    ax.text(xr, U - 0.005, f"U {U:.4f}", fontsize=6.5, color=TEXT2, ha="right", va="top")
    ax.text(xr, L8 + 0.004, f"L8 {L8:.4f}", fontsize=6.5, color=TEXT2, ha="right", va="bottom")
    ax.text(xr, l10_hi + 0.004, f"L10 {l10_med:.3f} (band: IQR)", fontsize=6.5, color=TEXT2, ha="right", va="bottom")
    griffe = [Line2D([], [], color=SERIE[p][0], marker=SERIE[p][1], lw=1.6, ms=4, mec=FLAECHE, label=SERIE[p][2])
              for p in ("hier_item", "hier_kal", "beta_binomial", "empirischer_mittelwert")]
    griffe.append(Line2D([], [], color=ORANGE, lw=1.0, ls=(0, (3, 2)), label="three-term formula for BB"))
    griffe.append(Line2D([], [], color=TEXT2, lw=0.8, ls=(0, (4, 2)), label="floors (U, U+D, L8, L10)"))
    fig.legend(handles=griffe, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0), columnspacing=1.2,
               handlelength=2.0, fontsize=6.8)
    quelle(fig, "modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json (tabelle_alle, vergleiche); floors: "
                "daten/beobachtung_discovery.json (U_E), daten/D_exakt.json, daten/leiter.json (L8), kuratierung/wiederholung_b.json (L10); "
                "formula: theorie/alc_law.py.")
    fig.tight_layout(w_pad=0.6, rect=(0, 0, 1, 0.85))
    speichern(fig, aus, "fig1_lernkurven")


# ================================================================ Abb. 2 Zerlegungs-Wasserfall
def abb2(aus):
    v = lade_json(Q["VERLUST"])
    fig, axs = plt.subplots(1, 2, figsize=(BREITE_IN, 2.7), sharey=True)
    for ax, S in zip(axs, ("S1", "S3")):
        stil(ax)
        a = feld(v, f"alc_anteil_{S}")
        floor, alc = float(a["floor_alc"]), float(a["alc"])
        schritte = []
        for b in BUDGETS:
            z = feld(v, "budget_hier_item", f"{S}|{b}")
            schritte.append((f"B{b}", GEW[b] * float(z["sq"])))
        itemg = sum(GEW[b] * float(feld(v, "budget_hier_item", f"{S}|{b}")["itemg"]) for b in BUDGETS)
        # Konsistenz: floor + Summe(sq) + itemg == alc (fail-closed auf 1e-6)
        if abs(floor + sum(s for _, s in schritte) + itemg - alc) > 1e-6:
            raise Eingabe(f"Zerlegung inkonsistent in {S}")
        xs, labels, lauf = [], [], floor
        ax.bar(0, floor, width=0.7, color=RASTER, edgecolor=FLAECHE, lw=1)
        ax.text(0, 0.1757, f"{floor:.4f}", ha="center", va="bottom", fontsize=6.5, color=TEXT1, rotation=90)
        labels.append("floor\nU")
        for i, ((name, s), farbe) in enumerate(zip(schritte, BLAU_RAMPE), start=1):
            ax.bar(i, s, bottom=lauf, width=0.7, color=farbe, edgecolor=FLAECHE, lw=1)
            ax.text(i, lauf + s + 0.0004, f"+{s:.4f}", ha="center", va="bottom", fontsize=6.5, color=TEXT1, rotation=90)
            lauf += s
            labels.append(f"{name}\n{100 * a['anteil'][str(BUDGETS[i - 1])]:.0f}%")
        i += 1
        ax.bar(i, itemg, bottom=lauf, width=0.7, color=AQUA, edgecolor=FLAECHE, lw=1)
        ax.text(i, lauf + itemg - 0.0004, vz(itemg, 4).replace("-", "−"), ha="center", va="top", fontsize=6.5, color=TEXT1, rotation=90)
        lauf += itemg
        labels.append("item\nstage")
        i += 1
        ax.bar(i, alc, width=0.7, color=BLAU, edgecolor=FLAECHE, lw=1)
        ax.text(i, alc + 0.0004, f"{alc:.4f}", ha="center", va="bottom", fontsize=6.5, color=TEXT1, fontweight="bold", rotation=90)
        labels.append("v1\nALC")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylim(0.175, 0.218)
        anteil_b0b3 = sum(a["anteil"][k] for k in ("0", "1", "3"))
        ax.set_title(f"{S}: excess over floor {a['excess_alc']:.4f},\n{100 * anteil_b0b3:.1f} % of it at B0–B3", loc="left", pad=3)
    axs[0].set_ylabel("Brier ALC (pairs weighted equally)")
    quelle(fig, "daten/verlust.json (alc_anteil_S1/S3, budget_hier_item: sq, itemg, floor); weights 0.1/0.2/0.2/0.2/0.2/0.1.")
    fig.tight_layout(w_pad=0.8)
    speichern(fig, aus, "fig2_zerlegung")


# ================================================================ Abb. 3 Formel vs gemessen
def abb3(aus):
    U, V0, kappa, D, F, beob = momente()
    tafel = lade_json(Q["TAFEL"])
    h2a = next(h for h in tafel["hypothesen"] if h["id"] == "H2a")
    konfB = feld(h2a, "teile", "B", "S1", "rel_fehler_exakt")
    konfB_2t = feld(h2a, "teile", "B", "S1", "rel_fehler_zweiterm")
    konfA = feld(h2a, "teile", "A", "S1", "rel_fehler_exakt")  # Schlussrunde: Design A konfirmatorisch ausgewertet
    verdict_A = feld(h2a, "teile", "A", "verdict_dieses_design")  # Tafel-Schema v2 (S1: neue Tafel)
    verdict_B = feld(h2a, "teile", "B", "verdict_dieses_design")
    bs = [1, 3, 7, 15, 31]
    xs = [math.log2(1 + b) for b in bs]

    def rel(formel, beobachtet):
        return [100 * (formel[b] - beobachtet[str(b)]) / beobachtet[str(b)] for b in bs]

    k_ex = alc_law.lernkurve(U, V0, kappa, D, F)
    k_2t = alc_law.lernkurve(U, V0, kappa, 0.0, 0.0)
    bbS1 = feld(beob, "S1/beta_binomial", "(q-R)^2")
    fig, (a, b) = plt.subplots(1, 2, figsize=(BREITE_IN, 3.05))
    # (a) BB: Formel-Fehler
    stil(a)
    a.axhspan(-10, 10, color=RASTER, lw=0, zorder=0)
    a.axhline(0, color=ACHSE, lw=0.7)
    for yy in (-3, 3):
        a.axhline(yy, color=MUTED, lw=0.5, ls=(0, (1.5, 1.5)))
    a.plot(xs, rel(k_ex, bbS1), color=BLAU, marker="o", ms=4.5, lw=1.4, mec=FLAECHE, label="exact form, A S1 (discovery)")
    a.plot(xs, [100 * konfA[str(bb)] for bb in bs], color=ORANGE, marker="D", ms=4.0, lw=1.4, mec=FLAECHE, ls=(0, (4, 1.5)),
           label="exact form, A S1 (confirmatory)")
    a.plot(xs, [100 * konfB[str(bb)] for bb in bs], color=ORANGE, marker="s", ms=4.5, lw=1.4, mec=FLAECHE,
           label="exact form, B S1 (confirmatory)")
    a.plot(xs, rel(k_2t, bbS1), color=MUTED, marker="x", ms=4.5, lw=1.0, ls=(0, (2, 2)),
           label="two-term form, A S1")
    a.plot(xs, [100 * konfB_2t[str(bb)] for bb in bs], color=MUTED, marker="x", ms=4.5, lw=1.0, ls=(0, (2, 2)), alpha=0.6,
           label="two-term form, B S1")
    for S, mk in (("S3", "v"), ("S30", "^")):
        bbS = feld(beob, f"{S}/beta_binomial", "(q-R)^2")
        a.plot(xs, rel(k_ex, bbS), color=AQUA, marker=mk, ms=4.2, lw=0.9, mfc=FLAECHE, mec=AQUA, mew=1.0,
               label=f"exact form, A {S} (sensitivity)")
    a.set_xticks(xs)
    a.set_xticklabels([str(x) for x in bs])
    a.set_xlabel("label budget B")
    a.set_ylabel("(formula − observed) / observed, %", fontsize=6.8)
    a.set_ylim(-27, 12)
    a.set_title(f"(a) beta-binomial curve, formula vs observed:\ngrey band ±10 % (H2a rule), dotted ±3 %;\n"
                f"H2a confirmatory: A {verdict_A.replace('_', ' ')}, B {verdict_B.replace('_', ' ')}", loc="left", pad=3, fontsize=7)
    hl, lb = a.get_legend_handles_labels()
    fig.legend(hl, lb, loc="lower center", ncol=3, frameon=False, fontsize=6.8, handlelength=1.8, columnspacing=1.0,
               labelspacing=0.3, bbox_to_anchor=(0.5, 0.0))
    # (b) festes-kappa-Formel vs gepooltes v1 (hier_item)
    stil(b)
    b.axhline(0, color=ACHSE, lw=0.7)
    V0v1 = float(feld(beob, "S1/hier_item", "(q-R)^2", "0"))
    k_v1 = alc_law.lernkurve(U, V0v1, kappa, D, F)
    for S, farbe, mk in (("S1", BLAU, "o"), ("S3", ORANGE, "s"), ("S30", AQUA, "^")):
        obs = feld(beob, f"{S}/hier_item", "(q-R)^2")
        y = rel(k_v1, obs)
        b.plot(xs, y, color=farbe, marker=mk, ms=4.5, lw=1.4, mec=FLAECHE, label=f"{S}")
        b.text(xs[0] + 0.12, y[0], f"{y[0]:+.0f} %".replace("-", "−"), fontsize=6.5, color=TEXT2, ha="left", va="bottom")
    b.set_xticks(xs)
    b.set_xticklabels([str(x) for x in bs])
    b.set_xlabel("label budget B")
    b.set_xlim(xs[0] - 0.3, xs[-1] + 0.3)
    b.set_title("(b) fixed-κ formula applied to pooled v1\n(V₀ = its own B0 excess), discovery;\n"
                f"H2b confirmatory: {urteil('H2b')}", loc="left", pad=3, fontsize=7)
    b.set_ylabel("(formula − observed) / observed, %", fontsize=6.8)
    b.legend(loc="upper right", frameon=False, title="regime", title_fontsize=6.8)
    quelle(fig, "(a) daten/beobachtung_discovery.json + daten/D_exakt.json via theorie/alc_law.py; "
                "konfirmation/hypothesen_tafel.json (H2a, teile.A.S1, teile.B.S1). (b) daten/beobachtung_discovery.json (S1/S3/S30 hier_item).")
    fig.tight_layout(w_pad=1.0, rect=(0, 0.13, 1, 1))
    speichern(fig, aus, "fig3_formel")


# ================================================================ Abb. 4 Orakel-Leiter B0 + L10-Verteilung
def abb4(aus):
    leiter = lade_json(Q["LEITER"])
    erg = lade_json(Q["LEITER2"])
    p2 = lade_json(Q["P2"])
    wdh = lade_json(Q["WDH"])
    nf = lade_csv(Q["NF"])
    e3 = lade_json(Q["E3"])
    L = {r["Stufe"].split(" ")[0]: r for r in leiter["leiter_B0"]}
    bb_b0 = feld(p2, "tabelle_alle", "S1", "beta_binomial", "brier_je_budget", "B0")
    pool_b0 = float(feld(e3, "orakel_pool_brier_je_budget_S1", "0"))
    # (Sprosse, Brier B0, erreicht/oracle, Beschriftung)
    sprossen = [
        ("L0", L["L0"]["Brier_B0"], True, "constant 0.5"),
        ("BB", bb_b0, True, "beta-binomial (B0 prior)"),
        ("L1", L["L1"]["Brier_B0"], True, "v1 (ours) at B0"),
        ("L3′", erg[next(k for k in erg if k.startswith("L3'"))]["Brier_B0"], False, "ability only, honest θ"),
        ("L3″", erg[next(k for k in erg if k.startswith("L3''"))]["Brier_B0"], False, "ability only, in-sample θ"),
        ("L2b", erg[next(k for k in erg if k.startswith("L2b"))]["Brier_B0"], False, "oracle location (logit)"),
        ("pool", pool_b0, False, "pooling oracle (LOO, strength 8)"),
        ("L2", L["L2"]["Brier_B0"], False, "oracle location (LOO mean)"),
        ("L4′", erg[next(k for k in erg if k.startswith("L4'"))]["Brier_B0"], False, "oracle location + honest θ"),
        ("L5′", erg[next(k for k in erg if k.startswith("L5'"))]["Brier_B0"], False, "oracle location + in-sample θ"),
        ("L6", L["L6"]["Brier_B0"], False, "ALS fully in-sample"),
        ("L7", L["L7"]["Brier_B0"], False, "oracle pair rate R (floor U)"),
        ("L8", L["L8"]["Brier_B0"], False, "oracle rate + LOO item difficulty"),
        ("L9", L["L9"]["Brier_B0"], False, "oracle item probability k/n (biased)"),
    ]
    q = feld(wdh, "schranke_je_bm_quantile")
    l10 = [float(r["L10_response_weighted"]) for r in nf if r["L10_response_weighted"] not in ("", None) and float(r["cells_rep"]) >= 100]
    if len(l10) != int(feld(wdh, "benchmarks_mit_>=100_wdh_zellen")):
        raise Eingabe(f"L10: {len(l10)} Benchmarks in CSV vs {wdh['benchmarks_mit_>=100_wdh_zellen']} in JSON")
    med = sorted(l10)[len(l10) // 2] if len(l10) % 2 else 0.5 * (sorted(l10)[len(l10) // 2 - 1] + sorted(l10)[len(l10) // 2])
    if abs(med - float(q["0.5"])) > 1e-5:
        raise Eingabe(f"L10-Median CSV {med} ≠ JSON {q['0.5']}")

    fig = plt.figure(figsize=(BREITE_IN, 3.7), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.32, 1.08])
    a = fig.add_subplot(gs[0])
    stil(a, raster_y=False)
    a.grid(True, axis="x", color=RASTER, lw=0.5)
    ys = list(range(len(sprossen)))[::-1]
    for y, (kurz, wert, erreicht, lab) in zip(ys, sprossen):
        farbe = BLAU if kurz == "L1" else (ORANGE if kurz == "BB" else TEXT2)
        a.plot([0, wert], [y, y], color=RASTER, lw=0.8, zorder=1)
        a.scatter([wert], [y], s=30, color=farbe if erreicht else FLAECHE, edgecolors=farbe, linewidths=1.2, zorder=3,
                  marker="o")
        a.text(wert + 0.008, y, f"{wert:.4f}", fontsize=6.5, color=TEXT1, va="center", ha="left")
    # L10 als Band
    y10 = -1
    a.plot([float(q["0.25"]), float(q["0.75"])], [y10, y10], color=TEXT2, lw=2.2, solid_capstyle="butt", zorder=2)
    a.scatter([float(q["0.5"])], [y10], s=30, color=FLAECHE, edgecolors=TEXT2, linewidths=1.2, zorder=3)
    a.set_yticks(ys + [y10])
    a.set_yticklabels([f"{kurz}  {lab}" for kurz, _, _, lab in sprossen] + [f"L10  repeat-noise floor ({len(l10)} benchmarks)"], fontsize=7)
    a.tick_params(axis="y", length=0)
    a.set_ylim(-1.8, len(sprossen) - 0.4)
    a.set_xlim(0, 0.31)
    a.set_xticks([0, 0.05, 0.1, 0.15, 0.2, 0.25])
    a.set_xlabel("Brier score at budget 0 (L9, L10: item level)\nfilled: predictor; hollow: oracle")
    a.spines["left"].set_visible(False)
    a.set_title("(a) bound ladder at budget 0", loc="left", pad=3)
    # (b) L10 Histogramm
    b = fig.add_subplot(gs[1])
    stil(b)
    b.hist(l10, bins=[i * 0.02 for i in range(0, 13)], color=BLAU_RAMPE[2], edgecolor=FLAECHE, lw=1)
    for qq, ls in (("0.25", (0, (1.5, 1.5))), ("0.5", "-"), ("0.75", (0, (1.5, 1.5)))):
        b.axvline(float(q[qq]), color=TEXT2, lw=0.8, ls=ls)
    b.set_xlabel("L10 (response-weighted)")
    b.set_ylabel("benchmarks")
    b.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    b.set_title(f"(b) L10, {len(l10)} benchmarks:\nmedian {float(q['0.5']):.3f},\nIQR {float(q['0.25']):.3f}–{float(q['0.75']):.3f};\nH7 (confirmatory):\n{urteil('H7')}", loc="left", pad=3)
    quelle(fig, "daten/leiter.json (leiter_B0), daten/leiter_ergaenzung.json (L2b, L3′, L3″, L4′, L5′), modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json (BB B0), "
                "daten/e3.json (pooling oracle S1 B0), kuratierung/wiederholung_b.json + kuratierung/noise_floor_by_benchmark.csv (L10). "
                "Design A, discovery (seeds 0–2).")
    speichern(fig, aus, "fig4_orakel_leiter")


# ================================================================ Abb. 5 Zuverlaessigkeit
def abb5(aus):
    z = lade_csv(Q["ZUV"])
    S = feld(lade_json(Q["ZUV_A"]), "primaer_S")
    budgets = sorted({int(r["budget"]) for r in z})
    fig, axs = plt.subplots(1, len(budgets), figsize=(BREITE_IN, 2.1), sharex=True, sharey=True)
    for ax, B in zip(axs, budgets):
        stil(ax)
        ax.plot([0, 1], [0, 1], color=TEXT2, lw=0.8, ls=(0, (4, 3)), zorder=1)
        for pr in ("empirischer_mittelwert", "beta_binomial", "hier_kal"):
            g = sorted((r for r in z if int(r["budget"]) == B and r["praediktor"] == pr and float(r["n"]) >= 20),
                       key=lambda r: int(r["bin"]))
            if not g:
                continue
            farbe, marker, _ = SERIE[pr]
            nmax = max(float(r["n"]) for r in g)
            ax.plot([float(r["q_mittel"]) for r in g], [float(r["R_mittel"]) for r in g], color=farbe, lw=1.4, zorder=2)
            ax.scatter([float(r["q_mittel"]) for r in g], [float(r["R_mittel"]) for r in g],
                       s=[10 + 60 * math.sqrt(float(r["n"]) / nmax) for r in g], color=farbe, marker=marker,
                       edgecolors=FLAECHE, linewidths=1.0, zorder=3)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([0, 0.5, 1])
        ax.set_xticklabels(["0", ".5", "1"])
        ax.set_yticks([0, 0.5, 1])
        ax.set_yticklabels(["0", ".5", "1"])
        ax.set_title(f"budget {B}", loc="left", pad=2)
    fig.supxlabel("mean predicted probability", fontsize=7, color=TEXT2)
    axs[0].set_ylabel("observed success rate")
    griffe = [Line2D([], [], color=SERIE[p][0], marker=SERIE[p][1], lw=1.4, ms=4, mec=FLAECHE, label=SERIE[p][2])
              for p in ("hier_kal", "beta_binomial", "empirischer_mittelwert")]
    fig.legend(handles=griffe, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=6.8)
    quelle(fig, "modell/ergebnisse/cv_A_p2/zuverlaessigkeit.csv (praediktor, budget, bin, n, q_mittel, R_mittel); regime from modell/ergebnisse/cv_A_p2/auswertung.json primaer_S.")
    fig.tight_layout(w_pad=0.4, rect=(0, 0, 1, 0.9))
    speichern(fig, aus, "fig5_zuverlaessigkeit")


# ================================================================ Abb. 6 Fehleranalyse
def abb6(aus):
    v = lade_json(Q["VERLUST"])
    jb = lade_csv(Q["JEBM"])
    fig = plt.figure(figsize=(BREITE_IN, 5.0), layout="constrained")
    gs0 = fig.add_gridspec(2, 1, height_ratios=[1, 1.25])
    gs = gs0[0].subgridspec(1, 2)
    # (a) Anteil des Ueberschusses je Budget
    a = fig.add_subplot(gs[0, 0])
    stil(a)
    regime = ["S1", "S3", "S30"]
    w = 0.26
    for i, (S, farbe) in enumerate(zip(regime, (BLAU_RAMPE[1], BLAU_RAMPE[3], BLAU_RAMPE[5]))):
        ant = feld(v, f"alc_anteil_{S}", "anteil")
        a.bar([k + (i - 1) * w for k in range(len(BUDGETS))], [100 * ant[str(b)] for b in BUDGETS], width=w, color=farbe,
              edgecolor=FLAECHE, lw=0.8, label=S)
    a.set_xticks(range(len(BUDGETS)))
    a.set_xticklabels([str(b) for b in BUDGETS])
    a.set_xlabel("label budget B")
    a.set_ylabel("share of ALC excess over floor, %")
    a.axhline(0, color=ACHSE, lw=0.7)
    a.legend(frameon=False, title="regime", loc="upper right")
    a.set_title("(a) share of excess per budget\n(S30, B31: item stage below floor)", loc="left", pad=3, fontsize=7)
    # (b) Gewinn vs BB je Benchmark gegen Subjektzahl
    b = fig.add_subplot(gs[0, 1])
    stil(b)
    b.axhline(0, color=ACHSE, lw=0.7)
    dirs = {"higher_is_better": (BLAU, "o", "higher is better"), "lower_is_better": (ORANGE, "s", "lower is better"),
            "unordered": (AQUA, "^", "unordered")}
    for d, (farbe, mk, lab) in dirs.items():
        rows = [r for r in jb if r["direction"] == d]
        b.scatter([float(r["n_subjects"]) for r in rows], [float(r["gewinn_vs_bb"]) for r in rows], s=14, color=farbe,
                  marker=mk, edgecolors=FLAECHE, linewidths=0.6, alpha=0.9, label=f"{lab} ({len(rows)})")
    b.set_xscale("log")
    log_klartext(b.xaxis, labels_minor=())
    b.set_xlabel("subjects per benchmark")
    b.set_ylabel("v1 − BB, ALC per benchmark")
    n_schl = feld(v, "n_benchmarks_schlechter_als_bb")
    b.set_title(f"(b) per benchmark, S3\n({n_schl} of {feld(v, 'n_benchmarks')} worse)",
                loc="left", pad=3, fontsize=7)
    b.set_ylim(top=0.042)
    b.legend(frameon=False, loc="upper right", fontsize=6.5, title="direction", title_fontsize=6.5, borderaxespad=0.1, handletextpad=0.2,
             labelspacing=0.25)
    # (c) Gewinn vs BB nach Gruppen
    c = fig.add_subplot(gs0[1])
    stil(c, raster_y=False)
    c.grid(True, axis="x", color=RASTER, lw=0.5)
    gruppen = []
    for schl, titel in (("gruppe_direction", "direction"), ("gruppe_domain_1", "domain"), ("gruppe_subj_klasse", "subjects per benchmark"),
                        ("gruppe_multi_single_turn", "turns"), ("gruppe_has_reference_answer", "reference answer")):
        g = feld(v, schl)
        reihen = sorted(g.items(), key=lambda kv: -kv[1]["n_bm"])
        if schl == "gruppe_domain_1":
            reihen = reihen[:6]
        if schl == "gruppe_subj_klasse":
            reihen = sorted(g.items(), key=lambda kv: KLASSEN_REIHE.index(kv[0]))
        for name, z in reihen:
            lab = {"True": "given", "False": "judge/rule-graded"}.get(name, KLASSEN_ANZEIGE.get(name, name.replace("_", " ")))
            gruppen.append((f"{titel}: {lab}", int(z["n_bm"]), float(z["gewinn_vs_bb"]), float(z["excess"])))
    ys = list(range(len(gruppen)))[::-1]
    c.axvline(0, color=ACHSE, lw=0.7)
    for y, (lab, n, gewinn, exc) in zip(ys, gruppen):
        c.plot([0, gewinn], [y, y], color=RASTER, lw=0.8, zorder=1)
        c.scatter([gewinn], [y], s=22 + 0.4 * n, color=BLAU, edgecolors=FLAECHE, linewidths=1.0, zorder=3)
        c.text(0.0056, y, f"excess {exc:.4f}", fontsize=6.5, color=TEXT2, va="center", ha="left")
    c.set_yticks(ys)
    c.set_yticklabels([f"{lab} (n={n})" for lab, n, _, _ in gruppen], fontsize=7)
    c.tick_params(axis="y", length=0)
    c.spines["left"].set_visible(False)
    c.set_xlim(-0.011, 0.0125)
    c.set_ylim(-0.8, len(gruppen) - 0.3)
    c.set_xlabel("v1 − BB, ALC (benchmark-balanced)")
    c.set_title("(c) v1 − BB by benchmark group, S3 (benchmark-balanced;\nmarker area ∝ number of benchmarks)", loc="left", pad=3, fontsize=7)
    quelle(fig, "daten/verlust.json (alc_anteil_*, gruppe_*, n_benchmarks_schlechter_als_bb), daten/je_benchmark.csv (gewinn_vs_bb, n_subjects, direction).")
    speichern(fig, aus, "fig6_fehleranalyse")


# Fig. 5(c): Klassen der Subjektzahl nach Wert (nicht nach Zeichenkette), Anzeige mit echten Zeichen
KLASSEN_REIHE = ["1", "2", "3-4", "5-9", "10-29", ">=30"]
KLASSEN_ANZEIGE = {"3-4": "3–4", "5-9": "5–9", "10-29": "10–29", ">=30": "≥30"}


# ================================================================ Anhang A1: V0_eff(S,B)
def abbA1(aus):
    v = lade_json(Q["VERLUST"])
    beob = lade_json(Q["BEOB"])
    pool = feld(v, "pooling_sq")
    fig, ax = plt.subplots(figsize=(BREITE_IN * 0.65, 2.55))
    stil(ax)
    farben = {"S1": BLAU_RAMPE[0], "S2": BLAU_RAMPE[2], "S3": BLAU_RAMPE[3], "S30": BLAU_RAMPE[5]}
    marker = {"S1": "o", "S2": "D", "S3": "s", "S30": "^"}
    for S in ("S1", "S2", "S3", "S30"):
        y = [float(feld(pool, S, str(b))) for b in BUDGETS]
        ax.plot(X, y, color=farben[S], marker=marker[S], ms=4, lw=1.4, mec=FLAECHE, label=f"v1 pair model, {S}")
    bb = feld(beob, "S1/beta_binomial", "(q-R)^2")
    ax.plot(X, [float(bb[str(b)]) for b in BUDGETS], color=ORANGE, marker="s", ms=3.5, lw=1.0, ls=(0, (3, 2)), mec=FLAECHE,
            label="beta-binomial, S1 (fixed κ)")
    ax.set_yscale("log")
    log_klartext(ax.yaxis)
    budget_achse(ax)
    ax.set_ylabel("(q − R)², pair level")
    ax.legend(frameon=False, loc="lower left", fontsize=6.8)
    quelle(fig, "daten/verlust.json (pooling_sq), daten/beobachtung_discovery.json (S1/beta_binomial).")
    fig.tight_layout()
    speichern(fig, aus, "figA1_v0_eff")


# ================================================================ Anhang A2: L10 je Benchmark
def abbA2(aus):
    nf = lade_csv(Q["NF"])
    rows = [r for r in nf if r["L10_response_weighted"] not in ("",) and float(r["cells_rep"]) >= 100]
    rows.sort(key=lambda r: float(r["L10_response_weighted"]))
    fig, ax = plt.subplots(figsize=(BREITE_IN, 8.0))
    stil(ax, raster_y=False)
    ax.grid(True, axis="x", color=RASTER, lw=0.5)
    ys = range(len(rows))
    ax.barh(list(ys), [float(r["L10_response_weighted"]) for r in rows], height=0.72, color=BLAU_RAMPE[2], edgecolor=FLAECHE, lw=0.6)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([f"{r['benchmark_id']}  (n_med={int(float(r['n_median_rep']))}, cells={int(float(r['cells_rep']))})" for r in rows], fontsize=7)
    ax.set_xlabel("L10: response-weighted repeat-noise floor")
    ax.set_ylim(-0.8, len(rows) - 0.2)
    quelle(fig, "kuratierung/noise_floor_by_benchmark.csv (L10_response_weighted, cells_rep, n_median_rep).")
    fig.tight_layout()
    speichern(fig, aus, "figA2_l10_je_benchmark")


# ================================================================ Anhang A3: Liga Forest-Plot
def abbA3(aus):
    vgl = lade_csv(Q["LIGA_VGL"])
    meta = lade_json(Q["LIGA_META"])
    falten = feld(meta, "falten")
    namen = {"irt2pl": "IRT 2PL", "irt1pl": "IRT 1PL (Rasch)", "mf": "matrix factorisation", "stack": "stacking",
             "knn": "kNN over subjects", "gb": "gradient boosting", "beta_binomial": "beta-binomial",
             "v1_ohne_itemstufe": "v1 without item stage", "empirischer_mittelwert": "empirical mean", "konstant_0.5": "constant 0.5"}
    regime = ["S1", "S2", "S3", "S30", "kompakt10"]
    methoden = [m for m in namen if any(r["modell"] == m and r["referenz"] == "v1_hier_item" for r in vgl)]
    fig, axa = plt.subplots(2, 3, figsize=(BREITE_IN, 4.5), sharex=True, sharey=True)
    axs = list(axa.flat)
    for ax, S in zip(axs, regime):
        stil(ax, raster_y=False)
        ax.grid(True, axis="x", color=RASTER, lw=0.5)
        ax.axvspan(-0.001, 0.001, color=RASTER, lw=0, zorder=0)
        ax.axvline(0, color=ACHSE, lw=0.7)
        for y, m in enumerate(methoden[::-1]):
            r = next((r for r in vgl if r["modell"] == m and r["referenz"] == "v1_hier_item" and r["S"] == S), None)
            if r is None:
                raise Eingabe(f"Liga-Vergleich fehlt: {m}/{S}")
            lo, hi, mitte = float(r["ki95_unten"]), float(r["ki95_oben"]), float(r["mittel"])
            farbe = ORANGE if r["urteil"] == "schlechter" else (BLAU if r["urteil"] == "besser" else TEXT2)
            ax.plot([lo, hi], [y, y], color=farbe, lw=1.2, solid_capstyle="butt", zorder=2)
            ax.scatter([mitte], [y], s=16, color=farbe, edgecolors=FLAECHE, linewidths=0.8, zorder=3, clip_on=True)
            if hi > 0.0135 and mitte > 0.011:
                ax.text(min(0.0133, lo - 0.0004), y, f"→ {mitte:+.3f}", fontsize=6.5, color=TEXT2, va="center", ha="right")
        ax.set_xlim(-0.004, 0.0135)
        ax.set_xticks([0, 0.005, 0.01])
        ax.set_xticklabels(["0", ".005", ".01"])
        ax.set_title("compact10" if S == "kompakt10" else S, loc="left", pad=2)
        ax.tick_params(axis="y", length=0)
    for ax in axa[:, 0]:
        ax.set_yticks(range(len(methoden)))
        ax.set_yticklabels([namen[m] for m in methoden[::-1]])
    for ax in axa[1, :2]:
        ax.set_xlabel("method − v1 (ALC)")
    nt = axs[-1]
    nt.axis("off")
    vorl = "PRELIMINARY: " if len(falten) < 10 else ""
    nt.text(0.0, 1.0, f"{vorl}{len(falten)}/10 folds, discovery seeds {saaten_text(feld(meta, 'saaten'))};\n"
            "test pairs capped at 30 per benchmark;\nnot confirmatory.\n\n"
            "dot: paired ALC difference,\nbar: 95 % cluster-robust CI;\ngrey band: equivalence margin ±0.001.",
            transform=nt.transAxes, fontsize=6.8, color=TEXT2, va="top", ha="left", linespacing=1.3)
    griffe = [Line2D([], [], color=ORANGE, lw=1.4, marker="o", ms=3.5, label="worse than v1 by the rule"),
              Line2D([], [], color=TEXT2, lw=1.4, marker="o", ms=3.5, label="no difference shown or equivalent"),
              Line2D([], [], color=BLAU, lw=1.4, marker="o", ms=3.5, label="better than v1 by the rule")]
    nt.legend(handles=griffe, loc="lower left", frameon=False, fontsize=6.8, bbox_to_anchor=(0.0, 0.0))
    quelle(fig, "liga/ergebnisse/vergleich_gepaart.csv (mittel, ki95_unten, ki95_oben, urteil), liga/ergebnisse/meta.json (falten, saaten).")
    fig.tight_layout(w_pad=0.5, h_pad=0.8)
    speichern(fig, aus, "figA3_liga_forest")


# ================================================================ Anhang A4: Akquise-Politiken (nur Pilot)
def abbA4(aus):
    t = lade_json(Q["AKQ"])
    vgl = feld(t, "vergleiche_vs_zufall")
    abd = feld(t, "abdeckung_bewertungsitems")
    fig, (a, b) = plt.subplots(1, 2, figsize=(BREITE_IN, 2.9), gridspec_kw=dict(width_ratios=[1, 1.3]))
    stil(a)
    a.axhline(0, color=ACHSE, lw=0.7)
    for i, r in enumerate(vgl):
        lo, hi = r["ki95"]
        a.errorbar([i], [r["mittel"]], yerr=[[r["mittel"] - lo], [hi - r["mittel"]]], fmt="o", color=BLAU, ms=5, mec=FLAECHE,
                   capsize=3, lw=1.2)
        a.text(i, hi + 0.0002, f"{r['mittel']:+.5f}\n{BUCHSTABE_WORT[buchstabe(r['mittel'], r['se'])]}\n"
               f"{r['n_paare']} pairs,\n{r['n_cluster']} clusters", fontsize=6.5, ha="center", va="bottom", color=TEXT2)
    a.set_xticks(range(len(vgl)))
    a.set_xticklabels([r["S"].replace("kompakt10", "compact10") for r in vgl])
    a.set_xlim(-0.6, len(vgl) - 0.4)
    a.set_ylim(-0.0035, 0.0042)
    a.set_ylabel("ALC(coverage policy) − ALC(random)")
    a.set_title("(a) coverage policy vs random\n(pilot: fold 0, seeds 0–2)", loc="left", fontsize=7, pad=3)
    stil(b)
    for S, farbe in (("kompakt10|rr|paar", BLAU), ("S3|rr|paar", GELB)):
        for pol, ls, mk in (("abdeckung", "-", "o"), ("zufall", (0, (3, 2)), "s")):
            y = [float(feld(abd, S, pol, f"B{bb}")) for bb in BUDGETS]
            b.plot(X, y, color=farbe, ls=ls, marker=mk, ms=3.8, lw=1.3, mec=FLAECHE,
                   label=f"{S.split('|')[0].replace('kompakt10', 'compact10')}, {'coverage' if pol == 'abdeckung' else 'random'}")
    budget_achse(b)
    b.set_ylabel("evaluation items with foreign\nlabels (mean per pair)")
    b.legend(frameon=False, fontsize=6.5, loc="upper left")
    b.set_title("(b) label coverage of evaluation items\n(compact10: ≈50 evaluation items per pair)", loc="left", fontsize=7, pad=3)
    quelle(fig, "daten/akquise_pilot_tabelle.json (vergleiche_vs_zufall, abdeckung_bewertungsitems); pilot only — "
                "the full policy run (S1/S3/S30/kompakt10 × 7 policies) was aborted on 2026-10-21 and is not evaluated (akquise/STATUS.md).")
    fig.tight_layout(w_pad=1.2)
    speichern(fig, aus, "figA4_akquise")


# ================================================================ Anhang A5: Fallbeispiele (zwei Lernkurven)
def abbA5(aus):
    fb = lade_json(Q["FALL"])
    faelle = [k for k in ("nyu_ctf_bench", "mind2web") if k in fb]
    if len(faelle) != 2:
        raise Eingabe("Fallbeispiele nyu_ctf_bench/mind2web fehlen in fallbeispiele.json")
    fig, axs = plt.subplots(1, 2, figsize=(BREITE_IN, 2.75))
    for ax, k in zip(axs, faelle):
        stil(ax)
        d = fb[k]
        for S, alpha in (("S1", 0.45), ("S3", 1.0)):
            if S not in d:
                continue
            bj = feld(d, S, "brier_je_budget")
            for pr in ("beta_binomial", "hier_item"):
                farbe, mk, _ = SERIE[pr]
                ax.plot(X, [float(bj[pr][str(b)]) for b in BUDGETS], color=farbe, alpha=alpha, marker=mk, ms=3.8, lw=1.3,
                        mec=FLAECHE, ls="-" if S == "S3" else (0, (3, 2)))
        fl = float(feld(d, "S3", "floor_R(1-R)"))
        ax.axhline(fl, color=TEXT2, lw=0.8, ls=(0, (4, 2)))
        ax.text(X[0], fl + 0.004, f"pair floor U = {fl:.3f}", fontsize=6.5, color=TEXT2, va="bottom", ha="left")
        s3 = d["S3"]
        se = s3["diff_se_ueber_paare"]
        se_txt = f"SE over pairs {se:.4f}" if isinstance(se, (int, float)) else "one pair: no SE"
        ax.set_title(f"{k}: {d['paare_test']} test {'pair' if d['paare_test'] == 1 else 'pairs'}\n"
                     f"{d['n_subjects_db']} {'subject' if d['n_subjects_db'] == 1 else 'subjects'} in the database, R̄={s3['R_mittel']:.2f}\n"
                     f"S3: v1 − BB {s3['diff_hier_item_minus_bb_alc']:+.4f} ({se_txt})".replace("-0", "−0"), loc="left", fontsize=7, pad=3)
        budget_achse(ax)
    axs[0].set_ylabel("Brier score")
    griffe = [Line2D([], [], color=SERIE["hier_item"][0], marker="o", lw=1.3, ms=4, mec=FLAECHE, label="v1 (ours), S3"),
              Line2D([], [], color=SERIE["beta_binomial"][0], marker="s", lw=1.3, ms=4, mec=FLAECHE, label="beta-binomial, S3"),
              Line2D([], [], color=TEXT2, lw=1.0, ls=(0, (3, 2)), alpha=0.6, label="same, S1 (dashed, faded)")]
    fig.legend(handles=griffe, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=6.8)
    quelle(fig, "kuratierung/fallbeispiele.json (brier_je_budget, floor_R(1-R), diff_hier_item_minus_bb_alc, n_subjects_db).")
    fig.tight_layout(w_pad=1.0, rect=(0, 0, 1, 0.92))
    speichern(fig, aus, "figA5_fallbeispiele")


# Abbildungsname -> \label im Bericht (Quellentabelle in Anhang F); figA4 ist (noch) nicht im PDF eingebunden.
# Reihenfolge = Abbildungsnummer im PDF (1 map, 2 league, 3 formula, 4 ladder, 5 errors, 6 cases, 7 waterfall, 8 rel, 9 v0eff, 10 l10);
# pruefe_zahlen.py prueft sie gegen die .aux-Datei.
LABEL = {"fig1_lernkurven": "fig:map", "figA3_liga_forest": "fig:league", "fig3_formel": "fig:formula", "fig4_orakel_leiter": "fig:ladder",
         "fig6_fehleranalyse": "fig:errors", "figA5_fallbeispiele": "fig:cases", "fig2_zerlegung": "fig:waterfall",
         "fig5_zuverlaessigkeit": "fig:rel", "figA1_v0_eff": "fig:v0eff", "figA2_l10_je_benchmark": "fig:l10"}


def tex_pfad(t):
    """Dateiliste -> TeX: Unterstriche escapen, an '/', '_' umbrechbar machen."""
    t = t.replace("kuratierung/", "curation/").replace("′", "'").replace("″", "''")
    return t.replace("_", "\\_\\allowbreak{}").replace("/", "/\\allowbreak{}")


def schreibe_quellen(aus: Path):
    """Quellentabelle fuer Anhang F: ersetzt die frueheren Quellzeilen IN den Abbildungen (S3: kein Kleintext in der Grafik)."""
    zeilen = []
    for name, lab in LABEL.items():
        if not QUELLEN.get(name):
            raise Eingabe(f"keine Quellenangabe fuer {name}")
        zeilen.append(f"    \\ref{{{lab}}} & \\texttt{{{tex_pfad(QUELLEN[name])}}} \\\\")
    kopf = ("% erzeugt von plots_v2.py (nicht von Hand aendern)\n\\begin{table}[H]\n  \\caption{\\raggedright Data files read by the figure script for each figure "
            "(paths relative to the repository root; \\texttt{daten/} = \\texttt{report/src/daten/}).}\n  \\label{tab:figsources}\n  \\centering\\scriptsize\n"
            "  \\begin{tabular}{@{}l>{\\raggedright\\arraybackslash}p{0.86\\linewidth}@{}}\n    \\toprule\n    figure & files \\\\\n    \\midrule\n")
    (aus / "quellen_abbildungen.tex").write_text(kopf + "\n".join(zeilen) + "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}\n", encoding="utf-8")
    print("ok quellen_abbildungen.tex")


ALLE = [abb1, abb2, abb3, abb4, abb5, abb6, abbA1, abbA2, abbA3, abbA4, abbA5]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--aus", default=str(HIER / "abbildungen"))
    ap.add_argument("--nur", default="", help="Kommaliste von Funktionsnamen (abb1,...)")
    a = ap.parse_args(argv)
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    fns = [f for f in ALLE if not a.nur or f.__name__ in a.nur.split(",")]
    fehler = 0
    for f in fns:
        try:
            f(aus)
        except Exception as e:  # fail-closed: melden, am Ende rc != 0
            fehler += 1
            print(f"FEHLER {f.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
    if not a.nur and not fehler:
        try:
            schreibe_quellen(aus)
        except Exception as e:
            fehler += 1
            print(f"FEHLER quellen: {type(e).__name__}: {e}", file=sys.stderr)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
