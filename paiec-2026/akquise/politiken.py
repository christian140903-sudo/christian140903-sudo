"""Akquise-Politiken für den Strom-Simulator — NUR Standardbibliothek (eine davon könnte später labeling.py werden;
im Paket ist KEINE, BAUPLAN-V2 §2.2 P5).

Schnittstelle je Politik (wie die Plattform-Hook, D-akquise §1.1):
    entscheide(input, prediction, labeled, context) -> bool
Der `Entscheider` hält je Politik einen Cache (inkrementell über `labeled`, append-only; bei Verletzung voller
Neuaufbau) und fällt bei JEDER Ausnahme auf die exakte Plattform-Zufallsreplik zurück (Fehlerfall F5, Zähler).

Plattform-Zufallsregel (paiec_baseline@cc88a959 tools/streaming_ingestion.py, Zweig hook.mode == "random"):
    key = json.dumps([context, input], sort_keys=True, separators=(",", ":"))
    uniform = int.from_bytes(sha256(key)[:8], "big") / 2**64
    query = uniform < min(1, labels_remaining / items_remaining)
Alle Politiken hier nutzen DIESELBE Uniforme als einzige Zufallsquelle (gemeinsame Zufallszahlen; Lemma 1: ohne
Fremdlabels kollabieren abdeckung/leicht_zuerst/information_naiv bit-identisch auf die Replik).
"""
import hashlib
import json
import math

FELDER = ("normalized_name", "provider", "release_date", "access_date", "harness", "harness_version",
          "reasoning_effort", "subject_features_extra")
MAX_LABELS = 31


def konfig(subject):
    return "\x1f".join("" if subject.get(f) is None else str(subject.get(f)) for f in FELDER)


def item_schluessel(item):
    """Wie inferenz.Modell.item_schluessel: Text + Merkmale; None ohne beides."""
    text = str((item or {}).get("item_content", "") or "")
    merk = str((item or {}).get("item_features", "") or "")
    return (text + "\x1f" + merk) if (text or merk) else None


