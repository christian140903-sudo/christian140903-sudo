#!/usr/bin/env python3
"""count_6_1_66.py - initial_release_date check for CSAF 2.0 documents (CSAF 2.1 CSD04).

What the script counts
    For every CSAF document it applies three rules of CSAF 2.1 CSD04:
    - Test 6.1.66: if the document status is "final" or "interim",
      /document/tracking/initial_release_date must be equal to the date of the
      revision history item with number "1" or "1.0.0". Dates are compared as
      points in time, so time zones are taken into account.
    - Clause 9.1.18: if test 6.1.66 fails, a CSAF 2.0 to CSAF 2.1 converter
      SHALL set initial_release_date to the date of that revision item.
      The script reports the new value, the shift in days and whether the year
      changes. The year is the one written at the start of the value; it is the
      folder name in Requirement 11 (section 7.1.11).
    - Test 6.2.5: initial_release_date is older than the date of the oldest
      revision history item.

Input
    Dump files of CIRCL vulnerability-lookup, https://vulnerability.circl.lu/dumps/
    (csaf_<name>.ndjson, one CSAF document per line), plain or gzip-compressed (.gz).
    If a tracking ID appears again in the same dump file, that line is skipped
    (the first line is used).

Output
    - With --csv FILE: one row per document (the columns are described in README-EN.md).
    - On standard output: counts per dump file and the key numbers.

How to run it on the dumps
    1. Download the 50 dump files listed in input-files.sha256 into an empty folder
       and check them (about 650 MB):
           for f in $(awk '{print $2}' input-files.sha256); do
               curl -O https://vulnerability.circl.lu/dumps/$f
           done
           sha256sum -c input-files.sha256
       These are all csaf_*.ndjson files of the dumps of 4 October 2026 except
       csaf_redhat, csaf_suse and csaf_opensuse.
    2. Count and write the CSV:
           python3 count_6_1_66.py --csv documents_6_1_66.csv csaf_*.ndjson
    To recount from the CSV only (no dumps needed):
           python3 count_6_1_66.py --from-csv documents_6_1_66.csv

Requirements: Python 3, standard library only (tested with Python 3.13).
"""

import argparse
import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

COLUMNS = [
    "source_dump",
    "publisher_name",
    "tracking_id",
    "self_urls",
    "csaf_version",
    "status",
    "initial_release_date",
    "revision_1_number",
    "revision_1_date",
    "test_6_1_66",
    "replaced",
    "initial_release_date_converted",
    "shift_days",
    "year_change",
    "fails_6_2_5",
]

# RFC 3339 date-time (the date format of CSAF)
DATE_TIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})$"
)

ONE_YEAR = timedelta(days=365)


def parse_date(value):
    """Return the date-time as an aware datetime in UTC, or None if it cannot be read."""
    if not isinstance(value, str):
        return None
    match = DATE_TIME.match(value)
    if not match:
        return None
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    microsecond = int((fraction or "0")[:6].ljust(6, "0"))
    try:
        if zone in ("Z", "z"):
            tz = timezone.utc
        else:
            sign = 1 if zone[0] == "+" else -1
            tz = timezone(sign * timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6])))
        moment = datetime(int(year), int(month), int(day), int(hour), int(minute),
                          int(second), microsecond, tzinfo=tz)
        return moment.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def text(value):
    """Return a JSON value as CSV text ('' if missing)."""
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value)


