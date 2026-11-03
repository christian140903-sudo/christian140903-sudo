#!/usr/bin/env python3
"""build_tables.py -- POSS-I plate dates in the MAST/STScI plate list (2024) checked against the
Palomar Observatory Sky Survey "Catalogue of Plates" (machine-readable version, VizieR VI/25).

Inputs (public; pass local paths as arguments):
  --plates  SurveyPlateListLatest.csv
            MAST page "Photographic Sky Surveys", https://outerspace.stsci.edu/x/JDGECg
            attachment version 1, modificationDate 2024-06-20:
            https://outerspace.stsci.edu/download/attachments/176435492/SurveyPlateListLatest.csv?version=1&modificationDate=1718908770237&api=v2
            sha256 62947dc69bf2de3903ff6c7c038e5db49d36ae21bb121c2c7c9960aded706834
  --nposs   nposs.dat of VizieR VI/25 (Palomar Obs. 1960; ADC version of 1995-12-12)
            https://cdsarc.cds.unistra.fr/ftp/VI/25/nposs.dat
            sha256 77be67e26ce95d34f46c82650252473eb6e13ea4c8c815b70d74356ac8180991
            byte layout from https://cdsarc.cds.unistra.fr/ftp/VI/25/ReadMe
            (sha256 ea9fc69f4f74fab613aec9b87c9f0d59c4ca357bbf7ab43eccb30e483a64e118)
Optional:
  --asteroids  asteroid_checks.csv (shipped with the package, see README; not derived from the two inputs)
  --external   external_checks.json (written by check_external.py: older plate list, DSS FITS headers,
               FitsArchive directory listings; the listings give column plateID_restored)
Outputs in --out:
  poss1_E_dates.csv, poss1_O_dates.csv, known_anomalies.csv, night_blocks_E.csv, summary.json, columns.csv

Rule for the true start (VI/25 ReadMe: Obs.D = "Day on which the observing night began",
ObsE/ObsO = "Exposure start times in Pacific Standard Time"):
  true UT start = Obs 00:00 + ObsE (or ObsO) + 8 h, plus 24 h if ObsE < 12 h.
Exception: if the Obs date of a VI/25 record differs by >= 28 d from both records with the adjacent
plate numbers (which agree with each other), the neighbours' night is used instead, but only when
both the listed Epoch and the listed hourangle support it (evidence level "indirect").
Clock mismatches (listed clock time != VI/25 start, date offset 0 or -1 d): the logged hour angle is
independent of both clock entries; if it fits one clock time on the VI/25 date within HA_TOL_MIN and
misses the other by more than CLOCK_SEP_MIN, that clock time is proposed (otherwise no proposal).

What the layer below does on failure (and what this script does): csv.DictReader silently yields
None for short rows, so required columns are checked explicitly; a checksum mismatch, a missing
column or an unparsable timestamp stops the run (exit code 2); nothing is filled with defaults.
Requires Python >= 3.8, numpy, astropy (with pyerfa). Run: python3 -I build_tables.py --help
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
import erfa
import astropy.units as u
from astropy.coordinates import FK4, ICRS, SkyCoord

SHA_PLATES = "62947dc69bf2de3903ff6c7c038e5db49d36ae21bb121c2c7c9960aded706834"
SHA_NPOSS = "77be67e26ce95d34f46c82650252473eb6e13ea4c8c815b70d74356ac8180991"

MAX_SEP_DEG = 0.5      # field-centre tolerance for a pair (VI/25 B1950 centre -> ICRS vs. list centre)
CLOCK_TOL_MIN = 2.0    # listed clock time vs. VI/25 start time + 8 h
HA_ID_TOL_MIN = 1.5    # listed hourangle vs. VI/25 starting hour angle (identity check)
HA_TOL_MIN = 1.5       # sidereal-time test: distance to the "no shift" / "one day" peak
HA_MAX_ABS_DEC = 80.0  # sidereal-time test not used closer to the pole (field-centre RA ill-defined)
NEIGHBOUR_DAYS = 28    # VI/25 record vs. both adjacent plate numbers
RUN_DAYS = 7           # "same run" window for the asteroid context of an hour-angle conflict
SID_SHIFT_MIN = 1440 * 0.00273790935  # 3.9426 min: sidereal gain of the same UT clock time one day later
CLOCK_SEP_MIN = 10.0   # clock mismatch: the rejected clock time must miss the hour-angle peak by more than this
TIME_ROUND_S = 18      # the list stores times as 0.01 h (36 s): a change up to 18 s is rounding, not an error
EPOCH_ENTRY_MAX_D = 60.0  # known_anomalies "Epoch (< 60 d)": day and month errors; larger offsets go with the gross errors
EPOCH_MONTH_MIN_D = 20.0  # within that entry: "Epoch off by about one month"
DAY_MIN = 1440.0
REGULAR = ("evening_date", "correct")

MON = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
NEED_COLS = ["plateID", "longitude", "latitude", "plateLabel", "Survey", "Region", "RightAscension", "Declination",
             "SeeingCode", "plateGrade", "Epoch", "UTobservation", "hourangle", "zenithdistance", "airmass"]
LABEL_RE = re.compile(r"^(?P<pfx>[EO]?)(?P<zone>[SQ]?)(?P<num>\d+)$")
SEEING_MONTH_RE = re.compile(r"^(\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d\d)$")


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(2)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


# ----------------------------------------------------------------------------- inputs
def read_plate_list(path):
    with open(path, newline="", encoding="ascii") as f:
        rd = csv.DictReader(f)
        missing = [c for c in NEED_COLS if c not in (rd.fieldnames or [])]
        if missing:
            die(f"plate list lacks columns {missing}")
        rows = list(rd)
    for i, r in enumerate(rows):
        if None in r.values() or None in r:
            die(f"plate list row {i + 2} has the wrong number of fields")
    return rows


def _int(s):
    s = s.strip()
    return int(s) if s else None


def vi25_key(poss):
    """'S 84' -> 'S84', ' 570' -> '570' (ReadMe: the S must be kept, numbers repeat elsewhere)."""
    s = poss.strip()
    return "S" + str(int(s[1:].strip())) if s.startswith("S") else str(int(s))


def read_vi25(path):
    rows = []
    with open(path, encoding="ascii") as f:
        for ln, line in enumerate(f, 1):
            line = line.rstrip("\n").ljust(150)

            def b(a, z):
                return line[a - 1:z]  # 1-based inclusive byte ranges of the ReadMe
            r = dict(rec=ln, POSS=b(1, 4).strip(), MLP=_int(b(6, 9)), Y=_int(b(73, 76)), M=b(78, 80).strip(),
                     D=_int(b(82, 83)), fM=b(85, 87).strip(), fD=_int(b(89, 90)),
                     E_h=_int(b(92, 93)), E_m=_int(b(95, 96)), O_h=_int(b(98, 99)), O_m=_int(b(101, 102)),
                     EHA_h=_int(b(104, 105)), EHA_m=_int(b(107, 108)), EHA_ew=b(110, 110).strip(),
                     OHA_h=_int(b(112, 113)), OHA_m=_int(b(115, 116)), OHA_ew=b(118, 118).strip(),
                     Eexp=_int(b(120, 121)), Oexp=_int(b(123, 124)),
                     RAh=_int(b(134, 135)), RAm=_int(b(137, 138)), RAs=_int(b(140, 141)), DEsign=b(142, 142),
                     DEd=_int(b(143, 144)), DEm=_int(b(146, 147)), DEs=_int(b(149, 150)))
            if r["Y"] is None or r["M"] not in MON or r["D"] is None:
                die(f"VI/25 record {ln}: unparsable observing date")
            r["key"] = vi25_key(r["POSS"])
            r["obs"] = datetime(r["Y"], MON[r["M"]], r["D"])
            nxt = r["obs"] + timedelta(days=1)
            r["fobs_ok"] = (MON.get(r["fM"]) == nxt.month and r["fD"] == nxt.day)
            r["id"] = f"{r['POSS']}|{r['MLP']}"
            rows.append(r)
    ra = np.array([15.0 * (r["RAh"] + r["RAm"] / 60 + r["RAs"] / 3600) for r in rows])
    de = np.array([(-1 if r["DEsign"] == "-" else 1) * (r["DEd"] + r["DEm"] / 60 + r["DEs"] / 3600) for r in rows])
    c = SkyCoord(ra * u.deg, de * u.deg, frame=FK4(equinox="B1950", obstime="B1950")).transform_to(ICRS())
    for r, a, d in zip(rows, c.ra.deg, c.dec.deg):
        r["ra"], r["de"] = float(a), float(d)
    neighbour_check(rows)
    return rows


def neighbour_check(vi):
    """Flag records whose night differs by >= NEIGHBOUR_DAYS from both adjacent plate numbers (n-1, n+1),
    when those two agree within 1 d. Only numeric POSS numbers of POSS-I proper (MLP <= 937)."""
    by = defaultdict(list)
    for v in vi:
        if v["MLP"] <= 937 and not v["key"].startswith("S"):
            by[int(v["key"])].append(v)
    for v in vi:
        v["nb_alt"] = None
        if v["MLP"] > 937 or v["key"].startswith("S"):
            continue
        n = int(v["key"])
        nb = by.get(n - 1, []) + by.get(n + 1, [])
        if len(nb) < 2:
            continue
        ds = sorted(w["obs"] for w in nb)
        if (ds[-1] - ds[0]).days <= 1 and min(abs((v["obs"] - d).days) for d in ds) >= NEIGHBOUR_DAYS:
            v["nb_alt"] = ds[0]
            v["nb_txt"] = ", ".join(f"{w['POSS']}: {w['obs']:%Y-%m-%d}" for w in nb)


# ----------------------------------------------------------------------------- helpers
def sep_deg(a1, d1, a2, d2):
    a1, d1, a2, d2 = map(math.radians, (a1, d1, a2, d2))
    x = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, x))))


def wrap_min(x):
    return ((x + DAY_MIN / 2) % DAY_MIN) - DAY_MIN / 2


def parse_ut(s):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def decyear(t):
    """Calendar-year fraction (the definition the listed Epoch values follow, see summary epoch_definition_test)."""
    y0, y1 = datetime(t.year, 1, 1), datetime(t.year + 1, 1, 1)
    return t.year + (t - y0).total_seconds() / (y1 - y0).total_seconds()


def jd_of(t):
    return 2440587.5 + (t - datetime(1970, 1, 1)).total_seconds() / 86400


def julian_epoch(t):
    return 2000.0 + (jd_of(t) - 2451545.0) / 365.25


def besselian_epoch(t):
    return 1900.0 + (jd_of(t) - 2415020.31352) / 365.242198781


def zd_deg(ha_h, dec_deg, lat_deg):
    """Zenith distance from hour angle (h), declination and latitude; the list's zenithdistance follows this
    with the listed (J2000) declination and the listed hourangle (see summary fields_vs_hourangle)."""
    f, d = math.radians(lat_deg), math.radians(dec_deg)
    c = math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(math.radians(15.0 * ha_h))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def hardie_airmass(z_deg):
    """Hardie (1962) airmass; the list's airmass follows this formula of its zenithdistance."""
    s = 1.0 / math.cos(math.radians(z_deg))
    x = s - 1.0
    return s - 0.0018167 * x - 0.002875 * x * x - 0.0008083 * x ** 3


def read_mod24(h, ref_east_h):
    """A listed hourangle outside +-12 h can be (a) the east-positive value modulo 24 h or (b) the same with the
    sign flipped (= the west-positive value modulo 24 h). (b) is used only if it, and not (a), matches the
    VI/25 starting hour angle within HA_ID_TOL_MIN. Returns (east-positive signed hours, reading)."""
    a = h - 24.0 if h > 12 else h + 24.0
    if ref_east_h is not None and abs(-a - ref_east_h) * 60 <= HA_ID_TOL_MIN < abs(a - ref_east_h) * 60:
        return -a, "modulo 24 h with the sign flipped"
    return a, "modulo 24 h"


