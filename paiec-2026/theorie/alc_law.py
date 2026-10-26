"""alc_law.py — Lernkurve und Brier-ALC eines Posterior-Mittel-Praediktors unter dem PAIEC-Protokoll.

Nur Standardbibliothek. Aufruf als Modul oder als Werkzeug:
    python3 -I alc_law.py --U 0.1833 --V0 0.0673 --kappa 2.73 --D 0.00138 [--F 0.00069] [--split exakt|quadrat]
Gibt JSON aus (Lernkurve je Budget, ALC mit Termzerlegung, ALC-optimales kappa, Paar-Boden). Rueckgabecode 0 nur
bei gueltigen Eingaben; jede ungueltige Eingabe (kappa <= 0, N < 2*B, negative Varianzen, NaN/inf) bricht mit
ALCLawError / Rueckgabecode 2 ab (fail-closed). Herleitung und Gueltigkeitsgrenzen: ANHANG-A.md (gleicher Ordner).

Modell (Anhang A, §A.2). Je Paar (Subjekt s, Benchmark b) mit N Items; die Items werden zufaellig in eine Akquise-
Haelfte A (N_A = N//2) und eine Bewertungs-Haelfte E geteilt. Budget B zieht B Items aus A ohne Zuruecklegen, je Item
eine Antwort y ~ Bernoulli(p_i); k = Summe der Labels. Bewertet wird gegen R_E = (gewichtetes) Mittel der p_i ueber E.
Ein Posterior-Mittel mit Prior-Mittel mu und Prior-Staerke kappa sagt q_B = (k + kappa*mu)/(B + kappa) vorher. Dann:

    E(q_B - R_E)^2 = [ B*(U - (B-1)*F) + kappa^2 * V0 ] / (B + kappa)^2  +  [ B/(B + kappa) ] * D        ("exakt")

mit U  = E R(1-R)            (Paar-Untergrenze, Brier einer paarkonstanten Vorhersage mit q = R),
    V0 = E (mu - R_E)^2      (Prior-Fehler; identisch mit dem (q-R)^2 bei Budget 0),
    D  = E (Rbar_A - R_E)^2  (Split-Term; bei zufaelliger Halbierung D_pair = 4*Var_i(p_i)/(N-1)),
    F  = E [ Var_i(p_i) / (N_A - 1) ]   (Endlichkeitskorrektur des Ziehens ohne Zuruecklegen; F ~ D/2).
Die Naeherung aus v2-plan/d-wissenschaft/split.py (2026-10-20 19:22Z) lautet dagegen
    E(q_B - R_E)^2 = [ B*U + kappa^2 * V0 ] / (B + kappa)^2  +  [ B/(B + kappa) ]^2 * D,   F = 0           ("quadrat")
und wird hier nur zur Reproduktion der dort berichteten Zahlen angeboten (split.json, alc_terme.json).

Bei B = 0 ist E(q_0 - R_E)^2 = V0 in beiden Formen. ALC = U + sum_B w_B * E(q_B - R_E)^2 mit den Wettbewerbsgewichten.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

BUDGETS = (0, 1, 3, 7, 15, 31)
GEWICHTE = (0.1, 0.2, 0.2, 0.2, 0.2, 0.1)
SPLIT_FORMEN = ("exakt", "quadrat")


class ALCLawError(ValueError):
    """Ungueltige Eingabe; der Aufrufer darf das Ergebnis nicht verwenden (fail-closed)."""


def _endlich(name, x):
    if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(float(x)):
        raise ALCLawError(f"{name} ist nicht endlich: {x!r}")
    return float(x)


def pruefe(U, V0, kappa, D=0.0, F=0.0, N=None, budgets=BUDGETS, split="exakt"):
    """Prueft alle Eingaben; wirft ALCLawError statt stillschweigend zu rechnen."""
    U, V0, kappa, D, F = (_endlich(n, v) for n, v in (("U", U), ("V0", V0), ("kappa", kappa), ("D", D), ("F", F)))
    if kappa <= 0:
        raise ALCLawError(f"kappa muss > 0 sein (Prior-Staerke), ist {kappa}")
    if not 0.0 <= U <= 0.25:
        raise ALCLawError(f"U = E R(1-R) muss in [0, 0.25] liegen, ist {U}")
    if V0 < 0 or D < 0 or F < 0:
        raise ALCLawError(f"V0, D, F muessen >= 0 sein: V0={V0}, D={D}, F={F}")
    if split not in SPLIT_FORMEN:
        raise ALCLawError(f"split muss eine von {SPLIT_FORMEN} sein, ist {split!r}")
    budgets = tuple(int(b) for b in budgets)
    if any(b < 0 for b in budgets):
        raise ALCLawError(f"Budgets muessen >= 0 sein: {budgets}")
    if N is not None:
        N = _endlich("N", N)
        if N < 2 * max(budgets):
            raise ALCLawError(f"N = {N} Items reichen nicht: die Akquise-Haelfte (N//2) muss >= B_max = {max(budgets)} sein")
        if N < 2:
            raise ALCLawError("N muss >= 2 sein")
    for b in budgets:
        if b >= 1 and U - (b - 1) * F < 0:
            raise ALCLawError(f"Endlichkeitskorrektur zu gross: U - (B-1)*F < 0 bei B={b} (U={U}, F={F})")
    return U, V0, kappa, D, F


def terme_budget(B, U, V0, kappa, D=0.0, F=0.0, split="exakt"):
    """Zerlegung von E(q_B - R_E)^2 in Stichproben-, Prior- und Split-Term (alle >= 0)."""
    B = int(B)
    if B == 0:
        return {"stichprobe": 0.0, "prior": V0, "split": 0.0, "mse": V0}
    nenner = (B + kappa) ** 2
    stich = B * (U - (B - 1) * F) / nenner
    prior = kappa * kappa * V0 / nenner
    frac = B / (B + kappa)
    spl = frac * D if split == "exakt" else frac * frac * D
    return {"stichprobe": stich, "prior": prior, "split": spl, "mse": stich + prior + spl}


def lernkurve(U, V0, kappa, D=0.0, F=None, N=None, budgets=BUDGETS, split="exakt"):
    """E(q_B - R_E)^2 je Budget als dict {B: Wert}. F=None: F = D/2 bei 'exakt', 0 bei 'quadrat'."""
    if F is None:
        F = D / 2.0 if split == "exakt" else 0.0
    U, V0, kappa, D, F = pruefe(U, V0, kappa, D, F, N, budgets, split)
    return {int(b): terme_budget(b, U, V0, kappa, D, F, split)["mse"] for b in budgets}


def alc(U, V0, kappa, D=0.0, F=None, N=None, budgets=BUDGETS, gewichte=GEWICHTE, split="exakt"):
    """Brier-ALC mit Termzerlegung: ALC = U + w_0*V0 + sum_{B>=1} w_B*(stich + prior + split)."""
    if F is None:
        F = D / 2.0 if split == "exakt" else 0.0
    U, V0, kappa, D, F = pruefe(U, V0, kappa, D, F, N, budgets, split)
    if len(gewichte) != len(budgets):
        raise ALCLawError("gewichte und budgets muessen gleich lang sein")
    if abs(sum(gewichte) - 1.0) > 1e-12:
        raise ALCLawError(f"ALC-Gewichte muessen sich zu 1 summieren, Summe {sum(gewichte)}")
    s = {"U": U, "B0": 0.0, "stichprobe": 0.0, "prior": 0.0, "split": 0.0}
    kurve = {}
    for w, b in zip(gewichte, budgets):
        t = terme_budget(b, U, V0, kappa, D, F, split)
        kurve[int(b)] = t["mse"]
        if b == 0:
            s["B0"] += w * V0
        else:
            s["stichprobe"] += w * t["stichprobe"]
            s["prior"] += w * t["prior"]
            s["split"] += w * t["split"]
    s["ALC"] = s["U"] + s["B0"] + s["stichprobe"] + s["prior"] + s["split"]
    s["paar_boden_V0_0"] = s["U"] + s["stichprobe"] + s["split"]  # perfekter Prior (V0 = 0, auch bei B0)
    s["kurve"] = kurve
    return s


def kappa_opt(U, V0, D=0.0, F=None, budgets=BUDGETS, gewichte=GEWICHTE, split="exakt", lo=1e-3, hi=1e3):
    """ALC-optimale Prior-Staerke kappa*.

    Ohne Split- und Endlichkeitsterm (D = F = 0) gilt fuer JEDES Budget B >= 1 geschlossen kappa* = U/V0
    (d/dkappa [B*U + kappa^2*V0]/(B+kappa)^2 = 0  <=>  kappa = U/V0), unabhaengig von den Gewichten. Fuer eine
    Beta-Prior mit korrekt spezifizierten Momenten ist U/V0 = kappa identisch (Momentenidentitaet Var R =
    mu(1-mu)/(kappa+1), E R(1-R) = mu(1-mu)*kappa/(kappa+1)); kappa* ~ kappa_ML prueft also die Spezifikation.
    Mit D > 0 oder F > 0 wird numerisch minimiert (Goldener Schnitt; das Ziel ist in kappa unimodal auf [lo, hi]).
    """
    if F is None:
        F = D / 2.0 if split == "exakt" else 0.0
    U, V0, _, D, F = pruefe(U, V0, 1.0, D, F, None, budgets, split)
    if V0 <= 0:
        raise ALCLawError("kappa* ist fuer V0 = 0 unendlich (perfekter Prior); nicht definiert")
    geschlossen = U / V0
    if D == 0.0 and F == 0.0:
        return {"kappa_opt": geschlossen, "kappa_opt_geschlossen_U_durch_V0": geschlossen, "methode": "geschlossen"}

    def ziel(k):
        return alc(U, V0, k, D, F, None, budgets, gewichte, split)["ALC"]

    g = (math.sqrt(5) - 1) / 2
    a, b = math.log(lo), math.log(hi)
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = ziel(math.exp(c)), ziel(math.exp(d))
    for _ in range(200):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = ziel(math.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = ziel(math.exp(d))
        if b - a < 1e-10:
            break
    k = math.exp((a + b) / 2)
    return {"kappa_opt": k, "kappa_opt_geschlossen_U_durch_V0": geschlossen, "methode": "goldener_schnitt", "ALC_bei_kappa_opt": ziel(k)}


def D_aus_varianz(var_i, N):
    """Split-Term eines Paares: E(Rbar_A - Rbar_E)^2 bei zufaelliger Halbierung von N Items mit Populationsvarianz
    var_i der Item-Wahrscheinlichkeiten p_i (gleich grosse Haelften, ungewichtet): 4*var_i/(N-1)."""
    var_i, N = _endlich("var_i", var_i), _endlich("N", N)
    if var_i < 0 or N < 2:
        raise ALCLawError(f"var_i >= 0 und N >= 2 noetig: var_i={var_i}, N={N}")
    return 4.0 * var_i / (N - 1.0)


def F_aus_varianz(var_i, N):
    """Endlichkeitskoeffizient eines Paares: var_i/(N_A - 1), N_A = N//2 (Ziehen ohne Zuruecklegen aus der Akquise-Haelfte)."""
    var_i, N = _endlich("var_i", var_i), _endlich("N", N)
    NA = int(N) // 2
    if var_i < 0 or NA < 2:
        raise ALCLawError(f"var_i >= 0 und N//2 >= 2 noetig: var_i={var_i}, N={N}")
    return var_i / (NA - 1.0)


