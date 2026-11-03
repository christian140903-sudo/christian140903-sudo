# Portfolio: what I found, delivered, and where I am credited

Christian Bucher, Vienna · [GitHub profile](https://github.com/christian140903-sudo) · Last checked: 3 November 2026

This collection lists my contributions to public research data, code and standards: what I found, what I delivered to
the people who maintain them, what changed, and where they name me. Every claim links to a public source; every
delivery is in its own folder.

**Start here: CIRCL.** In `CIRCL/vulnerability-scores`, the dataset behind CIRCL's VLAI severity classifiers, I found
train/test leakage and two readings of CVSS 4.0, and delivered three patches and a leakage check. CIRCL released them
as four commits in VulnTrain 3.4.0 on 29 October 2026, rebuilt the dataset, retrained its RoBERTa classifier and
published a technical report; the release notes say "reported and fixed by Christian Bucher". A second fix, for
`CIRCL/Vulnerability-FSTEC`, the dataset behind CIRCL's VLAI severity classifier for Russian, was merged on
3 November 2026. According to its
[changelog entry](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md),
every published row had been labelled from CVSS 2.0, and reading the v3 and v4 vectors changes 21,458 of the 82,960
labels (25.9%); the entry also says "reported and fixed by Christian Bucher".

→ [CIRCL details](./01-circl-vulntrain/README.md) · [Delivered files](./01-circl-vulntrain/delivered/) ·
[Technical report](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html) ·
[Release notes](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md) ·
[Second fix (FSTEC)](./01-circl-vulntrain/README.md#part-2-vulnerability-fstec-november-2026)

## At a glance

- **7 contributions:** two to CIRCL, and one each to AIT, AIP, the OASIS CSAF Technical Committee with BSI, STScI/MAST
  and the NeurIPS 2026 competition PAIEC. In addition, other projects' documentation refers to **2 of my tools**.
- **10 commits accepted** into the maintainers' repositories: 7 in CIRCL's VulnTrain (4 released in 3.4.0, 3 merged
  into `main` on 3 November 2026), 3 in AIT's CAM-LDS repository.
- **13 public pages on which the institutions name me:** 9 at CIRCL, 2 at AIP, 2 at OASIS/BSI. Each one is linked
  below. A page counts once, however often it names me (CIRCL's changelog names me in two entries); commits authored
  under my GitHub account are counted in the line above, not here.
- **Status:** accepted 3 (CIRCL twice, AIT) · acknowledged in errata 1 (AIP) · open 1 (OASIS/BSI) · delivered, no
  public response yet 2 (STScI/MAST, PAIEC).

## Contents

- [Overview](#overview)
- [1. CIRCL: VulnTrain and VLAI](#1-circl-vulntrain-and-vlai)
  - [1a. vulnerability-scores, October 2026](#1a-vulnerability-scores-october-2026)
  - [1b. Vulnerability-FSTEC, November 2026](#1b-vulnerability-fstec-november-2026)
- [2. AIT: CAM-LDS analysis scripts](#2-ait-cam-lds-analysis-scripts)
- [3. AIP: APPLAUSE plate archive](#3-aip-applause-plate-archive)
- [4. OASIS CSAF TC and BSI: CSAF 2.1 review](#4-oasis-csaf-tc-and-bsi-csaf-21-review)
- [5. STScI and MAST: POSS-I plate dates](#5-stsci-and-mast-poss-i-plate-dates)
- [6. PAIEC 2026: competition entry](#6-paiec-2026-competition-entry)
- [7. Tools cited by others](#7-tools-cited-by-others)
- [How this collection is organised](#how-this-collection-is-organised)

## Overview

| # | Institution (who) | Project | What I found | What I delivered | Where I am credited | Status |
|---|---|---|---|---|---|---|
| [1a](#1a-vulnerability-scores-october-2026) | [CIRCL](https://www.circl.lu/mission/), Luxembourg | [VulnTrain](https://github.com/vulnerability-lookup/VulnTrain): dataset `CIRCL/vulnerability-scores` for the VLAI severity classifiers | Train/test leakage; two readings of CVSS 4.0 | [3 patches, 2 scripts, tests](./01-circl-vulntrain/delivered/README.md#1-october-2026-vulnerability-scores-fix) | [Release notes](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md), [technical report](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html), [5 more](#1a-vulnerability-scores-october-2026) | **Accepted:** 4 commits in VulnTrain 3.4.0 (October 2026) |
| [1b](#1b-vulnerability-fstec-november-2026) | [CIRCL](https://www.circl.lu/mission/), Luxembourg | [VulnTrain](https://github.com/vulnerability-lookup/VulnTrain): dataset `CIRCL/Vulnerability-FSTEC` for the Russian VLAI severity classifier | CVSS v3 and v4 vectors were not read, so every row was labelled from CVSS 2.0 | [3 patches, 3 scripts, list of affected rows](./01-circl-vulntrain/delivered/README.md#2-november-2026-vulnerability-fstec-fix) | [Changelog](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md), [pull request #28](https://github.com/vulnerability-lookup/VulnTrain/pull/28), [dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC) | **Accepted:** 3 commits merged into `main` (November 2026), listed as "Unreleased" |
| [2](#2-ait-cam-lds-analysis-scripts) | [AIT](https://www.ait.ac.at/en/), Vienna | [CAM-LDS analysis scripts](https://github.com/ait-aecid/attack-manifestations-interpretation) | Addressed an issue described in AIT's README: identical prompts in 89 of 198 attack steps | [3 commits](./02-ait-cam-lds/delivered/) | [Commit history](https://github.com/ait-aecid/attack-manifestations-interpretation/commits?author=christian140903-sudo) (GitHub account) | **Accepted:** 3 commits on `main` |
| [3](#3-aip-applause-plate-archive) | [AIP](https://www.aip.de/en/), Potsdam | [APPLAUSE](https://www.plate-archive.org/) plate archive, DR3 and DR4 | Swapped site latitude and longitude columns for two plate archives | [Report to the maintainers](./03-aip-applause/delivered/) | Errata [DR4](https://www.plate-archive.org/metadata/applause_dr4/plate/), [DR3](https://www.plate-archive.org/metadata/applause_dr3/plate/) | **Acknowledged:** correction announced |
| [4](#4-oasis-csaf-tc-and-bsi-csaf-21-review) | [OASIS](https://www.oasis-open.org/) [CSAF TC](https://www.oasis-open.org/committees/csaf/); [BSI](https://www.bsi.bund.de/EN/Home/home_node.html) | [CSAF](https://www.csaf.io/) 2.1, public review of CSD04 | Under the new date rule, a converter would replace the date in 12,765 of 40,882 published CSAF 2.0 documents, moving 2,041 of them into a later year folder | [Review comment, counting script](./04-oasis-bsi-csaf/delivered/) | [Issue #1724](https://github.com/oasis-tcs/csaf/issues/1724), [BSI reply](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1) | **Open:** tracked as issue #1724 |
| [5](#5-stsci-and-mast-poss-i-plate-dates) | [STScI](https://github.com/spacetelescope) / MAST, Baltimore | POSS-I plate list of the [Digitized Sky Survey](https://gsss.stsci.edu/SkySurveys/Surveys.htm) | About three quarters of the listed POSS-I dates are one day early | [Correction package](./05-stsci-mast-poss1/delivered/) | Not credited publicly | **Delivered:** adoption not publicly documented |
| [6](#6-paiec-2026-competition-entry) | [Stanford AIMS](https://aims.stanford.edu/) | [PAIEC](https://aims.stanford.edu/competition), a NeurIPS 2026 competition | The baseline loader sees 60 of 156 eligible graded benchmarks | [Code, report, 3 patches](./06-paiec-2026/delivered/) | Not credited publicly | **Delivered:** no public result yet |
| [7](#7-tools-cited-by-others) | [agent-proven](https://github.com/MediaPlural/agent-proven), [ContextOS](https://github.com/contextosai/ContextOS) | Their documentation | — | [behaviorlock](https://github.com/christian140903-sudo/behaviorlock), [agent-invariants](https://github.com/christian140903-sudo/agent-invariants) | Links to my GitHub account | **Cited:** no usage documented |

## 1. CIRCL: VulnTrain and VLAI

**Who they are.** "The Computer Incident Response Center Luxembourg (CIRCL) is a government-driven initiative designed
to provide a systematic response facility to computer security threats and incidents."
([CIRCL mission statement](https://www.circl.lu/mission/)) Its project VulnTrain "turns the vulnerability data
collected by Vulnerability-Lookup into AI datasets and trained models" ([VulnTrain](https://github.com/vulnerability-lookup/VulnTrain)).
Two contributions, one per dataset: [1a](#1a-vulnerability-scores-october-2026) (October 2026) and
[1b](#1b-vulnerability-fstec-november-2026) (November 2026).

### 1a. vulnerability-scores, October 2026

**What happened.** CIRCL's VLAI classifiers estimate the severity of a vulnerability from its description and are
trained on the dataset `CIRCL/vulnerability-scores`. In revision `34e6a14` of that dataset I found two problems: 58.45%
of the labelled test rows had a training row with the same description, mostly a CVE record and the GitHub advisory for
the same CVE; and CVSS 4.0 scores were read in two different ways, so the same vulnerability could get two severity
labels. On 28 October 2026 I delivered three patches, a leakage check and an evaluation script. CIRCL released the
patches and the leakage check as four commits in VulnTrain 3.4.0 on 29 October 2026, rebuilt the dataset, retrained
its RoBERTa classifier and published a technical report. According to the report, the previous classifier scored 81.17%
on the old test split but 73.02% on test rows it had never seen; the retrained one scores 74.15% on the leakage-free
split.

- **What I delivered:** [`01-circl-vulntrain/delivered/vulnerability-scores-fix/`](./01-circl-vulntrain/delivered/vulnerability-scores-fix/):
  three patches, `check_split_leakage.py`, `eval_seen_unseen.py`, unit tests, README.
- **Where my name appears:**
  - [Release notes of VulnTrain 3.4.0 (CHANGELOG)](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/CHANGELOG.md), 2026-10-29: "… reported and fixed by Christian Bucher."
  - [GitHub release v3.4.0](https://github.com/vulnerability-lookup/VulnTrain/releases/tag/v3.4.0), 2026-10-29
  - [Technical report, web page (six mentions)](https://vulnerability-lookup.github.io/VulnTrain/vulnerability-scores-leakage-report.html), 2026-10-29: "the result of a careful external review by Christian Bucher"
  - [Technical report on Zenodo, doi:10.5281/zenodo.23760802](https://doi.org/10.5281/zenodo.23760802), 2026-10-29
  - [Pull request #27](https://github.com/vulnerability-lookup/VulnTrain/pull/27), merged 2026-10-29
  - [Docstring of `tools/dataset/check_split_leakage.py`](https://github.com/vulnerability-lookup/VulnTrain/blob/v3.4.0/tools/dataset/check_split_leakage.py#L31), 2026-10-29
  - [Commit message of the commit that adds the technical report, `4dd7913`](https://github.com/vulnerability-lookup/VulnTrain/commit/4dd791365666e476953fab0c8994b625ad795c86), 2026-10-29: "… crediting Christian Bucher."
  - Commits authored under my GitHub account, committed 2026-10-29:
    [`7ad1525`](https://github.com/vulnerability-lookup/VulnTrain/commit/7ad1525c0d7ecafee26586fdee4124e4eb0fa791),
    [`595aa75`](https://github.com/vulnerability-lookup/VulnTrain/commit/595aa754f61439e0f5cd541a3d508cf96c957939),
    [`1b521f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/1b521f4bc741d101cb272393ed5b8632d5d32ae4),
    [`42131f4`](https://github.com/vulnerability-lookup/VulnTrain/commit/42131f4de01333e2ee3320a1cfa78a41b040eed8)
- **Full details:** [`01-circl-vulntrain/README.md`, part 1](./01-circl-vulntrain/README.md#part-1-vulnerability-scores-october-2026)

### 1b. Vulnerability-FSTEC, November 2026

**The dataset.** "Russian vulnerability descriptions with CVSS scores from the Data Bank of Security Threats (BDU) of
FSTEC of Russia, extracted via Vulnerability-Lookup. It is used to train the VLAI severity classifier for Russian."
([dataset card](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC))

**What happened.** In CIRCL's words
([CHANGELOG](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md)):
"BDU stores its v3 and v4 vectors without the `CVSS:3.x/` / `CVSS:4.0/` prefix,
the parser rejected them silently, and every published row was labelled from CVSS 2.0. Reading them changes 21,458 of
the 82,960 labels (25.9%)." On 3 November 2026 I delivered three patches (the stored v3 and v4 vectors are read; v4.0
is scored as CVSS-B, like the other sources; `cve_id` holds one CVE id), the list of the 65,618 rows whose BDU record
has a v3 or v4 vector, and the scripts behind it. CIRCL committed the three patches, added two changes of its own,
merged all five commits into `main` with pull request #28 on 3 November 2026 and rebuilt the dataset (revision
`a104085`).

- **What I delivered:** [`01-circl-vulntrain/delivered/vulnerability-fstec-fix/`](./01-circl-vulntrain/delivered/vulnerability-fstec-fix/):
  three patches, the list of affected rows with its counts, three scripts,
  [README](./01-circl-vulntrain/delivered/vulnerability-fstec-fix/README-EN.md).
- **Where my name appears:**
  - [CHANGELOG, section "Unreleased"](https://github.com/vulnerability-lookup/VulnTrain/blob/8a770c608f87f7815814db8ca822ec3687d196a8/CHANGELOG.md), 2026-11-03: "CVSS scores in `CIRCL/Vulnerability-FSTEC`, reported and fixed by Christian Bucher."
  - [Pull request #28](https://github.com/vulnerability-lookup/VulnTrain/pull/28), merged 2026-11-03: "Fixes the CVSS scores of `CIRCL/Vulnerability-FSTEC`, reported by Christian Bucher …"
  - [Dataset card of `CIRCL/Vulnerability-FSTEC` (two mentions)](https://huggingface.co/datasets/CIRCL/Vulnerability-FSTEC), 2026-11-03: "Reported and fixed by Christian Bucher, see VulnTrain #28."
  - Commits authored under my GitHub account, committed 2026-11-03:
    [`483f4ee`](https://github.com/vulnerability-lookup/VulnTrain/commit/483f4ee9fc8b09216cac67d580852abb3063b798),
    [`947e608`](https://github.com/vulnerability-lookup/VulnTrain/commit/947e608a982580359773437cced1694748143af5),
    [`765d7b6`](https://github.com/vulnerability-lookup/VulnTrain/commit/765d7b667cdd933a758fbc40cedb003844841f0c);
    all seven of my VulnTrain commits are in the [commit list](https://github.com/vulnerability-lookup/VulnTrain/commits?author=christian140903-sudo)
- **Status:** merged into `main` on 3 November 2026; listed under "Unreleased" in the CHANGELOG, not yet in a release.
- **Full details:** [`01-circl-vulntrain/README.md`, part 2](./01-circl-vulntrain/README.md#part-2-vulnerability-fstec-november-2026)

## 2. AIT: CAM-LDS analysis scripts

**Who they are.** "The AIT Austrian Institute of Technology is Austria's largest research and technology organisation
with more than 1,600 employees working on the key infrastructure issues of the future." ([ait.ac.at](https://www.ait.ac.at/en/))
Its repository [`ait-aecid/attack-manifestations-interpretation`](https://github.com/ait-aecid/attack-manifestations-interpretation)
contains scripts that analyze the CAM-LDS log data set using LLMs; it accompanies the CAM-LDS paper (International
Journal of Information Security, 2026).

**What happened.** The paper refers to generating prompts "with new random samples of log lines", but the log lines
were sampled only once per scenario variant and attack step. As the maintainers' clarification in the README states
(20 October 2026), the five repetitions therefore used identical prompts for 89 of the 198 attack steps. I contributed
three commits, which the maintainer merged into `main` on 21 October 2026: a prompt script that samples the log lines
again in every repetition, as Sect. 5.1.2 of the paper describes; a script that reproduces the numbers of the
clarification; and README notes on data set versions and `attack_times.csv`.

- **What I delivered:** [`02-ait-cam-lds/delivered/`](./02-ait-cam-lds/delivered/): the three commits as a git mailbox
  and as single patches, and the two scripts.
- **Where my name appears:**
  - [Commit history: three commits authored under my GitHub account](https://github.com/ait-aecid/attack-manifestations-interpretation/commits?author=christian140903-sudo), committed 2026-10-21:
    [`a0a0bd9`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/a0a0bd9980e1a2b23ccec00bf6372607ee53c9e2),
    [`c839210`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/c8392102e23a94245b8f8173a08f3ffef47f895d),
    [`42bbd2c`](https://github.com/ait-aecid/attack-manifestations-interpretation/commit/42bbd2cf8409f64a1e6c8fc936c91725e8c558b2).
    The repository files themselves do not name me.
- **Full details:** [`02-ait-cam-lds/README.md`](./02-ait-cam-lds/README.md)

## 3. AIP: APPLAUSE plate archive

**Who they are.** "The Leibniz Institute for Astrophysics Potsdam (AIP) is dedicated to astrophysical questions ranging
from the study of our Sun to the evolution of the cosmos." ([aip.de](https://www.aip.de/en/)) "The APPLAUSE database is
a service by the Leibniz-Institute for Astrophysics Potsdam (AIP)." ([imprint](https://www.plate-archive.org/cms/imprint/))
APPLAUSE stands for "Archives of Photographic PLates for Astronomical USE".

**What happened.** In the APPLAUSE plate tables, the observing-site latitude and longitude are stored in swapped columns
for two plate archives: `archive_id` 205 and 208 in data release DR4, and 205 in DR3. I reported this to the archive
maintainers in October 2026. AIP added an erratum naming me to the DR3 and DR4 documentation; according to it, the swap
also affects zenith-angle and airmass values and the corresponding FITS files, and "The errors will be corrected in a
further data release."

- **What I delivered:** [`03-aip-applause/delivered/`](./03-aip-applause/delivered/): a written report to the
  maintainers (correspondence, not reproduced).
- **Where my name appears:**
  - [Erratum in the DR4 plate-table documentation](https://www.plate-archive.org/metadata/applause_dr4/plate/), 10/2026: "User (C. Bucher, Wien) has pointed out …"
  - [Erratum in the DR3 plate-table documentation](https://www.plate-archive.org/metadata/applause_dr3/plate/), 10/2026
- **Full details:** [`03-aip-applause/README.md`](./03-aip-applause/README.md)

## 4. OASIS CSAF TC and BSI: CSAF 2.1 review

**Who they are.** "OASIS Open is an established non-profit organization where individuals, organizations and
governments come together to solve some of the world’s biggest technical challenges through the development of open
code and open standards." ([oasis-open.org](https://www.oasis-open.org/)) Its
[CSAF Technical Committee](https://www.oasis-open.org/committees/csaf/) develops the Common Security Advisory
Framework, which "is a language to exchange Security Advisories" ([csaf.io](https://www.csaf.io/)). "The Federal Office
for Information Security (BSI) is the federal authority for cybersecurity in Germany."
([bsi.bund.de](https://www.bsi.bund.de/EN/Home/home_node.html))

**What happened.** During the public review of CSAF 2.1 Committee Specification Draft 04, I posted a review comment on
its new `initial_release_date` rule (clause 9.1.18, test 6.1.66), under which a converter from CSAF 2.0 replaces that
date when it converts a published document. For 40,882 published CSAF 2.0 documents from 50 publishers, the date would be replaced in
12,765 and move into a later year in 2,041, so that Requirement 11 files the converted document in a different year
folder than the original. Thomas Schmidt (BSI) replied on the comment list, and the committee opened issue #1724,
"created on behalf of Christian Bucher". The issue is open.

- **What I delivered:** [`04-oasis-bsi-csaf/delivered/`](./04-oasis-bsi-csaf/delivered/): the review comment as
  posted, and a counting script that reproduces its numbers from the public CIRCL dumps.
- **Where my name appears:**
  - [Issue #1724 in the CSAF TC's repository](https://github.com/oasis-tcs/csaf/issues/1724), opened 2026-10-28: "The below issue was created on behalf of Christian Bucher:"
  - [Reply by Thomas Schmidt (BSI) on the csaf-comment list](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1), October 2026: "Dear Mr. Bucher, thank you for commenting on CSAF 2.1 CSD04. …"
- **Full details:** [`04-oasis-bsi-csaf/README.md`](./04-oasis-bsi-csaf/README.md)

## 5. STScI and MAST: POSS-I plate dates

**Who they are.** "We are the Space Telescope Science Institute in Baltimore, Maryland, operated by the Association of
Universities for Research in Astronomy. We help humanity explore the universe with advanced space telescopes and
ever-growing data archives." ([STScI on GitHub](https://github.com/spacetelescope)) MAST, STScI's archive, lists the
surveys of the Digitized Sky Survey, among them the first Palomar Observatory Sky Survey, POSS-I
([survey list](https://gsss.stsci.edu/SkySurveys/Surveys.htm)).

**What happened.** The MAST plate list `SurveyPlateListLatest.csv` (2024) gives the observation dates of the POSS-I
plates in the Digitized Sky Survey. On about three quarters of the plates the listed date is one day early: it is the
date on which the night began, not the UT date of the exposure. I reported this to the MAST helpdesk on 13 October 2026
and published a correction package with one row per list row (1,870 POSS-I rows), evidence and scripts, under CC BY
4.0. Whether STScI has adopted it is not publicly documented.

- **What I delivered:** [`05-stsci-mast-poss1/delivered/`](./05-stsci-mast-poss1/delivered/): the correction package.
- **Where my name appears:** no public text by STScI names me; my name is in the package itself.
- **Full details:** [`05-stsci-mast-poss1/README.md`](./05-stsci-mast-poss1/README.md)

## 6. PAIEC 2026: competition entry

**Who they are.** The Predictive AI Evaluation Competition (PAIEC) at NeurIPS 2026 is run by Stanford AIMS (AI
Measurement Science): "This competition provides a shared testbed for studying the predictability of AI responses and
the amount of evidence required for accurate prediction." ([competition page](https://aims.stanford.edu/competition))

**What happened.** The task is to predict whether an AI system answers a benchmark item correctly, without running it.
My entry is a hierarchical logistic model that uses no language model at runtime; all numbers in it are offline
cross-validation results, and no leaderboard result is claimed. The entry includes a data-quality audit of the
competition data: the public baseline loader sees only 60 of 156 eligible graded benchmarks, because the Hugging Face
Hub file listing returns only the first 100,000 of 385,266 files. Three patches against the organisers' baseline are
proposed; the baseline has not changed since 15 October 2026, and no competition result for the entry is public yet.

- **What I delivered:** [`06-paiec-2026/delivered/`](./06-paiec-2026/delivered/): links to the code, the report and
  the patches.
- **Where my name appears:** no public text by the organisers names me; my name is in the entry itself.
- **Full details:** [`06-paiec-2026/README.md`](./06-paiec-2026/README.md)

## 7. Tools cited by others

**Who they are.** agent-proven (MediaPlural): "Full-suite verification and quality tooling for AI coding agents —
every claim backed by evidence." ([repository](https://github.com/MediaPlural/agent-proven)) ContextOS: "Shared
business limits for AI agents." ([repository](https://github.com/contextosai/ContextOS))

**What happened.** The agent-regression skill of agent-proven points to my tool behaviorlock for deterministic trace
comparison (since 3 October 2026), and ContextOS lists my tool agent-invariants among existing solutions in its
landscape review (since 22 October 2026). These are pointers in documentation, not usage reports.

- **What I delivered:** the tools themselves:
  [behaviorlock](https://github.com/christian140903-sudo/behaviorlock) and
  [agent-invariants](https://github.com/christian140903-sudo/agent-invariants) (both MIT).
- **Where they are cited:**
  - [agent-proven, `skills/agent-regression/SKILL.md` at commit `fe920e4`](https://github.com/MediaPlural/agent-proven/blob/fe920e4f0303bca837e43d6f6c40167aca7928b8/skills/agent-regression/SKILL.md), since 2026-10-03
  - [ContextOS, `docs/research/2026-10-22-value-proposition.md` at commit `ba5c41a`](https://github.com/contextosai/ContextOS/blob/ba5c41af785edb3cf940ac082739e69d5fdc6e00/docs/research/2026-10-22-value-proposition.md), since 2026-10-22
- **Full details:** [`07-tools-cited-by-others/README.md`](./07-tools-cited-by-others/README.md)

## How this collection is organised

- Each numbered folder belongs to one section of this page: a `README.md` with the details (who they are, what I found
  and delivered, what changed, verbatim quotes with links and dates, timeline, status, how to verify each statement;
  folder 1 has one part per CIRCL contribution) and, in folders 1 to 6, a `delivered/` folder with the files as
  delivered and an index. In folder 7 the tools themselves are the delivery.
- Files in `delivered/` are copies of what was delivered or published. Each index says where a copy comes from and,
  where it differs from the original, how.
- Quotes are verbatim, including the original spelling. "Open" means that nothing has been decided yet.
- Work that is not public yet is not listed.
- If something here is wrong or out of date, please open an issue in this repository.
