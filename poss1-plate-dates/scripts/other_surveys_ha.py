#!/usr/bin/env python3
"""other_surveys_ha.py -- the VI/25-independent hour-angle test of build_tables.py applied to every survey of the
MAST plate list (2024). Indication only: outside POSS-I there is no second witness here.

Input (public): --plates SurveyPlateListLatest.csv (sha256 62947dc6...6834, see build_tables.py for the URL).
Output: --out other_surveys_ha.json

Per survey: residual = listed hourangle minus the hour angle computed from the listed UT date and time, the
listed longitude (west) and the listed field centre (ICRS, precessed and nutated to date), in minutes, both
east-positive. The sign convention of the listed hourangle is not known for every survey, so both are tried and
the one with more residuals within 10 min of zero is kept. If the listed date is right the residual sits on a
"no-shift" peak (log offsets, about 0.3-0.5 min); if it is one day early, 3.94 min lower (sidereal time gains
3.94 min per day at the same clock time). Polar fields (|Dec| >= 80 deg) are left out. The no-shift peak is the
median of residuals in (-2, +2) min; a row is counted on a peak if it lies within 1.5 min of it.
Grouping is by the listed UT year (and that year modulo 4).

What the layer below does on failure: csv.DictReader yields None for short rows; such rows and unparsable
timestamps or numbers are counted as skipped per survey, never filled in. A checksum mismatch stops the run
(exit 2) unless --allow-other-version is given. Requires Python >= 3.8, numpy, pyerfa.
Run: python3 -I other_surveys_ha.py --plates SurveyPlateListLatest.csv --out other_surveys_ha.json
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import erfa

SHA_PLATES = "62947dc69bf2de3903ff6c7c038e5db49d36ae21bb121c2c7c9960aded706834"
SID_SHIFT_MIN = 1440 * 0.00273790935
PEAK_TOL_MIN = 1.5
MAX_ABS_DEC = 80.0


def ha_west_hours(t, ra_deg, dec_deg, lon_w_deg):
    """Same computation as build_tables.py (GMST IAU 1982 + equation of the equinoxes; IAU 1976/80 precession-
    nutation of the field centre to date; TT - UT taken as 60 s, irrelevant at this level)."""
    d1, d2 = erfa.cal2jd(t.year, t.month, t.day)
    d2 += (t.hour + t.minute / 60 + t.second / 3600) / 24
    gast = erfa.gmst82(d1, d2) + erfa.eqeq94(d1, d2 + 60.0 / 86400)
    v = erfa.rxp(erfa.pnm80(d1, d2 + 60.0 / 86400), erfa.s2c(math.radians(ra_deg), math.radians(dec_deg)))
    ra_d, _ = erfa.c2s(v)
    ha = (gast - math.radians(lon_w_deg) - ra_d + math.pi) % (2 * math.pi) - math.pi
    return math.degrees(ha) / 15.0


def wrap(x):
    return ((x + 720.0) % 1440.0) - 720.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-other-version", action="store_true")
    a = ap.parse_args()
    h = hashlib.sha256(open(a.plates, "rb").read()).hexdigest()
    if h != SHA_PLATES and not a.allow_other_version:
        print(f"ERROR: plate list sha256 {h} differs from {SHA_PLATES}", file=sys.stderr)
        sys.exit(2)
    by = defaultdict(list)
    with open(a.plates, newline="", encoding="ascii") as f:
        for r in csv.DictReader(f):
            by[r["Survey"]].append(r)
    out = dict(input=dict(file=a.plates.split("/")[-1], sha256=h), method=" ".join(__doc__.split("\n\n")[1].split()),
               sid_shift_min=round(SID_SHIFT_MIN, 4), surveys={})
    for s in sorted(by):
        R, skipped, polar = [], 0, 0
        for r in by[s]:
            try:
                t = datetime.fromisoformat(r["UTobservation"].strip())   # surveys differ: hh:mm, hh:mm:ss, hh:mm:ss.sss
                x = dict(t=t, ra=float(r["RightAscension"]), dec=float(r["Declination"]), ha=float(r["hourangle"]),
                         lon=float(r["longitude"]))
            except (ValueError, TypeError, AttributeError):
                skipped += 1
                continue
            if abs(x["dec"]) >= MAX_ABS_DEC:
                polar += 1
                continue
            x["hw"] = ha_west_hours(t, x["ra"], x["dec"], x["lon"])
            R.append(x)
        rec = dict(rows=len(by[s]), used=len(R), skipped_unparsable=skipped, polar_excluded=polar)
        if len(R) < 50:
            rec["note"] = "fewer than 50 usable rows, not evaluated"
            out["surveys"][s] = rec
            continue
        best = None
        for sign, name in ((1, "east-positive"), (-1, "west-positive")):
            res = np.array([wrap((x["hw"] + sign * (x["ha"] - 24 * round(x["ha"] / 24))) * 60) for x in R])
            n10 = int(np.sum(np.abs(res) < 10))
            if best is None or n10 > best[0]:
                best = (n10, name, res)
        n10, conv, res = best
        win = res[(res > -2) & (res < 2)]
        if win.size < 10:
            rec.update(hourangle_convention=conv, within_10_min=n10, note="fewer than 10 residuals in (-2, +2) min: no peak, not evaluated")
            out["surveys"][s] = rec
            continue
        c0 = float(np.median(win))
        c1 = c0 - SID_SHIFT_MIN
        lab = []
        for r_ in res:
            a0, a1 = abs(r_ - c0), abs(r_ - c1)
            lab.append("no_shift" if a0 <= PEAK_TOL_MIN and a0 < a1 else ("one_day" if a1 <= PEAK_TOL_MIN and a1 < a0 else "other"))
        one = res[np.array([l == "one_day" for l in lab])]
        yr, m4 = defaultdict(Counter), defaultdict(Counter)
        for x, l in zip(R, lab):
            yr[x["t"].year][l] += 1
            m4[x["t"].year % 4][l] += 1
        rec.update(hourangle_convention=conv, within_10_min=n10,
                   whole_minute_fraction=round(float(np.mean([abs(x["ha"] * 60 - round(x["ha"] * 60)) < 0.01 for x in R])), 3),
                   peak_no_shift_min=round(c0, 2), peak_one_day_median_min=round(float(np.median(one)), 2) if one.size else None,
                   rows_no_shift=lab.count("no_shift"), rows_one_day=lab.count("one_day"), rows_other=lab.count("other"),
                   by_UT_year={str(y): [yr[y]["one_day"], yr[y]["no_shift"], yr[y]["other"]] for y in sorted(yr)},
                   by_UT_year_mod4={str(k): [m4[k]["one_day"], m4[k]["no_shift"], m4[k]["other"]] for k in sorted(m4)},
                   years_mod4_eq_1_vs_other={"mod4 = 1": [m4[1]["one_day"], m4[1]["no_shift"], m4[1]["other"]],
                                             "mod4 != 1": [sum(m4[k][l] for k in (0, 2, 3)) for l in ("one_day", "no_shift", "other")]})
        out["surveys"][s] = rec
    out["columns_of_by_year"] = ["one_day (listed date 1 d early)", "no_shift (listed date consistent)", "other"]
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, allow_nan=False)
    for s, rec in out["surveys"].items():
        if "rows_no_shift" in rec:
            print(f"{s:14s} n={rec['used']:4d} {rec['hourangle_convention']:13s} whole-min {rec['whole_minute_fraction']:.2f} "
                  f"no-shift {rec['rows_no_shift']:4d} @ {rec['peak_no_shift_min']:+.2f}  one-day {rec['rows_one_day']:4d}  "
                  f"other {rec['rows_other']:4d}  mod4 {rec['by_UT_year_mod4']}")


if __name__ == "__main__":
    main()
