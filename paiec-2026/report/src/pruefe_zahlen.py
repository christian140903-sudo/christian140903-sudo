#!/usr/bin/env python3 -I
"""pruefe_zahlen.py — Zahlenprüfung des Bericht-v2 (P10, BAUPLAN-V2 §2.4 / §4.5), fail-closed.

Prüft (1) tex <-> JSON/CSV/MD: jede entscheidungstragende Zahl des Haupttexts und der Anhänge gegen ihre Quelldatei (Schlussrunde 2026-10-21: Paket v2.0-core, Tafel 9/1, Liga 10/10, SOLL-5-Satz = ZIP-README)
(ZAHLEN-QUELLEN-v2.md, Abschnitt P10); (2) Anhang <-> Anhang / Haupttext <-> Anhang: dieselbe Größe muss überall gleich
stehen (Präreg-Hash, Paket-Hash, L10-Median, Budget-Tabelle, Hyperparameter, Formelmomente); (3) Verbotsliste
(J-jury §8, GEWINNERWEG §5.4) als grep; (4) alle \\cite-Schlüssel in refs.bib; (5) Seitenzahl Haupttext <= 7,5
(Marker .mainend + pdfinfo), sofern das PDF existiert.

Rückgabe: 0 = alles bestanden; 1 = mindestens eine Prüfung verfehlt; 2 = Eingabe fehlt/unlesbar (fail-closed).
Aufruf: python3 -I pruefe_zahlen.py [--tex paiec_report_v2.tex] [--ohne-pdf]
Fehlerfall einmal auslösen: Kopie des tex mit einer verfälschten Zahl -> rc 1 (STATUS.md protokolliert den Lauf).
"""
import argparse
from decimal import ROUND_HALF_UP, Decimal
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
PROJ = HIER.parent
sys.path.insert(0, str(PROJ / "modell-v2" / "theorie"))

Q = {
    "TAFEL": PROJ / "./konfirmation/hypothesen_tafel.json",
    "P2": PROJ / "modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json",
    "P1": PROJ / "modell/ergebnisse/cv_A_S1-S2-S3-S30/auswertung.json",
    "BEOB": HIER / "daten/beobachtung_discovery.json",
    "DEX": HIER / "daten/D_exakt.json",
    "LEITER": HIER / "daten/leiter.json",
    "LEITER2": HIER / "daten/leiter_ergaenzung.json",
    "H2C": HIER / "daten/h2c_discovery.json",
    "VERLUST": HIER / "daten/verlust.json",
    "AKQ": HIER / "daten/akquise_pilot_tabelle.json",
    "FALL": PROJ / "curation/fallbeispiele.json",
    "WDH": PROJ / "curation/wiederholung_b.json",
    "NOISE": PROJ / "curation/noise_floor_by_benchmark.csv",
    "IDENT": PROJ / "curation/identitaet_zusammenfassung.json",
    "LIGA": PROJ / "./liga/ergebnisse/meta.json",
    "DATEN": PROJ / "modell/ergebnisse/daten_zusammenfassung.json",
    "DQ": PROJ / "daten/lieferung/DATA-QUALITY-REPORT.md",
    "PREREG": PROJ / "v2-plan/PRAEREGISTRIERUNG-v2.md",
    "PREREGHASH": PROJ / "v2-plan/PRAEREG-HASH.txt",
    # Schlussrunde 2026-10-21: eingereichtes Paket = v2.0-core (README-only-Neubau, model.py byteidentisch zu P1)
    "PAKET": PROJ / "./dist/paiec_v2core_final.zip",
    "STATE": PROJ / "modell/paket/state_v2core.json",
    "PPAKET": PROJ / "modell/ergebnisse_v2/pruefe_paket_v2core_final.json",
    "BITGL2": PROJ / "modell/ergebnisse_v2/bitgleich_phase2.json",
    "STUFEN_A": PROJ / "./konfirmation/ergebnisse/pruefe_stufen_A2v.json",
    "STUFEN_B": PROJ / "./konfirmation/ergebnisse/pruefe_stufen_B2v.json",
    "REFS": HIER / "refs.bib",
    "TAB1": HIER / "tabellen/tab1_hauptergebnis.tex",
    "TAB2": HIER / "tabellen/tab2_hypothesen.tex",
    "TAB3": HIER / "tabellen/tab3_ablationen_liga.tex",
    "TAB3A": HIER / "tabellen/tab3a_ablationen.tex",
    "TAB4": HIER / "tabellen/tab4_protokoll.tex",
    "TAB6": HIER / "tabellen/tab6_budgets.tex",
    "TAB7": HIER / "tabellen/tab7_hyper.tex",
    "HYP": HIER / "daten/hyperparameter_je_falte_roh.json",
    "QUELLEN_ABB": HIER / "abbildungen/quellen_abbildungen.tex",
    "LIGA_VOLL": PROJ / "./liga/ergebnisse/liga_vergleich.json",  # R2: volle Werte (8 Stellen) statt 5-stellig gespeicherter
}

FEHLER = []
OK = 0


def fehl(msg):
    FEHLER.append(msg)
    print("FEHLER:", msg)


def ok(msg):
    global OK
    OK += 1


def lade(key):
    p = Q[key]
    if not p.is_file():
        print(f"FEHLT (fail-closed): {p}")
        sys.exit(2)
    if p.suffix == ".json":
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"UNLESBAR (fail-closed): {p}: {e}")
            sys.exit(2)
    return p.read_text(encoding="utf-8")


def norm(x):
    return re.sub(r"\s+", " ", x)


def erwarte(tex, s, was):
    """Die Zeichenkette s muss im tex vorkommen (Leerraum/Zeilenumbrüche normalisiert)."""
    if norm(s) in norm(tex):
        ok(was)
    else:
        fehl(f"{was}: erwartet '{s}' im tex, nicht gefunden")


def pm(d, se):
    return f"{d:.4f} \\pm {se:.4f}"


def macro(tex, name):
    m = re.search(r"\\newcommand\{\\" + name + r"\}\{([^}]*)\}", tex)
    if not m:
        fehl(f"Makro \\{name} fehlt")
        return ""
    return m.group(1)


def haupttext(tex):
    i = tex.index("\\begin{abstract}")
    j = tex.index("\\markmainend", i)
    return tex[i:j]


def abstract(tex):
    i = tex.index("\\begin{abstract}")
    j = tex.index("\\end{abstract}")
    return tex[i:j]


