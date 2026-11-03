#!/usr/bin/env bash
# run_all.sh -- download the two public inputs, verify their sha256, rebuild all tables, compare with the package.
# Usage: bash scripts/run_all.sh [workdir]        (default workdir: ./rebuild)
# Needs: curl, sha256sum, cmp, python3 (>= 3.8) with numpy and astropy (pyerfa).
# Optional (network, STScI only): WITH_EXTERNAL=1 re-runs check_external.py (older list, FITS headers, FitsArchive
# listings) instead of using the shipped evidence/external_checks.json; the comparison then shows the expected
# differences (fetch times; anything STScI changed since 2026-10-14).
# On failure: set -e stops at the first failing command; a checksum mismatch stops before any table is built.
# Exit 3: rebuild finished but differs from the shipped files (listed as DIFF).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pkg="$(dirname "$here")"
w="${1:-rebuild}"
mkdir -p "$w/inputs" "$w/out"
curl -sS -L -o "$w/inputs/SurveyPlateListLatest.csv" \
  "https://outerspace.stsci.edu/download/attachments/176435492/SurveyPlateListLatest.csv?version=1&modificationDate=1718908770237&api=v2"
curl -sS -L -o "$w/inputs/nposs.dat" "https://cdsarc.cds.unistra.fr/ftp/VI/25/nposs.dat"
curl -sS -L -o "$w/inputs/ReadMe" "https://cdsarc.cds.unistra.fr/ftp/VI/25/ReadMe"
( cd "$w/inputs" && sha256sum -c - <<'EOF'
62947dc69bf2de3903ff6c7c038e5db49d36ae21bb121c2c7c9960aded706834  SurveyPlateListLatest.csv
77be67e26ce95d34f46c82650252473eb6e13ea4c8c815b70d74356ac8180991  nposs.dat
ea9fc69f4f74fab613aec9b87c9f0d59c4ca357bbf7ab43eccb30e483a64e118  ReadMe
EOF
)
if [ "${WITH_EXTERNAL:-0}" = "1" ]; then
  python3 -I "$here/check_external.py" --plates "$w/inputs/SurveyPlateListLatest.csv" \
    --raw-dir "$w/raw_headers" --out "$w/out/external_checks.json" > "$w/out/check_external.log"
  ext="$w/out/external_checks.json"
else
  ext="$pkg/evidence/external_checks.json"
fi
python3 -I "$here/build_tables.py" --plates "$w/inputs/SurveyPlateListLatest.csv" --nposs "$w/inputs/nposs.dat" \
  --asteroids "$pkg/inputs/asteroid_checks.csv" --external "$ext" --out "$w/out" > "$w/out/build_tables.log"
python3 -I "$here/other_surveys_ha.py" --plates "$w/inputs/SurveyPlateListLatest.csv" \
  --out "$w/out/other_surveys_ha.json" > "$w/out/other_surveys_ha.log"
echo "tables written to $w/out; comparison with the package:"
same=1
for f in poss1_E_dates.csv poss1_O_dates.csv known_anomalies.csv night_blocks_E.csv columns.csv summary.json \
         other_surveys_ha.json; do
  if cmp -s "$w/out/$f" "$pkg/$f"; then echo "  OK    $f"; else echo "  DIFF  $f"; same=0; fi
done
if [ "$same" = "1" ]; then
  echo "rebuild identical to the package"
else
  echo "rebuild differs from the package (expected only with WITH_EXTERNAL=1)"
  exit 3
fi
