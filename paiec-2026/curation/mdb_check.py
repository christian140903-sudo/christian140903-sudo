#!/usr/bin/env python3
"""mdb_check.py — Prüfwerkzeug für eine lokale measurement-db-Basis (formatted_tables, wie von build_basis.py abgelegt).

Prüft fünf Dinge und trennt dabei streng zwischen INTEGRITÄTSFEHLERN (Daten widersprechen sich selbst oder dem Schema)
und KURATIERUNGSBEFUNDEN (Daten sind in sich konsistent, aber für Nutzer heikel; werden gezählt und gelistet):
  1. Schema          Pflichtspalten/-typen in benchmarks, subjects, items/<bm>, responses/benchmark=<bm>; Katalog konsistent
                     (b_code eindeutig, folder = benchmark_id, Zeilenzahlen = Katalog-Fußzeile, Fremdschlüssel, keine doppelten
                     Beobachtungsschlüssel, binäre Antworten nur {0, 1, null})                                  -> FEHLER
  2. Polarität       `direction` je Benchmark; Widerspruch zwischen `direction` und `response_scale.direction` -> FEHLER;
                     binäre Benchmarks mit lower_is_better / unordered / ohne direction                           -> BEFUND (Zählung)
  3. Identität       subject_id je Benchmark eindeutig -> FEHLER; Subjekte eines Benchmarks mit identischen acht Wettbewerbs-
                     feldern (normalized_name, provider, release_date, access_date, harness, harness_version, reasoning_effort,
                     subject_features_extra; null = "")                                                            -> BEFUND
  4. Loader-Abdeckung  binär+public+coverage>0 („eligible") gegen `seen_by_baseline_script` (Sichtbarkeits-Grenze der
                     ersten 100 000 Dateien von `repo_info().siblings`, lokal als Ordner <= 'helm_afr' abgelegt)   -> BEFUND
  5. Wiederholungen  je binärem Benchmark: Zellen (Subjekt, Item) mit n >= 2 Antworten, Anteil, unverzerrte Rauschschranke
                     Σ n·k(n−k)/(n(n−1)) / Σ n (antwortgewichtet)                                                   -> INFO

Rückgabecodes: 0 = keine Integritätsfehler · 1 = Integritätsfehler (oder mit --streng: Befunde) · 2 = Datei fehlt / nicht
lesbar / Parse-Fehler (fail-closed: keine Teilaussage). Bericht als JSON (--aus), Kurzfassung auf stdout.
Keine Item-Texte werden gelesen oder ausgegeben; nur IDs, Hashes, Zählungen. Kein Netz, kein Token.
Aufruf: python3 -I mdb_check.py --basis DIR [--aus bericht.json] [--streng] [--ohne-wiederholung] [--nur bm1,bm2]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

FELDER8 = ("normalized_name", "provider", "release_date", "access_date", "harness", "harness_version",
           "reasoning_effort", "subject_features_extra")
SCHEMA = {
    "benchmarks": {"benchmark_id": "object", "folder": "object", "b_code": "int", "response_type": "object",
                   "release": "object", "coverage": "float", "rows_subjects": "int", "rows_items": "int",
                   "rows_responses": "int", "direction": "object", "response_scale": "object"},
    "subjects": {"s_code": "int", "benchmark_id": "object", "subject_id": "object", **{f: "object" for f in FELDER8}},
    "items": {"i_code": "int", "benchmark_id": "object", "item_id": "object", "content_hash": "object"},
    "responses": {"b_code": "int", "s_code": "int", "i_code": "int", "trial": "int", "test_condition": "object",
                  "interactors": "object", "response": "float"},
}
T0 = time.time()


class Pruefung:
    def __init__(self):
        self.fehler, self.befunde, self.info = [], [], {}

    def f(self, text):
        self.fehler.append(text)

    def b(self, text):
        self.befunde.append(text)


def typ_ok(dtype, soll):
    s = str(dtype)
    if soll == "int":
        return s.startswith("int") or s.startswith("uint")
    if soll == "float":
        return s.startswith("float") or s.startswith("int")
    return True  # object/string/dictionary/category akzeptiert


def lies(pfad, spalten=None):
    """Parquet lesen; jede Ausnahme ist ein Fail-closed-Abbruch (rc 2)."""
    if not Path(pfad).exists():
        raise FileNotFoundError(str(pfad))
    try:
        return pd.read_parquet(pfad, columns=spalten)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"nicht lesbar: {pfad}: {type(e).__name__}: {e}") from e


def pruefe_schema(df, name, P, pfad):
    for sp, soll in SCHEMA[name].items():
        if sp not in df.columns:
            P.f(f"{pfad}: Spalte fehlt: {sp}")
        elif not typ_ok(df[sp].dtype, soll):
            P.f(f"{pfad}: Spalte {sp} hat Typ {df[sp].dtype}, erwartet {soll}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", required=True)
    ap.add_argument("--aus", default=None, help="JSON-Bericht (Standard: stdout-Kurzfassung nur)")
    ap.add_argument("--streng", action="store_true", help="Befunde zählen als Fehler (rc 1)")
    ap.add_argument("--ohne-wiederholung", action="store_true")
    ap.add_argument("--nur", default=None, help="Komma-Liste von Benchmark-Ordnern (Teilprüfung; Katalog bleibt ganz)")
    a = ap.parse_args()
    basis = Path(a.basis)
    P = Pruefung()
    bericht = {"basis": str(basis), "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        rc = pruefe(basis, a, P, bericht)
    except (FileNotFoundError, RuntimeError, KeyError, ValueError) as e:
        bericht["abbruch"] = f"{type(e).__name__}: {e}"
        bericht["rc"] = 2
        ausgabe(bericht, P, a)
        return 2
    bericht["rc"] = rc
    ausgabe(bericht, P, a)
    return rc


def ausgabe(bericht, P, a):
    bericht["fehler"] = P.fehler
    bericht["befunde"] = P.befunde
    bericht["info"] = P.info
    bericht["kehrseite"] = ("rc 0 belegt Selbstkonsistenz (Schema, Zeilenzahlen, Schlüssel, Wertebereich) und das Fehlen bekannter "
                            "Befundklassen, nicht die Richtigkeit der Labels (z. B. bird_sql-Konfigurationen mit 0/360 sind formal gültig). "
                            "Wiederholungs-Statistik hier ohne Modell-Ausschlüsse (F3/F4) und inkl. withheld-Benchmarks; die Modellzahl steht "
                            "in wiederholung_b.json.")
    if a.aus:
        Path(a.aus).write_text(json.dumps(bericht, indent=1, default=str))
    print(f"mdb_check {bericht['basis']}: rc={bericht['rc']}  Fehler={len(P.fehler)}  Befunde={len(P.befunde)}"
          + (f"  ABBRUCH: {bericht['abbruch']}" if "abbruch" in bericht else ""))
    for t in P.fehler[:20]:
        print("  FEHLER ", t)
    for t in P.befunde[:20]:
        print("  BEFUND ", t)
    for k, v in P.info.items():
        if not isinstance(v, (list, dict)):
            print(f"  INFO    {k} = {v}")


def pruefe(basis, a, P, bericht):
    # ---- 1. Katalog + Schema
    bm = lies(basis / "benchmarks.parquet")
    pruefe_schema(bm, "benchmarks", P, "benchmarks.parquet")
    if P.fehler:
        return 1
    if not bm.b_code.is_unique:
        P.f("benchmarks.parquet: b_code nicht eindeutig")
    if not bm.benchmark_id.is_unique:
        P.f("benchmarks.parquet: benchmark_id nicht eindeutig")
    if (bm.folder != bm.benchmark_id).any():
        P.f(f"benchmarks.parquet: folder != benchmark_id in {(bm.folder != bm.benchmark_id).sum()} Zeilen")
    sub = lies(basis / "subjects.parquet")
    pruefe_schema(sub, "subjects", P, "subjects.parquet")
    if P.fehler:
        return 1
    if not sub.s_code.is_unique:
        P.f("subjects.parquet: s_code nicht eindeutig")
    unbekannt = set(sub.benchmark_id) - set(bm.benchmark_id)
    if unbekannt:
        P.f(f"subjects.parquet: {len(unbekannt)} benchmark_id nicht im Katalog")
    dup_sid = sub.duplicated(["benchmark_id", "subject_id"]).sum()
    if dup_sid:
        P.f(f"subjects.parquet: subject_id je Benchmark nicht eindeutig ({dup_sid} Dubletten)")
    rows_sub = sub.groupby("benchmark_id").size()
    bm_rows_sub = bm.set_index("benchmark_id").rows_subjects
    abw = [(b, int(rows_sub.get(b, 0)), int(bm_rows_sub[b])) for b in bm.benchmark_id if rows_sub.get(b, 0) != bm_rows_sub[b]]
    if abw:
        P.f(f"subjects.parquet: Zeilenzahl != Katalog rows_subjects bei {len(abw)} Benchmarks, z. B. {abw[:3]}")
    P.info["benchmarks"] = int(len(bm))
    P.info["subjects"] = int(len(sub))

    # ---- 2. Polarität
    binaer = bm[bm.response_type == "binary"]
    pol = {"binaer": int(len(binaer)),
           "higher_is_better": int((binaer.direction == "higher_is_better").sum()),
           "lower_is_better": sorted(binaer.loc[binaer.direction == "lower_is_better", "benchmark_id"]),
           "unordered": sorted(binaer.loc[binaer.direction == "unordered", "benchmark_id"]),
           "ohne_direction": sorted(binaer.loc[binaer.direction.isna() | (binaer.direction.astype(str) == ""), "benchmark_id"])}
    if pol["lower_is_better"]:
        P.b(f"Polarität: {len(pol['lower_is_better'])} binäre Benchmarks lower_is_better (1 = unerwünscht): {pol['lower_is_better']}")
    if pol["unordered"]:
        P.b(f"Polarität: {len(pol['unordered'])} binäre Benchmarks unordered: {pol['unordered']}")
    if pol["ohne_direction"]:
        P.b(f"Polarität: {len(pol['ohne_direction'])} binäre Benchmarks ohne direction: {pol['ohne_direction']}")
    widerspruch = []
    for r in bm.itertuples(index=False):
        try:
            sc = json.loads(r.response_scale) if isinstance(r.response_scale, str) and r.response_scale else {}
        except json.JSONDecodeError:
            P.f(f"{r.benchmark_id}: response_scale kein gültiges JSON")
            continue
        d = sc.get("direction")
        if d is not None and isinstance(r.direction, str) and r.direction and d != r.direction:
            widerspruch.append((r.benchmark_id, d, r.direction))
        if r.response_type == "binary" and "values" in sc and sorted(sc["values"]) != [0.0, 1.0]:
            P.f(f"{r.benchmark_id}: binär, aber response_scale.values = {sc['values']}")
    if widerspruch:
        P.f(f"Polarität: direction widerspricht response_scale.direction bei {len(widerspruch)}: {widerspruch[:5]}")
    P.info["polaritaet"] = pol

    # ---- 3. Identitäts-Duplikate (acht Wettbewerbsfelder identisch innerhalb eines Benchmarks)
    S8 = sub[list(FELDER8)].copy()
    for f in FELDER8:
        S8[f] = S8[f].map(lambda x: "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x))
    schluessel = sub.benchmark_id.astype(str) + "\x1f" + S8.apply(lambda r: "\x1f".join(r.values), axis=1)
    gz = schluessel.value_counts()
    gruppen = gz[gz >= 2]
    betroffen = int(gruppen.sum())
    ident = {"gruppen": int(len(gruppen)), "subjekte": betroffen,
             "benchmarks": sorted(set(k.split("\x1f", 1)[0] for k in gruppen.index)),
             "anteil_normalized_name_leer": float((S8.normalized_name == "").mean())}
    if betroffen:
        P.b(f"Identität: {betroffen} Subjekte in {len(gruppen)} Gruppen ({len(ident['benchmarks'])} Benchmarks) erhalten identischen "
            f"Wettbewerbs-Input (alle acht Felder gleich); Benchmarks: {ident['benchmarks']}")
    P.info["identitaet"] = ident

    # ---- 4. Loader-Abdeckung
    elig = bm[(bm.response_type == "binary") & (bm.release == "public") & (bm.coverage.fillna(0) > 0)]
    if "seen_by_baseline_script" in bm.columns:
        gesehen = elig.seen_by_baseline_script.astype(bool)
        quelle = "Spalte seen_by_baseline_script"
    else:
        gesehen = elig.folder <= "helm_afr"
        quelle = "abgeleitet: folder <= 'helm_afr' (Sichtbarkeitsgrenze 100 000 siblings)"
    lad = {"eligible": int(len(elig)), "im_loader": int(gesehen.sum()), "fehlend": int((~gesehen).sum()),
           "fehlend_liste": sorted(elig.loc[~gesehen, "benchmark_id"]), "quelle": quelle}
    if lad["fehlend"]:
        P.b(f"Loader-Abdeckung: {lad['fehlend']} von {lad['eligible']} eligible Benchmarks außerhalb der Sichtbarkeit des "
            f"Baseline-Loaders ({quelle})")
    P.info["loader_abdeckung"] = lad

    # ---- 5. Items + Antworten je Benchmark (Integrität) + Wiederholungen
    nur = set(a.nur.split(",")) if a.nur else None
    i_codes_gesamt = set()
    wdh = []
    n_resp_gesamt = 0
    s_codes = set(sub.s_code.tolist())
    for r in bm.sort_values("b_code").itertuples(index=False):
        if nur and r.folder not in nur:
            continue
        ip = basis / "items" / f"{r.folder}.parquet"
        rp = basis / "responses" / f"benchmark={r.folder}" / "part-0.parquet"
        it = lies(ip, ["i_code", "benchmark_id", "item_id", "content_hash"])
        pruefe_schema(it, "items", P, str(ip))
        if P.fehler:
            return 1
        if len(it) != int(r.rows_items):
            P.f(f"{r.folder}: items Zeilen {len(it)} != Katalog rows_items {int(r.rows_items)}")
        if not it.item_id.is_unique:
            P.f(f"{r.folder}: item_id nicht eindeutig")
        if (it.benchmark_id.astype(str) != r.benchmark_id).any():
            P.f(f"{r.folder}: items.benchmark_id abweichend")
        ic = set(it.i_code.tolist())
        if ic & i_codes_gesamt:
            P.f(f"{r.folder}: i_code nicht global eindeutig")
        i_codes_gesamt |= ic
        rs = lies(rp)
        pruefe_schema(rs, "responses", P, str(rp))
        if P.fehler:
            return 1
        if len(rs) != int(r.rows_responses):
            P.f(f"{r.folder}: responses Zeilen {len(rs)} != Katalog rows_responses {int(r.rows_responses)}")
        if (rs.b_code != r.b_code).any():
            P.f(f"{r.folder}: responses.b_code abweichend")
        fk_s = (~rs.s_code.isin(s_codes)).sum()
        fk_i = (~rs.i_code.isin(ic)).sum()
        if fk_s or fk_i:
            P.f(f"{r.folder}: verwaiste Fremdschlüssel (Subjekt {fk_s}, Item {fk_i})")
        dup = rs.duplicated(["s_code", "i_code", "trial", "test_condition", "interactors"]).sum()
        if dup:
            P.f(f"{r.folder}: {dup} doppelte Beobachtungsschlüssel")
        resp = rs.response.dropna()
        if r.response_type == "binary" and len(resp) and not resp.isin([0.0, 1.0]).all():
            P.f(f"{r.folder}: binär, aber {int((~resp.isin([0.0, 1.0])).sum())} Antworten außerhalb {{0,1}}")
        if len(resp) and not pd.Series(resp).map(lambda x: x == x and abs(x) != float("inf")).all():
            P.f(f"{r.folder}: nicht-endliche Antworten")
        n_resp_gesamt += len(rs)
        if r.response_type == "binary" and not a.ohne_wiederholung and len(resp):
            z = rs.dropna(subset=["response"]).groupby(["s_code", "i_code"], sort=False)["response"].agg(n="count", k="sum")
            rep = z[z.n >= 2]
            l10 = float((rep.k * (rep.n - rep.k) / (rep.n - 1)).sum() / rep.n.sum()) if len(rep) else None
            wdh.append({"benchmark_id": r.folder, "zellen": int(len(z)), "zellen_n_ge2": int(len(rep)),
                        "anteil_zellen_n_ge2": float(len(rep) / len(z)), "antworten": int(z.n.sum()),
                        "L10_antwortgewichtet": l10, "n_max": int(z.n.max())})
    P.info["antworten_gepruefte_benchmarks"] = int(n_resp_gesamt)
    if wdh:
        W = pd.DataFrame(wdh)
        P.info["wiederholung"] = {
            "benchmarks_binaer_gepruefte": int(len(W)), "benchmarks_mit_wiederholung": int((W.zellen_n_ge2 > 0).sum()),
            "anteil_zellen_n_ge2_gesamt": float(W.zellen_n_ge2.sum() / W.zellen.sum()),
            "L10_median_bm_mit_>=100_wdh_zellen": (float(W.loc[W.zellen_n_ge2 >= 100, "L10_antwortgewichtet"].median())
                                                  if (W.zellen_n_ge2 >= 100).any() else None),
            "je_benchmark": wdh}
    bericht["info_kurz"] = {k: v for k, v in P.info.items() if not isinstance(v, (list, dict))}
    if P.fehler:
        return 1
    if a.streng and P.befunde:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