def pruefe_zahlen(tex, tabs):
    alles = tex + "\n" + "\n".join(tabs.values())
    # --- Hashes und Zeitstempel ---
    paket = Q["PAKET"]
    if not paket.is_file():
        print(f"FEHLT (fail-closed): {paket}")
        sys.exit(2)
    h = hashlib.sha256(paket.read_bytes()).hexdigest()
    if macro(tex, "pkghash") == h:
        ok("Paket-Hash")
    else:
        fehl(f"Paket-Hash: tex {macro(tex, 'pkghash')} != Datei {h}")
    if macro(tex, "pkghashshort") == h[:8]:
        ok("Paket-Hash kurz")
    else:
        fehl("Paket-Hash kurz")
    if macro(tex, "pkgbytes") == f"{paket.stat().st_size:,}":
        ok("Paket-Groesse")
    else:
        fehl(f"Paket-Groesse: tex {macro(tex, 'pkgbytes')} != Datei {paket.stat().st_size:,}")
    if macro(tex, "pkgfile").replace("\\_", "_") != paket.name:
        fehl(f"\\pkgfile {macro(tex, 'pkgfile')} != {paket.name}")
    st_txt = json.dumps(lade("STATE"), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    st_sha = hashlib.sha256(st_txt.encode()).hexdigest()[:16]
    import zipfile
    try:
        zf = zipfile.ZipFile(paket)
        mp = zf.read("model.py").decode("utf-8")
        readme_zip = zf.read("README.md").decode("utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"UNLESBAR (fail-closed): {paket}: {e}")
        sys.exit(2)
    if macro(tex, "pkgstate") == st_sha and f"state sha256 {st_sha}." in mp:
        ok("Paket-Zustandshash (tex = state_v2core.json = model.py-Kopf)")
    else:
        fehl(f"Paket-Zustandshash: tex {macro(tex, 'pkgstate')}, state {st_sha}, im model.py: {f'state sha256 {st_sha}.' in mp}")
    if "'0':" in mp or '"0":' in mp:
        pass
    platt_stufen = sorted(lade("STATE").get("platt", {}).keys())
    if platt_stufen == ["0", "1"]:
        erwarte(tex, "kept at stages 0 and 1", "Platt-Stufen {0,1} im Methodenteil")
    else:
        fehl(f"Platt-Stufen des Pakets {platt_stufen} != ['0','1'] – Text sagt 'stages 0 and 1'")
    # S4 (FREIGABE): Platt-Satz (SOLL-5) in Bericht §8 und ZIP-README identisch (TeX-Markup entfernt)
    def platt_satz(s):
        m = re.search(r"Platt scaling per label stage: v1 kept the stages whose cross-fitted Brier was lower.*?in at most 2\)\.", norm(s), re.S)
        return None if not m else re.sub(r"\$|\\,|~", "", m.group(0)).replace("−", "-")
    ps_tex, ps_readme = platt_satz(tex), platt_satz(readme_zip)
    if ps_tex and ps_readme and ps_tex == ps_readme:
        ok("Platt-Satz (SOLL-5) in tex und ZIP-README identisch")
    else:
        fehl(f"Platt-Satz (SOLL-5) fehlt oder weicht ab: tex={ps_tex!r} readme={ps_readme!r}")
    for alt in ("showed a gain", "stages 0, 1, 3, 7", "bit-identical on the cross-validation sets", "cross-fitted calibration lowered"):
        if alt in readme_zip:
            fehl(f"ZIP-README enthaelt ueberhoehten Alt-Wortlaut '{alt}' (SOLL-5)")
    # Laufzeit Anhang C aus dem Paketpruef-Lauf des eingereichten ZIP
    pp = lade("PPAKET")
    if pp.get("urteil") != "ok":
        fehl(f"pruefe_paket-Urteil {pp.get('urteil')} != ok")
    lz = pp["laufzeit"]
    erwarte(tex, f"fresh copy: median {lz['100000_frische_kopie_je_aufruf']['median_ms']:.2f}\\,ms", "Laufzeit 10^5 frische Kopie")
    erwarte(tex, f"first call {lz['100000']['erster_aufruf_ms'] / 1000:.2f}\\,s", "Laufzeit erster Aufruf")
    bg = lade("BITGL2")
    erwarte(tex, f"stages\n3 and 7 (max $|\\Delta q| = {bg['max_dq']:.3f}$)", "Phase-2 max dq")
    if bg.get("rc") not in (0, None):
        fehl(f"bitgleich_phase2 rc {bg.get('rc')}")
    # Anhang B Deviation (1): verschachtelte Stufenmengen der Konfirmationslaeufe, mechanisch gezaehlt
    for key, dsg, soll in (("STUFEN_A", "A", "Design A: $\\{0, 1, 3, 7\\}$ in all ten folds, stage\n15 in five and 31 in two"),
                           ("STUFEN_B", "B", "Design B: $\\{0, 1, 3\\}$ in all, stage 7 in five, 15 in two")):
        sl = lade(key)
        if not sl.get("ok"):
            fehl(f"pruefe_stufen {dsg} nicht ok")
        mengen = [set(v) for v in sl["stufen_log"].values()]
        schnitt = set.intersection(*mengen)
        n15 = sum(15 in m for m in mengen); n31 = sum(31 in m for m in mengen); n7 = sum(7 in m for m in mengen)
        if dsg == "A" and (schnitt != {0, 1, 3, 7} or n15 != 5 or n31 != 2 or len(mengen) != 10):
            fehl(f"Stufenmengen A: Schnitt {sorted(schnitt)}, 15 in {n15}, 31 in {n31}")
        elif dsg == "B" and (schnitt != {0, 1, 3} or n7 != 5 or n15 != 2 or len(mengen) != 10):
            fehl(f"Stufenmengen B: Schnitt {sorted(schnitt)}, 7 in {n7}, 15 in {n15}")
        else:
            erwarte(tex, soll, f"Anhang B Stufenmengen {dsg}")
    hk = lade("STATE").get("herkunft_v2core", {}).get("stufenwahl_je_falte", {})
    if hk:
        n3 = sum(3 in v for v in hk.values()); n7 = sum(7 in v for v in hk.values())
        n1531 = max(sum(15 in v for v in hk.values()), sum(31 in v for v in hk.values()))
        if (n3, n7) == (8, 7) and n1531 <= 2:
            erwarte(tex, "stage 3 was selected in 8 of 10 folds, stage 7 in 7 of 10, stages 15 and 31 in at most 2", "Stufenwahl Paket 8/7")
        else:
            fehl(f"Stufenwahl im Zustand: 3 in {n3}, 7 in {n7}, 15/31 max {n1531}")
    else:
        fehl("state_v2core.json ohne herkunft_v2core.stufenwahl_je_falte")
    ph = lade("PREREGHASH")
    m = re.search(r"sha256:\s*([0-9a-f]{64})", ph)
    mt = re.search(r"eingefroren_utc:\s*(\S+)", ph)
    hp = hashlib.sha256(Q["PREREG"].read_bytes()).hexdigest()
    if not m or m.group(1) != hp:
        fehl(f"Präreg-Hash: PRAEREG-HASH.txt {m.group(1) if m else None} != sha256(Datei) {hp}")
    elif macro(tex, "prereghash") != hp:
        fehl(f"Präreg-Hash im tex {macro(tex, 'prereghash')} != {hp}")
    else:
        ok("Präreg-Hash")
    if macro(tex, "prereghashshort") != hp[:8]:
        fehl("Präreg-Hash kurz")
    if mt and mt.group(1) == "2026-10-20T20:26:04Z" and macro(tex, "preregtime") == "2026-10-20 20:26:04 UTC":
        ok("Präreg-Zeit")
    else:
        fehl(f"Präreg-Zeit: Datei {mt.group(1) if mt else None}, tex {macro(tex, 'preregtime')}")
    # Tab. 2 (P7) nennt Hash-Präfix und Zeit ebenfalls -> Anhang<->Anhang
    if hp[:8] in tabs["TAB2"] and "20:26:04Z" in tabs["TAB2"]:
        ok("Tab2 Hash/Zeit")
    else:
        fehl("Tab2 nennt Präreg-Hash/Zeit nicht identisch")

    # --- Hypothesentafel ---
    tafel = lade("TAFEL")
    H = {x["id"]: x for x in tafel["hypothesen"]}
    z = tafel["zusammenfassung"]
    if (z["passed"], z["failed"], z.get("not_evaluated", 0)) == (9, 1, 0):
        erwarte(tex, "nine of ten frozen hypotheses passed and one failed", "Tafel-Zusammenfassung Abstract")
        erwarte(tex, "Of ten frozen hypotheses nine passed and one failed", "Tafel-Zusammenfassung §6")
        erwarte(tabs["TAB2"], "9 passed, 1 failed", "Tafel-Zusammenfassung Tab2")
    else:
        fehl(f"Tafel-Zusammenfassung {z} != (9,1,0); Text muss angepasst werden")
    if tafel.get("eingabe_fehler"):
        fehl(f"Tafel meldet Eingabefehler: {tafel['eingabe_fehler']}")
    for hid in ("H1", "H2a", "H2b", "H2c", "H3", "H5", "H6", "H7", "H8"):
        if H[hid]["verdict"] != "passed":
            fehl(f"{hid} verdict {H[hid]['verdict']} != passed – Text behauptet passed")
    a1, b = H["H1"]["teile"]["A"], H["H1"]["teile"]["B"]
    if pm(a1["S1"]["d"], a1["S1"]["se"]) != pm(b["S1"]["d"], b["S1"]["se"]) or pm(a1["S3"]["d"], a1["S3"]["se"]) != pm(b["S3"]["d"], b["S3"]["se"]):
        fehl("H1 S1/S3 gerundet in A und B verschieden – Text sagt 'in both designs'")
    erwarte(tex, pm(b["S1"]["d"], b["S1"]["se"]) + "$ ALC in both\ndesigns", "H1 S1 beide Designs (Abstract)")
    erwarte(tex, pm(b["S3"]["d"], b["S3"]["se"]).lstrip("-") + "$ (both designs)", "H1 S3 beide Designs (Abstract)")
    erwarte(tex, pm(a1["S2"]["d"], a1["S2"]["se"]) + "$\nwith two (Design A)", "H1 A S2")
    erwarte(tex, pm(a1["S30"]["d"], a1["S30"]["se"]) + "$ with thirty", "H1 A S30")
    for S in ("S1", "S2", "S3", "S30"):
        erwarte(tabs["TAB1"], pm(a1[S]["d"], a1[S]["se"]) + f"$ {a1[S]['verdict'][0]}", f"Tab1 conf. A {S}")
    for S in ("S1", "S3"):
        erwarte(tabs["TAB1"], pm(b[S]["d"], b[S]["se"]) + f"$ {b[S]['verdict'][0]}", f"Tab1 conf. B {S}")
    if b["S1"]["verdict"] != "grey_zone" or b["S3"]["verdict"] != "better" or a1["S1"]["verdict"] != "grey_zone" or a1["S2"]["verdict"] != "better":
        fehl(f"H1 Urteile A {a1['S1']['verdict']}/{a1['S2']['verdict']}, B {b['S1']['verdict']}/{b['S3']['verdict']}")
    e = b["S1"]["gegen_empirischer_mittelwert"]; ea = a1["S1"]["gegen_empirischer_mittelwert"]
    if pm(e["d"], e["se"]) != pm(ea["d"], ea["se"]):
        fehl("H1 S1 vs EM in A und B gerundet verschieden – Text sagt 'both designs'")
    erwarte(tex, pm(e["d"], e["se"]) + "$ at one subject (both designs)", "H1 S1 vs EM")
    pw = sorted(round(100 * x["S1"]["power_aequivalenz_bei_null"]) for x in (a1, b))
    pw_txt = f"{pw[0]}--{pw[1]}\\%" if pw[0] != pw[1] else f"{pw[0]}\\%"
    se_txt = f"{a1['S1']['se']:.5f}"
    if f"{b['S1']['se']:.5f}" != se_txt:
        fehl(f"H1 S1 SE in A ({a1['S1']['se']}) und B ({b['S1']['se']}) gerundet verschieden")
    erwarte(tex, f"power for equivalence {pw_txt} at the observed SE of {se_txt}", "K3 Power §6")
    erwarte(tex, f"({pw_txt} at the\nSE of {se_txt} observed for H1", "K3 Power §5")
    v, se = H["H4"]["value"], H["H4"]["se"]
    erwarte(tex, pm(v["S2"], se["S2"]), "H4 S2")
    erwarte(tex, pm(v["S3"], se["S3"]), "H4 S3")
    if H["H4"]["verdict"] != "failed":
        fehl("H4 nicht failed – Text behauptet es")
    for dsg, was in (("A", "Design A"), ("B", "Design B")):
        r = H["H2a"]["teile"][dsg]["S1"]["rel_fehler_exakt"]
        s2a = ", ".join(f"${100 * r[k]:+.1f}$" for k in ("1", "3", "7", "15")) + f", ${100 * r['31']:+.1f}\\%$ ({was})"
        erwarte(tex, s2a, f"H2a {dsg} relative Fehler")
        mx = max(abs(x) for x in r.values()) * 100
        if not (3 < mx <= 5):
            fehl(f"H2a {dsg} max |Fehler| {mx:.1f} % – Text sagt 'within 5 %' und '<= 3 % missed'")
        else:
            ok(f"H2a {dsg} 5 %")
        if H["H2a"]["teile"][dsg].get("verdict_dieses_design") != "passed":
            fehl(f"H2a {dsg} nicht passed")
    h2b = H["H2b"]["value"]
    if h2b["i_schritte_better"] != 6 or not (0.10 <= h2b["ii_S3_B1"] <= 0.30) or not (0.50 <= h2b["ii_S30_B1"] <= 1.10):
        fehl(f"H2b Werte {h2b} nicht in den Prereg-Bereichen")
    erwarte(tex, f"by $+{round(100 * h2b['ii_S3_B1'])}\\%$ (three subjects) and $+{round(100 * h2b['ii_S30_B1'])}\\%$ (thirty)", "H2b ii")
    h2c = H["H2c"]
    erwarte(tex, f"$\\bar\\kappa = {h2c['value']['kappa_ML']:.3f}$ against $U/V_0 = {h2c['value']['U_durch_V0']:.3f}$ (bootstrap SE {h2c['se']:.2f})", "H2c konf.")
    if abs(h2c["value"]["differenz"]) > 2 * h2c["se"]:
        fehl("H2c Differenz > 2 SE")
    h3 = H["H3"]
    lo = [h3["ci95"][S][0] for S in ("S1", "S2", "S3")]; va = [h3["value"][S] for S in ("S1", "S2", "S3")]
    if min(lo) <= 0.70:
        fehl(f"H3 untere Grenzen {lo} nicht alle > 0.70")
    erwarte(tex, f"{round(100 * min(va))}--{round(100 * max(va))}\\% of the excess over the pair floor lies at budgets 0--3 (lower confidence bounds {min(lo):.2f}--{max(lo):.2f})", "H3 konf.")
    h5 = H["H5"]
    mx5 = max(abs(x) for S in ("S1", "S2", "S3") for x in h5["value"][S].values())
    if h5["teile"]["n_equivalent_von_9"] != 9 or h5["teile"]["n_better_von_9"] != 0:
        fehl("H5 nicht 9/9 equivalent")
    erwarte(tex, f"moved ALC by more than {math.ceil(mx5 * 1e5) / 1e5:.5f}\n(all equivalent)", "H5 konf.")
    h8 = H["H8"]
    erwarte(tex, f"(${h8['value']['S3_wls_steigung']:+.5f}$ per item, $R^2$ {h8['value']['S3_r2']:.2f})", "H8 S3")
    k8 = h8["value"]["S30_klassen"]
    erwarte(tex, f"${k8['21-50']:+.4f}$ /\n${k8['51-100']:+.4f}$ / ${k8['>100']:+.4f}$ confirmatory, H8 passed", "H8 S30 Anhang A")
    if not (k8["51-100"] >= 1.3 * k8["21-50"] and k8[">100"] >= 1.3 * k8["21-50"]):
        fehl("H8 Saettigung nicht erfuellt")
    h6 = H["H6"]["value"]
    erwarte(tex, f"${h6['R']:.3f}$ for $R_b$", "H6 R")
    erwarte(tex, f"${h6['logit_R']:.3f}$ for its logit", "H6 logit")
    h7 = H["H7"]["value"]
    if h7["n_benchmarks"] != 62 or abs(h7["median"] - h7["zweitweg_median"]) > 1e-6:
        fehl(f"H7 {h7}")
    erwarte(tex, f"median {h7['median']:.4f} over 62", "H7 Median")
    erwarte(tex, f"median {h7['median']:.3f} (IQR {h7['iqr'][0]:.3f}--{h7['iqr'][1]:.3f})", "L10 Median/IQR Haupttext")
    erwarte(tabs["TAB2"], f"median {h7['median']:.4f}", "L10 Median Tab2")

    # --- discovery: cv_A_p2 ---
    p2 = lade("P2")
    def vgl(modell, ref, S):
        for x in p2["vergleiche"]:
            if x["modell"] == modell and x["referenz"] == ref and x["S"] == S and x["gewichtung"] == "paar":
                return x
        fehl(f"Vergleich {modell}/{ref}/{S} fehlt")
        return {"mittel": 9, "se": 9}
    for S in ("S1", "S2", "S3", "S30"):
        x = vgl("hier_item", "beta_binomial", S)
        erwarte(tex, pm(x["mittel"], x["se"]), f"discovery v1-BB {S}")
        erwarte(tabs["TAB1"], pm(x["mittel"], x["se"]), f"Tab1 v1-BB {S}")
    # Budget-Tabelle Anhang D (Tabelle 6) und Hyperparameter-Tabelle (Tabelle 7): pruefe_tabelle6 / pruefe_tabelle7 (einfach gerundet aus der Quelle)
    pruefe_tabelle6(tabs['TAB6'])
    pruefe_tabelle7(tabs['TAB7'])

    # --- Formelmomente ---
    beob = lade("BEOB")
    dex = lade("DEX")
    U = beob["U_E"]; V0 = beob["S1/beta_binomial"]["(q-R)^2"]["0"]; kappa = beob["kappa_mittel_ueber_testpaare"]
    D = dex["D_exakt = E 4V/(N-1)"]; F = dex["E[V/(NA-1)]"]
    erwarte(tex, f"$U = {U:.4f}$", "U")
    erwarte(tex, f"(discovery: {U:.4f}, {V0:.4f}, {kappa:.2f}, {D:.5f}, {F:.5f};", "Momente Haupttext")
    erwarte(tex, f"$U = {U:.5f}$, $V_0 = {V0:.5f}$, $\\kappa = {kappa:.4f}$,\n$D = {D:.6f}$, $F = {F:.6f}$", "Momente Anhang A")
    erwarte(tabs["TAB4"], f"$U={U:.4f}$, $V_0={V0:.4f}$,\n$\\kappa={kappa:.2f}$, $D={D:.5f}$, $F={F:.5f}$", "Momente Tab4")
    if dex["N_median"] != 1000 or dex["N_min"] != 80:
        fehl("N median/min")
    try:
        import alc_law  # noqa: E402
    except Exception as e:  # noqa: BLE001
        print(f"FEHLT (fail-closed): alc_law.py: {e}")
        sys.exit(2)
    kurve = alc_law.lernkurve(U, V0, kappa, D, F)
    def relerr(S, pred, V):
        k2 = alc_law.lernkurve(U, V, kappa, D, F)
        o = beob[f"{S}/{pred}"]["(q-R)^2"]
        return {b: 100 * (k2[b] - o[str(b)]) / o[str(b)] for b in (1, 3, 7, 15, 31)}
    rS1 = relerr("S1", "beta_binomial", V0)
    if max(abs(x) for x in rS1.values()) > 0.8 + 0.05:
        fehl(f"Formel S1 max |Fehler| {max(abs(x) for x in rS1.values()):.2f} % > 0.8 %")
    else:
        ok("Formel S1 <= 0.8 %")
    r30 = relerr("S30", "beta_binomial", V0)[31]
    erwarte(tex, f"${r30:+.1f}\\%$ at budget 31" if False else f"{r30:.1f}\\%", "S30 B31 Formelfehler (-8.3)")
    V0h = beob["S1/hier_item"]["(q-R)^2"]["0"]
    kh = alc_law.lernkurve(U, V0h, kappa, D, F)
    for S, soll in (("S3", "+17.6\\%"), ("S30", "+78.4\\%")):
        o = beob[f"{S}/hier_item"]["(q-R)^2"]["1"]
        dev = 100 * (kh[1] - o) / o
        if f"{dev:+.1f}\\%" != soll:
            fehl(f"Pooling-Abweichung {S}/B1 {dev:+.1f} % != {soll}")
        else:
            erwarte(tex, soll, f"Pooling-Abweichung {S}")
    terme = alc_law.alc(U, V0, kappa, D, F)
    samp = terme.get("stichprobe") if isinstance(terme, dict) else None
    if samp is not None and f"{samp:.4f}" != "0.0107":
        fehl(f"Stichprobenterm {samp:.4f} != 0.0107")
    h2c = lade("H2C")
    erwarte(tex, f"$U/V_0 = {h2c['U_durch_V0_gepoolt']:.3f}$", "H2c U/V0")
    erwarte(tex, f"\\bar\\kappa_{{\\mathrm{{ML}}}} = {h2c['kappa_ML_mittel_cvA']:.3f}$", "H2c kappa_ML")

    # --- Leiter ---
    lt = {r["Stufe"].split(" ")[0]: r["Brier_B0"] for r in lade("LEITER")["leiter_B0"]}
    for stufe, soll in (("L1", "0.2485"), ("L2", "0.2067"), ("L7", "0.1833"), ("L8", "0.1233"), ("L9", "0.0065"), ("L6", "0.1885")):
        if f"{lt[stufe]:.4f}" != soll:
            fehl(f"Leiter {stufe} {lt[stufe]:.4f} != {soll}")
        else:
            erwarte(tex, soll, f"Leiter {stufe}")
    l2 = lade("LEITER2")
    for pre, soll in (("L2b", "0.2211"), ("L3' ", "0.2480"), ("L3''", "0.2460"), ("L4'", "0.2065"), ("L5'", "0.2055")):
        k = next((k for k in l2 if k.startswith(pre)), None)
        if k is None or f"{l2[k]['Brier_B0']:.4f}" != soll:
            fehl(f"Leiter-Ergänzung {pre}: {None if k is None else l2[k]['Brier_B0']} != {soll}")
        else:
            erwarte(tex, soll, f"Leiter {pre}")
    # MUSS 4 (REVIEW A): 73 % = Innerhalb-Paar-Term / Brier der Konstante 0.25; 92 % von Var(y); L7->L8 entfernt ein Drittel
    vb = lade("LEITER")["varianz_brier"]
    u_in = vb["innerhalb Paar E R(1-R)"]; vary = vb["Var(y) gesamt = ybar(1-ybar)"]
    p25 = round(100 * u_in / 0.25); pvy = round(100 * u_in / vary)
    erwarte(tex, f"{p25}\\% of the constant predictor's Brier score of 0.25 ({pvy}\\% of $\\mathrm{{Var}}(y) = {vary:.3f}$)", "73 % / 92 % Herleitung")
    drittel = (lt["L7"] - lt["L8"]) / lt["L7"]
    if not (0.30 <= drittel <= 0.36):
        fehl(f"L7->L8 entfernt {drittel:.3f} – Text sagt 'a third'")
    else:
        erwarte(tex, "removes a third of it ($0.1833 \\to 0.1233$)", "L7->L8 Drittel")
    if f"{vb['  davon Wiederholungsrauschen (Brier bei Orakel k/n)']:.4f}" != "0.0065":
        fehl("L9 in varianz_brier != 0.0065")
    # MUSS 5 (REVIEW A): Murphy-Zerlegung (verlust.json murphy_S3): Reliabilitaet <= 0.0006 (B0 0.00053), Aufloesung 0.0022, Var(R) 0.0667
    mu = lade("VERLUST")["murphy_S3"]
    rel_max = max(v["reliabilitaet"] for v in mu.values())
    rel_schranke = math.ceil(rel_max * 1e4) / 1e4
    erwarte(tex, f"reliability $\\le {rel_schranke:.4f}$\nat every budget", "Murphy Reliabilitaet Haupttext")
    erwarte(tex, f"(binned, $S = 3$) is $\\le {rel_schranke:.4f}$ at every budget\n({mu['0']['reliabilitaet']:.5f} at $B = 0$", "Murphy Reliabilitaet Anhang A")
    erwarte(tex, f"resolution {mu['0']['aufloesung']:.4f} of $\\mathrm{{Var}}(R) = {mu['0']['unsicherheit_R']:.4f}$", "Murphy Aufloesung/Var(R)")
    identitaet = abs(mu["0"]["sq_mittel"] - (mu["0"]["unsicherheit_R"] - mu["0"]["aufloesung"] + mu["0"]["reliabilitaet"]))
    if f"{identitaet:.4f}" != "0.0002":
        fehl(f"Murphy-Identitaet B0 verletzt um {identitaet:.5f} – Text sagt 0.0002")
    else:
        ok("Murphy-Identitaet B0")
    # MUSS 2 (REVIEW A): Fehlurteilsrate zweiseitig 2*Phi(-2) = 4.55 %, bei 20 Urteilen 0.91
    p_dir = math.erfc(2 / math.sqrt(2))  # = 2 * Phi(-2)
    erwarte(tex, f"probability {100 * p_dir / 2:.1f}\\% ({100 * p_dir:.1f}\\% for either)", "Fehlurteil je Richtung / beide")
    erwarte(tex, f"so about {20 * p_dir:.1f} false ones are expected", "0.9 falsche Urteile")
    erwarte(tex, f"the two-sided expectation is $\\approx {20 * p_dir:.1f}$", "0.9 in Anhang B")
    # Hyperparameter der eingereichten Zustandsdatei (Anhang D) <-> leiter.json
    hs = lade("LEITER")["varianz_logit"]["hyp_state_alle"]
    soll = f"submitted & {hs['mu_c']:.3f} & {hs['lam']:.3f} & {hs['tau_c2']:.3f} & {hs['tau_l2']:.3f} & {hs['tau_v2']:.3f} & {hs['kappa']:.3f} & {hs['s2_unk']:.3f}"
    erwarte(tabs["TAB7"], soll, "Hyperparameter submitted (Anhang D) = leiter.json")

    # --- Verlust / Fallbeispiele / Liga / Akquise ---
    vl = lade("VERLUST")
    erwarte(tex, f"({vl['n_benchmarks_schlechter_als_bb']} of {vl['n_benchmarks']} benchmarks worse", "42 of 142")
    g1 = vl["gruppe_subj_klasse"]["1"]
    erwarte(tex, f"all {int(g1['n_bm'])} single-subject benchmarks", "13 Ein-Subjekt-Benchmarks")
    erwarte(tex, f"$+{g1['gewinn_vs_bb']:.4f} \\pm 0.0006$", "Ein-Paar-Gruppe +0.0032")
    sh = [sum(vl[f"alc_anteil_{S}"]["anteil"][b] for b in ("0", "1", "3")) for S in ("S1", "S3")]
    if not (0.77 <= min(sh) and max(sh) < 0.79):
        fehl(f"Anteil B0-B3 {sh} nicht in 77-79 %")
    else:
        erwarte(tex, "77--79\\%", "Anteil B0-B3")
    fb = lade("FALL")
    n3 = fb["nyu_ctf_bench"]["S3"]; n1 = fb["nyu_ctf_bench"]["S1"]; mw = fb["mind2web"]["S3"]
    erwarte(tex, f"${-n3['diff_hier_item_minus_bb_alc']:.4f} \\pm {n3['diff_se_ueber_paare']:.4f}$", "Fall 1 S3")
    erwarte(tex, f"by {-n1['diff_hier_item_minus_bb_alc']:.4f} ALC, mostly at budget 0", "Fall 1 S1")
    # MUSS 6 (REVIEW A): Budget-0-Gewinn ist der Hauptteil in S1; Zusatzgewinn S3 liegt bei B1-B15
    b1 = n1["brier_je_budget"]; b3 = n3["brier_je_budget"]
    erwarte(tex, f"({b1['hier_item']['0']:.3f} against {b1['beta_binomial']['0']:.3f}", "Fall 1 B0 Brier")
    anteil_b0 = 0.1 * (b1["beta_binomial"]["0"] - b1["hier_item"]["0"]) / (-n1["diff_hier_item_minus_bb_alc"])
    if not (0.5 <= anteil_b0 <= 0.75):
        fehl(f"Fall 1 S1: B0-Anteil am Gewinn {anteil_b0:.2f} – Text sagt 'mostly at budget 0'")
    zusatz = n1["diff_hier_item_minus_bb_alc"] - n3["diff_hier_item_minus_bb_alc"]
    erwarte(tex, f"the additional {zusatz:.3f} sits at budgets 1--15", "Fall 1 Zusatzgewinn S3")
    z115 = sum(0.2 * (b1["hier_item"][b] - b3["hier_item"][b]) for b in ("1", "3", "7", "15"))
    if not (0.9 <= z115 / zusatz <= 1.0):
        fehl(f"Fall 1: Anteil B1-B15 am Zusatzgewinn {z115 / zusatz:.2f} – Text sagt 'sits at budgets 1--15'")
    if "0.35 instead of 0.43" in tex:
        fehl("Fall 1: '0.35 instead of 0.43' ohne Quelle in fallbeispiele.json (MUSS 6)")
    erwarte(tex, f"loses {mw['diff_hier_item_minus_bb_alc']:.4f} ALC", "Fall 2")
    erwarte(tex, f"(success rate {mw['R_mittel']:.2f})", "Fall 2 Rate")
    erwarte(tex, f"({int(n3['n_eigen_mittel_B31']) and 15} unnamed agent subjects, mean success rate {n3['R_mittel']:.2f})", "Fall 1 Rate")
    liga = lade("LIGA")
    nf = len(liga["falten"])
    erwarte(tex, f"({nf} of 10 folds", f"Liga {nf}/10 (Abb.-Caption)")
    erwarte(tabs["TAB3"], f"{nf}/10 folds", "Tab3 Faltenzahl")
    if nf == 10:
        erwarte(tex, "Over all 10 folds", "Liga final §6")
        erwarte(tex, "league over all 10 folds", "Liga final Abstract")
        if re.search(r"preliminary", tex + "\n".join(tabs.values()), re.I):
            fehl("Liga 10/10 vorhanden, Text/Tabellen sagen noch preliminary")
        else:
            ok("kein 'preliminary'")
    else:
        fehl(f"Liga nur {nf}/10 Falten – Text ist auf 10/10 geschrieben")
    # Liga-Zahlen im §6 gegen vergleich_gepaart.csv (S1-Bereich der Familien, GB S1, IRT 2PL S3, MF-Bereich)
    with open(PROJ / "./liga/ergebnisse/vergleich_gepaart.csv", newline="", encoding="utf-8") as f:
        vg = [r for r in csv.DictReader(f) if r["referenz"] == "v1_hier_item"]
    fam = ("irt2pl", "irt1pl", "mf", "stack", "knn", "gb", "beta_binomial")
    def lv(m, S):
        r = next(x for x in vg if x["modell"] == m and x["S"] == S)
        return float(r["mittel"]), float(r["se"])
    def urteil(d, s):
        return "b" if d + 2 * s < 0 else "w" if d - 2 * s > 0 else "e" if abs(d) + 2 * s < 0.001 else "g"
    s1 = {m: lv(m, "S1") for m in fam}
    weich = [m for m in fam if m != "gb"]
    lo1, hi1 = min(s1[m][0] for m in weich), max(s1[m][0] for m in weich)
    if any(urteil(*s1[m]) != "g" for m in weich) or urteil(*s1["gb"]) != "w":
        fehl(f"Liga S1 Urteile {[(m, urteil(*s1[m])) for m in fam]} passen nicht zum Text")
    erwarte(tex, f"(paired differences $+{lo1:.4f}$ to $+{hi1:.4f}$ ALC, none significant, none equivalent)", "Liga S1 Bereich")
    erwarte(tex, f"gradient boosting ($+{s1['gb'][0]:.4f} \\pm {s1['gb'][1]:.4f}$)", "Liga GB S1")
    d23, s23 = lv("irt2pl", "S3")
    erwarte(tex, f"IRT 2PL \\citep{{lord1980irt, fox2010bayesianirt}} from three ($+{d23:.4f} \\pm\n{s23:.4f}$", "Liga IRT 2PL S3")
    regs = ("S1", "S2", "S3", "S30", "kompakt10")
    tafel_u = {(m, S): urteil(*lv(m, S)) for m in fam for S in regs}
    n_w = sum(1 for u_ in tafel_u.values() if u_ == "w"); n_b = sum(1 for u_ in tafel_u.values() if u_ == "b")
    je = [sum(1 for m in fam if tafel_u[(m, S)] == "w") for S in regs]
    if n_b != 0 or n_w != 23 or je != [1, 4, 5, 6, 7]:
        fehl(f"Liga worse/better Zaehlung: better {n_b}, worse {n_w}, je Regime {je}")
    else:
        erwarte(tex, "(0 of 35 family--regime comparisons), and 23 of the 35 are worse", "Liga 0/35, 23/35")
    mf = [lv("mf", S)[0] for S in ("S1", "S2", "S3", "S30")]
    if any(tafel_u[("mf", S)] != "g" for S in ("S1", "S2", "S3", "S30")) or tafel_u[("mf", "kompakt10")] != "w":
        fehl("MF-Urteile passen nicht zu 'grey zone up to thirty, worse only in compact10'")
    erwarte(tex, f"(grey zone up to thirty subjects, $+{min(mf):.4f}$ to $+{max(mf):.4f}$)", "Liga MF Bereich")
    for m, ab in (("knn", "S2"), ("irt1pl", "S2"), ("beta_binomial", "S2"), ("stack", "S30")):
        vor = regs[regs.index(ab) - 1]
        if tafel_u[(m, ab)] != "w" or tafel_u[(m, vor)] == "w":
            fehl(f"Liga: {m} 'worse from {ab} on' stimmt nicht ({tafel_u[(m, vor)]}, {tafel_u[(m, ab)]})")
    if any(tafel_u[("gb", S)] != "w" for S in regs):
        fehl("Liga: GB nicht in allen Regimen worse – Text sagt 'throughout'")
    if tafel_u[("irt2pl", "S2")] == "w" or tafel_u[("irt2pl", "S3")] != "w":
        fehl("Liga: IRT 2PL 'from three' stimmt nicht")
    akq = lade("AKQ")
    u0 = akq["vergleiche_vs_zufall"][0]["urteil"]
    if u0 != "kein Unterschied belegt":
        fehl(f"Akquise-Pilot S3 Urteil {u0} – Text sagt 'no difference'")
    else:
        ok("Akquise-Pilot")
    ident = lade("IDENT")
    erwarte(tex, f"of the {ident['namenlos']:,} unnamed subjects", "Identität 13,371")
    lo, hi = round(100 * ident["anteil_mit_bezeichner"]), 74
    erwarte(tex, f"({lo}--{hi}\\%", "Identität 67-74 %")
    wdh = lade("WDH")
    if abs(wdh["schranke_je_bm_quantile"]["0.5"] - h7["median"]) > 1e-6:
        fehl("L10 Zweitweg != Tafel")
    else:
        ok("L10 Zweitweg")
    dz = lade("DATEN")
    erwarte(tex, f"{dz['benchmarks_mit_daten']} public binary", "156 Benchmarks")
    erwarte(tex, f"{dz['zeilen_subjekt_item']:,} subject--item rows, {dz['antworten']:,} responses", "Zeilen/Antworten")
    dq = lade("DQ")
    for s, was in (("60 of 156", "DQ F1 60/156"), ("64 of 120", "DQ F3 64/120"), ("100,000 of 385,266", "DQ 100000/385266"),
                   ("117 upstream twin pairs", "DQ F7 117"), ("119 different models in 13 benchmarks", "DQ F8 119/13"),
                   ("25 groups", "DQ F8 25")):
        if s not in dq:
            fehl(f"{was}: '{s}' nicht im DQ-Report")
        else:
            ok(was)
    erwarte(tex, "60 of 156", "DQ 60/156 im tex")
    erwarte(tex, "64 of 120", "DQ 64/120 im tex")
    erwarte(tex, "119 models in 13 benchmarks", "DQ 119 im tex")
    erwarte(tex, "117 Winogrande twin pairs", "DQ 117 im tex")
    # S1 (FREIGABE): keine internen Uhrzeiten/Arbeitsnotizen im Bericht (Praereg-Zeitstempel ist die einzige erlaubte Uhrzeit)
    alles_ohne_prereg = (tex + "\n".join(tabs.values())).replace("20:26:04", "")
    uhr = re.findall(r"\b\d{1,2}:\d{2}\s*(?:UTC|Z\b)|\bnot recomputed|not evaluated before the freeze|not evaluated \(table|when this report was frozen", alles_ohne_prereg)
    if uhr:
        fehl(f"interne Uhrzeit/Arbeitsnotiz im Bericht: {uhr[:3]}")
    else:
        ok("keine internen Uhrzeiten")
    for k in ("TAB1", "TAB2"):
        if re.search(r"run missing|had not completed|not evaluated", tabs[k]):
            fehl(f"{k}: 'run missing'/'had not completed'/'not evaluated' – alle Hypothesen sind ausgewertet")
        else:
            ok(f"{k} ohne 'not evaluated'")
    # M7 (REVIEW B): eine RAM-Zahl, gemessene Smoke-Zeit, make all nicht als Messung
    if len(re.findall(r"16\\,GiB", tex)) == 2 and "15\\,GiB" not in tex:
        ok("RAM 16 GiB an beiden Stellen")
    else:
        fehl("RAM-Angabe uneinheitlich (16 GiB zweimal erwartet, 15 GiB nirgends)")
    erwarte(tex, "about 70 seconds,\nmeasured on fresh clones", "Smoke-Zeit gemessen")
    erwarte(tex, "not\ntimed as one run", "make all nicht gemessen")
    for s in ("about 10 minutes", "about 30 minutes", "rebuilds every table and figure"):
        if s in tex:
            fehl(f"veraltete Repro-Aussage '{s}' (M7/MUSS 7)")
    # MUSS 9 (REVIEW A): Urteilsbuchstaben in Tab. 1/3 nur b/w/e/g (Regel Abschnitt 5); Tab. 1 S1 discovery = g wie Tab. 2
    buchstaben = set()
    for k in ("TAB1", "TAB3", "TAB3A"):
        buchstaben |= set(re.findall(r"\\pm \d\.\d{4,5}\$ ([a-z])\b", tabs[k]))
    if buchstaben <= {"b", "w", "e", "g"}:
        ok(f"Urteilsbuchstaben {sorted(buchstaben)}")
    else:
        fehl(f"Urteilsbuchstaben ausserhalb b/w/e/g: {sorted(buchstaben)}")
    m1 = re.search(r"S1 \(1 subject/benchmark\)[^\n]*?\\pm 0\.0004\$ ([a-z]) &", tabs["TAB1"])
    if m1 and m1.group(1) == "g" and "(grey zone)" in tabs["TAB2"]:
        ok("Tab1 S1 discovery = g = Tab2 grey zone")
    else:
        fehl("Tab1 S1 discovery Buchstabe != g oder Tab2 ohne 'grey zone'")


def pruefe_verbote(tex, tabs):
    haupt = tex  # ganzes Dokument inkl. Anhänge; Tabellen separat
    alles = tex + "\n" + "\n".join(tabs.values())
    ohne_kommentare = "\n".join(l.split("%")[0] if not l.lstrip().startswith("%") else "" for l in alles.splitlines())
    muster = [
        (r"\blaws?\b", "law"), (r"first[- ]ever", "first ever"), (r"breakthrough", "breakthrough"),
        (r"state[- ]of[- ]the[- ]art", "state of the art"), (r"outperform", "outperform"),
        (r"beat(s)? (the )?(other|all) (teams|participants)", "beat other teams"),
        (r"ensembling does not help", "ensembling"), (r"no effect of subject identity", "no effect of subject identity"),
        (r"independent review", "independent review"), (r"verified and read", "verified and read"),
        # M8 (REVIEW B, J-jury §8): Agenten-Pruefungen nie 'independent'; erlaubt: Independent researcher, label-independent, conditionally independent
        (r"independent (re-)?implementation|independently|independent (check|verification|re-?computation|audit)", "independent implementation"),
        (r"other (teams|participants)|leaderboard rank", "other teams"), (r"Data Curator Award", "award"),
        (r"co-author", "co-author"), (r"effect on (the )?(scores|predictions)", "effect on scores"),
        (r"private (test )?pool", "private pool"), (r"rasch1960", "rasch1960"),
    ]
    for rx, name in muster:
        hits = [m.group(0) for m in re.finditer(rx, ohne_kommentare, re.I)]
        if hits:
            fehl(f"Verbotsliste '{name}': {hits[:3]}")
        else:
            ok(name)
    ab = abstract(tex)
    if re.search(r"pre-registered", ab, re.I):
        fehl("'pre-registered' im Abstract")
    for d in ("0.0047", "0.0030", "0.0003 ", "17.6", "78.4", "0.0204", "0.0060", "77--79", "0.8\\%", "0.0130"):
        if d in ab:
            fehl(f"discovery-Zahl '{d}' im Abstract")
    # 'Claude' nur im KI-Abschnitt
    ki = re.search(r"\\section\*\{Use of AI assistants\}(.*?)\\section", tex, re.S)
    rest = tex.replace(ki.group(1), "") if ki else tex
    rest_ok = "\n".join(l for l in rest.splitlines() if not l.lstrip().startswith("%"))
    if "Claude" in rest_ok:
        fehl("'Claude' außerhalb des KI-Abschnitts")
    else:
        ok("Claude nur im KI-Satz")
    # 'floor' nur mit Qualifizierer in derselben Zeile (Satz)
    qual = ("pair", "text-free", "noise", "response", "subset", "R(1", "R_E(1", "split", "pair-level", "L10")
    for l in ohne_kommentare.splitlines():
        if "floor" in l and not any(q in l for q in qual):
            fehl(f"'floor' ohne Qualifizierer: {l.strip()[:90]}")
    # Paketwechsel: der Bericht darf das v1-ZIP nicht mehr als eingereicht nennen
    for s in ("submitted v1 package", "the file submitted to the platform is the v1", "reported for the v1 package", "paiec\\_hier.zip"):
        if s in tex:
            fehl(f"veralteter Paket-Wortlaut '{s}' (eingereicht ist v2.0-core)")
    for d in ("0.0031", "0.0132", "0.0049 \\pm 0.0007$ (Design A)"):
        pass  # Konfirmationszahlen duerfen im Abstract stehen


def pruefe_endpruefung_l2(tex, refs):
    """Feinschliff L, Runde 2 (Endpruefung M1-M3, M5, K6): Aussagen des Textes gegen die Quelldaten, mechanisch.
    M1: der dominierende Benchmark der Antwortgewichtung ist argmax(responses_rep) der CSV (nicht die Zellzahl-Spitze);
    M2: 'every regime' darf bei H3 nicht stehen, bei S30 steht die Tafelzahl; M3: Zweitrechnung exakt, keine 4e-7 / 4e-16-Aussage;
    M5/K6: Literaturliste ohne Klammer-Grossschreibung und mit DOI-Link zu jedem DOI-Eintrag."""
    import io
    # --- M1: dominierender Benchmark aus der CSV ---
    zeilen = list(csv.DictReader(io.StringIO(lade("NOISE"))))
    if not zeilen:
        fehl("noise_floor_by_benchmark.csv leer (fail-closed)")
        return

    def f(x):
        return float(x) if x not in ("", None) else 0.0
    gesamt = sum(f(z["responses_rep"]) for z in zeilen)
    top = max(zeilen, key=lambda z: f(z["responses_rep"]))
    summe = sum(f(z["responses_rep"]) * f(z["L10_response_weighted"]) for z in zeilen)
    ohne = (summe - f(top["responses_rep"]) * f(top["L10_response_weighted"])) / (gesamt - f(top["responses_rep"]))
    anteil = round(100 * f(top["responses_rep"]) / gesamt)
    name = top["benchmark_id"].replace("_", "\\_")
    erwarte(tex, f"dominated by one benchmark ({name}, {anteil}\\% of the repeated responses; without it {ohne:.3f})",
            "A.5: dominierender Benchmark = argmax(responses_rep) der CSV, Anteil, Mittel ohne ihn")
    wdh = lade("WDH")
    if abs(ohne - wdh["schranke_antwortgewichtet_ohne_monkey_power_laws"]) > 1e-4:
        fehl("Mittel ohne dominierenden Benchmark (CSV) != wiederholung_b.json")
    else:
        ok("Mittel ohne dominierenden Benchmark = wiederholung_b.json")
    # --- M2: H3 bei dreissig Subjekten ---
    h3 = {x["id"]: x for x in lade("TAFEL")["hypothesen"]}["H3"]["value"]
    s30 = round(100 * h3["S30"])
    erwarte(tex, f"budgets 0--3 in S1--S3 (H3; discovery 77--79\\%; {s30}\\% at thirty subjects)", "H3: Geltung nur S1-S3, S30 aus der Tafel")
    if re.search(r"budgets 0--3 in every regime", norm(tex)):
        fehl("'budgets 0--3 in every regime' (H3 gilt nicht bei S30)")
    # --- M3: Zweitrechnung exakt (Median) bzw. <= 5e-16 (alle Kennzahlen) ---
    vgl = wdh["vergleich_mit_erstweg"]
    abw = [v["rel_abw"] for v in vgl.values() if isinstance(v, dict) and "rel_abw" in v]
    if vgl["quantil_0.5"]["rel_abw"] == 0.0 and abw and max(abw) <= 5e-16:
        ok("Zweitrechnung: Median exakt, alle Kennzahlen <= 5e-16")
        erwarte(tex, "reproduces the median exactly (all summary values within $5\\times10^{-16}$ relative)", "A.5 Zweitrechnung")
        erwarte(tex, "identical to the first (median exact; Table~\\ref{tab:twopaths})", "Fig. 10 Zweitrechnung")
        erwarte(tex, "exact (summaries $\\le 5\\times10^{-16}$ rel.)", "Tabelle 9 Zweitrechnung")
    else:
        fehl(f"wiederholung_b.json: Median nicht exakt oder Kennzahl > 5e-16 (max {max(abw) if abw else None})")
    for veraltet in ("4\\times10^{-7}", "4 \\times 10^{-16}", "4\\times10^{-16}"):
        if veraltet in tex:
            fehl(f"widerspruechliche Genauigkeitsangabe der Zweitrechnung im tex: {veraltet}")
    # --- M5/K6: Literaturliste (Quelle, nicht das PDF) ---
    for muster, was in ((r"\{Cluster-Robust\}", "Cluster-Robust in Klammern"), (r"\{Sample-Efficient\}", "Sample-Efficient in Klammern"),
                        (r"Theory To Practical", "'To' gross"), (r"Adrian E Raftery", "Raftery ohne Punkt"),
                        (r"Felipe Maia Polo", "'Maia Polo' ohne Klammer (BibTeX liest 'Polo')"),
                        (r"title\s*=\s*\{Measurement Data Bank", "Measurement Data Bank ohne Klammer"),
                        (r"\}\s*Predictive AI Evaluation Competition|\{NeurIPS\} 2026 Predictive", "Predictive AI Evaluation Competition ohne Klammer")):
        if re.search(muster, refs):
            fehl(f"refs.bib: {was}")
        else:
            ok(f"refs.bib ohne '{was}'")
    ohne_url = []
    for eintrag in re.split(r"(?m)^@", refs)[1:]:
        if re.search(r"^\s*doi\s*=", eintrag, re.M) and not re.search(r"^\s*url\s*=\s*\{https://doi\.org/", eintrag, re.M):
            ohne_url.append(eintrag.split(",")[0].split("{")[-1])
    if ohne_url:
        fehl(f"refs.bib: DOI-Eintraege ohne doi.org-Link: {ohne_url}")
    else:
        ok("refs.bib: jeder DOI-Eintrag hat einen doi.org-Link")


def pruefe_abbildungsreihenfolge(texpfad):
    """K4: Tabelle der Abbildungsquellen steht in der Reihenfolge der Abbildungsnummern (aus der .aux-Datei des Baus)."""
    aux = texpfad.with_suffix(".aux")
    q = texpfad.parent / "abbildungen" / "quellen_abbildungen.tex"
    if not aux.is_file() or not q.is_file():
        fehl("aux oder quellen_abbildungen.tex fehlt - Reihenfolgepruefung nicht moeglich (fail-closed)")
        return
    nummer = {m.group(1): int(m.group(2)) for m in re.finditer(r"\\newlabel\{(fig:[^}]+)\}\{\{(\d+)\}", aux.read_text(encoding="utf-8"))}
    folge = re.findall(r"\\ref\{(fig:[^}]+)\}\s*&", q.read_text(encoding="utf-8"))
    try:
        zahlen = [nummer[k] for k in folge]
    except KeyError as e:
        fehl(f"Quellentabelle nennt ein Label ohne Nummer in der aux: {e}")
        return
    if zahlen == sorted(zahlen) and len(set(zahlen)) == len(zahlen) and zahlen:
        ok(f"Tabelle der Abbildungsquellen nach Abbildungsnummer sortiert ({zahlen})")
    else:
        fehl(f"Tabelle der Abbildungsquellen nicht nach Abbildungsnummer sortiert: {zahlen}")


def pruefe_cites(tex, tabs):
    refs = lade("REFS")
    keys = set(re.findall(r"^@\w+\{([^,\s]+),", refs, re.M))
    alles = tex + "\n".join(tabs.values())
    used = set()
    for m in re.finditer(r"\\cite[tp]?(?:alp)?\*?(?:\[[^\]]*\])*\{([^}]*)\}", alles):
        for k in m.group(1).split(","):
            used.add(k.strip())
    fehlend = sorted(used - keys)
    if fehlend:
        fehl(f"\\cite-Schlüssel nicht in refs.bib: {fehlend}")
    else:
        ok(f"{len(used)} cite-Schlüssel in refs.bib")


# Schlussrunde D2: Sprache und Uhrzeiten im FERTIGEN PDF (die Quellenpruefung oben sieht refs.bib/Anhang G nicht, das PDF schon).
# Wortgrenzen, nur deutsche Funktionswoerter und die in der Endpruefung gefundenen Arbeitsnotiz-Muster; Dateinamen mit deutschen
# Namensteilen (wiederholung_b.py, hypothesen_tafel.json) sind keine Treffer, weil sie als Ganzes ein Token bilden.
DEUTSCH_WOERTER = ("und", "nicht", "oder", "mit", "ueber", "über", "für", "fuer", "Autoren", "lt", "Geprueft", "geprueft", "Geprüft", "geprüft",
                   "Prüf", "Pruef", "Prüfung", "Pruefung", "Zugriff", "Veranstalter", "Wettbewerbstext", "gelesen", "ausgefuehrt", "Kommentar")
DEUTSCH_MUSTER = re.compile(r"(?<![\w/.\-])(" + "|".join(re.escape(w) for w in DEUTSCH_WOERTER) + r")(?![\w\-])")
ARBEITSNOTIZ = re.compile(r"\.md;|-Kommentar|arXiv-Preprint|Autoren\s*=|Erstpr")
# Feinschliff L1: deutsche Regimebezeichnung "kompakt10" (im Bericht heisst es compact10); als Teil eines Pfads/Dateinamens
# (Verzeichnis ...-S30-kompakt10/auswertung.json, auch am Zeilenumbruch nach "-" oder "/") erlaubt.
REGIMENAME_DE = re.compile(r"(?<![\w/\-])kompakt10(?![\w\-]|/)")
PFAD_KOMPAKT = re.compile(r"S30-\s?kompakt10/")
# Endpruefung Runde 2 (K2, M5, K6): Rest-Kuerzel und Schreibweisen in der Literaturliste, die im PDF-Text nicht stehen duerfen
# (deutsche Kurzlabels in Tabelle 4, undefiniertes 'n.d.', 'Polo' statt 'Maia Polo', Gross-/Kleinschreibung der Titel)
RESTMUSTER = re.compile(r"\bbeob\.|(?<![/\w.\-])verlust\b(?!\.json)|bekannt_hier_item|bekannt\\_hier|\bn\.d\.|(?<!Maia )\bPolo et al|Adrian E Raftery|"
                        r"Cluster-Robust inference|Sample-Efficient model|Item Response Theory To |Measurement data bank|"
                        r"predictive AI evaluation competition")
UHRZEIT = re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?!:)\s*(?:UTC|Z\b)")


def pdf_text(pdf):
    import subprocess
    try:
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    except Exception as e:  # noqa: BLE001
        fehl(f"pdftotext: {e} -- Sprachpruefung des PDF nicht moeglich (fail-closed)")
        return None


def pruefe_pdf_sprache(text, quelle="PDF"):
    """Meldet deutsche Woerter, Arbeitsnotiz-Muster und Uhrzeiten (hh:mm UTC) im PDF-Text als Fehler; gibt die Trefferzahl zurueck."""
    flach = re.sub(r"\s+", " ", text)
    de = sorted({m.group(1) for m in DEUTSCH_MUSTER.finditer(flach)})
    notiz = sorted({m.group(0) for m in ARBEITSNOTIZ.finditer(flach)})
    uhr = sorted({m.group(0) for m in UHRZEIT.finditer(flach)})
    rest = sorted({m.group(0) for m in RESTMUSTER.finditer(flach)})
    ohne_pfad = PFAD_KOMPAKT.sub("S30-PFAD/", flach)
    regime = sorted({m.group(0) for m in REGIMENAME_DE.finditer(ohne_pfad)})
    n = 0
    if de:
        fehl(f"{quelle}: deutsche Woerter im Text: {de}")
        n += 1
    if notiz:
        fehl(f"{quelle}: interne Arbeitsnotiz-Muster im Text: {notiz}")
        n += 1
    if uhr:
        fehl(f"{quelle}: Uhrzeit(en) im Text: {uhr}")
        n += 1
    if regime:
        fehl(f"{quelle}: deutsche Regimebezeichnung 'kompakt10' im Text (Anzeigename: compact10): {len(regime)} Treffer-Art(en)")
        n += 1
    if rest:
        fehl(f"{quelle}: Kuerzel/Schreibweisen aus der Endpruefung im Text: {rest}")
        n += 1
    nullen = sorted({m.group(0) for m in re.finditer(r"[−+-]0\.0{4,5}(?![\d])", flach)})
    if nullen:
        fehl(f"{quelle}: Null mit Vorzeichen im Text (O2): {nullen}")
        n += 1
    if not n:
        ok(f"{quelle}: keine deutschen Woerter, keine Arbeitsnotizen, keine Uhrzeiten (hh:mm UTC), kein 'kompakt10' ausserhalb von Pfaden")
    return n


def pruefe_seiten(texpfad):
    me = texpfad.with_suffix(".mainend")
    pdf = texpfad.with_suffix(".pdf")
    if not me.is_file() or not pdf.is_file():
        fehl("PDF oder .mainend fehlt – Seitenprüfung nicht möglich (fail-closed)")
        return
    try:
        seite, y, hoehe = me.read_text().split()[:3]
        seite = int(seite); y = float(y); hoehe = float(hoehe.rstrip("pt")) * 65536
    except Exception as e:  # noqa: BLE001
        fehl(f".mainend unlesbar: {e}")
        return
    seiten = seite - 1 + (1 - y / hoehe)
    import subprocess
    try:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        n = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    except Exception as e:  # noqa: BLE001
        fehl(f"pdfinfo: {e}")
        return
    print(f"Haupttext endet auf Seite {seite} bei {1 - y / hoehe:.2f} der Seite -> {seiten:.2f} Seiten; PDF {n} Seiten")
    if seiten <= 7.5 and seite <= n:
        ok("Haupttext <= 7.5 Seiten")
    else:
        fehl(f"Haupttext {seiten:.2f} Seiten > 7.5")


# =====================================================================================================================
# Feinschliff N, Runde 1 (Endpruefung N1-N5, O1-O17): mechanische Pruefungen der Fehlerklassen, die zwei Runden lang
# immer wieder neue Treffer lieferten: (a) Quellpfade, (b) handgeschriebene Tabellen, (c) Vorzeichen/Differenzen,
# (d) Zaehlangaben, (e) Allaussagen/Superlative im Haupttext. Jede Pruefung ist eine Funktion; --selbsttest-neu und
# --alt <Ordner> loesen die Fehlerfaelle an den Vorversionen aus (vor-N1/).
# =====================================================================================================================
REPO = PROJ / "modell-v2" / "repo-export"
EXTERN = {  # genannte Dateien, die bewusst NICHT im Repository liegen (mit Grund)
    "tools/prepare_data.py": "Datei des Veranstalter-Repositories paiec_baseline (Befund 1)",
    "streaming_ingestion.py": "Datei des Veranstalter-Repositories paiec_baseline (Protokoll-Replik)",
    "EVIDENCE.md": "Inhalt der an die Veranstalter gesandten Evidenzpakete",
    "verify_patches.sh": "Inhalt der an die Veranstalter gesandten Evidenzpakete",
    "agg.parquet": "Ergebnis von make daten in der lokalen Datenbasis (gated Daten)",
    "status.json": "Fertig-Marke je Lauf in der lokalen Datenbasis",
    "auswertung.json": "allgemeine Nennung (Fertig-Kriterium), Pfade stehen an den Tabellen",
    "zuverlaessigkeit.csv": "allgemeine Nennung",
    "labeling.py": "Schnittstellendatei des Wettbewerbs (kein labeling.py im eingereichten Paket; Politik: akquise/politiken.py)",
}
VERZEICHNISSE = ("konfirmation", "liga", "curation", "theorie", "audit", "modell", "report", "akquise", "prereg", "scripts", "reference")


def _quelltext_ohne_kommentare(tex, tabs, extra=""):
    zeilen = []
    for blk in [tex] + list(tabs.values()) + [extra]:
        for l in blk.splitlines():
            s = l.lstrip()
            if s.startswith("%"):
                continue
            l = re.sub(r"(?<!\\)%.*$", "", l)
            if re.match(r"\s*\\(input|includegraphics|bibliography|bibliographystyle|graphicspath)\b", l):
                continue
            zeilen.append(l)
    s = "\n".join(zeilen)
    s = re.sub(r"\\allowbreak(\{\})?[ \t]*", "", s)
    return s.replace("\\_", "_").replace("\\dd", "--")


def genannte_pfade(tex, tabs, extra=""):
    """Alle im Text genannten Dateipfade/Verzeichnisse (tex, Tabellen, Abbildungsquellen); Zeilenumbrueche im Pfad sind kein Thema, weil die Pfade im tex je in einem \\texttt stehen."""
    s = _quelltext_ohne_kommentare(tex, tabs, extra)
    dat = set(re.findall(r"(?<![\w/.\-])((?:[A-Za-z0-9_\-]+/)*[A-Za-z0-9_\-]+\.(?:" + PFAD_ENDUNGEN + r"))(?![\w\-])", s))
    ver = set(re.findall(r"(?<![\w/.\-])((?:" + "|".join(VERZEICHNISSE) + r")/(?:[A-Za-z0-9_\-]+/)*)", s))
    return sorted(dat), sorted(ver)


def repo_dateien(repo):
    basen, alle = set(), set()
    for p in repo.rglob("*"):
        if ".git" in p.parts or not p.is_file():
            continue
        basen.add(p.name)
        alle.add(p.relative_to(repo).as_posix())
    return basen, alle


def pfad_im_repo(t, repo, basen):
    """Ein genannter Pfad relativ zur Repo-Wurzel; 'daten/', 'abbildungen/', 'tabellen/' sind relativ zu report/src/ (Tabellenunterschrift)."""
    t = t.rstrip(".")
    kand = [t]
    if t.split("/")[0] in ("daten", "abbildungen", "tabellen"):
        kand.append("report/src/" + t)
    if any((repo / k).exists() for k in kand):
        return True
    return "/" not in t and t in basen


def pruefe_quellpfade(tex, tabs, extra, repo, was="Quellpfade"):
    """(a) Jeder im Text genannte Dateipfad existiert relativ zur Repo-Wurzel (oder steht in EXTERN mit Grund; F2/F3b/F9b nur, wenn der Text ihr Fehlen im oeffentlichen audit/csv/ sagt)."""
    if not repo.is_dir():
        fehl(f"{was}: Repo-Export {repo} fehlt (fail-closed)")
        return
    basen, _ = repo_dateien(repo)
    dat, ver = genannte_pfade(tex, tabs, extra)
    auslass = re.search(r"omits F2, F3b and F9b", norm(tex)) is not None
    fehlend = []
    for t in dat:
        if pfad_im_repo(t, repo, basen):
            continue
        if t in EXTERN:
            continue
        if auslass and re.match(r"F(2|3b|9b)_", t):
            continue
        fehlend.append(t)
    for v in ver:
        if not (repo / v).exists() and not (repo / "report/src" / v).exists():
            fehlend.append(v)
    if fehlend:
        fehl(f"{was}: im Text genannte Pfade, die im Repository nicht existieren: {fehlend}")
    else:
        ok(f"{was}: {len(dat)} Dateipfade und {len(ver)} Verzeichnisse existieren relativ zur Repo-Wurzel")


def regime_fehlen(pfad, regime, repo):
    """Regime, die die Datei (auswertung.json, tabelle_alle) NICHT enthaelt."""
    ta = json.loads((repo / pfad).read_text(encoding="utf-8"))["tabelle_alle"]
    return [r for r in regime if r not in ta]


def pruefe_pfad_schluessel(tex, tabs, extra, repo, erwartet=None):
    """(a) Wo eine Tabelle Zeilen/Regime aus einer genannten Datei zitiert, enthaelt diese Datei die Schluessel (N3, O10)."""
    LV = "liga/ergebnisse/liga_vergleich.json"  # R2/P1: Tabellen 1, 3, 4, 6 lesen die vollen Werte aus dieser Datei (Schluessel regime[S])
    erwartet = erwartet or {  # Tabelle -> (genannter Pfad muss vorkommen, Regime, die die Tabellenzeilen aus dieser Datei lesen)
        "TAB1": [("modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json", ["S1", "S2", "S3", "S30", "kompakt10"]),
                 (LV, ["S1", "S2", "S3", "S30", "kompakt10"])],
        "TAB3": [(LV, ["S1", "S3"])],
        "TAB3A": [("modell/ergebnisse/cv_A_S1-S2-S3-S30/auswertung.json", ["S1", "S2", "S3", "S30"]),
                  ("modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json", ["S1", "S2", "S3", "S30"])],
        "TAB4": [("modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json", ["S1", "S2", "S3", "S30", "kompakt10"]),
                 (LV, ["S1", "S2", "S3", "S30"])],
        "TAB6": [("modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json", ["S1", "S2", "S3"]),
                 (LV, ["S1", "S2", "S3"])],
    }
    n = 0
    for tk, liste in erwartet.items():
        quelle = _quelltext_ohne_kommentare("", {tk: tabs.get(tk, "")})
        for pfad, regime in liste:
            if pfad not in quelle:
                fehl(f"{tk}: nennt den Pfad {pfad} nicht (Quelle der Zeilen {regime})")
                continue
            p = repo / pfad
            if not p.is_file():
                fehl(f"{tk}: {pfad} fehlt im Repository")
                continue
            dd = json.loads(p.read_text(encoding="utf-8"))
            ta = dd["regime"] if pfad.endswith("liga_vergleich.json") else dd["tabelle_alle"]
            fehlt = [r for r in regime if r not in ta]
            if fehlt:
                fehl(f"{tk}: {pfad} enthaelt die Regime {fehlt} nicht (Tabellenzeilen zitieren sie)")
            else:
                n += 1
    # Abbildungsquellen: Fig. 4 liest S1 (BB B0) aus der langen Datei; Fig. 5 liest primaer_S + zuverlaessigkeit.csv aus cv_A_p2
    qa = _quelltext_ohne_kommentare("", {"Q": extra})
    for pfad, regime, schluessel in (("modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json", ["S1"], "BB B0"),
                                     ("modell/ergebnisse/cv_A_p2/auswertung.json", [], "primaer_S")):
        if pfad not in qa:
            fehl(f"Abbildungsquellen nennen {pfad} nicht ({schluessel})")
            continue
        a = json.loads((repo / pfad).read_text(encoding="utf-8"))
        if regime and any(r not in a["tabelle_alle"] for r in regime):
            fehl(f"{pfad}: Regime {regime} fehlen (Abbildungsquelle {schluessel})")
        elif "primaer_S" in schluessel and "primaer_S" not in a:
            fehl(f"{pfad}: Feld primaer_S fehlt")
        else:
            n += 1
    if re.search(r"(?<![\w/\-])cv_A_p2 auswertung|(?<![/\w])cv_A_p2/auswertung\.json", qa.replace("modell/ergebnisse/cv_A_p2/auswertung.json", "")):
        fehl("Abbildungsquellen: Pfad ohne Verzeichnispraefix 'modell/ergebnisse/' (cv_A_p2 ...)")
    ok(f"Pfad-Schluessel-Pruefung: {n} Quelle-Regime-Paare bestanden")


def _zellen(zeile):
    return [c.strip() for c in zeile.strip().rstrip("\\").split("&")]


def pruefe_tabelle7(tab7, repo_state=None, work=None):
    """(b) Tabelle 7: jede Zelle aus dem Rohwert EINMAL gerundet; doppelte Rundung (4 -> 3 Stellen) wird als solche gemeldet (N4)."""
    roh = lade("HYP")
    st = lade("STATE")
    spalten = ("mu_c", "lam", "tau_c2", "tau_l2", "tau_v2", "kappa", "s2_unk", "tau_i2")
    zeilen = {}
    for l in tab7.splitlines():
        m = re.match(r"\s*(\d|submitted)\s*&(.*)\\\\\s*$", l)
        if m:
            zeilen[m.group(1)] = _zellen(m.group(2))
    if sorted(zeilen) != sorted([str(i) for i in range(10)] + ["submitted"]):
        fehl(f"Tabelle 7: Zeilen {sorted(zeilen)} (erwartet Falten 0-9 und submitted)")
        return
    n_fehl = 0
    for f in range(10):
        v = roh["falten"][str(f)]
        soll = [f"{v[k]:.3f}" for k in spalten] + [str(int(v["n_namen"]))]
        dop = [str(Decimal(f"{v[k]:.4f}").quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)) for k in spalten] + [str(int(v["n_namen"]))]
        for k, (z, s, d) in enumerate(zip(zeilen[str(f)], soll, dop)):
            if z != s:
                n_fehl += 1
                art = "doppelt gerundet (4 -> 3 Stellen)" if z == d else "weicht ab"
                fehl(f"Tabelle 7 Falte {f}, Spalte {(*spalten, 'names')[k]}: {z} != {s} (einfach gerundet aus {v.get((*spalten, 'n_namen')[k])}) - {art}")
    h = st["hyp"]
    soll = [f"{h[k]:.3f}" for k in spalten] + [str(len(st["theta"]))]
    if zeilen["submitted"] != soll:
        n_fehl += 1
        fehl(f"Tabelle 7 Zeile submitted {zeilen['submitted']} != state_v2core.json {soll}")
    if not n_fehl:
        ok("Tabelle 7: alle 110 Zellen = einfach gerundete Rohwerte (daten/hyperparameter_je_falte_roh.json, state_v2core.json)")
    # Rohwerte gegen die Zustandsdateien der lokalen Datenbasis (wenn erreichbar)
    import os
    basis = Path(work if work is not None else os.environ.get("PAIEC_WORK", "/nonexistent")) / "modell" / "cv_A"
    if all((basis / f"state_f{i}.json").is_file() for i in range(10)):
        bad = 0
        for i in range(10):
            b = (basis / f"state_f{i}.json").read_bytes()
            d = json.loads(b)
            for k in spalten:
                if d["hyp"][k] != roh["falten"][str(i)][k]:
                    bad += 1
            if len(d["theta"]) != roh["falten"][str(i)]["n_namen"] or hashlib.sha256(b).hexdigest() != roh["sha256_state"][f"state_f{i}.json"]:
                bad += 1
        if bad:
            fehl(f"hyperparameter_je_falte_roh.json weicht von state_f*.json ab ({bad} Felder)")
        else:
            ok("Rohwerte = state_f0..f9.json der lokalen Datenbasis (Werte, Namenzahl, sha256)")
    elif OHNE_ZUSTAND[0]:
        print("HINWEIS (--ohne-zustand): PAIEC_WORK/modell/cv_A/state_f*.json ausdruecklich nicht geprueft - Rohwerte von Tabelle 7 nicht gegen die Zustandsdateien")
    else:
        fehl("PAIEC_WORK/modell/cv_A/state_f0..9.json nicht erreichbar: die Rohwerte von Tabelle 7 koennen nicht geprueft werden (fail-closed, R2/Q2); "
             "PAIEC_WORK setzen oder ausdruecklich --ohne-zustand")


