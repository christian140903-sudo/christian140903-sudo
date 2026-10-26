"""Vergleichs-Prädiktoren mit derselben Schnittstelle wie inferenz.Modell (wahrscheinlichkeit(input, labeled)).

Konstant(0.5)           Wettbewerbsreferenz (Brier 0,25)
EmpirischerMittelwert   Nachbau der Veranstalter-Baseline paiec_baseline@cc88a959 empirical_mean/model.py (gelesen,
                        nicht ausgeführt): Labels desselben vollständigen Subjekt-Dicts und derselben benchmark_id,
                        ungeglätteter Mittelwert, 0.5 ohne passende Labels
Konstant(p_train)       globale Trainingsquote (benchmark-balanciert)
BetaBinomial(al, be)    geglätteter Paar-Mittelwert (al + k) / (al + be + n); Prior aus Trainings-Paarquoten
"""
class Konstant:
    def __init__(self, p=0.5):
        self.p = float(p)

    def wahrscheinlichkeit(self, input, labeled=None):
        return self.p


def _zaehle(input, labeled):
    """Wie das Original: Subjekt-Dict muss vollständig gleich sein, benchmark_id gleich."""
    subject, item = input
    bid = (item or {}).get("benchmark_id") or ""
    k = n = 0
    for (s, it), lab in labeled or []:
        if (it.get("benchmark_id") or "") == bid and s == subject:
            k += 1 if float(lab) >= 0.5 else 0
            n += 1
    return k, n


class EmpirischerMittelwert:
    def wahrscheinlichkeit(self, input, labeled=None):
        k, n = _zaehle(input, labeled)
        return k / n if n else 0.5


class BetaBinomial:
    def __init__(self, alpha, beta):
        self.alpha, self.beta = float(alpha), float(beta)

    def wahrscheinlichkeit(self, input, labeled=None):
        k, n = _zaehle(input, labeled)
        return (self.alpha + k) / (self.alpha + self.beta + n)


def beta_prior(raten_je_benchmark):
    """Momentenmethode, benchmark-balanciert. raten_je_benchmark: Liste von Listen der Paarquoten."""
    mittel_b = [sum(r) / len(r) for r in raten_je_benchmark if r]
    zweit_b = [sum(x * x for x in r) / len(r) for r in raten_je_benchmark if r]
    mu = sum(mittel_b) / len(mittel_b)
    var = sum(zweit_b) / len(zweit_b) - mu * mu
    s = max(mu * (1 - mu) / max(var, 1e-6) - 1.0, 0.1)
    return mu * s, (1 - mu) * s, mu
