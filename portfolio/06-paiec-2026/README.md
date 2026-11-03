# 6. PAIEC 2026: competition entry

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: delivered.** Entry published (code and report); no public competition result for it yet; the proposed patches
have not been adopted in the organisers' public baseline (as of 3 November 2026).

## Who they are

- **The competition:** the Predictive AI Evaluation Competition (PAIEC) at NeurIPS 2026, run by Stanford AIMS (AI
  Measurement Science). In its own words: "This competition provides a shared testbed for studying the predictability of
  AI responses and the amount of evidence required for accurate prediction."
  ([competition page](https://aims.stanford.edu/competition); listed in the
  [NeurIPS 2026 competitions announcement](https://blog.neurips.cc/2026/07/28/neurips-2026-competitions-announced/))
- **AIMS:** "We develop the theory, methods, and open infrastructure to make those measurements valid, reliable, and fit
  for the decisions they inform." ([aims.stanford.edu](https://aims.stanford.edu/))

## Summary

Competition entry with code and report: a hierarchical logistic model that predicts, for a (subject, item) pair on a
benchmark, the probability that the AI system answers the item correctly. The predictor uses no language model at
runtime. All numbers in the entry are offline cross-validation results; no leaderboard result is claimed. The
entry includes a data-quality audit of the competition data with three proposed patches.

## What I found

The public baseline loader sees only 60 of 156 eligible graded benchmarks, because the Hugging Face Hub file listing
returns only the first 100,000 of the 385,266 files in the data repository (report, and the comment in the first
proposed patch: "this repository has 385,266 files").

## What I delivered

The entry, published in this repository on 26 October 2026 (code under MIT, report under CC BY 4.0). It is not copied
into this portfolio; [`delivered/`](./delivered/) links to each part:

- [the entry folder `paiec-2026/`](https://github.com/christian140903-sudo/christian140903-sudo/tree/claude/technosignatures-archive-analysis-nxoino/paiec-2026)
  and its [README](https://github.com/christian140903-sudo/christian140903-sudo/blob/claude/technosignatures-archive-analysis-nxoino/paiec-2026/README.md)
- the [report (PDF)](https://github.com/christian140903-sudo/christian140903-sudo/blob/claude/technosignatures-archive-analysis-nxoino/paiec-2026/report/paiec_report_v2.pdf)
- the [audit lists](https://github.com/christian140903-sudo/christian140903-sudo/tree/claude/technosignatures-archive-analysis-nxoino/paiec-2026/audit)
  and the three [proposed patches](https://github.com/christian140903-sudo/christian140903-sudo/tree/claude/technosignatures-archive-analysis-nxoino/paiec-2026/audit/patches)
  against the organisers' baseline: `01_prepare_data_full_listing.patch`, `02_optional_skip_ungraded_benchmarks.patch`,
  `03_databank_schema3_columns.patch`

## What changed

Nothing public yet. The organisers' [baseline repository](https://github.com/aims-foundations/paiec_baseline) has not
changed since 15 October 2026, and no competition result for this entry is public (as of 3 November 2026).

## Where my name appears

No public text by the organisers names me. My name appears only in the entry itself (for example on the report's title
page, in the license line and in `CITATION.cff`).

## Timeline

| Date | Event |
|---|---|
| 2026-10-15 | Last change to the organisers' public baseline repository. |
| 2026-10-26 | Code and report published in this repository. |
| — | Competition results: not public yet. |

## Status

**Delivered.** Entry published; no public result for it yet; patches not adopted publicly.

## How to verify

1. The entry's [README](https://github.com/christian140903-sudo/christian140903-sudo/blob/claude/technosignatures-archive-analysis-nxoino/paiec-2026/README.md)
   states how the numbers were obtained ("no leaderboard result is claimed") and how to reproduce them.
2. The first [proposed patch](https://github.com/christian140903-sudo/christian140903-sudo/blob/claude/technosignatures-archive-analysis-nxoino/paiec-2026/audit/patches/01_prepare_data_full_listing.patch)
   shows the cause of the 60-of-156 gap: the listing `repo_info().siblings` is capped at 100,000 entries.
3. The [commit history of the baseline](https://github.com/aims-foundations/paiec_baseline/commits/main) shows the last
   change on 15 October 2026.

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
