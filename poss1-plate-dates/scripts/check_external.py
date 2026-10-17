#!/usr/bin/env python3
"""check_external.py -- optional evidence for known_anomalies.csv from two further public STScI sources:
  1. the older plate list  https://gsss.stsci.edu/skysurveys/SurveyPlateList.txt  (UTF-16, fixed width;
     the copy read on 2026-10-14 had sha256 df81b0cb5a1d2ead7300e307cd4da4b162e0b21e690b128d07c9d9e04b7e536a)
  2. FITS primary headers of DSS plate scans:
     full-plate scans  https://archive.stsci.edu/missions/dss/FitsArchive/XEsurvey/  (first 28 800 bytes only,
     HTTP range request, no image data) and one cutout from https://archive.stsci.edu/cgi-bin/dss_search
  3. the directory listings FitsArchive/XEsurvey/ and FitsArchive/XOsurvey/: file names
     x<e|o><region number>_<plateID>_<nn>_<nn>.fits give the 4-character plateID of every scanned plate
Compared with the 2024 plate list (--plates, same file as for build_tables.py).
Writes --out external_checks.json, read by build_tables.py --external. Header bytes are saved in --raw-dir.
Run: python3 -I check_external.py --plates SurveyPlateListLatest.csv --raw-dir raw_headers --out external_checks.json
     [--old-list SurveyPlateList.txt]   (local copy instead of downloading)
What the layer below does on failure: urllib raises on HTTP errors and timeouts; this script then stops (no
partial JSON). A header without END card within 28 800 bytes is reported as such, not guessed.
Requires Python >= 3.8 and astropy (only to show what a FITS reader makes of the DATE-OBS card).
"""
import argparse
import csv
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

from astropy.io import fits

OLD_URL = "https://gsss.stsci.edu/skysurveys/SurveyPlateList.txt"
FA = "https://archive.stsci.edu/missions/dss/FitsArchive/"
DSS = "https://archive.stsci.edu/cgi-bin/dss_search?v=poss1_red&r={ra}&d={de}&e=J2000&h=1&w=1&f=fits"
SAMPLE = ["XE325", "XE001A", "XE098", "XE128", "XE217", "XE498", "XE628", "XE864", "XE876"]
# observation-related header cards recorded verbatim (which of them depend on the date, see README)
OBS_KEYS = ("DATE-OBS", "TIME-OBS", "TIMESYS", "EPOCH", "MJD-OBS", "EXPOSURE", "OBSHA", "OBSZD", "AIRMASS", "REFBETA",
            "REFBETAP", "REFK1", "REFK2", "SITELAT", "SITELONG", "EQUINOX", "SURVEY", "EMULSION", "FILTER", "SCANNUM",
            "DSCNDNUM")
