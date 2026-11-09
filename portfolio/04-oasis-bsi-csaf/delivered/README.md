# Delivered to the OASIS CSAF TC: review comment and counting script

[← OASIS/BSI details](../README.md) · [← Overview](../../README.md)

**Delivered:** a public review comment on CSAF 2.1 Committee Specification Draft 04, posted on the OASIS `csaf-comment`
list in October 2026.
**Public today:** tracked as [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724) in the CSAF TC's repository
("The below issue was created on behalf of Christian Bucher:"); resolved on 9 November 2026 and merged for CS01
([pull request #1739](https://github.com/oasis-tcs/csaf/pull/1739); details under
[What changed](../README.md#what-changed)).

| File | What it is | Public today |
|---|---|---|
| [`csaf-comment-csd04.md`](./csaf-comment-csd04.md) | The review comment as posted (wording unchanged): counts, one worked example, and the question to the TC | The [comment thread](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1); [issue #1724](https://github.com/oasis-tcs/csaf/issues/1724) |
| [`count_6_1_66.py`](./count_6_1_66.py) | Counting script that reproduces every number in the comment (Python 3, standard library only; version of 29 October 2026). It applies test 6.1.66, clause 9.1.18 and test 6.2.5 to every CSAF 2.0 document of the dumps and prints the key numbers. The comment offers it: "Happy to share the per-document list and the counting script." | Published here |
| [`input-files.sha256`](./input-files.sha256) | SHA-256 of the 50 input files: the `csaf_*.ndjson` files of the CIRCL Vulnerability-Lookup dumps of 4 October 2026, except Red Hat, SUSE and openSUSE | Published here |

**Run it** (about 650 MB of downloads), in an empty folder that holds the two files above:

```bash
for f in $(awk '{print $2}' input-files.sha256); do
    curl -O https://vulnerability.circl.lu/dumps/$f
done
sha256sum -c input-files.sha256        # macOS: shasum -a 256 -c input-files.sha256
python3 count_6_1_66.py --csv documents_6_1_66.csv csaf_*.ndjson
```

The output ends with the key numbers of the comment: 40,882 documents, 50 dump files, 12,765 documents in which
`initial_release_date` is replaced (2,850 Cisco, 9,808 MSRC), 9,658 MSRC documents in which revision 1 is dated later,
2,041 of them moving into a later year and 1,436 by more than 365 days. If CIRCL has updated the dumps since,
`sha256sum -c` reports it.

The script's docstring also mentions `README-EN.md` and the per-document list `documents_6_1_66.csv` (40,882 rows):
they are not reproduced here; the `--csv` option above recreates the list from the dumps.