def g7(v):
    return "" if v is None else f"{v:.7g}"


def epoch_tol_days(s):
    """Epoch is given with 0-3 decimals: half a unit of the last digit, plus 0.25 d for the day fraction."""
    nd = len(s.split(".")[1]) if "." in s else 0
    return 0.5 * 10 ** (-nd) * 365.25 + 0.25


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(c - h, 4), round(c + h, 4)]


def ha_west_hours(t, ra_deg, dec_deg, lon_w_deg):
    """Hour angle (west positive, hours) of the list's field centre (read as ICRS/J2000) at UT t.
    GAST = GMST(IAU 1982) + equation of the equinoxes (IAU 1994); centre precessed+nutated to date (IAU 1976/80).
    UT1 := listed UT (|UT1-UT| << 1 s is irrelevant against 3.94 min); TT = UT + 29 s (Delta T 1950s)."""
    d1, d2 = erfa.cal2jd(t.year, t.month, t.day)
    d2 += (t.hour + t.minute / 60 + t.second / 3600) / 24
    gast = erfa.gmst82(d1, d2) + erfa.eqeq94(d1, d2 + 29.0 / 86400)
    v = erfa.rxp(erfa.pnm80(d1, d2 + 29.0 / 86400), erfa.s2c(math.radians(ra_deg), math.radians(dec_deg)))
    ra_d, _ = erfa.c2s(v)
    ha = gast - math.radians(lon_w_deg) - ra_d
    ha = (ha + math.pi) % (2 * math.pi) - math.pi
    return math.degrees(ha) / 15.0


def zone_of(region):
    m = re.match(r"^X[EO](\d+)", region)
    n = int(m.group(1)) if m else -1
    if n == 1001:          # 'XO1001' = blue plate of the second polar field (red: XE001B)
        n = 1
    return "001-722" if n < 723 else "723-936"


def fmt_t(t, sec=False):
    if t is None:
        return ""
    return t.strftime("%Y-%m-%dT%H:%M:%S" if sec else "%Y-%m-%dT%H:%M")


def r2(x, n=2):
    return "" if x is None else round(x, n)


# ----------------------------------------------------------------------------- pairing and per-row evaluation
def pair_rows(rows, vi, band):
    bykey = defaultdict(list)
    for v in vi:
        bykey[v["key"]].append(v)
    out = []
    for p in rows:
        ra, de = float(p["RightAscension"]), float(p["Declination"])
        m = LABEL_RE.match(p["plateLabel"].strip())
        tries = []
        if m:
            n = int(m.group("num"))
            tries = [("ES/S spelling", "S%d" % n)] if m.group("zone") else \
                [("number+field", str(n)), ("number-1", str(n - 1))]
        match = None
        for rule, key in tries:
            c = sorted(((sep_deg(ra, de, v["ra"], v["de"]), v) for v in bykey.get(key, [])), key=lambda t: t[0])
            c = [t for t in c if t[0] < MAX_SEP_DEG]
            if c:
                match = (rule, c[0][0], c[0][1])
                break
        near = sorted(((sep_deg(ra, de, v["ra"], v["de"]), v) for v in vi), key=lambda t: t[0])[:2]
        if match is None and near[0][0] < MAX_SEP_DEG:
            match = ("field only", near[0][0], near[0][1])
        out.append(dict(p=p, label_ok=bool(m) and m.group("pfx") == band, match=match, nearest=near, band=band))
    return out


def start_from(v, band, obs):
    h, mi = (v["E_h"], v["E_m"]) if band == "E" else (v["O_h"], v["O_m"])
    if h is None:
        return None
    t = obs + timedelta(hours=h + 8, minutes=mi)
    return t + timedelta(hours=24) if h < 12 else t


def evaluate(P, band):
    lon_w = float(P[0]["p"]["longitude"])
    if any(abs(float(x["p"]["longitude"]) - lon_w) > 1e-6 for x in P):
        die("longitude differs between rows")
    for x in P:
        p = x["p"]
        x["t_list"] = parse_ut(p["UTobservation"])
        if x["t_list"] is None:
            die(f"unparsable UTobservation {p['UTobservation']!r} ({p['Region']})")
        x["hourangle_h"] = float(p["hourangle"])          # as listed (east-positive)
        x["epoch"] = float(p["Epoch"]) if p["Epoch"].strip() else None
        x["ra"], x["dec"] = float(p["RightAscension"]), float(p["Declination"])
        x["ha_ok_dec"] = abs(x["dec"]) < HA_MAX_ABS_DEC
        x.update(true=None, day_off=None, clock=None, ha_id=None, ha_resid_true=None, epoch_true_d=None,
                 alt_used=False, alt_txt="", alt_second=None, v_start=None, v_ha=None, v_exp=None, v_ha_east=None,
                 clock_fix=None, clock_test=None, ew_swap=None)
        v = x["match"][2] if x["match"] is not None else None
        if v is not None:
            hah, ham, haew = (v["EHA_h"], v["EHA_m"], v["EHA_ew"]) if band == "E" else (v["OHA_h"], v["OHA_m"], v["OHA_ew"])
            if hah is not None:
                x["v_ha_east"] = (hah + ham / 60) * (-1 if haew == "W" else 1)
        # signed east-positive hour angle actually used; differs from the listed value only beyond +-12 h
        x["ha_east_h"], x["ha_reading"] = x["hourangle_h"], ""
        if abs(x["hourangle_h"]) > 12:
            x["ha_east_h"], x["ha_reading"] = read_mod24(x["hourangle_h"], x["v_ha_east"])
        # residual = listed minus computed hour angle, east-positive, minutes (= computed minus listed, west-positive)
        x["resid"] = lambda t, x=x: wrap_min((ha_west_hours(t, x["ra"], x["dec"], lon_w) + x["ha_east_h"]) * 60)
        x["ha_resid_listed"] = x["resid"](x["t_list"])
        if v is None:
            continue
        h, mi = (v["E_h"], v["E_m"]) if band == "E" else (v["O_h"], v["O_m"])
        x["v_start"] = None if h is None else f"{h:02d}:{mi:02d}"
        x["v_ha"] = None if hah is None else f"{hah:02d}:{ham:02d} {haew}".strip()
        x["v_exp"] = v["Eexp"] if band == "E" else v["Oexp"]
        if x["v_ha_east"] is not None:
            x["ha_id"] = wrap_min((x["ha_east_h"] - x["v_ha_east"]) * 60)   # listed minus VI/25, east-positive
        set_true(x, start_from(v, band, v["obs"]))
        x["raw"] = dict(day_off=x["day_off"], clock=x["clock"])
    # sidereal-time peaks, from the listed timestamps only (VI/25-independent); polar fields excluded
    r = np.array([x["ha_resid_listed"] for x in P if x["ha_ok_dec"]])
    c0 = float(np.median(r[(r > -2) & (r < 2)]))
    c1 = float(np.median(r[(r > -6) & (r < -2)]))
    for x in P:
        x["c0"] = c0
        x["ha_verdict"] = ha_verdict(x["ha_resid_listed"], c0) if x["ha_ok_dec"] else "n/a (|Dec| >= 80)"
    # VI/25 records whose night disagrees with both neighbours: use the neighbours' night if Epoch and HA agree
    for x in P:
        if x["match"] is None or x["match"][2]["nb_alt"] is None or x["true"] is None:
            continue
        v = x["match"][2]
        alt = start_from(v, band, v["nb_alt"])
        ra_ = x["resid"](alt) - c0
        ep = (x["epoch"] - decyear(alt)) * 365.25 if x["epoch"] is not None else None
        ok_ha = x["ha_ok_dec"] and abs(ra_) <= HA_TOL_MIN
        ok_ep = ep is not None and abs(ep) <= epoch_tol_days(x["p"]["Epoch"])
        # second candidate: the record's own night with the listed clock time (a date shift of n days moves
        # sidereal time by n x 3.94 min, so a clock difference of the same size can hide it)
        own = x["true"]
        t2 = own + timedelta(minutes=round(wrap_min((x["t_list"] - own).total_seconds() / 60)))
        r2_ = x["resid"](t2) - c0
        ep2 = (x["epoch"] - decyear(t2)) * 365.25 if x["epoch"] is not None else None
        ok2_ha = x["ha_ok_dec"] and abs(r2_) <= HA_TOL_MIN
        x["alt_txt"] = (f"VI/25 night {v['obs']:%Y-%m-%d} differs from adjacent numbers ({v['nb_txt']}); "
                        f"with their night the start is {fmt_t(alt)}: hourangle residual {ra_ + c0:+.2f} min "
                        f"({'fits' if ok_ha else 'does not fit'}), Epoch {ep:+.1f} d ({'fits' if ok_ep else 'does not fit'})"
                        + f"; with the record's own night and its own clock time: {x['ha_resid_true']:+.2f} min, Epoch {x['epoch_true_d']:+.1f} d"
                        + f"; with the record's own night and the listed clock time ({fmt_t(t2)}): {r2_ + c0:+.2f} min "
                        f"({'fits' if ok2_ha else 'does not fit'}), Epoch {ep2:+.1f} d")
        x["alt_second"] = dict(t=fmt_t(t2), ha_resid=round(r2_ + c0, 2), ha_fits=ok2_ha, epoch_d=round(ep2, 1),
                               days=(alt.date() - t2.date()).days, clock_min=round(wrap_min((alt - t2).total_seconds() / 60)))
        if ok_ha and ok_ep:
            set_true(x, alt)
            x["alt_used"] = True
    # clock mismatches: which clock time does the logged hour angle support on the VI/25 date?
    for x in P:
        if x["true"] is None or x["day_off"] not in (-1, 0) or abs(x["clock"]) <= CLOCK_TOL_MIN or not x["ha_ok_dec"]:
            continue
        t_l = x["true"] + timedelta(minutes=round(x["clock"]))
        r_v, r_l = x["resid"](x["true"]) - c0, x["resid"](t_l) - c0
        x["clock_test"] = dict(listed_clock_on_vi25_date=fmt_t(t_l), resid_vi25_clock=round(r_v + c0, 2),
                               resid_listed_clock=round(r_l + c0, 2))
        if abs(r_l) <= HA_TOL_MIN and abs(r_v) > CLOCK_SEP_MIN:
            x["clock_fix"] = ("listed clock", t_l)
        elif abs(r_v) <= HA_TOL_MIN and abs(r_l) > CLOCK_SEP_MIN:
            x["clock_fix"] = ("VI/25 clock", x["true"])
    # VI/25 hour angle against the hour angle computed for the VI/25 start, as printed and with E/W swapped
    for x in P:
        if x["true"] is None or x["v_ha_east"] is None or not x["ha_ok_dec"]:
            continue
        hw = ha_west_hours(x["true"], x["ra"], x["dec"], lon_w)
        r_vi, r_sw = wrap_min((hw + x["v_ha_east"]) * 60) - c0, wrap_min((hw - x["v_ha_east"]) * 60) - c0
        x["phys_ha_east_min"] = -hw * 60
        if abs(r_sw) <= HA_TOL_MIN and abs(r_vi) > CLOCK_SEP_MIN:
            x["ew_swap"] = (round(r_vi + c0, 1), round(r_sw + c0, 1))
    return dict(peak_no_shift_min=round(c0, 3), peak_one_day_min=round(c1, 3), peak_separation_min=round(c0 - c1, 3),
                expected_separation_min=round(SID_SHIFT_MIN, 4), lon_w_deg=lon_w, c0=c0)


def set_true(x, t):
    x["true"] = t
    if t is None:
        return
    x["day_off"] = (x["t_list"].date() - t.date()).days
    x["clock"] = wrap_min((x["t_list"] - t).total_seconds() / 60)
    x["ha_resid_true"] = x["resid"](t)
    x["epoch_true_d"] = (x["epoch"] - decyear(t)) * 365.25 if x["epoch"] is not None else None


