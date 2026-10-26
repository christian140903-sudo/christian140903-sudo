"""tafel.py — baut hypothesen_tafel.json (Prereg v2 §7) aus den Ergebnisdateien der Konfirmationsskripte.

Felder je Hypothese: id, estimand, design, regime, seeds, rule, value, se, ci95, verdict, discovery_value, source_file,
teile (Unterurteile je Regime/Vergleich). Urteile stammen aus den Skripten (Code, nicht Hand); fehlende/unlesbare
Eingaben -> verdict 'not_evaluated' (fail-closed, nie stilles Bestehen). Schreibt zusätzlich HYPOTHESEN-TAFEL.md und
zahlen_quellen_P4.md (Fragment für bericht-v2/ZAHLEN-QUELLEN-v2.md).
Aufruf: python3 -I tafel.py --erg ergebnisse --aus hypothesen_tafel.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I
import kutil as ku  # noqa: E402

SEEDS = "200,201,202; Falten-Saat 200"
PREREG = "v2-plan/PRAEREGISTRIERUNG-v2.md (sha256 e5fd821f…1ab7)"
DISCOVERY = {
    "H1": "S1 −0.0003 ± 0.0004 (grey zone), S2 −0.0030 ± 0.0006 (better), S3 −0.0047 ± 0.0007 (better), S30 −0.0130 ± 0.0013",
    "H2a": "Design A S1 exakt: −0.1 / +0.1 / +0.8 / +0.4 / +0.3 %; Design B nicht verglichen",
    "H2b": "(i) B1 0.04881→0.04444→0.04123→0.02718, B3 0.03269→0.02874→0.02607→0.01918; (ii) S3/B1 +17.6 %, S30/B1 +78.4 %",
    "H2c": "κ̄_ML = 2.731, U/V0 = 2.722, Differenz +0.009, SE_boot 0.309",
    "H3": "S1 0.772 [0.753, 0.788], S2 0.781 [0.761, 0.799], S3 0.785 [0.765, 0.805]; S30 0.892 [0.841, 0.959]",
    "H4": "S1 −0.00048 ± 0.00035, S2 −0.00050 ± 0.00031, S3 −0.00051 ± 0.00028 — alle grey zone",
    "H5": "(a) −0.00003/+0.00006/+0.00005 (±0.00012/0.00003/0.00003); (b) +0.00015/+0.00030/+0.00030; (c) −0.00008/−0.00009/−0.00010 — alle equivalent, keiner better",
    "H6": "Merkmalsmenge A: LOBO-R² −0.024 (R), −0.025 (logit)",
    "H7": "Median 0.0488 (IQR 0.011–0.088), 62 Benchmarks, ein Rechenweg",
    "H8": "(i) S3 Steigung −0.00009/Item, R² 0.995; (ii) S30: 21–50 −0.0157, 51–100 −0.0125, >100 −0.0138 (Sättigung)",
}


def lade(pfad):
    p = Path(pfad)
    if not p.exists():
        return None, f"{p} fehlt"
    try:
        return json.loads(p.read_text()), None
    except Exception as e:  # noqa: BLE001
        return None, f"{p}: {type(e).__name__}: {e}"


def eintrag(hid, estimand, design, regime, rule, source, value=None, se=None, ci95=None, verdict="not_evaluated",
            teile=None, hinweis=None):
    e = {"id": hid, "estimand": estimand, "design": design, "regime": regime, "seeds": SEEDS, "rule": rule,
         "value": value, "se": se, "ci95": ci95, "verdict": verdict, "discovery_value": DISCOVERY.get(hid),
         "source_file": source, "prereg": PREREG}
    if teile is not None:
        e["teile"] = teile
    if hinweis:
        e["hinweis"] = hinweis
    return e


def h1(ergA, ergB):
    teile, src = {}, []
    for erg, dsg in ((ergA, "A"), (ergB, "B")):
        if erg is None or not isinstance(erg.get("H1"), dict):
            teile[dsg] = {"verdict": "not_evaluated"}
            continue
        teile[dsg] = erg["H1"]
    if not isinstance(teile.get("A"), dict) or "S2" not in teile["A"]:
        return eintrag("H1", "ALC(hier_item) − ALC(beta_binomial)", "A primär, B sekundär", "S1,S2,S3 (S30 berichtet)",
                       "S2, S3 better; S1 equivalent falls erreichbar, sonst grey zone mit Power", "ergebnisse/h_cv_A.json", teile=teile)
    A = teile["A"]
    v = {S: A.get(S, {}).get("verdict") for S in ("S1", "S2", "S3", "S30")}
    ok = v["S2"] == "better" and v["S3"] == "better" and v["S1"] in ("equivalent", "grey_zone")
    if "not_evaluated" in v.values():
        verdict = "not_evaluated"
    else:
        verdict = "passed" if ok else "failed"
    hinweis = None
    if v["S1"] == "better":
        hinweis = "S1 'better': Pooling-Gewinn auch bei einem Subjekt — widerspricht der Hypothese; wird so berichtet"
    elif v["S1"] == "grey_zone":
        hinweis = f"S1 nicht entscheidbar an Marge 0.001 (Power bei Null {A['S1'].get('power_aequivalenz_bei_null')})"
    return eintrag("H1", "ALC(hier_item) − ALC(beta_binomial), Paare gleich gewichtet, Mittel über 3 Saaten, SE cluster über Benchmarks",
                   "A primär, B sekundär", "S1,S2,S3 (S30 berichtet)", "S2, S3 better; S1 equivalent falls erreichbar, sonst grey zone",
                   "ergebnisse/h_cv_A.json, ergebnisse/h_cv_B.json",
                   value={S: A[S].get("d") for S in v if S in A}, se={S: A[S].get("se") for S in v if S in A},
                   ci95={S: A[S].get("ci95") for S in v if S in A}, verdict=verdict, teile=teile, hinweis=hinweis)


def h2a(lkA, lkB):
    teile = {}
    for lk, dsg in ((lkA, "A"), (lkB, "B")):
        if lk is None or not isinstance(lk.get("H2a"), dict) or "S1" not in lk["H2a"]:
            teile[dsg] = {"verdict": "not_evaluated", "grund": "Datei/Feld fehlt" if lk is None else lk.get("H2a", {}).get("grund")}
        else:
            teile[dsg] = lk["H2a"]
    va, vb = teile["A"].get("verdict_dieses_design"), teile["B"].get("verdict_dieses_design")
    if va is None or vb is None:
        verdict = "not_evaluated"
    else:
        verdict = "passed" if va == "passed" and vb == "passed" else "failed"
    val = {d: teile[d]["S1"]["rel_fehler_exakt"] for d in ("A", "B") if "S1" in teile[d]}
    # Ehrlichkeits-Hinweis (keine Regel): Prereg §4 nannte als Erwartung „≤ 3 % at every budget"; Regel bleibt ±10 %.
    hinweis = None
    try:
        gross = {f"{d}/B{b}": f"{100 * r:+.1f} %" for d in val for b, r in val[d].items() if abs(float(r)) > 0.03}
        if verdict == "passed" and gross:
            hinweis = f"Regel (±10 %) erfüllt; vorab erwartete ≤ 3 % je Budget verfehlt bei {gross} (Erwartung, keine Entscheidungsregel)"
    except (TypeError, ValueError):
        hinweis = None
    return eintrag("H2a", "relativer Fehler (Formel exakt − beobachtet)/beobachtet von (q_B−R_E)² der beta_binomial-Kurve, B=1,3,7,15,31",
                   "A und B", "S1 (S2/S3/S30 Sensitivität)", "alle fünf Budgets innerhalb ±10 % in beiden Designs",
                   "ergebnisse/lernkurve_A.json, ergebnisse/lernkurve_B.json", value=val, verdict=verdict, teile=teile, hinweis=hinweis)


def h2b(v0, lkA):
    t_i = v0.get("H2b_i") if v0 else None
    t_ii = lkA.get("H2b_ii") if lkA else None
    teile = {"i": t_i or {"verdict": "not_evaluated"}, "ii": t_ii or {"verdict": "not_evaluated"}}
    vi, vii = teile["i"].get("verdict"), teile["ii"].get("verdict")
    if "not_evaluated" in (vi, vii) or vi is None or vii is None:
        verdict = "not_evaluated"
    else:
        verdict = "passed" if vi == "passed" and vii == "passed" else "failed"
    val = {"i_schritte_better": teile["i"].get("schritte_better"), "ii_S3_B1": teile["ii"].get("S3_B1_abweichung"),
           "ii_S30_B1": teile["ii"].get("S30_B1_abweichung")}
    return eintrag("H2b", "(i) gepaarte Differenzen von (q_B−R_E)² hier_item bei B=1,3 zwischen S1→S2→S3→S30; (ii) Abweichung der fixed-κ-Formel (V0 = hier_item-B0) bei S3/B1 und S30/B1",
                   "A", "S1,S2,S3,S30", "(i) 6/6 Schritte better; (ii) S3/B1 in [+10 %, +30 %], S30/B1 in [+50 %, +110 %]",
                   "ergebnisse/v0_eff_A.json, ergebnisse/lernkurve_A.json", value=val, verdict=verdict, teile=teile)


def h2c(lkA):
    t = lkA.get("H2c") if lkA else None
    if not isinstance(t, dict) or "verdict" not in t:
        return eintrag("H2c", "κ̄_ML − U/V0", "A", "S1, B0", "|κ̄_ML − U/V0| ≤ 2·SE_boot", "ergebnisse/lernkurve_A.json")
    return eintrag("H2c", "κ̄_ML (paargewichtetes Mittel α_f+β_f) − U/V0 gepoolt (S1, B0, Saaten gemittelt); SE Cluster-Bootstrap 2000, Saat 200",
                   "A", "S1, B0", "|κ̄_ML − U/V0| ≤ 2·SE_boot", "ergebnisse/lernkurve_A.json",
                   value={"kappa_ML": t.get("kappa_ML_paargewichtet"), "U_durch_V0": t.get("U_durch_V0_gepoolt"), "differenz": t.get("differenz")},
                   se=t.get("se_boot"), ci95=t.get("ci95_boot_U_durch_V0"), verdict=t["verdict"], teile=t, hinweis=t.get("hinweis"))


def h3(ergA):
    t = ergA.get("H3") if ergA else None
    if not isinstance(t, dict) or "gesamt" not in t:
        return eintrag("H3", "Anteil ALC-gewichteter Überschuss B0–B3", "A", "S1,S2,S3 (S30 berichtet)", "untere KI-Grenze > 0.70", "ergebnisse/h_cv_A.json")
    return eintrag("H3", "Σ_{B∈{0,1,3}} w_B·(Brier_B − R(1−R)) / Σ_B w_B·(Brier_B − R(1−R)), hier_item; Cluster-Bootstrap 2000, Saat 200",
                   "A", "S1,S2,S3 (S30 berichtet; kompakt10 ausgeschlossen)", "untere 95%-KI-Grenze > 0.70 in S1, S2, S3", "ergebnisse/h_cv_A.json",
                   value={S: t[S].get("anteil") for S in ("S1", "S2", "S3", "S30") if isinstance(t.get(S), dict)},
                   se={S: t[S].get("se_boot") for S in ("S1", "S2", "S3", "S30") if isinstance(t.get(S), dict)},
                   ci95={S: t[S].get("ci95_boot") for S in ("S1", "S2", "S3", "S30") if isinstance(t.get(S), dict)},
                   verdict=t["gesamt"], teile=t)


def h4(ergA, ergB):
    teile = {}
    for erg, dsg in ((ergA, "A"), (ergB, "B")):
        teile[dsg] = erg["H4"] if (erg and isinstance(erg.get("H4"), dict)) else {"verdict": "not_evaluated"}
    A = teile["A"]
    v = {S: A.get(S, {}).get("verdict") for S in ("S1", "S2", "S3")}
    if None in v.values() or "not_evaluated" in v.values():
        verdict = "not_evaluated"
    elif all(x == "equivalent" for x in v.values()):
        verdict = "passed"
    elif any(x in ("better", "worse") for x in v.values()):
        verdict = "failed"
    else:
        verdict = "grey_zone"
    hinweis = None
    if verdict == "grey_zone":
        hinweis = ("grey zone: nicht entscheidbar an Marge 0.001; Power bei exaktem Nulleffekt je Regime: "
                   + str({S: A[S].get("power_aequivalenz_bei_null") for S in v if S in A}))
    elif verdict == "failed":
        # Grund (Prereg §4 H4 „If it fails": better ⇒ kleiner realer Effekt, Vergleich zum Pooling-Gewinn H1 desselben Laufs)
        try:
            grenze = {S: round(abs(A[S]["d"]) + 2 * A[S]["se"], 6) for S in v if S in A and "d" in A[S]}
            h1 = (ergA or {}).get("H1") or {}
            anteil = {S: round(A[S]["d"] / h1[S]["d"], 2) for S in v
                      if S in A and isinstance(h1.get(S), dict) and h1[S].get("d") and h1[S].get("verdict") == "better"}
            hinweis = (f"gescheitert, weil nicht 'equivalent': Urteile {v}; |d| + 2·SE = {grenze} > Marge 0.001; "
                       f"kleiner realer Effekt (Subjektwissen hilft minimal), Anteil am Pooling-Gewinn H1 (d_H4/d_H1, nur Regime mit H1 'better') {anteil}; "
                       "Prereg-Fallregel: als kleiner realer Effekt berichten, Satz 'subject knowledge carries little' mit Zahl behalten")
        except (KeyError, TypeError, ZeroDivisionError) as e:  # noqa: BLE001
            hinweis = f"gescheitert, weil nicht 'equivalent': Urteile {v} (Detail nicht berechenbar: {e})"
    return eintrag("H4", "ALC(hier) − ALC(hier_ohne_subjekt), beide unkalibriert", "A primär, B sekundär", "S1,S2,S3",
                   "equivalent (|d| + 2·SE < 0.001) in S1, S2, S3", "ergebnisse/h_cv_A.json, ergebnisse/h_cv_B.json",
                   value={S: A[S].get("d") for S in v if S in A}, se={S: A[S].get("se") for S in v if S in A},
                   ci95={S: A[S].get("ci95") for S in v if S in A}, verdict=verdict, teile=teile, hinweis=hinweis)


def h5(ens):
    t = ens.get("H5") if ens else None
    if not isinstance(t, dict) or "verdict" not in t:
        return eintrag("H5", "Ensemble/NPEB vs hier_kal bzw. BB", "A", "S1,S2,S3", "9/9 equivalent und keiner better", "ergebnisse/ensemble_A.json")
    val = {S: {k: v.get("d") for k, v in t[S].items() if not k.startswith("zusatz")} for S in ("S1", "S2", "S3") if S in t}
    se = {S: {k: v.get("se") for k, v in t[S].items() if not k.startswith("zusatz")} for S in ("S1", "S2", "S3") if S in t}
    return eintrag("H5", "(a) mix(hier_kal, BB) − hier_kal; (b) logit-stack(hier_kal, BB) − hier_kal; (c) NPEB − beta_binomial; Gewichte je Falte aus den anderen 9",
                   "A", "S1,S2,S3", "alle neun equivalent und keiner better", "ergebnisse/ensemble_A.json",
                   value=val, se=se, verdict=t["verdict"], teile=t)


def h6(b0):
    if not b0 or "verdict" not in b0:
        return eintrag("H6", "LOBO-R² Ridge, Merkmalsmenge B", "—", "B0", "LOBO-R² ≤ 0.05 für R_b und logit(R_b)", "ergebnisse/b0lage_K.json")
    r = b0.get("ergebnis", {})
    return eintrag("H6", "LOBO-R² einer Ridge (λ ∈ {3,10,30,100,300} per innerem LOBO) von Benchmark-Aggregaten (Merkmalsmenge B) auf R_b und logit(R_b)",
                   "— (142 Benchmarks)", "B0", "LOBO-R² ≤ 0.05 für beide Ziele", "ergebnisse/b0lage_K.json",
                   value={z: r.get(z, {}).get("r2_lobo") for z in r}, verdict=b0["verdict"], teile=b0,
                   hinweis="nicht saatabhängig; neue Merkmalsmenge B (Set A war Discovery)")


def h7(wd):
    if not wd or "verdict" not in wd:
        return eintrag("H7", "L10 je Benchmark", "—", "—", "Median ≥ 0.02; Zweitweg innerhalb 1 %", "ergebnisse/wiederholung_K.json")
    v = wd["verdict"]
    verdict = {"passed": "passed", "passed_zweitweg_offen": "passed", "passed_zweitweg_abweichend": "passed", "failed": "failed"}.get(v, "not_evaluated")
    hinweis = {"passed_zweitweg_offen": "Zweitweg (P8) lag nicht vor; Median-Kriterium erfüllt",
               "passed_zweitweg_abweichend": "Zweitweg weicht > 1 % ab — beide Werte berichten (Prereg)",
               "passed": "Zweitweg (P8, anderer Code) innerhalb 1 %"}.get(v)
    return eintrag("H7", "L10_b = Σ n·k(n−k)/(n(n−1)) / Σ n über Zellen n ≥ 2; Median/IQR über Benchmarks mit ≥ 100 Zellen",
                   "— (Datenstatistik)", "—", "Median ≥ 0.02; zwei Rechenwege innerhalb 1 %", "ergebnisse/wiederholung_K.json",
                   value={"median": wd.get("L10_median"), "iqr": wd.get("L10_iqr"), "n_benchmarks": wd.get("benchmarks_mit_>=100_wdh_zellen"),
                          "zweitweg_median": wd.get("zweitweg", {}).get("median")}, verdict=verdict, teile=wd, hinweis=hinweis)


def h8(ergA):
    t = ergA.get("H8") if ergA else None
    if not isinstance(t, dict) or "gesamt" not in t:
        return eintrag("H8", "Itemgewinn vs Fremdlabel-Items", "A", "S3, S30", "(i) S3 Steigung < 0, KI ohne 0, R² ≥ 0.8; (ii) S30 Sättigung", "ergebnisse/h_cv_A.json")
    s3, s30 = t.get("S3", {}), t.get("S30", {})
    return eintrag("H8", "Itemgewinn (itemgenauer − paarkonstanter Brier) bei B=31 gegen Zahl der Bewertungsitems mit Fremdlabels; Klassen ≥ 20 Paare; WLS der Klassenmittel; Paar-Steigung Cluster-Bootstrap 500, Saat 200",
                   "A", "S3 (i), S30 (ii), kompakt10 berichtet", "(i) S3: Steigung < 0, 95%-KI ohne 0, R² Klassenmittel ≥ 0.8; (ii) S30: Mittel 51–100 und >100 nicht negativer als 1.3 × Mittel 21–50",
                   "ergebnisse/h_cv_A.json",
                   value={"S3_wls_steigung": s3.get("wls_steigung_je_item"), "S3_r2": s3.get("r2_klassenmittel_gewichtet"),
                          "S3_paar_steigung": s3.get("paar_steigung_je_item"),
                          "S30_klassen": {k: v.get("itemgewinn_mittel") for k, v in s30.get("klassen", {}).items()}},
                   se={"S3_paar_steigung": s3.get("paar_steigung_se_boot")}, ci95={"S3_paar_steigung": s3.get("paar_steigung_ci95_boot")},
                   verdict=t["gesamt"], teile=t)


def z(s):
    """Senkrechte Striche für Markdown-Tabellenzellen entschärfen."""
    return str(s).replace("|", "∣")


def grund(h, fehler):
    """Kurzbegründung je Hypothese: Teil-Urteile (aus den Skripten) + Hinweis; bei not_evaluated der Eingabefehler."""
    teile = h.get("teile") or {}
    parts = []
    for k, v in teile.items():
        if not isinstance(v, dict):
            continue
        sub = {kk: x.get("verdict") for kk, x in v.items() if isinstance(x, dict) and x.get("verdict")}
        if sub:
            parts.append(f"{k}: " + ", ".join(f"{kk} {vv}" for kk, vv in sub.items()))
        elif v.get("verdict") and k not in ("verdict",):
            parts.append(f"{k}: {v['verdict']}" + (f" ({v['grund']})" if v.get("grund") else ""))
        elif v.get("verdict_dieses_design"):
            parts.append(f"{k}: {v['verdict_dieses_design']}")
    s = "; ".join(parts)
    if h.get("hinweis"):
        s = (s + " — " if s else "") + str(h["hinweis"])
    if h["verdict"] == "not_evaluated":
        quellen = [q.strip().split("/")[-1] for q in h["source_file"].split(",")]
        fe = [f"{k}: {v}" for k, v in fehler.items() if any(q in v for q in quellen)]
        s = "nicht ausgewertet (fail-closed): " + ("; ".join(fe) if fe else "Eingabefeld fehlt/unlesbar") + (" — " + s if s else "")
    return s or "—"


def _hcv_zeilen(d):
    """(H, Regime) -> (Wert, Urteil) aus einer h_cv-Datei: H1/H4 d, H3 Anteil, H8 S3-Steigung."""
    zl = {}
    if not isinstance(d, dict):
        return zl
    for Hn in ("H1", "H4"):
        for S, x in (d.get(Hn) or {}).items():
            if isinstance(x, dict) and x.get("d") is not None:
                zl[(Hn, S)] = (float(x["d"]), x.get("verdict"))
    for S, x in (d.get("H3") or {}).items():
        if isinstance(x, dict) and x.get("anteil") is not None:
            zl[("H3", S + " Anteil")] = (float(x["anteil"]), x.get("verdict"))
    h8 = d.get("H8") or {}
    if isinstance(h8.get("S3"), dict) and h8["S3"].get("wls_steigung_je_item") is not None:
        zl[("H8", "S3 WLS-Steigung")] = (float(h8["S3"]["wls_steigung_je_item"]), h8.get("gesamt"))
    return zl


def _lk_zeilen(d):
    zl = {}
    if not isinstance(d, dict):
        return zl
    a = d.get("H2a") or {}
    if isinstance(a.get("S1"), dict) and isinstance(a["S1"].get("rel_fehler_exakt"), dict):
        zl[("H2a", "S1 max∣rel. Fehler∣")] = (max(abs(float(v)) for v in a["S1"]["rel_fehler_exakt"].values()), a.get("verdict_dieses_design"))
    c = d.get("H2c") or {}
    if c.get("differenz") is not None:
        zl[("H2c", "Differenz")] = (float(c["differenz"]), c.get("verdict"))
    b = d.get("H2b_ii") or {}
    for k, lab in (("S3_B1_abweichung", "S3/B1"), ("S30_B1_abweichung", "S30/B1")):
        if b.get(k) is not None:
            zl[("H2b ii", lab)] = (float(b[k]), b.get("verdict"))
    return zl


def sensitivitaet_md(E):
    """Abschnitt: Urteile primär (verschachtelte Stufen je Falte) vs. Sensitivitätsläufe; fail-closed ('fehlt'/'—')."""
    md = ["", "## Sensitivität der Phase-2-Platt-Stufenwahl (Urteile primär vs. Sensitivitätsläufe)", "",
          "Primär = verschachtelte Platt-Stufenmenge je Falte (cv_K_*2v, Paketregel v2.0-core); S-0137 = erzwungene v1-Paketmenge {0,1,3,7} "
          "(cv_K_*2p); S-v1 = v1-Pipelinewahl auf allen Falten (cv_K_*2). Phase 1 ist in allen Varianten dieselbe (bitgleich belegt). "
          "Als Sensitivität gerechnet wurden nur h_cv (H1/H3/H4/H8) und lernkurve (H2a/H2b ii/H2c); '—' = nicht gerechnet, "
          "'fehlt' = Datei fehlt/unlesbar (fail-closed).", "",
          "| H | Design | Größe | primär: Wert (Urteil) | S-0137 | S-v1 | max ∣Δ∣ | Urteile gleich |", "|---|---|---|---|---|---|---|---|"]
    varianten = (("primär", E), ("S-0137", E / "sensitivitaet_stufen_0137"), ("S-v1", E / "sensitivitaet_stufenwahl"))
    n_zeilen = n_gleich = 0
    for dsg in ("A", "B"):
        for art, fn, fkt in (("h_cv", f"h_cv_{dsg}.json", _hcv_zeilen), ("lernkurve", f"lernkurve_{dsg}.json", _lk_zeilen)):
            tab = {}
            for name, ordner in varianten:
                p = ordner / fn
                if not p.exists():
                    tab[name] = None
                    continue
                d, err = lade(p)
                tab[name] = "fehlt" if err else fkt(d)
            prim = tab["primär"]
            if not isinstance(prim, dict) or not prim:
                md.append(f"| {art} | {dsg} | — | {'fehlt' if prim == 'fehlt' else '— (nicht gerechnet/leer)'} | | | | |")
                continue
            for (Hn, S), (w, u) in prim.items():
                zellen, werte, urteile = [], [w], [u]
                for name, _ in varianten[1:]:
                    t = tab[name]
                    if isinstance(t, dict) and (Hn, S) in t:
                        w2, u2 = t[(Hn, S)]
                        werte.append(w2)
                        urteile.append(u2)
                        zellen.append(f"{w2:.6f} ({u2})")
                    else:
                        zellen.append("fehlt" if t == "fehlt" else "—")
                if len(werte) > 1:
                    dmax = max(abs(x - w) for x in werte[1:])
                    gleich = len(set(urteile)) == 1
                    n_zeilen += 1
                    n_gleich += int(gleich)
                    g, dm = ("ja" if gleich else "NEIN"), f"{dmax:.1e}"
                else:
                    g, dm = "n/a", "—"
                md.append(f"| {Hn} | {dsg} | {S} | {w:.6f} ({u}) | {zellen[0]} | {zellen[1]} | {dm} | {g} |")
    md += ["", f"Urteile gleich in {n_gleich}/{n_zeilen} Zeilen mit mindestens einer Sensitivitätsvariante."]
    md += ["", "Platt-Stufenmenge je Falte in den Primärläufen (ergebnisse/pruefe_stufen_*2v.json, geprüft gegen kern-Auswertung und {0,1,3,7}-Lauf):", ""]
    for dsg in ("A", "B"):
        d, err = lade(E / f"pruefe_stufen_{dsg}2v.json")
        if err or not isinstance(d, dict) or "falten" not in d:
            md.append(f"- Design {dsg}: fehlt ({err or 'Feld falten fehlt'})")
            continue
        st = {f: d["falten"][f]["stufen"] for f in sorted(d["falten"], key=int)}
        abw = [f for f, s in st.items() if sorted(s) != [0, 1, 3, 7]]
        md.append(f"- Design {dsg}: Prüfung {'ok' if d.get('ok') else 'VERFEHLT'}; Stufen je Falte {json.dumps(st)}; "
                  f"von {{0,1,3,7}} abweichend in {len(abw)}/10 Falten ({', '.join('F' + f for f in abw) or 'keine'})")
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--erg", default="ergebnisse")
    ap.add_argument("--aus", default="hypothesen_tafel.json")
    a = ap.parse_args()
    E = Path(a.erg)
    dateien = {k: E / f for k, f in (("hA", "h_cv_A.json"), ("hB", "h_cv_B.json"), ("lkA", "lernkurve_A.json"), ("lkB", "lernkurve_B.json"),
                                     ("v0", "v0_eff_A.json"), ("ens", "ensemble_A.json"), ("b0", "b0lage_K.json"), ("wd", "wiederholung_K.json"))}
    geladen, fehler = {}, {}
    for k, p in dateien.items():
        geladen[k], err = lade(p)
        if err:
            fehler[k] = err
    H = [h1(geladen["hA"], geladen["hB"]), h2a(geladen["lkA"], geladen["lkB"]), h2b(geladen["v0"], geladen["lkA"]), h2c(geladen["lkA"]),
         h3(geladen["hA"]), h4(geladen["hA"], geladen["hB"]), h5(geladen["ens"]), h6(geladen["b0"]), h7(geladen["wd"]), h8(geladen["hA"])]
    H = [ku.rund(h) for h in H]
    zaehl = {}
    for h in H:
        zaehl[h["verdict"]] = zaehl.get(h["verdict"], 0) + 1
    out = {"zeit_utc": ku.jetzt(), "paketmodell": "v2.0-core (./dist/paiec_v2core.zip sha256 7883867c…e012; P1 FERTIG 2026-10-21T06:41Z): v1-Mathematik, bitgleich in Phase 1; Phase 2 mit verschachtelter Platt-Stufenwahl je Falte (Prereg §0 Nr. 2, dokumentierte Ausnahme)",
           "prereg": PREREG, "seeds": SEEDS, "laeufe": {"A_p1": "cv_K_A", "A_p2": "cv_K_A2v (verschachtelte Stufen je Falte, primär)", "B_p1": "cv_K_B", "B_p2": "cv_K_B2v (verschachtelte Stufen je Falte, primär)", "sensitivitaet": "cv_K_A2p/cv_K_B2p (Stufen {0,1,3,7} = v1-Paket), cv_K_A2/cv_K_B2 (v1-Pipelinewahl)"},
           "eingabe_fehler": fehler, "zusammenfassung": zaehl, "hypothesen": H,
           "kehrseite": ("Falsch oder wertlos, wenn das private Ingestion-Programm vom öffentlichen streaming_ingestion.py abweicht (Split je Item, "
                         "Zustand über Budgets, andere Zufallsquelle) — dann misst jeder Lauf ein anderes Protokoll; und weil alle Hypothesen aus denselben "
                         "142 Benchmarks stammen, belegt ein Bestehen nur Stabilität gegenüber Zufallsquellen (Saaten, Faltenzuteilung), nie Generalisierung "
                         "auf neue Benchmarks. Zusätzlich: wechselt das eingereichte Paket (K1, Text-Prior, labeling.py), gilt diese Tafel nicht (Regel R1); die Phase-2-Zahlen nutzen je Falte die verschachtelte Stufenmenge, das Paket selbst die Schnittmenge über die Trainingsfalten — kein exakter Paket-Nachlauf (Differenz in der Größenordnung 1e-5, kern/KERN-DIFF.md §4).")}
    ku.schreibe_json(a.aus, out)
    # Markdown
    md = [f"# Hypothesen-Tafel (Konfirmation, Saaten 200–202, Falten-Saat 200) — {out['zeit_utc']}", "",
          f"Paketmodell: {out['paketmodell']}", "", f"Prereg: {PREREG}", "",
          "Urteile (Prereg §7): passed = bestanden · failed = gescheitert · equivalent = äquivalent · grey_zone = Grauzone · "
          "not_evaluated = nicht ausgewertet (Grund in Spalte 'Hinweis / Grund'; fail-closed). Urteile stammen aus den Skripten, nicht von Hand.", "",
          "| H | Estimand (kurz) | Design/Regime | Regel | Wert | SE | Urteil | Hinweis / Grund | Discovery |", "|---|---|---|---|---|---|---|---|---|"]
    for h in H:
        md.append(f"| {h['id']} | {z(h['estimand'][:90])} | {z(h['design'])} / {z(h['regime'])} | {z(h['rule'])} | `{z(json.dumps(h['value'], ensure_ascii=False)[:160])}` | "
                  f"`{z(json.dumps(h['se'], ensure_ascii=False)[:80])}` | **{h['verdict']}** | {z(grund(h, fehler))[:420]} | {z(h['discovery_value'])} |")
    md += ["", f"Zusammenfassung: {json.dumps(zaehl)}", "", "Eingabefehler: " + (json.dumps(fehler, ensure_ascii=False) if fehler else "keine")]
    md += sensitivitaet_md(E)
    md += ["", "Kehrseite: " + out["kehrseite"]]
    Path(a.aus).with_name("HYPOTHESEN-TAFEL.md").write_text("\n".join(md) + "\n")
    # Fragment für ZAHLEN-QUELLEN-v2.md
    zq = [f"## P4 Konfirmation (Saaten 200–202, Falten-Saat 200, Paketmodell v2.0-core, Phase 2 verschachtelte Platt-Stufen je Falte) — {out['zeit_utc']}", "",
          "| Zahl | Wert | Datei | Feld |", "|---|---|---|---|"]
    for h in H:
        zq.append(f"| {h['id']} Urteil | {h['verdict']} | ./konfirmation/hypothesen_tafel.json | hypothesen[id={h['id']}].verdict |")
        if isinstance(h["value"], dict):
            for k, v in h["value"].items():
                zq.append(f"| {h['id']} {k} | `{json.dumps(v, ensure_ascii=False)[:100]}` | ./konfirmation/{h['source_file'].split(',')[0].strip()} | siehe Tafel: hypothesen[id={h['id']}].value.{k} |")
    Path(a.aus).with_name("zahlen_quellen_P4.md").write_text("\n".join(zq) + "\n")
    print(json.dumps({h["id"]: h["verdict"] for h in H}, indent=0))
    print("Eingabefehler:", fehler or "keine")
    return 0 if not fehler else 1


if __name__ == "__main__":
    sys.exit(main())
