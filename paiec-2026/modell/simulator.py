"""Offline-Nachbau der PAIEC-Bewertung auf Trainingsdaten (eigener Code nach Wettbewerbstext und
paiec_baseline@cc88a959 tools/streaming_ingestion.py, gelesen, nicht ausgeführt). Annahmen sind mit [A] markiert.

Paare       Subjekt (subject_id) x Benchmark mit >= 80 distinkten benoteten Items; je Benchmark höchstens 30 (fest)
Split       Items je Paar zufällig 50/50 in Akquise/Bewertung, fest je Saat
Akquise     Plattform-Zufallspolitik = gleichverteilte Teilmenge in zufälliger Reihenfolge; die ersten B Labels je Paar
            bilden Budget B (verschachtelt). Je Item EINE zufällige aufgezeichnete Antwort: y ~ Bernoulli(k_i / n_i)
Lauf        [A] Paare eines Benchmarks werden zu Läufen von S Subjekten gruppiert; labeled enthält beim Budget B die
            ersten B Labels JEDES Paares im Lauf (Wettbewerb: "entries across sampled subject-benchmark pairs")
Regime      "alle": jedes Paar mit allen seinen Items. "kompakt" [A]: S Subjekte teilen eine Zufallsauswahl von
            100 gemeinsamen Items (S=10 -> ~1 000 Subjekt-Item-Paare, wie die Obergrenze eines Formativlaufs);
            nur dann tragen Labels anderer Subjekte zum selben Item nennenswert bei
Bewertung   Brier je Paar über alle Antworten der Bewertungs-Items, je Item: sum(n q^2 - 2 q k + k) / sum(n).
            Ein Aufruf je Paar mit Platzhalter-Item liefert die Paarvorhersage; Items, zu denen im Lauf Labels
            existieren, werden einzeln vorhergesagt (nur für Prädiktoren mit Item-Stufe verschieden)
Anonymität  benchmark_id -> Pseudonym je Saat; Item-Text = Platzhalter "i<code>" (eindeutig je Item)
"""
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrik import BUDGETS  # noqa: E402

MAX_LABELS = 31
MIN_ITEMS = 80


def _saat(*teile):
    return int.from_bytes(hashlib.sha256("|".join(map(str, teile)).encode()).digest()[:8], "big")


def _paar(g, row, subjekte, seed, tag=""):
    n = g.n.values.astype(float)
    k = g.k.values.astype(float)
    ic = g.i_code.values
    rng = np.random.default_rng(_saat(seed, "paar", tag, row.b_code, row.s_code))
    perm = rng.permutation(len(g))
    halb = len(g) // 2
    akq, bew = perm[:halb], perm[halb:]
    lab = akq[:MAX_LABELS]
    y = (rng.random(len(lab)) < k[lab] / n[lab]).astype(int)
    return {"b_code": int(row.b_code), "s_code": int(row.s_code), "subject": subjekte[row.s_code],
            "konfig": row.konfig, "y": y.tolist(), "lab_i": ic[lab].tolist(),
            "bew_i": ic[bew], "bew_n": n[bew], "bew_k": k[bew], "N": float(n[bew].sum()), "K": float(k[bew].sum())}


def baue_paare(agg_b, testpaare, subjekte, seed):
    g_je_s = {s: g for s, g in agg_b.groupby("s_code", sort=False)}
    return [_paar(g_je_s[row.s_code], row, subjekte, seed) for row in testpaare.itertuples(index=False)]


def gruppiere_laeufe(paare, S, seed):
    if not paare:
        return []
    rng = np.random.default_rng(_saat(seed, "lauf", paare[0]["b_code"], S))
    idx = rng.permutation(len(paare))
    return [[paare[i] for i in idx[j:j + S]] for j in range(0, len(idx), S)]


def kompakte_laeufe(agg_b, testpaare, subjekte, seed, S=10, n_items=100):
    """Läufe von S Subjekten auf gemeinsamen Items (Schnittmenge, davon n_items zufällig); < 80 gemeinsame -> verworfen."""
    g_je_s = {s: g for s, g in agg_b.groupby("s_code", sort=False)}
    zeilen = list(testpaare.itertuples(index=False))
    if not zeilen:
        return []
    rng = np.random.default_rng(_saat(seed, "kompakt", zeilen[0].b_code, S))
    idx = rng.permutation(len(zeilen))
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
        laeufe.append([_paar(g_je_s[r.s_code][g_je_s[r.s_code].i_code.isin(wahl)], r, subjekte, seed, "k")
                       for r in gruppe])
    return laeufe


def _item(anon, code):
    return {"item_content": "" if code is None else "i%d" % code, "item_features": "", "interactors": "",
            "benchmark_id": anon}


def bewerte_lauf(lauf, praediktoren, seed):
    """-> Datensätze je (Prädiktor, Budget, Paar): q_paar, R, N, n_eigen, brier (itemgenau), n_items_angepasst."""
    anon = "bm_%016x" % _saat(seed, "anon", lauf[0]["b_code"])
    platz = _item(anon, None)
    out = []
    for B in BUDGETS:
        labeled = []
        codes = set()
        for p in lauf:
            for y, ic in zip(p["y"][:B], p["lab_i"][:B]):
                labeled.append([[p["subject"], _item(anon, ic)], int(y)])
                codes.add(ic)
        for name, pr in praediktoren.items():
            if hasattr(pr, "leere_cache"):
                pr.leere_cache()  # Läufe sind unabhängige Auswertungen
            itemfaehig = getattr(pr, "tau_i2", 0.0) > 0
            for p in lauf:
                q = float(pr.wahrscheinlichkeit([p["subject"], platz], labeled))
                if not (0.0 <= q <= 1.0) or q != q:
                    raise ValueError(f"{name}: ungültige Wahrscheinlichkeit {q}")
                qi = np.full(len(p["bew_i"]), q)
                n_adj = 0
                if itemfaehig and codes:
                    for j, ic in enumerate(p["bew_i"]):
                        if int(ic) in codes:
                            qi[j] = pr.wahrscheinlichkeit([p["subject"], _item(anon, int(ic))], labeled)
                            n_adj += 1
                brier = float(np.sum(p["bew_n"] * qi * qi - 2 * qi * p["bew_k"] + p["bew_k"]) / p["N"])
                n_eigen = sum(min(B, len(o["y"])) for o in lauf if o["konfig"] == p["konfig"])
                out.append((name, B, p["b_code"], p["s_code"], q, p["K"] / p["N"], p["N"], n_eigen, brier, n_adj))
    return out
