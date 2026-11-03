# 5. STScI and MAST: POSS-I plate dates in the DSS plate list

[← Back to overview](../README.md) · [What I delivered](./delivered/) · [Where my name appears](#where-my-name-appears) · [How to verify](#how-to-verify)

**Status: delivered.** Correction package public under CC BY 4.0; adoption by STScI is not publicly documented
(as of 3 November 2026).

## Who they are

- **STScI**, in its own words: "We are the Space Telescope Science Institute in Baltimore, Maryland, operated by the
  Association of Universities for Research in Astronomy. We help humanity explore the universe with advanced space
  telescopes and ever-growing data archives." ([STScI on GitHub](https://github.com/spacetelescope),
  [stsci.edu](https://www.stsci.edu/))
- **MAST and the Digitized Sky Survey (DSS):** MAST, the Mikulski Archive for Space Telescopes, is STScI's archive. Its
  Catalogs and Surveys Group lists the surveys of the DSS, among them the first Palomar Observatory Sky Survey (POSS-I)
  with its red (E) and blue (O) plates ([survey list](https://gsss.stsci.edu/SkySurveys/Surveys.htm)).

## Summary

A correction package for the POSS-I plate dates in the MAST plate list `SurveyPlateListLatest.csv` (2024): on about
three quarters of the plates the listed date is one day early, because it is the date on which the night began. For
each of the 1,870 POSS-I rows of the list (937 POSSI-E, 933 POSSI-O) the package gives the action needed, a proposed UT
date and time and the evidence. I reported the findings to the MAST helpdesk on 13 October 2026 and published the
package under CC BY 4.0.

## What I found

- On about three quarters of the plates the listed date is one day early: it is the date on which the night began, not
  the UT date of the exposure. The correction is then exactly one day.
- Gross errors in 8 E and 8 O rows, for example: the night of 1953-12-31 is listed as 1953-01-01 (XE603, XE666, XE730
  and the corresponding O plates); for XE217, XE864 and XO217 the UT date and time, hour angle, zenith distance and
  airmass were copied from XE001A.
- 44 POSSI-E plate IDs in the 2024 file were changed by a spreadsheet: 24 lost a leading zero and 20 are in scientific
  notation.

The package's actions per row:

| Action | Meaning | E rows | O rows |
|---|---|---|---|
| `date_plus_1d` | add one day to the listed date, keep the time | 706 | 700 |
| `no_change` | listed date and time are right | 218 | 220 |
| `replace_time` | set the proposed time | 1 | 0 |
| `replace_date_time` | gross error: set the proposed date and time | 8 | 8 |
| `review_keep_listed` | no proposal; keep the listed value until the log is checked | 4 | 5 |

## What I delivered

The package `poss1-plate-dates`, in [`delivered/poss1-plate-dates/`](./delivered/poss1-plate-dates/) (index:
[`delivered/README.md`](./delivered/README.md)):

| File | What it is |
|---|---|
| [`README.md`](./delivered/poss1-plate-dates/README.md) | Findings, how to apply the corrections, method, sources, license |
| [`poss1_E_dates.csv`](./delivered/poss1-plate-dates/poss1_E_dates.csv), [`poss1_O_dates.csv`](./delivered/poss1-plate-dates/poss1_O_dates.csv) | One row per list row, in list order (937 E, 933 O; 42 columns): action, proposed `UTobservation` (= `DATE-OBS`, UT start of exposure), evidence; where needed a proposed `Epoch`, hour angle, zenith distance and airmass |
| [`columns.csv`](./delivered/poss1-plate-dates/columns.csv) | Every column: type, unit, sign convention, allowed values |
| [`known_anomalies.csv`](./delivered/poss1-plate-dates/known_anomalies.csv) | 84 single cases and systematic issues, each with evidence and a suggested action |
| [`night_blocks_E.csv`](./delivered/poss1-plate-dates/night_blocks_E.csv), [`summary.json`](./delivered/poss1-plate-dates/summary.json) | Runs of nights with one date convention; all counts |
| [`other_surveys_ha.json`](./delivered/poss1-plate-dates/other_surveys_ha.json) | The hour-angle test applied to every survey of the list |
| [`evidence/external_checks.json`](./delivered/poss1-plate-dates/evidence/external_checks.json) | Older plate list, 10 DSS FITS headers, FitsArchive directory listings |
| [`inputs/asteroid_checks.csv`](./delivered/poss1-plate-dates/inputs/asteroid_checks.csv) | Asteroid-trail verdicts for 35 E plates |
| [`scripts/`](./delivered/poss1-plate-dates/scripts/) | `build_tables.py`, `check_external.py`, `other_surveys_ha.py`, `run_all.sh`: rebuild everything except the asteroid checks from public files |
| [`MANIFEST.txt`](./delivered/poss1-plate-dates/MANIFEST.txt) | SHA-256 of all files |

## What changed

Not publicly documented. Whether STScI has changed the plate list, the DSS database or the FITS headers is not recorded
in any public source I know of (as of 3 November 2026).

## Where my name appears

No public text by STScI names me. My name appears only in the package itself: its author line and the suggested credit
line "C. Bucher (2026), POSS-I plate dates in the MAST plate list".

## Timeline

| Date | Event |
|---|---|
| 2026-10-13 | Findings reported to the MAST helpdesk (according to the package README). |
| 2026-10-14 | Version date of the package. |
| 2026-10-17 | Package published in this repository. |

## Status

**Delivered.** Public under CC BY 4.0; adoption by STScI not publicly documented.

## How to verify

1. **Integrity:** in [`delivered/poss1-plate-dates/`](./delivered/poss1-plate-dates/), `sha256sum -c MANIFEST.txt`
   checks all 14 other files.
2. **One row as an example:** in [`poss1_E_dates.csv`](./delivered/poss1-plate-dates/poss1_E_dates.csv), the row with
   `Region` XE603 has `listed_UTobservation` 1953-01-01T08:43:12, `action` `replace_date_time` and
   `proposed_UTobservation` 1954-01-01T08:43:00.
3. **Rebuild:** `bash scripts/run_all.sh workdir` downloads the two public inputs (the 2024 MAST plate list and VizieR
   catalogue VI/25), checks their SHA-256, rebuilds the tables (Python ≥ 3.8, numpy, astropy) and compares every output
   byte by byte with the package (README, section 5).

Related: [3. AIP](../03-aip-applause/README.md), another archive of photographic plates.

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
