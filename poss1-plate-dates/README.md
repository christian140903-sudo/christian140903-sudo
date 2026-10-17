# POSS-I plate dates in the MAST plate list (2024): corrections for the DSS database and FITS headers

Christian Bucher, independent researcher, Vienna (christian140903@gmail.com). Version of 2026-10-14 20:38 UTC.
Follow-up to MAST helpdesk ticket INC0227319 (2026-10-13).

**Purpose.** For each of the 937 POSSI-E and 933 POSSI-O rows of `SurveyPlateListLatest.csv` (2024) the tables give
the action needed, a proposed `UTobservation` (= `DATE-OBS`, UT start of exposure), the evidence for it and, where
needed, a proposed `Epoch`, `hourangle`, `zenithdistance` and `airmass`. On about three quarters of the plates the
listed date is one day early: it is the date on which the night began. Everything except the asteroid checks is
rebuilt from public files by the scripts; every number below is in `summary.json` or `other_surveys_ha.json`.

## 1. Applying the corrections

| file | content |
|---|---|
| `poss1_E_dates.csv`, `poss1_O_dates.csv` | one row per list row, in list order (937 E, 933 O; 42 columns) |
| `columns.csv` | every column: type, unit, sign convention, allowed values |
| `known_anomalies.csv` | 84 single cases and systematic issues, each with evidence and a suggested action |
| `night_blocks_E.csv`, `summary.json` | runs of nights with one date convention; all counts |
| `other_surveys_ha.json` | the hour-angle test applied to every survey of the list (section 2.6) |
| `evidence/external_checks.json` | older plate list, 10 DSS FITS headers, FitsArchive directory listings |
| `inputs/asteroid_checks.csv` | asteroid-trail verdicts for 35 E plates (earlier work, not rebuilt here) |
| `scripts/` | `build_tables.py`, `check_external.py`, `other_surveys_ha.py`, `run_all.sh` |
| `MANIFEST.txt` | sha256 of all files (`sha256sum -c MANIFEST.txt`) |

**Key.** Join on `Survey` + `Region` + `plateID_restored`. Region alone is not unique (XE884, XO093, XO094 and XO095
occur twice). 44 E plateIDs of the 2024 CSV were changed by a spreadsheet: 24 lost a leading zero and 20 are in
scientific notation, ten of them `0.00E+00`. `plateID_restored` takes these from the FitsArchive file names
(XE269 `08E0`, XE691 `0E20`, XE366 `0725`, ...). All other POSS-I plateIDs equal the file names, except XE001B and the
second rows of XO093/094/095 (no file with that ID) and 100 O rows whose Region has no file.

**Per row, column `action`:**

| `action` | what to do with `UTobservation` / `DATE-OBS` | E rows | O rows |
|---|---|---|---|
| `date_plus_1d` | add one day to the listed date, keep the time | 706 | 700 |
| `no_change` | listed date and time are right | 218 | 220 |
| `replace_time` | set `proposed_UTobservation` (XE389: 07:00 → 06:36) | 1 | 0 |
| `replace_date_time` | gross error: set `proposed_UTobservation` | 8 | 8 |
| `review_keep_listed` | no proposal; keep the listed value until the log is checked | 4 | 5 |

`time_refinement_s` (−18 to +18 s) is the difference between the listed time and the VI/25 minute. The list stores
times as 0.01 h; in all 920 E and 915 O regular rows the listed time is the VI/25 minute rounded that way, so this
refinement is optional and not part of the error. Rows of one exposure (`duplicate`, `same_exposure_as`) carry the
same action. A correction applies to every scan and descendant of a plate (FitsArchive holds several files for some
plates, e.g. `xe271_08e2_00_00` and `xe271_08e2_00_03`).

**What changes and what does not.**
- `UTobservation` / `DATE-OBS`: as above. The value is the start of the exposure in UT (1949–1958 predates UTC; at the
  one-minute precision of the log the choice of UT realisation does not matter). Mid-exposure = start + half of
  `vi25_exp_min` (= `EXPOSURE`).
- `TIME-OBS` is blank in all 9 sampled full-plate headers; `DATE-OBS` carries date and time. It can stay blank.
- `hourangle` / `OBSHA`, `zenithdistance` / `OBSZD`, `airmass` / `AIRMASS` do **not** change with the date. `hourangle`
  is the logged starting hour angle (east-positive; whole minutes in 936 of 937 E and 933 of 933 O rows).
  `zenithdistance` follows from it, the listed J2000 declination and the latitude (residuals, 1st to 99th percentile,
  −0.16 to +0.13° for E), and `airmass` is the Hardie (1962) formula of `zenithdistance` (largest deviation 0.0012 E,
  0.0014 O; plain sec z deviates by up to 0.013). The logged values already fit the corrected date: the hour angle
  computed from `proposed_UTobservation` via sidereal time differs from the logged one typically by about +0.5 min
  (logged minus computed; peak +0.50 E, +0.41 O, section 4). Please keep them; recomputing would only replace logged
  values by computed ones. Exceptions, with replacement values in the row (`proposed_hourangle`,
  `proposed_zenithdistance`, `proposed_airmass`): XE217, XE864 and XO217, whose four values were copied from XE001A,
  and XE389, whose `hourangle` 23.33413 is +0.66587 h stored with the sign flipped modulo 24 h (VI/25: 00:40 E).