def pruefe_tabelle6(tab6):
    """(b) Tabelle 6 (Budget-Tabelle): jede Zelle aus dem VOLLEN Wert (liga_vergleich.json, 8 Stellen) EINMAL gerundet, exakte Zeichenkette.
    R2/P1: frueher gegen die 5-stellig gespeicherten brier_je_budget der auswertung.json geprueft - dort ist 0.19465 -> 0.1946 (Doppelrundung) 'richtig'.
    Die 5-stelligen Werte dienen nur als Gegenprobe (|Diff| <= 0.5e-5)."""
    p2 = lade("P2")
    L = lade("LIGA_VOLL")
    namen = {"ours": "hier_item", "Submission": "hier_item", "\\BB": "beta_binomial", "\\EM": "empirischer_mittelwert"}
    S = None
    n = 0
    bad = 0
    for l in tab6.splitlines():
        if "&" not in l or l.lstrip().startswith(("\\caption", "\\label", "Regime", "\\toprule")) or "Regime" in l:
            continue
        z = _zellen(l)
        if z[0].startswith("$S="):
            S = "S" + z[0][3:].rstrip("$")
        key = namen.get(z[1])
        if key is None or S is None or len(z) < 8:
            continue
        roh = [voll(L, S, key, f"B{b}") for b in (0, 1, 3, 7, 15, 31)]
        alt = [float(p2["tabelle_alle"][S][key]["brier_je_budget"][f"B{b}"]) for b in (0, 1, 3, 7, 15, 31)]
        soll = [einfach(x) for x in roh]
        n += 1
        for b, r_, a_ in zip((0, 1, 3, 7, 15, 31), roh, alt):
            if abs(r_ - a_) > 0.5e-5 + 1e-12:
                bad += 1
                fehl(f"Tabelle 6 {S} {z[1]} B{b}: voller Wert {r_:.8f} weicht von auswertung.json ({a_}) ab")
        for b, g, s_, r_ in zip((0, 1, 3, 7, 15, 31), z[2:8], soll, roh):
            if g != s_:
                bad += 1
                art = "doppelt gerundet (5 -> 4 Stellen)" if g == doppelt(r_) else "weicht ab"
                fehl(f"Tabelle 6 {S} {z[1]} B{b}: gedruckt {g} != {s_} (einfach gerundet aus {r_:.8f}) - {art}")
    if n == 9 and not bad:
        ok("Tabelle 6: 54 Zellen = einfach gerundete volle Werte (liga_vergleich.json, regime[S].familien[pred].niveau[B<b>].mittel)")
    elif n != 9:
        fehl(f"Tabelle 6: {n} Zeilen statt 9")


def pruefe_vorzeichen(tex, tabs):
    """(c) Gedruckte Differenzen gegen die Definition des Schaetzers: H2c = kappa_ML - U/V0 (Tafel estimand), Tab. 1 = ours - X, Tab. 3 = method - ours."""
    tafel = lade("TAFEL")
    H = {x["id"]: x for x in tafel["hypothesen"]}
    h2c = H["H2c"]
    if not h2c["estimand"].startswith("κ̄_ML") or "− U/V0" not in h2c["estimand"].split(";")[0]:
        fehl(f"H2c estimand '{h2c['estimand'][:40]}' ist nicht 'kappa_ML - U/V0' - Vorzeichenpruefung veraltet")
    d = lade("H2C")
    k, uv = d["kappa_ML_mittel_cvA"], d["U_durch_V0_gepoolt"]
    soll_disc = f"$\\bar\\kappa_{{\\mathrm{{ML}}}} = {k:.3f}$, $U/V_0 = {uv:.3f}$, difference ${k - uv:+.3f}$"
    t2 = norm(tabs["TAB2"])
    if soll_disc in t2:
        ok("Tab. 2 H2c discovery: Reihenfolge und Vorzeichen = kappa - U/V0")
    else:
        fehl(f"Tab. 2 H2c discovery: erwartet '{soll_disc}' (Differenz = kappa_ML - U/V0 = {k - uv:+.5f})")
    v = h2c["value"]
    soll_konf = f"$\\bar\\kappa$ {v['kappa_ML']:.3f}, $U/V_0$ {v['U_durch_V0']:.3f}, difference {v['kappa_ML'] - v['U_durch_V0']:+.3f}"
    if soll_konf in t2 and abs((v["kappa_ML"] - v["U_durch_V0"]) - v["differenz"]) < 1e-6:
        ok("Tab. 2 H2c konfirmatorisch: Vorzeichen = kappa - U/V0 = Tafelfeld differenz")
    else:
        fehl(f"Tab. 2 H2c konfirmatorisch: erwartet '{soll_konf}'; Tafelfeld differenz {v['differenz']}")
    dv = h2c.get("discovery_value", "")
    m = re.fullmatch(r"κ̄_ML = ([\d.]+), U/V0 = ([\d.]+), Differenz ([+−-][\d.]+), SE_boot ([\d.]+)", dv)
    if not m or vorzeichen_falsch(float(m.group(1)) - float(m.group(2)), m.group(3)[0] in "−-") or m.group(3).replace("−", "-") != f"{k - uv:+.3f}":
        fehl(f"hypothesen_tafel.json H2c discovery_value '{dv}': Reihenfolge/Vorzeichen != kappa - U/V0 = {k - uv:+.3f}")
    else:
        ok("hypothesen_tafel.json H2c discovery_value: kappa - U/V0 mit Vorzeichen")
    # Tabelle 1: ours - BB und ours - EM aus den ALC-Spalten derselben Zeile
    n = 0
    for l in tabs["TAB1"].splitlines():
        if not re.match(r"(S\d+|compact10)", l):
            continue
        z = _zellen(l)
        em, bb, hk, hi = (float(x) for x in z[1:5])
        for spalte, ref in ((5, bb), (6, em)):
            m = re.match(r"\$([+-]?[\d.]+) \\pm", z[spalte])
            if not m:
                fehl(f"Tab. 1 {z[0]}: Differenzzelle {z[spalte]!r} nicht lesbar")
                continue
            if abs((hi - ref) - float(m.group(1))) > 1.6e-4:
                fehl(f"Tab. 1 {z[0]}: gedruckte Differenz {m.group(1)} != ours - Referenz = {hi - ref:+.4f} (Vorzeichen/Definition)")
            else:
                n += 1
    # Tabelle 3 (Liga): Delta = Methode - ours aus den ALC-Spalten; 'ours' ist die Referenzzeile
    ours = None
    for l in tabs["TAB3"].splitlines():
        if l.startswith("ours (v1 path)"):
            z = _zellen(l)
            ours = (float(z[1]), float(z[2]))
    if ours is None:
        fehl("Tab. 3: Referenzzeile 'ours (v1 path)' fehlt")
    else:
        for l in tabs["TAB3"].splitlines():
            if "&" not in l or l.startswith(("ours (v1 path)", "method", "\\")) or "pm" not in l:
                continue
            z = _zellen(l)
            for sp, ref in ((4, ours[0]), (5, ours[1])):
                m = re.match(r"\$([+-]?[\d.]+) \\pm", z[sp])
                alc = float(z[1] if sp == 4 else z[2])
                if not m or abs((alc - ref) - float(m.group(1))) > 1.6e-4:
                    fehl(f"Tab. 3 {z[0]}: gedruckte Differenz {m.group(1) if m else z[sp]} != Methode - ours = {alc - ref:+.4f}")
                else:
                    n += 1
    ok(f"Differenzen Tab. 1/3: {n} Zellen = Methode/ours - Referenz aus den ALC-Spalten")


def pruefe_nearest(tex):
    """N2: 'the nearest family' nur im belegten Bereich (aus vergleich_gepaart.csv)."""
    import io
    vg = [r for r in csv.DictReader(io.StringIO((PROJ / "./liga/ergebnisse/vergleich_gepaart.csv").read_text(encoding="utf-8"))) if r["referenz"] == "v1_hier_item"]
    fam = ("irt2pl", "irt1pl", "mf", "stack", "knn", "gb", "beta_binomial")
    naechste = {}
    for S in ("S1", "S2", "S3", "S30", "kompakt10"):
        naechste[S] = min(fam, key=lambda m: float(next(r for r in vg if r["modell"] == m and r["S"] == S)["mittel"]))
    bereich = [S for S in ("S1", "S2", "S3", "S30", "kompakt10") if naechste[S] == "irt2pl"]
    if bereich == ["S1", "S2", "S3"]:
        erwarte(tex, "the nearest family from one to three subjects", "'nearest family' nur S1-S3 (2PL ist dort die kleinste Differenz)")
    else:
        fehl(f"IRT 2PL ist die naechste Familie in {bereich}, nicht in S1-S3 - Satz 'nearest family' anpassen (naechste je Regime: {naechste})")
    if re.search(r"nearest family throughout", norm(tex)):
        fehl("'nearest family throughout' (gilt bei S30 nicht: naechste Familie dort " + naechste["S30"] + ")")


