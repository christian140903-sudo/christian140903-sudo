# PAIEC 2026: hierarchical pair-level predictor, predictability analysis and measurement-db audit

Code for a submission to the NeurIPS 2026 PAIEC competition (Stanford AIMS). A hierarchical logistic model predicts
P(response = 1) for a (subject, item) pair on a benchmark; the shipped package is stdlib-only (no language model, no network,
no files read at runtime). The accompanying report is licensed CC BY 4.0 (`report/`); the code is MIT (`LICENSE`).

Code, offline evaluation, data audit and the drafting of the accompanying report were developed with AI coding assistance
(Claude Code, Anthropic), as permitted by the competition rules; the author directed the work and is responsible for all content.
The submitted predictor uses no language model at runtime.

Status: version `v2.0.1-paiec` (= `v2.0-paiec` with the publication location updated, the report rebuilt and two provenance notes in `report/src/`
reworded; code, results and packages unchanged; the frozen pre-registration is `prereg/PRAEREGISTRIERUNG-v2.md`, sha256 `e5fd821f...`). **Submitted package: `modell/dist/paiec_v2core_final.zip`
(sha256 `3274b09524221ac268be41f8b52fc56ca341daf72cf9734561be00e0f3a1e331`), package v2.0-core.** `modell/dist/v1/paiec_hier.zip` is the
v1 predictor it is derived from and is not the submitted file. All numbers below are offline
leave-benchmark-out cross-validation results on the public release of the AI Measurement Data Bank at revision
`54074453da7b9911be0f48e4c560be547bc84d21`. They are self-computed, not platform scores; no leaderboard result is claimed.

Where this lives: folder `paiec-2026/` on branch `claude/technosignatures-archive-analysis-nxoino` of the public repository
`christian140903-sudo/christian140903-sudo`: https://github.com/christian140903-sudo/christian140903-sudo/tree/claude/technosignatures-archive-analysis-nxoino/paiec-2026
The folder is a snapshot (`git archive`) of version `v2.0.1-paiec`; the project's own git history and its tags (`prereg-v2`,
`v2.0-paiec`, `v2.0.1-paiec`) are not part of it. To get it:
`git clone --branch claude/technosignatures-archive-analysis-nxoino --depth 1 https://github.com/christian140903-sudo/christian140903-sudo && cd christian140903-sudo/paiec-2026`
Here and in the report, "repository root" means this folder; all commands below run from it.

## Submitted package (v2.0-core) and the v1 predictor

The submitted file is `modell/dist/paiec_v2core_final.zip` (`model.py` plus `README.md`). Its `model.py` is byte-identical to the one in
`modell/dist/paiec_v2core.zip` (sha256 `62d2a1d2d629048cac081b93c9c4c33ec9070ad24633e5d7e2bc8b9a7dd58e33`), the file that passed the
failure-case protocol, the package check and the bit-identity comparisons; only the README was corrected before submission
(`modell/paket/baue_paket.py --model-py`). v2.0-core is the v1 predictor with hardening of the interface (fallback chain, label parsing,
thread lock, runtime limits; `modell/KERN-DIFF.md`) and with the Platt recalibration stages 3 and 7 removed: the stage set {0, 1} is the
intersection of the nested per-fold selections (stage 3 was selected in 8 of 10 folds, stage 7 in 7 of 10). Evidence in this repository:
phase 1 of the cross-validation is bit-identical to v1 (1,079,568 prediction sets, max |dq| = 0); phase 2 differs from v1 only in the
Platt stages 3 and 7 (pair-level ALC shift between +2e-5 and +7e-5, `modell/ergebnisse_v2/`); 26 unit tests;
`modell/ergebnisse_v2/pruefe_paket_v2core_final.json` is the package check of the submitted ZIP. The confirmatory runs (`konfirmation/`)
used, per fold, that fold's nested stage set rather than the package's exact set; the sensitivity runs with the v1 stage set gave the same
verdict in all 23 comparison rows (report, Appendix B). The discovery tables and the method league were computed along the v1 path.

## Layout