- `Epoch`: `epoch_action` is `keep` where the listed value agrees with the proposed start within half a unit of its
  last decimal plus 0.25 d (a kept value can therefore differ slightly from `proposed_Epoch`), else `recompute` (44 E,
  2 O rows); then use `proposed_Epoch`. It is empty in the rows without a proposal. The listed Epochs follow the
  calendar-year fraction of the start: within 0.25 d, 682 of 724 three-decimal E Epochs of regular rows fit it and 33
  more fit the start minus 1 d, while the Julian epoch fits 421 and the Besselian 470. Please confirm the DSS
  definition. A one-day error in Epoch moves a position propagated with 1″/yr proper motion by 2.7 mas.
- `REF*` refraction cards: not examined here.

**FITS headers.** In all 9 sampled full-plate headers `DATE-OBS` has its closing quote after the comment and writes
decimal hours as hh:mm (A83). Example XE325, now
`DATE-OBS= '1950-04-12T08:90:00 /Observation: Date' /Observation: Date`, proposed
`DATE-OBS= '1950-04-13T08:54:00' / Observation: start of exposure (UT)`.

**Open items.** No proposal: XE321, XE723, XE787, XE915, XO321, XO617, XO683, XO687, XO787 (known_anomalies gives
each conflict). Before changing XE098/XO098, an asteroid-trail check is advised (section 3).

## 2. Findings

### 2.1 The listed date is the evening date, in blocks of nights
"Evening date" describes the value: it equals the date on which the night began, i.e. the UT date of the start minus
one day. It is not the local calendar date of the start: 300 of the 702 evening-date E exposures began after local
midnight, where the PST date is already one day later, and the list still gives the earlier date. The correction is
therefore always exactly +1 d.

| nights (evening date) | listed date | nights | E exposures |
|---|---|---|---|
| 1949-11-18 – 1949-11-29 | correct | 5 | 9 |
| 1949-12-21 – 1952-12-21 | evening date | 125 | 245 |
| 1953-01-08 – 1954-01-02 | correct | 74 | 191 |
| 1954-01-03 · 1954-01-04 | evening · correct | 1 · 1 | 3 · 4 |
| 1954-01-27 – 1956-06-02 | evening date | 156 | 437 |
| 1957-04-27 – 1957-04-29 | correct | 3 | 9 |
| 1957-12-19 · 1957-12-20 | evening · correct | 1 · 1 | 3 · 3 |
| 1958-02-16 – 1958-12-10 | evening date | 7 | 14 |

Among the red plates classed `evening_date` or `correct`, no night of the 374 mixes conventions, and the blue plates
follow the red plates of their night, with one exception: in the night of 1951-06-27/28 XE389 is listed with the UT
date (its clock time is 24 min off, class `clock_mismatch`) while XO389 carries the evening date. The 1958 block is southern only; its last night with hour-angle support is 1958-07-11 (XE923), the night of
1958-12-10 is XE723, whose hour angle contradicts it (unresolved). By UT year the listed date is right in 1949 (Nov),
1953 and 1957, the years after a leap year, and one day early in the others: years ≡ 1 (mod 4) 5 evening / 208
correct E exposures, other years 697 / 8. The exceptions are four nights within two weeks of New Year (nights
1949-12-21, 1954-01-02, 1954-01-04, 1957-12-19). The night of 1953-12-31 is listed as 1953-01-01 (XE603, XE666, XE730
and their blue plates, section 2.3): day and month were advanced to the UT date, the year was not. This describes the
data; we do not know the mechanism. As a hint only: a date routine with an error in the four-year leap cycle could
explain the pattern of whole years, but not by itself the exception nights around New Year. The pattern may point to the step that
produced `UTobservation`.

The VI/25 times are Pacific Standard Time all year: with the VI/25 start, 448 of 461 E exposures of April–September
lie within 1.5 min of the hour-angle peak and none within 1.5 min of ±60 min (October–March: 430 of 445, none).

### 2.2 Southern zone, XE/XO723–936 (fields at Dec −11° to −31°; XE876 holds a plate of another field)
The label number is the VI/25 number + 1 (157 E rows) or the −30° zone is spelled `ES84` for VI/25 `S 84` (57 E rows);
field centre, clock time and hour angle identify the same exposures. These rows follow the same blocks: 175 evening /
33 correct E exposures. They have no physical witness of their own (section 3).

