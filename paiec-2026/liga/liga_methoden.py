"""Gegenmethoden der Methoden-Liga — Schnittstelle wie inferenz.Modell: wahrscheinlichkeit(input, labeled), leere_cache().

Jede Methode rekonstruiert alles aus `labeled` (Gruppierung einmal je Label-Menge: Listenidentität nach leere_cache(),
sonst Fingerabdruck). Zur Testzeit sichtbar sind nur die 8 Subjektfelder, benchmark_id, item_content (Platzhalter) und die
Labels des Laufs. Das Attribut `tau_i2 > 0` ist für den Simulator das Signal „Items mit Fremdlabels einzeln vorhersagen"
(Flag, kein Modellparameter).

Familien:
  IRT     1PL/2PL: Fähigkeit theta je Name aus einem Item-IRT-Fit auf den Trainingsbenchmarks (irt_fit); zur Testzeit
          Benchmark-Lage c_b (2PL: + Steigung a_b) als MAP/Laplace aus den Labels aller Subjekte des Laufs; theta bekannter
          Subjekte mit Prior N(theta_hat, kappa*V), unbekannte N(0, s2_unk); Item-Effekte d_i ~ N(0, sigma_i2) aus Fremdlabels.
  MF      Matrixfaktorisierung Rang r der Paar-Logit-Matrix (Namen x Trainingsbenchmarks, mf_fit); zur Testzeit
          Benchmark-Vektor (c_b, a_b in R^r) + Paar-Abweichung v_g per dichtem Newton/Laplace.
  KNN     Ähnlichkeit zwischen Namen aus gemeinsamen Trainingsbenchmarks (zentrierte Paar-Logits), online gewichtete
          Beta-Binomial-Mischung der Labels der Nachbarn im Lauf; Item-Stufe: gewichtete Fremdlabels zum selben Item.
  GB      Gradient Boosting (sklearn HistGradientBoostingClassifier) auf sichtbaren Subjekt-/Item-Merkmalen + Online-
          Statistiken; Trainingszeilen aus simulierten Läufen auf den Trainingsbenchmarks (gb_zeilen).
"""
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modell"))
from inferenz import Modell, posterior, praediktiv, sigmoid, logit, wahrscheinlichkeit_aus  # noqa: E402
from merkmale import konfig, name_schluessel, jahr, groesse_mrd  # noqa: E402

CLIP = 1e-4


def _clip(p):
    return min(max(float(p), CLIP), 1.0 - CLIP)


def gruppiere(labeled):
    """-> gr: bid -> {konfig: {"subject", "k", "n"}};  items: bid -> {item_schluessel: [(konfig, y), ...]}"""
    gr, items = {}, {}
    for (subj, it), lab in labeled:
        bid = it.get("benchmark_id") or ""
        if not bid:
            continue
        kf = konfig(subj)
        g = gr.setdefault(bid, {})
        if kf not in g:
            g[kf] = {"subject": subj, "k": 0.0, "n": 0.0}
        y = 1.0 if float(lab) >= 0.5 else 0.0
        g[kf]["k"] += y
        g[kf]["n"] += 1.0
        ik = Modell.item_schluessel(it)
        if ik is not None:
            items.setdefault(bid, {}).setdefault(ik, []).append((kf, y))
    return gr, items


class Basis:
    tau_i2 = 0.0

    def __init__(self):
        self._sub = {}
        self.leere_cache()

    def leere_cache(self):
        self._liste, self._fp, self._gr, self._items, self._c = None, None, {}, {}, {}

    def _bereite(self, labeled):
        if not labeled:
            if self._gr or self._c:
                self.leere_cache()
            return
        if labeled is self._liste:
            return
        fp = Modell.fingerabdruck(labeled)
        if fp == self._fp:
            self._liste = labeled
            return
        self.leere_cache()
        self._liste, self._fp = labeled, fp
        self._gr, self._items = gruppiere(labeled)

    def wahrscheinlichkeit(self, input, labeled=None):
        subject, item = input
        self._bereite(labeled or [])
        bid = (item or {}).get("benchmark_id") or ""
        kf = konfig(subject)
        p = self._paar(bid, kf, subject)
        if self.tau_i2 > 0 and bid in self._items:
            ik = Modell.item_schluessel(item)
            if ik is not None and ik in self._items[bid]:
                p = self._item(bid, ik, kf, p)
        q = _clip(p)
        if q != q:
            raise ValueError("NaN")
        return q

    def _paar(self, bid, kf, subject):
        raise NotImplementedError

    def _item(self, bid, ik, kf, p):
        return p