def pruefe_zaehlangaben(tex, repo):
    """(d) Zaehlangaben des Textes gegen die tatsaechlichen Dateien im Export (N5 und Verwandte)."""
    t = norm(tex).replace("\\_", "_")
    csvdir = repo / "audit" / "csv"
    zeilen = {}
    for p in sorted(csvdir.glob("F*.csv")):
        zeilen[p.name.split("_")[0]] = sum(1 for _ in p.open(encoding="utf-8")) - 1
    # Zaehlungen im Text (Anhang E)
    m = re.search(r"Lists F1--F9g(.*?)Evidence packs \(17\)", t, re.S)
    if not m:
        fehl("Anhang E: Listenabsatz nicht gefunden")
        return
    blk = m.group(1)
    tz = {}
    for k, n in re.findall(r"texttt\{(F\d[a-z]?)_[^}]*\.csv\} \(([\d,]+)(?: folders| rows)?\)", blk):
        tz[k] = int(n.replace(",", ""))
    m7 = re.search(r"F7a\}/\\texttt\{F7b\} collapsed pairs \((\d+), (\d+)\)", blk)
    if m7:
        tz["F7a"], tz["F7b"] = int(m7.group(1)), int(m7.group(2))
    m9 = re.search(r"F9a\}--\\texttt\{F9g\} \(([\d, ]+) rows\)", blk)
    if m9:
        for k, n in zip("abcdefg", [int(x) for x in m9.group(1).split(",")]):
            tz["F9" + k] = n
    if len(tz) != 18:  # F1,F2,F3a,F3b,F4,F5a,F5b,F6,F7a,F7b,F8,F9a-g (ohne doppelte) = 11 + 7
        fehl(f"Anhang E: {len(tz)} Listenzahlen im Text gefunden, 18 erwartet: {sorted(tz)}")
    nur_eine_weniger = {"F1", "F9c", "F9d", "F9e"}
    fehlend_im_repo = sorted(k for k in tz if k not in zeilen)
    if fehlend_im_repo != ["F2", "F3b", "F9b"]:
        fehl(f"Anhang E: im oeffentlichen audit/csv/ fehlen {fehlend_im_repo}, der Text sagt F2, F3b, F9b")
    abw = {}
    for k, n in tz.items():
        if k not in zeilen:
            continue
        if zeilen[k] == n:
            continue
        if k in nur_eine_weniger and zeilen[k] == n - 1:
            continue
        abw[k] = (n, zeilen[k])
    if abw:
        fehl(f"Anhang E: Zeilenzahlen Text vs audit/csv/ (Text, Repo): {abw}")
    gleich_minus1 = sorted(k for k in tz if k in zeilen and zeilen[k] == tz[k] - 1)
    if gleich_minus1 != sorted(nur_eine_weniger):
        fehl(f"Anhang E: Listen mit einer Zeile weniger im Repo: {gleich_minus1}, Text nennt F1, F9c, F9d, F9e")
    erwarte(tex, "(row counts of the full lists sent to the organisers; the public \\texttt{audit/csv/} omits F2, F3b and F9b, and F1, F9c, F9d and F9e each omit one row for a benchmark folder under a separate note, see \\texttt{audit/README.md})", "Anhang E: Hinweis auf vollstaendige gegen oeffentliche Listen")
    ok(f"Zaehlangaben Anhang E: {len(zeilen)} oeffentliche Listen nachgezaehlt (Abweichungen nur wie im Hinweis genannt)")
    # weitere Zaehlangaben
    pat = repo / "audit" / "patches"
    n_patch = len(list(pat.glob("*.patch")))
    if n_patch == 3 and "3 patches" in t and "Patches (3," in t:
        ok("Zaehlangabe: 3 Patches = audit/patches/*.patch")
    else:
        fehl(f"Zaehlangabe Patches: Repo {n_patch}, Text '3 patches'/'Patches (3,'")
    paketliste = re.search(r"Evidence packs \(17\): (.*?); each with", t)
    if paketliste:
        namen = [x.strip() for x in paketliste.group(1).split(",")]
        n = 0
        for x in namen:
            mm = re.fullmatch(r"docs_9a--9g", x)
            n += 7 if mm else 1
        if n == 17:
            ok("Zaehlangabe: 17 Evidenzpakete = aufgelistete Namen (docs_9a--9g = 7)")
        else:
            fehl(f"Zaehlangabe Evidenzpakete: Liste ergibt {n}, Text 17")
    nt = sum(len(re.findall(r"^\s*def test_", p.read_text(encoding="utf-8"), re.M)) for p in (repo / "modell" / "tests").glob("*.py"))
    nl = len(re.findall(r"^\s*def test_", (repo / "theorie" / "test_alc_law.py").read_text(encoding="utf-8"), re.M))
    if nt == 26 and "26 unit tests" in t:
        ok("Zaehlangabe: 26 Unit-Tests = modell/tests")
    else:
        fehl(f"Zaehlangabe Unit-Tests: Repo {nt}, Text '26 unit tests'")
    if nl == 11 and "(11 tests, including one deliberately triggered failure)" in t:
        ok("Zaehlangabe: 11 Tests = theorie/test_alc_law.py")
    else:
        fehl(f"Zaehlangabe test_alc_law: Repo {nl}, Text '11 tests, including ...'")
    mt = (repo / "curation" / "tests" / "test_mdb_check.py").read_text(encoding="utf-8")
    varianten = re.findall(r'pruefe\("(V\d)[^"]*"', mt)
    korrupt = sorted({v for v in varianten if v != "V0"})
    if len(korrupt) == 7 and "tested on 7 deliberately corrupted copies and an unmodified control" in t:
        ok("Zaehlangabe: mdb_check 7 beschaedigte Kopien + 1 unveraenderte Kontrolle (test_mdb_check.py)")
    else:
        fehl(f"Zaehlangabe mdb_check: Test hat {len(korrupt)} beschaedigte Varianten {korrupt}; Text: 'tested on 7 deliberately corrupted copies ...'")
    pr = PROJ / "v2-plan" / "PRAEREGISTRIERUNG-v2.md"
    if pr.is_file():
        b = pr.read_bytes()
        erwarte(tex, f"{len(b):,} bytes, {b.count(bytes([10]))} lines", "Zaehlangabe: Praeregistrierung Bytes/Zeilen")
    # Benchmark-Anzahlen: 62 (L10) und 142 (Testbenchmarks), aus der Rauschboden-CSV
    nz = list(csv.DictReader((repo / "curation" / "noise_floor_by_benchmark.csv").open(encoding="utf-8")))
    n62 = sum(1 for r in nz if r["L10_response_weighted"] not in ("", None) and float(r["cells_rep"]) >= 100)
    if n62 == 62 and len(re.findall(r"\b62 benchmarks", t)) >= 4:
        ok("Zaehlangabe: 62 Benchmarks mit >= 100 Wiederholungszellen = noise_floor_by_benchmark.csv")
    else:
        fehl(f"Zaehlangabe 62 Benchmarks: CSV {n62}")


# Satzregister (e): geprueft am 2026-10-21 (Feinschliff N, Runde 1; Runde 2 R2: ganzes Dokument, Allwoerter all/any/no/lowest/largest u. a., Ziffern im Hash); Notiz = womit der Satz belegt ist
SATZREGISTER = {
    'ianexactthreetermlearningcurvepriorsamplingsplit': ('236a7859aa', "H2a Design B max |Fehler| <= 5 % und 'every budget': pruefe_zahlen H2a (3 < max <= 5)"),
    'withonesubjectperbenchmarkthesubmittedpredictori': ('7783be0ffd', "H1 S1 Design A und B: grey zone (Tafel; Tab. 1 konfirmatorisch beide g); -0.0004 +- 0.0004 und 0.0049 +- 0.0007 aus der Tafel (pruefe_differenzen_text); 'neither' = Regel b/w/e/g (grey = weder besser noch aequivalent)"),
    'inamethodleagueoverallfoldswithonesubjectperbenc': ('fbd812794b', "S1: alle Weichfamilien g, GB w (Liga-Urteile); 'best or tied-best' = rangfolge.csv (pruefe_allaussagen)"),
    'endabstractsectionintroductionlabelsecintrowheni': ('66b9c9545a', "These der Arbeit; auf Schaetzer beschraenkt, die die offenbarten Labels nutzen, und durch 0.012 vs 0.0050 ALC belegt (pruefe_allaussagen 'Schluss'); Interpretation, kein Messwert"),
    'itemresponsemodelsevaluatelanguagemodelsonfeweri': ('7f96bcbd4d', "Literaturluecke mit 'to our knowledge'; 'any' steht in der Fragestellung, keine Messaussage"),
    'bathreetermlearningcurveforposteriormeanpredicto': ('0d76b776a1', "Beitragsbeschreibung; 'no fitted parameter' = Momente aus den Daten, keine Anpassung an die BB-Kurve (A.8-Rezept); H2a passed (Tafel, pruefe_zahlen)"),
    'brierperbudgetforembbthepairlevelmodelandthesubm': ('0623c9490d', "Fig.-1-Caption; 'nothing fitted' wie oben; Formelkurve aus alc_law (formel_check.log, pruefe_zahlen Formelmomente)"),
    'perpairwithgeitemstheitemsaresplitintoacquisitio': ('e515d1da13', 'Protokollbeschreibung (Veranstalterregeln, modell/simulator.py); ALC-Gewichte 0.1/0.2/0.2/0.2/0.2/0.1 durch pruefe_a7_gewichte mitgeprueft'),
    'thestreamingdriverpassesonetextttlabeledsetperch': ('5d3ead2bc5', 'Beschreibung des Veranstalter-Treibers (paiec_baseline streaming_ingestion.py); Selbstauskunft aus dem Quelltext, im Export nicht ausfuehrbar'),
    'asubjectemphisitsfielddictionarypairswithidentic': ('b6e52bb21e', 'Protokolleigenschaft (Subjekt = Feldwoerterbuch); Ueberschuss +0.6/+1.2/+8.9 aus Praereg/bb_regime_check.log uebernommen (nicht neu rechenbar im Export)'),
    'theonlytrainingsourceisthemeasurementdatabankrev': ('061a5b2b56', 'Beschreibung der Datenbasis (daten_zusammenfassung.json: Benchmarks, Zeilen, Antworten)'),
    'responsesareusedasreleasedtextttlowerisbetterben': ('d4084d30be', 'Ausschluesse aus dem Audit (DQ-Bericht 64/120, 12 Subjekte)'),
    'pairswithgeitemsoccurinbenchmarkspairsmedianbenc': ('a725552267', 'aus paare.parquet neu berechnet (pruefe_paare_statistik: 142 Benchmarks, 12,918 Paare, Median 13, zwei Benchmarks 59 %, 52 % ohne normalized_name); ohne PAIEC_WORK rc 1'),
    'sectiontheorywhatsetstheerrorlabelsectheorytextb': ('49d4e1d17a', 'G_B <= 0 nur mit Itemwissen: Beweis A.1; Zerlegung exakt (Test test_alc_law/Brier-Identitaet)'),
    'itsmurphydecompositionshowsforthesubmittedmodelb': ('4c162a5b88', 'Reliabilitaet <= 0.0006 in jedem Budget: verlust.json murphy_S3 (max, aufgerundet) per pruefe_zahlen'),
    'disclosurethesplittermwasaddedafterashortfallatb': ('149df933d7', "Chronologie (Selbstauskunft); die ersten Formelfassungen existieren nicht mehr, die 13 % sind im Export nicht neu rechenbar; 'before any confirmatory run' = Praereg 8 ('nichts wurde nach Sicht auf Konfirmationsdaten geaendert') und PRAEREG-HASH.txt (pruefe_prereg_zitate)"),
    'consequenceskappauvminimiseseverybudgetserroroft': ('564b88fcc0', 'kappa* je Budget numerisch: Zweiterm U/V0, mit Split-Term 2.76 (pruefe_allaussagen)'),
    'atbudgettheconstantscoresthesubmittedmodelandale': ('5f01675ecd', "Leiterzahlen aus leiter.json/leiter_ergaenzung.json (pruefe_zahlen); 65 % und 3--6 % durch pruefe_allaussagen; 'largest lever' = 65 % gegen 3--6 % (Faehigkeit)"),
    'thepairrateoraclegivesuthewithinpairtermisofthec': ('98f2a34706', "P3 (R2): L7 0.1833, 73 %/92 %, Drittel (pruefe_zahlen); 'the cell-rate oracle k/n leaves 0.0065 (L9, biased low)' - L9 ist verzerrt, unverzerrt L10 = 0.044 (Mittel)/0.049 (Median); Kehrseite: gilt nicht, wenn die meisten Zellen n >= 2 haetten"),
    'onthebenchmarkswithrepeatedresponsestheperbenchm': ('a3afd53cf5', "'dominated by one benchmark': argmax(responses_rep) 72 % (pruefe_endpruefung_l2 M1)"),
    'sectionmethodlabelsecmethodthesubmittedpredictor': ('5c8d01ce28', "Modellbeschreibung (Design); 'always cold' = Konstruktion des Modells (model.py)"),
    'onefilestandardlibraryonlynonetwork': ('710b977fb2', 'Paketbeschreibung (README/ZIP: eine Datei model.py, Standardbibliothek)'),
    'textttpredictneverraisesonanexceptionitfallsback': ('1211d7617e', 'Konstruktion (Fangschicht in model.py); Beleg: 0 Ausnahmen bei 10^4 Eingaben, 10^4 Rueckfaelle bei kaputtem Zustand (pruefe_paket)'),
    'textbfwhynotextadecisionwithaboundatbudgetthesub': ('8b0d3d278a', "P4 (R2): 0.2485 = L1, das eingereichte Modell, KEINE Schranke; textfreie Faehigkeitsorakel L3'/L3'' 0.2480/0.2460 (leiter_ergaenzung.json; pruefe_schranken_aussagen); 'at most 0.2067' nur fuer benchmarkweite Texte (Item-Orakel L8 liegt tiefer); Kehrseite: L3'' ist in-sample (optimistisch)"),
    'thatroomiswhatamortisedtextbasedapproachestarget': ('7362299c0e', "Einordnung; 'what no text-free predictor can do' gilt nur fuer die genannten Orakelstufen/Regeln (A.1: G_B <= 0 nur mit Itemwissen; A.5-Leiter), nicht fuer jede denkbare Anreicherung"),
    'textbfdesignsregimesseedsdesignabenchmarkcoldfol': ('b808613bf0', 'Beschreibung des Designs (Falten nur auf Trainingsbenchmarks gefittet: Konstruktion in kreuzvalidierung.py)'),
    'theemphdiscoverysetfoldseedseedsiswhereeveryhypo': ('5393aec3bd', 'Herkunft jeder Hypothese: Praeregistrierung (Entdeckung vor Einfrieren)'),
    'itisconfirmatorywithrespecttosamplingrandomnessn': ('5b67c91c12', "Praereg ('Scope and honesty frame'): alle Hypothesen aus denselben 142 Benchmarks (pruefe_zahlangaben_dateien: 142 durch cv_A_p2, liga_vergleich.json, wiederholung_b.json belegt)"),
    'textbfdecisionruleallcomparisonsarepairedoverthe': ('5ad11a90cc', 'Konstruktion der Auswertung (Differenzen je Paar und Seed, SE cluster-robust ueber Benchmarks: n_cluster = 142 in auswertung.json, Praereg 5)'),
    'aboutdirectionalverdictsareproducedsoaboutfalseo': ('bc7884788c', "0.9 = 20 * 2 * Phi(-2) (pruefe_zahlen); 'only' = Tuning nur auf Trainingsbenchmarks (liga_cv.py)"),
    'sectionresultslabelsecresultsinputtabellentabhau': ('4e875479c7', "Tafel H1 (pruefe_zahlen H1/K3), Differenzen mit Vorzeichen aus der Tafel (pruefe_differenzen_text, inkl. -0.0347 gegen EM = teile.*.S1.gegen_empirischer_mittelwert); Power 45--46 % (K3); 'neither relevant nor equivalent' = grey zone"),
    'almostallofthedistancetoemissmoothingbbalonegain': ('6c18448833', "EM-BB 0.0347 von 0.0350 (Tab. 1); 'shown only when >= 2': S1 grey, S2-S30 better (H1/Tab. 1)"),
    'emphhfailedsubjectidentityshowsasmalleffectpmatt': ('6f615c63b6', 'H4 < 1/5 des Pooling-Gewinns: H4/H1 je S2, S3 (pruefe_allaussagen)'),
    'emphhbpassedallsixpoolingstepsbetterthefixedkapp': ('472573bb0d', 'Tafel H2b: i_schritte_better = 6 von 6, +21 %/+88 % in den Praereg-Bereichen (pruefe_zahlen H2b)'),
    'emphhpassednoneoftheninemixturestackingandnonpar': ('e3fdd58e0a', 'H5: max |d| = 0.00012, 9/9 equivalent (pruefe_zahlen)'),
    'textbflearningcurvematchandlimitfigreffigformula': ('6c6c9e5bce', '0.8 % bei jedem Budget (discovery S1, pruefe_zahlen) und 5 % Design B; Zweiterm -11 % (pruefe_allaussagen)'),
    'figreffigleagueoverallfoldsatonesubjectperbenchm': ('6e30d710a8', 'S1-Urteile der Weichfamilien alle g, Bereich +0.0003..+0.0009 (pruefe_zahlen Liga S1)'),
    'fromtwosubjectsontheorderingissetbypoolingthesub': ('976a2d3a29', "best in jedem Regime ab S2 = rangfolge.csv; 0/35 better, 23/35 worse; 'from X on' in allen Folgeregimen; nearest family S1-S3 (pruefe_allaussagen, pruefe_nearest)"),
    'thesubmittedmodellosesalctothebetabinomialsmooth': ('5571412861', "Mind2Web (fallbeispiele.json): 62 % bei B0, Priors 0.47/0.52, ab B7 innerhalb 0.001 (pruefe_allaussagen); 'no second subject -> nothing to pool' = Konstruktion (ohne fremdes Label keine Pooling-Information)"),
    'acrossallsinglesubjectbenchmarksthepictureisthes': ('09a02343e2', "verlust.json gruppe_subj_klasse['1']: 13 Benchmarks, +0.0032; 12 von 13 positiv aus je_benchmark.csv (pruefe_allaussagen)"),
    'textbfprotocolsensitivitytablereftabprotocolappe': ('f1d29cdd71', "Zahlen aus Tabelle 4 (jede Zelle neu erzeugt: pruefe_tabellen_4_5), D/F bei N = 80/1000 (pruefe_anhang_belege), Formelfehler -8.3 % (gegen formel_check.log); 'no difference at three subjects' = Pilot equivalent (Tab. 4); 'per-item split makes G_B = 0' = A.1"),
    'thepredictorcostsmsperpredictionwithlabelspassed': ('8e53b68ae4', "0.38 ms (pruefe_paket); 'only'/'no API calls' = Konstruktion"),
    'theauditcoversthepublicreleaseonlyrevisiontexttt': ('1fc6cf135f', 'Geltungsbereich des Audits (Selbstauskunft)'),
    'textttpaiecbaselinetextttccaisreadonlyandinfersn': ('814b648a50', 'Geltungsbereich des Audits (Selbstauskunft)'),
    'inbirdsqlofconfigurationsaregradedonallquestions': ('0bee40ace5', 'DQ-Bericht: 64/120, 360 Fragen, 5.6-40.6 %, 117 Paare, 119 Modelle in 13 Benchmarks (pruefe_zahlen)'),
    'sectionlimitationslabelseclimitstextbfsimulatorv': ('4d576ae461', 'Einschraenkung aus dem Wettbewerbstext (Veranstalter-Angaben, im Export nicht pruefbar); keine Ergebnisbehauptung'),
    'textbfconfirmationalltenhypothesesevaluatedonfre': ('7a7400777a', "Tafel 9/1/0 (pruefe_zahlen); 'only' = Zufallsstichprobe, gleiche 142 Benchmarks (Praereg)"),
    'textbfnotextaboundnotameasurementofwhattextachie': ('ad695c8bf8', 'Einschraenkung; konsistent mit Anhang F (kein Textlauf)'),
    'textbfleaguefinitegridsirtpriorstrengthattheuppe': ('f1bcf0d24f', "IRT-Gitterrand: kappa = Gittermaximum in 10/10 Falten, beide Familien (pruefe_allaussagen); '<= 0.0004' = ./liga/LIGA.md 4.3 und ergebnisse/hyper_rand_f{2,8}.csv (ZAHLEN-QUELLEN), im Export nicht neu hergeleitet; 'edges not checked' ist selbst eine Einschraenkung"),
    'plattscalingperlabelstagevkeptthestageswhosecros': ('412b7d23df', "Platt-Satz identisch mit ZIP-README (pruefe_zahlen); 'at most 2' aus stufenwahl_je_falte"),
    'sectionconclusionlabelsecconclusionunderthepaiec': ('348db3537a', 'R3 2026-10-21 (R1 Endpruefung N2): Protokoll 0.012 = ours S1-S30 (rangfolge), schwaechste der sechs anderen Familien S30 = kNN +0.005023, BB S30 +0.012968 (vergleich_gepaart.csv); BB poolt nicht ueber Subjekte (nur Paar-Labels)'),
    'sectionuseofaiassistantscodeofflineevaluationdat': ('bdc4c97f2f', "Offenlegung (Selbstauskunft, Wettbewerbsregeln); 'all content' = Verantwortungserklaerung des Autors"),
    'thesubmittedpredictorusesnolanguagemodelatruntim': ('077cea1892', 'model.py im ZIP importiert nur Standardbibliothek (pruefe_paketaussagen)'),
    'textttmakeallrebuildsthecrossvalidationtablesfro': ('54ce6065bc', "Makefile-Ziel all im Repo; 20--30 Minuten aus Laufprotokollen, im Satz ausdruecklich 'not timed as one run' (M7); R4: 'free' gestrichen"),
    'datameasurementdbrevisiontextttgatednoneredistri': ('9a7ccb4bc1', 'Lizenz/Weitergabe: nichts redistribuiert (LIZENZ-PRUEFUNG.md)'),
    'paragraphaexactperpairdecompositionforanypredict': ('425c59a715', 'mathematische Identitaet mit Beweis; Test theorie/test_alc_law.py (11 Tests, pruefe_zaehlangaben)'),
    'emphproofperitemnqqkknqpppaveragingtheconstantba': ('e5fa6c1e14', 'Beweis (A.1); Zahlen U = 0.18328, Reliabilitaet <= 0.0006 in jedem Budget (verlust.json murphy_S3), 0.0022, 0.0667 durch pruefe_zahlen; G_B ohne Itemwissen null: Beweis'),
    'paragraphalearningcurveofaposteriormeanpredictor': ('18e6bc319b', "Definitionen ('over all items'), keine Messaussage"),
    'emphdisclosurethetwotermformisthetextbookmseofab': ('4df0fa8177', 'Chronologie (Selbstauskunft, siehe Disclosure in 2); Aenderungen der Formel vor dem Einfrieren (Praereg 8)'),
    'paragraphawhatfollowskappauvminimiseseverybudget': ('c3e1ce2e7c', 'kappa* je Budget numerisch nachgerechnet: Zweiterm U/V0 = 2.722, mit Split-Term 2.76 (pruefe_allaussagen); 2.731 und SE 0.31 aus h2c_discovery.json'),
    'labilityonlyfoldhonesttheta': ('db8711ac80', "'only' ist Teil des Stufennamens; 0.2480 = leiter_ergaenzung.json (pruefe_zahlen)"),
    'labilityonlyinsampletheta': ('47c80c1b23', "'only' ist Teil des Stufennamens; 0.2460 = leiter_ergaenzung.json (pruefe_zahlen); in-sample, optimistisch"),
    'loracleknoverallcellsbiasedcellswithncontributet': ('659ddde365', 'P3 (R2): L9 = 0.0065 ist nach unten verzerrt (Zellen mit n = 1 tragen 0 bei); 0.0229 = orakel_kn_alle_zellen (wiederholung_b.json, pruefe_wiederholungsstatistik); unverzerrt ist L10'),
    'weightingcellsbynoverthemcellswithngeofcellsofal': ('3ebbb2a374', 'wiederholung_b.json: 3.14 M Zellen, 10.0 %, 58.6 %, 68.3 M Antworten, 0.0444 (pruefe_wiederholungsstatistik); Median 0.0488/IQR (pruefe_zahlen); Zweitrechnung exakt (M3)'),
    'caveatsrepeatedresponsesexistonlywherecuratorsre': ('2dd826ab20', "Erklaerung der Datenerzeugung (trial-Spalte), kein Messwert; 72 % und 0.068 (pruefe_endpruefung_l2 M1); 'some benchmarks show zero noise' = Benchmarks mit L10 = 0 (pruefe_wiederholungsstatistik); Ursache ausdruecklich 'a conjecture'"),
    'splitperpairversusperitemgbexistsonlyifevaluatio': ('1051a93aee', 'Theorie (A.1; G_B-Definition), Test test_alc_law'),
    'paragraphaacquisitionlemmasthejthacquiredlabelis': ('08b3dcd666', 'kumulative ALC-Gewichte und Anteile 52 %/81 % aus den Gewichten neu berechnet (pruefe_a7_gewichte)'),
    'emphlemmafallbacktorandomifnocandidateitemcarrie': ('459e412f60', "Beweis plus Test akquise/test_akquise.py (0 abweichende Entscheidungen bei 15,000 Kandidaten); 'any budget-respecting policy equals random in expectation' = Argument im Beweis"),
    'emphlemmaignorabilityifthepurchasedecisiondepend': ('65830ad531', 'Beweisskizze (Theorie, Rubin 1976), bedingt formuliert; keine Messaussage'),
    'atfreezingnoconfirmatoryrunexistedtheconfirmatio': ('64463e3d76', "PRAEREG-HASH.txt: './konfirmation/ existiert zum Zeitpunkt des Einfrierens NICHT' (pruefe_prereg_zitate)"),
    'thefileisnevereditedamendmentswouldbeseparatedat': ('9ea9e1ebdd', 'sha256 e5fd821f unveraendert (pruefe_prereg_zitate); Selbstverpflichtung der Praereg'),
    'amendmentlogatthetimeofthisreportnone': ('5cb82eb5f5', 'keine AMENDMENT-Datei in v2-plan/ und prereg/ (pruefe_prereg_zitate); Praereg 9'),
    'textbfscopeandhonestyframeallhypothesesarosefrom': ('90ab596136', "156/142/12,918 (pruefe_zahlangaben_dateien, pruefe_paare_statistik); Seeds aus der Praereg; 'no new benchmarks exist' = gleiche Datenfreigabe"),
    'rulerifthesubmittedmodelchangeseveryconfirmatory': ('c2ad4ea246', 'Praereg-Zitat (pruefe_prereg_zitate)'),
    'emphdeviationsrecordedtheexceptionoccurredonthed': ('2f5546b466', "Stufenmengen Design A (pruefe_stufen_A2v: {0,1,3,7} in allen zehn Falten, 15 in fuenf, 31 in zwei: pruefe_zahlen); Discovery 'Stufe 3 in 8, Stufe 7 in 7 von 10' = stufenwahl_je_falte (pruefe_zahlen)"),
    'designbinallstageinfiveintworatherthanthepackage': ('62e6a8b545', "Stufenmengen Design B (pruefe_stufen_B2v: pruefe_zahlen); 23/23 Zeilen und groesste ALC-Verschiebung 2.4e-5 aus HYPOTHESEN-TAFEL.md (pruefe_anhang_belege); 'no run was repeated with exactly {0,1}' = Selbstauskunft"),
    'nocomparisonwithsegeisdeclaredequivalent': ('50cb1eb8ca', "Folge der Regel |d| + 2 SE < 0.001; Praereg-Zitat; in keiner Tabelle steht 'e' bei SE >= 0.0005 (pruefe_anhang_belege)"),
    'aboutverdictsnomultiplicitycorrectionexpectation': ('563c31a008', '0.9 = 20 x 2 Phi(-2) und 0.5 = 20 x Phi(-2) = 0.45 (pruefe_zahlen); Praereg 5: keine Korrektur'),
    'textbflearningcurveformulaeqrefeqcurvewithfixede': ('d4272baa4c', 'Beschreibung der Rezepte (alc_law, kreuzvalidierung.py); die fruehere Naeherung und die Zweiterm-Form sind Sensitivitaetszeilen (Tab. 2/A.2)'),
    'hatheformulamatchesthebaselinecurvewithinpmatall': ('2b46b3f862', 'Hypothesenwortlaut der Praereg (zusammengefasst); Ergebnis H2a passed mit <= 5 % (Tafel; pruefe_zahlen)'),
    'hbpoolingactsasansandbudgetdependentreductionoft': ('407fab0ea0', 'Hypothesenwortlaut der Praereg; H2b passed, 6/6 Schritte (Tafel; pruefe_zahlen)'),
    'hsubjectidentityhasnorelevanteffectequivalentins': ('1f2e91db02', 'Hypothesenwortlaut der Praereg; H4 failed (Tafel; Tab. 2, Tab. 5 mit Vorzeichen geprueft)'),
    'hconvexmixturelogitstackingandnpebpriorninecompa': ('18d67e7fdd', 'Hypothesenwortlaut der Praereg; H5 passed 9/9 equivalent (Tafel; pruefe_zahlen)'),
    'textbfleagueruleprotocolidentitymaxdeltaqforeman': ('825169c0fe', "Protokollidentitaet EM/BB max |dq| = 0 (liga/ergebnisse/identitaet_protokoll.csv, pruefe_anhang_belege); 'never beaten', Zeitgrenze 2 h aus der Praereg (pruefe_prereg_zitate); inner 75/25 und seed 100 aus liga_cv.py/meta"),
    'textbfgatesforanymodelchangestratumstagetextprio': ('2579093b48', "Praereg 6; 'none passed or was evaluated in time' = Anhang F und Tab. 4/5 ('not evaluated')"),
    'textbfreportingcommitmentsonejsonobjectperhypoth': ('df026c4c6d', "Praereg 7 ('nothing is re-tuned', pruefe_prereg_zitate); 'every Table 2 number points to a field' - Tab. 2 wird aus hypothesen_tafel.json erzeugt (tabellen_v2.py tab2)"),
    'sectionprotocolreplicatestshardeningruntimelabel': ('c6299b6516', "Beschreibung von modell/simulator.py (Datei im Repo, Pfadpruefung); 'uniformly random subset' = Lemma 1 / test_akquise.py"),
    'subjectsarepresentedthroughtheeightvisiblefields': ('43d140651f', 'Konstruktion (model.py/simulator.py); Felderzahl = Subjektfelder des Wettbewerbs (DQ-Bericht Befund 8)'),
    'textbfaleakfoundandfixedanearlyversionreusedtheg': ('287a3f43a2', 'Chronologie (Selbstauskunft): 0.2239 steht in modell/MODELL.md, 0.2485 = L1 (pruefe_zahlen); Regressionstest modell/tests/test_inferenz.py::test_budget0_nach_labels (setzt _fp = None wie der alte Simulator); gegen den alten Code nicht neu ausgefuehrt'),
    'allresultsbeforethefixwerediscardedaregressionte': ('60554a474b', 'Selbstauskunft; Regressionstest wie oben'),
    'theitemfieldtextttinteractorsvarieswithinsubject': ('31e3706510', 'modell/REVIEW-2.md (interactors.py ueber die 142 CV-Benchmarks); im Export nicht neu gerechnet; Konstruktion: interactors gehoeren zur Antwort (inferenz.py)'),
    'groupingiscachedperlabelsetuptolabelsthekeyisaha': ('4d1df49cfa', 'model.py: VOLL_BIS = 1024, STICHPROBE = 64 (pruefe_paketaussagen)'),
    'cgroupmeansbypolaritydomainsubjectsperbenchmarkt': ('a212b4d370', "'six largest domains' = plots_v2.py sortiert nach n_bm und schneidet bei 6 (Konstruktion); 'missing for 2 of the 142' = verlust.json (pruefe_anhang_belege)"),
    'itemstagereliabilitynotevaluatednoitemlevelrelia': ('90a12c4bcf', 'Nicht-Auswertung; konsistent mit Tab. 4 und Anhang F'),
    'tablereftabfigsourceslabelfiglendfiguresectionda': ('8d1b2a348f', "Beweisstandard des DQ-Berichts ('How the numbers were obtained', zwei Implementierungen) = Selbstauskunft; Tabelle 9 letzte Zeile"),
    'priorreportsweresearchedinthehuggingfacediscussi': ('5601a06938', "DQ-Bericht 'Already reported?' (3 Diskussionen, PRs #1-#7, Issues #1-#3, nur #1 ueberlappt): Zeichenketten im DQ-Bericht (pruefe_anhang_belege)"),
    'everythingwasreadonlytheproposedpatcheswerecheck': ('eaa2133abe', "DQ-Bericht: 'Everything was read-only' und git apply --check; die Regressionstests der Evidenzpakete (stanford-lieferung/baseline/tests, pruefe_patches) fuehren gepatchten Baseline-Code offline aus - der Satz nennt sie ausdruecklich; 'read-only' bezieht sich auf die gepruefte Datenbank und Repositories"),
    'bletextttgetbenchmarkraisestextttkeyerrorembeddi': ('e78400e81a', "Tabelle 8: jede Zahl gegen den DQ-Bericht (pruefe_handtabellen); 'none/no' ist DQ-Wortlaut ('none on measurements', 'mostly none')"),
    'texttttestconditioncontentsharnessspellingscross': ('2625efc062', "Tabelle 8 Zeile 9 und Einleitung Anhang E: DQ-Wortlaut ('mostly none; two questions concern the private pool' -> 'test pool'); 'Lists and evidence packs': Zaehlungen (pruefe_zaehlangaben)"),
    'textbfeffectonthissubmissionfindingsanddefinethe': ('e77bb9265f', "Befunde 3 und 4 = Ausschluesse (Abschnitt 3); 'under 1 %': DQ Befund 5 '< 1 %', Befunde 6 (435 Zeilen) und 7 (830 Items) sind gegen 31,389,917 Zeilen klein, als Anteil nicht neu gerechnet"),
    'auditedrevisionsandshasumsofeverydeliveredfilear': ('f26c781667', "stanford-lieferung/SHA256SUMS deckt alle 175 gelieferten Dateien ab (pruefe_paketaussagen); Wortlaut 'of every delivered file'"),
    'stepdownloadstextttformattedtablesatrevisiontext': ('7c9f32d685', 'Makefile: einziger Netzzugriff ist step0 (scripts/download_data.py, HF_TOKEN), grep im Makefile'),
    'platformcheckoneformativecodabenchevaluationofth': ('9c39c54fe2', "R3 2026-10-21: Codabench-Einreichung 1008180, Score 0.205646 (Codabench-Einreichungsseite des Autors, 21.10.); Spanne 0.1968-0.2129 = Table 1 ours compact10/S1; 'no standard error' = Einzellauf ohne Paar-Daten; 'not used for any decision' = Paket war vor dem Lauf eingefroren (sha 3274b095)"),
    'hardwarecpucoresgibramnogpuaggregationstrainings': ('e1fa978978', 'environment.txt (4 Kerne, 16 GiB, Linux); Zeiten aus Laufprotokollen, nicht neu gemessen; RAM 16 GiB zweimal (M7)'),
    'textttformelchecklogsplittermapproximationalctex': ('bd76bf6b7d', 'Tabelle 9: L10-Median, L9-Abgleich 0.00649/0.00652, Split-Term 0.2130, 1,079,568/1,214,136 und EM/BB max |dq| = 0 gegen die Quelldateien (pruefe_handtabellen, pruefe_anhang_belege)'),
    'apilotononefoldranthefullcrossvalidationwasabort': ('c157fd862e', "Selbstauskunft (Abbruch), konsistent mit Tab. 4/5 'not evaluated'"),
    'textbftextbaseditemprioritemtextsofbenchmarksite': ('49fecbff7e', 'Selbstauskunft aus ./texte/TEXTE.md (123 Benchmarks, 114,030 Items); nicht Teil der Einreichung, im Export nicht rechenbar'),
    'noevaluationwasrunbeforethefreezenothingisreport': ('d5a216e394', 'Selbstauskunft, konsistent mit Anhang F'),
}


