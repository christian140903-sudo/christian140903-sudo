"""Baut submission.zip: EIN eigenständiges model.py (merkmale + inferenz eingebettet, Zustand als JSON-Text
eingebettet, keine Dateizugriffe, nur Standardbibliothek) + README.md. Kein labeling.py (Plattform-Zufallsakquise).

v2.0-core (Härtung K4a, 2026-10-20): predict() hat eine gestufte Rückfallkette hier -> Beta-Binomial (alpha, beta aus
dem eingebetteten Zustand, eigene Labels gezählt) -> Konstante 0,5, mit Zählern je Stufe (model.diagnose(), nur für
lokale Tests; die Plattform ruft nur predict). Mathematik von predict unverändert v1 (bitgleich belegt, KERN-DIFF.md).

Aufruf: python3 -I paket/baue_paket.py --state <state.json> --aus <dir> [--name paiec_v2core] [--model-py <model.py>]
--model-py: README-only-Neubau — das angegebene model.py wird byteidentisch uebernommen (kein neuer Build-Zeitstempel),
nur README.md kommt neu aus paket/README_paket.md (SOLL-5, 2026-10-21). Das Skript prueft, dass das uebergebene
model.py zu --state gehoert (eingebetteter kanonischer State-Hash) und druckt dessen sha256.
Nichts wird hochgeladen. Hochladen geschieht nicht durch dieses Skript.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]

KOPF = '''"""PAIEC 2026 submission: hierarchical logistic pair-level predictor (no LLM, no network, stdlib only).