# ------------------------------------------------------------------ Item-Effekt (MAP, gemeinsam für IRT/MF)
def item_effekt(obs_logits, ys, sigma_i2):
    """d ~ N(0, sigma_i2); obs: Logits der Gruppen-Vorhersagen und Labels. -> (d, var)"""
    d = 0.0
    for _ in range(50):
        g, h = d / sigma_i2, 1.0 / sigma_i2
        for bt, y in zip(obs_logits, ys):
            p = sigmoid(bt + d)
            g += p - y
            h += p * (1.0 - p)
        s = max(min(g / h, 3.0), -3.0)
        d -= s
        if abs(s) < 1e-10:
            break
    h = 1.0 / sigma_i2 + sum(sigmoid(bt + d) * (1.0 - sigmoid(bt + d)) for bt in obs_logits)
    return d, 1.0 / h


class ItemMixin:
    """Item-Stufe über die Paar-Logits der Gruppen (self._p_gruppe(bid, kf) muss existieren)."""

    def _item(self, bid, ik, kf, p):
        key = (bid, ik)
        if key not in self._c:
            obs = self._items[bid][ik]
            lg = [logit(self._p_gruppe(bid, k)) for k, _ in obs]
            self._c[key] = item_effekt(lg, [y for _, y in obs], self.sigma_i2)
        d, v = self._c[key]
        if self.laplace:
            return sigmoid((logit(p) + d) / math.sqrt(1.0 + math.pi * v / 8.0))
        return sigmoid(logit(p) + d)


# ------------------------------------------------------------------ IRT (1PL / 2PL)
class IRT(ItemMixin, Basis):
    def __init__(self, fit, tau_c2=1.5, s2_unk=1.0, kappa=1.0, laplace=True, zweipl=False, tau_a2=0.3,
                 sigma_i2=0.0):
        super().__init__()
        self.theta = fit["theta"]
        self.mu_c = float(fit["mu_c"])
        self.tau_c2, self.s2_unk, self.kappa, self.laplace = tau_c2, s2_unk, kappa, laplace
        self.lam = 1.0
        self.tau_l2 = tau_a2 if zweipl else 1e-8
        self.sigma_i2 = sigma_i2
        self.tau_i2 = 1.0 if sigma_i2 > 0 else 0.0

    def prior(self, subject):
        kf = konfig(subject)
        if kf not in self._sub:
            nk = name_schluessel(subject)
            if nk is not None and nk in self.theta:
                th, V = self.theta[nk]
                self._sub[kf] = (float(th), self.kappa * float(V))
            else:
                self._sub[kf] = (0.0, self.s2_unk)
        return self._sub[kf]

    def _post(self, bid):
        key = ("post", bid)
        if key not in self._c:
            g = self._gr.get(bid, {})
            schl = list(g.keys())
            gruppen = []
            for k in schl:
                m, s2 = self.prior(g[k]["subject"])
                gruppen.append((m, s2, g[k]["k"], g[k]["n"]))
            post = posterior(gruppen, self.mu_c, self.tau_c2, self.lam, self.tau_l2)
            post["index"] = {k: i for i, k in enumerate(schl)}
            self._c[key] = post
        return self._c[key]

    def _vorher(self, mittel, var):
        return wahrscheinlichkeit_aus(mittel, var) if self.laplace else sigmoid(mittel)

    def _paar(self, bid, kf, subject):
        m_t, s2_t = self.prior(subject)
        post = self._post(bid)
        idx = post["index"].get(kf)
        mittel, var = praediktiv(post, idx, m_t, s2_t)
        return self._vorher(mittel, var)

    def _p_gruppe(self, bid, kf):
        key = ("pg", bid, kf)
        if key not in self._c:
            self._c[key] = _clip(self._paar(bid, kf, self._gr[bid][kf]["subject"]))
        return self._c[key]