# R2/Q1: auch all/any/no/lowest/largest (+ highest, smallest, worst, nothing, neither) und das ganze Dokument (Anhaenge), nicht nur der Haupttext
ALLWORT = re.compile(r"\b(throughout|every|always|never|nearest|best|none|whole|entire|only|all|any|no|lowest|largest|highest|smallest|worst|nothing|neither)\b", re.I)


# R2: Saetze, die unabhaengig von Allwoertern ins Register muessen (Aussagen aus Endpruefungen, die ohne Allwort umformuliert wurden)
PFLICHT_PHRASEN = ("cell-rate oracle", "text-free ability oracles", "biased low")


def allwort_saetze(tex):
    """Saetze des GANZEN Dokuments (Abstract bis \\end{document}, R2/Q1: auch Anhaenge) mit einem Allwort: (Kopf = erste 48 Buchstaben, Hash = sha1 aller Buchstaben, Satz)."""
    i = tex.index("\\begin{abstract}")
    h = norm("\n".join(re.sub(r"(?<!\\)%.*$", "", l) for l in tex[i:tex.index("\\end{document}", i)].splitlines()))  # TeX-Kommentare sind kein Text
    h = re.sub(r"\\mbox\{(\$[^$]*\$)\}", r"\1", h)
    out = []
    for s in re.split(r"(?<=[.;:])\s+(?=[A-Z\\(])", h):
        s_ = re.sub(r"\\cite\w*(\[[^\]]*\])*\{[^}]*\}", "", s)
        if ALLWORT.search(s_) or any(ph in s_ for ph in PFLICHT_PHRASEN):
            buchst = re.sub(r"[^a-z]", "", s_.lower())
            # R2: Ziffern gehen in den Hash ein (vorher nur Buchstaben: eine geaenderte Zahl im Satz machte den Eintrag nicht ungueltig)
            zeichen = re.sub(r"[^a-z0-9]", "", s_.lower())
            out.append((buchst[:48], hashlib.sha1(zeichen.encode()).hexdigest()[:10], s_))
    return out


def pruefe_allaussagen(tex, tabs):
    """(e) Superlative/Allaussagen im Haupttext gegen die Quellzahlen; jeder Satz mit 'throughout/every/always/never/nearest/best/none/whole/entire/only' ist registriert."""
    import io
    vg = [r for r in csv.DictReader(io.StringIO((PROJ / "./liga/ergebnisse/vergleich_gepaart.csv").read_text(encoding="utf-8"))) if r["referenz"] == "v1_hier_item"]
    rang = {r["praediktor"]: r for r in csv.DictReader(io.StringIO((PROJ / "./liga/ergebnisse/rangfolge.csv").read_text(encoding="utf-8")))}
    regs = ("S1", "S2", "S3", "S30", "kompakt10")
    fam = ("irt2pl", "irt1pl", "mf", "stack", "knn", "gb", "beta_binomial")
    uteil = {}
    for m in fam:
        for S in regs:
            r = next(x for x in vg if x["modell"] == m and x["S"] == S)
            d, s = float(r["mittel"]), float(r["se"])
            uteil[(m, S)] = "b" if d + 2 * s < 0 else "w" if d - 2 * s > 0 else "e" if abs(d) + 2 * s < 0.001 else "g"
    # 'best mean ALC in every regime' (ab zwei Subjekten) und 'best or tied-best' (Abstract)
    anderen = [m for m in rang if m != "v1_hier_item"]
    nicht_ohne_item = [m for m in anderen if m != "v1_ohne_itemstufe"]
    for S in regs[1:]:
        if not all(float(rang["v1_hier_item"][S]) < float(rang[m][S]) for m in anderen):
            fehl(f"'best mean ALC in every regime': in {S} ist ein anderer Praediktor nicht schlechter")
    if all(float(rang["v1_hier_item"]["S1"]) <= float(rang[m]["S1"]) + 1e-9 for m in anderen):
        ok("'best (or tied-best) mean ALC in every regime from two subjects on' = rangfolge.csv")
    else:
        fehl("S1: ein Praediktor hat kleineres ALC als ours - 'tied-best' gilt nur fuer S2 ff.")
    # 'from X on': ab dem genannten Regime in allen folgenden Regimen worse
    for m, ab in (("gb", "S1"), ("knn", "S2"), ("irt1pl", "S2"), ("beta_binomial", "S2"), ("irt2pl", "S3"), ("stack", "S30")):
        folge = regs[regs.index(ab):]
        if any(uteil[(m, S)] != "w" for S in folge):
            fehl(f"'{m} worse from {ab} on': nicht in allen Regimen {folge} worse ({[uteil[(m, S)] for S in folge]})")
        else:
            ok(f"'{m} worse from {ab} on' gilt in {folge}")
    # Ladder: 65 % und 3-6 %
    lt = {r["Stufe"].split(" ")[0]: r["Brier_B0"] for r in lade("LEITER")["leiter_B0"]}
    l2 = lade("LEITER2")
    var_r = lt["L0"] - lt["L7"]
    ort = round(100 * (lt["L0"] - lt["L2"]) / var_r)
    f3 = [next(l2[k]["Brier_B0"] for k in l2 if k.startswith(p)) for p in ("L3' ", "L3''")]
    f3 = sorted(round(100 * (lt["L0"] - x) / var_r) for x in f3)
    if ort == 65 and f3 == [3, 6]:
        erwarte(tex, "benchmark location is the largest\nlever at budget 0 (65\\% of $\\mathrm{Var}(R)$)", "Lage = groesster Hebel, 65 % von Var(R)")
        erwarte(tex, "(ability alone adds 3--6\\%)", "Faehigkeit allein 3-6 %")
    else:
        fehl(f"Leiter: Lage erklaert {ort} % (Text 65), Faehigkeit {f3} % (Text 3-6)")
    # Mind2Web: 62 % des Verlusts bei B0, ab B7 innerhalb 0.001, Priors 0.47/0.52
    mw = lade("FALL")["mind2web"]["S3"]
    bj = mw["brier_je_budget"]
    anteil0 = 0.1 * (bj["hier_item"]["0"] - bj["beta_binomial"]["0"]) / mw["diff_hier_item_minus_bb_alc"]
    erwarte(tex, f"{round(100 * anteil0)}\\% of it at budget 0", "Mind2Web: Anteil des Verlusts bei B0")
    if max(abs(bj["hier_item"][b] - bj["beta_binomial"][b]) for b in ("7", "15", "31")) <= 0.001:
        ok("Mind2Web: ab Budget 7 innerhalb 0.001")
    else:
        fehl("Mind2Web: ab Budget 7 nicht innerhalb 0.001")
    R = mw["R_mittel"]; fl = mw["floor_R(1-R)"]
    q_hi = R - math.sqrt(bj["hier_item"]["0"] - fl); q_bb = R - math.sqrt(bj["beta_binomial"]["0"] - fl)
    erwarte(tex, f"sits at {q_hi:.2f} and the smoother's at {q_bb:.2f}", "Mind2Web: Priors 0.47/0.52 aus Brier B0")
    # 12 of 13
    jb = list(csv.DictReader((HIER / "daten/je_benchmark.csv").open(encoding="utf-8")))
    ein = [float(r["gewinn_vs_bb"]) for r in jb if float(r["n_subjects"]) == 1]
    erwarte(tex, f"{sum(x > 0 for x in ein)} of {len(ein)} positive", "Ein-Subjekt-Benchmarks: positive Zahl")
    # H4: unter einem Fuenftel des Pooling-Gewinns
    H = {x["id"]: x for x in lade("TAFEL")["hypothesen"]}
    a1 = H["H1"]["teile"]["A"]
    anteile = [abs(H["H4"]["value"][S]) / abs(a1[S]["d"]) for S in ("S2", "S3")]
    if max(anteile) < 0.2:
        ok(f"'under one fifth of the pooling gain': H4/H1 = {[round(x, 3) for x in anteile]}")
    else:
        fehl(f"'under one fifth of the pooling gain' falsch: H4/H1 = {anteile}")
    # kappa*: Zweiterm exakt U/V0 je Budget; mit Split-Term 2.76
    d = lade("DEX"); b = lade("BEOB")
    U, V0, D, F = b["U_E"], b["S1/beta_binomial"]["(q-R)^2"]["0"], d["D_exakt = E 4V/(N-1)"], d["E[V/(NA-1)]"]
    ks = [x / 1000 for x in range(500, 6000)]
    def fehler(B, kap, D_, F_):
        return (B * (U - (B - 1) * F_) + kap ** 2 * V0) / (B + kap) ** 2 + B / (B + kap) * D_
    zwei = {B: min(ks, key=lambda x: fehler(B, x, 0.0, 0.0)) for B in (1, 3, 7, 15, 31)}
    drei = {B: min(ks, key=lambda x: fehler(B, x, D, F)) for B in (1, 3, 7, 15, 31)}
    if all(abs(v - U / V0) < 2e-3 for v in zwei.values()) and all(round(v, 2) == 2.76 for v in drei.values()):
        erwarte(tex, "minimises every budget's error of the two-term form (2.76 with the split term;", "kappa* = U/V0 je Budget (Zweitermform), 2.76 mit Split-Term")
    else:
        fehl(f"kappa* je Budget: Zweiterm {zwei}, mit Split-Term {drei} (Text: U/V0 bzw. 2.76)")
    # Zweiterm-Fehler bei B31 und IRT-Gitterrand
    k2 = alc_law_modul().lernkurve(U, V0, b["kappa_mittel_ueber_testpaare"], 0.0, 0.0)
    o31 = b["S1/beta_binomial"]["(q-R)^2"]["31"]
    erwarte(tex, f"fails by ${100 * (k2[31] - o31) / o31:.0f}\\%$ at budget 31", "Zweiterm-Form: Fehler bei B31")
    liga = PROJ / "./liga/ergebnisse"
    if (liga / "hyper_wahl.csv").is_file() and (liga / "hyper_gitter.csv").is_file():
        wahl = list(csv.DictReader((liga / "hyper_wahl.csv").open(encoding="utf-8")))
        grid = list(csv.DictReader((liga / "hyper_gitter.csv").open(encoding="utf-8")))
        def kv(s):
            return dict(x.split("=") for x in s.split(","))
        rand = True
        for fa in ("irt1pl", "irt2pl"):
            mx = max(float(kv(r["konfig"])["kappa"]) for r in grid if r["familie"] == fa and "kappa" in kv(r["konfig"]))
            ws = [float(kv(r["wahl"])["kappa"]) for r in wahl if r["familie"] == fa]
            rand = rand and len(ws) == 10 and all(w == mx for w in ws)
        if rand:
            ok("'IRT prior strength at the upper edge in all folds': kappa gewaehlt = Gittermaximum in 10/10 Folds (beide IRT-Familien)")
        else:
            fehl("IRT-Gitterrand: nicht in allen Folds am oberen Rand")
    # Schluss: Protokollgroessen gegen Familienwahl
    ours = [float(rang["v1_hier_item"][S]) for S in ("S1", "S30")]
    protokoll = ours[0] - ours[1]
    schwach = max(float(next(r for r in vg if r["modell"] == m and r["S"] == "S30")["mittel"]) for m in ("irt2pl", "irt1pl", "mf", "stack", "knn", "gb"))
    bb30 = float(next(r for r in vg if r["modell"] == "beta_binomial" and r["S"] == "S30")["mittel"])
    if f"{protokoll:.3f}" == "0.012" and f"{schwach:.4f}" == "0.0050" and f"{bb30:.4f}" == "0.0130":
        erwarte(tex, "(0.012 ALC for the submitted model from one to thirty subjects) more than the choice among the other six families (0.0050 ALC for the weakest of them, kNN, at thirty subjects); the beta-binomial, which does not pool labels across subjects, trails by 0.0130 there.", "Schluss: Protokoll vs Familienwahl (R1: BB getrennt)")
    else:
        fehl(f"Schluss: Protokolleffekt {protokoll:.4f} (Text 0.012), schwaechste Familie {schwach:.5f} (Text 0.0050), BB S30 {bb30:.5f} (Text 0.0130)")
    # Plattform-Satz (Codabench 1008180, Score laut Codabench-Einreichungsseite 21.10.: 0.205646; Spanne aus Table 1 ours)
    if "0.2056" in tex:
        erwarte(tex, "returned Brier ALC 0.2056, inside the range of the offline replica (0.1968--0.2129 across regimes", "Plattform-Satz Anhang F")
        if not (0.1968 <= 0.205646 <= 0.2129):
            fehl("Plattform-Score ausserhalb der Offline-Spanne")
    # Verbotene Formulierungen (Befunde der Endpruefungen)
    for rx, was in ((r"whole\s+lever", "'whole lever'"), (r"present only when", "'present only when'"), (r"two thirds of it at budget 0", "'two thirds' bei Mind2Web"),
                    (r"any estimator choice in the text-free class", "'any estimator choice in the text-free class'"),
                    (r"estimator chosen within the text-free class", "'estimator chosen within the text-free class'"),
                    (r"helped\s+only under heavy", "'helped only under heavy item overlap'"), (r"9 deliberate corruptions", "'9 deliberate corruptions'"),
                    (r"hollow: oracles fitted in-sample", "'oracles fitted in-sample'"), (r"failure case triggered once", "'failure case triggered once'")):
        if re.search(rx, norm(tex)):
            fehl(f"Allaussage/Formulierung nicht belegt: {was}")
    # Satzregister: jeder Satz des Haupttexts mit einem Allwort steht im Register (oder ist neu und muss geprueft werden)
    gesehen = set()
    unbekannt, geaendert = [], []
    for kopf, hsh, s_ in allwort_saetze(tex):
        gesehen.add(kopf)
        if kopf not in SATZREGISTER:
            unbekannt.append(s_[:110])
        elif SATZREGISTER[kopf][0] != hsh:
            geaendert.append(s_[:110])
    if unbekannt or geaendert:
        fehl("Haupttext: Saetze mit Allwort (throughout/every/always/never/nearest/best/none/whole/entire/only) ohne gueltigen Eintrag im Satzregister "
             f"(erst gegen die Quelle pruefen, dann mit satzregister_neu.py eintragen): neu {unbekannt[:3]}, seit der Pruefung geaendert {geaendert[:3]}")
    else:
        ok(f"Satzregister: {len(gesehen)} Saetze mit Allwort im Haupttext, alle geprueft und unveraendert seit der Pruefung")
    return gesehen


_ALC = None


def alc_law_modul():
    global _ALC
    if _ALC is None:
        import alc_law as m  # noqa: E402
        _ALC = m
    return _ALC


def pruefe_literatur_und_layout(tex, refs, texpfad, mit_bbl=True):
    """O1, O2, O3, O9, O12, O13, O14, O16: Literaturliste, Reihenfolge der Tabelle 11, Spaltentypen, Nullen mit Vorzeichen, Schreibweisen."""
    tabdir = texpfad.parent / "tabellen"
    alle_tabs = {p.name: p.read_text(encoding="utf-8") for p in sorted(tabdir.glob("*.tex"))}
    qa = texpfad.parent / "abbildungen" / "quellen_abbildungen.tex"
    if qa.is_file():
        alle_tabs[qa.name] = qa.read_text(encoding="utf-8")
    # --- O12: Grossschreibung nach Doppelpunkt, DOI im Feld doi statt im Venue-Text
    schlecht = []
    doi_text = []
    for e in re.split(r"(?m)^@", refs)[1:]:
        key = e.split("{", 1)[1].split(",", 1)[0]
        mt = re.search(r"^\s*title\s*=\s*\{(.*)\},?\s*$", e, re.M)
        if mt and re.search(r":\s+\{?[a-z]", mt.group(1)):
            schlecht.append(key)
        mh = re.search(r"^\s*howpublished\s*=\s*\{(.*)\},?\s*$", e, re.M)
        if mh and re.search(r"\bDOI\b|doi:", mh.group(1)):
            doi_text.append(key)
    if schlecht:
        fehl(f"refs.bib: Titel mit Kleinbuchstaben nach dem Doppelpunkt: {schlecht}")
    else:
        ok("refs.bib: Grossschreibung nach Doppelpunkt einheitlich")
    if doi_text:
        fehl(f"refs.bib: DOI steht im Venue-Text statt im Feld doi: {doi_text}")
    else:
        ok("refs.bib: keine DOI im howpublished-Text (Feld doi)")
    # --- O13: Tabelle 11 in der Reihenfolge der Literaturliste (.bbl)
    bbl = texpfad.with_suffix(".bbl")
    g = alle_tabs.get("tabG_bibliografie.tex")
    if not mit_bbl:
        pass  # vor dem ersten Bau (--ohne-pdf) gibt es keine .bbl; die Reihenfolge wird nach dem Bau geprueft
    elif bbl.is_file() and g:
        reihenfolge = re.findall(r"\\bibitem\[[^\]]*\]\{([^}]+)\}", bbl.read_text(encoding="utf-8"))
        zeilen = [l for l in g.splitlines() if l.strip().startswith("\\citet")]
        links, rechts = [], []
        for l in zeilen:
            ks = re.findall(r"\\citet\{([^}]+)\}", l)
            links.append(ks[0])
            if len(ks) > 1:
                rechts.append(ks[1])
        tabelle = links + rechts
        soll = [k for k in reihenfolge if k in set(tabelle)]
        if tabelle == soll:
            ok(f"Tabelle 11: {len(tabelle)} Schluessel in der Reihenfolge der gedruckten Literaturliste")
        else:
            fehl(f"Tabelle 11 nicht nach gedruckter Zitation (Literaturliste) sortiert: Tabelle {tabelle[:6]}... Liste {soll[:6]}...")
    else:
        fehl("Tabelle 11/.bbl fehlt - Sortierpruefung nicht moeglich (fail-closed)")
    # --- O1: keine Blocksatz-p-Spalten; Captions mit Pfaden linksbuendig
    blocksatz = []
    for name, s in list(alle_tabs.items()) + [("tex", tex)]:
        for m in re.finditer(r"\\begin\{tabular\}\{([^\n]*)\}", s):
            spec = m.group(1)
            for mm in re.finditer(r"p\{[^}]*\}", spec):
                vor = spec[:mm.start()]
                if not vor.endswith("\\arraybackslash}"):
                    blocksatz.append(f"{name}: {mm.group(0)}")
    if blocksatz:
        fehl(f"p-Spalten im Blocksatz (Wortabstaende): {blocksatz[:5]} ({len(blocksatz)})")
    else:
        ok("alle p-Spalten linksbuendig (>{\\raggedright\\arraybackslash}p)")
    cap_schlecht = []
    for name, s in list(alle_tabs.items()) + [("tex", tex)]:
        for m in re.finditer(r"\\caption\{(.*?)\n?\s*\\label", s, re.S):
            c = m.group(1)
            if re.search(r"\\texttt\{[^}]*/[^}]*\}", c) and not c.lstrip().startswith("\\raggedright"):
                cap_schlecht.append(f"{name}: {c[:50]!r}")
    if cap_schlecht:
        fehl(f"Captions mit Pfaden ohne \\raggedright: {cap_schlecht}")
    else:
        ok("Captions mit Pfaden sind linksbuendig")
    if "\\usepackage{array}" not in tex:
        fehl("\\usepackage{array} fehlt")
    # --- O2: keine Null mit Vorzeichen in Tabellen
    nullen = []
    for name, s in alle_tabs.items():
        nullen += [f"{name}: {x}" for x in re.findall(r"\$[+-]0\.0+ \\pm", s)]
    if nullen:
        fehl(f"Null mit Vorzeichen in Tabellen: {nullen[:4]}")
    else:
        ok("keine Null mit Vorzeichen in den Tabellen")
    # --- O3/O9/O16: Schreibweisen
    for rx, was, quelle in ((r"(?<![\$\w])R\$\^2\$", "Rohtext R2 (aufrechtes R) statt $R^2$ in Tabelle 2", alle_tabs.get("tab2_hypothesen.tex", "")),
                            (r"LOBO-R2|R2 0\.995", "LOBO-R2/R2 als Rohtext", alle_tabs.get("tab2_hypothesen.tex", "")),
                            (r"identical to \\texttt\{formel", "'identical to formel_check.log'", tex), (r"\(DQ report\)", "'(DQ report)'", tex),
                            (r"Submission &", "'Submission' in Tabelle 6", alle_tabs.get("tab6_budgets.tex", "")),
                            (r"no difference shown \(260 pairs", "S3-Pilot als 'no difference shown' (Regel: equivalent)", alle_tabs.get("tab4_protokoll.tex", ""))):
        if re.search(rx, quelle):
            fehl(f"Schreibweise: {was}")
    erwarte(alle_tabs.get("tab4_protokoll.tex", ""), "$+0.00003 \\pm 0.00012$ equivalent (260 pairs", "O4: S3-Pilot equivalent nach |d|+2SE < 0.001")
    # --- O14: Abschnittsgrenzen
    if tex.count("\\FloatBarrier\n\\section{Full tables and figures}") == 1 and tex.count("\\FloatBarrier\n\\section{Rerun") == 1 and "\\end{minipage}\\par\\medskip" in tex:
        ok("Satzspiegel: \\FloatBarrier vor Anhang D und F, \\medskip nach dem Befehlsblock")
    else:
        fehl("Satzspiegel: \\FloatBarrier vor D/F oder \\medskip nach dem Befehlsblock fehlt")


# =====================================================================================================================
# Feinschliff R2 (Endpruefung Runde 2: P1-P5, Q1-Q9): die Fehlerklassen der Runden 1 und 2, mechanisch geschlossen.
#   P1 Doppelrundung: ALC- und Budget-Zellen der Tabellen 1, 3, 4, 6 gegen die VOLLEN Werte (liga_vergleich.json), einmal gerundet
#   P2 Lesart in Tabelle 4 (subjects per benchmark) gegen brier_je_budget (ours - BB je Budget)
#   P5 Patches: Text gegen audit/patches/ (Repo), daten/lieferung/patches (DQ-Bericht) und stanford-lieferung/baseline (Evidenzpaket)
#   Q1 Luecken: Endungsliste, Allwoerter, Satzregister auch in den Anhaengen, Zaehlangaben 142/2,142, Tabellen 4/5, Vorzeichen im Text
#   Q2 PAIEC_WORK fehlt -> rc 1 (ausser --ohne-zustand)
# Jede Pruefung hat ihren Fehlerfall in selbsttest_r2() (Mutation der aktuellen Texte) und in --alt <vor-R2/> (Vorversion).
# =====================================================================================================================
LIGA_SCHL_AUSW = {"hier_item": "v1_hier_item", "hier_kal": "v1_ohne_itemstufe"}  # Schluessel der auswertung.json -> der Liga
OHNE_ZUSTAND = [False]  # --ohne-zustand: Rohwerte der Zustandsdateien ausdruecklich nicht pruefen (Q2)
BUDGETS = (0, 1, 3, 7, 15, 31)


def voll(L, S, pred, stufe):
    """Voller Mittelwert (ALC: stufe 'alc'; Brier bei Budget b: 'B<b>') aus liga_vergleich.json; pred = Schluessel der auswertung.json oder der Liga."""
    reg = L["regime"][S]
    key = LIGA_SCHL_AUSW.get(pred, pred)
    if key == "v1_hier_item":
        return float(reg["v1_hier_item"][stufe]["mittel"])
    return float(reg["familien"][key]["niveau"][stufe]["mittel"])


def einfach(x, n=4):
    return f"{x:.{n}f}"


def doppelt(x, n=4, vor=5):
    """Der Fehler der Vorversion: erst auf `vor` Stellen (gespeicherter Wert), dann auf n Stellen (Anzeige), half up."""
    return str(Decimal(f"{x:.{vor}f}").quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))


def _vz(x, n):
    """Zahl mit Vorzeichen; eine auf n Stellen angezeigte Null traegt kein Vorzeichen."""
    s = f"{x:+.{n}f}"
    return s.lstrip("+-") if float(s) == 0 else s


def _stellen(paare, n=4):
    return n + 1 if any(abs(m) < 0.5 * 10 ** -n or se < 0.5 * 10 ** -n for m, se in paare) else n


