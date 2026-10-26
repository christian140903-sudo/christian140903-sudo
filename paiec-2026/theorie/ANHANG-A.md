# Appendix A — Derivations: decomposition, learning curve, bounds, protocol dependence, acquisition lemmas

Vorbemerkung (deutsch): Dieser Text ist der Entwurf für Anhang A des Berichts (P10 setzt ihn in LaTeX). Jede Zahl trägt
ihre Quelle; „discovery" = Design A, Saaten 0–2, `cv_REG2`; Konfirmationszahlen (Saaten 200–202) liefert P4 und ersetzt
hier nichts, sondern kommt als eigene Spalte dazu. Rechenwerkzeug: `./theorie/alc_law.py` (Standardbibliothek),
Tests `test_alc_law.py` (11/11, Fehlerfall ausgelöst, `test_alc_law.log`). Werkzeug-Output mit KI-Unterstützung; Autor der
Einreichung: Christian Bucher. Zugehörige Präregistrierung:
`v2-plan/PRAEREGISTRIERUNG-v2.md`, eingefroren 2026-10-20T20:26:04Z, sha256
e5fd821fdf6e2db3be86e1e341b02bc4199d4721790dd3ae8f027b60e9521ab7 (`v2-plan/PRAEREG-HASH.txt`). Hinweis für P10: die
Präregistrierung nennt den zweiten L10-Rechenweg „independent computation" — im Bericht als „a second computation with
different code" formulieren, nie „independent review" (J-jury §8).

## A.0 Notation and protocol assumptions

Pair (s, b): subject s evaluated on benchmark b with N distinct graded items; item i has n_i recorded responses with k_i
successes, p_i := k_i/n_i. The protocol (competition text and `streaming_ingestion.py`, re-implemented in
`modell/simulator.py`; assumptions marked [A]) does the following per pair and seed:

- **Split.** Items are permuted at random; the first N_A = ⌊N/2⌋ form the acquisition half A, the rest the evaluation half E. [protocol]
- **Acquisition.** Budget B reveals the first B items of A in permutation order (nested budgets 1 ⊂ 3 ⊂ … ⊂ 31); each
  revealed item contributes **one** response y_i ~ Bernoulli(p_i). k := Σ y_i over the B revealed items. [protocol; one response per item: A]
- **Scoring.** Brier over **all** recorded responses of the evaluation items: Brier_B = Σ_{i∈E} (n_i q_i² − 2 q_i k_i + k_i) / Σ_{i∈E} n_i,
  where q_i is the prediction for item i. With a pair-constant prediction q this equals (q − R_E)² + U_E, where
  R_E := Σ_E k_i / Σ_E n_i is the response-weighted mean of p_i over E and U_E := R_E(1 − R_E). [protocol]
- **Runs.** [A] S pairs of the same benchmark share `labeled`; the labels of the other S−1 subjects are visible. Subjects are
  identified by their visible field dictionary only; pairs with identical dictionaries are indistinguishable and their
  labels are counted together by every predictor (discovery: ≈ 2 % of pair–budget rows have more "own" labels than B;
  mean surplus at B = 31: S2 +0.6, S3 +1.2, S30 +8.9, compact10 +10.1; none in S1). [protocol consequence, measured]
- ALC := Σ_B w_B Brier_B with w = (0.1, 0.2, 0.2, 0.2, 0.2, 0.1) on B = (0, 1, 3, 7, 15, 31). [protocol]

## A.1 Exact per-pair decomposition

For any predictor that returns q_i for item i ∈ E,

  Brier_B = (q̄ − R_E)² + R_E(1 − R_E) + G_B,   G_B := Brier_B(item-wise) − Brier_B(pair-constant q̄),

where q̄ is the response-weighted mean of the q_i. *Proof.* Per item, (n q² − 2 q k + k)/n = q² − 2qp + p = (q − p)² + p(1 − p).
Averaging the pair-constant prediction q̄ over E with weights n_i gives Σ_w (q̄ − p_i)² + Σ_w p_i(1−p_i) =
(q̄ − R_E)² + Var_w(p) + mean_w p(1−p) = (q̄ − R_E)² + R_E(1 − R_E), using the identity mean(p)(1−mean(p)) = mean(p(1−p)) + var(p)
for the weighted mean R_E. G_B is the difference by definition and is non-zero only for predictors with item-level information. □