def irt_fit(agg, sub_names, b_codes, zweipl=False, max_items=2000, iter_n=40, seed=0, protokoll=None):
    """Item-IRT auf den Trainingsbenchmarks, nur Subjekte mit Namen (übertragbare Einheit), Items je Benchmark gekappt.
    1PL: logit p = theta_u - b_i;  2PL: a_i (theta_u - b_i), a_i = exp(alpha_i), Ridge alpha ~ N(0, 0.25).
    theta auf Mittel 0 / Streuung 1 normiert (Skala). -> {"theta": {name: [theta, V]}, "mu_c": mittlere Benchmark-Lage}
    """
    rng = np.random.default_rng(seed)
    import pandas as pd
    # Speicher: eine Maske, dann je Benchmark Items kappen; Zwischenstücke sofort freigeben (OOM-Lehre 2026-10-20)
    m = agg.b_code.isin(b_codes).values & agg.s_code.isin(sub_names.index).values
    a = agg.loc[m, ["b_code", "s_code", "i_code", "n", "k"]]
    del m
    teile = []
    for b, g in a.groupby("b_code", sort=False):
        its = g.i_code.unique()
        if len(its) > max_items:
            g = g[g.i_code.isin(rng.choice(its, max_items, replace=False))]
        teile.append(g)
    del a
    a = pd.concat(teile, ignore_index=True)
    del teile
    namen = a.s_code.map(sub_names).values
    ui, units = pd.factorize(namen)
    ii, _ = pd.factorize(a.i_code.values)
    bi, bcodes = pd.factorize(a.b_code.values)
    k = a.k.values.astype(float) / a.n.values.astype(float)  # Erfolgsquote je (Subjekt, Item) als EINE Beobachtung
    n = np.ones_like(k)                                        # (Wiederholungen eines Items sind korreliert; vgl. training.py)
    U, I = len(units), ii.max() + 1
    th = np.zeros(U)
    r = (np.bincount(ii, k, I) + 0.5) / (np.bincount(ii, n, I) + 1.0)
    b = -np.log(r / (1 - r))
    al = np.zeros(I)
    for it in range(iter_n):
        A = np.exp(al)
        eta = np.clip(A[ii] * (th[ui] - b[ii]), -30, 30)
        p = 1 / (1 + np.exp(-eta))
        w = n * p * (1 - p)
        res = n * p - k
        # Items (b, bei 2PL auch alpha)
        gb = np.bincount(ii, -A[ii] * res, I) + b / 10.0
        hb = np.bincount(ii, A[ii] ** 2 * w, I) + 0.1
        b = np.clip(b - np.clip(gb / hb, -2, 2), -12, 12)
        if zweipl and it >= 5:
            eta = np.clip(A[ii] * (th[ui] - b[ii]), -30, 30)
            p = 1 / (1 + np.exp(-eta))
            w = n * p * (1 - p)
            res = n * p - k
            ga = np.bincount(ii, res * eta, I) + al / 0.25
            ha = np.bincount(ii, w * eta * eta, I) + 1 / 0.25
            al = np.clip(al - np.clip(ga / ha, -1, 1), math.log(0.2), math.log(5.0))
            A = np.exp(al)
        eta = np.clip(A[ii] * (th[ui] - b[ii]), -30, 30)
        p = 1 / (1 + np.exp(-eta))
        w = n * p * (1 - p)
        res = n * p - k
        gt = np.bincount(ui, A[ii] * res, U) + th
        ht = np.bincount(ui, A[ii] ** 2 * w, U) + 1.0
        th = np.clip(th - np.clip(gt / ht, -2, 2), -12, 12)
        mu, sd = th.mean(), th.std()
        if sd > 0:
            th = (th - mu) / sd
            b = (b - mu) / sd
            al = np.clip(al + math.log(sd), math.log(0.2), math.log(5.0))
        if protokoll and it % 10 == 0:
            protokoll(f"    irt{'2' if zweipl else '1'} it {it}: nll/n {float(np.sum(n * np.logaddexp(0, eta) - k * eta) / n.sum()):.4f}")
    del a
    A = np.exp(al)
    eta = np.clip(A[ii] * (th[ui] - b[ii]), -30, 30)
    p = 1 / (1 + np.exp(-eta))
    V = 1.0 / (np.bincount(ui, A[ii] ** 2 * n * p * (1 - p), U) + 1.0)
    # Benchmark-Lage: mittlere -b je Benchmark (Items gleich gewichtet)
    lage = np.bincount(bi, -b[ii], len(bcodes)) / np.bincount(bi, minlength=len(bcodes))
    return {"theta": {str(u): [float(th[j]), float(V[j])] for j, u in enumerate(units)},
            "mu_c": float(np.mean(lage)), "sd_c": float(np.std(lage)), "n_items": int(I), "n_units": int(U),
            "zweipl": bool(zweipl)}