| Path | Content |
|---|---|
| `modell/` | training, cross-validation, evaluation, tests (`daten.py`, `training.py`, `kreuzvalidierung.py`, `auswertung.py`, `inferenz.py`, ...); code comments are partly German |
| `modell/basis/` | `build_basis.py`, `hfio.py`: build the local data base from measurement-db (Step 0b) |
| `modell/paket/`, `modell/dist/` | package build and check; `state_final.json` (v1 fitted state), `state_v2core.json` (Platt stages {0, 1}); `paiec_v2core_final.zip` (submitted), `paiec_v2core.zip` (same `model.py`, earlier README), `model.py`, `README.md`, `v1/paiec_hier.zip` |
| `modell/ergebnisse/`, `modell/ergebnisse_v2/` | aggregated cross-validation outputs (JSON/CSV) of phase 1 and phase 2 |
| `modell/fehlerfaelle/` | failure-case protocol F1-F7 (each case run red, then green) |
| `theorie/` | `alc_law.py` (learning-curve law under the protocol, stdlib only), tests, `ANHANG-A.md` (derivations; German working draft) |
| `curation/` | scripts and count/identifier tables of the data-curation check (no item text), see `curation/README.md` |
| `audit/` | identifier/count lists of the measurement-db audit and proposed patches; `LIZENZ-PRUEFUNG.md` |
| `konfirmation/` | confirmatory re-analysis (seeds 200-202, fold seed 200, Designs A and B): code, `hypothesen_tafel.json` (10 hypotheses: 9 passed, H4 failed), `HYPOTHESEN-TAFEL.md` (table and stage-choice sensitivity), `auswertung_K.json`, `ergebnisse/` (JSON/CSV); not part of `make` |
| `liga/` | method league: code and `ergebnisse/` (all 10 folds; aggregated CSV/JSON, grid-edge checks `hyper_rand*.csv`; the 3 MB per-pair file is available on request); not part of `make` |
| `akquise/` | acquisition pilot: code snapshot without results of the aborted full run; not part of `make` |
| `report/` | the report PDF (CC BY 4.0) and its source `report/src/` (LaTeX, tables, figures, data files, build and check scripts; `make report-tabs`, `make report-figs`) |
| `prereg/` | the frozen pre-registration and its SHA-256 |
| `reference/` | reference predictions of fold 0 (seed 0) for `make smoke` |
| `scripts/` | `download_data.py` (Step 0a) and SHA-256 checksums |
| `SHA256SUMS` | checksums of all tracked files (checked by `make hash-check`) |

Comments and German working notes inside the code and in the shipped Markdown files refer to internal planning and review notes
(labels such as "BAUPLAN-V2 §2.2 P5", "D-akquise §6.2", "GEWINNERWEG", "REVIEW M3", "STATUS.md") that are not part of the repository;
they document the author's workflow and carry no information needed to run the code.

## Results (cross-validation, pair-level ALC, lower is better)

142 benchmarks, 2,142 pairs after the 30-item cap, 10 folds, seeds 0-2. "S" is the number of subjects per benchmark whose labels share one
`labeled` set at test time; the platform value is not publicly documented, so regimes are reported side by side. Differences are mean
+/- cluster-robust SE (clusters = benchmarks). Source: `modell/ergebnisse_v2/auswertung_V2K2.json` (phase 2 with the nested per-fold
Platt-stage choice, the computation `make tab1` reproduces). The report's discovery tables use the v1 path
(`modell/ergebnisse/cv_A_p2_S1-S2-S3-S30-kompakt10/auswertung.json`: S1 -0.0003, S2 -0.0030, S3 -0.0047, S30 -0.0130 against
Beta-Binomial); the two paths differ by +2e-5 to +7e-5 ALC. Confirmatory values on fresh seeds (Design A, `konfirmation/hypothesen_tafel.json`,
H1): S1 -0.0004 +/- 0.0004 (grey zone), S2 -0.0031 +/- 0.0006, S3 -0.0049 +/- 0.0007, S30 -0.0132 +/- 0.0012 (better).