def ha_verdict(res, c0):
    a, b = abs(res - c0), abs(res - (c0 - SID_SHIFT_MIN))
    if a <= HA_TOL_MIN and a < b:
        return "listed date consistent"
    if b <= HA_TOL_MIN and b < a:
        return "listed date 1 d early"
    return "unclear"


def classify(x):
    if x["match"] is None or x["true"] is None:
        return "unpaired"
    if x["day_off"] not in (-1, 0):
        return "gross_error"
    if abs(x["clock"]) > CLOCK_TOL_MIN:
        return "clock_mismatch"
    return "evening_date" if x["day_off"] == -1 else "correct"


def ha_agrees(x):
    """Does the VI/25-independent hour-angle verdict agree with the class? None = not decidable."""
    if x["cls"] == "evening_date":
        return {"listed date 1 d early": True, "listed date consistent": False}.get(x["ha_verdict"])
    if x["cls"] == "correct":
        return {"listed date consistent": True, "listed date 1 d early": False}.get(x["ha_verdict"])
    return None


# ----------------------------------------------------------------------------- asteroid checks (optional input)
def read_asteroids(path):
    if not path:
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(row for row in f if not row.startswith("#"))
        return {r["Region"]: r for r in rd}


def assign_evidence(tables, ast):
    for band, P in tables.items():
        for x in P:
            p = x["p"]
            a = ast.get(p["Region"]) if band == "E" else None
            x["ast_txt"], x["ast_agree"], x["ast_dec"] = "", None, False
            if a and x["exp_first"]:
                if a["plateLabel"] != p["plateLabel"]:
                    die(f"asteroid table label mismatch for {p['Region']}")
                x["ast_txt"] = f"{a['strength']}: supports {a['supported_UT_date'] or '-'} ({a['hits']})"
                if a["strength"] in ("decisive", "weak") and x["true"] is not None:
                    x["ast_agree"] = a["supported_UT_date"] == x["true"].strftime("%Y-%m-%d")
                x["ast_dec"] = a["strength"] == "decisive"
            ep_ok = x["epoch_true_d"] is not None and abs(x["epoch_true_d"]) <= epoch_tol_days(p["Epoch"])
            cls = x["cls"]
            if x["ast_dec"] and x["ast_agree"] is not None:
                ev = "asteroid-confirmed" if x["ast_agree"] else "unresolved"
            elif x["alt_used"]:
                ev = "indirect"
            elif cls in REGULAR:
                ev = {True: "catalogue+HA", False: "unresolved", None: "catalogue-only"}[ha_agrees(x)]
            elif cls == "gross_error":
                ev = "catalogue+Epoch" if ep_ok else "catalogue-only"
            elif cls == "clock_mismatch":
                ev = "unresolved" if x["clock_fix"] is None else (
                    "catalogue+HA" if x["clock_fix"][0] == "VI/25 clock" else "catalogue date+HA, listed clock")
            else:
                ev = "unresolved"
            x["evidence"], x["ep_ok"] = ev, ep_ok
    # an hour-angle conflict on one plate is downgraded to "catalogue-only" (VI/25 date kept) when
    # (a) the other-colour plate of the same field and night agrees with VI/25 (catalogue+HA or asteroids), or
    # (b) asteroid-confirmed plates of the same run (+-RUN_DAYS) show the same conflict.
    partner = {b: {x["match"][2]["id"]: x for x in P if x["match"] and x["exp_first"]} for b, P in tables.items()}
    conf = [x for x in tables["E"] if x["evidence"] == "asteroid-confirmed" and ha_agrees(x) is False]
    for band, P in tables.items():
        other = partner["O" if band == "E" else "E"]
        for x in P:
            if not (x["evidence"] == "unresolved" and x["cls"] in REGULAR and ha_agrees(x) is False):
                continue
            y = other.get(x["match"][2]["id"])
            if y is not None and y["cls"] == x["cls"] and y["evidence"] in ("asteroid-confirmed", "catalogue+HA"):
                x["evidence"] = "catalogue-only"
                x["partner_ctx"] = f"{y['p']['Region']} ({y['evidence']})"
                continue
            near = [z["p"]["Region"] for z in conf
                    if abs((z["match"][2]["obs"] - x["match"][2]["obs"]).days) <= RUN_DAYS]
            if near:
                x["evidence"] = "catalogue-only"
                x["run_ctx"] = ", ".join(sorted(set(near)))


def gross_alternative(tables):
    """Gross errors whose listed time + 1 d fits the logged hour angle as well as the proposed start. A date shift moves
    sidereal time by 3.94 min per day, so a shift of months or years together with another clock time can land on almost
    the same sidereal time; the hour angle cannot decide then. Records the alternative and what the proposal rests on.
    Text only: class, start, action and evidence level are not changed here."""
    rec = {b: {x["match"][2]["id"]: x for x in P if x["match"] and x["exp_first"]} for b, P in tables.items()}
    for band, P in tables.items():
        other = rec["O" if band == "E" else "E"]
        for x in P:
            x["gross_alt"] = None
            if (x["cls"] != "gross_error" or x["true"] is None or x["evidence"] == "unresolved" or x["alt_used"]
                    or x["copy_of"] or x["ha_verdict"] != "listed date 1 d early"):
                continue
            t1 = x["t_list"] + timedelta(days=1)
            r1, rp = x["resid"](t1) - x["c0"], x["ha_resid_true"] - x["c0"]
            if abs(r1) > HA_TOL_MIN or abs(rp) > HA_TOL_MIN:
                continue
            v = x["match"][2]
            basis = [f"VI/25 POSS {v['POSS']} (night {v['obs']:%Y-%m-%d}" + ("" if v["fobs_ok"] else ", record inconsistent in itself") + ")"]
            if x["ast_dec"] and x["ast_agree"]:
                basis.append(f"the decisive asteroid-trail check (supports {x['true']:%Y-%m-%d}; column asteroid_verdict)")
            if x["ep_ok"]:
                basis.append(f"Epoch {x['p']['Epoch']} ({x['epoch_true_d']:+.1f} d)")
            y = other.get(v["id"])
            if y is not None and y["evidence"] in ("asteroid-confirmed", "catalogue+HA", "catalogue+Epoch"):
                basis.append(f"the {'blue' if band == 'E' else 'red'} plate of the same field and VI/25 record, {y['p']['Region']} "
                             f"(label {y['p']['plateLabel']}, {y['evidence']}"
                             + (f", Epoch {y['p']['Epoch']}, {y['epoch_true_d']:+.1f} d" if y["ep_ok"] else "") + ")")
            x["gross_alt"] = (f"the hour angle does not decide: the listed time + 1 d ({fmt_t(t1)}) gives the field the hour angle "
                              f"of the proposed start within {abs(wrap_min(r1 - rp)):.1f} min (hourangle residual {r1 + x['c0']:+.2f} and "
                              f"{rp + x['c0']:+.2f} min, no-shift peak {x['c0']:+.2f}), which is why ha_verdict_listed reads "
                              f"'{x['ha_verdict']}'; the proposal rests on "
                              + ", ".join(basis[:-1]) + (" and " if len(basis) > 1 else "") + basis[-1])


def ha_check(x):
    """Listed and VI/25 hour angle against the hour angle computed for the start (proposed, else VI/25)."""
    t = x.get("prop_t") or x["true"]
    if t is None or not x["ha_ok_dec"]:
        return None
    exp = x["ha_east_h"] * 60 - x["resid"](t) + x["c0"]       # expected listed value incl. the no-shift offset
    vi = None if x["v_ha_east"] is None else x["v_ha_east"] * 60
    return dict(t=t, expected=exp, listed_ok=abs(x["ha_east_h"] * 60 - exp) <= HA_TOL_MIN,
                vi25_ok=None if vi is None else abs(vi - exp) <= HA_TOL_MIN)


