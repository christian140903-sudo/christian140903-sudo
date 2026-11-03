# Delivered for STScI/MAST: POSS-I plate dates, correction package

[← STScI/MAST details](../README.md) · [← Overview](../../README.md)

**Delivered:** findings reported to the MAST helpdesk on 13 October 2026; the correction package (version of
14 October 2026) published in this repository on 17 October 2026, under CC BY 4.0.
**Public today:** this package. Adoption by STScI is not publicly documented.
**This copy:** identical to the package as published on 17 October 2026, except the author line of `README.md`, from
which a contact address was removed on 3 November 2026 (`MANIFEST.txt` updated accordingly).

| File | What it is |
|---|---|
| [`poss1-plate-dates/README.md`](./poss1-plate-dates/README.md) | Findings, how to apply the corrections, method, sources, license (CC BY 4.0) |
| [`poss1-plate-dates/poss1_E_dates.csv`](./poss1-plate-dates/poss1_E_dates.csv) | One row per POSSI-E row of the list (937 rows, 42 columns) |
| [`poss1-plate-dates/poss1_O_dates.csv`](./poss1-plate-dates/poss1_O_dates.csv) | One row per POSSI-O row of the list (933 rows, 42 columns) |
| [`poss1-plate-dates/columns.csv`](./poss1-plate-dates/columns.csv) | Every column: type, unit, sign convention, allowed values |
| [`poss1-plate-dates/known_anomalies.csv`](./poss1-plate-dates/known_anomalies.csv) | 84 single cases and systematic issues |
| [`poss1-plate-dates/night_blocks_E.csv`](./poss1-plate-dates/night_blocks_E.csv) | Runs of nights with one date convention |
| [`poss1-plate-dates/summary.json`](./poss1-plate-dates/summary.json) | All counts |
| [`poss1-plate-dates/other_surveys_ha.json`](./poss1-plate-dates/other_surveys_ha.json) | Hour-angle test applied to every survey of the list |
| [`poss1-plate-dates/evidence/external_checks.json`](./poss1-plate-dates/evidence/external_checks.json) | Older plate list, 10 DSS FITS headers, FitsArchive directory listings (URLs, times, checksums) |
| [`poss1-plate-dates/inputs/asteroid_checks.csv`](./poss1-plate-dates/inputs/asteroid_checks.csv) | Asteroid-trail verdicts for 35 E plates (not rebuilt by the scripts) |
| [`poss1-plate-dates/scripts/build_tables.py`](./poss1-plate-dates/scripts/build_tables.py) | Builds the tables from the public inputs |
| [`poss1-plate-dates/scripts/check_external.py`](./poss1-plate-dates/scripts/check_external.py) | Re-reads the STScI sources |
| [`poss1-plate-dates/scripts/other_surveys_ha.py`](./poss1-plate-dates/scripts/other_surveys_ha.py) | Hour-angle test for the other surveys |
| [`poss1-plate-dates/scripts/run_all.sh`](./poss1-plate-dates/scripts/run_all.sh) | Downloads the inputs, checks them, rebuilds and compares byte by byte |
| [`poss1-plate-dates/MANIFEST.txt`](./poss1-plate-dates/MANIFEST.txt) | SHA-256 of all files (`sha256sum -c MANIFEST.txt`) |
