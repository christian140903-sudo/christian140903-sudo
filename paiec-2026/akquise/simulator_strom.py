"""Strom-Simulator der PAIEC-Akquise (P5, BAUPLAN-V2 §2.2; D-akquise §3.3). Eigener Code nach Wettbewerbstext und
paiec_baseline@cc88a959 tools/streaming_ingestion.py (gelesen, nicht ausgeführt). Annahmen [A].

Gegenüber modell/simulator.py (v1, „erste B der Permutation") entscheidet hier eine POLITIK je Kandidat:
  Paar        wie v1 `_paar`: Split der Items 50/50 je Paar (Saat, fest) — oder [A] Split je ITEM im Benchmark (--split item)
  Kandidaten  Permutation der Akquise-Hälfte, gekappt auf POOL_KAPPE [A]; Kandidat j: context wie Plattform
              (labels_acquired, labels_remaining = 31 - a, max_labels 31, items_remaining = Rest inkl. aktuellem)
  Antwort     EINE feste Uniforme je Item (gemeinsame Zufallszahlen über Politiken/Ordnungen): y_i = u_i < k_i/n_i
  Koordinator [A] Ordnung der Paare eines Laufs: paar | rr | zufall (Plattform unbekannt; Spanne wird berichtet)
  labeled     alle bisher gekauften Labels ALLER Paare des Laufs, in Kaufreihenfolge (append-only)
  Bewertung   Budget B = die ersten B gekauften Labels je Paar (verschachtelt), Brier itemgenau wie v1 bewerte_lauf
  Leck-Wächter (F6): vor jeder Entscheidung muss |labeled| == Zahl der Käufe sein; --leck fügt den Kandidaten vor der
              Entscheidung ein -> LeckFehler muss fliegen.
Prädiktoren: v1 modell/inferenz.Modell (Paket = hier_item), Empirical Mean, Beta-Binomial, Orakel-d (bekannte LOO-Schwierigkeit).
"""
import hashlib
import math
import os
import sys
from pathlib import Path

import numpy as np

MODELL = Path(os.environ.get("PAIEC_MODELL", Path(__file__).resolve().parents[2] / "modell"))
sys.path.insert(0, str(MODELL))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import politiken  # noqa: E402
from metrik import BUDGETS  # noqa: E402

MAX_LABELS = 31
MIN_ITEMS = 80
POOL_KAPPE = 200


class LeckFehler(AssertionError):
    pass


def _saat(*teile):
    return int.from_bytes(hashlib.sha256("|".join(map(str, teile)).encode()).digest()[:8], "big")


def _item(anon, code):
    return {"item_content": "" if code is None else "i%d" % code, "item_features": "", "interactors": "",
            "benchmark_id": anon}


# ------------------------------------------------------------------ Paare und Läufe
def baue_paar(g, row, subjekte, seed, split="paar", tag="", orakel_d=None):
    """g: agg-Zeilen des Paares (b_code, s_code, i_code, n, k). orakel_d: dict i_code -> LOO-Schwierigkeit (optional)."""
    n = g.n.values.astype(float)
    k = g.k.values.astype(float)
    ic = g.i_code.values.astype(int)
    b, s = int(row.b_code), int(row.s_code)
    rng = np.random.default_rng(_saat(seed, "paar", tag, b, s))
    perm = rng.permutation(len(g))
    if split == "paar":
        halb = len(g) // 2
        akq, bew = perm[:halb], perm[halb:]
    elif split == "item":
        bit = np.array([_saat(seed, "splititem", b, int(c)) & 1 for c in ic], dtype=bool)
        akq, bew = perm[~bit[perm]], perm[bit[perm]]
    else:
        raise ValueError(split)
    u = np.random.default_rng(_saat(seed, "y", tag, b, s)).random(len(g))
    y_alle = (u < k / n).astype(int)
    kand = akq[:POOL_KAPPE]
    if len(kand) == 0 or len(bew) == 0:
        return None
    d = None
    if orakel_d is not None:
        d = {int(c): float(orakel_d.get(int(c), 0.0)) for c in ic}
        m = float(np.mean([d[int(c)] for c in ic]))
        d = {c: v - m for c, v in d.items()}
    return {"b_code": b, "s_code": s, "subject": subjekte[s], "konfig": row.konfig,
            "kand_i": ic[kand].tolist(), "kand_y": y_alle[kand].tolist(),
            "bew_i": ic[bew], "bew_n": n[bew], "bew_k": k[bew], "N": float(n[bew].sum()), "K": float(k[bew].sum()),
            "d": d}