def finish_row(x, band):
    p, cls = x["p"], x["cls"]
    notes = []
    x["prop_t"], basis = None, ""
    if cls in REGULAR and x["evidence"] != "unresolved":
        x["prop_t"] = x["true"]
        basis = ("date unchanged" if cls == "correct" else "date +1 d") + "; time = VI/25 minute"
    elif cls == "gross_error" and x["evidence"] != "unresolved":
        x["prop_t"], basis = x["true"], "VI/25 start" + (" (neighbours' night)" if x["alt_used"] else "")
    elif cls == "clock_mismatch" and x["clock_fix"] is not None:
        src, x["prop_t"] = x["clock_fix"]
        basis = ("UT date of the VI/25 start; time = listed clock time to the minute (the log hour angle supports it)"
                 if src == "listed clock" else "VI/25 start, date and time (the log hour angle supports the VI/25 clock)")
    elif cls == "clock_mismatch":
        basis = "manual: listed clock time differs from VI/25; the hour angle does not decide"
    elif cls == "unpaired":
        basis = "manual: no VI/25 pair"
    else:
        basis = "manual: witnesses disagree"
    x["prop"], x["basis"] = fmt_t(x["prop_t"], sec=True), basis
    # action for the archive, rounding refinement separate
    x["time_ref"] = ""
    if x["prop_t"] is None:
        x["action"] = "review_keep_listed"
    else:
        dd = (x["prop_t"].date() - x["t_list"].date()).days
        ds = (x["prop_t"] - x["t_list"]).total_seconds() - dd * 86400
        if abs(ds) <= TIME_ROUND_S and dd in (0, 1):
            x["action"], x["time_ref"] = ("no_change" if dd == 0 else "date_plus_1d"), int(round(ds))
        else:
            x["action"] = "replace_time" if dd == 0 else "replace_date_time"
    # Epoch (calendar-year fraction of the start, 3 decimals)
    x["prop_epoch"], x["epoch_action"], x["epoch_prop_d"] = "", "", None
    if x["prop_t"] is not None:
        pe = decyear(x["prop_t"])
        x["prop_epoch"] = f"{pe:.3f}"
        if x["epoch"] is None:
            x["epoch_action"] = "set"
        else:
            x["epoch_prop_d"] = (x["epoch"] - pe) * 365.25
            x["epoch_action"] = "keep" if abs(x["epoch_prop_d"]) <= epoch_tol_days(p["Epoch"]) else "recompute"
    # replacement hour angle / zenith distance / airmass (list units: decimal hours east-positive, degrees)
    x["prop_ha"] = x["prop_zd"] = x["prop_am"] = None
    if x["copy_of"] and not x["copy_same_exp"] and x["v_ha_east"] is not None and x["prop_t"] is not None:
        x["prop_ha"] = x["v_ha_east"]
        x["prop_zd"] = zd_deg(x["prop_ha"], x["dec"], float(p["latitude"]))
        x["prop_am"] = hardie_airmass(x["prop_zd"])
    elif x["ha_reading"]:
        x["prop_ha"] = x["ha_east_h"]
    x["ha_chk"] = ha_check(x) if x["ha_id"] is not None and abs(x["ha_id"]) > HA_ID_TOL_MIN else None
    # notes
    if len(x["exp_group"]) > 1:
        notes.append("one exposure, rows " + ", ".join(f"{y['p']['Region']}:{y['p']['plateID']}" for y in x["exp_group"])
                     + f" (same VI/25 record); this is the {'first' if x['exp_first'] else 'second'} row")
    if x["dup"]:
        notes.append("Region appears twice in the list")
    if x["copy_of"]:
        notes.append(f"UT/hourangle/zenithdistance/airmass identical to {x['copy_of']}"
                     + (" (same exposure)" if x["copy_same_exp"] else " (entry copied from another plate)"))
    if x["match"] is not None:
        rule, sp, v = x["match"]
        if rule == "number-1":
            notes.append("label number = VI/25 POSS + 1")
        if rule == "field only":
            notes.append(f"label does not match VI/25 POSS {v['POSS']}; paired by field centre")
        if not v["fobs_ok"]:
            notes.append(f"VI/25 record inconsistent in itself (Obs {v['obs']:%Y-%m-%d}, fObs {v['fM']} {v['fD']})")
        if x["alt_txt"]:
            notes.append(x["alt_txt"] + ("; neighbours' night used" if x["alt_used"] else "; not used"))
            a2 = x["alt_second"]
            if x["alt_used"] and a2 and a2["ha_fits"]:
                notes.append(f"the hour angle does not separate the neighbours' night from the record's own night with the listed "
                             f"clock time ({a2['t']}): {a2['days']:+d} d move sidereal time by {a2['days'] * SID_SHIFT_MIN:+.0f} min, "
                             f"the clock times differ by {a2['clock_min']:+d} min; Epoch ({a2['epoch_d']:+.1f} d for the own night) "
                             "favours the neighbours' night; an asteroid-trail check is recommended before the database is changed")
        if x["ha_reading"]:
            notes.append(f"hourangle {p['hourangle']} lies outside +-12 h; read {x['ha_reading']} = {x['ha_east_h']:+.5f} h")
        if x["ha_id"] is not None and abs(x["ha_id"]) > HA_ID_TOL_MIN:
            hc = x["ha_chk"]
            notes.append(f"listed hourangle minus VI/25 starting hour angle = {x['ha_id']:+.0f} min (east-positive)"
                         + ("" if hc is None else
                            f"; hour angle computed for {fmt_t(hc['t'])} (plus the no-shift offset): {hc['expected']:+.1f} min, "
                            f"listed {x['ha_east_h'] * 60:+.1f} ({'agrees' if hc['listed_ok'] else 'differs'}), VI/25 "
                            f"{x['v_ha_east'] * 60:+.0f} ({'agrees' if hc['vi25_ok'] else 'differs'})"))
        if x["ew_swap"]:
            notes.append(f"VI/25 hour angle {x['v_ha']} fits the hour angle computed for the VI/25 start only with E and W "
                         f"swapped (residual {x['ew_swap'][0]:+.1f} min as printed, {x['ew_swap'][1]:+.1f} min swapped)")
        if cls == "clock_mismatch":
            ct = x["clock_test"]
            notes.append(f"listed clock time differs from VI/25 start by {x['clock']:+.0f} min; hourangle residual "
                         f"{x['ha_resid_listed']:+.1f} min with the listed date and time"
                         + ("" if ct is None else
                            f", {ct['resid_vi25_clock']:+.1f} min with the VI/25 start, {ct['resid_listed_clock']:+.1f} min with the "
                            f"listed clock time on the VI/25 date ({ct['listed_clock_on_vi25_date']})")
                         + f" (no-shift peak {x['c0']:+.2f}); "
                         + ("the hour angle supports the " + x["clock_fix"][0] if x["clock_fix"] else "the hour angle supports neither clock time on the VI/25 date"))
        if cls == "gross_error":
            notes.append(f"listed date {x['t_list']:%Y-%m-%d} vs UT date {x['true']:%Y-%m-%d}")
        if x.get("gross_alt"):
            notes.append(x["gross_alt"])
        if x["epoch"] is not None and x["true"] is not None and not x["ep_ok"]:
            notes.append(f"Epoch {p['Epoch']} is {x['epoch_true_d']:+.1f} d from the start")
        if x["ast_agree"] is False:
            notes.append("asteroids contradict this date")
        if x["evidence"] == "unresolved" and cls in REGULAR and ha_agrees(x) is False:
            notes.append("listed hourangle contradicts the VI/25 date")
        if x.get("partner_ctx"):
            notes.append(f"hourangle contradicts VI/25, but the other-colour plate of the same field and night, "
                         f"{x['partner_ctx']}, agrees with VI/25")
        if x.get("run_ctx"):
            notes.append(f"hourangle contradicts VI/25 as on asteroid-confirmed {x['run_ctx']} of the same run "
                         "(a ~4-min clock or hour-angle offset gives the same signature)")
    if not x["label_ok"]:
        notes.append(f"plateLabel {p['plateLabel']!r} lacks the {band} prefix")
    if x["pid_src"].startswith("FitsArchive"):
        notes.append(f"plateID {p['plateID']!r} as printed; {x['pid']!r} from the FitsArchive file name")
    x["note"] = "; ".join(notes)


# name, type, unit / allowed values, description  (written to columns.csv; E names, O table: ObsO, OHA)
COLUMNS = [
    ("Survey", "text", "POSSI-E | POSSI-O", "as listed"),
    ("Region", "text", "", "as listed"),
    ("plateID", "text", "", "as printed in the 2024 CSV (44 E values were mangled by a spreadsheet; use plateID_restored)"),
    ("plateID_restored", "text", "4 characters", "plateID from the FitsArchive file name x<e|o><region>_<plateID>_nn_nn.fits where the printed value is mangled; else as listed. Join key: Survey + Region + plateID_restored"),
    ("plateID_source", "text", "", "where plateID_restored comes from"),
    ("plateLabel", "text", "", "as listed"),
    ("zone", "text", "001-722 | 723-936", "Region number 001-722 (label number = VI/25 number) or 723-936 (label = VI/25 number + 1, or ES/S spelling of the -30 deg zone); XO1001, the blue plate of the second polar field, counts as 001-722"),
    ("Declination", "deg", "J2000", "as listed"),
    ("listed_UTobservation", "UT", "YYYY-MM-DDThh:mm:ss", "as listed"),
    ("listed_hourangle", "h", "east-positive", "as listed"),
    ("listed_Epoch", "yr", "", "as listed"),
    ("duplicate", "text", "'' | first row | second row", "rows describing one exposure (same VI/25 record); first = lowest Region name"),
    ("same_exposure_as", "text", "Region:plateID", "the other row(s) of the same exposure"),
    ("vi25_POSS", "text", "", "VI/25 POSS number of the paired record"),
    ("vi25_MLP", "int", "", "VI/25 MLP number"),
    ("vi25_match_rule", "text", "number+field | number-1 | ES/S spelling | field only", "how the row was paired"),
    ("vi25_sep_deg", "deg", "", "list field centre to VI/25 field centre (B1950 -> ICRS)"),
    ("vi25_Obs", "date", "YYYY-MM-DD", "VI/25 Obs = date on which the night began, as printed (for 1425 and 673 the record's own night; the neighbours' night used is in true_UT_start)"),
    ("vi25_ObsE_PST / vi25_ObsO_PST", "PST", "hh:mm", "VI/25 exposure start, Pacific Standard Time"),
    ("vi25_EHA / vi25_OHA", "text", "hh:mm E|W", "VI/25 starting hour angle"),
    ("vi25_exp_min", "min", "", "VI/25 exposure time"),
    ("true_UT_start", "UT", "YYYY-MM-DDThh:mm", "VI/25 start in UT: night date + PST + 8 h (+24 h if PST < 12 h); minute precision as in VI/25"),
    ("day_offset_listed_minus_true", "d", "", "listed date minus UT date of true_UT_start"),
    ("clock_resid_min", "min", "", "listed clock time minus true_UT_start clock time, wrapped to +-12 h"),
    ("hourangle_minus_vi25_HA_min", "min", "east-positive", "listed hourangle (signed, see note for values beyond +-12 h) minus VI/25 starting hour angle"),
    ("class", "text", "evening_date | correct | clock_mismatch | gross_error | unpaired", "date offset checked first: -1 d evening_date, 0 correct, other gross_error; then a clock difference > 2 min makes clock_mismatch"),
    ("ha_resid_listed_min", "min", "", "listed hourangle minus the hour angle computed from the listed date and time (both east-positive); no-shift peak +0.50 (E) / +0.41 (O), one-day peak 3.94 min lower"),
    ("ha_resid_true_min", "min", "", "same with true_UT_start"),
    ("ha_verdict_listed", "text", "listed date consistent | listed date 1 d early | unclear | n/a (|Dec| >= 80)", "VI/25-independent: ha_resid_listed within 1.5 min of the no-shift peak or of that peak minus 3.94 min (not used at |Dec| >= 80)"),
    ("epoch_minus_true_days", "d", "", "listed Epoch minus calendar-year fraction of true_UT_start, in days"),
    ("asteroid_verdict", "text", "", "from inputs/asteroid_checks.csv (35 E plates, not a random sample)"),
    ("evidence_level", "text", "asteroid-confirmed | catalogue+HA | catalogue date+HA, listed clock | catalogue+Epoch | indirect | catalogue-only | unresolved", "what supports the proposal (README)"),
    ("action", "text", "date_plus_1d | no_change | replace_time | replace_date_time | review_keep_listed", "what to do with UTobservation/DATE-OBS of this row"),
    ("proposed_UTobservation", "UT", "YYYY-MM-DDThh:mm:ss", "proposed exposure start (= DATE-OBS); empty = no proposal"),
    ("time_refinement_s", "s", "-18..+18", "for date_plus_1d / no_change: proposed minus listed clock time; the list stores 0.01 h, this restores the VI/25 minute and is not an error"),
    ("proposed_basis", "text", "", "how the proposal was formed"),
    ("proposed_Epoch", "yr", "3 decimals", "calendar-year fraction of proposed_UTobservation"),
    ("epoch_action", "text", "keep | recompute | '' (empty)", "keep = listed Epoch agrees with proposed_Epoch within half a unit of its last decimal plus 0.25 d (a kept value can differ from proposed_Epoch by up to that amount); recompute = use proposed_Epoch; empty = no proposal (action review_keep_listed). The script would write 'set' for an empty listed Epoch; that does not occur in the 2024 list"),
    ("proposed_hourangle", "h", "east-positive, signed", "only where the listed value must change (copied entries: VI/25 starting hour angle; values beyond +-12 h: signed value)"),
    ("proposed_zenithdistance", "deg", "", "only for copied entries: from proposed_hourangle, Declination and latitude"),
    ("proposed_airmass", "", "", "only for copied entries: Hardie (1962) of proposed_zenithdistance, as the list does"),
    ("note", "text", "", "free text, '; '-separated"),
]


def write_columns(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["column", "type", "unit_or_values", "description"])
        w.writerows(COLUMNS)


def write_band(P, band, path):
    st, ha = ("ObsE", "EHA") if band == "E" else ("ObsO", "OHA")
    cols = []
    for c in COLUMNS:
        n = c[0]
        cols.append(n.split(" / ")[0 if band == "E" else 1] if " / " in n else n)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for x in P:
            p, m = x["p"], x["match"]
            v = m[2] if m else None
            grp = x["exp_group"]
            dup = "" if len(grp) < 2 else ("first row" if x["exp_first"] else "second row")
            same = " ".join(f"{y['p']['Region']}:{y['pid'] or y['p']['plateID']}" for y in grp if y is not x)
            w.writerow([p["Survey"], p["Region"], p["plateID"], x["pid"], x["pid_src"], p["plateLabel"], zone_of(p["Region"]),
                        p["Declination"], p["UTobservation"], p["hourangle"], p["Epoch"], dup, same,
                        v["POSS"] if v else "", v["MLP"] if v else "", m[0] if m else "none",
                        round(m[1], 4) if m else "", v["obs"].strftime("%Y-%m-%d") if v else "",
                        x["v_start"] or "", x["v_ha"] or "", x["v_exp"] if v and x["v_exp"] is not None else "",
                        fmt_t(x["true"]), "" if x["day_off"] is None else x["day_off"], r2(x["clock"]),
                        r2(x["ha_id"]), x["cls"], r2(x["ha_resid_listed"]), r2(x["ha_resid_true"]),
                        x["ha_verdict"], r2(x["epoch_true_d"]), x["ast_txt"], x["evidence"], x["action"], x["prop"],
                        x["time_ref"], x["basis"], x["prop_epoch"], x["epoch_action"], g7(x["prop_ha"]), g7(x["prop_zd"]),
                        g7(x["prop_am"]), x["note"]])


