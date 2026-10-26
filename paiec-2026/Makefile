# PAIEC 2026 - Reproduktion (eingereichtes Paket: modell/dist/paiec_v2core_final.zip = v2.0-core; v1-Vorlaeufer modell/dist/v1/paiec_hier.zip). PAIEC_WORK ist der einzige Pfadparameter (Standard: ./work).
# Recipes beginnen mit '>' statt Tab. Voraussetzung fuer alles ausser test/hash-check/theorie: die lokale Datenbasis
# (gated Datensatz, nicht im Repo): siehe README, Schritt 0 (make step0) und Schritt 0c (make daten).
.RECIPEPREFIX := >
SHELL := /bin/bash
export PAIEC_WORK ?= $(CURDIR)/work
export OMP_NUM_THREADS ?= 1
export OPENBLAS_NUM_THREADS ?= 1
export MKL_NUM_THREADS ?= 1
PY := python3 -I
PROZESSE ?= 4
W := $(PAIEC_WORK)/modell
STATE_SHA := 046e55c5cf5a8c337a60b1bc07fd3cc5c38c1809648fda267ba8226b9cd3bae4
# submitted package (v2.0-core, README corrected 2026-10-21; model.py byte-identical to paiec_v2core.zip)
FINAL_ZIP_SHA := 3274b09524221ac268be41f8b52fc56ca341daf72cf9734561be00e0f3a1e331
ZIP_SHA := 7883867c250c27b167dc45960cfe56f980a55597a9a9177adb8c0e00f8b9e012
# v1 predictor (not submitted): modell/dist/v1/paiec_hier.zip
V1_ZIP_SHA := f6e9d4eb603cabf4e03229ed7ff0c8a3081be1b9ceb9cfcac6a5b34888bb3d4e

.PHONY: report-tabs report-figs help all smoke test test-theorie hash-check need-data fold0 compare0 step0 daten cv1 tab-cv1 cv2 tab1 fig package-check

help:
> @echo "make smoke        Tests + Hash-Check + Falte 0 (Phase 1, Saat 0) + Vergleich 1e-9 (braucht \$$PAIEC_WORK/modell, 1 Rechenprozess)"
> @echo "make all          test, test-theorie, hash-check, package-check, tab-cv1, tab1, fig (braucht \$$PAIEC_WORK/modell; PROZESSE=$(PROZESSE))"
> @echo "make step0        Schritt 0: Datenbasis bauen (HF_TOKEN noetig, grosser Download)"
> @echo "make daten        Schritt 0c: Selektion + Aggregation -> \$$PAIEC_WORK/modell/agg.parquet"
> @echo "make report-tabs  Tabellen des Berichts aus JSON/CSV (report/src/tabellen_v2.py);  make report-figs  Abbildungen (matplotlib)"
> @echo "make tab-cv1      Phase 1 (Tabelle = v1-Zahlen, bitgleich)    make tab1  Phase 2 (Haupttabelle)    make fig  Abbildungen"

# ---------- Smoke ----------
smoke: hash-check test fold0 compare0
> @echo "SMOKE OK"

test:
> cd modell && $(PY) -m unittest discover -s tests -t .

test-theorie:
> cd theorie && $(PY) test_alc_law.py

# Hash-Check: alle verfolgten Dateien (SHA256SUMS) UND die gepinnten Hashes von Zustand und Paket.
hash-check:
> sha256sum --quiet -c SHA256SUMS
> @echo "$(STATE_SHA)  modell/paket/state_final.json" | sha256sum --quiet -c -
> @echo "$(FINAL_ZIP_SHA)  modell/dist/paiec_v2core_final.zip" | sha256sum --quiet -c -
> @echo "$(ZIP_SHA)  modell/dist/paiec_v2core.zip" | sha256sum --quiet -c -
> @echo "$(V1_ZIP_SHA)  modell/dist/v1/paiec_hier.zip" | sha256sum --quiet -c -
> @echo "hash-check ok"

need-data:
> @test -f "$(W)/agg.parquet" -a -f "$(W)/subjekte.parquet" || { echo "FEHLT: $(W)/agg.parquet bzw. subjekte.parquet - erst 'make step0 daten' (README, Schritt 0)"; exit 2; }

fold0: need-data
> rm -rf "$(PAIEC_WORK)/smoke/cv_f0"
> cd modell && $(PY) kreuzvalidierung.py --design A --saaten 0 --S 1,2,3,30 --nur 0 --prozesse 1 --aus "$(PAIEC_WORK)/smoke/cv_f0"

compare0:
> cd modell && $(PY) smoke_vergleich.py "$(PAIEC_WORK)/smoke/cv_f0/saetze_f0.parquet" ../reference/saetze_f0_saat0.parquet --tol 1e-9

# ---------- Schritt 0 und Daten ----------
step0:
> $(PY) scripts/download_data.py
> cd modell && $(PY) basis/build_basis.py 3

daten:
> cd modell && $(PY) daten.py

# ---------- Tabellen und Abbildungen ----------
cv1: need-data
> cd modell && $(PY) kreuzvalidierung.py --design A --S 1,2,3,30 --prozesse $(PROZESSE) --aus "$(W)/cv_V2K1"

tab-cv1: cv1
> cd modell && $(PY) auswertung.py --design V2K1

cv2: tab-cv1
> cd modell && $(PY) kreuzvalidierung.py --phase 2 --von cv_V2K1 --regime S1,S2,S3,S30,kompakt10 --prozesse $(PROZESSE) --aus "$(W)/cv_V2K2"

tab1: cv2
> cd modell && $(PY) auswertung.py --design V2K2 --phase 2

fig: tab-cv1
> cd modell && $(PY) plots.py --design V2K1 --S S3 --aus "$(PAIEC_WORK)/abbildungen"

package-check:
> $(PY) modell/paket/pruefe_paket.py modell/dist/paiec_v2core_final.zip --state modell/paket/state_v2core.json

all: test test-theorie hash-check package-check tab-cv1 tab1 fig
> @echo "ALL OK"

# ---------- Berichtsquelle (report/src): Tabellen/Abbildungen aus den mitgelieferten JSON/CSV ----------
report-tabs:
> cd report/src && $(PY) tabellen_v2.py --aus tabellen

report-figs:
> cd report/src && $(PY) plots_v2.py --aus abbildungen