# ------------------------------------------------------------------ Matrixfaktorisierung
def mf_fit(p, rang=2, iter_n=60, tau_a2=4.0, protokoll=None):
    """ALS auf Paar-Logits l (Messvarianz vl): l = c_b + a_b . u_s + e, e ~ N(0, sig2 + vl); u ~ N(0, I), a ~ N(0, tau_a2 I).
    Einheiten wie training.py (Name, sonst eigene Einheit). Exportiert u nur für Namen.
    -> {"u": {name: [u...]}, "V": {name: var}, "mu_c", "tau_c2", "a0": mittlere Ladung, "rang"}"""
    import pandas as pd
    bi, b_codes = pd.factorize(p.b_code)
    ui, units = pd.factorize(p.einheit)
    l, vl = p.l.values, p.vl.values
    B, U, r = len(b_codes), len(units), rang
    c = np.bincount(bi, l, B) / np.bincount(bi, minlength=B)
    namen = np.array([not str(u).startswith("s:") for u in units])
    # Start: Rang-r-SVD der zentrierten, mit 0 aufgefüllten Einheiten-x-Benchmark-Matrix (Spalten orthogonal, kein Kollaps)
    Zm = np.zeros((U, B))
    Zm[ui, bi] = l - c[bi]
    uu, ss, vt = np.linalg.svd(Zm, full_matrices=False)
    Ua = uu[:, :r] * np.sqrt(ss[:r])
    A = (vt[:r].T * np.sqrt(ss[:r]))
    sd0 = Ua[namen].std(axis=0)
    sd0 = np.where(sd0 > 0, sd0, 1.0)
    Ua, A = Ua / sd0, A * sd0
    a0 = A.mean(axis=0)  # Prior-Mittel der Ladungen folgt den Daten (wie training.als: lam = mittel(a))
    sig2 = 1.0
    for it in range(iter_n):
        w = 1.0 / (sig2 + vl)
        # Einheiten
        Ab = A[bi]
        res = l - c[bi]
        for u in range(U):
            m = ui == u
            X = Ab[m]
            ww = w[m]
            M = X.T @ (X * ww[:, None]) + np.eye(r)
            Ua[u] = np.linalg.solve(M, X.T @ (ww * res[m]))
        # Benchmarks
        Uu = Ua[ui]
        X1 = np.concatenate([np.ones((len(l), 1)), Uu], axis=1)
        for b in range(B):
            m = bi == b
            X = X1[m]
            ww = w[m]
            M = X.T @ (X * ww[:, None]) + np.diag([1e-6] + [1.0 / tau_a2] * r)
            rhs = X.T @ (ww * l[m])
            rhs[1:] += a0 / tau_a2
            sol = np.linalg.solve(M, rhs)
            c[b], A[b] = sol[0], sol[1:]
        pred = c[bi] + np.sum(A[bi] * Ua[ui], axis=1)
        resid = l - pred
        je_b = np.bincount(bi, resid * resid - vl, B) / np.bincount(bi, minlength=B)
        sig2 = max(0.05, float(np.mean(je_b)))  # benchmark-balanciert wie training.als
        # Skala (Identifikation): u-Spalten über Namen auf Streuung 1, Ladungen entsprechend (wie training.als)
        sd = Ua[namen].std(axis=0)
        sd = np.where(sd > 1e-8, sd, 1.0)
        Ua /= sd
        A *= sd
        a0 = A.mean(axis=0)
        if protokoll and it % 20 == 0:
            protokoll(f"    mf r{rang} it {it}: sig2 {sig2:.3f}")
    w = 1.0 / (sig2 + vl)
    V = np.zeros(U)
    for u in range(U):
        m = ui == u
        V[u] = 1.0 / (float(np.sum(w[m] * np.sum(A[bi[m]] ** 2, axis=1))) / r + 1.0)
    out_u = {str(units[u]): Ua[u].tolist() for u in range(U) if namen[u]}
    out_V = {str(units[u]): float(V[u]) for u in range(U) if namen[u]}
    return {"u": out_u, "V": out_V, "mu_c": float(c.mean()), "tau_c2": float(c.var()), "a0": A.mean(axis=0).tolist(),
            "a_var": A.var(axis=0).tolist(), "rang": r, "sig2": sig2, "a_sd": A.std(axis=0).tolist()}