def uniform(context, input):
    key = json.dumps([context, input], sort_keys=True, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") / 2 ** 64


def replik(input, prediction=None, labeled=None, context=None):
    """Exakte Plattform-Zufallsregel (Referenzpolitik `zufall`)."""
    u = uniform(context, input)
    return bool(u < min(1, context["labels_remaining"] / context["items_remaining"]))


def hook_pruefung(result):
    """Replik der Typprüfung in AcquisitionHook.__call__ (Fehlerfall F3: numpy.bool_ scheitert)."""
    if type(result) is not bool:
        raise ValueError("Streaming acquisition_function(input, prediction, labeled, context) must return a bool")
    return result


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def logit(p):
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


class Index:
    """Inkrementeller Parser von `labeled`: je benchmark_id -> {item_key: [(konfig, y), ...]} und je (bid, konfig) -> [k, n].
    Append-only vorausgesetzt; Längenrückgang oder geänderter letzter bekannter Eintrag -> voller Neuaufbau (F4-Schutz)."""

    def __init__(self):
        self.leere()

    def leere(self):
        self.n = 0
        self.letzter = None
        self.items = {}      # bid -> {ik: [(kf, y)]}
        self.eigen = {}      # (bid, kf) -> [k, n]
        self.fremd_je_bid = {}  # bid -> set(ik) mit Labels (irgendwelcher Konfig)

    def aktualisiere(self, labeled):
        labeled = labeled or []
        L = len(labeled)
        if L < self.n or (self.n and self.letzter is not None and labeled[self.n - 1] != self.letzter):
            self.leere()
        for (subj, it), lab in labeled[self.n:]:
            bid = it.get("benchmark_id") or ""
            kf = konfig(subj)
            y = 1 if float(lab) >= 0.5 else 0
            e = self.eigen.setdefault((bid, kf), [0, 0])
            e[0] += y
            e[1] += 1
            ik = item_schluessel(it)
            if ik is not None:
                self.items.setdefault(bid, {}).setdefault(ik, []).append((kf, y))
                self.fremd_je_bid.setdefault(bid, set()).add(ik)
        self.n = L
        self.letzter = labeled[L - 1] if L else None

    def fremdlabels(self, bid, ik, kf):
        return [y for k2, y in self.items.get(bid, {}).get(ik, []) if k2 != kf]

    def hat_fremd(self, bid, kf):
        """Gibt es im Benchmark irgendein Label einer ANDEREN Konfiguration?"""
        for (b, k2), (_, n) in self.eigen.items():
            if b == bid and k2 != kf and n > 0:
                return True
        return False

    def eigene(self, bid, kf):
        return self.eigen.get((bid, kf), [0, 0])


def _zweistufig(u, k, N, bevorzugt, f_hat):
    """Budgettreue zweistufige Regel (D-akquise §3.1 Nr. 3): bevorzugte Kandidaten kaufen mit min(1, k/(f N)),
    übrige mit max(0, (k - f N)/((1 - f) N)); Erwartung = k. f = 1 => identisch zur Plattformregel."""
    if N <= k:
        return True
    if bevorzugt:
        return u < min(1.0, k / (f_hat * N))
    if f_hat >= 1.0:
        return False
    return u < max(0.0, (k - f_hat * N) / ((1.0 - f_hat) * N))


class Entscheider:
    """Eine Politik mit Cache und Fallback. politik in POLITIKEN; `orakel` optional (nur orakel_d): dict mit
    'd' (item_key -> Schwierigkeit), 'pool' (pair_id -> Liste verbleibender item_keys, vom Simulator gepflegt),
    'mu', 'var' (Prior für b)."""

    def __init__(self, politik, orakel=None):
        if politik not in POLITIKEN:
            raise ValueError(politik)
        self.politik = politik
        self.index = Index()
        self.paar_cache = {}  # (bid, kf) -> [gesehen, bevorzugt_gesehen]
        self.orakel = orakel
        self.fallbacks = 0
        self.aufrufe = 0

    def __call__(self, input, prediction=None, labeled=None, context=None):
        self.aufrufe += 1
        try:
            ergebnis = POLITIKEN[self.politik](self, input, prediction, labeled, context)
            return bool(ergebnis)
        except Exception:
            self.fallbacks += 1
            return replik(input, prediction, labeled, context)

    # -- Hilfen
    def _basis(self, input, labeled, context):
        subject, item = input
        bid = item.get("benchmark_id") or ""
        kf = konfig(subject)
        self.index.aktualisiere(labeled)
        k, N = context["labels_remaining"], context["items_remaining"]
        return subject, item, bid, kf, k, N

    def _f_hat(self, bid, kf, bevorzugt):
        c = self.paar_cache.setdefault((bid, kf), [0, 0])
        f = min(1.0, max(0.05, (c[1] + 1.0) / (c[0] + 1.0)))
        c[0] += 1
        c[1] += 1 if bevorzugt else 0
        return f


# ------------------------------------------------------------------ Politiken
def p_zufall(E, input, prediction, labeled, context):
    return replik(input, prediction, labeled, context)


def p_abdeckung(E, input, prediction, labeled, context):
    """Stufe 1 (D §2.2): Kandidaten ohne Fremdlabel bevorzugen; ohne Fremdlabels im Benchmark exakt die Replik."""
    subject, item, bid, kf, k, N = E._basis(input, labeled, context)
    u = uniform(context, input)
    if not E.index.hat_fremd(bid, kf):
        return u < min(1, k / N)
    ik = item_schluessel(item)
    frei = ik is None or not E.index.fremdlabels(bid, ik, kf)
    return _zweistufig(u, k, N, frei, E._f_hat(bid, kf, frei))


def p_leicht_zuerst(E, input, prediction, labeled, context):
    """Verzerrungs-Demonstration: Items bevorzugen, deren Fremdlabels alle 1 sind (muss schaden)."""
    subject, item, bid, kf, k, N = E._basis(input, labeled, context)
    u = uniform(context, input)
    if not E.index.hat_fremd(bid, kf):
        return u < min(1, k / N)
    ik = item_schluessel(item)
    fl = E.index.fremdlabels(bid, ik, kf) if ik is not None else []
    bev = bool(fl) and all(y == 1 for y in fl)
    return _zweistufig(u, k, N, bev, E._f_hat(bid, kf, bev))


def p_information_naiv(E, input, prediction, labeled, context):
    """Stufe-2-Auswahl OHNE itembedingte Likelihood (Fehlerfall F2): Items mit Fremdlabels bevorzugen, deren
    geschätzte Erfolgswahrscheinlichkeit für dieses Subjekt nahe 0,5 liegt (p_i = sigma(b_hat + d_hat_i),
    b_hat aus eigenen Labels, d_hat_i aus Fremdlabels relativ zum Benchmark-Fremdmittel)."""
    subject, item, bid, kf, k, N = E._basis(input, labeled, context)
    u = uniform(context, input)
    if not E.index.hat_fremd(bid, kf):
        return u < min(1, k / N)
    ik = item_schluessel(item)
    fl = E.index.fremdlabels(bid, ik, kf) if ik is not None else []
    bev = False
    if fl:
        ke, ne = E.index.eigene(bid, kf)
        b_hat = logit((ke + 1.0) / (ne + 2.0))
        K = n = 0
        for (b2, k2), (kk, nn) in E.index.eigen.items():
            if b2 == bid and k2 != kf:
                K += kk
                n += nn
        r_bar = (K + 1.0) / (n + 2.0)
        r_i = (sum(fl) + 1.0) / (len(fl) + 2.0)
        d_hat = logit(r_i) - logit(r_bar)
        bev = abs(sigmoid(b_hat + d_hat) - 0.5) <= 0.2
    return _zweistufig(u, k, N, bev, E._f_hat(bid, kf, bev))


def p_unsicherheit(E, input, prediction, labeled, context):
    """Veranstalter-Politik ble/labeling.py: Zwangskauf, sonst |prediction - 0,5| <= 0,15 (prediction = Itemvorhersage
    des Paketmodells, vom Simulator geliefert)."""
    if prediction is None:
        raise ValueError("unsicherheit braucht prediction")
    k, N = context["labels_remaining"], context["items_remaining"]
    if k <= 0:
        return False
    return bool(N <= k or abs(prediction - 0.5) <= 0.15)


def p_unsicherheit_em(E, input, prediction, labeled, context):
    """Dieselbe Regel mit Empirical-Mean-Vorhersage aus eigenen Labels (0,5 ohne Labels) — Veranstalter-Baseline-Paar."""
    subject, item, bid, kf, k, N = E._basis(input, labeled, context)
    if k <= 0:
        return False
    ke, ne = E.index.eigene(bid, kf)
    p = ke / ne if ne else 0.5
    return bool(N <= k or abs(p - 0.5) <= 0.15)


def p_orakel_d(E, input, prediction, labeled, context):
    """Obergrenze eigener Hebel im Strom: bekannte LOO-Schwierigkeit d_i (Orakel), b_hat Laplace-Modus aus eigenen
    Labels mit bekannten d; kaufen, wenn |b_hat + d_i| unter den k kleinsten der verbleibenden Pool-Items liegt."""
    subject, item, bid, kf, k, N = E._basis(input, labeled, context)
    if N <= k:
        return True
    O = E.orakel
    d = O["d"]
    ik = item_schluessel(item)
    keys, pos = O["pool"][(bid, kf)]  # alle Kandidatenschlüssel des Paares + Position (vom Simulator gepflegt)
    pool = keys[pos:]  # verbleibende inkl. aktuellem
    # eigene Labels mit d
    obs = [(d.get(k2, 0.0), y) for (k2, y) in O["eigen"].get((bid, kf), [])]
    b = O["mu"]
    for _ in range(30):
        g, h = (b - O["mu"]) / O["var"], 1.0 / O["var"]
        for di, y in obs:
            p = sigmoid(b + di)
            g += p - y
            h += p * (1.0 - p)
        s = max(min(g / h, 2.0), -2.0)
        b -= s
        if abs(s) < 1e-8:
            break
    werte = sorted(abs(b + d.get(j, 0.0)) for j in pool)
    schwelle = werte[min(k, len(werte)) - 1]
    return abs(b + d.get(ik, 0.0)) <= schwelle


POLITIKEN = {"zufall": p_zufall, "abdeckung": p_abdeckung, "leicht_zuerst": p_leicht_zuerst,
             "information_naiv": p_information_naiv, "unsicherheit_0.15": p_unsicherheit,
             "unsicherheit_em": p_unsicherheit_em, "orakel_d": p_orakel_d}
BRAUCHT_VORHERSAGE = {"unsicherheit_0.15"}
