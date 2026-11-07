# 4. OASIS CSAF TC and BSI: public review of CSAF 2.1 (CSD04)

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: open.** The review comment is tracked as [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724); the
committee has not decided yet. The draft minutes of its meeting on 28 October 2026 list the converter/date feedback
for discussion on 9 November.

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
#1724, "created on behalf of Christian Bucher". The issue is open.

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

- Thomas Schmidt (BSI) replied on the comment list, and the committee opened
  [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724) to track the comment (label `csdpr04-v-2-1-feedback`).
- The draft minutes of the TC meeting on 28 October 2026
  ([pull request #1730](https://github.com/oasis-tcs/csaf/pull/1730), file `meeting_minutes/2026/2026-10-28.md`, opened
  2026-11-03, not yet approved) record the discussion of a review comment that "concerned the converter's treatment of
  an advisory whose `initial_release_date` differs from the initial entry in its revision history". The section ends:

  > Members were asked to consider the trade-off before the **November 9** meeting.
  > **No resolution or change to the conversion rules was approved at this meeting.**

  Among the action items: "**TC members** to review the converter/date feedback and prepare their positions for
  discussion on November 9". The minutes do not name the author of the comment.
- Nothing has been decided: the issue is open, and no change to the specification is documented.

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

My own comment in the same thread is signed with my name.

## Timeline

| Date | Event |
|---|---|
| October 2026 | Comment on the `csaf-comment` list; the list shows relative dates only. |
| 2026-10-28 | TC meeting: a review comment on the converter and `initial_release_date` is discussed; according to the draft minutes (pull request #1730, opened 2026-11-03), it "had not yet been transferred into the GitHub issue list". |
| 2026-10-28 | Issue #1724 opened in the CSAF TC's repository to track the comment. |
| October 2026 | Reply from Thomas Schmidt (BSI) on the list, with the link to issue #1724. |
| 2026-11-09 | TC meeting ("the next additional TC meeting" in the draft minutes); the converter/date feedback is listed for discussion. |
| — | Decision by the committee: pending. |

## Status

**Open.** No decision by the committee yet; the draft minutes of 28 October list the converter/date feedback for
discussion on 9 November.

## How to verify

1. Open the [comment thread](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1):
   the comment, the reply and its signature.
2. Open [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724): first sentence, label, status.
3. The rules referred to (clause 9.1.18, test 6.1.66, Requirement 11, section 7.4) are in the
   [CSAF 2.1 CSD04 document](https://docs.oasis-open.org/csaf/csaf/v2.1/csd04/csaf-v2.1-csd04.html).
4. Recount the numbers from the public dumps with the [counting script](./delivered/count_6_1_66.py); the steps are in
   [`delivered/README.md`](./delivered/README.md).
5. Open [pull request #1730](https://github.com/oasis-tcs/csaf/pull/1730), file `meeting_minutes/2026/2026-10-28.md`, section
   "CSAF 2.1 CSD04 Public Review".

Related: [1. CIRCL](../01-circl-vulntrain/README.md), whose Vulnerability-Lookup dumps provided the documents.

---

Last checked: 7 November 2026 · [← Back to overview](../README.md)