def _newton_dense(ng, kg, Xg, prior_m, prior_v):
    """MAP von x (dim D) bei eta_g = Xg[g] . x, Labels (k_g, n_g), Prior N(prior_m, diag(prior_v)). -> (x, H)"""
    D = len(prior_m)
    x = prior_m.copy()
    Pi = 1.0 / prior_v

    def ziel(x):
        eta = Xg @ x
        return float(np.sum(ng * np.logaddexp(0, eta) - kg * eta) + 0.5 * np.sum(Pi * (x - prior_m) ** 2))

    f = ziel(x)
    for _ in range(60):
        eta = Xg @ x
        p = 1 / (1 + np.exp(-eta))
        g = Xg.T @ (ng * p - kg) + Pi * (x - prior_m)
        H = Xg.T @ (Xg * (ng * p * (1 - p))[:, None]) + np.diag(Pi)
        dx = np.linalg.solve(H, g)
        s = 1.0
        while True:
            xn = x - s * dx
            fn = ziel(xn)
            if fn <= f + 1e-12 or s < 1e-4:
                break
            s *= 0.5
        delta = float(np.max(np.abs(s * dx)))
        x, f = xn, fn
        if delta < 1e-9:
            break
    eta = Xg @ x
    p = 1 / (1 + np.exp(-eta))
    H = Xg.T @ (Xg * (ng * p * (1 - p))[:, None]) + np.diag(Pi)
    return x, H


class MF(ItemMixin, Basis):
    def __init__(self, fit, tau_a2=0.5, s2_v=0.2, s2_unk=1.0, tau_c2=None, laplace=True, sigma_i2=0.0, kappa=1.0):
        super().__init__()
        self.u = fit["u"]
        self.Vu = fit["V"]
        self.r = int(fit["rang"])
        self.mu_c = float(fit["mu_c"])
        self.tau_c2 = float(fit["tau_c2"]) if tau_c2 is None else float(tau_c2)
        self.a0 = np.array(fit["a0"], dtype=float)
        self.tau_a2, self.s2_v, self.s2_unk, self.laplace, self.kappa = tau_a2, s2_v, s2_unk, laplace, kappa
        self.sigma_i2 = sigma_i2
        self.tau_i2 = 1.0 if sigma_i2 > 0 else 0.0

    def prior(self, subject):
        kf = konfig(subject)
        if kf not in self._sub:
            nk = name_schluessel(subject)
            if nk is not None and nk in self.u:
                self._sub[kf] = (np.array(self.u[nk], dtype=float), self.s2_v + self.kappa * self.Vu[nk])
            else:
                self._sub[kf] = (np.zeros(self.r), self.s2_unk)
        return self._sub[kf]

    def _post(self, bid):
        key = ("post", bid)
        if key not in self._c:
            g = self._gr.get(bid, {})
            schl = list(g.keys())
            G = len(schl)
            D = 1 + self.r + G
            Xg = np.zeros((G, D))
            ng = np.zeros(G)
            kg = np.zeros(G)
            pm = np.concatenate([[self.mu_c], self.a0, np.zeros(G)])
            pv = np.concatenate([[self.tau_c2], np.full(self.r, self.tau_a2), np.ones(G)])
            for j, k in enumerate(schl):
                u, s2 = self.prior(g[k]["subject"])
                Xg[j, 0] = 1.0
                Xg[j, 1:1 + self.r] = u
                Xg[j, 1 + self.r + j] = 1.0
                pv[1 + self.r + j] = s2
                ng[j], kg[j] = g[k]["n"], g[k]["k"]
            if G:
                x, H = _newton_dense(ng, kg, Xg, pm, pv)
                S = np.linalg.inv(H)
            else:
                x, S = pm, np.diag(pv)
            self._c[key] = {"x": x, "S": S, "index": {k: i for i, k in enumerate(schl)}, "G": G}
        return self._c[key]

    def _paar(self, bid, kf, subject):
        u, s2 = self.prior(subject)
        post = self._post(bid)
        idx = post["index"].get(kf)
        D = len(post["x"])
        e = np.zeros(D)
        e[0] = 1.0
        e[1:1 + self.r] = u
        if idx is not None:
            e[1 + self.r + idx] = 1.0
            var = float(e @ post["S"] @ e)
        else:
            var = float(e @ post["S"] @ e) + s2
        mittel = float(e @ post["x"])
        return wahrscheinlichkeit_aus(mittel, var) if self.laplace else sigmoid(mittel)

    def _p_gruppe(self, bid, kf):
        key = ("pg", bid, kf)
        if key not in self._c:
            self._c[key] = _clip(self._paar(bid, kf, self._gr[bid][kf]["subject"]))
        return self._c[key]