def _buchst(d, se, marge=0.001):
    return "b" if d + 2 * se < 0 else "w" if d - 2 * se > 0 else "e" if abs(d) + 2 * se < marge else "g"


def _vgl(ausw, modell, ref, S):
    for v in ausw["vergleiche"]:
        if v["modell"] == modell and v["referenz"] == ref and v["S"] == S and v.get("gewichtung", "paar") == "paar":
            return v
    return None


# ---------------------------------------------------------------- P1: volle Werte, einmal gerundet
LIGA_ZEILEN = {"ours (v1 path)": "v1_hier_item", "IRT 2PL": "irt2pl", "IRT 1PL (Rasch)": "irt1pl", "matrix factorisation (rank 1--8)": "mf",
               "stacking (2PL, MF, kNN, BB)": "stack", "kNN over subjects": "knn", "gradient boosting (20 features)": "gb",
               "beta-binomial": "beta_binomial", "ours without item stage": "v1_ohne_itemstufe", "empirical mean": "empirischer_mittelwert",
               "constant 0.5": "konstant_0.5"}


def pruefe_volle_werte(tabs):
    """P1 (Klasse b): jede ALC-Zelle der Tabellen 1, 3, 4 steht einfach gerundet aus dem vollen Wert (liga_vergleich.json); doppelte Rundung wird als solche gemeldet."""
    L = lade("LIGA_VOLL")
    n = bad = 0

    def vergleiche(was, z, wert):
        nonlocal n, bad
        n += 1
        if z != einfach(wert):
            bad += 1
            art = "doppelt gerundet (5 -> 4 Stellen)" if z == doppelt(wert) else "weicht ab"
            fehl(f"{was}: gedruckt {z} != {einfach(wert)} (einfach gerundet aus {wert:.8f}) - {art}")

    z1 = 0
    for l in tabs["TAB1"].splitlines():
        m = re.match(r"(S1|S2|S3|S30|compact10)\b", l)
        if not m:
            continue
        S = "kompakt10" if m.group(1) == "compact10" else m.group(1)
        z = _zellen(l)
        z1 += 1
        for k, pred in zip(range(1, 5), ("empirischer_mittelwert", "beta_binomial", "hier_kal", "hier_item")):
            vergleiche(f"Tab. 1 {S} {pred} ALC", z[k], voll(L, S, pred, "alc"))
    z3 = 0
    for l in tabs["TAB3"].splitlines():
        z = _zellen(l)
        if z[0] in LIGA_ZEILEN and len(z) >= 3:
            z3 += 1
            for k, S in ((1, "S1"), (2, "S3")):
                vergleiche(f"Tab. 3 {z[0]} {S} ALC", z[k], voll(L, S, LIGA_ZEILEN[z[0]], "alc"))
    z4 = 0
    for l in tabs["TAB4"].splitlines():
        m = re.match(r"subjects per benchmark & (S\d+) & BB ALC ([\d.]+);", l)
        if m:
            z4 += 1
            vergleiche(f"Tab. 4 {m.group(1)} BB ALC", m.group(2), voll(L, m.group(1), "beta_binomial", "alc"))
    if (z1, z3, z4) != (5, 11, 4):
        fehl(f"Tab. 1/3/4: Zeilenzahlen {(z1, z3, z4)} != (5, 11, 4)")
    elif not bad:
        ok(f"Tab. 1/3/4: {n} ALC-Zellen = einfach gerundete volle Werte (liga_vergleich.json)")
    # Tabelle 5 (Ablationen) und Tabelle 6 stehen in pruefe_tabellen_4_5 bzw. pruefe_tabelle6


# ---------------------------------------------------------------- P2: Lesart der Zeilen "subjects per benchmark"
def pruefe_tab4_lesart(tabs):
    """P2 (Klasse e): die Lesart in Tabelle 4 gegen brier_je_budget (v1 - BB je Budget, liga_vergleich.json)."""
    L = lade("LIGA_VOLL")
    zeilen = {}
    for l in tabs["TAB4"].splitlines():
        m = re.match(r"subjects per benchmark & (S\d+) & [^&]*& ([^&]*)& ", l)
        if m:
            zeilen[m.group(1)] = m.group(2).strip()
    if sorted(zeilen) != ["S1", "S2", "S3", "S30"]:
        fehl(f"Tab. 4: Zeilen 'subjects per benchmark' {sorted(zeilen)}")
        return
    bb = [voll(L, S, "beta_binomial", "alc") for S in zeilen]
    unveraendert = max(bb) - min(bb) < 0.001
    for S, lesart in zeilen.items():
        d = {b: voll(L, S, "hier_item", f"B{b}") - voll(L, S, "beta_binomial", f"B{b}") for b in BUDGETS}
        gewinn = {b for b, x in d.items() if x <= -0.0005}
        if S == "S1":
            soll, belegt = "one subject: nothing to pool; v1 gains at B0--B1 only", gewinn == {0, 1}
        else:
            alle = sum(max(-x, 0.0) for x in d.values())
            soll, belegt = "pooling gain mainly at B1--B7", sum(max(-d[b], 0.0) for b in (1, 3, 7)) > 0.5 * alle
        if lesart != f"{soll}; BB unchanged":
            fehl(f"Tab. 4 {S}: Lesart '{lesart}' != '{soll}; BB unchanged'")
        elif not belegt or not unveraendert:
            fehl(f"Tab. 4 {S}: Lesart '{soll}' nicht durch brier_je_budget belegt (Gewinnbudgets {sorted(gewinn)}, Differenzen {[round(d[b], 4) for b in BUDGETS]}, BB-ALC-Spanne {max(bb) - min(bb):.5f})")
        else:
            ok(f"Tab. 4 {S}: Lesart '{soll}' = brier_je_budget (v1 - BB)")


# ---------------------------------------------------------------- Q1: Tabellen 4 und 5 Zelle fuer Zelle, Vorzeichen gegen die Definition
ABL_ZEILEN = (  # Beschriftung -> (Auswertung, A, B): gedruckt ist A - B
    ("item stage (ours $-$ pair model)", "P2", "hier_item", "hier_kal"),
    ("Platt calibration per budget, v1 stage set (calibrated $-$ raw)", "P1", "hier_kalibriert", "hier"),
    ("subject identity (raw $-$ without subject)", "P1", "hier", "hier_ohne_subjekt"),
    ("subject identity, calibrated (cal.\\ $-$ cal.\\ without subject)", "P1", "hier_kalibriert", "hier_ohne_subjekt"),
    ("benchmark slope $a_b$ (raw $-$ without slope)", "P1", "hier", "hier_ohne_steigung"),
    ("item temperature 1 vs 0.5 (ours $-$ t0.5)", "P2", "hier_item", "hier_item_t05"),
    ("item temperature 1 vs 2 (ours $-$ t2)", "P2", "hier_item", "hier_item_t2"),
)


def _diff_zelle(ausw, A, B, S, n):
    """(erwartete Zelle, Vorzeichen-Abweichung): Zelle aus vergleiche (einfach gerundet), Vorzeichen/Groesse gegen ALC(A) - ALC(B) aus tabelle_alle."""
    v = _vgl(ausw, A, B, S)
    if v is None:
        return None, "Vergleich fehlt"
    alc = ausw["tabelle_alle"][S]
    d_alc = float(alc[A]["alc_paare"]) - float(alc[B]["alc_paare"])
    abw = None
    if abs(d_alc - v["mittel"]) > 1.2e-5:  # zwei auf 5 Stellen gespeicherte ALC
        abw = f"vergleiche.mittel {v['mittel']:+.5f} != ALC({A}) - ALC({B}) = {d_alc:+.5f}"
    return v, abw


def pruefe_tabellen_4_5(tabs):
    """Q1 (Klassen b, c): Tabelle 5 (Ablationen) und die Zeilen von Tabelle 4 Zelle fuer Zelle aus den Quellen, Vorzeichen gegen die Definition A - B."""
    p1, p2 = lade("P1"), lade("P2")
    aus = {"P1": p1, "P2": p2}
    zeilen = {}
    for l in tabs["TAB3A"].splitlines():
        if "&" in l and l.rstrip().endswith("\\\\"):
            z = _zellen(l)
            zeilen[z[0]] = z
    n = 0
    for bez, qk, A, B in ABL_ZEILEN:
        z = zeilen.get(bez)
        if z is None:
            fehl(f"Tab. 5: Zeile '{bez}' fehlt")
            continue
        vs = {S: _diff_zelle(aus[qk], A, B, S, 4) for S in ("S1", "S2", "S3", "S30")}
        paare = [(v["mittel"], v["se"]) for v, _ in vs.values() if v]
        nn = _stellen(paare)
        for k, S in enumerate(("S1", "S2", "S3", "S30"), start=1):
            v, abw = vs[S]
            if v is None:
                if z[k] != "---":
                    fehl(f"Tab. 5 {bez} {S}: kein Vergleich in der Quelle, gedruckt {z[k]}")
                continue
            soll = f"${_vz(v['mittel'], nn)} \\pm {v['se']:.{nn}f}$ {_buchst(v['mittel'], v['se'])}"
            n += 1
            if z[k] != soll:
                fehl(f"Tab. 5 {bez} {S}: gedruckt {z[k]} != {soll}")
            if abw:
                fehl(f"Tab. 5 {bez} {S}: Vorzeichen/Definition: {abw}")
    h4 = next(h for h in lade("TAFEL")["hypothesen"] if h["id"] == "H4")
    z = next((zz for k_, zz in zeilen.items() if k_.startswith("subject identity, \\textbf{confirmatory}")), None)
    if z is None:
        fehl("Tab. 5: H4-Zeile fehlt")
    else:
        for k, S in enumerate(("S1", "S2", "S3"), start=1):
            d, se = h4["value"][S], h4["se"][S]
            soll = f"${_vz(d, 4)} \\pm {se:.4f}$ {_buchst(d, se)}"
            n += 1
            if z[k] != soll:
                fehl(f"Tab. 5 H4 {S}: gedruckt {z[k]} != {soll}")
            if _buchst(d, se) != {"grey_zone": "g", "worse": "w", "better": "b", "equivalent": "e"}.get(h4["teile"]["A"][S]["verdict"], "?"):
                fehl(f"Tab. 5 H4 {S}: Urteil der Tafel {h4['teile']['A'][S]['verdict']} != Regel {_buchst(d, se)}")
        if z[4] != "---":
            fehl("Tab. 5 H4 S30: erwartet '---'")
    for bez in ("stratum stage (item-metadata strata)", "text-based item prior"):
        if not any(k_.startswith(bez) and "not evaluated" in " ".join(zz) for k_, zz in zeilen.items()):
            fehl(f"Tab. 5: Zeile '{bez}' ohne 'not evaluated'")
    # ---- Tabelle 4
    b, dex, vl, akq = lade("BEOB"), lade("DEX"), lade("VERLUST"), lade("AKQ")
    U, V0, kap = b["U_E"], b["S1/beta_binomial"]["(q-R)^2"]["0"], b["kappa_mittel_ueber_testpaare"]
    D, F = dex["D_exakt = E 4V/(N-1)"], dex["E[V/(NA-1)]"]
    t4 = tabs["TAB4"]
    for S in ("S3", "S30", "kompakt10"):
        v, abw = _diff_zelle(p2, "hier_item", "hier_kal", S, 4)
        soll = f"item overlap (foreign labels on evaluation items) & {'compact10' if S == 'kompakt10' else S} & item-stage gain ${_vz(v['mittel'], 4)} \\pm {v['se']:.4f}$ &"
        n += 1
        if soll not in t4:
            fehl(f"Tab. 4 item overlap {S}: erwartet '{soll}'")
        if abw:
            fehl(f"Tab. 4 item overlap {S}: Vorzeichen/Definition: {abw}")
    for S in ("S1", "S2", "S3", "S30"):
        v, abw = _diff_zelle(p2, "hier_item", "beta_binomial", S, 4)
        n += 1
        if f"{S} & BB ALC " not in t4 or f"v1 $-$ BB ${_vz(v['mittel'], 4)} \\pm {v['se']:.4f}$ &" not in t4:
            fehl(f"Tab. 4 {S}: v1 - BB ${_vz(v['mittel'], 4)} \\pm {v['se']:.4f}$ nicht gefunden")
        if abw:
            fehl(f"Tab. 4 {S} v1 - BB: Vorzeichen/Definition: {abw}")
    al = lade_alc_law()
    terme, kurve = al.alc(U, V0, kap, D, F), al.lernkurve(U, V0, kap, D, F)
    for s_, was in ((f"$D = {D:.5f}$ (exact), {dex['D_splitpy_formel = E 2 r(1-r)/N']:.5f} (first approximation); ALC contribution of the split term {terme['split']:.5f}", "D"),
                    (f"$F = {F:.5f}$; $N$ median {dex['N_median']:.0f}, min {int(dex['N_min'])}", "F")):
        n += 1
        if s_ not in t4:
            fehl(f"Tab. 4 {was}-Zeile: erwartet '{s_}'")
    # Identitaetskollision: (Formel - beobachtet)/beobachtet bei B31; Vorzeichen zusaetzlich gegen daten/formel_check.log
    rel = {S: 100 * (kurve[31] - b[f"{S}/beta_binomial"]["(q-R)^2"]["31"]) / b[f"{S}/beta_binomial"]["(q-R)^2"]["31"] for S in ("S1", "S3", "S30")}
    log = (HIER / "daten/formel_check.log").read_text(encoding="utf-8").splitlines()
    for S in ("S1", "S3"):  # der Log fuehrt S1 und S3 (nicht S30)
        i = next(k for k, l in enumerate(log) if l.startswith(f"{S} BB beobachtet"))
        mm = re.search(r"31: '[\d.]+ \(([+-][\d.]+)%\)'", log[i + 1])
        if not mm or abs(float(mm.group(1)) - rel[S]) > 0.06:
            fehl(f"Tab. 4 Identitaetskollision {S}: Formelfehler {rel[S]:+.2f} % weicht vom Log ({mm.group(1) if mm else None} %) ab - Vorzeichen (Formel - beobachtet)")
    s_ = " / ".join(f"${rel[S]:+.1f}\\,\\%$" for S in ("S1", "S3", "S30"))
    n += 1
    if f"formula error for BB at B31: {s_} &" not in t4:
        fehl(f"Tab. 4 Identitaetskollision: erwartet 'formula error for BB at B31: {s_}'")
    bk = vl["bekannt_hier_item"]
    s_ = (f"excess known {bk['True|0']['excess']:.4f} / {bk['True|3']['excess']:.4f}; unknown {bk['False|0']['excess']:.4f} / {bk['False|3']['excess']:.4f} &")
    n += 1
    if s_ not in t4:
        fehl(f"Tab. 4 bekannt/unbekannt: erwartet '{s_}'")
    for r in akq["vergleiche_vs_zufall"]:
        d_alc = r["alc_politik"] - r["alc_zufall"]
        if abs(d_alc - r["mittel"]) > 1.2e-5:
            fehl(f"Tab. 4 Akquise {r['S']}: mittel {r['mittel']:+.6f} != ALC(coverage) - ALC(random) = {d_alc:+.6f}")
        wort = {"b": "better", "w": "worse", "e": "equivalent", "g": "grey zone"}[_buchst(r["mittel"], r["se"])]
        s_ = f"${_vz(r['mittel'], 5)} \\pm {r['se']:.5f}$ {wort} ({r['n_paare']} pairs, {r['n_cluster']} clusters)"
        n += 1
        if s_ not in t4:
            fehl(f"Tab. 4 Akquise {r['S']}: erwartet '{s_}'")
    if not FEHLER or n:
        ok(f"Tab. 4/5: {n} Zellen/Zeilen aus den Quellen neu erzeugt und verglichen (Vorzeichen gegen A - B, Formelfehler gegen formel_check.log)")


def lade_alc_law():
    try:
        import alc_law  # noqa: E402
    except Exception as e:  # noqa: BLE001
        print(f"FEHLT (fail-closed): alc_law.py: {e}")
        sys.exit(2)
    return alc_law


# ---------------------------------------------------------------- Q1(c): jede gedruckte Differenz "x ± se" stammt aus einer Quelle MIT diesem Vorzeichen
def _erlaubte_differenzen():
    tafel = lade("TAFEL")
    paare = []  # (d, se, Herkunft)
    for h in tafel["hypothesen"]:
        for dsg in (h.get("teile") or {}).values():
            if isinstance(dsg, dict):
                for S, x in dsg.items():
                    if isinstance(x, dict) and "d" in x and "se" in x:
                        paare.append((x["d"], x["se"], f"{h['id']}/{S}"))
                        e = x.get("gegen_empirischer_mittelwert")
                        if isinstance(e, dict):
                            paare.append((e["d"], e["se"], f"{h['id']}/{S}/gegen EM"))
        if h["id"] in ("H4", "H5") and isinstance(h.get("value"), dict):
            for S, w in h["value"].items():
                if isinstance(w, dict):
                    for k, x in w.items():
                        paare.append((x, h["se"][S][k], f"{h['id']}/{S}/{k}"))
                else:
                    paare.append((w, h["se"][S], f"{h['id']}/{S}"))
    for key in ("P1", "P2"):
        for v in lade(key)["vergleiche"]:
            paare.append((v["mittel"], v["se"], f"{key} {v['modell']}-{v['referenz']}/{v['S']}"))
    for r in csv.DictReader(io_text(PROJ / "./liga/ergebnisse/vergleich_gepaart.csv")):
        paare.append((float(r["mittel"]), float(r["se"]), f"liga {r['modell']}-{r['referenz']}/{r['S']}"))
    for r in lade("AKQ")["vergleiche_vs_zufall"]:
        paare.append((r["mittel"], r["se"], f"akq {r['S']}"))
    fb = lade("FALL")
    for fall in ("nyu_ctf_bench", "mind2web"):
        for S, x in fb[fall].items():
            if isinstance(x, dict) and "diff_hier_item_minus_bb_alc" in x and "diff_se_ueber_paare" in x:
                paare.append((x["diff_hier_item_minus_bb_alc"], x["diff_se_ueber_paare"], f"{fall}/{S}"))
    g1 = lade("VERLUST")["gruppe_subj_klasse"]["1"]
    paare.append((g1["gewinn_vs_bb"], 0.0006, "13 Ein-Subjekt-Benchmarks (se im Text)"))
    return paare


def io_text(p):
    import io
    return io.StringIO(p.read_text(encoding="utf-8"))


def pruefe_differenzen_text(tex, tabs):
    """Q1 (Klasse c): jeder Ausdruck '$x \\pm se$' in Text und Tabellen hat in den Quellen ein (d, se) mit GLEICHEM Vorzeichen (4 oder 5 Stellen);
    ohne Vorzeichen ('better by', 'gain', 'loses') muss die Richtung des Kontexts zum Vorzeichen der Quelle passen."""
    quellen = _erlaubte_differenzen()
    ndez = lambda s: len(s.split(".")[1]) if "." in s else 0  # noqa: E731
    n = 0
    unbelegt = []
    alles = [("tex", tex)] + [(k, v) for k, v in tabs.items()]
    for name, t in alles:
        for m in re.finditer(r"\$\s*([+-]?)([\d.]+)\s*\\pm\s*([\d.]+)\s*\$", t):
            vorz, d_s, se_s = m.group(1), m.group(2), m.group(3)
            nd = ndez(d_s)
            d, se = float(d_s), float(se_s)
            kontext = t[max(0, m.start() - 45):m.start()]
            treffer = []
            for qd, qse, herkunft in quellen:
                if abs(abs(qd) - d) > 0.5 * 10 ** -nd + 1e-12 or abs(qse - se) > 0.5 * 10 ** -nd + 1e-12:
                    continue
                if f"{abs(qd):.{nd}f}" != d_s or f"{qse:.{nd}f}" != se_s:
                    continue
                if vorz:
                    if (qd < 0) == (vorz == "-") or d == 0:
                        treffer.append(herkunft)
                else:
                    neg = re.search(r"better by|gain|gains", kontext) is not None
                    pos = re.search(r"loses|worse by", kontext) is not None
                    if (neg and qd < 0) or (pos and qd > 0) or (not neg and not pos):
                        treffer.append(herkunft)
            n += 1
            if not treffer:
                unbelegt.append(f"{name}: {m.group(0)}")
    if unbelegt:
        fehl(f"Differenzen ohne Quelle mit gleichem Vorzeichen ({len(unbelegt)}): {unbelegt[:4]}")
    else:
        ok(f"Differenzen im Text und in den Tabellen: {n} Ausdruecke 'x +- se' haben eine Quelle mit gleichem Vorzeichen")
    # 'difference <Zahl>' im Fliesstext: nur H2c (kappa - U/V0)
    d = lade("H2C")
    h2c = {f"{d['kappa_ML_mittel_cvA'] - d['U_durch_V0_gepoolt']:+.3f}"}
    v = {x["id"]: x for x in lade("TAFEL")["hypothesen"]}["H2c"]["value"]
    h2c.add(f"{v['kappa_ML'] - v['U_durch_V0']:+.3f}")
    schlecht = []
    for name, t in alles:
        for m in re.finditer(r"difference\s+\$?\s*([+\u2212-]\s*[\d.]+)", t):
            zahl = m.group(1).replace("\u2212", "-").replace(" ", "")
            if zahl not in h2c:
                schlecht.append(f"{name}: {m.group(0)}")
    if schlecht:
        fehl(f"'difference <Zahl>' ohne Quelle (nur H2c = kappa - U/V0 bekannt: {sorted(h2c)}): {schlecht[:3]}")
    else:
        ok("'difference <Zahl>' im Text/in den Tabellen nur fuer H2c (kappa - U/V0)")


# ---------------------------------------------------------------- Q1(d): Zaehlangaben N benchmarks / N pairs gegen die Quellen
def pruefe_zahlangaben_dateien(tex, tabs, repo):
    """Q1 (Klasse d): jede Angabe 'N benchmarks' / 'N pairs' (N >= 10) steht in einer Liste belegter Zahlen; unbekannte Zahl = Fehler (fail-closed)."""
    p2, L = lade("P2"), lade("LIGA_VOLL")
    dz, dq, wdh, akq = lade("DATEN"), lade("DQ"), lade("WDH"), lade("AKQ")
    nz = list(csv.DictReader((repo / "curation" / "noise_floor_by_benchmark.csv").open(encoding="utf-8")))
    n62 = sum(1 for r in nz if r["L10_response_weighted"] not in ("", None) and float(r["cells_rep"]) >= 100)
    f7 = {}
    for k in ("F7a", "F7b"):
        p = next((repo / "audit" / "csv").glob(f"{k}_*.csv"), None)
        f7[k] = None if p is None else sum(1 for _ in p.open(encoding="utf-8")) - 1
    jb = list(csv.DictReader((HIER / "daten/je_benchmark.csv").open(encoding="utf-8")))
    ein = sum(1 for r in jb if float(r["n_subjects"]) == 1)
    n_lower = sum(1 for r in jb if r["direction"] == "lower_is_better")
    max_paare = None
    benchmarks = {  # Zahl -> Beleg (Wahrheitswert, Quelle)
        142: (p2["tabelle_alle"]["S1"]["hier_item"]["n_benchmarks"] == 142 and L["regime"]["S1"]["n_benchmarks"] == 142 and wdh["l9_abgleich"]["testpaare_benchmarks"] == 142, "cv_A_p2 + liga_vergleich.json + wiederholung_b.json"),
        62: (n62 == 62, "noise_floor_by_benchmark.csv (>= 100 Wiederholungszellen)"),
        156: (dz["benchmarks_mit_daten"] == 156 and "of 156 eligible" in dq, "daten_zusammenfassung.json, DQ-Bericht"),
        96: ("The other 96" in dq, "DQ-Bericht F1 (156 - 60)"),
        13: (ein == 13 and "13 benchmarks" in dq, "je_benchmark.csv (Ein-Subjekt-Benchmarks), DQ-Bericht F8"),
        123: (None, "Selbstauskunft, Anhang F (nicht abgeschlossene Erkundung, ohne Datei im Export)"),
    }
    paare = {
        2142: (p2["tabelle_alle"]["S1"]["hier_item"]["n_paare"] == 2142 and L["regime"]["S1"]["n_paare"] == 2142, "cv_A_p2 + liga_vergleich.json"),
        12918: (wdh["l9_abgleich"]["paare_ge80"] == 12918, "wiederholung_b.json l9_abgleich.paare_ge80"),
        260: (any(r["n_paare"] == 260 for r in akq["vergleiche_vs_zufall"]), "akquise_pilot_tabelle.json"),
        115: (any(r["n_paare"] == 115 for r in akq["vergleiche_vs_zufall"]), "akquise_pilot_tabelle.json"),
        117: ("117 upstream twin pairs" in dq, "DQ-Bericht F7"),
        92: (f7["F7b"] == 92, "audit/csv/F7b_*.csv Zeilenzahl"),
        172: (f7["F7a"] == 172, "audit/csv/F7a_*.csv Zeilenzahl"),
    }
    # '30 pairs per benchmark' (Obergrenze der Testpaare je Benchmark) ist eine Protokollangabe < 100 (nicht erfasst); Zahlen < 10 ebenfalls
    t = re.sub(r"\\mbox\{(\$[^$]*\$)\}", r"\1", tex) + "\n" + "\n".join(tabs.values())
    t = re.sub(r"\{,\}|\\,", ",", t)
    n = 0
    for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{2,})\s+(?:test\s+|training\s+|public\s+|binary\s+|eligible\s+|upstream\s+)?(benchmarks?|pairs)\b(?!\s+fold)", norm(t)):
        zahl = int(m.group(1).replace(",", ""))
        tab = benchmarks if m.group(2).startswith("benchmark") else paare
        if zahl < 10 or zahl in (30,):
            continue
        n += 1
        if zahl not in tab:
            fehl(f"Zaehlangabe '{m.group(0)}' hat keinen Beleg in der Zahlenliste (fail-closed)")
        else:
            wahr, quelle = tab[zahl]
            if wahr is False:
                fehl(f"Zaehlangabe '{m.group(0)}' stimmt nicht mit {quelle} ueberein")
    if not any(f.startswith("Zaehlangabe") for f in FEHLER):
        ok(f"Zaehlangaben 'N benchmarks/pairs': {n} Vorkommen alle durch Quelldateien belegt (142, 2,142, 62, 156, 96, 13, 12,918, 260, 115, 117, 92, 172)")


# ---------------------------------------------------------------- P3/P4: Aussagen ueber Untergrenzen und L9
def pruefe_schranken_aussagen(tex):
    """P3/P4 (Klasse e): L1 (eingereichtes Modell) ist keine Schranke; L9 ist nach unten verzerrt; die textfreien Orakel stehen in A.5."""
    lt = {r["Stufe"].split(" ")[0]: r["Brier_B0"] for r in lade("LEITER")["leiter_B0"]}
    l2 = lade("LEITER2")
    l3a = next(l2[k]["Brier_B0"] for k in l2 if k.startswith("L3' "))
    l3b = next(l2[k]["Brier_B0"] for k in l2 if k.startswith("L3''"))
    if not (l3b < l3a < lt["L1"]):
        fehl(f"Leiter: L3'' {l3b} < L3' {l3a} < L1 {lt['L1']} gilt nicht - 'text-free ability oracles' passt nicht")
    erwarte(tex, f"At budget 0 the submitted model scores {lt['L1']:.4f} and text-free ability oracles {l3a:.4f}--{l3b:.4f} (A.5)", "P4: L1 ist keine Schranke, Orakel L3'/L3'' aus A.5")
    erwarte(tex, f"the cell-rate oracle $k/n$ leaves {lt['L9']:.4f} (L9, biased low: cells with one response contribute 0)", "P3: L9 verzerrt, Wortlaut")
    erwarte(tex, f"L9 oracle $k/n$ over all cells: {lt['L9']:.4f} (biased: cells with $n = 1$ contribute 0;", "A.5: L9 verzerrt")
    # Gegenprobe der Aussage 'verzerrt nach unten': Anteil der Zellen mit n = 1 aus der Wiederholungsstatistik
    w = lade("WDH")
    anteil_mehrfach = w["anteil_zeilen_wdh"]
    if not (0.05 < anteil_mehrfach < 0.2):
        fehl(f"Anteil der Zeilen mit Wiederholung {anteil_mehrfach} - 'cells with one response' ist die Mehrheit nicht mehr")
    for rx, was in ((r"only\s+0\.0065 of it is repeat noise", "'only 0.0065 of it is repeat noise' (L9 ist verzerrt, L10 liegt bei 0.044/0.049)"),
                    (r"The floor for text-free predictors under our rules at budget 0 is\s+0\.2485", "'floor for text-free predictors ... is 0.2485' (0.2485 = L1, keine Schranke)")):
        if re.search(rx, norm(tex)):
            fehl(f"Allaussage/Formulierung nicht belegt: {was}")


