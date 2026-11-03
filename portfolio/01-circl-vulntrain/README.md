# 1. CIRCL: VulnTrain and the VLAI severity classifiers

[← Back to overview](../README.md) · [Part 1: vulnerability-scores](#part-1-vulnerability-scores-october-2026) · [Part 2: Vulnerability-FSTEC](#part-2-vulnerability-fstec-november-2026) · [What I delivered](./delivered/)

**Status: accepted.** Part 1: four commits in VulnTrain 3.4.0 (29 October 2026); CIRCL rebuilt the dataset, retrained
its classifier and published a technical report. Part 2: three commits merged into `main` on 3 November 2026 and listed
under "Unreleased" in the CHANGELOG; CIRCL rebuilt the dataset `CIRCL/Vulnerability-FSTEC` (revision `a104085`).

## Who they are

- **CIRCL**, in its own words: "The Computer Incident Response Center Luxembourg (CIRCL) is a government-driven
  initiative designed to provide a systematic response facility to computer security threats and incidents."
  ([mission statement](https://www.circl.lu/mission/))
- **Vulnerability-Lookup**, CIRCL's vulnerability database: "Vulnerability-Lookup correlates vulnerabilities across
  multiple sources in real time, independent of their IDs, and turns scattered advisories into a single, searchable
  knowledge base." ([README](https://github.com/vulnerability-lookup/vulnerability-lookup), public instance
  [vulnerability.circl.lu](https://vulnerability.circl.lu))
- **VulnTrain**: "VulnTrain turns the vulnerability data collected by Vulnerability-Lookup into AI datasets and trained
  models." ([README](https://github.com/vulnerability-lookup/VulnTrain)) Its dataset
  [`CIRCL/vulnerability-scores`](https://huggingface.co/datasets/CIRCL/vulnerability-scores) trains the VLAI severity
  classifiers; VLAI "predicts software vulnerability severity levels directly from text descriptions"
  ([model card](https://huggingface.co/CIRCL/vulnerability-severity-classification-roberta-base)).
- **Vulnerability-FSTEC**, the dataset of part 2: "Russian vulnerability descriptions with CVSS scores from the Data
  Bank of Security Threats (BDU) of FSTEC of Russia, extracted via Vulnerability-Lookup. It is used to train the VLAI
  severity classifier for Russian." ([dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC))

## Part 1: vulnerability-scores, October 2026

[What I delivered](./delivered/README.md#1-october-2026-vulnerability-scores-fix) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

### Summary

In revision `34e6a14` of the dataset I found two problems: train/test leakage, and CVSS 4.0 scores read in two
different ways. On 28 October 2026 I delivered three patches, a leakage check and an evaluation script. CIRCL committed
the patches and the leakage check as four commits, released them in VulnTrain 3.4.0, rebuilt the dataset, retrained its
RoBERTa classifier and published a technical report with a DOI. The release notes say "reported and fixed by Christian
Bucher".

### What I found

1. **Train/test leakage.** The dataset was split with "a plain random train_test_split(test_size=0.1), with no seed, no
   grouping and no deduplication" (CIRCL's report). Copies of the same vulnerability therefore landed on both sides:
   according to the report, 58.45% of the labelled test rows had a train row with the same description, mostly a CVE
   record and the GitHub advisory for the same CVE. The previous RoBERTa classifier scored 81.17% on that test split,
   but 73.02% on the test rows it had never seen in any form.
2. **Two readings of CVSS 4.0.** In the report's words: "VulnTrain read CVE records’ baseScore as published, but
   computed the score of GitHub, PySec and CSAF advisories from their vector with cvss.CVSS4(vector).base_score, which
   applies every metric in the vector." The same vulnerability could therefore get two severity labels. The report's
   example: CVE-2025-6876 at 5.3 (Medium) and GHSA-pq67-v76v-mvgg at 2.1 (Low), with the same description and the same
   vector.

### What I delivered

One package, delivered to CIRCL on 28 October 2026. The files are in
[`delivered/vulnerability-scores-fix/`](./delivered/vulnerability-scores-fix/), with an index in
[`delivered/README.md`](./delivered/README.md#1-october-2026-vulnerability-scores-fix).

| File | What it is | At CIRCL today |
|---|---|---|
| [`0001-new-dataset-group-aware-train-test-split-description.patch`](./delivered/vulnerability-scores-fix/patches/0001-new-dataset-group-aware-train-test-split-description.patch) | Group-aware train/test split (description, id, alias) and removal of repeated documents | Same code in commit [`7ad1525`](https://github.com/vulnerability-lookup/VulnTrain/commit/7ad1525c0d7ecafee26586fdee4124e4eb0fa791) |
| [`0002-fix-utils-score-every-CVSS-4.0-vector-with-one-readi.patch`](./delivered/vulnerability-scores-fix/patches/0002-fix-utils-score-every-CVSS-4.0-vector-with-one-readi.patch) | One reading for every CVSS 4.0 score (base metrics only, CVSS-B) | Same code in commit [`595aa75`](https://github.com/vulnerability-lookup/VulnTrain/commit/595aa754f61439e0f5cd541a3d508cf96c957939) |
| [`0003-chg-trainers-select-checkpoints-on-a-validation-spli.patch`](./delivered/vulnerability-scores-fix/patches/0003-chg-trainers-select-checkpoints-on-a-validation-spli.patch) | Checkpoint selection on a validation split | Same code in commit [`1b521f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/1b521f4bc741d101cb272393ed5b8632d5d32ae4) |
| [`check_split_leakage.py`](./delivered/vulnerability-scores-fix/scripts/check_split_leakage.py) | Leakage check for any dataset revision; with `--max-shared-groups 0` it exits 1 when groups span splits | Commit [`42131f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/42131f4de01333e2ee3320a1cfa78a41b040eed8) as `tools/dataset/check_split_leakage.py`, plus a line naming me |
| [`eval_seen_unseen.py`](./delivered/vulnerability-scores-fix/scripts/eval_seen_unseen.py) | A model's test accuracy on rows with and without a train twin | Named in the report's acknowledgements; not in the repository |
| [`test_package.py`](./delivered/vulnerability-scores-fix/scripts/tests/test_package.py) | 10 unit tests for the patch helpers and both scripts | Not in the repository |
| [`README.md`](./delivered/vulnerability-scores-fix/README.md) | How to apply the patches, notes, what was and was not run | Public copy: two notes left out (marked) |

Not included here: the per-row twin flags `data/twin_flags_test_34e6a14.csv` (82,314 rows, no text, 3.6 MB). The report
says about them: "the per-row flags match his on all 82,314 test rows".

### What changed

- **Released:** [VulnTrain 3.4.0](https://github.com/vulnerability-lookup/VulnTrain/releases/tag/v3.4.0) on 29 October
  2026, with the group-aware split, one CVSS 4.0 reading (CVSS-B), a validation split and the leakage check, merged with
  [pull request #27](https://github.com/vulnerability-lookup/VulnTrain/pull/27).
- **Dataset rebuilt:** revision
  [`55a886a`](https://huggingface.co/datasets/CIRCL/vulnerability-scores/commit/55a886a483bb27aabb6461edc64e8058cc136e24)
  of `CIRCL/vulnerability-scores` (29 October 2026), "Leakage-free group split (80/10/10) and CVSS-B scoring for CVSS 4.0".
- **Classifier retrained:** revision
  [`064daa2`](https://huggingface.co/CIRCL/vulnerability-severity-classification-roberta-base/commit/064daa20420f89e47cf1667cc7228e4ae09b0918)
  (29 October 2026) scores 74.15% on the leakage-free test split (macro F1 0.646). The
  [model card](https://huggingface.co/CIRCL/vulnerability-severity-classification-roberta-base) explains the new split in
  a "Note (October 2026)". From the report:

  > Figures reported on the previous split are about 7 points higher for RoBERTa than the leakage-free figures, and are
  > superseded by the new ones.

- **Technical report** by Cédric Bonhomme (CIRCL): *Improving vulnerability-scores: Leakage-Free Splits and Consistent
  CVSS 4.0 Scoring*, [doi:10.5281/zenodo.23760802](https://doi.org/10.5281/zenodo.23760802), also as a
  [web page](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html).
- **A check on every rebuild:** "The leakage check runs after every rebuild of the dataset, so future versions keep the
  same guarantee." (report, Next steps). CIRCL's publishing runbook
  ([`dbd0de0`](https://github.com/vulnerability-lookup/VulnTrain/commit/dbd0de013009804bcadfd52dea42eb6b816be57a),
  30 October 2026) says to "run the leakage check after each push".
- **Also in 3.4.0:** "`compute_metrics` no longer fails when an eval split lacks a severity class."
  ([CHANGELOG](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md)). The delivered README notes
  this crash in its last note ("Also noticed, not in the patches").

### Where my name appears

Verbatim quotes, with place and date:

1. **Release notes of VulnTrain 3.4.0**, 2026-10-29:
   [CHANGELOG at tag v3.4.0](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md) and
   [GitHub release page](https://github.com/vulnerability-lookup/VulnTrain/releases/tag/v3.4.0)

   > Train/test leakage and CVSS 4.0 scoring in `CIRCL/vulnerability-scores`, reported and fixed by Christian Bucher.

2. **Technical report, web page**, 2026-10-29
   ([link](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html)), six mentions:
   - introduction:

     > It is the result of a careful external review by Christian Bucher, who measured two problems in the previous
     > version, contributed the patches that fix them and a leakage check that now guards every rebuild. Every figure he
     > reported was reproduced independently before the changes were adopted.

   - "Measurement on revision 34e6a14":

     > These figures were reported by Christian Bucher and reproduced independently with the same script: the per-row
     > flags match his on all 82,314 test rows.

   - "What it means for the previous model":

     > For reference, Christian Bucher measured a TF-IDF baseline (the settings of VulnTrain’s CERT-FR trainer) at 81.8%
     > on the published split, 74.7% with rows sharing a description kept on one side, and 73.1% with CVE/GHSA aliases
     > grouped too.

   - "Extent" (second finding):

     > Christian Bucher found that the CVE records are not consistent either: in the 45,432 cvelistV5 records for 2025,
     > at least 586 of the 12,498 CNA CVSS 4.0 blocks publish a baseScore with Exploit Maturity applied, mostly from
     > GitHub and QNAP as CNA.

   - "Leakage check":

     > tools/dataset/check_split_leakage.py (contributed by Christian Bucher)

   - "Acknowledgements":

     > Many thanks to Christian Bucher for his careful and constructive review: the analysis, the patches (group-aware
     > split, CVSS 4.0 reading, validation split), the per-row twin flags, and the leakage and seen/unseen evaluation
     > scripts.

3. **Zenodo record of the report**, 2026-10-29
   ([doi:10.5281/zenodo.23760802](https://doi.org/10.5281/zenodo.23760802)):

   > The changes follow an external review by Christian Bucher, which found two problems in the previous dataset
   > revision (34e6a14)

4. **Pull request #27**, merged 2026-10-29 ([link](https://github.com/vulnerability-lookup/VulnTrain/pull/27)):

   > Fixes the two problems that Christian Bucher reported in `CIRCL/vulnerability-scores` …

   and further down: "Patches contributed by Christian:"

5. **Docstring of the leakage check** in VulnTrain 3.4.0, 2026-10-29
   ([`tools/dataset/check_split_leakage.py`, line 31](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/tools/dataset/check_split_leakage.py#L31)):

   > Contributed by Christian Bucher (https://github.com/christian140903-sudo).

6. **Commit message of the commit that adds the technical report**, 2026-10-29
   ([`4dd7913`](https://github.com/vulnerability-lookup/VulnTrain/commit/4dd791365666e476953fab0c8994b625ad795c86)):

   > Draft of a public report on the group-aware split, the CVSS-B reading and their effect on the evaluation of the
   > VLAI severity classifiers, crediting Christian Bucher.

7. **Commit pages** of [`7ad1525`](https://github.com/vulnerability-lookup/VulnTrain/commit/7ad1525c0d7ecafee26586fdee4124e4eb0fa791),
   [`595aa75`](https://github.com/vulnerability-lookup/VulnTrain/commit/595aa754f61439e0f5cd541a3d508cf96c957939),
   [`1b521f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/1b521f4bc741d101cb272393ed5b8632d5d32ae4) and
   [`42131f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/42131f4de01333e2ee3320a1cfa78a41b040eed8),
   committed 2026-10-29: authored under my GitHub account (git author "Christian Bucher"), committed by Cédric Bonhomme.

### Timeline

| Date | Event |
|---|---|
| 2026-10-14 | Dataset revision `34e6a14` published on Hugging Face; the previous classifier (`10d9861`) is trained on it. |
| 2026-10-28 | Package delivered to CIRCL: three patches, two scripts, unit tests, README. |
| 2026-10-29 | The three patches and the leakage check committed by Cédric Bonhomme (CIRCL); dataset rebuilt as `55a886a`; pull request #27 merged; VulnTrain 3.4.0 released; technical report published on Zenodo; RoBERTa classifier retrained (`064daa2`); model card updated. |
| 2026-10-30 | Publishing runbook: run the leakage check after each push (`dbd0de0`). |

### Status

**Accepted.** Four commits on `main` and in the tag `v3.4.0`; dataset rebuilt, classifier retrained, technical report
published. The other files of the delivery (`eval_seen_unseen.py`, the unit tests) are not part of the repository.

### How to verify

1. **Credit:** open the [CHANGELOG at tag v3.4.0](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md)
   (lines 7–8) and search the
   [report](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html) for "Bucher"
   (six mentions).
2. **The delivered patches are the code CIRCL committed.** In a clone of VulnTrain, compare patch IDs:

   ```bash
   git clone https://github.com/vulnerability-lookup/VulnTrain && cd VulnTrain
   for c in 7ad1525 595aa75 1b521f4; do git show $c | git patch-id --stable; done
   for p in /path/to/delivered/vulnerability-scores-fix/patches/*.patch; do git patch-id --stable < "$p"; done
   ```

   Both loops print the same three patch IDs (`6cf719c6126b…`, `49d73be2d614…`, `1e9c9b77b510…`).
3. **Authorship and release:** `git log -1 --format='%an | %cn' 7ad1525` prints `Christian Bucher | Cédric Bonhomme`
   (likewise for `595aa75`, `1b521f4`, `42131f4`); `git merge-base --is-ancestor 7ad1525 v3.4.0 && echo yes` prints
   `yes`.
4. **Leakage check:**
   `git show 42131f4:tools/dataset/check_split_leakage.py | diff - /path/to/delivered/vulnerability-scores-fix/scripts/check_split_leakage.py`
   shows only the two lines CIRCL added: an empty line and the line "Contributed by Christian Bucher …".
5. **Effect on the data and the model:** dataset commit
   [`55a886a`](https://huggingface.co/datasets/CIRCL/vulnerability-scores/commit/55a886a483bb27aabb6461edc64e8058cc136e24),
   model commit
   [`064daa2`](https://huggingface.co/CIRCL/vulnerability-severity-classification-roberta-base/commit/064daa20420f89e47cf1667cc7228e4ae09b0918)
   and the "Note (October 2026)" in the
   [model card](https://huggingface.co/CIRCL/vulnerability-severity-classification-roberta-base).

## Part 2: Vulnerability-FSTEC, November 2026

[What I delivered](./delivered/README.md#2-november-2026-vulnerability-fstec-fix) · [Where my name appears](#where-my-name-appears-1) · [How to verify](#how-to-verify-1)

### Summary

In `CIRCL/Vulnerability-FSTEC`, the CVSS v3 and v4 scores were empty in every row, so every severity label came from
CVSS 2.0. On 3 November 2026 I delivered three patches, a list of the affected rows and the scripts behind it. CIRCL
committed the three patches, added two changes of its own, merged them into `main` with pull request #28 on 3 November
2026 and rebuilt the dataset. The CHANGELOG lists the fix under "Unreleased" and says "reported and fixed
by Christian Bucher".

### What I found

The BDU records in Vulnerability-Lookup store their CVSS v3 and v4 vectors without the `CVSS:3.x/` and `CVSS:4.0/`
prefix. The parser rejected these vectors and stored no score, without a message, so the v3 and v4 columns were empty
in every row of `CIRCL/Vulnerability-FSTEC` and every severity label came from CVSS 2.0 (commit message of
[`483f4ee`](https://github.com/vulnerability-lookup/VulnTrain/commit/483f4ee9fc8b09216cac67d580852abb3063b798)).
According to CIRCL's
[CHANGELOG](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md),
reading the vectors changes 21,458 of the 82,960 labels (25.9%). The delivered list has
one row for each of the 65,618 rows of revision `5bd7fba` whose BDU record has a v3 or v4 vector.

### What I delivered

One package, delivered to CIRCL on 3 November 2026. The files are in
[`delivered/vulnerability-fstec-fix/`](./delivered/vulnerability-fstec-fix/), with an index in
[`delivered/README.md`](./delivered/README.md#2-november-2026-vulnerability-fstec-fix).

| File | What it is | At CIRCL today |
|---|---|---|
| [`0001-fix-dataset-read-the-FSTEC-CVSS-v3-and-v4-vectors-mi.patch`](./delivered/vulnerability-fstec-fix/patches/0001-fix-dataset-read-the-FSTEC-CVSS-v3-and-v4-vectors-mi.patch) | Reads the stored v3 and v4 vectors: adds the missing prefix and reports a vector that still cannot be read | Same code in commit [`483f4ee`](https://github.com/vulnerability-lookup/VulnTrain/commit/483f4ee9fc8b09216cac67d580852abb3063b798) |
| [`0002-fix-dataset-score-the-FSTEC-CVSS-4.0-vectors-as-CVSS.patch`](./delivered/vulnerability-fstec-fix/patches/0002-fix-dataset-score-the-FSTEC-CVSS-4.0-vectors-as-CVSS.patch) | Scores the FSTEC v4.0 vectors with `cvss4_score()` (base metrics only, CVSS-B), like every other source since 3.4.0 | Same code in commit [`947e608`](https://github.com/vulnerability-lookup/VulnTrain/commit/947e608a982580359773437cced1694748143af5) |
| [`0003-chg-dataset-FSTEC-cve_id-one-CVE-id-other-identifier.patch`](./delivered/vulnerability-fstec-fix/patches/0003-chg-dataset-FSTEC-cve_id-one-CVE-id-other-identifier.patch) | `cve_id` holds the first CVE id of BDU's field of other identifiers; the field itself is kept in a new column `other_identifiers` | Same code in commit [`765d7b6`](https://github.com/vulnerability-lookup/VulnTrain/commit/765d7b667cdd933a758fbc40cedb003844841f0c) |
| [`affected_rows.csv.gz`](./delivered/vulnerability-fstec-fix/data/affected_rows.csv.gz) | The 65,618 rows of revision `5bd7fba` whose BDU record has a v3 or v4 vector, with the stored vectors, their scores and the published and new labels; `label_changed` = `yes` for 21,458 (no titles or descriptions) | Not in the repository |
| [`count_fstec_labels.py`](./delivered/vulnerability-fstec-fix/scripts/count_fstec_labels.py) | Writes that list and its counts from the Vulnerability-Lookup dump and the dataset files | Not in the repository |
| [`split_overlap.py`](./delivered/vulnerability-fstec-fix/scripts/split_overlap.py) | CVE ids shared by train and test under the 3.4.0 group split, depending on what `cve_id` holds | Not in the repository |
| [`test_fstec_patches.py`](./delivered/vulnerability-fstec-fix/scripts/test_fstec_patches.py) | Checks per patch on a VulnTrain checkout | Not in the repository |
| [`README-EN.md`](./delivered/vulnerability-fstec-fix/README-EN.md) | How to apply the patches, what each one changes, the counts, what was and was not run | Public copy: six references to earlier correspondence left out (marked) |

The other files in `data/` hold the counts as JSON and the column descriptions of the list.

### What changed

- **Merged:** [pull request #28](https://github.com/vulnerability-lookup/VulnTrain/pull/28), "Read the FSTEC CVSS v3/v4
  vectors, CVSS-B for v4, clean cve_id", merged into `main` on 3 November 2026 (merge commit
  [`8a770c6`](https://github.com/vulnerability-lookup/VulnTrain/commit/8a770c608f87f7815814db8ca822ec3687d196a8)), with
  my three commits and two of CIRCL's own.
- **CIRCL's own additions** (not part of my delivery):
  [`c064c97`](https://github.com/vulnerability-lookup/VulnTrain/commit/c064c97960fcdf4837d9c0e9cc8cdee2d00ebb9d) "fix:
  [dataset] treat no-impact FSTEC vectors (score 0.0) as missing" and
  [`df989e1`](https://github.com/vulnerability-lookup/VulnTrain/commit/df989e1b111011229ad44d47e4fab24da24f9ee0) "chg:
  [tools] leakage check reads cve_id and cve_ids, as the group split does", which also adds the CHANGELOG entry.
- **Not released yet:** the CHANGELOG lists the fix under "Unreleased"; the latest release is still 3.4.0 (as of
  3 November 2026).
- **Dataset rebuilt:** revision
  [`a104085`](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC/commit/a1040858f08db3bbfd0d23cfc24126f638e0637d)
  of `CIRCL/Vulnerability-FSTEC` (3 November 2026), "Read CVSS v3/v4 vectors, CVSS-B for v4, group split (80/10/10),
  clean cve_id". The [dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC) has a note at the top:
  "Revision a104085 (2026-11-03) fixes the CVSS scores."

### Where my name appears

Verbatim quotes, with place and date:

1. **CHANGELOG, section "Unreleased"**, 2026-11-03
   ([CHANGELOG at commit `8a770c6`](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md),
   lines 7–11):

   > CVSS scores in `CIRCL/Vulnerability-FSTEC`, reported and fixed by Christian Bucher. BDU stores its v3 and v4
   > vectors without the `CVSS:3.x/` / `CVSS:4.0/` prefix, the parser rejected them silently, and every published row
   > was labelled from CVSS 2.0. Reading them changes 21,458 of the 82,960 labels (25.9%).

2. **Pull request #28**, merged 2026-11-03 ([link](https://github.com/vulnerability-lookup/VulnTrain/pull/28)):

   > Fixes the CVSS scores of `CIRCL/Vulnerability-FSTEC`, reported by Christian Bucher …

3. **Dataset card of `CIRCL/Vulnerability-FSTEC`** on Hugging Face, 2026-11-03
   ([card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC);
   [as of revision `808245d`](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC/blob/808245d581fea9a9f01f1c50d546b01e96fade49/README.md)),
   two mentions:
   - note at the top:

     > Reported and fixed by Christian Bucher, see VulnTrain #28.

   - "Acknowledgements":

     > Thanks to Christian Bucher (christian140903-sudo) for finding and fixing the CVSS reading …

4. **Commit pages** of [`483f4ee`](https://github.com/vulnerability-lookup/VulnTrain/commit/483f4ee9fc8b09216cac67d580852abb3063b798),
   [`947e608`](https://github.com/vulnerability-lookup/VulnTrain/commit/947e608a982580359773437cced1694748143af5) and
   [`765d7b6`](https://github.com/vulnerability-lookup/VulnTrain/commit/765d7b667cdd933a758fbc40cedb003844841f0c),
   committed 2026-11-03: authored under my GitHub account (git author "Christian Bucher"), committed by Cédric Bonhomme.
5. **Commit list** of my VulnTrain commits
   ([`commits?author=christian140903-sudo`](https://github.com/vulnerability-lookup/VulnTrain/commits?author=christian140903-sudo)):
   seven commits, the four of part 1 and these three.

### Timeline

| Date (UTC) | Event |
|---|---|
| 2026-04-06 | Dataset revision `5bd7fba` published on Hugging Face (82,960 rows, CVSS 2.0 scores only). |
| 2026-11-03 | Package delivered to CIRCL: three patches, three scripts, the list of affected rows with its counts, README. |
| 2026-11-03 12:35 | The three patches committed by Cédric Bonhomme (CIRCL). |
| 2026-11-03 12:39 | CIRCL's own commits `c064c97` and `df989e1`, with the CHANGELOG entry. |
| 2026-11-03 12:53 | Pull request #28 merged into `main` (`8a770c6`). |
| 2026-11-03 12:56 | Dataset rebuilt: revision `a104085`. |
| 2026-11-03 12:59 | Dataset card updated (`808245d`), with the note and the acknowledgement naming me. |

### Status

**Accepted.** Three commits merged into `main` (pull request #28) and listed under "Unreleased" in the CHANGELOG; no
release contains them yet (as of 3 November 2026). The dataset was rebuilt (revision `a104085`). The scripts and data
files of the delivery are not part of the repository.

### How to verify

1. **Credit:** open the
   [CHANGELOG at commit `8a770c6`](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md)
   (lines 7–11, under "Unreleased"), [pull request #28](https://github.com/vulnerability-lookup/VulnTrain/pull/28) and
   the [dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC) (note at the top and
   "Acknowledgements").
2. **The delivered patches are the code CIRCL committed.** In a clone of VulnTrain, compare patch IDs:

   ```bash
   git clone https://github.com/vulnerability-lookup/VulnTrain && cd VulnTrain
   for c in 483f4ee 947e608 765d7b6; do git show $c | git patch-id --stable; done
   for p in /path/to/delivered/vulnerability-fstec-fix/patches/*.patch; do git patch-id --stable < "$p"; done
   ```

   Both loops print the same three patch IDs (`c49bb5bba942…`, `54d4ec1372f0…`, `5aa22820d0ad…`).
3. **Authorship, merge and release:** `git log -1 --format='%an | %cn' 483f4ee` prints
   `Christian Bucher | Cédric Bonhomme` (likewise for `947e608` and `765d7b6`);
   `git merge-base --is-ancestor 765d7b6 main && echo yes` prints `yes`; `git tag --contains 765d7b6` prints nothing,
   because no release tag contains these commits yet (as of 3 November 2026).
4. **CIRCL's own additions:** `git log -1 --format='%an | %s' c064c97` prints
   `Cédric Bonhomme | fix: [dataset] treat no-impact FSTEC vectors (score 0.0) as missing`, and for `df989e1`
   `Cédric Bonhomme | chg: [tools] leakage check reads cve_id and cve_ids, as the group split does`.
5. **The copy:** in [`delivered/vulnerability-fstec-fix/`](./delivered/vulnerability-fstec-fix/),
   `sha256sum -c SHA256SUMS` reports `OK` for all ten files.
6. **Effect on the data:** dataset commit
   [`a104085`](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC/commit/a1040858f08db3bbfd0d23cfc24126f638e0637d)
   and the note at the top of the [dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC).

Related: [4. OASIS CSAF TC and BSI](../04-oasis-bsi-csaf/README.md). The CSAF documents counted there come from CIRCL's
Vulnerability-Lookup dumps.

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
