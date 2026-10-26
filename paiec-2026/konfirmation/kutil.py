"""kutil.py — gemeinsame Hilfen für die Konfirmationsskripte (P4, Prereg v2 §2).

Lädt CV-Sätze (Phase 1 / Phase 2) aus PAIEC_WORK/modell/<ordner>/saetze_f*.parquet, rechnet Paar-ALC exakt wie
code_v1/auswertung.py (importiert), liefert die eingefrorene Urteilsregel (Prereg §2) und Cluster-Bootstrap.
Alles fail-closed: fehlende Dateien/Spalten → Ausnahme, kein stilles Weiterrechnen.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER / "code_v1"))
import metrik  # noqa: E402
import auswertung as ausw  # noqa: E402

WORK = Path(os.environ.get("PAIEC_WORK", "")) / "modell"
BUDGETS = metrik.BUDGETS
GEW = dict(zip(metrik.BUDGETS, metrik.GEWICHTE))
MARGE = 0.001  # Äquivalenzschranke (Prereg §2, eingefroren)
Z = 2.0


class KonfError(RuntimeError):
    pass


def pruefe_work():
    if not os.environ.get("PAIEC_WORK"):
        raise KonfError("PAIEC_WORK nicht gesetzt (fail-closed)")
    if not WORK.exists():
        raise KonfError(f"{WORK} fehlt")


def lade_saetze(ordner, erwartete_falten=10):
    """Alle saetze_f*.parquet eines CV-Ordners; status.json muss fertig == falten melden (fail-closed)."""
    pruefe_work()
    d = WORK / ordner
    st = d / "status.json"
    if not st.exists():
        raise KonfError(f"{st} fehlt")
    s = json.loads(st.read_text())
    if int(s.get("fertig", -1)) != int(s.get("falten", erwartete_falten)) or int(s.get("falten", 0)) != erwartete_falten:
        raise KonfError(f"{ordner}: status.json nicht fertig: {s}")
    teile = sorted(d.glob("saetze_f*.parquet"))
    if len(teile) != erwartete_falten:
        raise KonfError(f"{ordner}: {len(teile)} Parquet-Dateien statt {erwartete_falten}")
    df = pd.concat([pd.read_parquet(t) for t in teile], ignore_index=True)
    noetig = {"saat", "S", "praediktor", "budget", "b_code", "s_code", "q", "R", "N", "n_eigen", "brier", "falte"}
    fehlt = noetig - set(df.columns)
    if fehlt:
        raise KonfError(f"{ordner}: Spalten fehlen: {fehlt}")
    if not np.isfinite(df.q.values).all() or not np.isfinite(df.R.values).all():
        raise KonfError(f"{ordner}: nicht-endliche q/R")
    return d, df, s


def saaten(df):
    return sorted(int(x) for x in df.saat.unique())


def paar_alc(df):
    """Paar-ALC je (S, Prädiktor, Paar), Mittel über Saaten — identischer Code wie code_v1/auswertung.paar_alc."""
    return ausw.paar_alc(df)


def vergleich(pa, S, modell, referenz, maske=None, balanciert=False):
    """Gepaarte Differenz Modell − Referenz (negativ = Modell besser), SE cluster-robust über Benchmarks."""
    if not ((pa.S == S) & (pa.praediktor == modell)).any() or not ((pa.S == S) & (pa.praediktor == referenz)).any():
        raise KonfError(f"Vergleich {modell} vs {referenz} in {S}: Prädiktor fehlt")
    v = ausw.vergleich(pa, S, modell, referenz, maske=maske, balanciert=balanciert)
    if "mittel" not in v or "se" not in v:
        raise KonfError(f"Vergleich {modell} vs {referenz} in {S}: {v.get('urteil')}")
    return v


def urteil(d, se, marge=MARGE, z=Z):
    """Prereg §2: better d+2SE<0; worse d−2SE>0; equivalent |d|+2SE<marge; sonst grey_zone.
    'equivalent' kann mit better/worse zusammenfallen → Flag 'signifikant_aber_irrelevant'."""
    if d is None or se is None or not (math.isfinite(d) and math.isfinite(se)):
        return {"verdict": "not_evaluated", "grund": "d/SE nicht endlich"}
    better = d + z * se < 0
    worse = d - z * se > 0
    aequiv = abs(d) + z * se < marge
    out = {"d": d, "se": se, "ci95": [d - 1.96 * se, d + 1.96 * se], "better": bool(better), "worse": bool(worse),
           "equivalent": bool(aequiv), "marge": marge}
    if aequiv:
        out["verdict"] = "equivalent"
        if better or worse:
            out["zusatz"] = ("better" if better else "worse") + ", below relevance margin"
    elif better:
        out["verdict"] = "better"
    elif worse:
        out["verdict"] = "worse"
    else:
        out["verdict"] = "grey_zone"
        if se > 0:
            # Power des Äquivalenztests bei exaktem Nulleffekt: P(|d|+2SE<marge | d~N(0,SE)) = 2Φ(marge/SE−2)−1
            out["power_aequivalenz_bei_null"] = max(0.0, 2 * norm_cdf(marge / se - z) - 1)
    return out


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def cluster_bootstrap(stat, gruppen, n_boot=2000, seed=200):
    """stat(liste_von_gruppen_indizes) -> float; Benchmarks (Gruppen) mit Zurücklegen gezogen. Gibt (SE, KI95, Werte)."""
    rng = np.random.default_rng(seed)
    G = len(gruppen)
    werte = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, G, G)
        werte[i] = stat(idx)
    werte = werte[np.isfinite(werte)]
    if len(werte) < n_boot * 0.95:
        raise KonfError("Bootstrap: zu viele nicht-endliche Replikate")
    return float(werte.std(ddof=1)), [float(np.percentile(werte, 2.5)), float(np.percentile(werte, 97.5))], werte


def jetzt():
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def schreibe_json(pfad, obj):
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=_json_default))
    tmp.rename(pfad)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(str(type(o)))


def rund(x, n=6):
    if isinstance(x, float):
        return round(x, n)
    if isinstance(x, dict):
        return {k: rund(v, n) for k, v in x.items()}
    if isinstance(x, list):
        return [rund(v, n) for v in x]
    return x