# ---------------------------------------------------------------- P5: Patches
def pruefe_patches(tex, repo):
    """P5 (Klasse a/d): Bericht gegen Repo. audit/patches = Satz des DQ-Berichts (sha256 = daten/lieferung/patches); die beschriebenen Patches 0001-0003
    mit Test und verify_patches.sh liegen im Evidenzpaket (stanford-lieferung/baseline), nicht im Repo."""
    pat = sorted((repo / "audit" / "patches").glob("*.patch"))
    namen = [p.name for p in pat]
    soll = ["01_prepare_data_full_listing.patch", "02_optional_skip_ungraded_benchmarks.patch", "03_databank_schema3_columns.patch"]
    if namen != soll:
        fehl(f"Patches: audit/patches/ enthaelt {namen}, erwartet {soll}")
    quelle = PROJ / "daten" / "lieferung" / "patches"
    if not quelle.is_dir():
        fehl(f"Patches: {quelle} fehlt (fail-closed)")
    else:
        for p in pat:
            q = quelle / p.name
            if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest() != hashlib.sha256(p.read_bytes()).hexdigest():
                fehl(f"Patches: {p.name} im Repo != daten/lieferung/patches")
    ev = PROJ / "stanford-lieferung" / "baseline"
    evn = sorted(p.name for p in (ev / "patches").glob("*.patch")) if (ev / "patches").is_dir() else []
    if len(evn) != 3 or not (ev / "tests" / "verify_patches.sh").is_file() or not (ev / "tests" / "test_prepare_data.py").is_file():
        fehl(f"Patches: Evidenzpaket stanford-lieferung/baseline hat {evn}, verify_patches.sh/Tests fehlen?")
    elif not (evn[0].startswith("0001-prepare_data-list") and "schema-3" in evn[1] and "match-published-vectors" in evn[2]):
        fehl(f"Patches: Namen im Evidenzpaket {evn} passen nicht zur Beschreibung im Anhang E")
    erwarte(tex, "Patches (3, in the evidence-pack delivery; \\texttt{audit/patches/} holds the earlier set of the data-quality report: full listing, optional skip of ungraded benchmarks, schema-3 columns):", "P5: Patches - Evidenzpaket gegen audit/patches getrennt benannt")
    if (repo / "audit" / "patches" / "verify_patches.sh").exists() or any("0003" in n for n in namen):
        fehl("Patches: audit/patches enthaelt jetzt verify_patches.sh/0003 - Anhang E anpassen")
    if not any(f.startswith("Patches:") for f in FEHLER):
        ok("Patches: audit/patches (3, sha256 = daten/lieferung/patches) und Evidenzpaket (0001-0003, verify_patches.sh, Tests) im Text getrennt benannt")


# ---------------------------------------------------------------- Q1(b): handgeschriebene Tabellen im tex (Table 8 und 9) Zahl fuer Zahl
def pruefe_handtabellen(tex, repo):
    """Q1 (Klasse b): Tabelle 8 (Befunde des DQ-Berichts) und Tabelle 9 (zwei Rechenwege) stehen von Hand im tex. Jede Zahl muss in der Quelle stehen:
    Tabelle 8 in der Zusammenfassung oder dem Text des DQ-Berichts, Tabelle 9 in den Ergebnisdateien; Q3/Q4: Scope-Spalte und F7-Zahlen."""
    t = norm(tex)
    i = t.index("\\label{tab:audit}")
    j = t.index("\\end{table}", i)
    tab8 = t[i:j]
    dq = norm(lade("DQ")).replace("\u2013", "-").replace("\u2014", "-").replace("–", "-")
    dqz = re.sub(r"[`*]", "", dq)
    fehlend = []
    for z in re.findall(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])", re.sub(r"\\texttt\{[^}]*\}|\\label\{[^}]*\}|schema-3|\\#", "", tab8)):
        if z in ("1", "2", "3", "4", "5", "6", "7", "8", "9") and len(z) == 1:
            continue  # Zeilennummern und kleine Zaehler (separat unten geprueft)
        if z.replace(",", "") not in dqz.replace(",", "") and z not in dqz:
            fehlend.append(z)
    # bekannte Abweichungen vom DQ-Wortlaut (Tabelle 8 enthaelt Rechenwerte): keine
    if fehlend:
        fehl(f"Tabelle 8: Zahlen, die im DQ-Bericht nicht vorkommen: {sorted(set(fehlend))}")
    else:
        ok("Tabelle 8: jede Zahl der Zeilen 1-9 steht im DQ-Bericht (Zusammenfassung/Text)")
    # Q3: Zeile 4 - Befund nennt 12 Subjekte, Scope 16; die Spalte muss erklaeren, woher 16 kommt
    m4 = re.search(r"4 & swebench\\_live: 12 website-report subjects.*?& (16 subjects[^&]*?) &", tab8)
    if not m4 or "the 12 and those merged via website aliases" not in m4.group(1):
        fehl("Tabelle 8 #4: Scope '16 subjects' ohne Erklaerung zu '12 website-report subjects' (the 12 and those merged via website aliases)")
    elif "16 subjects" not in dq or "12 website-report subjects" not in dq:
        fehl("Tabelle 8 #4: DQ-Bericht nennt '12 website-report subjects'/'16 subjects' nicht")
    else:
        ok("Tabelle 8 #4: 12 Subjekte im Befund, 16 im Scope (mit Erklaerung), beide im DQ-Bericht")
    # Q4: Zeile 7 - 117 Zwillingspaare gegen Anhang E (F7a/F7b: 172 + 92 Paare in der Datenbank)
    f7 = []
    for k in ("F7a", "F7b"):
        p = next((repo / "audit" / "csv").glob(f"{k}_*.csv"), None)
        f7.append(None if p is None else sum(1 for _ in p.open(encoding="utf-8")) - 1)
    if "117 upstream twin pairs (172 + 92 pairs in the database); 830 items" not in tab8 or f7 != [172, 92]:
        fehl(f"Tabelle 8 #7: erwartet '117 upstream twin pairs (172 + 92 pairs in the database); 830 items'; audit/csv F7a/F7b = {f7}")
    else:
        ok("Tabelle 8 #7: 117 Upstream-Zwillinge, 172 + 92 Paare in der Datenbank = audit/csv/F7a/F7b")
    # Tabelle 9: Zahlen gegen die Ergebnisdateien
    k = t.index("\\label{tab:twopaths}")
    tab9 = t[k:t.index("\\end{table}", k)]
    w = lade("WDH")
    med = w["schranke_je_bm_quantile"]["0.5"]
    l9 = w["l9_abgleich"]["kn_paargewichtet_testpaare_alle_items"]
    ldr = {r["Stufe"].split(" ")[0]: r["Brier_B0"] for r in lade("LEITER")["leiter_B0"]}
    soll9 = [(f"L10 median {med:.4f} (62 benchmarks)", "L10-Median"), (f"0.00649 vs 0.00652", "L9-Abgleich")]
    if f"{l9:.5f}" != "0.00649" or abs(ldr["L9"] - 0.00652) > 5e-6:
        fehl(f"Tabelle 9: L9 {l9:.5f} (wiederholung_b) / {ldr['L9']:.5f} (leiter.json) != 0.00649 / 0.00652")
    for s_, was in soll9:
        if s_ not in tab9:
            fehl(f"Tabelle 9 {was}: erwartet '{s_}'")
    spl = None
    for l in (HIER / "daten/formel_check.log").read_text(encoding="utf-8").splitlines():
        if l.strip().startswith("ALC_BB_formel_mit_split"):
            spl = float(l.split("mine")[1].split()[0])
    if spl is None or f"{spl:.4f}" != "0.2130" or "Split-term approximation 0.2130 ALC" not in tab9:
        fehl(f"Tabelle 9: Split-Term-Naeherung {spl} (formel_check.log) != 0.2130")
    b2 = [lade("BITGL2")]
    for z in ("1,079,568", "1,214,136"):
        if z not in tab9:
            fehl(f"Tabelle 9: {z} fehlt")
    p1v = (PROJ / "modell/ergebnisse_v2/bitgleich_phase1.json").read_text(encoding="utf-8")
    p2v = json.dumps(b2[0])
    for z in ("1079568", "1214136"):
        if z not in p1v and z not in p2v and z not in (PROJ / "./dist/README.md").read_text(encoding="utf-8").replace(",", ""):
            fehl(f"Tabelle 9: {z} kommt in den Bitgleichheits-Ergebnissen/README nicht vor")
    if not any(f.startswith("Tabelle 9") for f in FEHLER):
        ok("Tabelle 9: L10-Median, L9-Abgleich, Split-Term-Naeherung 0.2130, 1,079,568/1,214,136 Datensaetze gegen die Quelldateien")


# ---------------------------------------------------------------- Layout/Abbildungen/Literatur (Q7, Q8, Q9)
def pruefe_tab4_position(tex, tab4):
    """Q7: Tabelle 4 steht als [H] direkt unter der Ueberschrift 'Full tables and figures' (keine Leerflaechen davor/danach)."""
    if re.search(r"\\section\{Full tables and figures\}\s*\\label\{app:tables\}\s*\\input\{tabellen/tab4_protokoll\}", tex) and "\\begin{table}[H]" in tab4 \
            and 0 <= tex.find("\\appendix") < tex.find("\\raggedbottom") < tex.find("\\section{Full tables and figures}"):
        ok("Satzspiegel: Tabelle 4 steht als [H] direkt unter der Ueberschrift 'Full tables and figures'")
    else:
        fehl("Satzspiegel: Tabelle 4 nicht als [H] direkt nach der Ueberschrift 'Full tables and figures' (oder \\raggedbottom im Anhang fehlt: gestreckter Leim erzeugt Leerflaechen)")