def check_document(dump, doc):
    """Return (CSV row, facts) for one CSAF document."""
    document = doc.get("document") or {}
    tracking = document.get("tracking") or {}
    publisher = document.get("publisher") or {}
    revisions = [r for r in tracking.get("revision_history") or [] if isinstance(r, dict)]
    references = [r for r in document.get("references") or [] if isinstance(r, dict)]

    ird_text = tracking.get("initial_release_date")
    ird = parse_date(ird_text)
    first = [r for r in revisions if r.get("number") in ("1", "1.0.0")]
    rev1 = first[0] if first else {}
    rev1_text = rev1.get("date")
    rev1_date = parse_date(rev1_text)

    # Test 6.1.66
    status = tracking.get("status")
    if status not in ("final", "interim"):
        result = "not_applicable"
    elif ird is None or rev1_date is None:
        result = "undetermined"
    elif ird == rev1_date:
        result = "pass"
    else:
        result = "fail"
    replaced = result == "fail"

    # Test 6.2.5
    dates = [parse_date(r.get("date")) for r in revisions]
    if ird is None or not dates or any(d is None for d in dates):
        fails_625 = "undetermined"
    else:
        fails_625 = "yes" if ird < min(dates) else "no"

    # Clause 9.1.18
    if replaced:
        shift = rev1_date - ird
        shift_days = "%.6f" % (shift.total_seconds() / 86400)
        year_change = ird_text[:4] != rev1_text[:4]
        converted = rev1_text
    else:
        shift = timedelta(0)
        shift_days = ""
        year_change = False
        converted = ird_text

    row = {
        "source_dump": dump,
        "publisher_name": text(publisher.get("name")),
        "tracking_id": text(tracking.get("id")),
        "self_urls": " ".join(r["url"] for r in references
                              if r.get("category") == "self" and isinstance(r.get("url"), str)),
        "csaf_version": text(document.get("csaf_version")),
        "status": text(status),
        "initial_release_date": text(ird_text),
        "revision_1_number": text(rev1.get("number")),
        "revision_1_date": text(rev1_text),
        "test_6_1_66": result,
        "replaced": "yes" if replaced else "no",
        "initial_release_date_converted": text(converted),
        "shift_days": shift_days,
        "year_change": "yes" if year_change else "no",
        "fails_6_2_5": fails_625,
    }
    facts = {
        "result": result,
        "replaced": replaced,
        "later": shift > timedelta(0),
        "year_change": year_change,
        "over_365_days": shift > ONE_YEAR,
        "fails_6_2_5": fails_625 == "yes",
    }
    return row, facts


def facts_from_row(row):
    """Return the facts of one CSV row (used by --from-csv)."""
    shift = float(row["shift_days"]) if row["shift_days"] else 0.0
    return {
        "result": row["test_6_1_66"],
        "replaced": row["replaced"] == "yes",
        "later": shift > 0,
        "year_change": row["year_change"] == "yes",
        "over_365_days": shift > 365,
        "fails_6_2_5": row["fails_6_2_5"] == "yes",
    }


def add(counter, facts):
    counter["documents"] += 1
    counter["6.1.66 " + facts["result"]] += 1
    if facts["replaced"]:
        counter["replaced"] += 1
        if facts["later"]:
            counter["later"] += 1
            counter["later_year_change"] += facts["year_change"]
            counter["later_over_365_days"] += facts["over_365_days"]
            counter["later_fails_6_2_5"] += facts["fails_6_2_5"]


def read_dumps(paths):
    """Read the dump files. Return (rows, counts per dump, reading statistics)."""
    rows = []
    per_dump = defaultdict(Counter)
    stats = Counter()
    seen = defaultdict(set)
    for path in paths:
        dump = os.path.basename(path).split(".")[0]
        stats["files"] += 1
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                stats["lines"] += 1
                try:
                    doc = json.loads(line)
                except ValueError:
                    doc = None
                if not isinstance(doc, dict):
                    stats["lines_not_json_object"] += 1
                    continue
                tracking_id = ((doc.get("document") or {}).get("tracking") or {}).get("id")
                if isinstance(tracking_id, str):
                    if tracking_id in seen[dump]:
                        stats["lines_repeated_tracking_id"] += 1
                        continue
                    seen[dump].add(tracking_id)
                row, facts = check_document(dump, doc)
                rows.append(row)
                add(per_dump[dump], facts)
    return rows, per_dump, stats


