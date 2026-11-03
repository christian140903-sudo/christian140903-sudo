# Review comment on CSAF 2.1 CSD04 (csaf-comment list)

[← OASIS/BSI details](../README.md) · [← Overview](../../README.md)

Public comment by Christian Bucher on the OASIS `csaf-comment` list, October 2026. Copied on 3 November 2026 from the
[thread](https://groups.oasis-open.org/discussion/csd04-6-1-66-9-1-18-converted-documents-can-change-their-year-folder-requirement-11-1),
wording unchanged.

**Subject:** CSD04 6.1.66 / 9.1.18: converted documents can change their year folder (Requirement 11)

---

Dear CSAF TC,

I checked how the new initial_release_date rule in 9.1.18 (test 6.1.66, #1691) affects published documents: 40,882 CSAF 2.0 documents from 50 publishers, taken from the CIRCL vulnerability-lookup dumps of 4 October 2026 (excluding Red Hat and SUSE).

The converter would replace initial_release_date in 12,765 of them, almost all from Cisco (2,850) and MSRC (9,808). In 9,658 MSRC documents revision 1 is dated later than initial_release_date, and almost all of these already fail test 6.2.5. For them the converter moves initial_release_date later, in 2,041 documents into a later year (in 1,436 by more than 365 days).

One example:\
<https://msrc.microsoft.com/csaf/vex/2023/msrc_cve-2023-0225.json>\
initial_release_date is 2023-04-01; the only revision ("1", "Information published.") is dated 2024-10-15. After conversion, initial_release_date is 2024-10-15, so Requirement 11 places the CSAF 2.1 document in folder 2024, while the CSAF 2.0 document and its self reference use 2023.

During the parallel distribution described in 7.4, the same document would then sit in two different year folders. Is that intended? If so, would it help if the converter's warning also mentioned the year change?

Happy to share the per-document list and the counting script.

Best regards,

Christian Bucher