Consequences. (i) R_E(1 − R_E) is the floor of every pair-constant predictor; its ALC-weighted mean on the discovery test
pairs is **U = 0.18328** (2 142 pairs × 3 seeds, `cv_REG2`, constant across budgets). (ii) The gap (q̄ − R_E)² is the only
term a pair-level predictor can move; its Murphy decomposition (reliability − resolution + uncertainty) shows for the
submitted model reliability ≤ 0.0005 at every budget and resolution 0.0022 of Var(R_E) = 0.0667 at B = 0 — the B0 problem is
resolution, not calibration (C-FEHLERANALYSE §1.1). (iii) G_B is bounded below by the item-difficulty oracle: with perfect
item probabilities the score is Σ n_i p_i(1−p_i)/Σ n_i (ladder rung L10, §A.5).

## A.2 Learning curve of a posterior-mean predictor

**Setting.** Fixed prior mean μ and prior strength κ (Beta prior: κ = α + β), posterior mean q_B = (k + κμ)/(B + κ).
Write p̄_A := mean of p_i over A (unweighted — one response per item), p̄ := mean over all N items, δ := p̄_A − R_E.

1. q_B − R_E = [ (k − B p̄_A) + κ(μ − R_E) + B(p̄_A − R_E) ] / (B + κ).   (algebra; the three brackets are the
   sampling error, the prior error and the split error)
2. Given the split, k is a sum over B items drawn without replacement from A, each with an independent Bernoulli response:
   E[k | A] = B p̄_A and Var[k | A] = B·W_A + B·V_A·(N_A − B)/(N_A − 1), with W_A := mean_A p_i(1−p_i) and
   V_A := population variance of p_i over A. The first part is response noise, the second the between-item variance with the
   hypergeometric finite-population factor.
3. Cross terms with (k − B p̄_A) vanish because its conditional mean given the halves is 0.
4. Over a random split, δ is symmetric (swapping the halves changes its sign while μ − p̄ is invariant), so E[(μ − p̄)δ] = 0.
   With R_E = p̄ − δ/2 (equal halves, unweighted; A.0 caveats below): E[(μ − R_E)δ] = E[δ²]/2 = D/2, where D := E δ².
5. E[(μ − R_E)²] =: V0 is exactly the B0 excess (q_0 − R_E)² of the predictor and is used as measured.
6. Collecting: (B + κ)² E(q_B − R_E)² = B·E[W_A + V_A·(N_A−B)/(N_A−1)] + κ² V0 + B² D + 2κB·(D/2)
   = B·(U − (B − 1)·F) + κ² V0 + B(B + κ) D, using E[W_A + V_A] = E[R_A(1−R_A)] = U (same identity as in A.1, symmetric halves)
   and F := E[V_A/(N_A − 1)].
7. **Result.**
   E(q_B − R_E)² = [ B·(U − (B−1)·F) + κ²·V0 ] / (B + κ)² + [ B/(B + κ) ]·D,   E(q_0 − R_E)² = V0.
8. **Split term.** For a random halving of N values with population variance V, Var(mean_A) = V/(N − 1) and δ = 2(mean_A − p̄),
   hence D_pair = 4·V/(N − 1) and D = E[4·Var_i(p_i)/(N − 1)] — a protocol quantity (item count and 50/50 design), not a
   model error. Likewise F = E[Var_i(p_i)/(N_A − 1)] ≈ D/2. Both are computed from the item tables of the test pairs, not fitted.
9. ALC of the predictor: ALC = U + 0.1·V0 + Σ_{B≥1} w_B·E(q_B − R_E)²; the sum splits into a prior term Σ w_B κ²V0/(B+κ)², a
   sampling term Σ w_B B(U − (B−1)F)/(B+κ)² and a split term Σ w_B B·D/(B+κ).

**Disclosure of how this formula came about.** The two-term form (D = F = 0) is the textbook mean-squared error of a Beta
posterior mean (Morris 1983). The split term was added on 2026-10-20 *after* the two-term comparison with the baseline curve
showed a 13 % shortfall at B = 31 (`d-wissenschaft/lernkurve.json`); its first version (`split.py`) used
D ≈ 2r(1−r)/N and a squared coefficient [B/(B+κ)]². The derivation above (same day, before any confirmatory run) corrects
three things: the coefficient is B/(B+κ) (step 4 cross term), D is 4·Var_i(p_i)/(N−1) (step 8; the earlier value was low by a
factor ≈ 1.9 because R_A and R_E are perfectly anti-correlated given the pair, and because the relevant variance is that of
the p_i, which here nearly equals r(1−r) since most items have n_i = 1), and the finite-population factor F was missing. The
corrections partly cancel; none of U, V0, κ, D, F is fitted to the curve.

**Zero-fitted-parameter comparison, beta-binomial baseline, discovery set** (Design A, seeds 0–2; U = 0.18328,
V0 = 0.06734, κ = 2.7268 = pair-weighted mean of α_f + β_f, D = 0.001382, F = 0.000695; `p2work/formel_check.log`):

