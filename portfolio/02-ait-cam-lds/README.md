# 2. AIT: CAM-LDS analysis scripts

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: accepted.** Three commits on `main` of AIT's repository (21 October 2026).

## Who they are

- **AIT**, in its own words: "The AIT Austrian Institute of Technology is Austria's largest research and technology
  organisation with more than 1,600 employees working on the key infrastructure issues of the future."
  ([ait.ac.at](https://www.ait.ac.at/en/))
- **The repository**
  [`ait-aecid/attack-manifestations-interpretation`](https://github.com/ait-aecid/attack-manifestations-interpretation):
  "This repository contains scripts to process and analyze the Cyber Attack Manifestations - Log Data Set (CAM-LDS)
  using LLMs." It accompanies the paper *CAM-LDS: Cyber Attack Manifestations for Automatic Interpretation of System Logs
  and Security Alerts* by M. Landauer, W. Hotwagner, T. Boenke, F. Skopik and M. Wurzenberger (International Journal of
  Information Security 25(5), 2026, [doi:10.1007/s10207-026-01318-x](https://doi.org/10.1007/s10207-026-01318-x)).

## Summary

Three commits contributed to the repository and merged into `main` on 21 October 2026: a prompt script that samples
the log lines again in every repetition, as Sect. 5.1.2 of the paper describes; a script that counts identical prompts
per attack step and reproduces the numbers of the README's clarification of the paper's stability results; and README
notes on data set versions and `attack_times.csv`.

## What the commits address

The repository README contains this clarification by the maintainers, added on 20 October 2026 (section
"Clarification regarding the stability results in our paper"):

> The paper refers to generating prompts "with new random samples of log lines." However, log lines are sampled only
> once per scenario variant and attack step, and reused whenever the same variant is selected. Consequently, the five
> repetitions resulted in identical prompts for 89 of the 198 attack steps, while prompts varied for the remaining 109
> steps.

The first commit adds a script that samples the log lines again in every repetition; the second reproduces the counts
in this clarification from the repository's data.

## What I delivered

Three commits, delivered to the maintainers on 20 October 2026. The files are in [`delivered/`](./delivered/), with an
index in [`delivered/README.md`](./delivered/README.md).

| Commit on `main` | Message | Content | Files in `delivered/` |
|---|---|---|---|
| [`a0a0bd9`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/a0a0bd9980e1a2b23ccec00bf6372607ee53c9e2) | Add prompt creation with new log samples per repetition | `create_llm_prompt_resample.py`: works like `create_llm_prompt.py` and takes the same parameters, but samples the log lines again in every repetition | [patch](./delivered/ait-cam-lds-resample/patches/0001-Add-prompt-creation-with-new-log-samples-per-repetit.patch), [script](./delivered/ait-cam-lds-resample/create_llm_prompt_resample.py) |
| [`c839210`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/c8392102e23a94245b8f8173a08f3ffef47f895d) | Add script to count identical prompts per step | `count_identical_prompts.py`: counts identical prompts per step and reproduces the numbers of the clarification | [patch](./delivered/ait-cam-lds-resample/patches/0002-Add-script-to-count-identical-prompts-per-step.patch), [script](./delivered/ait-cam-lds-resample/count_identical_prompts.py) |
| [`42bbd2c`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/42bbd2cf8409f64a1e6c8fc936c91725e8c558b2) | Add notes on data set versions and attack_times.csv to README | README notes | [patch](./delivered/ait-cam-lds-resample/patches/0003-Add-notes-on-data-set-versions-and-attack_times.csv-.patch) |

All three commits are also in one git mailbox,
[`cam-lds-resample.mbox`](./delivered/ait-cam-lds-resample/cam-lds-resample.mbox), with a
[package README](./delivered/ait-cam-lds-resample/README.md) and the upstream
[license](./delivered/ait-cam-lds-resample/LICENSE) (GPL-3.0).

## What changed

`main` now contains `create_llm_prompt_resample.py` and `count_identical_prompts.py`, and the
[README](https://github.com/ait-aecid/attack-manifestations-interpretation/blob/main/README.md) points users to them:

> To create prompts with new random samples of log lines in every repetition, as described in Sect. 5.1.2 of the paper,
> use the following script instead.

> The numbers in this clarification can be reproduced with the following script.

## Where my name appears

- **Commit history**, committed 2026-10-21:
  [three commits authored under my GitHub account](https://github.com/ait-aecid/attack-manifestations-interpretation/commits?author=christian140903-sudo)
  ([`a0a0bd9`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/a0a0bd9980e1a2b23ccec00bf6372607ee53c9e2),
  [`c839210`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/c8392102e23a94245b8f8173a08f3ffef47f895d),
  [`42bbd2c`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/42bbd2cf8409f64a1e6c8fc936c91725e8c558b2)).
  The page shows "christian140903-sudo authored and landauermax committed"; the git author is "Christian Bucher".
- The repository files themselves do not name me.

## Timeline

| Date | Event |
|---|---|
| 2026-10-20 | Clarification of the stability results added to the README by the maintainers (`61af22b`). |
| 2026-10-20 | Three commits delivered to the maintainers (author date 14:31 UTC); the same patch set published in this repository at 14:32 UTC (commit `dbad253`). |
| 2026-10-21 | The three commits committed to `main` (06:56 UTC). |
| 2026-11-03 | `42bbd2c` is still the latest commit on `main`. |

## Status

**Accepted.** Three commits on `main`.

## How to verify

1. **Commits:** the
   [commit list](https://github.com/ait-aecid/attack-manifestations-interpretation/commits?author=christian140903-sudo)
   shows the three commits under "Commits on Oct 21, 2026".
2. **The delivered patches are the commits on `main`.** Compare patch IDs:

   ```bash
   git clone https://github.com/ait-aecid/attack-manifestations-interpretation && cd attack-manifestations-interpretation
   for c in a0a0bd9 c839210 42bbd2c; do git show $c | git patch-id --stable; done
   for p in /path/to/delivered/ait-cam-lds-resample/patches/*.patch; do git patch-id --stable < "$p"; done
   ```

   Both loops print the same three patch IDs (`0c2366e2f06d…`, `de3f952de4a4…`, `6ddff294eb0d…`).
3. **Author:** `git log -1 --format='%an | %ad' --date=iso a0a0bd9` prints `Christian Bucher | 2026-10-20 14:31:02 +0000`.
4. **Scripts:** `git show a0a0bd9:create_llm_prompt_resample.py | cmp - /path/to/delivered/ait-cam-lds-resample/create_llm_prompt_resample.py`
   and `git show c839210:count_identical_prompts.py | cmp - /path/to/delivered/ait-cam-lds-resample/count_identical_prompts.py`
   report no difference.
5. **README:** search the
   [README on `main`](https://github.com/ait-aecid/attack-manifestations-interpretation/blob/main/README.md) for "can be
   reproduced with the following script".

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