def D_naeherung_split_py(r, N):
    """Nur zur Dokumentation: Naeherung aus v2-plan/d-wissenschaft/split.py, 2*r*(1-r)/N. Sie unterschaetzt den
    Split-Term etwa um den Faktor 2 (richtig: 4*var_i/(N-1), und var_i ~ r(1-r) nur, wenn fast alle Items n = 1 haben)."""
    r, N = _endlich("r", r), _endlich("N", N)
    return 2.0 * r * (1.0 - r) / N


def _main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--U", type=float, required=True, help="E R(1-R), Paar-Untergrenze")
    ap.add_argument("--V0", type=float, required=True, help="E(mu - R_E)^2, (q-R)^2 bei Budget 0")
    ap.add_argument("--kappa", type=float, required=True, help="Prior-Staerke (Beta: alpha+beta)")
    ap.add_argument("--D", type=float, default=0.0, help="Split-Term E(Rbar_A - R_E)^2")
    ap.add_argument("--F", type=float, default=None, help="Endlichkeitskoeffizient E[var_i/(N_A-1)]; Standard D/2 (exakt) bzw. 0 (quadrat)")
    ap.add_argument("--N", type=float, default=None, help="Itemzahl je Paar (nur Pruefung N >= 2*B_max)")
    ap.add_argument("--split", default="exakt", choices=SPLIT_FORMEN)
    a = ap.parse_args(argv)
    try:
        out = alc(a.U, a.V0, a.kappa, a.D, a.F, a.N, split=a.split)
        out["kappa_opt"] = kappa_opt(a.U, a.V0, a.D, a.F, split=a.split)
        out["eingabe"] = {"U": a.U, "V0": a.V0, "kappa": a.kappa, "D": a.D, "F": a.F, "N": a.N, "split": a.split}
    except ALCLawError as e:
        print(json.dumps({"fehler": str(e), "urteil": "ABBRUCH (fail-closed)"}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