# ------------------------------------------------------------------ kNN über Subjekte
def knn_fit(p):
    """Zentrierte Paar-Logits z_ub = l_ub - mittel_b(l) je Name; paarweise mittlere quadrierte Differenz über gemeinsame
    Benchmarks (>= 2). -> {"namen": [...], "D": Matrix, "shared": Matrix, "zbar": {name: z}, "mu": globale Quote (logit)}"""
    import pandas as pd
    q = p[p.name != ""]
    cb = p.groupby("b_code").l.mean()
    z = q.l.values - q.b_code.map(cb).values
    ni, namen = pd.factorize(q.name)
    bi, bcodes = pd.factorize(q.b_code)
    Z = np.zeros((len(namen), len(bcodes)))
    M = np.zeros_like(Z)
    Z[ni, bi] = z
    M[ni, bi] = 1.0
    shared = M @ M.T
    Z2 = Z * Z
    sq = Z2 @ M.T + M @ Z2.T - 2 * Z @ Z.T
    with np.errstate(invalid="ignore", divide="ignore"):
        D = np.where(shared >= 2, sq / np.maximum(shared, 1), np.nan)
    zbar = {str(namen[j]): float(np.sum(Z[j]) / max(M[j].sum(), 1)) for j in range(len(namen))}
    mu = float(np.average(p.rate.values)) if "rate" in p.columns else 0.5
    return {"namen": [str(x) for x in namen], "D": D, "shared": shared, "zbar": zbar, "mu": mu,
            "l_global": float(cb.mean())}


class KNN(Basis):
    def __init__(self, fit, alpha=4.0, h=1.0, w0=0.2, beta=2.0, gamma=1.0, item=True):
        super().__init__()
        self.idx = {n: j for j, n in enumerate(fit["namen"])}
        self.D = fit["D"]
        self.zbar = fit["zbar"]
        self.l0 = fit["l_global"]
        self.alpha, self.h, self.w0, self.beta, self.gamma = alpha, h, w0, beta, gamma
        self.tau_i2 = 1.0 if item else 0.0

    def info(self, subject):
        kf = konfig(subject)
        if kf not in self._sub:
            nk = name_schluessel(subject)
            j = self.idx.get(nk) if nk is not None else None
            zb = self.zbar.get(nk, 0.0) if nk is not None else 0.0
            self._sub[kf] = (j, zb)
        return self._sub[kf]

    def gewicht(self, s_t, s_o):
        jt, _ = self.info(s_t)
        jo, _ = self.info(s_o)
        if jt is None or jo is None:
            return self.w0
        d = self.D[jt, jo]
        if d != d:
            return self.w0
        return math.exp(-d / (2.0 * self.h * self.h))

    def _paar(self, bid, kf, subject):
        key = ("p", bid, kf)
        if key in self._c:
            return self._c[key]
        _, zb = self.info(subject)
        p0 = sigmoid(self.l0 + self.gamma * zb)
        num, den = self.alpha * p0, self.alpha
        g = self._gr.get(bid, {})
        for k2, o in g.items():
            w = 1.0 if k2 == kf else self.gewicht(subject, o["subject"])
            num += w * o["k"]
            den += w * o["n"]
        self._c[key] = num / den
        return self._c[key]

    def _item(self, bid, ik, kf, p):
        subject = self._gr[bid][kf]["subject"] if kf in self._gr[bid] else None
        num, den = self.beta * p, self.beta
        for k2, y in self._items[bid][ik]:
            if k2 == kf:
                continue
            w = self.gewicht(subject, self._gr[bid][k2]["subject"]) if subject is not None else self.w0
            num += w * y
            den += w
        return num / den


# ------------------------------------------------------------------ Gradient Boosting
FEHLT = -9.0  # Sentinel statt NaN (sklearn 1.9.1 bricht bei Spalten ohne endlichen Wert)
GB_MERKMALE = ("prov", "jahr", "lgroesse", "harness", "effort", "bekannt", "zbar", "nb", "n_own", "k_own", "n_subj",
               "N_oth", "K_oth", "zbar_oth", "bek_oth", "n_i", "k_i", "rate_own", "rate_oth", "rate_i")


