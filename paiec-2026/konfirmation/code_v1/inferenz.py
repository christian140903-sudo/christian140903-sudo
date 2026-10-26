"""Hierarchischer logistischer Prädiktor auf Paarebene — NUR Standardbibliothek (geht unverändert ins Paket).

Modell für die Erfolgsquote r eines Subjekt-Benchmark-Paares (Items zufällig gezogen, je Item eine Antwort):
    logit r_sb = c_b + a_b * m_s + v_sb
  m_s     Subjekt-Fähigkeit aus dem Training (Lookup über normalized_name), sonst Metadaten-Regression
  c_b     Benchmark-Lage, Prior N(mu_c, tau_c2) — kalter Start, Posterior aus den Labels ALLER Subjekte des Benchmarks
  a_b     Benchmark-Steigung auf der Fähigkeit, Prior N(lam, tau_l2) — dito
  v_sb    Paar-Abweichung, Prior N(0, s2_s) mit s2_s = tau_v2 + kappa * V_s (V_s = Unsicherheit von m_s),
          für unbekannte Subjekte s2_unk
Item-Stufe (optional, tau_i2 > 0): Labels ANDERER Subjekte zum selben Item (gleicher Text + Merkmale, gleiche
benchmark_id) verschieben das Zielitem um d_i ~ N(0, tau_i2); ohne solche Labels bleibt die Paarvorhersage exakt.
Labels y ~ Bernoulli(sigma(logit r_sb)). Posterior von (c, a, v_1..v_G) per Laplace; die Hesse-Matrix ist eine
Pfeilspitze mit 2x2-Kopf, Newton-Schritte exakt in O(G) über das Schur-Komplement. Vorhersage = Posterior-Mittel
von sigma(eta) per Probit-Näherung sigma(m / sqrt(1 + pi*var/8)); danach optional Platt je Budget-Stufe.
"""
import hashlib
import json
import math

from merkmale import konfig, meta_merkmale, name_schluessel

STUFEN = (0, 1, 3, 7, 15, 31)


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def logit(p):
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(p / (1.0 - p))


def _log1pexp(x):
    return x + math.log1p(math.exp(-x)) if x > 0 else math.log1p(math.exp(x))


def stufe(n):
    s = 0
    for b in STUFEN:
        if n >= b:
            s = b
    return s


def posterior(gruppen, mu_c, tau_c2, lam, tau_l2, iter_max=60):
    """gruppen: Liste (m, s2, k, n) je Subjekt-Gruppe mit Labels in diesem Benchmark.
    -> dict c, a, v[], d[], h[], Sigma_kopf (2x2 als (scc, sca, saa))."""
    G = len(gruppen)
    c, a = mu_c, lam
    v = [0.0] * G

    def ziel(c, a, v):
        f = (c - mu_c) ** 2 / (2 * tau_c2) + (a - lam) ** 2 / (2 * tau_l2)
        for (m, s2, k, n), vg in zip(gruppen, v):
            e = c + a * m + vg
            f += n * _log1pexp(e) - k * e + vg * vg / (2 * s2)
        return f

    f_alt = ziel(c, a, v)
    h = [0.0] * G
    d = [0.0] * G
    for _ in range(iter_max):
        gc = (c - mu_c) / tau_c2
        ga = (a - lam) / tau_l2
        acc, aca, aaa = 1.0 / tau_c2, 0.0, 1.0 / tau_l2
        rc = ra = 0.0
        gv = [0.0] * G
        for j, ((m, s2, k, n), vg) in enumerate(zip(gruppen, v)):
            p = sigmoid(c + a * m + vg)
            r = n * p - k
            hh = n * p * (1.0 - p)
            gc += r
            ga += r * m
            g_v = r + vg / s2
            dd = hh + 1.0 / s2
            acc += hh - hh * hh / dd
            aca += hh * m - hh * hh * m / dd
            aaa += hh * m * m - hh * hh * m * m / dd
            rc += hh * g_v / dd
            ra += hh * m * g_v / dd
            gv[j], h[j], d[j] = g_v, hh, dd
        det = acc * aaa - aca * aca
        b1, b2 = -gc + rc, -ga + ra
        x0 = (aaa * b1 - aca * b2) / det
        x1 = (acc * b2 - aca * b1) / det
        dv = [(-gv[j] - h[j] * x0 - h[j] * gruppen[j][0] * x1) / d[j] for j in range(G)]
        schritt = 1.0
        while True:
            c_n, a_n = c + schritt * x0, a + schritt * x1
            v_n = [vg + schritt * dx for vg, dx in zip(v, dv)]
            f_neu = ziel(c_n, a_n, v_n)
            if f_neu <= f_alt + 1e-12 or schritt < 1e-4:
                break
            schritt *= 0.5
        delta = max([abs(schritt * x0), abs(schritt * x1)] + [abs(schritt * dx) for dx in dv])
        c, a, v, f_alt = c_n, a_n, v_n, f_neu
        if delta < 1e-9:
            break
    # Krümmung am Modus
    acc, aca, aaa = 1.0 / tau_c2, 0.0, 1.0 / tau_l2
    for j, ((m, s2, k, n), vg) in enumerate(zip(gruppen, v)):
        p = sigmoid(c + a * m + vg)
        hh = n * p * (1.0 - p)
        dd = hh + 1.0 / s2
        acc += hh - hh * hh / dd
        aca += hh * m - hh * hh * m / dd
        aaa += hh * m * m - hh * hh * m * m / dd
        h[j], d[j] = hh, dd
    det = acc * aaa - aca * aca
    return {"c": c, "a": a, "v": v, "h": h, "d": d, "m": [g[0] for g in gruppen],
            "S": (aaa / det, -aca / det, acc / det)}