### 2.3 Gross errors (8 E, 8 O rows)
XE603, XE666, XE730 (and the O plates): listed 1953-01-01, true 1954-01-01. XE217, XE864, XO217: UT, hour angle, zenith
distance and airmass copied from XE001A. XE498/XO498: VI/25 record 1079 contradicts itself; asteroids give
1954-06-01 04:48 UT. XE098/XO098 and XE128/XO128: VI/25 records 1425 and 673 disagree with both neighbouring plate
numbers; the neighbours' night is used because hour angle and Epoch fit it. XO864 (label `1607`): paired by field. Its
listed time + 1 d (1956-05-11T10:58) gives the field the hour angle of the proposed start within 0.7 min, so the hour angle does
not decide; 1950 rests on VI/25, Epoch 1950.546 and the red plate XE864 of the same field (label E192, i.e. VI/25 191
by the rule of section 2.2; Epoch also 1950.546). See the row's note and A32.

### 2.4 Clock mismatches: the logged hour angle decides 15 of 19
In 9 E and 10 O rows the listed clock time differs from VI/25 (by whole hours, 1 to 8 h, except XE389 with 24 min). The
logged hour angle does not depend on either clock entry. On the VI/25 date it fits the listed clock time in 14 rows
(VI/25 is 1–4 h off there) and the VI/25 time for XE389, each within 1.5 min, and misses the other time by more than
10 min. With date offsets of 0 or 1 d the sidereal time cannot alias such clock differences. Undecided: XE787, XO787
(8 h), XE915 (fits the listed clock only on the listed date), XO617 (see 2.5).

### 2.5 Hour-angle disagreements with VI/25
XE200, XE692, XO057, XO576: the computed hour angle agrees with the list; VI/25 is off by 60 or 282 min; nothing to
change. XE856 and XO617: the VI/25 hour angle fits only with E and W swapped. XE389: see section 1.

### 2.6 Other surveys: an indication only
The same hour-angle test on the POSSII-J/F/N rows of the list (hour angles also in whole minutes, east-positive)
shows the same two peaks, 3.9 min apart, and the same dependence on the year. POSSII-J: 223 rows on the no-shift
peak, 587 one day early, 74 elsewhere (of 884); in years ≡ 1 (mod 4) 204 no-shift against 5 one-day, in all other
years 19 against 582 (POSSII-F 226/15 and 11/556; POSSII-N 182/2 and 3/626). There is no second witness for POSS-II
here: a one-day error in the sidereal time behind the logged hour angles would look the same. An asteroid-trail check
of a few POSS-II plates would decide. The other surveys use other hour-angle conventions; their results are in the
file and not interpreted.

## 3. Evidence and limits

| evidence_level | meaning | E | O |
|---|---|---|---|
| `asteroid-confirmed` | decisive asteroid-trail check agrees | 30 | – |
| `catalogue+HA` | VI/25 date and time, hour angle agrees | 857 | 875 |
| `catalogue date+HA, listed clock` | VI/25 date, listed clock time, hour angle agrees (2.4) | 6 | 8 |
| `catalogue+Epoch` | gross error, Epoch agrees | 5 | 5 |
| `indirect` | VI/25 record replaced by the neighbours' night (XE/XO098, XE/XO128) | 2 | 2 |
| `catalogue-only` | hour angle unclear or polar, or in conflict while the other-colour plate of the night or asteroid-confirmed plates of the same run support VI/25 | 33 | 38 |
| `unresolved` | no proposal | 4 | 5 |

- All 30 decisive asteroid checks agree with the VI/25 rule. The 35 checked E plates were chosen in earlier work
  (plates near the ecliptic from a subset defined for another purpose, stratified by how listed date, VI/25 and Epoch
  relate, plus plates with unusual log entries). They are not a random sample and all lie in XE055–XE641. For that set the
  disagreement rate is below 9.5 % (95 %, one-sided; two-sided limit 11.6 %). The southern rows have no physical
  witness; they rest on clock time and hour angle. XE325 is named here because it is the FITS example of section 1 and,
  like most plates, has no physical witness of its own: 1950-04-13 08:54 UT rests on VI/25 and the E and O hour angles
  (one clock). Its Epoch 1950.278 points to April 12, one day before the start, as in most of XE308–XE347 (A64).
- VI/25 is the 1995 transcription of the 1960 catalogue; no logbook was consulted. Records 673 and 1425 are
  contradicted by their neighbours, Epoch and hour angle, record 1079 by itself; others may be wrong unnoticed.