| regime | B | 1 | 3 | 7 | 15 | 31 |
|---|---|---:|---:|---:|---:|---:|
| **S1** (clean) | observed (q−R_E)² | 0.04966 | 0.03258 | 0.01938 | 0.01100 | 0.00612 |
| | exact form | −0.1 % | +0.1 % | +0.8 % | +0.4 % | +0.3 % |
| | discovery approximation (`split.json`) | −0.7 % | −1.1 % | −0.7 % | −1.2 % | −1.1 % |
| | two-term (no split, no F) | −0.8 % | −1.7 % | −2.7 % | −6.0 % | −11.2 % |
| S3 | observed | 0.04983 | 0.03286 | 0.01972 | 0.01137 | 0.00652 |
| | exact form | −0.4 % | −0.7 % | −0.9 % | −2.9 % | −5.9 % |
| S30 | observed | 0.04988 | 0.03285 | 0.01975 | 0.01150 | 0.00669 |
| | exact form | −0.5 % | −0.7 % | −1.1 % | −4.0 % | −8.3 % |

Reading. In S1 — the only regime in which the baseline's labels are exactly its own B labels — the exact form matches the
budget dependence within 0.8 % at every budget with nothing fitted; the previous approximation was within 1.2 %, the
two-term form fails at large budgets. The growing shortfall in S3/S30 is the identity collision of A.0 (surplus labels from
indistinguishable subjects of *other* pairs, which the formula does not model), not a failure of the three terms. Wording
rule for the report (J-skeptiker §2.4 Nr. 2): all moments are estimated from the same test pairs, so the statement is
"*the predicted budget dependence matches within X %*", not "*predicts*". ALC from the formula: 0.21319 against 0.21315
observed (S1); terms: U 0.18328, B0 0.00673, prior 0.01168, sampling 0.01072, split 0.00078. **Monte-Carlo check of the
derivation** (`test_alc_law.py` T2, synthetic pairs with the exact protocol mechanics, 600 pairs × 60 replications):
summed relative error of the exact form 1.5 %, of the discovery approximation 27.6 %.

## A.3 Validity limits (stated before the confirmatory runs)

1. **Fixed prior strength and a prior mean independent of the labels.** The submitted model is *not* such a predictor: its
   benchmark location is updated from the labels of the other S−1 subjects, so its effective V0 depends on S and B. Using the
   formula with the model's own B0 excess (0.06522) and the baseline κ overstates its (q−R_E)² at B = 1 by +17.6 % (S3) and
   +78.4 % (S30), with the deviation vanishing by B = 31 (+0.1 %, +2.2 %) — discovery, `formel_check.log`. The formula therefore
   describes posterior-mean predictors with fixed prior strength (the baseline, and the submitted model in S1 within
   1.7 %); for the pooled model it holds only with a budget- and S-dependent V0(S, B) — tested as H2b.
2. **Identity collision** (A.0): for S ≥ 2 some pairs receive labels of indistinguishable other subjects; the formula's "B" is
   then smaller than the label count actually used. Clean test: S1 (H2a); S2–S30 reported as sensitivity.
3. **Exchangeable items, one response per revealed item, equal halves, unweighted vs. response-weighted means.** R_E weights
   items by n_i, p̄_A does not; the two coincide when n_i is constant within the pair (69 % of test pairs); otherwise step 4 is
   approximate. For odd N the halves differ by one item. These effects are second order in 1/N (median N = 1 000, minimum 80).
4. **In-sample moments.** U, V0, D, F and κ are estimated on the same pairs whose curve is compared; the test is of the
   budget dependence (five points), not an out-of-sample prediction. Design B (different test pairs) and the fresh seeds of
   H2a are the closest we can get without new benchmarks.
5. **Assumption 6/step 6 uses E[R_A(1−R_A)] = E[R_E(1−R_E)]**, true by symmetry of the random split; with unequal
   weighting it is approximate (point 3).

## A.4 What follows from the formula

- **ALC-optimal prior strength.** For every budget B ≥ 1, d/dκ [B U + κ² V0]/(B+κ)² = 0 ⇔ κ = U/V0: the classical
  noise-to-signal ratio, independent of the ALC weights. For a Beta prior with correctly specified moments,
  Var R = μ(1−μ)/(κ+1) and E R(1−R) = μ(1−μ)·κ/(κ+1), hence U/V0 = κ *identically*. "κ* ≈ κ_ML" is therefore a test of the
  prior's specification in the two ALC-relevant moments, not an independent discovery (discovery: U/V0 = 2.722 vs
  κ̄_ML = 2.731, cluster-bootstrap SE 0.31; H2c). With the split term the optimum shifts slightly upward
  (κ* = 2.76 with D = 0.00138, F = 0.00070; `alc_law.kappa_opt`).
