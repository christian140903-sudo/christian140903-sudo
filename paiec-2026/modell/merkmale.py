"""Subjekt-Merkmale — NUR Standardbibliothek (identisch in Training und Paket).

Nur Felder, die zur Testzeit sichtbar sind (Wettbewerbsseite, Predictor Interface): die 8 Subjektfelder als Strings.
"""
import math
import re

FELDER = ("normalized_name", "provider", "release_date", "access_date", "harness", "harness_version",
          "reasoning_effort", "subject_features_extra")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_GROESSE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*([bm])(?![a-z0-9])")
_DATUM = re.compile(r"^\s*(\d{4})(?:-(\d{1,2}))?")


def _s(x):
    return "" if x is None else str(x)


def konfig(subject):
    """Volle Testzeit-Identität: alle 8 Felder. Gleiche Konfig = für den Prädiktor dasselbe Subjekt."""
    return "\x1f".join([_s(subject.get(f)) for f in FELDER])


def name_schluessel(subject):
    n = " ".join(_s(subject.get("normalized_name")).split()).casefold()
    return n or None


def jahr(datum):
    m = _DATUM.match(_s(datum))
    if not m:
        return None
    j = int(m.group(1))
    if not 1990 <= j <= 2100:
        return None
    monat = int(m.group(2)) if m.group(2) else 6
    return j + (min(max(monat, 1), 12) - 0.5) / 12.0


def groesse_mrd(name):
    """Parameterzahl in Milliarden aus dem Namen ('70B', '1.5b', '350M'), sonst None."""
    werte = []
    for zahl, einheit in _GROESSE.findall(name):
        v = float(zahl) / (1000.0 if einheit == "m" else 1.0)
        if 0.01 <= v <= 5000:
            werte.append(v)
    return max(werte) if werte else None


def tokens(name):
    return sorted(set(_TOKEN.findall(name)))


def meta_merkmale(subject):
    """-> dict Merkmal -> Wert (dünn). Vokabular wird im Training festgelegt; unbekannte Schlüssel wirken 0."""
    name = name_schluessel(subject) or ""
    x = {}
    prov = " ".join(_s(subject.get("provider")).split()).casefold()
    if prov:
        x["prov=" + prov] = 1.0
    else:
        x["prov_fehlt"] = 1.0
    if not name:
        x["name_fehlt"] = 1.0
    for t in tokens(name):
        x["tok=" + t] = 1.0
    g = groesse_mrd(name)
    if g is None:
        x["groesse_fehlt"] = 1.0
    else:
        x["log10_groesse"] = math.log10(g)
    j = jahr(subject.get("release_date"))
    if j is None:
        x["jahr_fehlt"] = 1.0
    else:
        x["jahr"] = j - 2024.0
    if _s(subject.get("harness")).strip():
        x["harness_da"] = 1.0
    if _s(subject.get("reasoning_effort")).strip():
        x["effort_da"] = 1.0
    return x