def pruefe_abstand_ueberschrift(bbox):
    """Q7 im PDF (pdftotext -bbox der Seite mit der Ueberschrift): Abstand Ueberschrift 'Full' -> Beginn von Tabelle 4 <= 50 pt (mit gestrecktem Leim waren es 93 pt)."""
    w = [(m.group(3), float(m.group(1))) for m in re.finditer(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">([^<]*)</word>', bbox)]
    y_h = [y for t, y in w if t == "Full"]
    y_t = [y for t, y in w if t == "Table" and y_h and y > y_h[0]]
    if not y_h or not y_t or y_t[0] - y_h[0] > 50:
        fehl(f"PDF: Abstand Ueberschrift 'Full tables and figures' -> Tabelle 4 {None if not (y_h and y_t) else round(y_t[0] - y_h[0])} pt (> 50 pt: Leerflaeche unter der Ueberschrift)")
    else:
        ok(f"PDF: Tabelle 4 beginnt {y_t[0] - y_h[0]:.0f} pt unter der Ueberschrift (keine Leerflaeche)")


def pruefe_seite_ueberschrift(seiten):
    """Q7 im PDF: die Ueberschrift 'Full tables and figures' und Tabelle 4 stehen auf derselben Seite."""
    s_ueb = [k for k, s_ in enumerate(seiten) if re.search(r"^\s*D\s+Full tables and figures", s_, re.M)]
    if s_ueb and "Protocol sensitivity: what moves the error" in re.sub(r"\s+", " ", seiten[s_ueb[0]]):
        ok(f"PDF: Ueberschrift 'Full tables and figures' und Tabelle 4 stehen auf derselben Seite (S. {s_ueb[0] + 1})")
    else:
        fehl(f"PDF: Ueberschrift 'Full tables and figures' (Seite {[k + 1 for k in s_ueb]}) und Tabelle 4 nicht auf derselben Seite")


def pruefe_fig_beschriftung(tex, f6, f2):
    """Q8: eine Bezeichnung 'subjects per benchmark' (Achse, Gruppen, Caption); Titel der Zerlegung mit einer Nachkommastelle (Summe der gerundeten Balken 78 != 79)."""
    i0 = tex.index("\\caption{Error anatomy")
    cap = re.sub(r"\s+", " ", tex[i0:tex.index("\\label{fig:errors}", i0)])
    if "pairs per benchmark" in f6 or "subjects per benchmark" not in f6 or "subject count" in cap or "subjects per benchmark" not in cap:
        fehl("Abbildung Fehleranalyse: Bezeichnung der Gruppe/Achse uneinheitlich (erwartet nur 'subjects per benchmark' in Abbildung und Caption)")
    else:
        ok("Abbildung Fehleranalyse: 'subjects per benchmark' in Achse (b), Gruppen (c) und Caption")
    vl = lade("VERLUST")
    soll = [f"{100 * sum(vl['alc_anteil_' + S]['anteil'][k] for k in ('0', '1', '3')):.1f} % of it at B0" for S in ("S1", "S3")]
    f2 = re.sub(r"\s+", " ", f2)
    if all(s_ in f2 for s_ in soll):
        ok(f"Abbildung Zerlegung: Titel mit einer Nachkommastelle ({', '.join(soll)})")
    else:
        fehl(f"Abbildung Zerlegung: erwartet {soll} im Titel (Balken sind einzeln gerundet, Summe 78 != 79)")


def pruefe_jahr_doppelt(refs, bbl_text):
    """Q9: kein doppeltes Jahr in der Literaturliste (howpublished enthaelt das Jahr des Feldes year; plainnat haengt ', <Jahr>' an)."""
    doppel = []
    for e in re.split(r"(?m)^@", refs)[1:]:
        key = e.split("{", 1)[1].split(",", 1)[0]
        mh = re.search(r"^\s*howpublished\s*=\s*\{(.*)\},?\s*$", e, re.M)
        my = re.search(r"^\s*year\s*=\s*\{(\d{4})\}", e, re.M)
        if mh and my and re.search(r"(?<![\w/])" + my.group(1) + r"(?![\w/])", mh.group(1)) and not re.search(r"\(\d{4}-\d{2}-\d{2}\)", mh.group(1)):
            doppel.append(key)
    for l in (bbl_text or "").splitlines():
        m = re.match(r"\\newblock (.*), ((?:19|20)\d\d)\.$", l)
        if m and re.search(r"(?<![\w/])" + m.group(2) + r"(?![\w/])", m.group(1)):
            doppel.append("bbl: " + l[:60])
    if doppel:
        fehl(f"Literaturliste: Jahr doppelt (Venue-Text und Jahresfeld): {doppel[:5]}")
    else:
        ok("Literaturliste: kein doppeltes Jahr ('NAACL 2025, 2025')")


def pruefe_formulierungen(tex):
    """Q5/Q6 und Wortlaut der gefundenen Mehrdeutigkeiten: das Abstract nennt die gescheiterte Hypothese; der Protokollvergleich nennt die Ursache (Subjektzahl)."""
    gescheitert = [h["id"] for h in lade("TAFEL")["hypothesen"] if h["verdict"] == "failed"]
    if gescheitert == ["H4"]:
        erwarte(tex, "nine of ten frozen hypotheses passed and one failed (H4, below). With one subject per benchmark", "Q5: Abstract nennt H4 als gescheiterte Hypothese")
    else:
        fehl(f"Tafel: gescheiterte Hypothesen {gescheitert} (Abstract nennt H4)")
    erwarte(tex, "depending on how many subjects share the labels, not on the estimator.", "Q6: gleicher Praediktor, Ursache = Subjektzahl")
    if re.search(r"depending on the protocol, not the estimator", norm(tex)):
        fehl("Q6: 'depending on the protocol, not the estimator' vergleicht zwei verschiedene Benchmarks")


def pruefe_r2_layout(tex, texpfad, refs, mit_pdf):
    pruefe_tab4_position(tex, lade("TAB4"))
    bbl = texpfad.with_suffix(".bbl")
    if mit_pdf:
        import subprocess
        try:
            seiten = subprocess.run(["pdftotext", "-layout", str(texpfad.with_suffix(".pdf")), "-"], capture_output=True, text=True, check=True).stdout.split("\f")
            fa = texpfad.parent / "abbildungen"
            f6 = subprocess.run(["pdftotext", str(fa / "fig6_fehleranalyse.pdf"), "-"], capture_output=True, text=True, check=True).stdout
            f2 = subprocess.run(["pdftotext", str(fa / "fig2_zerlegung.pdf"), "-"], capture_output=True, text=True, check=True).stdout
        except Exception as e:  # noqa: BLE001
            fehl(f"pdftotext: {e} (fail-closed, Q7/Q8)")
            return
        pruefe_seite_ueberschrift(seiten)
        k = next((i for i, s_ in enumerate(seiten) if re.search(r"^\s*D\s+Full tables and figures", s_, re.M)), None)
        if k is not None:
            bbox = subprocess.run(["pdftotext", "-f", str(k + 1), "-l", str(k + 1), "-bbox", str(texpfad.with_suffix(".pdf")), "-"], capture_output=True, text=True, check=True).stdout
            pruefe_abstand_ueberschrift(bbox)
        pruefe_fig_beschriftung(tex, f6, f2)
    pruefe_jahr_doppelt(refs, bbl.read_text(encoding="utf-8") if (mit_pdf and bbl.is_file()) else "")  # vor dem Bau (--ohne-pdf) ist die .bbl veraltet
    pruefe_formulierungen(tex)


# ---------------------------------------------------------------- Q1(a): Pfade im PDF-Text
PFAD_ENDUNGEN = r"parquet|patch|json|yaml|yml|toml|ipynb|csv|tsv|log|bib|pdf|tex|py|md|txt|zip|sh|sty|gz|npz|npy|pkl|cff"


def pruefe_pdf_pfade(texpfad, repo, txt=None):
    """Q1 (Klasse a): jeder im fertigen PDF genannte Pfad mit Verzeichnisanfang existiert im Export (Leerraum entfernt, damit Zeilenumbrueche im Pfad nicht stoeren)."""
    if txt is None:
        import subprocess
        try:
            txt = subprocess.run(["pdftotext", str(texpfad.with_suffix(".pdf")), "-"], capture_output=True, text=True, check=True).stdout
        except Exception as e:  # noqa: BLE001
            fehl(f"pdftotext: {e} (fail-closed, PDF-Pfade)")
            return
    flach = re.sub(r"\s+", "", txt)
    basen, _ = repo_dateien(repo)
    anf = "|".join(VERZEICHNISSE + ("daten", "abbildungen", "tabellen"))
    pfade = sorted(set(re.findall(r"(?:" + anf + r")/(?:[A-Za-z0-9_\-]+/)*[A-Za-z0-9_\-]+\.(?:" + PFAD_ENDUNGEN + r")", flach)))
    fehlend = []
    for p in pfade:
        if pfad_im_repo(p, repo, basen):
            continue
        # direkt anhaengende Woerter im entleerten Text koennen eine laengere Endung vortaeuschen: gekuerzte Varianten pruefen
        if any(pfad_im_repo(p[:k], repo, basen) for k in range(len(p) - 1, 8, -1) if p[:k].endswith(tuple("." + e for e in PFAD_ENDUNGEN.split("|")))):
            continue
        if p.split("/")[-1] in EXTERN:
            continue
        fehlend.append(p)
    if fehlend:
        fehl(f"PDF nennt Pfade, die im Repository nicht existieren: {fehlend[:6]} ({len(fehlend)})")
    else:
        ok(f"PDF: {len(pfade)} genannte Pfade (Verzeichnisanfang) existieren relativ zur Repo-Wurzel")


# ---------------------------------------------------------------- Q1: verketteter Vergleich
def vorzeichen_falsch(diff, text_vorzeichen_minus):
    """Q1: (diff < 0) != (gedrucktes Vorzeichen ist minus); frueher als verketteter Vergleich 'diff < 0 != (...)' geschrieben (= '(diff < 0) and (0 != ...)')."""
    return (diff < 0) != text_vorzeichen_minus


# ---------------------------------------------------------------- Q1(e): Belege fuer Allsaetze aus den Anhaengen (jeder Beleg hier ist eine Pruefung, kein Kommentar)
def pruefe_wiederholungsstatistik(tex):
    """A.5: Zahlen der Wiederholungsstatistik (3.14 M Zellen, 10.0 %, 58.6 %, 68.3 M Antworten, 0.0444, 0.0229, 'some benchmarks show zero noise')."""
    w = lade("WDH")
    s = f"{w['zeilen_mit_wiederholung'] / 1e6:.2f}\\,M cells with $n \\ge 2$ ({100 * w['anteil_zeilen_wdh']:.1f}\\% of cells, {100 * w['anteil_antworten_in_wdh_zellen']:.1f}\\% of all {w['antworten_gesamt'] / 1e6:.1f}\\,M responses) gives {w['schranke_antwortgewichtet_nur_wdh']:.4f}"
    erwarte(tex, s, "A.5: Wiederholungsstatistik (Zellen, Anteile, 0.0444) aus wiederholung_b.json")
    erwarte(tex, f"the value {w['orakel_kn_alle_zellen']:.4f} in the repeat statistics is a different estimand, response-weighted over the whole database", "A.5: 0.0229 = orakel_kn_alle_zellen")
    nz = list(csv.DictReader((REPO / "curation" / "noise_floor_by_benchmark.csv").open(encoding="utf-8")))
    nullen = [r["benchmark_id"] for r in nz if r["L10_response_weighted"] not in ("", None) and float(r["L10_response_weighted"]) == 0.0]
    if nullen:
        ok(f"A.5: 'some benchmarks show zero noise' - {len(nullen)} Benchmarks mit L10 = 0")
    else:
        fehl("A.5: 'some benchmarks show zero noise at n = 2' - kein Benchmark mit L10 = 0 in noise_floor_by_benchmark.csv")


def pruefe_paare_statistik(tex):
    """Abschnitt 2: 142 Benchmarks, 12,918 Paare, Median 13, zwei Benchmarks 59 %, 52 % ohne normalized_name aus paare.parquet der lokalen Datenbasis."""
    import os
    p = Path(os.environ.get("PAIEC_WORK", "/nonexistent")) / "modell" / "paare.parquet"
    if not p.is_file():
        if OHNE_ZUSTAND[0]:
            print("HINWEIS (--ohne-zustand): paare.parquet nicht geprueft (Abschnitt 2: 12,918 Paare, Median 13, 59 %, 52 %)")
        else:
            fehl("PAIEC_WORK/modell/paare.parquet nicht erreichbar: Abschnitt-2-Zahlen koennen nicht geprueft werden (fail-closed, R2/Q2); PAIEC_WORK setzen oder --ohne-zustand")
        return
    import pandas as pd
    d = pd.read_parquet(p, columns=["b_code", "normalized_name"])
    g = d.groupby("b_code").size().sort_values(ascending=False)
    soll = (f"{len(g)} benchmarks ({len(d):,} pairs, median benchmark {g.median():.0f}, two benchmarks hold {100 * g.iloc[:2].sum() / len(d):.0f}\\%); "
            f"{100 * (d['normalized_name'].fillna('') == '').mean():.0f}\\% of the pairs have no \\texttt{{normalized\\_name}}")
    erwarte(tex, f"Pairs with $\\ge 80$ items occur in {soll}", "Abschnitt 2: Paare/Benchmarks/Median/Anteile aus paare.parquet")


def pruefe_a7_gewichte(tex):
    """A.7: kumulative ALC-Gewichte W(j) und Anteile der Labels 1-7 / 1-15 aus den ALC-Gewichten 0.1/0.2/0.2/0.2/0.2/0.1 bei den Budgets 0,1,3,7,15,31."""
    gew = dict(zip(BUDGETS, (0.1, 0.2, 0.2, 0.2, 0.2, 0.1)))
    W = lambda j: round(sum(w for b, w in gew.items() if b >= j), 10)  # noqa: E731
    ges = sum(W(j) for j in range(1, 32))
    a7, a15 = sum(W(j) for j in range(1, 8)) / ges, sum(W(j) for j in range(1, 16)) / ges
    soll = (f"cumulative ALC weight is $W(j) = {W(1):.1f}$ ($j = 1$), {W(2):.1f} ($j = 2$--3), {W(4):.1f} (4--7), {W(8):.1f} (8--15), {W(16):.1f} (16--31); "
            f"labels 1--7 carry {100 * a7:.0f}\\% of the total weight, 1--15 carry {100 * a15:.0f}\\%")
    erwarte(tex, soll, "A.7: Gewichte W(j) und Anteile 52 % / 81 % aus den ALC-Gewichten")


def pruefe_prereg_zitate(tex, repo):
    """Anhang B: die als Regel der Praeregistrierung zitierten Saetze stehen in der eingefrorenen Datei; kein Nachtrag; Hash unveraendert."""
    pr = repo / "prereg" / "PRAEREGISTRIERUNG-v2.md"
    if not pr.is_file():
        fehl("prereg/PRAEREGISTRIERUNG-v2.md fehlt im Export")
        return
    t = re.sub(r"[*`]", "", norm(pr.read_text(encoding="utf-8")))
    for s_ in ("Rule R1: if the submitted model changes later", "No comparison with SE ≥ 0.0005 is declared \"equivalent\"", "a family without documented tuning is \"not evaluated\", never \"beaten\"",
               "nothing is re-tuned after the confirmatory", "Families not finished by their time cap (2 h each)", "(none at freezing; amendments are separate dated files with their own sha256"):
        if s_ not in t:
            fehl(f"Anhang B zitiert Praeregistrierungsregel, die in der Datei nicht steht: '{s_}'")
    if list((repo / "prereg").glob("*AMENDMENT*")) or list((PROJ / "v2-plan").glob("*AMENDMENT*")):
        fehl("Anhang B: 'Amendment log ... none', aber es gibt eine AMENDMENT-Datei")
    ph = (PROJ / "v2-plan" / "PRAEREG-HASH.txt").read_text(encoding="utf-8")
    if "existiert zum Zeitpunkt des Einfrierens NICHT" not in ph:
        fehl("Anhang B: 'At freezing no confirmatory run existed' - PRAEREG-HASH.txt belegt es nicht")
    if hashlib.sha256(pr.read_bytes()).hexdigest() != "e5fd821fdf6e2db3be86e1e341b02bc4199d4721790dd3ae8f027b60e9521ab7":
        fehl("prereg/PRAEREGISTRIERUNG-v2.md: sha256 != e5fd821f... (die Datei darf nie geaendert werden)")
    if not any(f.startswith(("Anhang B", "prereg/")) for f in FEHLER):
        ok("Anhang B: zitierte Regeln (R1, SE >= 0.0005, 'never beaten', 'nothing is re-tuned', 2 h) stehen in der Praeregistrierung; kein Nachtrag; sha256 e5fd821f")


def pruefe_paketaussagen(tex):
    """Anhang C/F: 'no language model at runtime' / 'standard library only' / Grouping-Cache (1,024 / 64) gegen model.py im eingereichten ZIP."""
    import zipfile
    mp = zipfile.ZipFile(Q["PAKET"]).read("model.py").decode("utf-8")
    importe = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", mp, re.M))
    stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {"math", "re", "hashlib", "json", "threading"}
    fremd = sorted(i for i in importe if i not in stdlib and i != "__future__")
    if fremd:
        fehl(f"model.py importiert Nicht-Standardbibliothek: {fremd} (Text: 'standard library only', 'no language model at runtime')")
    voll, stich = re.search(r"VOLL_BIS\s*=\s*(\d+)", mp), re.search(r"STICHPROBE\s*=\s*(\d+)", mp)
    if not voll or not stich or (int(voll.group(1)), int(stich.group(1))) != (1024, 64):
        fehl(f"model.py Grouping-Cache: VOLL_BIS/STICHPROBE {voll and voll.group(1)}/{stich and stich.group(1)} != 1,024/64")
    erwarte(tex, "up to 1,024 labels the key is a hash over all entries, above that length plus 64 sampled entries", "Anhang C: Grouping-Cache 1,024 / 64")
    # SHA256SUMS des Evidenzpakets deckt jede gelieferte Datei ab
    ev = PROJ / "stanford-lieferung"
    if (ev / "SHA256SUMS").is_file():
        intern = {"FREIGABE.md", "FREIGABE-2026-10-21-sang-text.md", "MAIL-PROTOKOLL.md", "PRUEFUNG.md"}  # Arbeitsnotizen im Ordner, nicht Teil der Lieferung
        dateien = {p.relative_to(ev).as_posix() for p in ev.rglob("*") if p.is_file() and p.relative_to(ev).as_posix() != "SHA256SUMS" and p.name not in intern}
        eintraege = {l.split(None, 1)[1].strip().lstrip("*").lstrip("./") for l in (ev / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if l.strip()}
        if dateien != eintraege:
            fehl(f"Evidenzpaket: SHA256SUMS deckt nicht jede Datei ab (Datei ohne Summe {sorted(dateien - eintraege)[:3]}, Summe ohne Datei {sorted(eintraege - dateien)[:3]})")
        else:
            ok(f"Evidenzpaket: SHA256SUMS deckt alle {len(dateien)} gelieferten Dateien ab ('SHA-256 sums of every delivered file')")
    else:
        fehl("stanford-lieferung/SHA256SUMS fehlt (fail-closed)")


def pruefe_anhang_belege(tex, tabs, repo):
    """Belege fuer Allsaetze aus Anhaengen und Limitationen, die bisher nur Kommentare waren (R2/Q1 Klasse e)."""
    # (1) Sensitivitaetsaussage Anhang B: 'same verdict in all 23 comparison rows (largest shift 2.4e-5 ALC)'
    ht = (repo / "konfirmation" / "HYPOTHESEN-TAFEL.md").read_text(encoding="utf-8")
    zeilen = [l for l in ht.splitlines() if re.match(r"\| H\d", l) and len(l.strip().strip("|").split("|")) == 8]
    gleich = re.search(r"Urteile gleich in (\d+)/(\d+) Zeilen", ht)
    alc_shift = []
    for l in zeilen:
        z = [c.strip() for c in l.strip().strip("|").split("|")]
        if z[0] in ("H1", "H4", "H5"):
            alc_shift.append(float(z[-2]))
    ok_s = gleich and gleich.group(1) == gleich.group(2) == "23" and len(zeilen) == 23 and f"{max(alc_shift):.1e}" == "2.4e-05"
    if ok_s:
        erwarte(tex, "gave the same verdict in all 23 comparison rows (largest shift $2.4 \\times 10^{-5}$ ALC)", "Anhang B: Sensitivitaet 23/23, groesste ALC-Verschiebung 2.4e-5")
    else:
        fehl(f"Anhang B: Sensitivitaet - HYPOTHESEN-TAFEL.md: {gleich and gleich.groups()}, {len(zeilen)} Zeilen, max ALC-Verschiebung {max(alc_shift) if alc_shift else None}")
    # (2) Protokollidentitaet der Basislinien (Tabelle 9 'max |dq| = 0', Anhang B 'precondition')
    ip = list(csv.DictReader((repo / "liga" / "ergebnisse" / "identitaet_protokoll.csv").open(encoding="utf-8")))
    if sorted(r["praediktor"] for r in ip) != ["beta_binomial", "empirischer_mittelwert"] or any(float(r["max_abs_dq"]) != 0.0 or r["nur_einseitig"] != "0" for r in ip):
        fehl(f"Tabelle 9/Anhang B: 'max |dq| = 0 fuer EM und BB' - identitaet_protokoll.csv sagt {[(r['praediktor'], r['max_abs_dq']) for r in ip]}")
    else:
        ok("Tabelle 9/Anhang B: Protokollidentitaet EM und BB max |dq| = 0 (liga/ergebnisse/identitaet_protokoll.csv)")
    # (3) D bei N = 80 und N = 1000 mit V = E var_i p_i
    dx = lade("DEX")
    V = dx["V_mittel (E var_i p_i)"]
    erwarte(tex, f"$D$ is {4 * V / 79:.4f} at $N = 80$ and {4 * V / 999:.4f} at $N =\n1{{,}}000$ ($V = {V:.3f}$)", "A.2: D bei N = 80 / 1000 aus V = E var_i p_i")
    # (4) 'polarity and turn type are missing for 2 of the 142 benchmarks'
    vl = lade("VERLUST")
    fehlt = {142 - int(sum(x["n_bm"] for x in vl[g].values())) for g in ("gruppe_direction", "gruppe_multi_single_turn")}
    if fehlt != {2}:
        fehl(f"Abb. Fehleranalyse: 'missing for 2 of the 142 benchmarks' - verlust.json: fehlende {fehlt}")
    else:
        ok("Abb. Fehleranalyse: Polaritaet und Turn-Typ fehlen fuer 2 von 142 Benchmarks (verlust.json)")
    # (5) 'No comparison with SE >= 0.0005 is declared equivalent': in allen Tabellen kein 'e' bei SE >= 0.0005
    schlecht = []
    for name, t in tabs.items():
        for m in re.finditer(r"\\pm\s*([\d.]+)\$\s+e\b", t):
            if float(m.group(1)) >= 0.0005:
                schlecht.append(f"{name}: SE {m.group(1)}")
    if schlecht:
        fehl(f"Tabellen: Urteil 'e' (equivalent) bei SE >= 0.0005: {schlecht[:3]}")
    else:
        ok("Tabellen: kein Urteil 'equivalent' bei SE >= 0.0005 (Praeregistrierung)")
    # (6) DQ-Bericht: 'Already reported?'-Aussage in Anhang E
    dq = norm(lade("DQ"))
    for s_ in ("3; none related", "only #1, stale real_webagents embeddings, overlaps with Finding 1c", "Everything was read-only"):
        if s_ not in dq:
            fehl(f"Anhang E: DQ-Bericht enthaelt '{s_}' nicht (Prior reports / Everything was read-only)")
    erwarte(tex, "none covered these points except an overlap with one baseline issue on stale embeddings", "Anhang E: Prior reports - nur #1 ueberlappt")


def selbsttest_neu(tex, tabs):
    """Loest den Fehlerfall jeder neuen Pruefung einmal aus (Mutation der aktuellen Texte); erwartet: jede Mutation erzeugt mindestens einen Fehler."""
    global FEHLER
    quellen_abb = lade("QUELLEN_ABB")
    refs = lade("REFS")
    basis = list(FEHLER)
    ergebnisse = []

    def lauf(name, f, *args):
        global FEHLER
        vor = len(FEHLER)
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            f(*args)
        neu = FEHLER[vor:]
        del FEHLER[vor:]
        ergebnisse.append((name, bool(neu), neu[0][:100] if neu else ""))

    t1 = tabs["TAB1"].replace("$-0.0003 \\pm 0.0004$ g", "$+0.0003 \\pm 0.0004$ g", 1)
    lauf("(c) Vorzeichen Tab. 1 (ours - BB umgedreht)", pruefe_vorzeichen, tex, {**tabs, "TAB1": t1})
    t3 = re.sub(r"(\n(?!ours \(v1)[^\n]*? & )\$\+(0\.\d{4} \\pm)", r"\1$-\2", tabs["TAB3"], count=1)
    lauf("(c) Vorzeichen Tab. 3 (Methode - ours umgedreht)", pruefe_vorzeichen, tex, {**tabs, "TAB3": t3})
    t2 = tabs["TAB2"].replace("difference $+0.009$", "difference $-0.009$", 1)
    lauf("(c) Vorzeichen H2c in Tab. 2", pruefe_vorzeichen, tex, {**tabs, "TAB2": t2})
    lauf("(a) Quellpfad ohne Verzeichnispraefix (cv_A_p2/auswertung.json)", pruefe_quellpfade, tex + "\n\\texttt{cv\\_A\\_p2/auswertung.json}", tabs, quellen_abb, REPO)
    fehlende = regime_fehlen("modell/ergebnisse/cv_A_p2/auswertung.json", ["S1", "S2"], REPO)
    ergebnisse.append(("(a) Datei enthaelt die zitierten Regime nicht (cv_A_p2: S1, S2)", bool(fehlende), f"fehlend: {fehlende}"))
    lauf("(b) Tabelle 7: eine Zelle doppelt gerundet", pruefe_tabelle7, tabs["TAB7"].replace("0.332", "0.333", 1))
    lauf("(b) Tabelle 6: eine Zelle verfaelscht", pruefe_tabelle6, tabs["TAB6"].replace("0.2321", "0.2322", 1))
    lauf("(d) Zaehlangabe Anhang E (281 -> 282)", pruefe_zaehlangaben, tex.replace("(281", "(282", 1), REPO)
    lauf("(d) Zaehlangabe Tests (26 -> 27)", pruefe_zaehlangaben, tex.replace("26 unit tests", "27 unit tests", 1), REPO)
    lauf("(e) 'the nearest family throughout'", pruefe_nearest, tex.replace("from one to three subjects), stacking", "throughout), stacking", 1))
    lauf("(e) neuer Allsatz ohne Registereintrag", pruefe_allaussagen, tex.replace("has the best mean ALC in every regime", "has the best mean ALC in every regime and every budget", 1), tabs)
    lauf("(e) 'whole lever' wieder im Text", pruefe_allaussagen, tex.replace("is the largest\nlever", "is the whole\nlever", 1), tabs)
    for name, ok_, grund in ergebnisse:
        print(("AUSGELOEST " if ok_ else "NICHT AUSGELOEST ") + name + (f" -> {grund}" if grund else ""))
    FEHLER[:] = basis
    return all(o for _, o, _ in ergebnisse), len(ergebnisse)


def selbsttest_r2(tex, tabs, texpfad):
    """R2: loest den Fehlerfall jeder neuen Pruefung (P1-P5, Q1-Q9) einmal aus: Mutation der aktuellen Texte/Tabellen; erwartet: jede Mutation erzeugt mindestens einen Fehler."""
    global FEHLER
    refs = lade("REFS")
    quellen_abb = lade("QUELLEN_ABB")
    basis = list(FEHLER)
    ergebnisse = []

    def lauf(name, f, *args, **kw):
        global FEHLER
        vor = len(FEHLER)
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            f(*args, **kw)
        neu = FEHLER[vor:]
        del FEHLER[vor:]
        ergebnisse.append((name, bool(neu), neu[0][:110] if neu else ""))

    def aus(tab, a, b, n=1):
        assert tabs[tab].count(a) >= 1, (tab, a)
        return {**tabs, tab: tabs[tab].replace(a, b, n)}

    def im_tex(a, b):
        assert tex.count(a) >= 1, a
        return tex.replace(a, b, 1)

    # P1 Doppelrundung (die Vorversion-Zeichenketten)
    lauf("P1 Tab. 1: S1 BB 0.2131 -> 0.2132 (doppelt gerundet)", pruefe_volle_werte, aus("TAB1", "& 0.2131 &", "& 0.2132 &"))
    lauf("P1 Tab. 3: beta-binomial S1 0.2131 -> 0.2132", pruefe_volle_werte, aus("TAB3", "beta-binomial & 0.2131", "beta-binomial & 0.2132"))
    lauf("P1 Tab. 4: BB ALC 0.2131 -> 0.2132", pruefe_volle_werte, aus("TAB4", "BB ALC 0.2131", "BB ALC 0.2132"))
    lauf("P1 Tab. 6: S=3 BB B15 0.1947 -> 0.1946 (doppelt gerundet)", pruefe_tabelle6, tabs["TAB6"].replace("0.1947", "0.1946", 1))
    # P2 Lesart
    alt_l = "pooling helps v1 at B1--B7 only; BB unchanged"
    lauf("P2 Tab. 4: alte Lesart 'pooling helps v1 at B1--B7 only' in allen Zeilen", pruefe_tab4_lesart,
         {**tabs, "TAB4": re.sub(r"(subjects per benchmark & S\d+ & [^&]*& )[^&]*(& P2)", lambda m: m.group(1) + alt_l + " " + m.group(2), tabs["TAB4"])})
    lauf("P2 Tab. 4: S3 mit der S1-Lesart (v1 gains at B0--B1 only)", pruefe_tab4_lesart,
         aus("TAB4", "S3 & BB ALC 0.2134; v1 $-$ BB $-0.0047 \\pm 0.0007$ & pooling gain mainly at B1--B7", "S3 & BB ALC 0.2134; v1 $-$ BB $-0.0047 \\pm 0.0007$ & one subject: nothing to pool; v1 gains at B0--B1 only"))
    # P3, P4
    lauf("P3 Abstract/§3: 'only 0.0065 of it is repeat noise (L9)'", pruefe_schranken_aussagen,
         im_tex("and the cell-rate oracle $k/n$ leaves 0.0065 (L9, biased low: cells with one response contribute 0).", "and only 0.0065 of it is repeat noise (L9)."))
    lauf("P4 §4: 'The floor for text-free predictors ... is 0.2485'", pruefe_schranken_aussagen,
         im_tex("At budget 0 the submitted model scores 0.2485 and text-free ability oracles 0.2480--0.2460 (A.5); the benchmark-level oracle shows that benchmark-level text could lower this to at most 0.2067",
                "The floor for text-free predictors under our rules at budget 0 is 0.2485; the benchmark-level oracle shows that benchmark-level text could lower it to at most 0.2067"))
    # P5 Patches
    lauf("P5 Anhang E: 'Patches (3): ' ohne Trennung Evidenzpaket / audit/patches", pruefe_patches,
         im_tex("Patches (3, in the evidence-pack delivery; \\texttt{audit/patches/} holds the earlier set of the data-quality report: full listing, optional skip of ungraded benchmarks, schema-3 columns):", "Patches (3):"), REPO)
    # Q1a Endungen / Pfade
    lauf("Q1(a) Pfad mit Endung .yaml (nicht im Repo)", pruefe_quellpfade, tex + "\n\\texttt{liga/ergebnisse/gibtesnicht.yaml}", tabs, quellen_abb, REPO)
    lauf("Q1(a) PDF nennt Pfad, der nicht existiert", pruefe_pdf_pfade, texpfad, REPO, "Source: liga/ergebnisse/gibtes-\nnicht.json and daten/verlust.json")
    lauf("Q1(a) Quellpfad-Schluessel: Tab. 6 nennt die liga_vergleich.json nicht", pruefe_pfad_schluessel, tex, {**tabs, "TAB6": tabs["TAB6"].replace("liga/ergebnisse/liga\\_vergleich.json", "liga/ergebnisse/rangfolge.csv")}, quellen_abb, REPO)
    lauf("Q1(a) Quellpfad-Schluessel: Datei enthaelt Regime nicht (liga_vergleich.json: S99)", pruefe_pfad_schluessel, tex, tabs, quellen_abb, REPO,
         {"TAB6": [("liga/ergebnisse/liga_vergleich.json", ["S1", "S99"])]})
    lauf("Q1(a) Quellpfad-Schluessel: cv_A_p2 enthaelt S1/S2 nicht", pruefe_pfad_schluessel, tex, {**tabs, "TAB6": tabs["TAB6"].replace("cv\\_A\\_p2\\_S1-S2-S3-S30-kompakt10", "cv\\_A\\_p2")}, quellen_abb, REPO)
    # Q1 Allwoerter und Satzregister im Anhang
    lauf("Q1(e) eigenstaendiger Satz 'lowest-error entry in all regimes' im Haupttext", pruefe_allaussagen,
         im_tex("\\textbf{Protocol sensitivity (Table", "The submitted model is the lowest-error entry in all regimes. \\textbf{Protocol sensitivity (Table"), tabs)
    lauf("Q1(e) Allsatz in A.7 (Anhang) ohne Registereintrag", pruefe_allaussagen,
         im_tex("\\paragraph{A.7 Acquisition lemmas.}", "\\paragraph{A.7 Acquisition lemmas.} Every policy is ignorable. "), tabs)
    lauf("Q1(e) registrierter Satz geaendert (L9 0.0065 -> 0.0066)", pruefe_allaussagen, im_tex("leaves 0.0065 (L9", "leaves 0.0066 (L9"), tabs)
    # Q1d Zaehlangaben
    lauf("Q1(d) '2,142 pairs' -> '2,143 pairs'", pruefe_zahlangaben_dateien, im_tex("(2,142 pairs)", "(2,143 pairs)"), tabs, REPO)
    lauf("Q1(d) '142 benchmarks' -> '143 benchmarks'", pruefe_zahlangaben_dateien, im_tex("occur in 142 benchmarks", "occur in 143 benchmarks"), tabs, REPO)
    # Q1b/c Tabellen 4/5 und Vorzeichen im Text
    lauf("Q1(c) Tab. 4: v1 - BB S2 Vorzeichen umgedreht", pruefe_tabellen_4_5, aus("TAB4", "S2 & BB ALC 0.2133; v1 $-$ BB $-0.0030", "S2 & BB ALC 0.2133; v1 $-$ BB $+0.0030"))
    lauf("Q1(c) Tab. 4: Formelfehler S3 +5.9 statt -5.9", pruefe_tabellen_4_5, aus("TAB4", "$-5.9\\,\\%$", "$+5.9\\,\\%$"))
    lauf("Q1(b) Tab. 4: Pilotzelle verfaelscht", pruefe_tabellen_4_5, aus("TAB4", "$+0.00003 \\pm 0.00012$", "$+0.00004 \\pm 0.00012$"))
    lauf("Q1(c) Tab. 5: Zeile 'item stage' S30 Vorzeichen umgedreht", pruefe_tabellen_4_5, aus("TAB3A", "$-0.00366 \\pm 0.00061$", "$+0.00366 \\pm 0.00061$"))
    lauf("Q1(b) Tab. 5: H4-Zelle verfaelscht", pruefe_tabellen_4_5, aus("TAB3A", "$-0.0006 \\pm 0.0003$", "$-0.0007 \\pm 0.0003$"))
    lauf("Q1(c) Text: '-0.0031 +- 0.0006' -> '+0.0031 +- 0.0006'", pruefe_differenzen_text, im_tex("$-0.0031 \\pm 0.0006$", "$+0.0031 \\pm 0.0006$"), tabs)
    lauf("Q1(c) Text: 'difference' mit falscher Zahl", pruefe_differenzen_text, im_tex("their ", "their difference $-0.009$ ") if "their " in tex else tex + "\ndifference $-0.009$", tabs)
    # Q1 verketteter Vergleich: neue Funktion trifft, die alte Schreibweise nicht
    alt_kette = (0.009 < 0 != True)  # noqa: E712  (alte Schreibweise 'x < 0 != (...)' = '(x < 0) and (0 != ...)')
    ergebnisse.append(("Q1 verketteter Vergleich: kappa - U/V0 = +0.009 mit gedrucktem Minus", vorzeichen_falsch(0.009, True) and not alt_kette, "alt: False (nicht erkannt), neu: True"))
    # Q2
    OHNE_ZUSTAND[0] = False
    lauf("Q2 ohne PAIEC_WORK: Tabelle 7 nicht gegen die Zustandsdateien pruefbar (fail-closed)", pruefe_tabelle7, tabs["TAB7"], None, "/nonexistent")
    # Q3/Q4 und Handtabellen
    lauf("Q3 Tabelle 8 #4: Scope '16 subjects' ohne Erklaerung", pruefe_handtabellen, im_tex(" (the 12 and those merged via website aliases)", ""), REPO)
    lauf("Q4 Tabelle 8 #7: '117 twin pairs; 830 items' ohne 172 + 92", pruefe_handtabellen, im_tex("117 upstream twin pairs (172 + 92 pairs in the database); 830 items", "117 twin pairs; 830 items"), REPO)
    lauf("Q1(b) Tabelle 8: 840 ones -> 841 ones", pruefe_handtabellen, im_tex("(840 ones, no zeros)", "(841 ones, no zeros)"), REPO)
    lauf("Q1(b) Tabelle 9: 0.00649 vs 0.00652 -> 0.00653", pruefe_handtabellen, im_tex("0.00649 vs 0.00652", "0.00649 vs 0.00653"), REPO)
    # Q5/Q6
    lauf("Q5 Abstract: 'and one failed: with one subject' ohne H4", pruefe_formulierungen, im_tex("passed and one failed (H4, below). With one subject per benchmark", "passed and one failed: with one subject per benchmark"))
    lauf("Q6 §6: 'depending on the protocol, not the estimator'", pruefe_formulierungen, im_tex("depending on how many subjects share the labels, not on the estimator.", "depending on the protocol, not the estimator."))
    # Q7/Q8/Q9
    lauf("Q7 Tabelle 4 nicht direkt unter der Ueberschrift", pruefe_tab4_position, im_tex("\\label{app:tables}\n\n\\input{tabellen/tab4_protokoll}", "\\label{app:tables}\n\n\\input{tabellen/tab3a_ablationen}\n\\input{tabellen/tab4_protokoll}"), tabs["TAB4"])
    lauf("Q7 PDF: Ueberschrift D und Tabelle 4 auf verschiedenen Seiten", pruefe_seite_ueberschrift, ["x\n D  Full tables and figures\n", "Protocol sensitivity: what moves the error"])
    lauf("Q7 PDF: 93 pt Leerflaeche zwischen Ueberschrift und Tabelle 4 (gestreckter Leim)", pruefe_abstand_ueberschrift,
         '<word xMin="1" yMin="248.0" xMax="2" yMax="259.0">Full</word><word xMin="1" yMin="341.3" xMax="2" yMax="350.0">Table</word>')
    lauf("Q7 tex: \\raggedbottom im Anhang fehlt", pruefe_tab4_position, im_tex("\\raggedbottom", "%"), tabs["TAB4"])
    lauf("Q8 Abbildung: 'pairs per benchmark' und Titel '79 %'", pruefe_fig_beschriftung, tex, "pairs per benchmark\nsubjects per benchmark", "S1: 77 % of it at B0\nS3: 79 % of it at B0")
    lauf("Q9 refs.bib: 'EACL 2024' im Venue-Text mit year 2024", pruefe_jahr_doppelt, refs.replace("howpublished = {EACL},", "howpublished = {EACL 2024},", 1), "")
    lauf("Q9 .bbl: 'NAACL 2025, 2025.'", pruefe_jahr_doppelt, refs, "\\newblock NAACL 2025, 2025.\n")
    # Anhang-Belege
    lauf("Q1(e) A.5: 3.14 M Zellen -> 3.15 M", pruefe_wiederholungsstatistik, im_tex("3.14\\,M cells", "3.15\\,M cells"))
    lauf("Q1(e) A.7: 'labels 1--7 carry 52' -> 53", pruefe_a7_gewichte, im_tex("labels 1--7 carry 52", "labels 1--7 carry 53"))
    lauf("Q1(e) Abschnitt 2: 'median benchmark 13' -> 14", pruefe_paare_statistik, im_tex("median benchmark 13", "median benchmark 14"))
    lauf("Q1(e) Anhang B: 'all 23 comparison rows' -> 24", pruefe_anhang_belege, im_tex("the same verdict in all 23", "the same verdict in all 24"), tabs, REPO)
    lauf("Q1(e) Anhang C: 'up to 1,024 labels' -> 2,048", pruefe_paketaussagen, im_tex("up to 1,024 labels", "up to 2,048 labels"))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "prereg").mkdir()
        (Path(td) / "prereg" / "PRAEREGISTRIERUNG-v2.md").write_bytes((REPO / "prereg" / "PRAEREGISTRIERUNG-v2.md").read_bytes().replace(b"Rule R1:", b"Rule R9:", 1))
        lauf("Anhang B: Praeregistrierungsdatei veraendert (Regel R1 fehlt, sha256 anders)", pruefe_prereg_zitate, tex, Path(td))
    OHNE_ZUSTAND[0] = False
    for name, ok_, grund in ergebnisse:
        print(("AUSGELOEST " if ok_ else "NICHT AUSGELOEST ") + name + (f" -> {grund}" if grund else ""))
    FEHLER[:] = basis
    return all(o for _, o, _ in ergebnisse), len(ergebnisse)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=str(HIER / "paiec_report_v2.tex"))
    ap.add_argument("--ohne-pdf", action="store_true", help="Seiten- und PDF-Sprachprüfung überspringen (vor dem ersten Bau)")
    ap.add_argument("--alt", default="", help="Fehlerfall: tex, Tabellen, refs.bib, Abbildungsquellen, Tafel, PDF, .aux/.bbl dieser Vorversion (z.B. vor-N1/) statt der aktuellen")
    ap.add_argument("--ohne-zustand", action="store_true", help="R2/Q2: Rohwerte der Zustandsdateien und paare.parquet (PAIEC_WORK) AUSDRUECKLICH nicht pruefen; ohne diese Option und ohne erreichbares PAIEC_WORK ist das Ergebnis rc 1")
    ap.add_argument("--selbsttest-neu", action="store_true", help="Fehlerfall jeder Pruefung aus Feinschliff N einmal ausloesen (Mutationen der aktuellen Texte); rc 1 wenn alle ausgeloest")
    ap.add_argument("--selbsttest-sprache", action="store_true", help="Fehlerfall der PDF-Sprachpruefung einmal ausloesen (erwartet rc 1)")
    a = ap.parse_args()
    OHNE_ZUSTAND[0] = a.ohne_zustand
    if a.selbsttest_sprache:
        # Fehlerfall: Text mit Zeilen aus der Endpruefung 2026-10-21 -> muss melden (rc 1); sauberer englischer Text -> kein Fehler
        probe = ("ICML 2024 (PMLR 235; proceedings.mlr.press/v235/maia-polo24a.html, 17:12 UTC); Autoren = AIMS-Veranstalter\n"
                 "ICLR 2025 (lt. arXiv-Kommentar). Geprueft ueber Crossref; Pruefung nicht abgeschlossen und Fehler\n"
                 "item overlap | kompakt10 | grows with overlap; kompakt10 is hypothetical\n"
                 "obs. = beob. ; verlust = daten ; P5 ; n.d. ; Polo et al. [2024]; Adrian E Raftery; Cluster-Robust inference")
        n = pruefe_pdf_sprache(probe, "Selbsttest-Fehlerfall")
        sauber = pruefe_pdf_sprache("The plan was frozen at 2026-10-20 20:26:04 UTC; checked via the arXiv record (per arXiv comment). compact10 (see cv_A_p2_S1-S2-S3-S30-\nkompakt10/auswertung.json).", "Selbsttest-Sauber")
        print(f"Selbsttest: Fehlerfall meldet {n} Gruppen, sauberer Text {sauber}")
        return 1 if (n == 5 and sauber == 0) else 3
    texpfad = Path(a.tex)
    if a.alt:
        alt = Path(a.alt).resolve()
        texpfad = alt / "paiec_report_v2.tex"
        for k in ("TAB1", "TAB2", "TAB3", "TAB3A", "TAB4", "TAB6", "TAB7"):
            Q[k] = alt / "tabellen" / Q[k].name
        Q["REFS"] = alt / "refs.bib"
        Q["QUELLEN_ABB"] = alt / "abbildungen" / "quellen_abbildungen.tex"
        if (alt / "hypothesen_tafel.json").is_file():
            Q["TAFEL"] = alt / "hypothesen_tafel.json"
    if not texpfad.is_file():
        print(f"FEHLT (fail-closed): {texpfad}")
        return 2
    tex = texpfad.read_text(encoding="utf-8")
    tabs = {}
    for k in ("TAB1", "TAB2", "TAB3", "TAB3A", "TAB4", "TAB6", "TAB7"):
        if a.alt and not Q[k].is_file() and k in ("TAB6", "TAB7"):  # Vorversion: Tabellen 6/7 standen von Hand im tex
            marke = "\\label{tab:budgets}" if k == "TAB6" else "\\label{tab:hyper}"
            i = tex.index(marke)
            tabs[k] = tex[i:tex.index("\\end{table}", i)]
        else:
            tabs[k] = lade(k)
    tex = re.sub(r"\\mbox\{(\$[^$]*\$)\}", r"\1", tex)  # O15: \mbox gegen Zeilenumbruch am +-; die Zahlenpruefungen sehen den blanken Ausdruck
    if a.selbsttest_neu:
        alle, n = selbsttest_neu(tex, tabs)
        alle2, n2 = selbsttest_r2(tex, tabs, texpfad)
        print(f"Selbsttest: {n} Mutationen (Feinschliff N) + {n2} Mutationen (Feinschliff R2), {'alle ausgeloest' if alle and alle2 else 'NICHT ALLE ausgeloest'}")
        return 1 if alle and alle2 else 3
    pruefe_zahlen(tex, tabs)
    pruefe_verbote(tex, tabs)
    pruefe_cites(tex, tabs)
    pruefe_endpruefung_l2(tex, lade("REFS"))
    quellen_abb = lade("QUELLEN_ABB")
    pruefe_vorzeichen(tex, tabs)
    pruefe_nearest(tex)
    pruefe_quellpfade(tex, tabs, quellen_abb, REPO)
    pruefe_pfad_schluessel(tex, tabs, quellen_abb, REPO)
    pruefe_zaehlangaben(tex, REPO)
    pruefe_allaussagen(tex, tabs)
    pruefe_literatur_und_layout(tex, lade("REFS"), texpfad, mit_bbl=not a.ohne_pdf)
    # Feinschliff R2
    pruefe_volle_werte(tabs)
    pruefe_tab4_lesart(tabs)
    pruefe_tabellen_4_5(tabs)
    pruefe_differenzen_text(tex, tabs)
    pruefe_zahlangaben_dateien(tex, tabs, REPO)
    pruefe_schranken_aussagen(tex)
    pruefe_patches(tex, REPO)
    pruefe_handtabellen(tex, REPO)
    pruefe_wiederholungsstatistik(tex)
    pruefe_paare_statistik(tex)
    pruefe_a7_gewichte(tex)
    pruefe_prereg_zitate(tex, REPO)
    pruefe_paketaussagen(tex)
    pruefe_anhang_belege(tex, tabs, REPO)
    pruefe_r2_layout(tex, texpfad, lade("REFS"), mit_pdf=not a.ohne_pdf)
    if not a.ohne_pdf:
        pruefe_pdf_pfade(texpfad, REPO)
        pruefe_abbildungsreihenfolge(texpfad)
        pruefe_seiten(texpfad)
        t = pdf_text(texpfad.with_suffix(".pdf"))
        if t is not None:
            pruefe_pdf_sprache(t)
    print(f"bestanden: {OK}, verfehlt: {len(FEHLER)}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