- **Where the loss sits.** With the discovery moments the formula puts 77.5 % of the ALC excess over U at budgets 0–3
  (observed baseline 77.2 %, submitted model 78.5 % in S3); the 1/(B+κ)² shape and the weights w_B fix this, so the prior and
  the first three labels decide the score and B = 31 contributes 2 % (H3).
- **Pair-level floor.** Even with a perfect prior (V0 = 0, also at B = 0) a predictor without item information cannot go below
  U + sampling + split = 0.18328 + 0.01072 + 0.00078 = **0.1948** ALC (discovery moments; the approximation gave 0.1945).
  The sampling term alone (0.0107) exceeds the whole gap between the submitted model and the baseline at S3 (0.0047): under
  this metric the competition is information-limited, not estimator-limited.
- **Pooling as prior-variance reduction.** The pooled model's gain over the baseline (S1 −0.0003, S2 −0.0030, S3 −0.0047,
  S30 −0.0130; MODELL §13.1) enters the formula only through V0(S, B) := the prior error after seeing the other subjects'
  labels; H2b tests the ordering S1 > S2 > S3 > S30 of (q−R_E)² at B = 1 and 3 and the size of the fixed-κ deviation.
- **Protocol parameters.** D and F scale with 1/N: D = 4·0.177/(N−1) is 0.0090 at N = 80, 0.0015 at N = 488, 0.0007 at
  N = 1 000 (per pair, V = 0.177). The item count per pair, the per-pair vs. per-item split and S move the attainable score
  more than any estimator choice within the text-free class (§A.6).

## A.5 Bound ladder and the noise-floor estimator L10

Rungs (C-FEHLERANALYSE §3.1, `c-fehleranalyse/leiter.json`; Brier at B = 0 unless marked ALC): L0 constant 0.5 → 0.2500;
L1 submitted model → 0.2485; L3' ability only → 0.2480; L2 benchmark-location oracle (LOO mean of the other pairs) → 0.2067;
L7 pair-rate oracle → 0.1833 (ALC floor U); L8 rate + LOO item difficulty → 0.1233; L10 response-noise floor; L9 oracle k/n over
all cells → 0.0065 (biased: n = 1 cells contribute 0).

**L10 estimator.** For a cell (s, i) with n ≥ 2 recorded responses and k successes, k(n − k)/(n(n − 1)) is unbiased for p(1 − p):
E[k(n−k)] = E[k]·n − E[k²] = n²p − (np(1−p) + n²p²) = n(n−1)p(1−p). Weighting cells by n (as the Brier does) over the 3.14 M
cells with n ≥ 2 (10.0 % of cells, 58.6 % of all 68.3 M responses) gives 0.0444; the per-benchmark distribution over the 62
benchmarks with ≥ 100 such cells has median **0.049**, IQR 0.011–0.088 (`d-wissenschaft/wiederholung.json`). It is a
*subset bound*: repeated responses exist only where curators recorded trials; the answer-weighted mean is dominated by one
benchmark (monkey_power_laws, 28.8 M of 40.0 M repeated responses), and some benchmarks show zero noise at n = 2 (greedy decoding or de-duplication,
[Vermutung]). Report wording: "on the 62 benchmarks with repeated responses, the per-benchmark noise floor has median 0.049
(IQR 0.011–0.088)". The two numbers 0.0065 (L9, oracle k/n including n = 1 cells, Brier at the item level) and 0.0229
(`orakel_kn_alle_zellen` in wiederholung.json) are different estimands; P8 reconciles their definitions before either is
printed, and `pruefe_zahlen.py` checks the appendices against each other.

## A.6 Protocol dependence (quantitative statements the report makes)

| protocol quantity | effect on the attainable score | source |
|---|---|---|
| subjects per benchmark sharing `labeled` (S) | gain vs. baseline −0.0003 (S1) → −0.0030 (S2) → −0.0047 (S3) → −0.0130 (S30) ALC; in the formula V0(S, B) | MODELL §13.1; H1, H2b |
| split per pair vs. per item | item-stage gain G_B exists only if evaluation items carry foreign labels; per item split ⇒ G_B ≡ 0 | REVIEW-2 SOLL-2; C §1.5 |
| items per pair N | D, F ∝ 1/N (A.4); fewer items ⇒ larger split floor | A.2 step 8 |
| items with foreign labels | G_B linear in their number up to ≈ 50 items (S3: −0.00009 per item at B = 31, R² 0.995), saturating beyond (S30 classes 21–50 / 51–100 / > 100: −0.0157 / −0.0125 / −0.0138) | discovery, H8 |
| indistinguishable subjects | surplus labels for ≈ 2 % of rows; shifts baseline curves between regimes by up to 9 % at B = 31 | A.0 |

