# 3. AIP: APPLAUSE plate archive (DR3 and DR4)

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: acknowledged.** Erratum with my name in the DR3 and DR4 documentation; the data correction is announced for a
further data release.

## Who they are

- **AIP**, in its own words: "The Leibniz Institute for Astrophysics Potsdam (AIP) is dedicated to astrophysical
  questions ranging from the study of our Sun to the evolution of the cosmos." ([aip.de](https://www.aip.de/en/))
- **APPLAUSE** ("Archives of Photographic PLates for Astronomical USE") is a database of digitised astronomical
  photographic plates: "The APPLAUSE database is a service by the Leibniz-Institute for Astrophysics Potsdam (AIP)."
  ([plate-archive.org](https://www.plate-archive.org/), [imprint](https://www.plate-archive.org/cms/imprint/))

## Summary

I pointed out that the observing-site latitude and longitude are stored in swapped columns for two plate archives
(`archive_id` 205 and 208) in the APPLAUSE plate tables. AIP added an erratum naming me to the documentation of data
releases DR3 and DR4 and announced that "The errors will be corrected in a further data release."

## What I found

The columns `site_latitude` and `site_longitude` are swapped for `archive_id` 205 and 208 in DR4, and for 205 in DR3.
According to AIP's errata, the swap also affects the zenith-angle and airmass values in table `source_calib` and is
carried over into the corresponding FITS files.

## What I delivered

A written report to the archive maintainers in October 2026. It was sent as correspondence and is not reproduced here
(see [`delivered/`](./delivered/)); the public record of it is the erratum quoted below.

## What changed

AIP added errata notes, dated 10/2026, to the plate-table documentation of
[DR4](https://www.plate-archive.org/metadata/applause_dr4/plate/) and
[DR3](https://www.plate-archive.org/metadata/applause_dr3/plate/). The correction of the data itself is announced for a
further data release and has not been published yet.

## Where my name appears

1. **APPLAUSE DR4, plate-table documentation**, 10/2026
   ([link](https://www.plate-archive.org/metadata/applause_dr4/plate/)):

   > Errata: [10/2026] User (C. Bucher, Wien) has pointed out that the column names site_latitude and site_longitude
   > are swapped. The swap also affects the zenit_angle and airmass values in table source_calib. It's also carried over
   > into the corresponding fits files. This is true for archive_id=208 and archive_id=205. The errors will be corrected
   > in a further data release.

2. **APPLAUSE DR3, plate-table documentation**, 10/2026
   ([link](https://www.plate-archive.org/metadata/applause_dr3/plate/)):

   > Errata: [10/2026] User (C. Bucher, Wien) has pointed out that the column names site_latitude and site_longitude
   > are swapped. The swap also affects the zenit_angle and airmass values in table source_calib. It is also carried
   > over into the corresponding fits files. This is true for archive_id=205. The errors will be corrected in a further
   > data release.

The quotes keep AIP's original spelling ("zenit_angle").

## Timeline

| Date | Event |
|---|---|
| October 2026 | Report to the archive maintainers; errata published in the DR3 and DR4 documentation (the pages give month and year only). |
| Not yet dated | Data correction "in a further data release". |

## Status

**Acknowledged.** Erratum with my name; the data correction is still to come.

## How to verify

1. Open the [DR4 plate-table page](https://www.plate-archive.org/metadata/applause_dr4/plate/) and the
   [DR3 plate-table page](https://www.plate-archive.org/metadata/applause_dr3/plate/) and search for "Errata" or
   "Bucher".
2. Operator of the database: [imprint](https://www.plate-archive.org/cms/imprint/).

Related: [5. STScI and MAST](../05-stsci-mast-poss1/README.md), another archive of photographic plates.

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
