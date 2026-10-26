"""Brier, Brier-ALC, ECE (10 gleich breite Bins, nach Antwortzahl gewichtet), Murphy-Zerlegung.

Zeugen (Wettbewerbsseite, quellen/competition.txt Z. 483-515, 704): Gewichte 0.1/0.2/0.2/0.2/0.2/0.1;
Beispiel Brier 0.22, 0.18, 0.145, 0.12, 0.1, 0.09 -> ALC 0.140; konstant 0.5 -> 0.25.
"""
import math

BUDGETS = (0, 1, 3, 7, 15, 31)
GEWICHTE = (0.1, 0.2, 0.2, 0.2, 0.2, 0.1)


def brier(p, y):
    return sum((a - b) ** 2 for a, b in zip(p, y)) / len(p)


def alc(brier_je_budget):
    """brier_je_budget: dict budget->Brier oder Liste in BUDGETS-Reihenfolge."""
    werte = [brier_je_budget[b] for b in BUDGETS] if isinstance(brier_je_budget, dict) else list(brier_je_budget)
    return sum(g * w for g, w in zip(GEWICHTE, werte))


def ece(p, y, bins=10):
    n = len(p)
    summe = [[0, 0.0, 0.0] for _ in range(bins)]
    for a, b in zip(p, y):
        k = min(int(a * bins), bins - 1)
        summe[k][0] += 1
        summe[k][1] += a
        summe[k][2] += b
    return sum(c / n * abs(sp / c - sy / c) for c, sp, sy in summe if c)


def zuverlaessigkeit(p, y, bins=10):
    tab = []
    for k in range(bins):
        sel = [(a, b) for a, b in zip(p, y) if min(int(a * bins), bins - 1) == k]
        if sel:
            tab.append({"bin": f"{k / bins:.1f}-{(k + 1) / bins:.1f}", "n": len(sel),
                        "p_mittel": sum(a for a, _ in sel) / len(sel), "y_mittel": sum(b for _, b in sel) / len(sel)})
    return tab


def murphy(p, y, bins=10):
    """Brier ≈ Reliabilität − Auflösung + Unsicherheit (binnenweise)."""
    n = len(p)
    ybar = sum(y) / n
    rel = res = 0.0
    for z in zuverlaessigkeit(p, y, bins):
        rel += z["n"] / n * (z["p_mittel"] - z["y_mittel"]) ** 2
        res += z["n"] / n * (z["y_mittel"] - ybar) ** 2
    return {"reliabilitaet": rel, "aufloesung": res, "unsicherheit": ybar * (1 - ybar)}


def cluster_vergleich(diff_je_paar, cluster_je_paar, z_schwelle=2.0):
    """Gepaarte Differenz (Modell − Referenz, negativ = besser), Paare gleich gewichtet wie im
    Wettbewerb, SE cluster-robust über Benchmarks. Entscheidung „besser“ nur, wenn
    mittel + z*SE < 0. Betriebskennlinie: P(Fehlentscheidung „besser“ | Nulleffekt) = 1 − Phi(z)."""
    n = len(diff_je_paar)
    if n == 0:
        return {"n_paare": 0, "urteil": "unbekannt (keine Paare)"}
    d = sum(diff_je_paar) / n
    cl = {}
    for x, c in zip(diff_je_paar, cluster_je_paar):
        cl.setdefault(c, []).append(x - d)
    C = len(cl)
    if C < 2:
        return {"n_paare": n, "n_cluster": C, "mittel": d, "urteil": "unbekannt (< 2 Cluster)"}
    se = math.sqrt(sum(sum(v) ** 2 for v in cl.values()) / n ** 2 * C / (C - 1))
    p_fehl = 0.5 * math.erfc(z_schwelle / math.sqrt(2))
    if se == 0:
        urteil = "besser" if d < 0 else ("schlechter" if d > 0 else "kein Unterschied belegt")
    else:
        urteil = "besser" if d + z_schwelle * se < 0 else ("schlechter" if d - z_schwelle * se > 0
                                                           else "kein Unterschied belegt")
    return {"n_paare": n, "n_cluster": C, "mittel": d, "se": se, "z": d / se if se else None,
            "ki95": [d - 1.96 * se, d + 1.96 * se], "schwelle": f"mittel + {z_schwelle}*SE < 0",
            "p_fehlentscheidung_bei_nulleffekt": p_fehl,
            "grauzone_breite_in_se": 2 * z_schwelle, "urteil": urteil}


def brier_paar(q, R):
    """Brier eines Paares bei paarkonstanter Vorhersage q und Erfolgsquote R der Bewertungsantworten:
    mittel (q - y)^2 = (q - R)^2 + R(1 - R)."""
    return (q - R) ** 2 + R * (1.0 - R)