# ----------------------------------------------------------------------------- summaries
def counts(P, c0):
    """All per-band counts of summary.json."""
    c = dict(rows=len(P), distinct_regions=len(set(x["p"]["Region"] for x in P)),
             exposures=sum(1 for x in P if x["exp_first"]),
             match_rule=dict(Counter(x["match"][0] if x["match"] else "none" for x in P)),
             class_rows=dict(Counter(x["cls"] for x in P)),
             evidence_rows=dict(Counter(x["evidence"] for x in P)),
             ha_verdict_listed_rows=dict(Counter(x["ha_verdict"] for x in P)))
    reg = [x for x in P if x["cls"] in REGULAR and x["exp_first"]]
    k = sum(1 for x in reg if x["cls"] == "evening_date")
    c.update(regular_exposures=len(reg), evening_date=k, correct=len(reg) - k,
             evening_share=round(k / len(reg), 4) if reg else None, evening_share_wilson95=wilson(k, len(reg)))
    byz, byy = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for x in reg:
        i = 0 if x["cls"] == "evening_date" else 1
        byz[zone_of(x["p"]["Region"])][i] += 1
        byy[x["true"].year][i] += 1
    c["by_zone_evening_correct"] = dict(sorted(byz.items()))
    c["by_true_UT_year_evening_correct"] = {str(y): byy[y] for y in sorted(byy)}
    c["declination_range_by_zone"] = {z: [round(min(x["dec"] for x in P if zone_of(x["p"]["Region"]) == z), 1),
                                          round(max(x["dec"] for x in P if zone_of(x["p"]["Region"]) == z), 1)]
                                      for z in ("001-722", "723-936")}
    c["class_x_ha_verdict_exposures"] = dict(sorted(Counter(f"{x['cls']}|{x['ha_verdict']}" for x in P if x["exp_first"]).items()))
    c["ha_identity_ok_rows"] = sum(1 for x in P if x["ha_id"] is not None and abs(x["ha_id"]) <= HA_ID_TOL_MIN)
    c["clock_ok_rows"] = sum(1 for x in P if x["clock"] is not None and abs(x["clock"]) <= CLOCK_TOL_MIN)
    dec = [x for x in P if x["ast_dec"] and x["ast_agree"] is not None]
    nd, kd = len(dec), sum(1 for x in dec if x["ast_agree"])
    c["asteroid_decisive_agree"] = [kd, nd]
    # exact (Clopper-Pearson) 95 % upper limit of the disagreement rate, only for zero disagreements
    c["asteroid_disagreement_rate_upper95"] = round(1 - 0.025 ** (1 / nd), 4) if nd and kd == nd else None
    c["ha_identity_mismatch"] = [(x["p"]["Region"], round(x["ha_id"])) for x in P if x["ha_id"] is not None and abs(x["ha_id"]) > HA_ID_TOL_MIN]
    c["clock_mismatch"] = [(x["p"]["Region"], round(x["clock"], 1)) for x in P if x["cls"] == "clock_mismatch"]
    c["gross_error"] = [(x["p"]["Region"], x["p"]["UTobservation"], fmt_t(x["true"])) for x in P if x["cls"] == "gross_error"]
    c["alt_night_used"] = [x["p"]["Region"] for x in P if x["alt_used"]]
    c["alt_night_flagged_not_used"] = [x["p"]["Region"] for x in P if x["alt_txt"] and not x["alt_used"]]
    c["unpaired"] = [x["p"]["Region"] for x in P if x["cls"] == "unpaired"]
    c["unresolved"] = [x["p"]["Region"] for x in P if x["evidence"] == "unresolved"]
    c["run_context_downgraded"] = [x["p"]["Region"] for x in P if x.get("run_ctx")]
    c["partner_downgraded"] = [x["p"]["Region"] for x in P if x.get("partner_ctx")]
    c["number_minus_1_by_zone"] = dict(Counter(zone_of(x["p"]["Region"]) for x in P if x["match"] and x["match"][0] == "number-1"))
    sep = [x["match"][1] for x in P if x["match"]]
    c["sep_deg_max"] = round(max(sep), 4)
    c["matched_is_nearest_field_rows"] = sum(1 for x in P if x["match"] and x["match"][2] is x["nearest"][0][1])
    c["second_nearest_field_min_deg"] = round(min(x["nearest"][1][0] for x in P if x["match"]), 3)
    # single-plate reliability of the HA test under the VI/25 date (regular, non-polar)
    res = np.array([x["ha_resid_true"] - c0 for x in reg if x["ha_ok_dec"]])
    c["ha_resid_true_minus_peak"] = dict(n=int(res.size), median=round(float(np.median(res)), 3),
                                         robust_sigma=round(float(1.4826 * np.median(np.abs(res - np.median(res)))), 3),
                                         frac_abs_gt_1p5=round(float(np.mean(np.abs(res) > 1.5)), 4),
                                         frac_abs_gt_half_shift=round(float(np.mean(np.abs(res) > SID_SHIFT_MIN / 2)), 4))
    ep = Counter()
    for x in reg:
        if x["epoch_true_d"] is None:
            continue
        e = x["epoch_true_d"]
        t = epoch_tol_days(x["p"]["Epoch"])
        if abs(e) <= t:
            k2 = "fits UT start"
        elif abs(e + 1) <= t:
            k2 = "fits start - 1 d (evening date)"
        else:
            k2 = "fits neither"
        ep[f"{x['cls']}|{k2}"] += 1
    c["epoch_vs_start_exposures"] = dict(sorted(ep.items()))
    ep3 = Counter()
    for x in reg:
        if x["epoch_true_d"] is None or len(x["p"]["Epoch"].split(".")[-1]) != 3 or "." not in x["p"]["Epoch"]:
            continue
        e, t = x["epoch_true_d"], epoch_tol_days(x["p"]["Epoch"])
        ep3["fits UT start" if abs(e) <= t else ("fits evening date" if abs(e + 1) <= t else "fits neither")] += 1
    c["epoch_3_decimals_vs_start_exposures"] = dict(ep3)
    c["action_rows"] = dict(Counter(x["action"] for x in P))
    c["epoch_action_rows"] = dict(Counter(x["epoch_action"] or "no proposal" for x in P))
    c["plateID_source_rows"] = dict(Counter(x["pid_src"] for x in P))
    c["plateID_restored_from_file_name"] = [(x["p"]["Region"], x["p"]["plateID"], x["pid"]) for x in P if x["pid_src"].startswith("FitsArchive")]
    c["clock_mismatch_resolved_by_hour_angle"] = [(x["p"]["Region"], x["clock_fix"][0], x["prop"]) for x in P if x["clock_fix"]]
    c["clock_mismatch_unresolved"] = [x["p"]["Region"] for x in P if x["cls"] == "clock_mismatch" and not x["clock_fix"]]
    c["vi25_ha_fits_with_EW_swapped"] = [(x["p"]["Region"], x["v_ha"], x["ew_swap"][1]) for x in P if x["ew_swap"]]
    c["neighbour_night_second_solution"] = [(x["p"]["Region"], x["alt_second"]) for x in P if x["alt_used"]]
    c["hourangle_beyond_12h"] = [(x["p"]["Region"], x["p"]["hourangle"], x["ha_reading"], round(x["ha_east_h"], 5)) for x in P if x["ha_reading"]]
    c["proposed_field_replacements"] = [(x["p"]["Region"], g7(x["prop_ha"]), g7(x["prop_zd"]), g7(x["prop_am"])) for x in P if x["prop_ha"] is not None]
    # evening-date rows that began after local midnight: their PST calendar date is already Obs + 1
    ev = [x for x in reg if x["cls"] == "evening_date"]
    c["evening_date_exposures_started_after_local_midnight"] = [
        sum(1 for x in ev if (x["true"] - timedelta(hours=8)).date() > x["match"][2]["obs"].date()), len(ev)]
    # zenithdistance and airmass follow the listed hourangle (not the date): deviations, copied entries excluded
    fz = [x for x in P if not (x["copy_of"] and not x["copy_same_exp"])]
    dz = np.array([float(x["p"]["zenithdistance"]) - zd_deg(x["ha_east_h"], x["dec"], float(x["p"]["latitude"])) for x in fz])
    dh = np.array([float(x["p"]["airmass"]) - hardie_airmass(float(x["p"]["zenithdistance"])) for x in fz])
    dsec = np.array([float(x["p"]["airmass"]) - 1 / math.cos(math.radians(float(x["p"]["zenithdistance"]))) for x in fz])
    c["fields_vs_hourangle"] = dict(
        rows=len(fz), zd_minus_computed_deg_p1_p50_p99=[round(float(q), 3) for q in np.percentile(dz, [1, 50, 99])],
        zd_rows_abs_gt_0p2_deg=[(x["p"]["Region"], round(float(d), 3)) for x, d in zip(fz, dz) if abs(d) > 0.2],
        airmass_minus_hardie_max_abs=round(float(np.max(np.abs(dh))), 4), airmass_minus_secz_max_abs=round(float(np.max(np.abs(dsec))), 4),
        copied_rows_excluded=[x["p"]["Region"] for x in P if x["copy_of"] and not x["copy_same_exp"]])
    # standard time all year? summer (Apr-Sep) and winter rows on the no-shift peak, or 60 min off it
    dst = {}
    for name, months in (("Apr-Sep", range(4, 10)), ("Oct-Mar", (10, 11, 12, 1, 2, 3))):
        rr = [x["ha_resid_true"] - c0 for x in reg if x["ha_ok_dec"] and x["true"].month in months]
        dst[name] = dict(n=len(rr), within_1p5_of_peak=sum(1 for r in rr if abs(r) <= HA_TOL_MIN),
                         within_1p5_of_peak_plus_or_minus_60=sum(1 for r in rr if abs(abs(r) - 60) <= HA_TOL_MIN))
    c["standard_time_test"] = dst
    # listed-date class by UT year modulo 4, and the regular exposures that break the pattern
    m4 = defaultdict(lambda: [0, 0])
    for x in reg:
        m4[x["true"].year % 4][0 if x["cls"] == "evening_date" else 1] += 1
    c["by_UT_year_mod4_evening_correct"] = {str(k): m4[k] for k in sorted(m4)}
    c["by_UT_year_mod4_eq1_vs_other_evening_correct"] = {"mod4 = 1": m4[1], "mod4 != 1": [sum(m4[k][i] for k in (0, 2, 3)) for i in (0, 1)]}
    maj = {k: ("evening_date" if v[0] >= v[1] else "correct") for k, v in m4.items()}
    exc = Counter(((x["true"] - timedelta(hours=20)).date().isoformat(), x["cls"]) for x in reg if x["cls"] != maj[x["true"].year % 4])
    c["year_mod4_exceptions_night_class_exposures"] = [(k[0], k[1], n) for k, n in sorted(exc.items())]
    # asteroid sample: which plates
    ar = [x for x in P if x["ast_txt"]]
    c["asteroid_sample"] = dict(rows=len(ar), decisive=sum(1 for x in ar if x["ast_dec"]),
                                regions_min_max=[min(x["p"]["Region"] for x in ar), max(x["p"]["Region"] for x in ar)] if ar else None,
                                by_zone=dict(Counter(zone_of(x["p"]["Region"]) for x in ar)))
    c["asteroid_disagreement_rate_upper95_one_sided"] = round(1 - 0.05 ** (1 / nd), 4) if nd and kd == nd else None
    # Epoch: which year definition do the listed values follow (regular exposures, 3 decimals, proposed start)
    edt = Counter()
    for x in reg:
        e = x["p"]["Epoch"]
        if x["prop_t"] is None or "." not in e or len(e.split(".")[1]) != 3:
            continue
        edt["n"] += 1
        for name, f in (("calendar_year_fraction", decyear), ("julian_epoch", julian_epoch), ("besselian_epoch", besselian_epoch)):
            d = (float(e) - f(x["prop_t"])) * 365.25
            edt[name + "|start"] += abs(d) <= 0.25
            edt[name + "|start-1d"] += abs(d + 1) <= 0.25
    c["epoch_definition_test_within_0p25d"] = dict(edt)
    c["proposal_basis_rows"] = dict(Counter(x["basis"] for x in P))
    c["rows_with_proposal"] = sum(1 for x in P if x["prop"])
    c["rows_date_change_proposed"] = sum(1 for x in P if x["prop"] and x["prop"][:10] != x["p"]["UTobservation"][:10])
    c["epoch_decimals_rows"] = dict(Counter(len(x["p"]["Epoch"].split(".")[1]) if "." in x["p"]["Epoch"] else 0 for x in P))
    c["asteroid_rows"] = dict(Counter(f"{x['evidence']}|agree={x['ast_agree']}" for x in P if x["ast_txt"]))
    return c