logit r_sb = c_b + a_b * m_s + v_sb. m_s: subject ability learned on measurement-db (rev 54074453) via
normalized_name, else a ridge regression on visible metadata. c_b, a_b: benchmark location and slope, unknown at
test time (cold start); their Laplace posterior uses the revealed labels of ALL subjects of the benchmark in
`labeled`. v_sb: pair deviation. Prediction = posterior mean of sigmoid (probit approximation), optional Platt
recalibration per label stage (kept only where cross-fitted calibration lowered the Brier score). v2.0-core: staged
fallback hier -> beta-binomial -> 0.5 and tolerant label parsing; predict() never raises. Built %(zeit)s, state sha256 %(sha)s.
"""
'''

FUSS = '''

import threading  # noqa: E402

_STATE = json.loads(_STATE_JSON)
_MODELL = Modell(_STATE)
_RUECKFALL = float(_STATE.get("rueckfall", 0.5))
_CLIP = float(_STATE.get("clip", 1e-4))
_BB = _STATE.get("baselines") or {}
_BB_ALPHA = float(_BB.get("beta_alpha", 1.0))
_BB_BETA = float(_BB.get("beta_beta", 1.0))
_SPERRE = threading.Lock()  # the model keeps lazy caches; serialise calls if the platform uses threads
# Fallback counters (diagnostics for local tests only; never part of any prediction):
#   hier = hierarchical model answered; beta_binomial = stage 2 (smoothed own mean); konstant = stage 3 (constant)
_ZAEHLER = {"aufrufe": 0, "hier": 0, "beta_binomial": 0, "konstant": 0}


def _klemme(p):
    return min(max(float(p), _CLIP), 1.0 - _CLIP)


def _beta_binomial(input, labeled):
    """Stage 2: (alpha + k) / (alpha + beta + n) from the target pair's own labels (same 8 subject fields, same
    benchmark_id), O(|labeled|); tolerant of malformed entries (skipped)."""
    subject, item = input
    bid = (item.get("benchmark_id") or "") if isinstance(item, dict) else ""
    kf = konfig(subject) if isinstance(subject, dict) else None
    k = n = 0.0
    for e in labeled or []:
        try:
            (s, it), lab = e
            if not isinstance(s, dict) or not isinstance(it, dict):
                continue
            if (it.get("benchmark_id") or "") != bid or konfig(s) != kf:
                continue
            y = label_wert(lab)
            if y is None:
                continue
            k += y
            n += 1.0
        except Exception:
            continue
    return (_BB_ALPHA + k) / (_BB_ALPHA + _BB_BETA + n)


def predict(input, labeled=None):
    """Predict P(response == 1) for input = [subject, item]; labeled = [[[subject, item], label], ...].
    Never raises; always returns a finite float in [_CLIP, 1 - _CLIP]."""
    try:
        with _SPERRE:
            _ZAEHLER["aufrufe"] += 1
            p = _MODELL.wahrscheinlichkeit(input, labeled or [])
            if isinstance(p, float) and p == p and 0.0 <= p <= 1.0:
                _ZAEHLER["hier"] += 1
                return _klemme(p)
    except Exception:  # never let one odd input fail the whole evaluation (failure code 40)
        pass
    try:
        p = float(_beta_binomial(input, labeled))
        if p == p and 0.0 <= p <= 1.0:
            with _SPERRE:
                _ZAEHLER["beta_binomial"] += 1
            return _klemme(p)
    except Exception:
        pass
    try:
        with _SPERRE:
            _ZAEHLER["konstant"] += 1
    except Exception:
        pass
    return _RUECKFALL


def diagnose():
    """Copy of the fallback counters (local tests only)."""
    with _SPERRE:
        return dict(_ZAEHLER)
'''


def quelltext(datei, ohne_import=None):
    s = (HIER / datei).read_text(encoding="utf-8")
    if ohne_import:
        s = re.sub(ohne_import, "", s, count=1)
    return s


def baue(state_pfad, aus, name, zeit, model_py=None):
    state = json.loads(Path(state_pfad).read_text(encoding="utf-8"))
    if state.get("pipeline_test"):
        name += "_PIPELINE-TEST"
    state_txt = json.dumps(state, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    sha = hashlib.sha256(state_txt.encode()).hexdigest()[:16]
    if model_py:
        # README-only-Neubau: vorhandenes model.py byteidentisch uebernehmen; es muss zu --state gehoeren.
        code = Path(model_py).read_text(encoding="utf-8")
        if f"state sha256 {sha}." not in code.splitlines()[7]:
            raise SystemExit(f"model.py {model_py} gehoert nicht zu {state_pfad} (State-Hash {sha} fehlt im Kopf)")
    else:
        teile = [KOPF % {"zeit": zeit, "sha": sha},
                 "# ---- merkmale.py ----\n", quelltext("merkmale.py"),
                 "\n# ---- inferenz.py ----\n",
                 re.sub(r"\ndef lade\(pfad\):\n(?:    [^\n]*\n)+", "\n", quelltext("inferenz.py", r"from merkmale import [^\n]+\n")),
                 "\n_STATE_JSON = r'''" + state_txt.replace("'''", "\\'\\'\\'") + "'''\n", FUSS]
        code = "".join(teile)
    compile(code, "model.py", "exec")
    aus = Path(aus)
    aus.mkdir(parents=True, exist_ok=True)
    if not (model_py and Path(model_py).resolve() == (aus / "model.py").resolve()):
        (aus / "model.py").write_text(code, encoding="utf-8")
    readme = (HIER / "paket" / "README_paket.md").read_text(encoding="utf-8")
    (aus / "README.md").write_text(readme, encoding="utf-8")
    zp = aus / f"{name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(aus / "model.py", "model.py")
        z.write(aus / "README.md", "README.md")
    return zp, sha


if __name__ == "__main__":
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--aus", required=True)
    ap.add_argument("--name", default="paiec_v2core")
    ap.add_argument("--model-py", default=None, help="vorhandenes model.py byteidentisch uebernehmen (README-only-Neubau)")
    a = ap.parse_args()
    zp, sha = baue(a.state, a.aus, a.name, time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), a.model_py)
    mp = hashlib.sha256((Path(a.aus) / "model.py").read_bytes()).hexdigest()
    print(zp, "state", sha, zp.stat().st_size, "Bytes", "model.py sha256", mp, "zip sha256",
          hashlib.sha256(zp.read_bytes()).hexdigest())