- The hour-angle test cannot tell one day from a 3.94-min clock or reading offset, and `hourangle` comes from the same
  log as VI/25. In Nov 1949 the asteroid-confirmed XE464 and XE468 show the one-day signature although their listed
  date is right. The two peaks (+0.50 and −3.48 min, E) are 3.98 min apart, where one day gives 3.94 min; 683 + 216
  of 937 E rows lie on them. Per plate the robust scatter is 0.43 min and 2.4 % of non-polar plates lie more than half
  a day shift from their peak.
- XE098: the neighbours' night (1955-05-17 07:15 UT) and the record's own night with the listed clock time
  (1955-03-17 11:15 UT) fit the hour angle equally well, because 61 days move sidereal time by 240 min and the clock
  times differ by 240 min. Epoch favours May, but for XE498 (same pattern) the Epoch pointed the wrong way and only the
  asteroids decided.
- Agreement of a listed time with the hour angle is no proof on its own: for XE498 the listed time fits the hour angle
  with the one-day shift, yet the asteroids put the start two months later and 4 h earlier.
- XE876 holds a second scan of plate E1144 (as XE628; its FITS header says so); the red plate of field VI/25 1150 is
  absent. VI/25 1618 and 895 share RA and differ by exactly 1° in Dec; 895 (1953) has no row (XE722/XO722 absent). The
  100 Whiteoak records of VI/25 (MLP 938–1037, no start times) have no row in the list and were not examined.
- Counts are complete counts of the list, not a sample. The table is wrong for a plate if VI/25's night or start time
  is wrong for it and no witness caught it.

## 4. Method
Each row is paired with the VI/25 record whose number equals the label number and whose field centre (B1950 → ICRS)
lies within 0.5°; failing that, label number − 1 (157 rows XE/XO723–936 and 4 blue plates of Nov 1949) or the
spelling `ES84`/`S 84`; one blue row (XO864) pairs by field only. All rows pair; the largest centre offset is 0.34°.
The VI/25 ReadMe defines `Obs` as the day the night began and the start times as PST, so the UT start is
`Obs + ObsE + 8 h`, plus 24 h if `ObsE` < 12 h (`ObsO` for blue plates). The listed clock time equals this within
±2 min for 924 E / 919 O rows, and `hourangle` equals the VI/25 starting hour angle within ±1.5 min for 931 E / 929 O
rows, so the rows describe the same exposures. Class: the date offset is checked first (−1 d `evening_date`, 0
`correct`, otherwise `gross_error`), then a clock difference over 2 min makes `clock_mismatch`. The VI/25-independent
test uses `hourangle`: computed from the listed date, time, field centre and longitude, residuals form a no-shift peak
(+0.50 min E, +0.41 O); a row's verdict is "consistent" within ±1.5 min of it and "1 d early" within ±1.5 min of
that peak minus 3.94 min (not used at |Dec| ≥ 80°). Thirty E plates have decisive asteroid-trail checks (DSS cutouts
against SkyBoT predictions for each candidate date). A VI/25 record whose night differs by ≥ 28 d from both adjacent
plate numbers is replaced by the neighbours' night only if hour angle and Epoch both fit. The message of 2026-10-13
counted northern rows only (533/186 E); `summary.json` → `reconciliation_E`/`_O` reproduces it and the extended count
(707/219 of 926 E rows) and lists every difference to the tables here.

## 5. Sources and rebuild
(1) `SurveyPlateListLatest.csv`, attachment version 1 (2024-06-20) on https://outerspace.stsci.edu/x/JDGECg, sha256
`62947dc6…aded706834`. (2) VI/25 `nposs.dat` (Palomar Obs. 1960, ADC version 1995),
https://cdsarc.cds.unistra.fr/ftp/VI/25/, sha256 `77be67e2…6ac8180991`; `ReadMe` `ea9fc69f…a64e118`. Optional:
https://gsss.stsci.edu/skysurveys/SurveyPlateList.txt, DSS headers and FitsArchive listings from archive.stsci.edu
(read 2026-10-14; URLs, times and checksums in `evidence/external_checks.json`).
`bash scripts/run_all.sh workdir` downloads (1) and (2), checks the sha256, runs `build_tables.py` and
`other_surveys_ha.py` (Python ≥ 3.8, numpy, astropy) and compares every output byte by byte with this package
(identical tables expected; exit code 3 otherwise). `WITH_EXTERNAL=1` re-reads the STScI sources first.

## 6. Use
The tables, scripts and this README are released under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/):
STScI/MAST and anyone else may use, modify and redistribute them, including in archive databases and FITS headers.
Please credit "C. Bucher (2026), POSS-I plate dates in the MAST plate list" in documentation or release notes; no
per-record credit in database rows or FITS headers is needed. Columns prefixed `vi25_` reproduce VizieR catalogue VI/25
(CDS, Strasbourg); please acknowledge CDS/VizieR as usual when citing those values.
