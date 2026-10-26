# Pre-registration v2 — confirmatory re-analysis plan for the PAIEC 2026 report (Christian Bucher)

Vorbemerkung (deutsch, für Chriso): Dieses Dokument wird nach dem Einfrieren nie mehr geändert. Sein sha256 steht in
`v2-plan/PRAEREG-HASH.txt` (mit `date -u`), im Bericht (Anhang B) und — nach Chrisos Push — als Git-Tag `prereg-v2`.
Nachträge gibt es nur als eigene, datierte Dateien `PRAEREGISTRIERUNG-v2-AMENDMENT-<n>.md` mit eigenem Hash (Regel R1,
BAUPLAN-V2 §1.3 Nr. 1). Der englische Text unten ist der Wortlaut für Anhang B. Autor der Einreichung ist Christian
Bucher; dieses Dokument wurde als Werkzeug-Output mit KI-Unterstützung (Claude Code) erstellt und ist von ihm zu lesen.

Frozen: 2026-10-20 (UTC time stamp in `PRAEREG-HASH.txt`). Status at freezing: no confirmatory run (seeds 200–202,
fold assignment 200) has been started; the first such run is package P4 of BAUPLAN-V2 §2.2 and starts only after
the hash file exists (file time stamps document the order).

---

## 0. Scope and honesty frame

1. **What is confirmed.** The hypotheses below arose from the analysis of one data release (measurement-db revision
   54074453; 156 benchmarks, 142 with ≥ 1 usable pair, 12 918 subject–benchmark pairs with ≥ 80 items) on the
   *discovery* randomness: fold assignment seed 1234 (`modell/ergebnisse/cv_A/falten.json`), split/acquisition/run-group
   seeds 0, 1, 2 (CV sets `cv_REG1`, `cv_REG2`, `cv_B`). They are tested here on *fresh* randomness only: fold
   assignment seed **200**, seeds **200, 201, 202**. No new benchmarks exist. Wording for the report:
   *"confirmatory with respect to sampling randomness (seeds and fold assignment), not with respect to the benchmark
   population; all hypotheses originated from the same 142 benchmarks."* The word "pre-registered" is not used in the
   abstract; the report says "confirmatory re-analysis on fresh seeds and fold assignment, with rules frozen before the runs".
2. **Model under test.** The *submitted* predictor: `predict` of package v2.0-core (`modell-v2/dist/paiec_v2core.zip`),
   which is mathematically v1 (`modell/dist/paiec_hier.zip`, sha256 f6e9d4eb…3d4e) plus hardening (fallback chain,
   parsing, threading) and must be **bit-identical** to v1 on `cv_REG1`/`cv_REG2` (max |Δq| = 0) — with the single
   documented exception that a nested Platt stage selection may change the stage set {0, 1, 3, 7}; if that happens, the
   changed predictor is the one that runs here and the change is stated in the report. If v2.0-core is not ready, v1 runs.
   **Rule R1:** if the submitted model changes later (stratum stage K1, text prior, `labeling.py`), *every* confirmatory
   run is repeated in full for the new model; the report cites confirmatory numbers only for the submitted model; this
   text is not edited — an amendment with its own hash records the change.
3. **Protocol fact stated in advance (affects several hypotheses).** In the competition interface a subject is only its
   visible field dictionary. Subjects with identical visible fields are indistinguishable; all predictors, including the
   organizers' baselines and our own, therefore count their labels together. In the discovery CV this inflates the
   number of "own" labels for ≈ 2 % of pair–budget rows (`n_eigen` > B; mean extra labels at B = 31: S2 +0.6, S3 +1.2,
   S30 +8.9, compact10 +10.1; none in S1). It is the reason why the beta-binomial curve is not identical across regimes.
   S1 is therefore the clean regime for the learning-curve test (H2a); S2–S30 are reported as sensitivity.

## 1. Data, designs, regimes, scripts