def loo_schwierigkeit(agg_b):
    """Orakel: je Item Summen über alle Subjekte des Benchmarks (K_i, N_i); LOO je Paar in baue_paar."""
    g = agg_b.groupby("i_code")[["n", "k"]].sum()
    return g.n.to_dict(), g.k.to_dict()


def orakel_d_fuer(g, Ni, Ki):
    out = {}
    for c, n, k in zip(g.i_code.values, g.n.values, g.k.values):
        c = int(c)
        N_o, K_o = Ni[c] - n, Ki[c] - k
        out[c] = math.log((K_o + 0.5) / (N_o - K_o + 0.5)) if N_o > 0 else 0.0
    return out


def baue_paare(agg_b, testpaare, subjekte, seed, split="paar", orakel=False):
    g_je_s = {s: g for s, g in agg_b.groupby("s_code", sort=False)}
    Ni, Ki = loo_schwierigkeit(agg_b) if orakel else (None, None)
    out = []
    for row in testpaare.itertuples(index=False):
        g = g_je_s[row.s_code]
        od = orakel_d_fuer(g, Ni, Ki) if orakel else None
        p = baue_paar(g, row, subjekte, seed, split, "", od)
        if p is not None:
            out.append(p)
    return out


def gruppiere_laeufe(paare, S, seed):
    """Wie v1: Paare eines Benchmarks zu Läufen von S Subjekten (Saat, fest)."""
    if not paare:
        return []
    rng = np.random.default_rng(_saat(seed, "lauf", paare[0]["b_code"], S))
    idx = rng.permutation(len(paare))
    return [[paare[i] for i in idx[j:j + S]] for j in range(0, len(idx), S)]


def kompakte_laeufe(agg_b, testpaare, subjekte, seed, S=10, n_items=100, split="paar", orakel=False):
    """Wie v1 kompakte_laeufe: S Subjekte auf gemeinsamen Items (Schnittmenge, davon n_items zufällig); < 80 gemeinsame -> verworfen."""
    g_je_s = {s: g for s, g in agg_b.groupby("s_code", sort=False)}
    zeilen = list(testpaare.itertuples(index=False))
    if not zeilen:
        return []
    rng = np.random.default_rng(_saat(seed, "kompakt", zeilen[0].b_code, S))
    idx = rng.permutation(len(zeilen))
    Ni, Ki = loo_schwierigkeit(agg_b) if orakel else (None, None)
    laeufe = []
    for j in range(0, len(idx), S):
        gruppe = [zeilen[i] for i in idx[j:j + S]]
        if len(gruppe) < 2:
            continue
        gemeinsam = set(g_je_s[gruppe[0].s_code].i_code.values)
        for r in gruppe[1:]:
            gemeinsam &= set(g_je_s[r.s_code].i_code.values)
        if len(gemeinsam) < MIN_ITEMS:
            continue
        wahl = set(rng.choice(sorted(gemeinsam), min(n_items, len(gemeinsam)), replace=False).tolist())
        lauf = []
        for r in gruppe:
            g = g_je_s[r.s_code]
            g = g[g.i_code.isin(wahl)]
            od = orakel_d_fuer(g, Ni, Ki) if orakel else None
            p = baue_paar(g, r, subjekte, seed, split, "k", od)
            if p is not None:
                lauf.append(p)
        if len(lauf) >= 2:
            laeufe.append(lauf)
    return laeufe