def reconcile(P):
    """Rule of the earlier count (2026-10-14): 'north' = number+field pairs, counted by date only (listed date =
    VI/25 Obs or Obs+1); 'south' = the other pairs, counted only where clock (+-2 min) AND hourangle (+-1.5 min)
    match VI/25. Rows, not exposures; VI/25 records taken as given."""
    n0 = n1 = s0 = s1 = 0
    counted = set()
    for x in P:
        if x["match"] is None or "raw" not in x or x["raw"]["day_off"] is None:
            continue
        d, clk = x["raw"]["day_off"], x["raw"]["clock"]
        if x["match"][0] == "number+field":
            n0 += d == -1
            n1 += d == 0
            if d in (-1, 0):
                counted.add(id(x))
        elif abs(clk) <= CLOCK_TOL_MIN and x["ha_id"] is not None and abs(x["ha_id"]) <= HA_ID_TOL_MIN:
            s0 += d == -1
            s1 += d == 0
            if d in (-1, 0):
                counted.add(id(x))
    n = n0 + n1 + s0 + s1
    table = set(id(x) for x in P if x["cls"] in REGULAR and x["exp_first"])
    why = Counter()
    only_earlier, only_table = [], []
    for x in P:
        if id(x) in counted and id(x) not in table:
            k = "second row" if not x["exp_first"] else ("VI/25 record corrected" if x["alt_used"] else x["cls"])
            why[k] += 1
            only_earlier.append((x["p"]["Region"], k))
        elif id(x) in table and id(x) not in counted:
            why["added: clock ok, hour angle differs"] += 1
            only_table.append(x["p"]["Region"])
    return dict(rule=" ".join(reconcile.__doc__.split()), north=[n0, n1], south=[s0, s1],
                total=[n0 + s0, n1 + s1], n=n, share=round((n0 + s0) / n, 4), wilson95=wilson(n0 + s0, n),
                difference_to_table=dict(why), only_in_earlier_count=only_earlier, only_in_table=only_table)


def time_rounding(tables):
    """Is the listed clock time the VI/25 minute converted to two-decimal hours (0.01 h = 36 s)?"""
    out = {}
    for band, P in tables.items():
        ok = [x for x in P if x["cls"] in REGULAR]
        same = 0
        for x in ok:
            tt = x["true"]
            dec = round(tt.hour + tt.minute / 60, 2)
            hh = int(dec)
            if (x["t_list"].hour, x["t_list"].minute * 60 + x["t_list"].second) == (hh % 24, int(round((dec - hh) * 3600))):
                same += 1
        out[band] = dict(rows=len(ok), equals_vi25_minute_rounded_to_0p01h=same,
                         clock_resid_p1_p50_p99=[round(float(q), 2) for q in np.percentile([x["clock"] for x in ok], [1, 50, 99])])
    return out


