# Delivered to CIRCL: two packages for VulnTrain datasets

[← CIRCL details](../README.md) · [← Overview](../../README.md)

Two packages, one per contribution. Each folder holds copies of the delivered files; the README of each package is a
public copy with a note at the top.

- [`vulnerability-scores-fix/`](./vulnerability-scores-fix/), delivered on 28 October 2026: three patches, a leakage
  check, an evaluation script and unit tests for `CIRCL/vulnerability-scores`. CIRCL released the patches and the
  leakage check in VulnTrain 3.4.0. [Details below](#1-october-2026-vulnerability-scores-fix).
- [`vulnerability-fstec-fix/`](./vulnerability-fstec-fix/), delivered on 3 November 2026: three patches, the list of
  affected rows with its counts, and three scripts for `CIRCL/Vulnerability-FSTEC`. CIRCL released the patches in
  VulnTrain 3.5.0 on 4 November 2026. [Details below](#2-november-2026-vulnerability-fstec-fix).

## 1. October 2026: `vulnerability-scores-fix/`

**Delivered:** 28 October 2026, to CIRCL (the maintainers of VulnTrain), as one package (`vulnerability-scores-fix.zip`).
**Refers to:** dataset revision `34e6a14` of `CIRCL/vulnerability-scores` and VulnTrain commit `8134623`.
**This copy:** the files below are byte-identical to the delivered ones, except the README (public copy, see the last row).

| File | What it is | Public today |
|---|---|---|
| [`patches/0001-new-dataset-group-aware-train-test-split-description.patch`](./vulnerability-scores-fix/patches/0001-new-dataset-group-aware-train-test-split-description.patch) | Group-aware split in `create_dataset.py` (new `vulntrain/datasets/grouping.py`), removal of repeated documents, `aliases` column, dataset card (`git format-patch`) | Same code in commit [`7ad1525`](https://github.com/vulnerability-lookup/VulnTrain/commit/7ad1525c0d7ecafee26586fdee4124e4eb0fa791), VulnTrain 3.4.0 |
| [`patches/0002-fix-utils-score-every-CVSS-4.0-vector-with-one-readi.patch`](./vulnerability-scores-fix/patches/0002-fix-utils-score-every-CVSS-4.0-vector-with-one-readi.patch) | `utils.py`: every CVSS 4.0 score from its vector with one function; switch `CVSS4_BASE_ONLY` for base metrics only (CVSS-B) | Same code in commit [`595aa75`](https://github.com/vulnerability-lookup/VulnTrain/commit/595aa754f61439e0f5cd541a3d508cf96c957939), VulnTrain 3.4.0 |
| [`patches/0003-chg-trainers-select-checkpoints-on-a-validation-spli.patch`](./vulnerability-scores-fix/patches/0003-chg-trainers-select-checkpoints-on-a-validation-spli.patch) | `classify_severity.py` selects checkpoints on `validation` if the dataset has one | Same code in commit [`1b521f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/1b521f4bc741d101cb272393ed5b8632d5d32ae4), VulnTrain 3.4.0 |
| [`scripts/check_split_leakage.py`](./vulnerability-scores-fix/scripts/check_split_leakage.py) | Overlap report for any dataset revision; with `--max-shared-groups 0` it exits 1 when groups span splits (CI gate) | Commit [`42131f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/42131f4de01333e2ee3320a1cfa78a41b040eed8) as [`tools/dataset/check_split_leakage.py`](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/tools/dataset/check_split_leakage.py); identical except two lines CIRCL added (an empty line and "Contributed by Christian Bucher …") |
| [`scripts/eval_seen_unseen.py`](./vulnerability-scores-fix/scripts/eval_seen_unseen.py) | A model's test accuracy on rows with and without a train twin, from a predictions file | Not in the repository; named in the report's acknowledgements ("the leakage and seen/unseen evaluation scripts") |
| [`scripts/tests/test_package.py`](./vulnerability-scores-fix/scripts/tests/test_package.py) | 10 unit tests for the patch helpers and both scripts | Not in the repository |
| [`README.md`](./vulnerability-scores-fix/README.md) | How to apply the patches, notes, what was and was not run | **Public copy:** two notes about other datasets built by the same pipeline are left out and marked in the text; nothing else is changed |

Not part of this copy:

- `data/twin_flags_test_34e6a14.csv`: one row per test row of revision `34e6a14` (82,314 rows, flags only, no text,
  3.6 MB), left out because of its size. CIRCL's report: "the per-row flags match his on all 82,314 test rows". The
  leakage check writes such a file for any downloaded revision:
  `python3 check_split_leakage.py --data-dir <revision> --flags-out twin_flags.csv` (example in its docstring).
- `SHA256SUMS` of the original package (its line for the README no longer applies to the public copy).

The relative paths in the README (`patches/`, `scripts/`) work in this folder.

## 2. November 2026: `vulnerability-fstec-fix/`

**Delivered:** 3 November 2026, to CIRCL, as one package (`vulnerability-fstec-fix.zip`).
**Refers to:** VulnTrain `main` at `dbd0de0`; revisions `5bd7fba` and `c890dd1` of `CIRCL/Vulnerability-FSTEC`; the
Vulnerability-Lookup dump `fstec.ndjson` of 2026-10-04.
**This copy:** all files are byte-identical to the delivered ones, except the README (public copy) and `SHA256SUMS`
(see the last two rows).

| File | What it is | Public today |
|---|---|---|
| [`patches/0001-fix-dataset-read-the-FSTEC-CVSS-v3-and-v4-vectors-mi.patch`](./vulnerability-fstec-fix/patches/0001-fix-dataset-read-the-FSTEC-CVSS-v3-and-v4-vectors-mi.patch) | Reads the stored v3 and v4 vectors: adds the missing `CVSS:3.0/` / `CVSS:4.0/` prefix and reports a vector that still cannot be read (`git format-patch`) | Same code in commit [`483f4ee`](https://github.com/vulnerability-lookup/VulnTrain/commit/483f4ee9fc8b09216cac67d580852abb3063b798), VulnTrain 3.5.0 |
| [`patches/0002-fix-dataset-score-the-FSTEC-CVSS-4.0-vectors-as-CVSS.patch`](./vulnerability-fstec-fix/patches/0002-fix-dataset-score-the-FSTEC-CVSS-4.0-vectors-as-CVSS.patch) | Scores the FSTEC v4.0 vectors with `cvss4_score()`, i.e. CVSS-B like every other source | Same code in commit [`947e608`](https://github.com/vulnerability-lookup/VulnTrain/commit/947e608a982580359773437cced1694748143af5), VulnTrain 3.5.0 |
| [`patches/0003-chg-dataset-FSTEC-cve_id-one-CVE-id-other-identifier.patch`](./vulnerability-fstec-fix/patches/0003-chg-dataset-FSTEC-cve_id-one-CVE-id-other-identifier.patch) | `cve_id` holds the first CVE id; the BDU field of other identifiers is kept in a new column `other_identifiers` | Same code in commit [`765d7b6`](https://github.com/vulnerability-lookup/VulnTrain/commit/765d7b667cdd933a758fbc40cedb003844841f0c), VulnTrain 3.5.0 |
| [`data/affected_rows.csv.gz`](./vulnerability-fstec-fix/data/affected_rows.csv.gz) | The 65,618 rows of revision `5bd7fba` whose BDU record has a v3 or v4 vector, with identifiers, stored vectors, scores and labels; `label_changed` = `yes` for 21,458 (783 KB; no titles or descriptions) | Not in the repository |
| [`data/affected_rows_summary.json`](./vulnerability-fstec-fix/data/affected_rows_summary.json) | Column descriptions of the list, sources with checksums, the counts | Not in the repository |
| [`data/count_output.json`](./vulnerability-fstec-fix/data/count_output.json) | Output of `count_fstec_labels.py`, to compare a rerun with | Not in the repository |
| [`data/split_overlap_5bd7fba.json`](./vulnerability-fstec-fix/data/split_overlap_5bd7fba.json) | Output of `split_overlap.py` on revision `5bd7fba` | Not in the repository |
| [`scripts/count_fstec_labels.py`](./vulnerability-fstec-fix/scripts/count_fstec_labels.py) | Writes the list and the counts from the Vulnerability-Lookup dump and the dataset's parquet files | Not in the repository |
| [`scripts/split_overlap.py`](./vulnerability-fstec-fix/scripts/split_overlap.py) | CVE ids shared by train and test under the 3.4.0 group split, depending on what `cve_id` holds | Not in the repository |
| [`scripts/test_fstec_patches.py`](./vulnerability-fstec-fix/scripts/test_fstec_patches.py) | Checks per patch on a VulnTrain checkout | Not in the repository |
| [`README-EN.md`](./vulnerability-fstec-fix/README-EN.md) | How to apply the patches, what each one changes, the counts, what was and was not run | **Public copy:** six references to earlier correspondence are left out and marked in the text; nothing else is changed |
| [`SHA256SUMS`](./vulnerability-fstec-fix/SHA256SUMS) | Checksums of the ten files above, as delivered | The delivered line for the README is removed, because the public copy differs |

The relative paths in the README (`patches/`, `scripts/`, `data/`) work in this folder.

---

[← CIRCL details](../README.md) · [← Overview](../../README.md)
