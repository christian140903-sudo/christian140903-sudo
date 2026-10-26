# liga/ — method league under the same protocol

Comparison of the submitted predictor (along the v1 computation path, records from the phase-2 cross-validation) with further
text-free families under one protocol: IRT 1PL/2PL, matrix factorisation, kNN over subjects, gradient boosting, stacking, the
beta-binomial and empirical-mean baselines and the constant. Discovery seeds 0-2, all 10 folds, test pairs capped at 30 per
benchmark; hyperparameters of every family chosen on the training benchmarks of each fold (inner 75/25 split, seed 100).

- `liga_methoden.py`, `liga_cv.py`: the families and the fold runner; `liga_auswertung.py`, `liga_vergleich.py`, `liga_tabellen.py`:
  aggregation, paired comparisons (cluster-robust SE over benchmarks), tables; `liga_rand.py`: grid-edge checks (`--nachtrag` for the
  lower edges).
- `ergebnisse/`: `vergleich_gepaart.csv` (paired ALC differences method - ours per regime, with 95 % CI and verdict), `rangfolge.csv`,
  `brier_je_budget*.csv`, `hyper_wahl.csv`, `hyper_gitter.csv`, `hyper_rand*_f{2,8}.csv` (grid edges on two folds), `identitaet_protokoll.csv`
  (beta-binomial and empirical mean recomputed in this harness: max |dq| = 0 against the cross-validation records, the precondition for
  the league), `laufzeit.csv`, `liga_vergleich.json`, `meta.json` (folds, seeds), `tabellen_liga.md`. The 3 MB per-pair file is available
  on request.
- Not part of `make smoke` or `make all`; `make report-tabs` and `make report-figs` read `ergebnisse/`.

Reading: with one subject per benchmark no learned family is distinguishable from ours by the decision rule (grey zone), gradient boosting
and the unsmoothed baselines are worse; from two subjects on no family is better in any regime and 23 of 35 family-regime comparisons are
worse. "No difference shown" is not "equally good" (CI width about +/- 0.001). Asymmetry: the submitted predictor was developed on the
same 142 benchmarks; the families had one inner search per fold.