def night_blocks(E, O, path):
    nights = defaultdict(lambda: dict(E=Counter(), O=Counter(), zones=Counter()))
    for x in E:
        if x["cls"] in REGULAR and x["exp_first"]:
            n = nights[(x["true"] - timedelta(hours=20)).date()]   # UT 20:00 = PST noon: night key = evening date
            n["E"][x["cls"]] += 1
            n["zones"][zone_of(x["p"]["Region"])] += 1
    for x in O:
        if x["cls"] in REGULAR and x["exp_first"]:
            nights[(x["true"] - timedelta(hours=20)).date()]["O"][x["cls"]] += 1
    keys = sorted(k for k in nights if nights[k]["E"])
    blocks = []
    for k in keys:
        conv = "mixed" if len(nights[k]["E"]) > 1 else next(iter(nights[k]["E"]))
        if not blocks or blocks[-1]["convention"] != conv:
            blocks.append(dict(first_night=str(k), last_night=str(k), convention=conv, nights=0, E_exposures=0,
                               regions_001_722=0, regions_723_936=0, O_same_convention=0, O_other_convention=0))
        b = blocks[-1]
        b["last_night"] = str(k)
        b["nights"] += 1
        b["E_exposures"] += sum(nights[k]["E"].values())
        b["regions_001_722"] += nights[k]["zones"]["001-722"]
        b["regions_723_936"] += nights[k]["zones"]["723-936"]
        b["O_same_convention"] += nights[k]["O"].get(conv, 0)
        b["O_other_convention"] += sum(v for cc, v in nights[k]["O"].items() if cc != conv)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(blocks[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(blocks)
    return dict(nights=len(keys), nights_mixed_E=[str(k) for k in keys if len(nights[k]["E"]) > 1],
                nights_mixed_E_or_O=[str(k) for k in keys if len(set(nights[k]["E"]) | set(nights[k]["O"])) > 1],
                O_only_nights=sorted(str(k) for k in nights if not nights[k]["E"]), blocks=len(blocks))


# ----------------------------------------------------------------------------- known anomalies
def anomalies(rows, tables, vi, ext, path):
    A = []

    def add(cat, survey, regions, field, listed, reference, description, evidence, action, n=None):
        A.append(dict(anomaly_id=f"A{len(A) + 1:02d}", category=cat, survey=survey, regions=" ".join(regions),
                      n_rows=n if n is not None else len([r for r in regions if r not in ("...", "-")]), field=field, listed_value=listed,
                      reference_value=reference, description=description, evidence=evidence, suggested_action=action))

    E, O = tables["E"], tables["O"]
    for band, P in (("POSSI-E", E), ("POSSI-O", O)):
        for x in P:
            p = x["p"]
            if x["cls"] == "gross_error":
                v = x["match"][2]
                add("date (gross)", band, [p["Region"]], "UTobservation", p["UTobservation"], fmt_t(x["true"]),
                    f"listed date is {(x['t_list'].date() - x['true'].date()).days:+d} d from the UT date of the start"
                    + (f"; entry copied from {x['copy_of']}" if x["copy_of"] else "")
                    + (f"; {x['gross_alt']}" if x.get("gross_alt") else ""),
                    f"VI/25 POSS {v['POSS']} night {v['obs']:%Y-%m-%d}" + (" (record suspect; neighbours' night used)" if x["alt_used"] else "")
                    + f"; Epoch {p['Epoch']} ({x['epoch_true_d']:+.1f} d)" + (f"; asteroids {x['ast_txt']}" if x["ast_txt"] else "")
                    + f"; evidence {x['evidence']}",
                    ("replace date and time by proposed_UTobservation" + ("; replace hourangle, zenithdistance, airmass by the "
                     "proposed_* values" if x["prop_ha"] is not None else "")
                     + ("; asteroid-trail check recommended first (see note)" if x["alt_used"] and x["alt_second"] and x["alt_second"]["ha_fits"] else ""))
                    if x["prop"] else "check logbook")
        for x in P:
            p = x["p"]
            if x["cls"] == "clock_mismatch":
                ct, cf = x["clock_test"], x["clock_fix"]
                add("time", band, [p["Region"]], "UTobservation", p["UTobservation"], x["prop"] or fmt_t(x["true"]),
                    f"listed clock time is {x['clock']:+.0f} min from VI/25 start + 8 h (date offset {x['day_off']} d)"
                    + (f"; VI/25 E/W probably swapped (VI/25 hour angle fits the computed one with E/W swapped, residual "
                       f"{x['ew_swap'][1]:+.1f} min)" if x["ew_swap"] else ""),
                    f"VI/25 POSS {x['match'][2]['POSS']}; hourangle residual {x['ha_resid_listed']:+.1f} min with the listed date and time"
                    + ("" if ct is None else f", {ct['resid_vi25_clock']:+.1f} min with the VI/25 start, {ct['resid_listed_clock']:+.1f} min "
                       f"with the listed clock time on the VI/25 date")
                    + f" (no-shift peak {tables['c0'][band[-1]]:+.2f}, one-day peak {tables['c0'][band[-1]] - SID_SHIFT_MIN:+.2f}); "
                    f"Epoch {r2(x['epoch_true_d'], 1)} d",
                    (f"set proposed_UTobservation: the log hour angle supports the {cf[0]}" if cf else
                     "check logbook: the hour angle supports neither clock time on the VI/25 date"))
        for x in P:
            p = x["p"]
            if x["ha_id"] is not None and abs(x["ha_id"]) > HA_ID_TOL_MIN and x["cls"] != "gross_error":
                hc = x["ha_chk"]
                act = "check logbook"
                if hc and hc["listed_ok"] and not hc["vi25_ok"]:
                    act = "none for the list (listed value agrees with the computed hour angle; VI/25 differs)"
                add("hour angle", band, [p["Region"]], "hourangle", p["hourangle"], x["v_ha"] or "",
                    f"listed hourangle minus VI/25 starting hour angle = {x['ha_id']:+.0f} min (east-positive)"
                    + (f"; VI/25 E/W probably swapped (fits the computed hour angle with E/W swapped, residual {x['ew_swap'][1]:+.1f} min)"
                       if x["ew_swap"] else ""),
                    f"VI/25 POSS {x['match'][2]['POSS']}; class {x['cls']}; hourangle residual {x['ha_resid_listed']:+.1f} min"
                    + ("" if hc is None else f"; hour angle computed for {fmt_t(hc['t'])} plus the no-shift offset: {hc['expected']:+.1f} min "
                       f"(listed {x['ha_east_h'] * 60:+.1f} {'agrees' if hc['listed_ok'] else 'differs'}, VI/25 {x['v_ha_east'] * 60:+.0f} "
                       f"{'agrees' if hc['vi25_ok'] else 'differs'})"), act)
        for x in P:
            if x["alt_txt"] and not x["alt_used"]:
                add("VI/25 record", band, [x["p"]["Region"]], "VI/25 Obs", f"{x['match'][2]['obs']:%Y-%m-%d}", "",
                    x["alt_txt"], "nposs.dat; plate list", "check logbook")
        for x in P:
            if x["evidence"] == "unresolved" and x["cls"] in REGULAR:
                add("date (conflict)", band, [x["p"]["Region"]], "UTobservation", x["p"]["UTobservation"], fmt_t(x["true"]),
                    f"VI/25 gives class {x['cls']}, the listed hourangle says '{x['ha_verdict']}' "
                    f"(residual {x['ha_resid_listed']:+.2f} min; VI/25 time {x['ha_resid_true']:+.2f} min)",
                    f"VI/25 POSS {x['match'][2]['POSS']} ({x['match'][0]}), night {x['match'][2]['obs']:%Y-%m-%d}, start {x['v_start']} PST",
                    "check logbook; table keeps VI/25 date, no proposal")
    # copies and duplicates
    groups = defaultdict(list)
    for P in (E, O):
        for x in P:
            if x["copy_of"] and not x["copy_same_exp"]:     # same exposure: see "duplicate exposure"
                groups[x["copy_of"]].append(x)
    for src, xs in sorted(groups.items()):
        s = next(y for P in (E, O) for y in P if y["p"]["Region"] == src)
        own = []
        for y in xs:
            d = sep_deg(y["ra"], y["dec"], s["ra"], s["dec"])
            own.append(f"{y['p']['Region']} {d:.1f} deg" if d >= 1 else f"{y['p']['Region']} {d * 60:.1f} arcmin")
        add("copied entry", "POSSI-E/O", [y["p"]["Region"] for y in xs], "UTobservation, hourangle, zenithdistance, airmass",
            s["p"]["UTobservation"], "", f"same four values as {src}; field-centre distance to {src}: " + ", ".join(own),
            "identical strings in the 2024 list",
            "replace UTobservation, hourangle, zenithdistance, airmass by the rows' proposed_* values (VI/25 start and starting "
            "hour angle; zenith distance and airmass recomputed the way the list computes them)")
    for band, P in (("POSSI-E", E), ("POSSI-O", O)):
        by = defaultdict(list)
        for x in P:
            if x["match"]:
                by[x["match"][2]["id"]].append(x)
        for vid, xs in sorted(by.items()):
            if len(xs) < 2:
                continue
            regs = [y["p"]["Region"] for y in xs]
            d = sep_deg(xs[0]["ra"], xs[0]["dec"], xs[1]["ra"], xs[1]["dec"]) * 60
            add("duplicate exposure", band, regs, "Region / plateID", " / ".join(f"{y['p']['Region']}:{y['p']['plateID']}" for y in xs),
                f"VI/25 POSS {xs[0]['match'][2]['POSS']}",
                f"{len(xs)} rows describe one exposure (same VI/25 record, same UTobservation); centres {d:.1f}' apart; Epoch "
                + " / ".join(y["p"]["Epoch"] for y in xs)
                + ("" if len(set(regs)) == 1 else "; Region names differ, so one field slot holds another field's plate"),
                "2024 list + VI/25", "keep one row per exposure, or flag the second scan")
    # fields of VI/25 (POSS-I proper) without a row, and missing Region numbers
    for band, P, pre in (("POSSI-E", E, "XE"), ("POSSI-O", O, "XO")):
        used = set(x["match"][2]["id"] for x in P if x["match"])
        miss = [v for v in vi if v["MLP"] <= 937 and v["id"] not in used]
        if miss:
            add("missing field", band, [f"POSS {v['POSS']}" for v in miss], "-",
                "", "; ".join(f"POSS {v['POSS']} MLP {v['MLP']} night {v['obs']:%Y-%m-%d} RA/Dec(ICRS) {v['ra']:.2f}/{v['de']:.2f}, "
                              + "nearest other VI/25 field POSS {1} at {0:.2f} deg".format(*min(
                                  ((sep_deg(v['ra'], v['de'], w['ra'], w['de']), w['POSS']) for w in vi if w is not v and w['MLP'] <= 937)))
                              for v in miss),
                f"{len(miss)} VI/25 POSS-I fields have no {band} row within {MAX_SEP_DEG} deg", "nposs.dat vs 2024 list",
                "check whether a scan exists")
        nums = set()
        for x in P:
            m = re.match(pre + r"(\d+)", x["p"]["Region"])
            nums.add(1 if int(m.group(1)) == 1001 else int(m.group(1)))
        gap = sorted(set(range(1, max(nums) + 1)) - nums)
        if gap:
            add("missing Region", band, [f"{pre}{n:03d}" for n in gap], "Region", "", "",
                f"Region numbers absent between {pre}001 and {pre}{max(nums):03d}", "2024 list", "information")
    # labels and numbering
    vi_count = Counter(v["key"] for v in vi if v["MLP"] <= 937)
    for band, P, pre in (("POSSI-E", E, "E"), ("POSSI-O", O, "O")):
        sh = [x for x in P if x["match"] and x["match"][0] == "number-1" and zone_of(x["p"]["Region"]) == "723-936"]
        if sh:
            lab_count = Counter(x["p"]["plateLabel"] for x in P)
            ncoll = sum(1 for x in sh if vi_count[x["match"][2]["key"]] > 1)
            rg = sorted(x["p"]["Region"] for x in sh)
            add("plate number", band, [rg[0], "...", rg[-1]], "plateLabel", f"{pre}<n>", "VI/25 POSS n-1",
                f"{len(sh)} rows of X{pre}723-936 (Dec -11 to -25 deg): label number = VI/25 POSS + 1; field centre, clock time and hour "
                f"angle identify the same exposure. {ncoll} of the VI/25 numbers n-1 are also carried by another VI/25 POSS-I record "
                f"(different field and night); {sum(1 for x in sh if lab_count[x['p']['plateLabel']] > 1)} of the list labels n are used twice. "
                "This favours the list's numbering, but the printed catalogue was not consulted",
                "match_rule 'number-1'", "none if the list is right; note the offset for users of VI/25", n=len(sh))
        es = [x for x in P if x["match"] and x["match"][0] == "ES/S spelling"]
        if es:
            pf = Counter(LABEL_RE.match(x["p"]["plateLabel"]).group("pfx") + LABEL_RE.match(x["p"]["plateLabel"]).group("zone") for x in es)
            rg = sorted(x["p"]["Region"] for x in es)
            add("plate number", band, [rg[0], "...", rg[-1]], "plateLabel",
                ", ".join(f"{k}<n> ({v})" for k, v in sorted(pf.items())), "VI/25 'S <n>'",
                f"{len(es)} rows of the -30 deg zone: spelling only (ReadMe: the S is needed because numbers repeat)",
                "match_rule 'ES/S spelling'", "cosmetic" if band == "POSSI-E" else "cosmetic; two prefixes (OS, OQ) for one zone", n=len(es))
        for x in P:
            if x["match"] and x["match"][0] == "field only":
                add("plate number", band, [x["p"]["Region"]], "plateLabel", x["p"]["plateLabel"], x["match"][2]["POSS"],
                    "label matches no VI/25 number at this field; paired by field centre only",
                    f"sep {x['match'][1]:.3f} deg; clock {r2(x['clock'])} min; hour angle {r2(x['ha_id'])} min", "check label")
            if not x["label_ok"]:
                add("plate label", band, [x["p"]["Region"]], "plateLabel", x["p"]["plateLabel"], "",
                    f"label lacks the {pre} prefix", "2024 list", "add prefix")
            if abs(x["hourangle_h"]) > 12:
                a_ = x["hourangle_h"] - 24 if x["hourangle_h"] > 12 else x["hourangle_h"] + 24
                hb = ha_check(x) if x["true"] is not None else None
                add("hour angle", band, [x["p"]["Region"]], "hourangle", x["p"]["hourangle"], f"{x['ha_east_h']:+.5f}",
                    f"hour angle outside +-12 h. Read as east-positive modulo 24 h it is {a_:+.5f} h; read {x['ha_reading']} it is "
                    f"{x['ha_east_h']:+.5f} h"
                    + ("" if x["v_ha_east"] is None else f"; VI/25 {x['v_ha']} = {x['v_ha_east']:+.5f} h")
                    + ("" if hb is None else f"; hour angle computed for {fmt_t(hb['t'])} plus the no-shift offset: {hb['expected'] / 60:+.5f} h"),
                    "2024 list; VI/25; computed hour angle",
                    f"store {x['ha_east_h']:+.5f} (east-positive, signed)")
        nonint = [x["p"]["Region"] for x in P if abs(x["hourangle_h"] * 60 - round(x["hourangle_h"] * 60)) > 0.01]
        add("hour angle (information)", band, nonint or ["-"], "hourangle", "", "",
            f"{len(P) - len(nonint)} of {len(P)} values are whole minutes, i.e. copied from the log, not computed; "
            f"exceptions: {', '.join(nonint) or 'none'}", "2024 list", "none")
        for x in P:
            if x["epoch"] is None:
                continue
            dl = (x["epoch"] - decyear(x["t_list"])) * 365.25
            if abs(dl) > 30 and (x["epoch_true_d"] is None or abs(x["epoch_true_d"]) > 30):
                add("Epoch", band, [x["p"]["Region"]], "Epoch", x["p"]["Epoch"], fmt_t(x["true"]),
                    f"Epoch is {dl:+.0f} d from the listed date and {r2(x['epoch_true_d'], 0)} d from the start",
                    "2024 list", "set proposed_Epoch" if x.get("prop_epoch") else "recompute Epoch after the date is settled")
        ep1 = [x for x in P if x["epoch_action"] == "recompute" and abs(x["epoch_prop_d"]) < EPOCH_ENTRY_MAX_D]
        if ep1:
            m1 = [x for x in ep1 if abs(x["epoch_prop_d"] + 1) <= epoch_tol_days(x["p"]["Epoch"])]
            mon = [x for x in ep1 if x not in m1 and abs(x["epoch_prop_d"]) >= EPOCH_MONTH_MIN_D]
            rest = [x for x in ep1 if x not in m1 and x not in mon]
            one = len(ep1) == 1
            ev_mon = sorted(set(x["evidence"] for x in mon))
            add(f"Epoch (< {EPOCH_ENTRY_MAX_D:.0f} d)", band, [x["p"]["Region"] for x in ep1], "Epoch", "", "proposed_Epoch",
                f"{len(ep1)} listed Epoch{'' if one else 's'} disagree{'s' if one else ''} with the proposed start by more than "
                f"{'its' if one else 'their'} own precision but less than {EPOCH_ENTRY_MAX_D:.0f} d: {len(m1)} "
                f"fit{'s' if len(m1) == 1 else ''} the start minus 1 d"
                + ("" if not rest else f"; {len(rest)} other day offset{'' if len(rest) == 1 else 's'} (" + ", ".join(
                    f"{x['p']['Region']} {x['epoch_prop_d']:+.1f} d" for x in rest) + ")")
                + ("" if not mon else f"; Epoch off by about one month in {len(mon)} row{'' if len(mon) == 1 else 's'} (" + ", ".join(
                    f"{x['p']['Region']} {x['p']['Epoch']}: {x['epoch_prop_d']:+.1f} d" for x in mon) + f"), evidence {', '.join(ev_mon)}"
                    + (": the start does not rest on Epoch there, so the Epoch is the error"
                       if set(ev_mon) <= {"catalogue+HA", "asteroid-confirmed"} else "")),
                "2024 list; proposed_UTobservation", "set proposed_Epoch (calendar-year fraction of the start)")
    # O label number vs E label number of the same Region
    enum = {}
    for x in E:
        m = LABEL_RE.match(x["p"]["plateLabel"])
        if m and x["exp_first"] and not x["copy_of"]:
            enum[x["p"]["Region"][2:]] = (m.group("zone") != "", int(m.group("num")), x["p"]["plateLabel"])
    for x in O:
        k = x["p"]["Region"][2:]
        k = {"001": "001A", "1001": "001B"}.get(k, k)
        m = LABEL_RE.match(x["p"]["plateLabel"])
        if k in enum and m and (m.group("zone") != "", int(m.group("num"))) != enum[k][:2]:
            add("plate number", "POSSI-O", [x["p"]["Region"]], "plateLabel", x["p"]["plateLabel"], f"red plate {enum[k][2]}",
                "blue plate number differs from the red plate number of the same Region (VI/25 lists one number per field)",
                f"VI/25 POSS {x['match'][2]['POSS'] if x['match'] else '-'} (match rule {x['match'][0] if x['match'] else 'none'})",
                "check label")
    # SeeingCode cells converted to day-month strings, plateGrade truncation
    sc = Counter(r["Survey"] for r in rows if SEEING_MONTH_RE.match(r["SeeingCode"].strip()))
    vals = Counter(r["SeeingCode"].strip() for r in rows if SEEING_MONTH_RE.match(r["SeeingCode"].strip()))
    if sc:
        add("SeeingCode", "all surveys", [f"{k}:{v}" for k, v in sorted(sc.items(), key=lambda t: -t[1])], "SeeingCode",
            ", ".join(f"{k} ({v})" for k, v in vals.most_common()), "e.g. '2-3'",
            f"{sum(sc.values())} cells hold a day-month or month-year string; a spreadsheet turns a range such as '2-3' into "
            "'3-Feb' (month 2, day 3). The original values are inferred, not seen in this file",
            "2024 list, patterns ^d-Mon$ and ^Mon-yy$", "regenerate the CSV from the database without spreadsheet conversion",
            n=sum(sc.values()))
    rest = {(x["p"]["Region"], x["p"]["plateID"]): x["pid"] for P in (E, O) for x in P if x["pid_src"].startswith("FitsArchive")}
    lens = Counter(len(r["plateID"].strip()) for r in rows)
    short = Counter(r["Survey"] for r in rows if len(r["plateID"].strip()) < 4 and r["plateID"].strip().isdigit())
    sci = [r for r in rows if re.match(r"^\d\.\d\dE\+\d\d$", r["plateID"].strip())]
    if short:
        add("plateID", "all surveys", [f"{k}:{v}" for k, v in sorted(short.items(), key=lambda t: -t[1])], "plateID",
            ", ".join(sorted(set(r["plateID"] for r in rows if len(r["plateID"].strip()) < 4))[:3]) + ", ...",
            "4 characters" + (f"; POSS-I: {sum(1 for k in rest if len(k[1]) < 4)} restored from FitsArchive file names (column plateID_restored)"
               if rest else ""),
            f"{sum(short.values())} plateIDs are numeric and shorter than 4 characters ({lens[4]} of {len(rows)} have 4): "
            "leading zeros lost, as a spreadsheet does with numeric-looking codes", "2024 list; FitsArchive file names (POSS-I)",
            "restore 4-character plateIDs (POSS-I: plateID_restored)", n=sum(short.values()))
    if sci:
        sv = Counter(r["Survey"] for r in sci)
        add("plateID", "all surveys", [f"{k}:{v}" for k, v in sorted(sv.items(), key=lambda t: -t[1])], "plateID",
            ", ".join(r["plateID"] for r in sci[:3]) + ", ...",
            ", ".join(f"{k[0]} {v}" for k, v in sorted(rest.items()) if "E+" in k[1]) if rest else "",
            f"{len(sci)} plateIDs are written in scientific notation: a spreadsheet reads a code such as 08E0 as 8 x 10^0 and "
            "0E20 as 0 x 10^20 = 0, so ten different codes became '0.00E+00'. "
            + (f"For the {sum(1 for k in rest if 'E+' in k[1])} POSS-I rows the FitsArchive file names give the codes (reference "
               "value, column plateID_restored); for other surveys they are not checked here" if rest else
               "The original codes are not checked here"),
            "2024 list, pattern ^d.ddE+dd$; FitsArchive directory listings",
            "regenerate the CSV from the database (POSS-I: plateID_restored)", n=len(sci))
    pg = Counter(r["Survey"] for r in rows if r["plateGrade"].strip() == "unavailabl")
    if pg:
        add("plateGrade", "all surveys", [f"{k}:{v}" for k, v in sorted(pg.items(), key=lambda t: -t[1])], "plateGrade",
            "unavailabl", "unavailable", f"{sum(pg.values())} cells truncated to 10 characters", "2024 list", "cosmetic",
            n=sum(pg.values()))
    for v in vi:
        if not v["fobs_ok"]:
            add("VI/25 record", "VI/25", [f"POSS {v['POSS']}"], "Obs / fObs", f"{v['obs']:%Y %b %d} / {v['fM']} {v['fD']}", "",
                "record inconsistent in itself (final day is not Obs + 1 d)", "nposs.dat", "use other witnesses")
    if ext:
        for item in ext.get("anomalies", []):
            add(item["category"], item["survey"], item["regions"], item["field"], item["listed_value"],
                item.get("reference_value", ""), item["description"], item["evidence"], item["suggested_action"],
                n=item.get("n_rows"))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(A[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(A)
    return len(A)


def _num_eq(a, b):
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def restore_plateid(p, fa, have_listing):
    pid = p["plateID"].strip()
    if not have_listing:
        return (pid if len(pid) == 4 else ""), "not checked (no FitsArchive listing given)"
    m = re.match(r"^X([EO])(\d+)", p["Region"])
    ids = fa.get(("X" + m.group(1), m.group(2)), set()) if m else set()
    if pid.upper() in ids:
        return pid, "list = FitsArchive file name"
    num = [i for i in ids if _num_eq(i, pid)]
    if len(pid) != 4 and len(num) == 1:
        return num[0], "FitsArchive file name (printed value mangled by a spreadsheet)"
    if len(pid) == 4:
        return pid, ("list (no FitsArchive file with this plateID)" if ids else "list (no FitsArchive file for this Region)")
    return "", "unresolved"


# ----------------------------------------------------------------------------- main
def build(args):
    for path, ref, name in ((args.plates, SHA_PLATES, "plate list"), (args.nposs, SHA_NPOSS, "nposs.dat")):
        h = sha256(path)
        if h != ref and not args.allow_other_version:
            die(f"{name}: sha256 {h} differs from the documented version {ref} (use --allow-other-version)")
    rows = read_plate_list(args.plates)
    vi = read_vi25(args.nposs)
    ast = read_asteroids(args.asteroids)
    ext = json.load(open(args.external, encoding="utf-8")) if args.external else None
    os.makedirs(args.out, exist_ok=True)
    S = dict(inputs=dict(plates=dict(file=os.path.basename(args.plates), sha256=sha256(args.plates), rows=len(rows)),
                         nposs=dict(file=os.path.basename(args.nposs), sha256=sha256(args.nposs), records=len(vi)),
                         asteroids=dict(file=os.path.basename(args.asteroids), sha256=sha256(args.asteroids)) if args.asteroids else None,
                         external=dict(file=os.path.basename(args.external), sha256=sha256(args.external)) if args.external else None),
             rules=dict(max_sep_deg=MAX_SEP_DEG, clock_tol_min=CLOCK_TOL_MIN, ha_identity_tol_min=HA_ID_TOL_MIN,
                        ha_peak_tol_min=HA_TOL_MIN, ha_max_abs_dec=HA_MAX_ABS_DEC, neighbour_days=NEIGHBOUR_DAYS,
                        run_days=RUN_DAYS, sidereal_shift_per_day_min=round(SID_SHIFT_MIN, 4)))
    tables, c0 = {}, {}
    for band, survey in (("E", "POSSI-E"), ("O", "POSSI-O")):
        P = pair_rows([r for r in rows if r["Survey"] == survey], vi, band)
        pk = evaluate(P, band)
        c0[band] = pk.pop("c0")
        S["ha_peaks_" + band] = pk
        reg_count = Counter(x["p"]["Region"] for x in P)
        first, groups = {}, defaultdict(list)
        for i, x in sorted(enumerate(P), key=lambda t: (t[1]["p"]["Region"], t[0])):  # first = lowest Region name
            x["cls"] = classify(x)
            x["dup"] = reg_count[x["p"]["Region"]] > 1
            key = x["match"][2]["id"] if x["match"] else x["p"]["Region"] + "|" + x["p"]["plateID"]
            x["exp_first"] = key not in first
            x["exp_first_region"] = first.setdefault(key, x["p"]["Region"])
            groups[key].append(x)
            x["exp_group"] = groups[key]
        tables[band] = P
    # plateID: the FitsArchive file names carry the 4-character code (spreadsheet-mangled values restored)
    fa = defaultdict(set)
    for pre, fl in ((ext or {}).get("fitsarchive_files") or {}).items():
        for fn in fl:
            m = re.match(r"^x[eo](\d+)_([0-9a-z]+)_\d\d_\d\d\.fits$", fn)
            if m:
                fa[(pre, m.group(1))].add(m.group(2).upper())
    for band in ("E", "O"):
        for x in tables[band]:
            x["pid"], x["pid_src"] = restore_plateid(x["p"], fa, bool(fa))
    sig = defaultdict(list)
    for band in ("E", "O"):
        for x in tables[band]:
            p = x["p"]
            sig[(p["UTobservation"], p["hourangle"], p["zenithdistance"], p["airmass"])].append(x)
    copy_of = {}
    for g in sig.values():
        if len(set(y["p"]["Region"] for y in g)) < 2:
            continue
        src = sorted(g, key=lambda y: (y["cls"] not in REGULAR, y["p"]["Region"]))[0]
        for y in g:
            if y["p"]["Region"] != src["p"]["Region"]:
                same = bool(y["match"] and src["match"] and y["match"][2]["id"] == src["match"][2]["id"])
                copy_of[id(y)] = (src["p"]["Region"], same)
    for band in ("E", "O"):
        for x in tables[band]:
            x["copy_of"], x["copy_same_exp"] = copy_of.get(id(x), (None, False))
    assign_evidence(tables, ast)
    gross_alternative(tables)
    for band in ("E", "O"):
        for x in tables[band]:
            finish_row(x, band)
    write_columns(os.path.join(args.out, "columns.csv"))
    write_band(tables["E"], "E", os.path.join(args.out, "poss1_E_dates.csv"))
    write_band(tables["O"], "O", os.path.join(args.out, "poss1_O_dates.csv"))
    for band in ("E", "O"):
        S["counts_" + band] = counts(tables[band], c0[band])
    S["night_blocks_E"] = night_blocks(tables["E"], tables["O"], os.path.join(args.out, "night_blocks_E.csv"))
    S["reconciliation_E"] = reconcile(tables["E"])
    S["reconciliation_O"] = reconcile(tables["O"])
    S["listed_time_rounding"] = time_rounding(tables)
    S["vi25"] = dict(records=len(vi), poss_i_proper=sum(1 for v in vi if v["MLP"] <= 937),
                     fobs_inconsistent=[v["POSS"] for v in vi if not v["fobs_ok"]],
                     numbers_used_twice_in_poss_i_proper=sum(1 for k, n in Counter(v["key"] for v in vi if v["MLP"] <= 937).items() if n > 1),
                     neighbour_flags=[(v["POSS"], f"{v['obs']:%Y-%m-%d}", f"{v['nb_alt']:%Y-%m-%d}") for v in vi if v["nb_alt"]],
                     records_beyond_poss_i_proper=dict(n=sum(1 for v in vi if v["MLP"] > 937),
                                                       mlp_range=[min((v["MLP"] for v in vi if v["MLP"] > 937), default=None),
                                                                  max((v["MLP"] for v in vi if v["MLP"] > 937), default=None)],
                                                       with_E_start_time=sum(1 for v in vi if v["MLP"] > 937 and v["E_h"] is not None),
                                                       paired_list_rows=sum(1 for b in ("E", "O") for x in tables[b] if x["match"] and x["match"][2]["MLP"] > 937)))
    S["epoch_one_day_shift_mas_per_arcsec_per_yr"] = round(1000 / 365.25, 3)
    tables["c0"] = c0
    S["known_anomalies_rows"] = anomalies(rows, tables, vi, ext, os.path.join(args.out, "known_anomalies.csv"))
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(S, f, indent=1, default=str)
    brief = {b: {k: S["counts_" + b][k] for k in ("rows", "exposures", "match_rule", "class_rows", "regular_exposures",
                                                  "evening_date", "correct", "evening_share", "evening_share_wilson95",
                                                  "by_zone_evening_correct", "evidence_rows")} for b in ("E", "O")}
    brief["reconciliation_E"] = S["reconciliation_E"]
    print(json.dumps(brief, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plates", required=True, help="SurveyPlateListLatest.csv (MAST, 2024-06-20)")
    ap.add_argument("--nposs", required=True, help="nposs.dat (CDS VizieR VI/25)")
    ap.add_argument("--asteroids", help="asteroid_checks.csv (optional)")
    ap.add_argument("--external", help="external_checks.json from check_external.py (optional)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--allow-other-version", action="store_true", help="run although checksums differ")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
