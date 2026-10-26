#!/usr/bin/env python3
"""Identitäts-Reparaturtabelle (P8; Vorschlag an die Kuratoren von measurement-db).

Frage: Bei 58 % der Subjektzeilen ist `normalized_name` leer. Trägt das zur Testzeit sichtbare Feld `subject_features_extra`
einen Modellbezeichner, aus dem sich ein `normalized_name` ableiten ließe? (D-merkmale §2.3 zählte 74 %; hier eigener Weg.)

Verfahren (nur Subjekt-Metadaten; keine Item-Texte):
  1. `subject_features_extra` als 'k=v;k=v' zerlegen. Bezeichner-Schlüssel in Prioritätsfolge: model_identifier, source_model_label,
     reported_model, source_model, base_model, source_model_filename, source_model_token, checkpoint_path, model_name, model, model_id;
     danach jeder weitere Schlüssel, der 'model' enthält und dessen Wert kein Status-Text ist (nicht 'not_recorded', keine Leerzeichen).
  2. Normalisieren: Kleinbuchstaben, Pfadpräfixe/Org-Präfixe ('org__name', 'org/name') abschneiden, nur a-z0-9 behalten.
  3. Abgleich mit der Menge der bekannten `normalized_name` (gleich normalisiert):
       exact        – normalisierter Bezeichner = bekannter Name
       contains     – Bezeichner enthält genau einen bekannten Namen (≥ 5 Zeichen) als Teilstring; bei mehreren: den längsten
       cross_bm     – kein bekannter Name, aber derselbe Bezeichner tritt namenlos in ≥ 2 Benchmarks auf (Vorschlag: neuer Registry-Eintrag)
       single_bm    – Bezeichner nur in einem Benchmark (für Transfer wertlos, aber als Label dokumentierbar)
       none         – kein Bezeichner gefunden
Ausgabe: identitaet_reparatur.csv (eine Zeile je namenlosem Subjekt: benchmark_id, subject_id, s_code, quelle_schluessel,
bezeichner_roh, bezeichner_norm, vorschlag_normalized_name, konfidenz, n_benchmarks_bezeichner, display_name_entspricht),
identitaet_zusammenfassung.json. Fail-closed bei fehlender Datei. rc 0 = gelaufen.
Aufruf: PAIEC_WORK=... python3 -I identitaet.py
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
WORK = Path(os.environ.get("PAIEC_WORK", "work"))
PRIO = ["model_identifier", "source_model_label", "reported_model", "source_model", "base_model", "source_model_filename",
        "source_model_token", "checkpoint_path", "model_name", "model", "model_id"]
STATUS_WERTE = {"", "not_recorded", "unknown", "none", "null", "n/a", "na", "unrecorded", "literal_published_label",
                "upstream_filename_only"}


def norm(s: str) -> str:
    s = s.strip().lower()
    s = s.split("/")[-1] if "/" in s else s          # Pfad -> letzter Teil
    s = re.sub(r"^[a-z0-9.\-]+__", "", s)             # 'org__name' -> 'name'
    return re.sub(r"[^a-z0-9]", "", s)


def zerlege(extra):
    if not isinstance(extra, str) or not extra:
        return {}
    kv = {}
    for teil in extra.split(";"):
        if "=" in teil:
            k, v = teil.split("=", 1)
            kv.setdefault(k.strip(), v.strip())
    return kv


def bezeichner(kv):
    for k in PRIO:
        v = kv.get(k)
        if v and v.lower() not in STATUS_WERTE and " " not in v.strip():
            return k, v
    for k, v in kv.items():
        if "model" in k.lower() and k not in PRIO and v and v.lower() not in STATUS_WERTE and " " not in v.strip() and len(v) < 120:
            return k, v
    return None, None


def main():
    sub = pd.read_parquet(WORK / "basis" / "subjects.parquet")
    leer = sub.normalized_name.isna() | (sub.normalized_name.astype(str).str.strip() == "")
    bekannt_norm = {}
    for nm in sub.loc[~leer, "normalized_name"].astype(str).unique():
        bekannt_norm.setdefault(norm(nm), nm)
    bekannt_lang = sorted((k for k in bekannt_norm if len(k) >= 5), key=len, reverse=True)
    N = sub[leer].copy()
    quelle, roh, nrm = [], [], []
    for extra in N.subject_features_extra:
        k, v = bezeichner(zerlege(extra))
        quelle.append(k or "")
        roh.append(v or "")
        nrm.append(norm(v) if v else "")
    N["quelle_schluessel"], N["bezeichner_roh"], N["bezeichner_norm"] = quelle, roh, nrm
    # Verbreitung je Bezeichner über Benchmarks (nur namenlose Zeilen)
    bm_je_bez = defaultdict(set)
    for b, z in zip(N.benchmark_id, N.bezeichner_norm):
        if z:
            bm_je_bez[z].add(b)
    vorschlag, konf, nbm, dn_gleich = [], [], [], []
    for z, dn in zip(N.bezeichner_norm, N.display_name.astype(str)):
        dn_gleich.append(bool(z) and norm(dn) == z)
        if not z:
            vorschlag.append(""); konf.append("none"); nbm.append(0); continue
        nbm.append(len(bm_je_bez[z]))
        if z in bekannt_norm:
            vorschlag.append(bekannt_norm[z]); konf.append("exact"); continue
        treffer = [k for k in bekannt_lang if k in z]
        if treffer:
            vorschlag.append(bekannt_norm[treffer[0]]); konf.append("contains"); continue
        if len(bm_je_bez[z]) >= 2:
            vorschlag.append(f"NEU:{z}"); konf.append("cross_bm")
        else:
            vorschlag.append(""); konf.append("single_bm")
    N["vorschlag_normalized_name"], N["konfidenz"], N["n_benchmarks_bezeichner"], N["display_name_entspricht"] = vorschlag, konf, nbm, dn_gleich
    aus = N[["benchmark_id", "subject_id", "s_code", "quelle_schluessel", "bezeichner_roh", "bezeichner_norm",
             "vorschlag_normalized_name", "konfidenz", "n_benchmarks_bezeichner", "display_name_entspricht"]]
    aus.to_csv(HIER / "identitaet_reparatur.csv", index=False)
    mit = aus.bezeichner_norm != ""
    zus = {"zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "subjektzeilen_gesamt": int(len(sub)), "namenlos": int(len(aus)), "anteil_namenlos": float(len(aus) / len(sub)),
           "namenlos_mit_bezeichner": int(mit.sum()), "anteil_mit_bezeichner": float(mit.mean()),
           "bezeichner_verschieden": int(aus.loc[mit, "bezeichner_norm"].nunique()),
           "bezeichner_in_>=2_benchmarks": int(sum(1 for z, b in bm_je_bez.items() if len(b) >= 2)),
           "konfidenz_zaehlung": {k: int(v) for k, v in aus.konfidenz.value_counts().items()},
           "quelle_schluessel_zaehlung": {k: int(v) for k, v in Counter(q for q in aus.quelle_schluessel if q).most_common(15)},
           "display_name_entspricht_anteil_bei_bezeichner": float(aus.loc[mit, "display_name_entspricht"].mean()),
           "benchmarks_mit_namenlosen": int(aus.benchmark_id.nunique()),
           "vorschlaege_bekannter_name": int(aus.konfidenz.isin(["exact", "contains"]).sum()),
           "top_vorgeschlagene_namen": {k: int(v) for k, v in aus.loc[aus.konfidenz.isin(["exact", "contains"]), "vorschlag_normalized_name"].value_counts().head(15).items()},
           "kehrseite": ("Vorschläge der Klasse 'contains' können Varianten verwechseln (z. B. 'gpt4' in 'gpt4o'); sie sind Kuratoren-"
                         "Hinweise, keine Zuordnungen. Score-Wirkung einer Reparatur laut C §5 / D-merkmale §2.3 < 0,001 ALC.")}
    (HIER / "identitaet_zusammenfassung.json").write_text(json.dumps(zus, indent=1))
    print(json.dumps(zus, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
