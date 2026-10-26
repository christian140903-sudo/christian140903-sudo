# Hypothesen-Tafel (Konfirmation, Saaten 200–202, Falten-Saat 200) — 2026-10-21T08:56:30Z

Paketmodell: v2.0-core (./dist/paiec_v2core.zip sha256 7883867c…e012; P1 FERTIG 2026-10-21T06:41Z): v1-Mathematik, bitgleich in Phase 1; Phase 2 mit verschachtelter Platt-Stufenwahl je Falte (Prereg §0 Nr. 2, dokumentierte Ausnahme)

Prereg: v2-plan/PRAEREGISTRIERUNG-v2.md (sha256 e5fd821f…1ab7)

Urteile (Prereg §7): passed = bestanden · failed = gescheitert · equivalent = äquivalent · grey_zone = Grauzone · not_evaluated = nicht ausgewertet (Grund in Spalte 'Hinweis / Grund'; fail-closed). Urteile stammen aus den Skripten, nicht von Hand.

| H | Estimand (kurz) | Design/Regime | Regel | Wert | SE | Urteil | Hinweis / Grund | Discovery |
|---|---|---|---|---|---|---|---|---|
| H1 | ALC(hier_item) − ALC(beta_binomial), Paare gleich gewichtet, Mittel über 3 Saaten, SE clus | A primär, B sekundär / S1,S2,S3 (S30 berichtet) | S2, S3 better; S1 equivalent falls erreichbar, sonst grey zone | `{"S1": -0.000421, "S2": -0.003133, "S3": -0.004936, "S30": -0.013208}` | `{"S1": 0.000383, "S2": 0.000553, "S3": 0.000668, "S30": 0.001231}` | **passed** | A: S1 grey_zone, S2 better, S3 better, S30 better; B: S1 grey_zone, S3 better — S1 nicht entscheidbar an Marge 0.001 (Power bei Null 0.458778) | S1 −0.0003 ± 0.0004 (grey zone), S2 −0.0030 ± 0.0006 (better), S3 −0.0047 ± 0.0007 (better), S30 −0.0130 ± 0.0013 |
| H2a | relativer Fehler (Formel exakt − beobachtet)/beobachtet von (q_B−R_E)² der beta_binomial-K | A und B / S1 (S2/S3/S30 Sensitivität) | alle fünf Budgets innerhalb ±10 % in beiden Designs | `{"A": {"1": 0.016407, "3": 0.020096, "7": 0.024675, "15": -0.023735, "31": -0.041972}, "B": {"1": 0.016066, "3": 0.019383, "7": 0.023933, "15": -0.024148, "31":` | `null` | **passed** | A: passed; B: passed — Regel (±10 %) erfüllt; vorab erwartete ≤ 3 % je Budget verfehlt bei {'A/B31': '-4.2 %', 'B/B31': '-4.2 %'} (Erwartung, keine Entscheidungsregel) | Design A S1 exakt: −0.1 / +0.1 / +0.8 / +0.4 / +0.3 %; Design B nicht verglichen |
| H2b | (i) gepaarte Differenzen von (q_B−R_E)² hier_item bei B=1,3 zwischen S1→S2→S3→S30; (ii) Ab | A / S1,S2,S3,S30 | (i) 6/6 Schritte better; (ii) S3/B1 in [+10 %, +30 %], S30/B1 in [+50 %, +110 %] | `{"i_schritte_better": 6, "ii_S3_B1": 0.214359, "ii_S30_B1": 0.876961}` | `null` | **passed** | i: B1:S1->S2 better, B1:S2->S3 better, B1:S3->S30 better, B3:S1->S2 better, B3:S2->S3 better, B3:S3->S30 better; ii: passed | (i) B1 0.04881→0.04444→0.04123→0.02718, B3 0.03269→0.02874→0.02607→0.01918; (ii) S3/B1 +17.6 %, S30/B1 +78.4 % |
| H2c | κ̄_ML (paargewichtetes Mittel α_f+β_f) − U/V0 gepoolt (S1, B0, Saaten gemittelt); SE Clust | A / S1, B0 | ∣κ̄_ML − U/V0∣ ≤ 2·SE_boot | `{"kappa_ML": 2.734802, "U_durch_V0": 2.725276, "differenz": 0.009526}` | `0.309284` | **passed** | v1 fittet die Beta-Prior per Momentenmethode (baselines.beta_prior), nicht per Marginal-Likelihood; kappa_f = alpha_f + beta_f aus state_f.json wie in der Discovery-Rechnung (p2work/h2c_discovery.json) | κ̄_ML = 2.731, U/V0 = 2.722, Differenz +0.009, SE_boot 0.309 |
| H3 | Σ_{B∈{0,1,3}} w_B·(Brier_B − R(1−R)) / Σ_B w_B·(Brier_B − R(1−R)), hier_item; Cluster-Boot | A / S1,S2,S3 (S30 berichtet; kompakt10 ausgeschlossen) | untere 95%-KI-Grenze > 0.70 in S1, S2, S3 | `{"S1": 0.767475, "S2": 0.777778, "S3": 0.783006, "S30": 0.893657}` | `{"S1": 0.009454, "S2": 0.009393, "S3": 0.009634, "S30": 0.03078}` | **passed** | S1: passed; S2: passed; S3: passed; S30: reported | S1 0.772 [0.753, 0.788], S2 0.781 [0.761, 0.799], S3 0.785 [0.765, 0.805]; S30 0.892 [0.841, 0.959] |
| H4 | ALC(hier) − ALC(hier_ohne_subjekt), beide unkalibriert | A primär, B sekundär / S1,S2,S3 | equivalent (∣d∣ + 2·SE < 0.001) in S1, S2, S3 | `{"S1": -0.000545, "S2": -0.000598, "S3": -0.000677}` | `{"S1": 0.000338, "S2": 0.000287, "S3": 0.000256}` | **failed** | A: S1 grey_zone, S2 better, S3 better; B: S1 grey_zone, S3 better — gescheitert, weil nicht 'equivalent': Urteile {'S1': 'grey_zone', 'S2': 'better', 'S3': 'better'}; ∣d∣ + 2·SE = {'S1': 0.001221, 'S2': 0.001172, 'S3': 0.001189} > Marge 0.001; kleiner realer Effekt (Subjektwissen hilft minimal), Anteil am Pooling-Gewinn H1 (d_H4/d_H1, nur Regime mit H1 'better') {'S2': 0.19, 'S3': 0.14}; Prereg-Fallregel: als kleiner | S1 −0.00048 ± 0.00035, S2 −0.00050 ± 0.00031, S3 −0.00051 ± 0.00028 — alle grey zone |
| H5 | (a) mix(hier_kal, BB) − hier_kal; (b) logit-stack(hier_kal, BB) − hier_kal; (c) NPEB − bet | A / S1,S2,S3 | alle neun equivalent und keiner better | `{"S1": {"a_mix_hk_bb_minus_hk": -1.6e-05, "b_stack_hk_bb_minus_hk": 4.5e-05, "c_npeb_minus_bb": -7.9e-05}, "S2": {"a_mix_hk_bb_minus_hk": 2.8e-05, "b_stack_hk_b` | `{"S1": {"a_mix_hk_bb_minus_hk": 7.9e-05, "b_stack_hk_bb_minus_hk": 0.000229, "c_` | **passed** | S1: a_mix_hk_bb_minus_hk equivalent, b_stack_hk_bb_minus_hk equivalent, c_npeb_minus_bb equivalent, zusatz_mix_hk_np_minus_hk equivalent; S2: a_mix_hk_bb_minus_hk equivalent, b_stack_hk_bb_minus_hk equivalent, c_npeb_minus_bb equivalent, zusatz_mix_hk_np_minus_hk equivalent; S3: a_mix_hk_bb_minus_hk equivalent, b_stack_hk_bb_minus_hk equivalent, c_npeb_minus_bb equivalent, zusatz_mix_hk_np_minus_hk equivalent | (a) −0.00003/+0.00006/+0.00005 (±0.00012/0.00003/0.00003); (b) +0.00015/+0.00030/+0.00030; (c) −0.00008/−0.00009/−0.00010 — alle equivalent, keiner better |
| H6 | LOBO-R² einer Ridge (λ ∈ {3,10,30,100,300} per innerem LOBO) von Benchmark-Aggregaten (Mer | — (142 Benchmarks) / B0 | LOBO-R² ≤ 0.05 für beide Ziele | `{"R": -0.04774, "logit_R": -0.056479}` | `null` | **passed** | nicht saatabhängig; neue Merkmalsmenge B (Set A war Discovery) | Merkmalsmenge A: LOBO-R² −0.024 (R), −0.025 (logit) |
| H7 | L10_b = Σ n·k(n−k)/(n(n−1)) / Σ n über Zellen n ≥ 2; Median/IQR über Benchmarks mit ≥ 100  | — (Datenstatistik) / — | Median ≥ 0.02; zwei Rechenwege innerhalb 1 % | `{"median": 0.048821, "iqr": [0.010642, 0.088086], "n_benchmarks": 62, "zweitweg_median": 0.048821}` | `null` | **passed** | Zweitweg (P8, anderer Code) innerhalb 1 % | Median 0.0488 (IQR 0.011–0.088), 62 Benchmarks, ein Rechenweg |
| H8 | Itemgewinn (itemgenauer − paarkonstanter Brier) bei B=31 gegen Zahl der Bewertungsitems mi | A / S3 (i), S30 (ii), kompakt10 berichtet | (i) S3: Steigung < 0, 95%-KI ohne 0, R² Klassenmittel ≥ 0.8; (ii) S30: Mittel 51–100 und >100 nicht negativer als 1.3 × Mittel 21–50 | `{"S3_wls_steigung": -8.7e-05, "S3_r2": 0.982495, "S3_paar_steigung": -7.8e-05, "S30_klassen": {"0": 0.0, "1-2": -0.000698, "3-5": -0.000773, "6-10": -0.001286, ` | `{"S3_paar_steigung": 1.3e-05}` | **passed** | S3: passed; S30: passed; kompakt10: reported | (i) S3 Steigung −0.00009/Item, R² 0.995; (ii) S30: 21–50 −0.0157, 51–100 −0.0125, >100 −0.0138 (Sättigung) |

Zusammenfassung: {"passed": 9, "failed": 1}

Eingabefehler: keine

## Sensitivität der Phase-2-Platt-Stufenwahl (Urteile primär vs. Sensitivitätsläufe)

Primär = verschachtelte Platt-Stufenmenge je Falte (cv_K_*2v, Paketregel v2.0-core); S-0137 = erzwungene v1-Paketmenge {0,1,3,7} (cv_K_*2p); S-v1 = v1-Pipelinewahl auf allen Falten (cv_K_*2). Phase 1 ist in allen Varianten dieselbe (bitgleich belegt). Als Sensitivität gerechnet wurden nur h_cv (H1/H3/H4/H8) und lernkurve (H2a/H2b ii/H2c); '—' = nicht gerechnet, 'fehlt' = Datei fehlt/unlesbar (fail-closed).

| H | Design | Größe | primär: Wert (Urteil) | S-0137 | S-v1 | max ∣Δ∣ | Urteile gleich |
|---|---|---|---|---|---|---|---|
| H1 | A | S1 | -0.000421 (grey_zone) | -0.000424 (grey_zone) | -0.000428 (grey_zone) | 7.0e-06 | ja |
| H1 | A | S2 | -0.003133 (better) | -0.003136 (better) | -0.003138 (better) | 5.0e-06 | ja |
| H1 | A | S3 | -0.004936 (better) | -0.004939 (better) | -0.004940 (better) | 4.0e-06 | ja |
| H1 | A | S30 | -0.013208 (better) | -0.013213 (better) | -0.013207 (better) | 5.0e-06 | ja |
| H4 | A | S1 | -0.000545 (grey_zone) | -0.000545 (grey_zone) | -0.000545 (grey_zone) | 0.0e+00 | ja |
| H4 | A | S2 | -0.000598 (better) | -0.000598 (better) | -0.000598 (better) | 0.0e+00 | ja |
| H4 | A | S3 | -0.000677 (better) | -0.000677 (better) | -0.000677 (better) | 0.0e+00 | ja |
| H3 | A | S1 Anteil | 0.767475 (passed) | 0.767557 (passed) | 0.767674 (passed) | 2.0e-04 | ja |
| H3 | A | S2 Anteil | 0.777778 (passed) | 0.777877 (passed) | 0.777933 (passed) | 1.6e-04 | ja |
| H3 | A | S3 Anteil | 0.783006 (passed) | 0.783121 (passed) | 0.783124 (passed) | 1.2e-04 | ja |
| H3 | A | S30 Anteil | 0.893657 (reported) | 0.893916 (reported) | 0.893726 (reported) | 2.6e-04 | ja |
| H8 | A | S3 WLS-Steigung | -0.000087 (passed) | -0.000087 (passed) | -0.000087 (passed) | 0.0e+00 | ja |
| H2a | A | S1 max∣rel. Fehler∣ | 0.041972 (passed) | 0.041972 (passed) | — | 0.0e+00 | ja |
| H2c | A | Differenz | 0.009526 (passed) | 0.009526 (passed) | — | 0.0e+00 | ja |
| H2b ii | A | S3/B1 | 0.214359 (passed) | 0.214359 (passed) | — | 0.0e+00 | ja |
| H2b ii | A | S30/B1 | 0.876961 (passed) | 0.876961 (passed) | — | 0.0e+00 | ja |
| H1 | B | S1 | -0.000431 (grey_zone) | -0.000455 (grey_zone) | -0.000455 (grey_zone) | 2.4e-05 | ja |
| H1 | B | S3 | -0.004864 (better) | -0.004876 (better) | -0.004876 (better) | 1.2e-05 | ja |
| H4 | B | S1 | -0.000644 (grey_zone) | -0.000644 (grey_zone) | -0.000644 (grey_zone) | 0.0e+00 | ja |
| H4 | B | S3 | -0.000682 (better) | -0.000682 (better) | -0.000682 (better) | 0.0e+00 | ja |
| H2a | B | S1 max∣rel. Fehler∣ | 0.042256 (passed) | 0.042256 (passed) | — | 0.0e+00 | ja |
| H2b ii | B | S3/B1 | 0.215518 (passed) | 0.215518 (passed) | — | 0.0e+00 | ja |
| H2b ii | B | S30/B1 | 0.873229 (passed) | 0.873597 (passed) | — | 3.7e-04 | ja |

Urteile gleich in 23/23 Zeilen mit mindestens einer Sensitivitätsvariante.

Platt-Stufenmenge je Falte in den Primärläufen (ergebnisse/pruefe_stufen_*2v.json, geprüft gegen kern-Auswertung und {0,1,3,7}-Lauf):

- Design A: Prüfung ok; Stufen je Falte {"0": [0, 1, 3, 7], "1": [0, 1, 3, 7], "2": [0, 1, 3, 7], "3": [0, 1, 3, 7, 15, 31], "4": [0, 1, 3, 7], "5": [0, 1, 3, 7, 15], "6": [0, 1, 3, 7, 15], "7": [0, 1, 3, 7], "8": [0, 1, 3, 7, 15], "9": [0, 1, 3, 7, 15, 31]}; von {0,1,3,7} abweichend in 5/10 Falten (F3, F5, F6, F8, F9)
- Design B: Prüfung ok; Stufen je Falte {"0": [0, 1, 3], "1": [0, 1, 3], "2": [0, 1, 3], "3": [0, 1, 3, 7, 15], "4": [0, 1, 3, 7], "5": [0, 1, 3, 7], "6": [0, 1, 3, 7, 15], "7": [0, 1, 3, 7], "8": [0, 1, 3], "9": [0, 1, 3]}; von {0,1,3,7} abweichend in 7/10 Falten (F0, F1, F2, F3, F6, F8, F9)

Kehrseite: Falsch oder wertlos, wenn das private Ingestion-Programm vom öffentlichen streaming_ingestion.py abweicht (Split je Item, Zustand über Budgets, andere Zufallsquelle) — dann misst jeder Lauf ein anderes Protokoll; und weil alle Hypothesen aus denselben 142 Benchmarks stammen, belegt ein Bestehen nur Stabilität gegenüber Zufallsquellen (Saaten, Faltenzuteilung), nie Generalisierung auf neue Benchmarks. Zusätzlich: wechselt das eingereichte Paket (K1, Text-Prior, labeling.py), gilt diese Tafel nicht (Regel R1); die Phase-2-Zahlen nutzen je Falte die verschachtelte Stufenmenge, das Paket selbst die Schnittmenge über die Trainingsfalten — kein exakter Paket-Nachlauf (Differenz in der Größenordnung 1e-5, kern/KERN-DIFF.md §4).