def praediktiv(post, idx, m_t, s2_t):
    """Mittel und Varianz von eta für das Zielsubjekt. idx = Gruppenindex oder None (keine eigenen Labels)."""
    scc, sca, saa = post["S"]
    var_kopf = scc + 2 * m_t * sca + m_t * m_t * saa
    if idx is None:
        return post["c"] + post["a"] * m_t, var_kopf + s2_t
    hh, dd = post["h"][idx], post["d"][idx]
    # b = (hh, hh*m_t); Sigma_kopf b
    sb0 = scc * hh + sca * hh * m_t
    sb1 = sca * hh + saa * hh * m_t
    u_sb = sb0 + m_t * sb1
    b_sb = hh * sb0 + hh * m_t * sb1
    var = var_kopf - 2.0 * u_sb / dd + 1.0 / dd + b_sb / (dd * dd)
    return post["c"] + post["a"] * m_t + post["v"][idx], var


def wahrscheinlichkeit_aus(mittel, var):
    return sigmoid(mittel / math.sqrt(1.0 + math.pi * max(var, 0.0) / 8.0))


class Modell:
    """state: dict aus training.exportiere(); Schalter für Ablationen."""

    def __init__(self, state, subjektwissen=True, steigung=True, kalibrierung=True, item_effekt=True):
        self.state = state
        self.theta = state["theta"]
        self.meta_b0 = state["meta"]["b0"]
        self.meta_w = state["meta"]["w"]
        hy = state["hyp"] if subjektwissen else state["hyp_null"]
        self.mu_c, self.tau_c2 = hy["mu_c"], hy["tau_c2"]
        self.lam = hy["lam"]
        self.tau_l2 = hy["tau_l2"] if steigung else 1e-8
        self.tau_v2, self.kappa, self.s2_unk = hy["tau_v2"], hy["kappa"], hy["s2_unk"]
        self.subjektwissen = subjektwissen
        self.platt = {int(k): tuple(v) for k, v in (state.get("platt") or {}).items()} if kalibrierung else {}
        self.clip = state.get("clip", 1e-4)
        self.tau_i2 = float(state["hyp"].get("tau_i2", 0.0)) if item_effekt else 0.0
        self._prior_cache = {}
        self.leere_cache()

    # --- Subjekt-Prior ---
    def subjekt_prior(self, subject):
        key = konfig(subject)
        if key in self._prior_cache:
            return self._prior_cache[key]
        if not self.subjektwissen:
            out = (0.0, self.s2_unk)
        else:
            nk = name_schluessel(subject)
            if nk is not None and nk in self.theta:
                m, V = self.theta[nk]
                out = (m, self.tau_v2 + self.kappa * V)
            else:
                x = meta_merkmale(subject)
                m = self.meta_b0 + sum(self.meta_w.get(f, 0.0) * w for f, w in x.items())
                out = (m, self.s2_unk)
        self._prior_cache[key] = out
        return out

    # --- Labels gruppieren (einmal je Label-Menge) ---
    @staticmethod
    def fingerabdruck(labeled):
        hsh = hashlib.sha1(str(len(labeled)).encode())
        for (subj, it), lab in labeled:
            text = str(it.get("item_content", "") or "")
            hsh.update(("%s\x1f%s\x1f%d\x1f%s\x1f%s\x1e" % (it.get("benchmark_id", ""), konfig(subj), len(text),
                                                          text[:64], "1" if float(lab) >= 0.5 else "0")).encode())
        return hsh.hexdigest()

    def leere_cache(self):
        self._fp, self._gruppen, self._items, self._post, self._ipost = None, {}, {}, {}, {}

    @staticmethod
    def item_schluessel(item):
        """Item-Identität zur Testzeit: Text + Merkmale (interactors gehören zur Antwort, nicht zum Item)."""
        text = str((item or {}).get("item_content", "") or "")
        merk = str((item or {}).get("item_features", "") or "")
        return (text + "\x1f" + merk) if (text or merk) else None

    # Laufzeit-Begrenzung (REVIEW M3, 2026-10-20): bis VOLL_BIS Labels exakter Fingerabdruck über alle Labels (alte
    # Fassung, unverändert); darüber ein Stichproben-Schlüssel aus Länge + STICHPROBE gleich verteilten Einträgen
    # (inkl. erstem und letztem), Kosten je Aufruf unabhängig von |labeled|. Er verwechselt zwei Label-Mengen nur, wenn
    # sie gleich lang sind, an allen Stichprobenpositionen übereinstimmen und nacheinander ohne leere_cache() an
    # dasselbe Modell gehen. Auf der Plattform wächst |labeled| je Checkpoint streng (verschachtelte Budgets, je Paar
    # >= 40 Akquise-Items >= 31), innerhalb eines Checkpoints ist labeled für alle Ziele gleich.
    VOLL_BIS = 1024
    STICHPROBE = 64

    @classmethod
    def stichproben_schluessel(cls, labeled):
        n = len(labeled)
        k = cls.STICHPROBE
        pos = sorted({(j * (n - 1)) // (k - 1) for j in range(k)})
        hsh = hashlib.sha1(("s%d" % n).encode())
        for i in pos:
            (subj, it), lab = labeled[i]
            text = str(it.get("item_content", "") or "")
            hsh.update(("%d\x1f%s\x1f%s\x1f%d\x1f%s\x1f%s\x1e" % (i, it.get("benchmark_id", ""), konfig(subj), len(text),
                                                              text[:64], "1" if float(lab) >= 0.5 else "0")).encode())
        return "s" + hsh.hexdigest()

    def _bereite(self, labeled):
        if not labeled:
            # Budget 0: nie Gruppen aus einer früheren Label-Menge weiterverwenden (Leck, 2026-10-20 gefunden)
            self._fp, self._gruppen, self._items, self._post, self._ipost = "", {}, {}, {}, {}
            return
        if len(labeled) > self.VOLL_BIS:
            fp = self.stichproben_schluessel(labeled)
            self._liste = None  # Schnellpfad der exakten Fassung nie mit einer großen Liste mischen
            if fp == self._fp:
                return
        else:
            # Schnellpfad: dasselbe Listenobjekt (Referenz gehalten -> keine id-Wiederverwendung), gleiche Länge,
            # gleiche Ränder, gleiche Label-Summe -> Fingerabdruck sparen. In-place-Änderungen der Mitte ohne
            # Label-Änderung würden nicht erkannt; die Plattform baut labeled je Ereignis neu (streaming_ingestion.py).
            summe = sum(1 for _, lab in labeled if float(lab) >= 0.5)
            if (self._fp and labeled is getattr(self, "_liste", None) and len(labeled) == self._schnell[0]
                    and summe == self._schnell[1] and labeled[0] == self._rand[0] and labeled[-1] == self._rand[1]):
                return
            fp = self.fingerabdruck(labeled)
            self._liste, self._schnell, self._rand = labeled, (len(labeled), summe), (labeled[0], labeled[-1])
            if fp == self._fp:
                return
        gruppen, items = {}, {}
        for (subj, it), lab in labeled:
            bid = it.get("benchmark_id") or ""
            if not bid:
                continue
            g = gruppen.setdefault(bid, {})
            kf = konfig(subj)
            if kf not in g:
                m, s2 = self.subjekt_prior(subj)
                g[kf] = [m, s2, 0.0, 0.0]
            y = 1.0 if float(lab) >= 0.5 else 0.0
            g[kf][2] += y
            g[kf][3] += 1.0
            if self.tau_i2 > 0:
                ik = self.item_schluessel(it)
                if ik is not None:
                    items.setdefault(bid, {}).setdefault(ik, []).append((kf, y))
        self._fp, self._gruppen, self._items, self._post, self._ipost = fp, gruppen, items, {}, {}

    def _posterior(self, bid):
        if bid not in self._post:
            g = self._gruppen.get(bid, {})
            schl = list(g.keys())
            post = posterior([tuple(g[k]) for k in schl], self.mu_c, self.tau_c2, self.lam, self.tau_l2)
            post["index"] = {k: i for i, k in enumerate(schl)}
            post["n"] = [g[k][3] for k in schl]
            post["p_kal"] = {}
            self._post[bid] = post
        return self._post[bid]

    def kalibriere(self, p, n_eigen):
        ab = self.platt.get(stufe(n_eigen))
        if ab:
            p = sigmoid(ab[0] * logit(p) + ab[1])
        return min(max(p, self.clip), 1.0 - self.clip)

    def _p_gruppe(self, bid, kf):
        """Kalibrierte Paar-Wahrscheinlichkeit einer Gruppe mit Labels (für die Item-Stufe)."""
        post = self._posterior(bid)
        if kf not in post["p_kal"]:
            idx = post["index"][kf]
            g = self._gruppen[bid][kf]
            mittel, var = praediktiv(post, idx, g[0], g[1])
            post["p_kal"][kf] = self.kalibriere(wahrscheinlichkeit_aus(mittel, var), post["n"][idx])
        return post["p_kal"][kf]

    def _item_post(self, bid, ik):
        """Posterior der Item-Abweichung d ~ N(0, tau_i2) aus Labels aller Subjekte zu diesem Item.
        Bedingte Logits beta_t = logit(p_t) * c, c = sqrt(1 + pi tau_i2 / 8) (inverse Probit-Näherung), damit ohne
        Item-Labels exakt die Paar-Wahrscheinlichkeit herauskommt."""
        key = (bid, ik)
        if key in self._ipost:
            return self._ipost[key]
        c = math.sqrt(1.0 + math.pi * self.tau_i2 / 8.0)
        obs = [(logit(self._p_gruppe(bid, kf)) * c, y) for kf, y in self._items[bid][ik]]
        d = 0.0
        for _ in range(50):
            g, h = d / self.tau_i2, 1.0 / self.tau_i2
            for bt, y in obs:
                p = sigmoid(bt + d)
                g += p - y
                h += p * (1.0 - p)
            schritt = max(min(g / h, 3.0), -3.0)
            d -= schritt
            if abs(schritt) < 1e-10:
                break
        h = 1.0 / self.tau_i2 + sum(sigmoid(bt + d) * (1.0 - sigmoid(bt + d)) for bt, _ in obs)
        self._ipost[key] = (d, 1.0 / h, c)
        return self._ipost[key]

    def wahrscheinlichkeit(self, input, labeled=None):
        subject, item = input
        m_t, s2_t = self.subjekt_prior(subject)
        bid = (item or {}).get("benchmark_id") or ""
        self._bereite(labeled or [])
        if bid and bid in self._gruppen:
            post = self._posterior(bid)
            idx = post["index"].get(konfig(subject))
            n_eigen = post["n"][idx] if idx is not None else 0
        else:
            post = posterior([], self.mu_c, self.tau_c2, self.lam, self.tau_l2) if not hasattr(self, "_leer") \
                else self._leer
            self._leer = post
            idx, n_eigen = None, 0
        mittel, var = praediktiv(post, idx, m_t, s2_t)
        p = self.kalibriere(wahrscheinlichkeit_aus(mittel, var), n_eigen)
        if self.tau_i2 > 0 and bid in self._items:
            ik = self.item_schluessel(item)
            if ik is not None and ik in self._items[bid]:
                d, v, c = self._item_post(bid, ik)
                p = sigmoid((logit(p) * c + d) / math.sqrt(1.0 + math.pi * v / 8.0))
                p = min(max(p, self.clip), 1.0 - self.clip)
        return float(p)


def lade(pfad):
    with open(pfad, encoding="utf-8") as f:
        return Modell(json.load(f))