class GBMerkmale:
    """Merkmalsberechnung (Training und Testzeit identisch). info: {"prov": {provider: code}, "zbar": {name: z},
    "nb": {name: n}}"""

    def __init__(self, info):
        self.prov = info["prov"]
        self.zbar = info["zbar"]
        self.nb = info["nb"]
        self._sub = {}

    def subjekt(self, subject):
        kf = konfig(subject)
        if kf not in self._sub:
            nk = name_schluessel(subject)
            prov = " ".join(str(subject.get("provider") or "").split()).casefold()
            j = jahr(subject.get("release_date"))
            g = groesse_mrd(nk or "")
            bek = 1.0 if (nk is not None and nk in self.zbar) else 0.0
            self._sub[kf] = (float(self.prov.get(prov, -1)), FEHLT if j is None else j - 2024.0,
                             FEHLT if g is None else math.log10(g),
                             1.0 if str(subject.get("harness") or "").strip() else 0.0,
                             1.0 if str(subject.get("reasoning_effort") or "").strip() else 0.0,
                             bek, self.zbar.get(nk, FEHLT) if bek else FEHLT, float(self.nb.get(nk, 0)) if bek else 0.0)
        return self._sub[kf]

    def zeile(self, subject, gr_bid, kf, item_obs):
        s = self.subjekt(subject)
        eig = gr_bid.get(kf)
        n_own, k_own = (eig["n"], eig["k"]) if eig else (0.0, 0.0)
        N = K = 0.0
        zs, zw = 0.0, 0.0
        bek = 0.0
        cnt = 0
        for k2, o in gr_bid.items():
            if k2 == kf:
                continue
            cnt += 1
            N += o["n"]
            K += o["k"]
            so = self.subjekt(o["subject"])
            if so[5] > 0:
                bek += 1
                zs += so[6] * o["n"]
                zw += o["n"]
        n_i = k_i = 0.0
        if item_obs:
            for k2, y in item_obs:
                if k2 != kf:
                    n_i += 1
                    k_i += y
        return s + (n_own, k_own, float(len(gr_bid)), N, K, zs / zw if zw > 0 else FEHLT,
                    bek / cnt if cnt else FEHLT, n_i, k_i,
                    (k_own + 1.0) / (n_own + 2.0), (K + 1.0) / (N + 2.0) if N > 0 else FEHLT,
                    (k_i + 0.5) / (n_i + 1.0) if n_i > 0 else FEHLT)


class GB(Basis):
    def __init__(self, modell, info, item=True):
        super().__init__()
        self.m = modell
        self.mk = GBMerkmale(info)
        self.tau_i2 = 1.0 if item else 0.0
        self._pc = {}

    def leere_cache(self):
        super().leere_cache()
        self._pc = {}

    def _vorher(self, x):
        key = tuple(x)
        if key not in self._pc:
            self._pc[key] = float(self.m.predict_proba(np.array([x], dtype=float))[0, 1])
        return self._pc[key]

    def _paar(self, bid, kf, subject):
        return self._vorher(self.mk.zeile(subject, self._gr.get(bid, {}), kf, None))

    def _item(self, bid, ik, kf, p):
        subject = self._gr[bid][kf]["subject"] if kf in self._gr.get(bid, {}) else None
        if subject is None:
            return p
        return self._vorher(self.mk.zeile(subject, self._gr[bid], kf, self._items[bid][ik]))


def gb_info(p, sub):
    """Trainingsseitige Subjektinformation aus der Paartabelle: Provider-Vokabular, zentrierte mittlere Logits je Name."""
    cb = p.groupby("b_code").l.mean()
    q = p[p.name != ""].assign(z=lambda d: d.l - d.b_code.map(cb))
    zbar = q.groupby("name").z.mean().to_dict()
    nb = q.groupby("name").b_code.nunique().to_dict()
    provs = sorted(set(" ".join(str(x).split()).casefold() for x in sub.provider.values if str(x).strip()))
    return {"prov": {pv: i for i, pv in enumerate(provs)}, "zbar": {k: float(v) for k, v in zbar.items()},
            "nb": {k: int(v) for k, v in nb.items()}}