# ------------------------------------------------------------------ Akquise
def _ordnung(lauf, ordnung, seed):
    """Generator der Paar-Indizes in Koordinator-Reihenfolge; der Aufrufer überspringt fertige Paare."""
    n = len(lauf)
    if ordnung == "paar":
        for i in range(n):
            for _ in range(len(lauf[i]["kand_i"])):
                yield i
    elif ordnung == "rr":
        while True:
            for i in range(n):
                yield i
    elif ordnung == "zufall":
        folge = np.concatenate([np.full(len(p["kand_i"]), i) for i, p in enumerate(lauf)])
        rng = np.random.default_rng(_saat(seed, "ordnung", lauf[0]["b_code"], n, lauf[0]["s_code"]))
        for i in rng.permutation(folge):
            yield int(i)
    else:
        raise ValueError(ordnung)


def akquiriere(lauf, politik, ordnung, seed, modell=None, leck=False, zaehle_replik=True):
    """Führt die Akquise eines Laufs aus. Schreibt je Paar p['gek_i'], p['gek_y'] (Kaufreihenfolge).
    -> Statistik: kandidaten, kaeufe, abweichungen (Politik != Replik), fallbacks."""
    anon = "bm_%016x" % _saat(seed, "anon", lauf[0]["b_code"])
    orakel = None
    if politik == "orakel_d":
        hyp = modell.state["hyp"] if modell is not None else {"mu_c": 0.0, "tau_c2": 1.0, "s2_unk": 1.0}
        orakel = {"d": {}, "pool": {}, "eigen": {}, "mu": hyp["mu_c"], "var": hyp["tau_c2"] + hyp["s2_unk"]}
    E = politiken.Entscheider(politik, orakel)
    R = politiken.Entscheider("zufall") if zaehle_replik else None
    labeled = []
    n_kaeufe = 0
    pos = [0] * len(lauf)
    acq = [0] * len(lauf)
    fertig = [False] * len(lauf)
    sids = ["sj_%016x" % _saat(seed, "sid", p["b_code"], p["s_code"]) for p in lauf]
    kf = [politiken.konfig(p["subject"]) for p in lauf]
    for i, p in enumerate(lauf):
        p["gek_i"], p["gek_y"] = [], []
        if len(p["kand_i"]) == 0:
            fertig[i] = True
    if orakel is not None:
        for i, p in enumerate(lauf):
            keys = [politiken.item_schluessel(_item(anon, c)) for c in p["kand_i"]]
            orakel["pool"][(anon, kf[i])] = (keys, 0)
            orakel["d"].update({kk: p["d"][c] for kk, c in zip(keys, p["kand_i"])} if p["d"] else {})
            orakel["eigen"][(anon, kf[i])] = []
    if modell is not None:
        modell.leere_cache()
    st = {"kandidaten": 0, "kaeufe": 0, "abweichungen": 0, "fallbacks": 0}
    offen = sum(1 for f in fertig if not f)
    for i in _ordnung(lauf, ordnung, seed):
        if offen == 0:
            break
        if fertig[i]:
            continue
        p = lauf[i]
        j = pos[i]
        code, y = p["kand_i"][j], int(p["kand_y"][j])
        item = _item(anon, code)
        inp = [p["subject"], item]
        a = acq[i]
        context = {"subject_id": sids[i], "benchmark_id": anon, "labels_acquired": a,
                   "labels_remaining": MAX_LABELS - a, "max_labels": MAX_LABELS,
                   "items_remaining": len(p["kand_i"]) - j}
        if leck:
            labeled.append([[p["subject"], item], y])  # absichtliches Leck (F6)
        if len(labeled) != n_kaeufe:
            raise LeckFehler(f"labeled hat {len(labeled)} Einträge, gekauft {n_kaeufe}")
        vorhersage = None
        if politik in politiken.BRAUCHT_VORHERSAGE:
            vorhersage = float(modell.wahrscheinlichkeit(inp, labeled))
        if orakel is not None:
            orakel["pool"][(anon, kf[i])] = (orakel["pool"][(anon, kf[i])][0], j)
        q = politiken.hook_pruefung(E(inp, vorhersage, labeled, context))
        st["kandidaten"] += 1
        if R is not None and q != R(inp, None, labeled, context):
            st["abweichungen"] += 1
        if q:
            labeled.append([[p["subject"], item], y])
            n_kaeufe += 1
            p["gek_i"].append(int(code))
            p["gek_y"].append(y)
            acq[i] += 1
            if orakel is not None:
                orakel["eigen"][(anon, kf[i])].append((politiken.item_schluessel(item), y))
        pos[i] += 1
        if acq[i] >= MAX_LABELS or pos[i] >= len(p["kand_i"]):
            fertig[i] = True
            offen -= 1
    st["kaeufe"] = n_kaeufe
    st["fallbacks"] = E.fallbacks
    return st