FILE_RE = r'href="(x[eo]\d+_[0-9a-z]+_\d\d_\d\d\.fits)"'


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, nbytes=None, timeout=120):
    req = urllib.request.Request(url, headers={"Range": f"bytes=0-{nbytes - 1}"} if nbytes else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_old(raw):
    txt = raw.decode("utf-16")
    lines = txt.splitlines()
    names = lines[0].split()
    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", lines[1])]
    if len(names) != len(spans):
        raise SystemExit("old list: header and column rulers disagree")
    rows = []
    for ln in lines[2:]:
        if ln.strip():
            rows.append({n: (ln[a:b].strip() if i < len(spans) - 1 else ln[a:].strip()) for i, (n, (a, b)) in enumerate(zip(names, spans))})
    return rows


def cards_of(raw):
    cards = [raw[i:i + 80].decode("ascii", "replace") for i in range(0, len(raw) - len(raw) % 80, 80)]
    end = next((i for i, c in enumerate(cards) if c.rstrip() == "END"), None)
    return cards[:end + 1] if end is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", required=True)
    ap.add_argument("--old-list")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.raw_dir, exist_ok=True)
    new = [r for r in csv.DictReader(open(a.plates, newline="", encoding="ascii")) if r["Survey"] in ("POSSI-E", "POSSI-O")]
    J = dict(run_utc=now(), sources={}, anomalies=[])

    # ---- 1. older plate list
    raw = open(a.old_list, "rb").read() if a.old_list else get(OLD_URL)
    J["sources"]["old_list"] = dict(url=OLD_URL, local=bool(a.old_list), fetched_utc=now(), bytes=len(raw),
                                    sha256=hashlib.sha256(raw).hexdigest())
    old = {(r["Survey"], r["plateID"]): r for r in parse_old(raw) if r["Survey"] in ("POSSI-E", "POSSI-O")}
    padded = [r for r in new if (r["Survey"], r["plateID"]) not in old and (r["Survey"], r["plateID"].zfill(4)) in old]
    pairs = [(old.get((r["Survey"], r["plateID"])) or old.get((r["Survey"], r["plateID"].zfill(4))), r) for r in new]
    miss = sum(1 for o, _ in pairs if o is None)
    pairs = [(o, r) for o, r in pairs if o is not None]
    mm = [o for o, _ in pairs if re.match(r"^\d{4}-\d\d-\d\dT\d\d:(\d\d)", o["UTobservation"]) and
          int(o["UTobservation"][14:16]) > 59]
    same_date = sum(1 for o, r in pairs if o["UTobservation"][:10] == r["UTobservation"][:10])
    ep = [(r["Region"], o["Epoch"], r["Epoch"]) for o, r in pairs
          if o["Epoch"] and r["Epoch"] and abs(float(o["Epoch"]) - float(r["Epoch"])) > 0.5]
    J["old_list"] = dict(rows_poss1=len(old), matched_by_plateID=len(pairs), matched_only_after_zero_padding=len(padded), unmatched=miss,
                         minute_field_gt_59=len(mm), same_date_part=same_date,
                         example_XE325=next((o["UTobservation"] for o, r in pairs if r["Region"] == "XE325"), None),
                         epoch_differs_gt_half_year=ep)
    J["anomalies"].append(dict(
        category="older export", survey="POSSI-E/O", regions=["all POSS-I rows"], n_rows=len(pairs), field="UTobservation",
        listed_value=f"e.g. XE325 {J['old_list']['example_XE325']!r}", reference_value="hh:mm:ss in the 2024 list",
        description=f"older list stores the time as decimal hours written like hh:mm ({len(mm)} of {len(pairs)} POSS-I rows have a "
                    f"'minute' field > 59); the date part equals the 2024 list in {same_date} of {len(pairs)} rows",
        evidence=f"{OLD_URL} (sha256 {J['sources']['old_list']['sha256'][:12]}...)", suggested_action="retire the older list"))
    if padded:
        J["anomalies"].append(dict(
            category="plateID", survey="POSSI-E/O", regions=[r["Region"] for r in padded], field="plateID",
            listed_value=", ".join(r["plateID"] for r in padded[:3]) + ", ...", reference_value="0" + padded[0]["plateID"] + ", ... (older list)",
            description=f"{len(padded)} POSS-I plateIDs lost their leading zero in the 2024 list (4-character codes elsewhere)",
            evidence=OLD_URL, suggested_action="restore 4-character plateIDs"))
    for reg, eo, en in ep:
        J["anomalies"].append(dict(category="Epoch (older export)", survey="POSSI-E/O", regions=[reg], field="Epoch",
                                   listed_value=eo, reference_value=en, description="Epoch differs by > 0.5 yr between the older list and the 2024 list",
                                   evidence=OLD_URL, suggested_action="none for the 2024 list (fixed there)"))

    # ---- 2. FITS headers
    J["fitsarchive_files"] = {}
    for pre in ("XE", "XO"):
        raw_l = get(FA + pre + "survey/")
        fl = sorted(set(re.findall(FILE_RE, raw_l.decode("utf-8", "replace"))))
        J["sources"]["fitsarchive_listing_" + pre] = dict(url=FA + pre + "survey/", fetched_utc=now(), files=len(fl),
                                                          sha256=hashlib.sha256(raw_l).hexdigest())
        J["fitsarchive_files"][pre] = fl
    files = [f for f in J["fitsarchive_files"]["XE"] if f.startswith("xe")]
    byreg = {r["Region"]: r for r in new if r["Survey"] == "POSSI-E"}
    hdrs = []
    for reg in SAMPLE:
        r = byreg[reg]
        num = re.match(r"XE(\d+)", reg).group(1)
        cand = [f for f in files if f.startswith(f"xe{num}_{r['plateID'].lower()}_")]
        for fn in cand[:1]:
            raw = get(FA + "XEsurvey/" + fn, 28800)
            open(os.path.join(a.raw_dir, fn + ".hdr"), "wb").write(raw)
            cs = cards_of(raw)
            rec = dict(region=reg, file=fn, url=FA + "XEsurvey/" + fn, fetched_utc=now(), sha256_bytes=hashlib.sha256(raw).hexdigest(),
                       end_card_found=cs is not None)
            if cs:
                rec["DATE-OBS_card"] = next((c for c in cs if c.startswith("DATE-OBS")), None)
                h = fits.Header.fromstring("".join(cs))
                for k in ("REGION", "PLATEID", "PLTLABEL", "PLATERA", "PLATEDEC", "OBSHA", "EXPOSURE", "DATE"):
                    rec[k] = h.get(k)
                rec["DATE-OBS_as_read_by_astropy"] = h.get("DATE-OBS")
                rec["keywords"] = [c[:8].strip() for c in cs if c[:8].strip()]
                rec["obs_cards"] = {k: next((c.rstrip() for c in cs if c[:8].strip() == k), None) for k in OBS_KEYS}
                rec["list_RA_Dec"] = [float(r["RightAscension"]), float(r["Declination"])]
            hdrs.append(rec)
    # one dss_search cutout (XE325 field centre)
    r = byreg["XE325"]
    url = DSS.format(ra=r["RightAscension"], de=r["Declination"])
    raw = get(url)
    open(os.path.join(a.raw_dir, "dss_search_XE325.fits"), "wb").write(raw)
    cs = cards_of(raw[:28800])
    hdrs.append(dict(region="XE325", file="dss_search cutout", url=url, fetched_utc=now(), sha256_bytes=hashlib.sha256(raw).hexdigest(),
                     end_card_found=cs is not None, **({"DATE-OBS_card": next((c for c in cs if c.startswith("DATE-OBS")), None),
                                                        "REGION": fits.Header.fromstring("".join(cs)).get("REGION")} if cs else {})))
    J["fits"] = hdrs
    fa = [h for h in hdrs if h["file"] != "dss_search cutout" and h.get("DATE-OBS_card")]
    bad_quote = [h for h in fa if "/" in (re.match(r"^DATE-OBS= '([^']*)'", h["DATE-OBS_card"]) or [None, "/"])[1]]
    dech = [h for h in hdrs if h.get("DATE-OBS_card") and re.search(r"T\d\d:([6-9]\d)", h["DATE-OBS_card"])]
    newt = {r["Region"]: r["UTobservation"] for r in new if r["Survey"] == "POSSI-E"}
    dec_eq = 0
    for h in hdrs:
        m = re.search(r"(\d{4}-\d\d-\d\d)T(\d\d):(\d\d)", h.get("DATE-OBS_card") or "")
        t = newt.get(h["region"])
        if m and t:
            hh = int(t[11:13]) + int(t[14:16]) / 60 + int(t[17:19]) / 3600
            h["header_decimal_hours_equal_2024_time"] = (m.group(1) == t[:10] and abs(int(m.group(2)) + int(m.group(3)) / 100 - hh) < 0.004)
            dec_eq += h["header_decimal_hours_equal_2024_time"]
    J["anomalies"].append(dict(
        category="FITS header", survey="POSSI-E (DSS)", regions=[h["region"] for h in fa], field="DATE-OBS",
        listed_value=(bad_quote[0]["DATE-OBS_card"].rstrip() if bad_quote else ""),
        reference_value="DATE-OBS= 'YYYY-MM-DDThh:mm:ss'",
        description=f"FitsArchive full-plate headers: closing quote misplaced in {len(bad_quote)} of {len(fa)} sampled DATE-OBS cards; "
                    + (f"a FITS reader returns e.g. {bad_quote[0]['DATE-OBS_as_read_by_astropy']!r}. " if bad_quote else "")
                    + 
                    f"In {dec_eq} of {len([h for h in hdrs if h.get('DATE-OBS_card')])} sampled headers (full-plate and dss_search) DATE-OBS is "
                    "the list date with the time as decimal hours written like hh:mm (hh + mm/100 = the 2024 time; "
                    f"visible where the 'minute' field exceeds 59: {len(dech)})",
        evidence="; ".join(h["url"] for h in hdrs), suggested_action="regenerate DATE-OBS from the corrected UT start"))
    for h in fa:
        if h.get("PLATERA") is not None and h.get("list_RA_Dec"):
            dra = abs(float(h["PLATERA"]) - h["list_RA_Dec"][0])
            dde = abs(float(h["PLATEDEC"]) - h["list_RA_Dec"][1])
            h["plate_centre_vs_list_deg"] = [round(dra, 4), round(dde, 4)]
    x = next((h for h in fa if h["region"] == "XE876"), None)
    if x:
        J["anomalies"].append(dict(
            category="FITS header", survey="POSSI-E (DSS)", regions=["XE876"], field="REGION / PLTLABEL / PLATERA / PLATEDEC",
            listed_value=f"{x.get('REGION')} {x.get('PLTLABEL')} {x.get('PLATERA')} {x.get('PLATEDEC')}",
            reference_value="field of VI/25 POSS 1150 (ICRS RA 333.24, Dec -23.38), where XO876 (O1151) lies",
            description="header of the XE876 full-plate scan (what plate and centre it reports)", evidence=x["url"],
            suggested_action="compare with the image; see the duplicate-exposure row XE876/XE628"))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(J, f, indent=1, default=str)
    print(json.dumps(dict(old_list=J["old_list"], fits=[{k: h.get(k) for k in ("region", "file", "DATE-OBS_card", "DATE-OBS_as_read_by_astropy", "REGION", "PLTLABEL", "PLATERA", "PLATEDEC", "plate_centre_vs_list_deg")} for h in hdrs]), indent=1, default=str))


if __name__ == "__main__":
    main()