# ------------------------------------------------------------------ Stacking der Gegenmethoden
class Stack:
    """Logit-Mischung mehrerer Basis-Prädiktoren mit Gewichten je Budget-Stufe (eigene Labels des Zielsubjekts).
    gewichte: {stufe: [w0, w_1..w_m]} in der Reihenfolge von `basen`. Die Basen werden mit demselben `labeled`
    aufgerufen (ihre Caches greifen); die Stufe kommt aus der ersten Basis mit Gruppierung."""
    tau_i2 = 1.0

    def __init__(self, basen, gewichte):
        self.basen = basen
        self.gew = {int(k): np.array(v, dtype=float) for k, v in gewichte.items()}

    def leere_cache(self):
        pass  # Basen erkennen eine neue Label-Menge selbst (Listenidentität/Fingerabdruck); kein Doppelrechnen

    @staticmethod
    def stufe_von(n):
        s = 0
        for b in (0, 1, 3, 7, 15, 31):
            if n >= b:
                s = b
        return s

    def wahrscheinlichkeit(self, input, labeled=None):
        qs = [b.wahrscheinlichkeit(input, labeled) for b in self.basen.values()]
        erste = next(iter(self.basen.values()))
        erste = getattr(erste, "pr", erste)  # Zeit-Hülle durchgreifen
        bid = (input[1] or {}).get("benchmark_id") or ""
        g = getattr(erste, "_gr", {}).get(bid, {}).get(konfig(input[0]))
        w = self.gew[self.stufe_von(g["n"] if g else 0)]
        x = w[0] + sum(wj * logit(q) for wj, q in zip(w[1:], qs))
        return _clip(sigmoid(x))


def stack_fit(df, basen, stufen=(0, 1, 3, 7, 15, 31)):
    """Gewichte je Stufe aus Paar-Sätzen (q je Basis, R): min Summe (sigmoid(w0 + sum w_j logit q_j) - R)^2.
    df: Spalten praediktor, saat, S, budget, b_code, s_code, q, R, n_eigen. -> {stufe: [w0, w...]}"""
    from scipy.optimize import minimize
    piv = df[df.praediktor.isin(basen)].pivot_table(index=["saat", "S", "budget", "b_code", "s_code"], columns="praediktor",
                                                    values="q")[list(basen)]
    meta = df[df.praediktor == basen[0]].set_index(["saat", "S", "budget", "b_code", "s_code"])[["R", "n_eigen"]]
    piv = piv.join(meta).dropna()
    st = piv.n_eigen.map(Stack.stufe_von)
    out = {}
    for s in stufen:
        m = piv[st == s]
        if len(m) < 20:
            out[s] = [0.0] + [1.0 / len(basen)] * len(basen)
            continue
        L = np.log(np.clip(m[list(basen)].values, 1e-6, 1 - 1e-6) / (1 - np.clip(m[list(basen)].values, 1e-6, 1 - 1e-6)))
        R = m.R.values

        def f(w):
            p = 1 / (1 + np.exp(-(w[0] + L @ w[1:])))
            return float(np.mean((p - R) ** 2)) + 1e-4 * float(np.sum(w[1:] ** 2))
        x0 = np.array([0.0] + [1.0 / len(basen)] * len(basen))
        res = minimize(f, x0, method="L-BFGS-B")
        out[s] = [float(v) for v in res.x]
    return out


# ------------------------------------------------------------------ Zeitmessung
class Zeit:
    """Hülle: zählt Aufrufe und Zeit getrennt nach Paar- (Platzhalter-Item) und Item-Aufrufen."""

    def __init__(self, pr):
        self.pr = pr
        self.t_paar = self.t_item = 0.0
        self.n_paar = self.n_item = 0

    @property
    def tau_i2(self):
        return getattr(self.pr, "tau_i2", 0.0)

    def leere_cache(self):
        if hasattr(self.pr, "leere_cache"):
            self.pr.leere_cache()

    def wahrscheinlichkeit(self, input, labeled=None):
        t0 = time.perf_counter()
        q = self.pr.wahrscheinlichkeit(input, labeled)
        dt = time.perf_counter() - t0
        if (input[1] or {}).get("item_content"):
            self.t_item += dt
            self.n_item += 1
        else:
            self.t_paar += dt
            self.n_paar += 1
        return q

    def stat(self):
        return {"n_paar": self.n_paar, "ms_je_1000_paar": 1000.0 * 1000.0 * self.t_paar / max(self.n_paar, 1),
                "n_item": self.n_item, "ms_je_1000_item": 1000.0 * 1000.0 * self.t_item / max(self.n_item, 1)}