# ------------------------------------------------------------------ Bewertung
def _orakel_vorhersagen(p, B, hyp):
    """Orakel-d-Prädiktor (C §3.3 im Strom): b ~ N(mu, var), Likelihood sigma(b + d_i) je eigenem Label; Vorhersage je
    Bewertungs-Item sigma((b + d_t) / sqrt(1 + pi v / 8))."""
    mu, var = hyp["mu_c"], hyp["tau_c2"] + hyp["s2_unk"]
    obs = [(p["d"][c], y) for c, y in zip(p["gek_i"][:B], p["gek_y"][:B])]
    b = mu
    for _ in range(50):
        g, h = (b - mu) / var, 1.0 / var
        for di, y in obs:
            s = politiken.sigmoid(b + di)
            g += s - y
            h += s * (1.0 - s)
        step = max(min(g / h, 2.0), -2.0)
        b -= step
        if abs(step) < 1e-10:
            break
    h = 1.0 / var + sum(politiken.sigmoid(b + di) * (1 - politiken.sigmoid(b + di)) for di, _ in obs)
    v = 1.0 / h
    c = math.sqrt(1.0 + math.pi * v / 8.0)
    return np.array([politiken.sigmoid((b + p["d"][int(t)]) / c) for t in p["bew_i"]])


def bewerte_lauf(lauf, praediktoren, seed, orakel_hyp=None):
    """Nach akquiriere(). -> Zeilen (praediktor, B, b_code, s_code, q, R, N, n_eigen, brier, n_items_angepasst).
    praediktoren: dict name -> Objekt mit wahrscheinlichkeit(input, labeled); Name 'orakel_d' -> Orakel-Prädiktor."""
    anon = "bm_%016x" % _saat(seed, "anon", lauf[0]["b_code"])
    platz = _item(anon, None)
    out = []
    for B in BUDGETS:
        labeled = []
        codes = set()
        for p in lauf:
            for y, ic in zip(p["gek_y"][:B], p["gek_i"][:B]):
                labeled.append([[p["subject"], _item(anon, ic)], int(y)])
                codes.add(ic)
        for name, pr in praediktoren.items():
            if name == "orakel_d":
                for p in lauf:
                    qi = _orakel_vorhersagen(p, B, orakel_hyp)
                    brier = float(np.sum(p["bew_n"] * qi * qi - 2 * qi * p["bew_k"] + p["bew_k"]) / p["N"])
                    n_eigen = min(B, len(p["gek_y"]))
                    n_adj = int(sum(1 for ic in p["bew_i"] if int(ic) in codes))
                    out.append((name, B, p["b_code"], p["s_code"], float(np.mean(qi)), p["K"] / p["N"], p["N"],
                                n_eigen, brier, n_adj))
                continue
            if hasattr(pr, "leere_cache"):
                pr.leere_cache()
            itemfaehig = getattr(pr, "tau_i2", 0.0) > 0
            for p in lauf:
                q = float(pr.wahrscheinlichkeit([p["subject"], platz], labeled))
                if not (0.0 <= q <= 1.0) or q != q:
                    raise ValueError(f"{name}: ungültige Wahrscheinlichkeit {q}")
                qi = np.full(len(p["bew_i"]), q)
                n_adj = 0
                for j, ic in enumerate(p["bew_i"]):
                    if int(ic) in codes:
                        n_adj += 1
                        if itemfaehig:
                            qi[j] = pr.wahrscheinlichkeit([p["subject"], _item(anon, int(ic))], labeled)
                brier = float(np.sum(p["bew_n"] * qi * qi - 2 * qi * p["bew_k"] + p["bew_k"]) / p["N"])
                n_eigen = min(B, len(p["gek_y"]))
                out.append((name, B, p["b_code"], p["s_code"], q, p["K"] / p["N"], p["N"], n_eigen, brier, n_adj))
    return out
