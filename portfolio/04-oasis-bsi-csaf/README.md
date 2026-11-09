# 4. OASIS CSAF TC and BSI: public review of CSAF 2.1 (CSD04)

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: resolved, merged for CSAF 2.1 CS01.** On 9 November 2026,
[pull request #1739](https://github.com/oasis-tcs/csaf/pull/1739), "Comment Resolution CSD04PR: #1724", was merged into
the committee's editor revision, and the editor revision into `master`. It adds an informative note on the year-folder
change in three places of the specification. At its meeting that day, the committee passed a motion to accept this and
other pull requests "as comment resolution to the respective issues"; its comment resolution log marks the comment
"Completed", and issue #1724 was closed as completed. CSAF 2.1 CS01 is not published yet.

## Who they are

- **OASIS**, in its own words: "OASIS Open is an established non-profit organization where individuals, organizations
  and governments come together to solve some of the world’s biggest technical challenges through the development of
  open code and open standards." ([oasis-open.org](https://www.oasis-open.org/))
- **The CSAF Technical Committee:** "The OASIS CSAF Technical Committee is chartered to make a major revision to the
  Common Vulnerability Reporting Framework (CVRF) under a new name for the framework that reflects the primary purpose:
  a Common Security Advisory Framework (CSAF)." ([TC page](https://www.oasis-open.org/committees/csaf/)) "Common
  Security Advisory Framework (CSAF) is a language to exchange Security Advisories." ([csaf.io](https://www.csaf.io/),
  the TC's website)
- **BSI**, in its own words: "The Federal Office for Information Security (BSI) is the federal authority for
  cybersecurity in Germany." ([bsi.bund.de](https://www.bsi.bund.de/EN/Home/home_node.html)) The reply to the comment
  came from Thomas Schmidt, whose signature reads "Subject Matter Expert" and "Federal Office for Information Security (BSI) Germany".

## Summary

Public review comment on the committee's comment list `csaf-comment`: under the new `initial_release_date` rule of
CSAF 2.1 CSD04 (clause 9.1.18, test 6.1.66), a converter from CSAF 2.0 would replace that date in 12,765 of 40,882
published CSAF 2.0 documents and move it into a later year in 2,041 of them, so that a converted document can end up in
a different year folder than the original. Thomas Schmidt (BSI) replied, and the committee tracks the comment as issue
#1724, "created on behalf of Christian Bucher". On 9 November 2026 the comment was resolved, and the change was merged
for CS01: an informative note now states that the conversion or the quick fix can move a document from one
year folder to another, and advises issuing parties to check whether that reflects the facts. The committee's comment
resolution log lists "CB = Christian Bucher" and marks the comment "Completed".

## What I found

The [comment](./delivered/csaf-comment-csd04.md) reports, for 40,882 CSAF 2.0 documents from 50 publishers taken from
the CIRCL vulnerability-lookup dumps of 4 October 2026 (excluding Red Hat and SUSE):

- The converter would replace `initial_release_date` in 12,765 documents, almost all from Cisco (2,850) and MSRC (9,808).
- In 9,658 MSRC documents, revision 1 is dated later than `initial_release_date`. For these the converter moves the date
  later: in 2,041 documents into a later year, in 1,436 by more than 365 days.
- Requirement 11 then places the converted CSAF 2.1 document in a different year folder than the CSAF 2.0 document.
  Example: `msrc_cve-2023-0225` has `initial_release_date` 2023-04-01 and only one revision, dated 2024-10-15.

The comment asks the committee:

> During the parallel distribution described in 7.4, the same document would then sit in two different year folders.
> Is that intended? If so, would it help if the converter's warning also mentioned the year change?

## What I delivered

The public comment with the counts, a worked example and the question, together with an offer to share the
per-document list and the counting script. In [`delivered/`](./delivered/):

| File | What it is |
|---|---|
| [`csaf-comment-csd04.md`](./delivered/csaf-comment-csd04.md) | The comment as posted (wording unchanged) |
| [`count_6_1_66.py`](./delivered/count_6_1_66.py) | Counting script that reproduces every number in the comment from the public CIRCL dumps |
| [`input-files.sha256`](./delivered/input-files.sha256) | SHA-256 of the 50 input files |

## What changed

- **Resolution merged, 9 November 2026.** [Pull request #1739](https://github.com/oasis-tcs/csaf/pull/1739),
  "Comment Resolution CSD04PR: #1724", was merged into the branch `editor-revision-2026-11-09` (merge commit
  [`5425f92`](https://github.com/oasis-tcs/csaf/commit/5425f92370d40ea73c022cb239bfd401eed751f4)). Its description
  includes: "add informative comment to point out year change problem and recommend fixing mistakes to reflect facts". It
  adds the same note to the rules of both converters, the CVRF CSAF Converter (clause 9.1.5) and the CSAF 2.0 to
  CSAF 2.1 Converter (clause 9.1.18):

  > If the year of the `initial_release_date` changed during this conversion step
  > it can lead to a situation where a CSAF document moves from one year folder to another
  > (see `[sec](#requirement-11-one-folder-per-year)`).
  > Issuing parties are strongly advised to double-check whether that conversion reflects the facts.
  > If that is not the case, the issuing party should correct the mistake in the input file.

  and a matching note after the quick fix of test 6.1.66:

  > If the year of the `initial_release_date` changed during the quick fix
  > this can lead to a situation where a CSAF document moves from one year folder to another (see `[sec](#requirement-11-one-folder-per-year)`).
  > Issuing parties are strongly advised to double-check whether this reflects the facts.
  > If that is not the case, the issuing party should correct the mistake by updating the revision history.

  `[sec](#requirement-11-one-folder-per-year)` is the source text's cross-reference to Requirement 11. The conversion
  rule itself and its warning are unchanged.
- **Accepted as comment resolution, 9 November 2026.** The minutes of that day's TC meeting
  ([issue #1743](https://github.com/oasis-tcs/csaf/issues/1743), "Meeting minutes 2026-11-09") record a "Super Motion":

  > Motion to accept the PRs as comment resolution to the respective issues and mark them as "Completed", …

  The same motion classifies the changes as non-material. Its list includes "Comment Resolution CSD04PR: #1724 #1739",
  and the result reads "… no objections, discussions, concerns => motion passed". A second motion, "to request a ballot
  to promote CSAF 2.1 CSD04 with the non-material changes from the editor revision" to CSAF 2.1 CS01, also passed.
  Pull requests #1739 and #1747 carry the label `motion_passed`.
- **Editor revision merged into `master`, 9 November 2026.** The editor revision is
  [pull request #1747](https://github.com/oasis-tcs/csaf/pull/1747), "CSAF 2.1 CSD04 Public Feedback Resolution and
  Editor revision for TC meeting 2026-11-09". It renames the draft from CSD04 to CS01 and lists under "Editorial
  Changes": "fixes CSD04 6.1.66 / 9.1.18: converted documents can change their year folder (Requirement 11) #1724
  (#1739)". It was merged into `master` that evening (merge commit
  [`c74c79a`](https://github.com/oasis-tcs/csaf/commit/c74c79aeae3bb847a1ef394ba456bd597dd49a0d)), which is tagged
  `csaf-2.1-cs-01-20261109-rc1`. CSAF 2.1 CS01 is not published yet: the
  [CSAF 2.1 folder on docs.oasis-open.org](https://docs.oasis-open.org/csaf/csaf/v2.1/) lists the stages up to CSD04.
- **Issue #1724** was closed as completed with pull request #1747 on 9 November 2026. Since 7 November 2026 it has
  been assigned to `tschmidtb51` and carries the labels `editor-revision` ("already worked on in the editor revision")
  and `csaf 2.1`.
- **Before that:** Thomas Schmidt (BSI) replied on the comment list, and the committee opened issue #1724 to track the
  comment (label `csdpr04-v-2-1-feedback`). The draft minutes of the TC meeting on 28 October 2026
  ([pull request #1730](https://github.com/oasis-tcs/csaf/pull/1730);
  [file at commit `694df97`](https://github.com/oasis-tcs/csaf/blob/694df97606c36576920e08964a0a1ae1248e6aa3/meeting_minutes/2026/2026-10-28.md))
  record the discussion of a review comment on the converter's treatment of `initial_release_date`; TC members were to
  prepare their positions for 9 November.

## Where my name appears

1. **Issue #1724** in the CSAF TC's repository, opened 2026-10-28
   ([link](https://github.com/oasis-tcs/csaf/issues/1724)), first sentence:

   > The below issue was created on behalf of Christian Bucher:

2. **Reply on the `csaf-comment` list** by Thomas Schmidt (BSI), October 2026
   ([thread](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1)):

   > Dear Mr. Bucher,
   >
   > thank you for commenting on CSAF 2.1 CSD04. We have opened an issue to track your comment:
   > https://github.com/oasis-tcs/csaf/issues/1724

3. **Comment resolution log** of the CSD04 public review, `csaf_2.1/comment_resolution/log_from_csd04pr.md`: drafted
   on 2026-11-07 in [pull request #1735](https://github.com/oasis-tcs/csaf/pull/1735)
   ([commit `17ee1e5`](https://github.com/oasis-tcs/csaf/commit/17ee1e59d562d580d453ee80cd43a0110dc2cd95)), and part of
   the committee's editor revision, now merged into `master`, since 9 November 2026; with the decisions of that day at
   [commit `74ec423`](https://github.com/oasis-tcs/csaf/blob/74ec4239480ce5d83f9a56053ec4559b6d5b93a6/csaf_2.1/comment_resolution/log_from_csd04pr.md).
   Among the abbreviations:

   > CB = Christian Bucher

   Item 4 of the table, dated 2026-10-28, has the commenter "CB" and links to issue #1724, "CSD04 6.1.66 / 9.1.18:
   converted documents can change their year folder (Requirement 11)". Since 9 November 2026 it lists the resolution
   "Comment Resolution CSD04PR: #1724" (pull request #1739) and the disposition "Completed", which, according to the
   log, "indicates that the editors have implemented the changes on which the TC decided".

My own comment in the `csaf-comment` thread (item 2) is signed with my name.

## Timeline

| Date | Event |
|---|---|
| 2026-10-28 | Comment on the `csaf-comment` list (date as given in the committee's comment resolution log). |
| 2026-10-28 | TC meeting: a review comment on the converter's treatment of `initial_release_date` is discussed (draft minutes, pull request #1730). |
| 2026-10-28 | Issue #1724 opened in the CSAF TC's repository to track the comment. |
| October 2026 | Reply from Thomas Schmidt (BSI) on the list, with the link to issue #1724. |
| 2026-11-07 | Comment resolution log drafted in pull request #1735 ([`17ee1e5`](https://github.com/oasis-tcs/csaf/commit/17ee1e59d562d580d453ee80cd43a0110dc2cd95)); it lists "CB = Christian Bucher". Issue #1724 assigned to `tschmidtb51` and labelled `editor-revision`. First commit of the resolution ([`8f06f33`](https://github.com/oasis-tcs/csaf/commit/8f06f33fab3e28420f14e5b6188885b3caf7e83b)). |
| 2026-11-09 | Second commit of the resolution ([`0f014c2`](https://github.com/oasis-tcs/csaf/commit/0f014c2262c319b235d0c776f43e00a3866fc58a), "make year change explicit"). |
| 2026-11-09 | TC meeting: motions passed to accept the resolution pull requests, among them #1739 for #1724, as comment resolutions, and to request a ballot to promote CSD04 with these changes to CS01 (minutes in issue #1743). |
| 2026-11-09 | Pull request #1735 merged into the editor revision: the comment resolution log is now part of it. |
| 2026-11-09 | Pull request #1739 merged into the editor revision (merge commit `5425f92`). |
| 2026-11-09 | Comment resolution log updated with the decisions of that day's meeting: item 4 acknowledged on 2026-11-09, resolution "Comment Resolution CSD04PR: #1724" (pull request #1739), disposition "Completed" ([commit `74ec423`](https://github.com/oasis-tcs/csaf/commit/74ec4239480ce5d83f9a56053ec4559b6d5b93a6)). |
| 2026-11-09 | Editor revision merged into `master` with pull request #1747 (merge commit `c74c79a`); issue #1724 closed as completed; the merge commit is tagged `csaf-2.1-cs-01-20261109-rc1`. |
| — | Ballot on CS01 and publication: pending. |

## Status

**Resolved, merged for CSAF 2.1 CS01.** The resolution (pull request #1739) is merged into the editor revision and,
with pull request #1747, into `master`; the committee accepted it as comment resolution on 9 November 2026 (minutes in
issue #1743); the committee's comment resolution log marks item 4 "Completed"; issue #1724 is closed as completed.
Not done yet: the ballot on CS01 and its publication.

## How to verify

1. Open the [comment thread](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1):
   the comment, the reply and its signature.
2. Open [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724): first sentence, labels, assignee, status.
3. Open [pull request #1739](https://github.com/oasis-tcs/csaf/pull/1739): merged into `editor-revision-2026-11-09`,
   two commits, label `motion_passed`. The note as merged, at merge commit `5425f92`:
   [CVRF CSAF Converter](https://github.com/oasis-tcs/csaf/blob/5425f92370d40ea73c022cb239bfd401eed751f4/csaf_2.1/prose/edit/src/conformance-01-cls-05-cvrf-converter.md?plain=1#L238-L242),
   [CSAF 2.0 to CSAF 2.1 Converter](https://github.com/oasis-tcs/csaf/blob/5425f92370d40ea73c022cb239bfd401eed751f4/csaf_2.1/prose/edit/src/conformance-01-cls-18-csaf-2-0-converter.md?plain=1#L408-L412),
   [test 6.1.66](https://github.com/oasis-tcs/csaf/blob/5425f92370d40ea73c022cb239bfd401eed751f4/csaf_2.1/prose/edit/src/tests-01-mndtr-66-non-draft-initial-release-date.md?plain=1#L37-L41).
4. Open the [comment resolution log at commit `74ec423`](https://github.com/oasis-tcs/csaf/blob/74ec4239480ce5d83f9a56053ec4559b6d5b93a6/csaf_2.1/comment_resolution/log_from_csd04pr.md?plain=1#L13):
   line 13 ("CB = Christian Bucher") and item 4 in line 24, with "Completed" in the last column.
5. Open [issue #1743](https://github.com/oasis-tcs/csaf/issues/1743), "Meeting minutes 2026-11-09": the "Super Motion"
   with the line "Comment Resolution CSD04PR: #1724 #1739", and the motion on CS01.
6. Open [pull request #1747](https://github.com/oasis-tcs/csaf/pull/1747): merged into `master` on 9 November 2026,
   section "Editorial Changes". The
   [CSAF 2.1 folder on docs.oasis-open.org](https://docs.oasis-open.org/csaf/csaf/v2.1/) shows the published stages.
7. The rules referred to (clause 9.1.18, test 6.1.66, Requirement 11, section 7.4) are in the
   [CSAF 2.1 CSD04 document](https://docs.oasis-open.org/csaf/csaf/v2.1/csd04/csaf-v2.1-csd04.html).
8. Recount the numbers from the public dumps with the [counting script](./delivered/count_6_1_66.py); the steps are in
   [`delivered/README.md`](./delivered/README.md).
9. Open [pull request #1730](https://github.com/oasis-tcs/csaf/pull/1730) (draft minutes of 28 October 2026) or the
   [file at commit `694df97`](https://github.com/oasis-tcs/csaf/blob/694df97606c36576920e08964a0a1ae1248e6aa3/meeting_minutes/2026/2026-10-28.md),
   section "CSAF 2.1 CSD04 Public Review".

Related: [1. CIRCL](../01-circl-vulntrain/README.md), whose Vulnerability-Lookup dumps provided the documents.

---

Last checked: 9 November 2026 · [← Back to overview](../README.md)
