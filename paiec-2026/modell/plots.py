"""Kalibrierungsplot (Zuverlässigkeitsdiagramme je Budget) und Lernkurven aus der CV-Auswertung.

Aufruf: python3 -I plots.py --design A [--S 3] --aus <ordner>
Farben: validierte Referenzpalette der dataviz-Vorgaben (hell), feste Zuordnung Entität -> Farbe in beiden Abbildungen;
Markerformen als zweite Kodierung (Kontrast < 3:1 bei aqua/gelb), direkte Beschriftung, Diagonale/Referenz grau.
"""
import argparse
import json
import os
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SCRATCH = Path(os.environ.get("PAIEC_WORK", "work")) / "modell"
FLAECHE, TEXT1, TEXT2, RASTER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIE = {  # Entität -> (Farbe, Marker, Beschriftung)
    "hier_kalibriert": ("#2a78d6", "o", "hierarchical (ours, calibrated)"),
    "beta_binomial": ("#eb6834", "s", "beta-binomial pair mean"),
    "empirischer_mittelwert": ("#1baf7a", "^", "empirical mean (organizer baseline)"),
    "hier_ohne_subjekt": ("#eda100", "D", "ours without subject knowledge"),
}

KURZ = {"hier_kalibriert": "hierarchical, calibrated (ours)", "empirischer_mittelwert": "empirical mean (organizers)"}


def stil(ax):
    ax.set_facecolor(FLAECHE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(TEXT2)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=TEXT2, labelsize=8)
    ax.grid(True, color=RASTER, linewidth=0.6)
    ax.set_axisbelow(True)


def zuverlaessigkeit(d, S, aus):
    z = pd.read_csv(d / "zuverlaessigkeit.csv")
    budgets = sorted(z.budget.unique())
    zeilen = math.ceil(len(budgets) / 2)
    fig, axs = plt.subplots(zeilen, 2, figsize=(4.2, 1.6 * zeilen), sharex=True, sharey=True, facecolor=FLAECHE)
    axs = axs.ravel()
    for ax, B in zip(axs, budgets):
        stil(ax)
        ax.plot([0, 1], [0, 1], color=TEXT2, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        for pr in ("empirischer_mittelwert", "beta_binomial", "hier_kalibriert"):
            g = z[(z.budget == B) & (z.praediktor == pr) & (z.n >= 20)].sort_values("bin")
            if g.empty:
                continue
            farbe, marker, _ = SERIE[pr]
            gross = [8 + 40 * math.sqrt(n / g.n.max()) for n in g.n]
            ax.plot(g.q_mittel, g.R_mittel, color=farbe, linewidth=2, zorder=2)
            ax.scatter(g.q_mittel, g.R_mittel, s=gross, color=farbe, marker=marker, edgecolors=FLAECHE,
                       linewidths=1.5, zorder=3)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title(f"budget {B}", fontsize=9, color=TEXT1, loc="left")
    for ax in axs[-2:]:
        ax.set_xlabel("mean predicted probability", fontsize=8, color=TEXT2)
    fig.supylabel("observed success rate", fontsize=8, color=TEXT2)
    griffe = [plt.Line2D([], [], color=SERIE[p][0], marker=SERIE[p][1], linewidth=2, markersize=6,
                         markeredgecolor=FLAECHE, label=SERIE[p][2])
              for p in ("hier_kalibriert", "beta_binomial", "empirischer_mittelwert")]
    fig.legend(handles=griffe, loc="upper center", ncol=2, frameon=False, fontsize=8, labelcolor=TEXT1,
               bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(aus / "kalibrierung.png", dpi=180, facecolor=FLAECHE, bbox_inches="tight")
    plt.close(fig)


def lernkurven(d, S, aus):
    erg = json.loads((d / "auswertung.json").read_text())
    t = erg["tabelle_alle"][S]
    budgets = [0, 1, 3, 7, 15, 31]
    x = [math.log2(1 + b) for b in budgets]
    fig, ax = plt.subplots(figsize=(5.0, 2.35), facecolor=FLAECHE)
    stil(ax)
    ax.axhline(0.25, color=TEXT2, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(x[-1], 0.2515, "constant 0.5", fontsize=7, color=TEXT2, ha="right", va="bottom")
    for pr in ("empirischer_mittelwert", "beta_binomial", "hier_kalibriert"):
        if pr not in t:
            continue
        y = [t[pr]["brier_je_budget"][f"B{b}"] for b in budgets]
        farbe, marker, lab = SERIE[pr]
        lab = KURZ.get(pr, lab)
        ax.plot(x, y, color=farbe, linewidth=2, marker=marker, markersize=6, markeredgecolor=FLAECHE,
                markeredgewidth=1.5, label=f"{lab} — ALC {t[pr]['alc_paare']:.4f}")
    ax.set_xticks(x)
    ax.set_xticklabels([str(b) for b in budgets])
    ax.set_xlabel("label budget per pair (log2(1+n) spacing, as in the competition ALC)", fontsize=8, color=TEXT2)
    ax.set_ylabel("Brier score (pairs weighted equally)", fontsize=8, color=TEXT2)
    lo = min(min(t[p]["brier_je_budget"].values()) for p in ("empirischer_mittelwert", "beta_binomial", "hier_kalibriert") if p in t)
    ax.set_ylim(lo - 0.01, 0.32)
    if "empirischer_mittelwert" in t:
        b1 = t["empirischer_mittelwert"]["brier_je_budget"]["B1"]
        if b1 > 0.32:
            ax.text(x[1], 0.306, f"{b1:.3f} at\nbudget 1", fontsize=7.5, color=TEXT2, ha="center", va="center")
    ax.legend(frameon=False, fontsize=7.5, labelcolor=TEXT1, loc="upper right", ncol=1)
    fig.tight_layout()
    fig.savefig(aus / "lernkurven.png", dpi=180, facecolor=FLAECHE, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="A")
    ap.add_argument("--S", default="S3")
    ap.add_argument("--aus", required=True)
    a = ap.parse_args()
    d = SCRATCH / f"cv_{a.design}"
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    zuverlaessigkeit(d, a.S, aus)
    lernkurven(d, a.S, aus)
    print("ok", aus)