- **Design A** (benchmark-cold): 10 folds over the 142 benchmarks with test pairs, all pairs of a benchmark in one fold;
  training (abilities, hyper-parameters, calibration) on the other folds only. **Design B** (benchmark- and subject-cold):
  additionally 5 folds over subject names; evaluated on test-benchmark pairs with test names.
- **Fold assignment:** seed **200** (new parameter `--falten-saat` in the `modell-v2/kern` copy of `kreuzvalidierung.py`;
  the resulting `falten.json` must differ from `cv_A/falten.json` — mechanical check, logged).
- **Seeds (split, acquisition, run groups):** **200, 201, 202**. Each pair contributes the mean over the three seeds.
- **Regimes:** S1, S2, S3 (reported with equal standing), S30 (limiting case), compact10 (hypothetical upper bound:
  10 subjects share 100 common items). Budgets 0, 1, 3, 7, 15, 31; ALC weights 0.1/0.2/0.2/0.2/0.2/0.1.
- **Test pairs:** ≤ 30 per benchmark (fixed cap), pairs weighted equally (as in the competition); benchmark-balanced
  values reported in addition.
- **Predictors:** `hier_item` (submitted model), `hier_kalibriert` (pair level without item stage), `hier` and
  `hier_ohne_subjekt` (uncalibrated, for H4), `beta_binomial` (Beta prior fitted by marginal likelihood on the training
  folds; α+β =: κ_ML,f), `empirischer_mittelwert` (organizers' Empirical Mean), `konstant_0.5`.
- **Commands (from `modell-v2/kern/`, `python3 -I`, `OMP_NUM_THREADS=1`, `PAIEC_WORK` set):**
  `kreuzvalidierung.py --design A --saaten 200,201,202 --falten-saat 200 --S 1,2,3,30` (phase 1),
  `kreuzvalidierung.py --design A --phase 2 --von <phase-1 dir> --saaten 200,201,202 --falten-saat 200 --regime S1,S2,S3,S30,kompakt10`,
  the same for `--design B`; `auswertung.py`; new scripts `modell-v2/konfirmation/{lernkurve_test.py,v0_eff.py}`;
  `modell-v2/theorie/alc_law.py` for all formula values. Mechanical completion criterion: `status.json` → `fertig = 10`
  for each run; `hypothesen_tafel.json` with one entry per hypothesis (fields in §7).

## 2. Estimand and decision rule (all paired comparisons)

- **Estimand:** per-pair ALC (or per-pair Brier at a budget) of predictor X minus reference Y; mean over the three seeds
  per pair; pairs equally weighted; mean d̂ over the 2 142 (Design A) test pairs; standard error cluster-robust over
  benchmarks (`modell/metrik.py: cluster_vergleich`, Cameron & Miller 2015). Negative = X better.
- **Verdicts (fixed):**
  - *better*: d̂ + 2·SE < 0 · *worse*: d̂ − 2·SE > 0 ·
  - *equivalent* (no relevant effect): |d̂| + 2·SE < **0.001** ALC (margin fixed in advance: ≈ 1/5 of the v1–BB gap at S3) ·
  - *grey zone*: none of the above. "equivalent" may coincide with "better/worse" (a significant but irrelevant effect);
    both are then reported ("worse, below the relevance margin").
- **Operating characteristics (Regel 1, Betriebskennlinie).** Under a true null effect, P(*better*) = P(*worse*) =
  1 − Φ(2) = 2.28 % each (one-sided); the grey zone is 4 SE wide; the minimal effect detected with 80 % power is
  2.84·SE. At the decision point d̂ = −2·SE the 95 % CI is [−3.96·SE, −0.04·SE]. For the equivalence verdict,
  P(*equivalent* | true effect 0.001) ≤ 2.28 % by construction; P(*equivalent* | true effect 0) = 2Φ(0.001/SE − 2) − 1,
  i.e. the test is **undecidable when SE ≥ 0.0005**:

  | expected SE (from discovery) | 0.0001 | 0.0002 | 0.0003 | 0.0004 | ≥ 0.0005 |
  |---|---:|---:|---:|---:|---:|
  | P(equivalent \| null) | 100 % | 99.7 % | 82 % | 38 % | 0 % (not decidable) |
  | MDE (80 % power, 2-SE rule) | 0.0003 | 0.0006 | 0.0009 | 0.0011 | ≥ 0.0014 |
  | comparisons with this SE | E1 convex mixture | NPEB − BB, stacking | subject ablation (H4) | hier_item − BB, S1 | hier_item − BB, S2/S3/S30 |

  Consequence stated in advance: an equivalence verdict is reachable for H4 and H5; for H1 at S1 (SE ≈ 0.0004) only with
  38 % power — a grey-zone outcome there is the likely result and is reported as "not decidable at margin 0.001 (power 38 %)",
  not as a null finding. No comparison with SE ≥ 0.0005 is declared "equivalent".
- **Multiplicity:** about 20 directional two-sided verdicts are produced (H1 ×3, H2b ×6, H5 ×9, Liga ×k). Under a global
  null ≈ 0.5 false "better/worse" verdicts are expected; no correction is applied to any decision (there is no decision
  that depends on a single verdict except the gates in §6, which require several simultaneous conditions); the report
  states this expectation next to the table.

## 3. Learning-curve formula (used by H2a–H2c; derivation in `modell-v2/theorie/ANHANG-A.md`)

For a posterior-mean predictor q_B = (k + κμ)/(B + κ) under the protocol (N items per pair split 50/50 into acquisition
half A, N_A = ⌊N/2⌋, and evaluation half E; B labels drawn from A without replacement, one Bernoulli(p_i) response each;
scored against R_E = mean of p_i over E):

  E(q_B − R_E)² = [ B·(U − (B−1)·F) + κ²·V0 ] / (B + κ)²  +  [ B/(B + κ) ]·D      (B ≥ 1);   E(q_0 − R_E)² = V0,

with U = E R(1−R) (pair floor), V0 = E(μ − R_E)² (B0 excess), D = E(R̄_A − R_E)² = E[4·Var_i(p_i)/(N−1)] (split term),
F = E[Var_i(p_i)/(N_A − 1)] ≈ D/2 (finite-population correction). Implemented as `alc_law.lernkurve(..., split="exakt")`.
The approximation used in the discovery analysis (`d-wissenschaft/split.json`: squared split coefficient, D ≈ 2r(1−r)/N,
no finite correction; `split="quadrat"`) and the two-term textbook form (D = F = 0) are reported alongside as sensitivity
rows, never as the primary test. **Estimation recipes (fixed):** U = mean over test pairs × seeds of R_E(1−R_E) (equal to the
Brier of `beta_binomial` minus (q−R)², or directly from `R`); V0 = mean (q_0 − R_E)² of `beta_binomial`; κ = pair-weighted
mean of κ_ML,f over the folds of the run; D and F from `agg.parquet` for exactly the test pairs of the run (per-pair
Var_i(k_i/n_i), N = item count). Nothing is fitted to the curve. Discovery values (Design A, seeds 0–2): U = 0.18328,
V0 = 0.06734, κ = 2.7268, D = 0.001382, F = 0.000695.

## 4. Hypothesis table (frozen)

Status column: discovery value with its verdict under the rule in §2 (recomputed 2026-10-20 from `cv_REG2`), then the
pre-stated expectation for the confirmatory run. Every hypothesis is reported as it falls; failing hypotheses are
reported as negative findings with the same prominence.

| # | Hypothesis | Estimand, data | Rule | Discovery (seeds 0–2) | Expected | If it fails |
|---|---|---|---|---|---|---|
| **H1** | The submitted model beats the beta-binomial baseline when ≥ 2 subjects of a benchmark share `labeled`, not when one does. | ALC(hier_item) − ALC(beta_binomial), Design A, S1/S2/S3 primary, S30 reported; Design B S1/S3 secondary (reported) | S2 and S3: *better*. S1: *equivalent* if reachable, otherwise grey zone reported with power. | S1 −0.0003 ± 0.0004 (grey zone: 0.0003+0.0008 > 0.001), S2 −0.0030 ± 0.0006 (better), S3 −0.0047 ± 0.0007 (better), S30 −0.0130 ± 0.0013 | S2, S3 better; S1 grey zone (power 38 %) | "pooling gain" claim is dropped for the regime that fails; Table 1 shows the numbers either way |
| **H2a** | The formula of §3 (exact form, no fitted parameter) matches the beta-binomial learning curve in the clean regime and on a different test set. | relative error (formula − observed)/observed of (q_B − R_E)² at B = 1, 3, 7, 15, 31 for `beta_binomial`; Design A **S1** and Design B **S1**, seeds 200–202 | all five budgets within **±10 %** in both designs | Design A S1 (exact form): −0.1 / +0.1 / +0.8 / +0.4 / +0.3 %; (quadrat form: −0.7…−1.2 %; two-term: −0.8…−11.2 %); Design B not yet compared | ≤ 3 % at every budget; S2/S3/S30 reported as sensitivity with the identity-collision note (discovery S3 −0.4…−5.9 %, S30 up to −8.3 %) | report as "approximation within X % for the baseline, fails at budget Y"; §3 of the report keeps the decomposition and the bound ladder |
| **H2b** | Pooling across subjects acts as a budget- and S-dependent reduction of the prior error; the fixed-κ formula does not describe the pooled model. | (i) mean (q_B − R_E)² of `hier_item` at B = 1 and B = 3, paired per-pair differences between adjacent regimes S1→S2, S2→S3, S3→S30 (Design A); (ii) relative deviation of the fixed-κ formula (κ, U, D, F as in §3; V0 = hier_item B0 excess) from the observed hier_item curve at B = 1 in S3 and S30 | (i) each of the 6 steps *better* (d̂ + 2·SE < 0, i.e. strictly decreasing with S); (ii) deviation at S3/B1 in [+10 %, +30 %] and at S30/B1 in [+50 %, +110 %] | (i) B1: 0.04881 → 0.04444 → 0.04123 → 0.02718; B3: 0.03269 → 0.02874 → 0.02607 → 0.01918 (all steps large against SE ≈ 0.0003–0.0013); (ii) S3/B1 +17.6 %, S30/B1 +78.4 % | (i) 6/6 steps; (ii) inside both intervals | if a step is not *better*, the S-ordering claim is restricted to the steps that hold; if (ii) leaves the interval, the "V0(S, B)" description is reported as unstable across seeds |
| **H2c** | The likelihood-fitted prior strength of the beta-binomial baseline equals the ALC-optimal strength κ* = U/V0 (moment identity of a correctly specified Beta prior; a specification test, not a discovery). | κ̄_ML = pair-weighted mean of (α_f + β_f) over the 10 folds; U/V0 pooled over all Design A test pairs (S1, B0, seeds averaged); SE from a cluster bootstrap over benchmarks (2 000 draws, seed 200) | \|κ̄_ML − U/V0\| ≤ 2·SE_boot | U/V0 = 2.722, κ̄_ML = 2.731, difference −0.009; SE_boot = 0.309 (a ±0.3 window per fold, as first drafted, is < 1 SE and was discarded; per-fold values range 1.7–5.7 because V0 varies between benchmarks) | holds (P(fail \| identity true) ≈ 5 %; only a misspecification ≥ ≈ 0.6 is detectable) | reported as evidence that the Beta prior is misspecified in the ALC-relevant moments; the "κ* = κ" sentence is removed from the report |
| **H3** | At least 70 % of the submitted model's ALC-weighted excess over the pair floor R(1−R) lies at budgets 0–3, in every regime without item-stage dominance. | share = Σ_{B∈{0,1,3}} w_B·(Brier_B − R(1−R)) / Σ_B w_B·(Brier_B − R(1−R)) for `hier_item`, Design A, S1, S2, S3; cluster-bootstrap 95 % CI (2 000 draws, seed 200); S30 reported, compact10 excluded (item stage pushes B15/B31 below the floor; share undefined) | lower CI bound > 0.70 in S1, S2 and S3 | S1 0.772 [0.753, 0.788], S2 0.781 [0.761, 0.799], S3 0.785 [0.765, 0.805]; S30 0.892 [0.841, 0.959] | holds in all three | the sentence "the prior and the first three labels decide" is restricted to the regimes where it holds |
| **H4** | Subject identity (ability transfer from training benchmarks) has no relevant effect on ALC. | ALC(hier) − ALC(hier_ohne_subjekt), both uncalibrated, Design A S1/S2/S3; Design B S1/S3 secondary | *equivalent* (\|d̂\| + 2·SE < 0.001) in S1, S2, S3 | S1 −0.00048 ± 0.00035, S2 −0.00050 ± 0.00031, S3 −0.00051 ± 0.00028 — all **grey zone** by the rule (0.00107–0.00118 > 0.001; the earlier draft wording "passed narrowly" was wrong) | grey zone or equivalent (power 82 % under exact null; a true −0.0005 gives P(equivalent) = Φ(3) − Φ(0.33) ≈ 37 %) | if *better*: reported as a small real effect (< 1/4 of the pooling gain), the "subject knowledge carries little" sentence is kept with the number |
| **H5** | Neither a convex nor a logit-stacked combination of the submitted model with the baseline, nor a non-parametric marginal prior, changes ALC by a relevant amount. | (a) convex mixture(hier_kal, BB) − hier_kal; (b) logit stacking(hier_kal, BB) − hier_kal; (c) NPEB − beta_binomial; combiner weights per fold from the other 9 folds (`d-ensemble/ensemble.py` on the new sets); Design A S1, S2, S3 | *equivalent* in all nine comparisons **and** none *better* | (a) S1 −0.00003 ± 0.00012, S2 +0.00006 ± 0.00003, S3 +0.00005 ± 0.00003; (b) +0.00015 ± 0.00026, +0.00030 ± 0.00015, +0.00030 ± 0.00012 (S3: worse, below margin); (c) −0.00008, −0.00009, −0.00010 (± 0.00008) — all equivalent, none better | 9/9 equivalent, 0 better | a *better* combiner is reported as such; it enters the package only through the gate in §6 (it would be a model change) |
| **H6** | Visible non-text item aggregates do not predict the benchmark location at budget 0. | leave-one-benchmark-out R² of a ridge regression (λ ∈ {3, 10, 30, 100, 300} chosen by inner LOBO) from per-benchmark aggregates to mean pair rate R_b and to its logit; **feature set B, fixed now:** quantiles P10/P25/P50/P75/P90 of log text length, log item count, share of items with non-empty `item_features`, number of distinct keys, Shannon entropy of the key distribution, share of numeric-valued keys, indicators of the 20 most frequent key names (set A of `d-merkmale/b0lage.py` is the discovery set) | LOBO-R² ≤ 0.05 for both targets | set A: −0.024 (R), −0.025 (logit) | ≤ 0.02 | reported as "weak but non-zero signal"; the "why no text" paragraph then quantifies it |
| **H7** | The irreducible response-noise floor is material: per-benchmark median ≥ 0.02 Brier on benchmarks with ≥ 100 repeated (subject, item) cells. | L10 per benchmark = Σ n·k(n−k)/(n(n−1)) / Σ n over cells with n ≥ 2; median and IQR over benchmarks with ≥ 100 such cells; second, independent computation (P8, other code, other author) | median ≥ 0.02; the two computations agree within 1 % (else both values reported) | median 0.0488 (IQR 0.011–0.088), 62 benchmarks, one computation | holds; second path within 1 % | reported as computed; the floor sentence carries the IQR and the "subset of 62 benchmarks" qualifier in any case |
| **H8** | The item-stage gain grows with the number of evaluation items carrying foreign labels, approximately linearly up to ≈ 50 items, and saturates beyond. | per-pair item gain (item-wise Brier − pair-constant Brier) at B = 31 vs. the number of evaluation items with foreign labels, classes {0, 1–2, 3–5, 6–10, 11–20, 21–50, 51–100, > 100} with ≥ 20 pairs; weighted least squares of class means; cluster-bootstrap CI of the per-pair slope (500 draws, seed 200); Design A | (i) S3: slope < 0 with 95 % CI excluding 0 and R² of class means ≥ 0.8; (ii) S30: saturation — class means for 51–100 and > 100 are not more negative than 1.3 × the 21–50 class mean | (i) S3 slope −0.00009/item, R² 0.995; (ii) S30: 21–50 −0.0157, 51–100 −0.0125, > 100 −0.0138 (saturation); compact10 only two classes (−0.0071, −0.0361) | (i) and (ii) hold | the protocol-dependence statement is restricted to the range that holds; the saturation (or its absence) is reported |

## 5. Method-league comparison rule (package P3; applies to IRT 1PL/2PL, matrix factorisation, kNN, gradient boosting, pooled beta-binomial, NPEB, ensembles)

- Protocol identity is a precondition: `beta_binomial` and `empirischer_mittelwert` recomputed in the league harness must
  reproduce the CV sets exactly (max |Δq| = 0); without it no league number is reported.
- Each competitor is tuned only on the training benchmarks of its fold (inner 75/25 split over benchmarks, simulation seed
  100), grid and result documented (`hyper_*.csv`); a family without documented tuning is "not evaluated", never "beaten".
- Verdicts per family × regime (S1, S2, S3, S30, compact10) × budget use the rule of §2 in **both directions** and are
  reported identically whether v1 or the competitor wins. A competitor replaces the submitted model only if it is *better*
  in S1, S2 **and** S3, uses the standard library only, and passes the gate of §6 (Fri 2026-10-23 18:00 UTC).
- Families not finished by their time cap (2 h each) are reported as "not evaluated".

## 6. Conditional hypotheses — gates for any change of the submitted model (decision Fri 2026-10-23 18:00 UTC; rules only, no discretion; at most ONE model change until 2026-10-28; after a change Rule R1 applies)

| Candidate | Hypothesis (frozen) | Rule for entering the package | Also required |
|---|---|---|---|
| **K1 stratum stage** (pair → stratum → item, residualised d_i \| u_g; package P6) | HK1: ALC(hier_strat_item) − ALC(hier_item) < 0 at S3; no harm at S1, S2; the combined stage is at least as good as each single stage | S3 *better* (d̂ + 2·SE < 0) **and** S1 and S2 non-inferior (d̂ − 2·SE ≤ 0) **and** "both stages" ≤ each single-stage ablation, on discovery seeds 0–2 (then confirmation on 200–202 after the switch, R1) | failure case "strata without shrinkage harm" triggered once; empty `item_features` ⇒ bit-identical to v2.0-core; runtime < 2 ms per call at 10⁵ labels (fresh copy); pilot runnable by Thu 2026-10-22 12:00 UTC |
| **Text prior** (MiniLM embedding → d_i; package P9a, TEXTE.md H1–H5) | HT: ALC(hier_item + text prior) − ALC(hier_item) ≤ −0.003 at S3; S1 not inferior | S3 *better* with d̂ ≤ −0.003 **and** S1 non-inferior (d̂ − 2·SE ≤ 0) **and** TEXTE H5 (≤ 150 ms/item batch 1, first call < 30 s, model ≤ 90 MB bundled or `models.txt`) | disclosure of the pretrained model in the report; if both K1 and the text prior pass, the one with the larger confirmed S3 gain enters — never both |
| **`labeling.py` acquisition** (package P5; D-akquise §6.2) | HL: coverage acquisition is not worse than the platform's random policy in any regime/split and better in compact10 | D-akquise §6.2 verbatim: S1 decisions bit-identical to the sha256 replica (counter = 0) **and** non-inferior (d̂ − 2·SE ≤ 0) in S1, S3, S30, compact10 and both split designs **and** *better* in compact10 (round-robin) | organizer confirmation that the 50/50 split is per pair; pilot MDE in compact10 ≤ 0.0025 with 3 seeds, else 5 seeds (fixed before the run) |

If no gate passes, v2.0-core (or v1) is final and these candidates are reported as exploratory or negative findings.

## 7. Reporting commitments

- `modell-v2/konfirmation/hypothesen_tafel.json`: one object per hypothesis with fields `id, estimand, design, regime,
  seeds, rule, value, se, ci95, verdict ∈ {better, worse, equivalent, grey_zone, passed, failed, not_evaluated},
  discovery_value, source_file`. Verdicts are produced by code (`auswertung.py`, `lernkurve_test.py`, `v0_eff.py`,
  `alc_law.py`), not by hand; parse failures are fail-closed (`not_evaluated`, never a silent pass).
- Every number in the report's Table 2 points to a field of this file (`bericht-v2/ZAHLEN-QUELLEN-v2.md`), checked by
  `pruefe_zahlen.py` before each PDF build.
- Discovery values stay visible in the report as the "discovery set" column; nothing is re-tuned after the confirmatory
  run; if a confirmatory run is not finished in time, the report labels the discovery numbers as such and the
  confirmation is completed before 2026-10-27 or declared missing.
- What this plan does **not** decide: the submission itself (no gate here can prevent the submission of v2.0-core/v1),
  the data-audit findings (separate evidence standard), the related-work text.

## 8. Kehrseite (unter welcher Bedingung ist diese Präregistrierung falsch oder wertlos?)

Wenn das private Ingestion-Programm der Plattform vom öffentlichen `streaming_ingestion.py` abweicht (Split je Item statt
je Paar, Zustand über Budgets, andere Zufallsquelle), misst jeder Konfirmationslauf ein anderes Protokoll als den
Wettbewerb — die Hypothesen bleiben intern gültig, ihre Übertragung nicht; wenn die Identitätskollision (§0 Nr. 3) im
Summativlauf häufiger ist als in unserer Datenbasis (Anonymisierung der Subjektfelder), verschieben sich H1/H2b in
Richtung „mehr scheinbares Pooling"; und weil alle Hypothesen aus denselben 142 Benchmarks stammen, kann ein Bestehen auf
frischen Saaten nur Stabilität gegenüber Zufallsquellen belegen, nie Generalisierung auf neue Benchmarks.

**Abweichung vom Auftrag (eine Zeile):** Gegenüber D-wissenschaft §4 sind drei Regeln geändert, weil ihre Kennlinie auf
dem Discovery-Satz ungültig war — H2c (±0,3 je Falte → 2·Bootstrap-SE gepoolt, da ±0,3 < 1 SE), H8 (Linearität überall →
Linearität bis ≈ 50 Items plus Sättigung, da S30 schon auf Discovery R² 0,33 zeigt) und die Formel selbst (exakte Form mit
Koeffizient B/(B+κ), korrigiertem D und Endlichkeitskorrektur statt der Quadrat-Näherung; Anhang A) — und H4 ist ehrlich
als Grauzone statt „knapp bestanden" geführt; nichts wurde nach Sicht auf Konfirmationsdaten geändert, denn es gibt noch keine.

## 9. Amendment log

(none at freezing; amendments are separate dated files with their own sha256, listed here only by a later amendment file, never by editing this one)
