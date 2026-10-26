#!/bin/bash
# Fehlerfall-Protokoll F1–F7 (D-ensemble §7.1, Regel 3: gebaut = Fehlerfall einmal ausgelöst, rot -> grün).
# Jeder Fall: ROT-Kommando (muss rc != 0 liefern) und GRÜN-Kommando (muss rc 0 liefern); rc mechanisch protokolliert.
# Aufruf: bash fehlerfaelle/protokoll.sh   (aus modell/; PAIEC_WORK gesetzt)
# Schreibt NUR anhängend nach fehlerfaelle/PROTOKOLL.md und fehlerfaelle/protokoll.log.
set -u
KERN=$(cd "$(dirname "$0")/.." && pwd)
cd "$KERN" || exit 9
export OMP_NUM_THREADS=1
SCR=$PAIEC_WORK/paiec-v2kern
V1=$SCR/v1paket
V2=$KERN/dist
LOG=fehlerfaelle/protokoll.log
MD=fehlerfaelle/PROTOKOLL.md
mkdir -p "$SCR/leer" "$SCR/rot"
if [ ! -f "$V1/model.py" ]; then mkdir -p "$V1" && (cd "$V1" && unzip -oq "$KERN/dist/v1/paiec_hier.zip"); fi
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "## Lauf $STAMP" >> "$MD"
echo "| Fall | Seite | Kommando (gekürzt) | rc | Soll | Ergebnis |" >> "$MD"
echo "|---|---|---|---:|---|---|" >> "$MD"
GESAMT=0
lauf() {  # lauf <Fall> <Seite rot|gruen> <soll: 0|!=0> <Beschreibung> <Kommando...>
  local fall=$1 seite=$2 soll=$3 besch=$4; shift 4
  echo "=== $fall $seite: $*" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  local ok
  if [ "$soll" = "0" ]; then [ $rc -eq 0 ] && ok=erfuellt || ok=VERFEHLT; else [ $rc -ne 0 ] && ok=erfuellt || ok=VERFEHLT; fi
  [ "$ok" = "VERFEHLT" ] && GESAMT=1
  echo "| $fall | $seite | $besch | $rc | $soll | $ok |" >> "$MD"
  echo "$fall $seite rc=$rc soll=$soll $ok"
}
UT="python3 -I -m unittest discover -s tests -t . -p test_haertung.py"
lauf F1 rot  "!=0" "v1-Paket: tests.test_haertung TestF1" env PAIEC_MODEL_DIR="$V1" $UT -k TestF1
lauf F1 gruen 0    "v2core: TestF1 (injizierte Ausnahme -> BB-Wert, Zähler; Kette bis 0,5)" env PAIEC_MODEL_DIR="$V2" $UT -k TestF1
lauf F2 rot  "!=0" "v1-Paket: TestF2 (true/yes/None)" env PAIEC_MODEL_DIR="$V1" $UT -k TestF2
lauf F2 gruen 0    "v2core: TestF2 (Labelformen bitgleich, None übersprungen)" env PAIEC_MODEL_DIR="$V2" $UT -k TestF2
lauf F3 rot  "!=0" "v1-Paket: TestF3 (Zähler fehlen / 0,5 statt BB)" env PAIEC_MODEL_DIR="$V1" $UT -k TestF3
lauf F3 gruen 0    "v2core: TestF3 (1e4 Eingaben 0 Fallbacks; gebrochener Zustand 1e4 BB; 1e3 Konstante)" env PAIEC_MODEL_DIR="$V2" $UT -k TestF3
lauf F4 rot  "!=0" "v2core OHNE Sperre (PAIEC_OHNE_SPERRE=1), 8 Threads" env PAIEC_OHNE_SPERRE=1 PAIEC_MODEL_DIR="$V2" $UT -k TestF4
lauf F4 gruen 0    "v2core mit Sperre, 8 Threads = sequenzielle Referenz" env PAIEC_MODEL_DIR="$V2" $UT -k TestF4
lauf F5 rot  "!=0" "frischer_prozess.py auf leerem Verzeichnis (fail-closed, rc 2)" python3 -I messungen/frischer_prozess.py --model-dir "$SCR/leer" --labels 1000 --aufrufe 1 --aus "$SCR/rot/f5.json"
lauf F5 gruen 0    "frischer_prozess.py v2core 1e5/3e5 Labels, 20 Aufrufe, Median erster predict < 5 s" python3 -I messungen/frischer_prozess.py --model-dir "$V2" --labels 100000,300000 --aufrufe 20 --max-s 5 --aus messungen/frischer_prozess.json
lauf F6 rot  "!=0" "speicher.py --limit-mb 1 (Grenze verletzt, rc 1)" python3 -I messungen/speicher.py --model-dir "$V2" --labels 300000 --limit-mb 1 --aus "$SCR/rot/f6.json"
lauf F6 gruen 0    "speicher.py v2core 3e5 Labels < 500 MB" python3 -I messungen/speicher.py --model-dir "$V2" --labels 300000 --limit-mb 500 --aus messungen/speicher.json
lauf F7 rot  "!=0" "pruefe_platt_wahl.py auf v1 cv_A/auswertung.json (Stufenwahl nicht verschachtelt)" python3 -I pruefe_platt_wahl.py ../../modell/ergebnisse/cv_A/auswertung.json --state paket/state_final.json
lauf F7 gruen 0    "pruefe_platt_wahl.py auf cv_V2K1 + state_v2core.json" python3 -I pruefe_platt_wahl.py ergebnisse_v2/auswertung_V2K1.json --state paket/state_v2core.json
echo "" >> "$MD"
echo "Ergebnis des Laufs $STAMP: GESAMT=$GESAMT (0 = alle 7 Fälle rot UND grün wie gefordert). Log: fehlerfaelle/protokoll.log" >> "$MD"
echo "" >> "$MD"
echo "GESAMT=$GESAMT"
exit $GESAMT
