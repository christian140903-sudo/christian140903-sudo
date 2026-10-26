# Hierarchical logistic pair-level predictor (PAIEC 2026), package v2.0-core

`model.py` is self-contained: Python standard library only, no network, no LLM, no files read at runtime. The fitted
state (subject abilities, metadata regression, hyperparameters, recalibration) is embedded as JSON text.

## Method in one paragraph

For a subject s on a benchmark b, the success rate is modelled as `logit r_sb = c_b + a_b * m_s + v_sb`. `m_s` is the
subject's ability, learned on the public measurement-db release (revision 54074453, 156 graded binary public
benchmarks) and looked up by `normalized_name`; unseen names get a ridge regression on visible metadata (provider,
release date, name tokens, parameter count parsed from the name). The benchmark location `c_b` and slope `a_b` are
unknown for a held-out benchmark; their Laplace posterior is computed from the revealed labels of all subjects of that
benchmark in `labeled` (grouped by the anonymous `benchmark_id`). `v_sb` is the pair's own deviation, learned from its
own labels. The hyperparameters were fitted by Gaussian marginal likelihood on inner leave-benchmark-out folds. The
prediction is the posterior mean of the sigmoid (probit approximation), followed by a Platt recalibration at label
stages 0 and 1 (a pair's label count 0 or 1-2). Platt scaling per label stage: v1 kept the stages whose cross-fitted
Brier was lower (B0 -0.0042, B1 -0.0009, B3/B7 -0.00002; point estimates, stage choice on all folds); v2.0-core keeps
only stages 0 and 1, the intersection of the nested per-fold selections (stage 3 was selected in 8 of 10 folds, stage 7
in 7 of 10, stages 15 and 31 in at most 2). Items without `benchmark_id` get the prior prediction.

Item stage: if `labeled` contains responses of other subjects to the same item (same `item_content` and
`item_features` within the same `benchmark_id`), the target item gets a Laplace posterior offset
`d_i ~ N(0, tau_i2)` (tau_i2 = median empirical-Bayes Rasch item variance of the training benchmarks). Without such
labels the prediction equals the pair-level one exactly.

No `labeling.py`: the platform's random acquisition is used.

## Relation to v1 and to the reported cross-validation numbers

v2.0-core is the v1 predictor (`paiec_hier.zip`) with hardening of the interface and with the Platt stages 3 and 7
removed. On the phase-1 cross-validation sets (1,079,568 prediction records) its predictions are bit-identical to v1.
In phase 2 they differ from v1 only for pairs with 3-14 own labels (the removed Platt stages): individual predictions
by up to 0.024, the pair-level ALC by less than 1e-4 in every regime (at most a fifth of a standard error, never
significant). The discovery cross-validation and the method league in the report were computed along the v1 path; the
confirmatory runs used, per fold, the nested stage set of that fold (sensitivity runs with the v1 stage set gave the
same verdict in all 23 comparison rows). No cross-validation was rerun with exactly the package's stage set {0, 1}.

Robustness (v2.0-core): `predict` never raises. If the hierarchical model fails on an input it falls back to a
beta-binomial estimate from the pair's own labels (prior alpha, beta embedded in the state), and only if that fails
too to the constant 0.5. Labels are accepted as bool, int, float or strings ("1", "true", "yes", ...); unreadable
labels (None, NaN, other text) are skipped. On 10,000 competition-shaped inputs the fallback was never taken.

Runtime: `labeled` is grouped once per distinct label set. Up to 1,024 labels the set is identified by a hash over all
labels; above that by its length and 64 evenly spaced entries, so the per-call cost does not grow with the size of
`labeled` (this relies on `labeled` being the same for all inputs of a checkpoint and growing between checkpoints, as in
the platform protocol). Calls are serialised with a lock because the model keeps lazy caches.

## Data and licence

Fitted on `aims-foundations/measurement-db` (Hugging Face, revision `54074453da7b9911be0f48e4c560be547bc84d21`), curation
licensed CC BY-SA 4.0, individual benchmarks under their upstream licences. The embedded state contains only derived
parameters (one ability value and its variance per `normalized_name`, regression weights, hyperparameters); no item
text and no responses. Excluded from training: 64 bird_sql configurations graded 0 on all 360 questions and 12
swebench_live subjects carrying only successes (see the accompanying data-quality report).
