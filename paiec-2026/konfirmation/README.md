# konfirmation/ — confirmatory re-analysis on fresh seeds

Code and results of the confirmatory runs (seeds 200-202, fold assignment 200; Design A benchmark-cold, Design B benchmark- and
subject-cold) against the hypothesis table frozen in `../prereg/PRAEREGISTRIERUNG-v2.md` before any confirmatory run.

- `hypothesen_tafel.json`: one object per hypothesis (`id, estimand, design, regime, seeds, rule, value, se, ci95, verdict,
  discovery_value, source_file, teile`); verdicts are produced by `tafel.py`, fail-closed to `not_evaluated`. Final state: 9 passed,
  H4 failed (subject identity has a small real effect, not equivalent at the margin 0.001). `HYPOTHESEN-TAFEL.md` renders the table and
  the sensitivity of the verdicts to the Platt-stage choice (primary = nested per-fold choice; sensitivity = v1 stage set {0,1,3,7} and the
  v1 pooled choice; all 23 comparison rows keep their verdict).
- `auswertung_K.json`, `ergebnisse/`: the aggregated outputs the table is built from (`h_cv_A/B.json`, `lernkurve_A/B.json`, `v0_eff_A.json`,
  `ensemble_A.json`, `b0lage_K.json`, `wiederholung_K.json`, `pruefe_stufen_A2v/B2v.json` = the stage set used per fold, `pruefe_fertig.txt` =
  the mechanical completion check, `sensitivitaet_*/`). The per-record Parquet files are not included (size).
- `code_v1/`: the v1 cross-validation code with three lines taken over from `../modell/` for the nested stage choice (`CODE-DIFF.md`).
- The shell drivers used for the runs contained machine-specific paths and are not included. The folder is not part of `make smoke`
  or `make all`; `make report-tabs` reads `hypothesen_tafel.json`.

The model under test is package v2.0-core (`../modell/dist/paiec_v2core_final.zip`, same `model.py` as `paiec_v2core.zip`); the runs
used, per fold, that fold's nested Platt-stage set rather than the package's exact set {0, 1} (report, Appendix B, deviation 1).