## A.7 Acquisition lemmas (used in §6.8 of the report; from D-akquise §1.3 and §2.1)

**Weight of a label by rank.** The j-th acquired label is contained in all budgets B ≥ j, so its cumulative ALC weight is
W(j) = Σ_{B ≥ j} w_B = 0.9 (j = 1), 0.7 (j = 2–3), 0.5 (4–7), 0.3 (8–15), 0.1 (16–31); Σ_j W(j) = 8.3, of which labels 1–7
carry 52 %, 1–15 carry 81 %.

**Lemma 1 (fallback to random).** If no candidate item carries labels of other subjects (S = 1, or the first pair under a
pair-wise coordinator order), all candidates have identical information value, so any budget-respecting policy is
equivalent in expectation; a policy built on the platform's sha256-uniform with the same threshold is then *bit-identical*
to the random policy. *Proof.* The value V(s, i, j) of D-akquise §2.1 depends on i only through I_i and Var(d_i), which are
equal across items without foreign labels; ties are broken by the shared uniform, which is the random rule. □
(Mechanically checked in P5: counter of differing decisions = 0 on 10⁴ candidates.)

**Lemma 2 (ignorability; Rubin 1976).** If the purchase decision depends only on quantities that are conditionally
independent of the pair's own outcome y_{s,i} given the pool (presence of foreign labels, `context`, the sha256-uniform), the
acquired set is a random subset of the pool with respect to the outcomes; the sample mean and the (k, n) likelihood for R
remain unbiased, and `predict` needs no change. If the decision depends on an estimate d̂_i of item difficulty, the
selection is ignorable only when the likelihood conditions on d̂_i (missing at random given the conditioning variables);
otherwise it is biased in the direction reported for uncertainty sampling with the Empirical Mean (organizers' warning;
Kossen et al. 2021). *Proof sketch.* Rubin's condition: the selection mechanism depends on the data only through observed
quantities that are included in the model; coverage-based selection uses none of the pair's outcomes. □

## A.8 Reproduction and sources

- Formula values: `python3 -I ./theorie/alc_law.py --U 0.18328 --V0 0.06734 --kappa 2.7268 --D 0.001382 --F 0.000695`
  (`--split quadrat --F 0 --D 0.000732` reproduces `d-wissenschaft/split.json` and `alc_terme.json` to 1e-6; test T1).
- Moments from data: `$PAIEC_WORK/p2work/D_exakt.json` (V, W, D, F for the 2 142 test pairs from `agg.parquet`),
  `beobachtung_discovery.json` (observed (q−R_E)² per budget and regime), `formel_check.log`, `h2c_discovery.json`,
  `h3_h8_kennlinie.log`, `bb_regime_check.log` (identity collision). P4 recomputes all of them for seeds 200–202 and writes
  the confirmation column.
- Sources: C-FEHLERANALYSE §0–3; MODELL.md §4, §13.1; D-wissenschaft §3–4; D-akquise §1.3, §2.1; J-skeptiker §2.4;
  J-jury §2.2, §8; `modell/simulator.py` (protocol), `modell/baselines.py` (`_zaehle`: identity by visible fields);
  literature keys (BIBLIOGRAFIE.bib, checked 2026-10-20): `brier1950`, `murphy1973partition`, `gneiting2007proper`,
  `morris1983peb`, `efron1975stein`, `cameron2015cluster`, `guyon2011alc`, `lord1980irt`; to add with check date:
  `rubin1976` (DOI 10.1093/biomet/63.3.581, Crossref-checked 2026-10-20 19:34Z per J-skeptiker §1.4), `kossen2021activetesting`.

**Kehrseite (unter welcher Bedingung ist dieser Anhang falsch?):** Wenn die Plattform je Item mehrere Antworten als Labels
liefert oder die Bewertung nur eine Antwort je Item nutzt, ändern sich W, V und damit D und F (die Formel bleibt, die
Zahlen nicht); wenn die Konfirmation in Design B oder S1 mehr als 10 % Abweichung zeigt, ist die „information-limited"-
Erzählung auf Zerlegung und Leiter zu beschränken; und wenn die Identitätskollision im Summativlauf viel häufiger ist als
hier (2 % der Zeilen), beschreibt die Formel auch die Baseline nicht mehr sauber.