def read_csv(path):
    """Read a CSV written by this script. Return counts per dump."""
    per_dump = defaultdict(Counter)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            sys.exit("error: %s does not have the expected columns" % path)
        for row in reader:
            add(per_dump[row["source_dump"]], facts_from_row(row))
    return per_dump


def write_csv(path, rows):
    rows.sort(key=lambda r: (r["source_dump"], r["tracking_id"]))
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def report(per_dump):
    keys = ["documents", "replaced", "later", "later_year_change",
            "later_over_365_days", "later_fails_6_2_5"]
    total = Counter()
    print("Counts per dump file")
    print("%-36s %7s %7s %7s %7s %7s %7s" % ("dump file", "A", "B", "C", "D", "E", "F"))
    for dump in sorted(per_dump):
        total.update(per_dump[dump])
        print("%-36s %7d %7d %7d %7d %7d %7d" % ((dump,) + tuple(per_dump[dump][k] for k in keys)))
    print("%-36s %7d %7d %7d %7d %7d %7d" % (("TOTAL (%d dump files)" % len(per_dump),)
                                              + tuple(total[k] for k in keys)))
    print("A = documents")
    print("B = initial_release_date replaced (test 6.1.66 fails)")
    print("C = of B: revision 1 is dated later than initial_release_date")
    print("D = of C: the year changes")
    print("E = of C: shift of more than 365 days")
    print("F = of C: the document fails test 6.2.5")
    print()
    print("Test 6.1.66, all documents: pass %d, fail %d, undetermined %d, not applicable %d"
          % (total["6.1.66 pass"], total["6.1.66 fail"], total["6.1.66 undetermined"],
             total["6.1.66 not_applicable"]))
    print()
    cisco = per_dump.get("csaf_cisco", Counter())
    msrc = per_dump.get("csaf_microsoft", Counter())
    print("Key numbers")
    print("%7d  documents" % total["documents"])
    print("%7d  dump files (publishers)" % len(per_dump))
    print("%7d  documents in which initial_release_date is replaced" % total["replaced"])
    print("%7d    of these from Cisco (csaf_cisco)" % cisco["replaced"])
    print("%7d    of these from MSRC (csaf_microsoft)" % msrc["replaced"])
    print("%7d  MSRC documents in which revision 1 is dated later than initial_release_date"
          % msrc["later"])
    print("%7d    of these fail test 6.2.5" % msrc["later_fails_6_2_5"])
    print("%7d    of these move into a later year" % msrc["later_year_change"])
    print("%7d    of these move by more than 365 days" % msrc["later_over_365_days"])


def main():
    parser = argparse.ArgumentParser(
        description="Check initial_release_date of CSAF 2.0 documents against "
                    "test 6.1.66 and clause 9.1.18 of CSAF 2.1 CSD04.")
    parser.add_argument("dumps", nargs="*", help="dump files (.ndjson or .ndjson.gz)")
    parser.add_argument("--csv", help="write one row per document to this CSV file")
    parser.add_argument("--from-csv", dest="from_csv",
                        help="recount from this CSV file instead of reading dump files")
    args = parser.parse_args()
    if bool(args.from_csv) == bool(args.dumps):
        parser.error("give either dump files or --from-csv FILE")
    if args.from_csv:
        if args.csv:
            parser.error("--csv cannot be used with --from-csv")
        report(read_csv(args.from_csv))
        return
    rows, per_dump, stats = read_dumps(args.dumps)
    if args.csv:
        write_csv(args.csv, rows)
    print("Read %d lines from %d files; skipped %d lines whose tracking ID already appeared "
          "in the same dump file; %d lines were not a JSON object."
          % (stats["lines"], stats["files"], stats["lines_repeated_tracking_id"],
             stats["lines_not_json_object"]))
    print()
    report(per_dump)


if __name__ == "__main__":
    main()