| Regime | This model | Beta-Binomial | Empirical Mean (organizer) | Model - Beta-Binomial | Model - Empirical Mean |
|---|---:|---:|---:|---:|---:|
| S1 | 0.2129 | 0.2132 | 0.2479 | -0.0002 +/- 0.0004 (no difference) | -0.0350 +/- 0.0024 |
| S2 | 0.2104 | 0.2133 | 0.2475 | -0.0029 +/- 0.0006 | -0.0371 +/- 0.0021 |
| S3 | 0.2087 | 0.2134 | 0.2475 | -0.0047 +/- 0.0007 | -0.0387 +/- 0.0020 |
| S30 (edge case) | 0.2005 | 0.2135 | 0.2470 | -0.0129 +/- 0.0013 | -0.0465 +/- 0.0021 |
| compact10 (hypothetical upper bound) | 0.1968 | 0.2158 | 0.2504 | -0.0190 +/- 0.0014 | -0.0536 +/- 0.0028 |

Most of the gap to the organizer baseline comes from simple Bayesian smoothing (Beta-Binomial vs Empirical Mean is about -0.034); the model
adds nothing measurable in S1 and 0.003-0.005 in S2/S3. These results were not confirmed on the platform's hold-out data. They would not hold if
the platform draws one subject per benchmark or filters `labeled` per pair (then only the gap to Empirical Mean remains).

## Reproduce

Requirements: Python 3.13 (3.11+ expected to work), numpy, pandas, pyarrow, scipy, requests, matplotlib for `plots.py`; exact versions in
`environment.txt`. `PAIEC_WORK` is the only path parameter (default `./work`). The raw data are not included.

```bash
make smoke      # hash check + unit tests + fold 0 of the cross-validation (1 process) + comparison to reference/ at 1e-9; needs the data (below)
make test       # unit tests only (no data needed)
make hash-check # SHA256SUMS and the pinned hashes of state_final.json, the submitted paiec_v2core_final.zip, paiec_v2core.zip and v1/paiec_hier.zip (no data needed)
make all        # tests, hash check, package check, phase 1 and phase 2 tables, figures (needs the data)
```

Data: `aims-foundations/measurement-db` is a gated Hugging Face dataset: create your own account, accept the access conditions on the dataset
page, create a read token and export it (`export HF_TOKEN=...`, only read from the environment).

```bash
export PAIEC_WORK=$PWD/work HF_TOKEN=...      # your own token
make step0      # 0a: small tables at the pinned revision, SHA-256 checked; 0b: local data base (large download, range requests)
make daten      # 0c: selection + aggregation -> $PAIEC_WORK/modell/agg.parquet
make smoke
```

Steps 0a and 0b (`scripts/download_data.py`, `modell/basis/build_basis.py`) need a token and were not run live for this snapshot; the later steps were run on
the author's local data base built earlier by the same scripts.

Timing: fold 0 of the smoke takes about 40 s on one core (measured). `make all` was not timed as one run; the logged phases of the author's
runs (phase 1: about 6 min, phase 2: about 13 min, 4 processes, shared machine) suggest 20-30 min on four free cores [estimate, not measured here].
`make smoke` compares a freshly computed fold with stored predictions; it checks that the code reproduces the author's numbers, not that the numbers are right.

## Report source and result files

`report/paiec_report_v2.pdf` is the submitted report; `report/src/` holds its LaTeX source, `refs.bib`, the generated tables
(`tabellen/`), figures (`abbildungen/`) and the small JSON/CSV files they are built from (`daten/`, provenance in `daten/HERKUNFT.md`).
`make report-tabs` and `make report-figs` rebuild tables and figures from `modell/ergebnisse/`, `konfirmation/`, `liga/ergebnisse/`,
`curation/` and `report/src/daten/` (the scripts detect the repository layout). `report/src/pruefe_zahlen.py` (the fail-closed number check
run before every PDF build) and `report/src/Makefile` target `pdf` refer to files of the author's working tree that are not in this repository
(the data-quality report with record excerpts, the pre-registration hash file, the package under its working-tree path) and are included for
inspection. In the copied JSON files, absolute paths of the author's machine were replaced by `$PAIEC_WORK`, `$SCRATCH` and `./`; no number was changed.

## Not included

Experimental extensions that were not evaluated to completion (a feature-stratum stage, an item-text prior) are neither part of this
repository nor of the package. The raw data and item texts are not redistributed; each upstream benchmark keeps its own terms.

## License

Code: MIT (c) 2026 Christian Bucher. Report: CC BY 4.0. Data: not redistributed here. See `LIZENZ-PRUEFUNG.md` for what was checked in `curation/` and `audit/`.
