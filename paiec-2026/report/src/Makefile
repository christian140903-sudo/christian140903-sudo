# bericht-v2/Makefile — Abbildungen und Tabellen des Bericht-v2 aus JSON/CSV (P7, BAUPLAN-V2 §2.3)
# Aufruf: make figs tabs   (rc 0 nur, wenn alle Dateien erzeugt wurden; Skripte brechen bei fehlender Eingabe ab)
PY ?= python3 -I
PRUEF ?=
export OMP_NUM_THREADS ?= 1
export OPENBLAS_NUM_THREADS ?= 1
export MKL_NUM_THREADS ?= 1

ABB := abbildungen
TAB := tabellen
FIGS := fig1_lernkurven fig2_zerlegung fig3_formel fig4_orakel_leiter fig5_zuverlaessigkeit fig6_fehleranalyse \
        figA1_v0_eff figA2_l10_je_benchmark figA3_liga_forest figA4_akquise figA5_fallbeispiele
TABS := tab1_hauptergebnis tab2_hypothesen tab3_ablationen_liga tab3a_ablationen tab4_protokoll tab6_budgets tab7_hyper

.PHONY: all figs tabs check clean refs pdf check-pages check-druck
all: figs tabs refs pdf

TEX := paiec_report_v2
LATEX := pdflatex -interaction=nonstopmode -halt-on-error

refs:
	$(PY) baue_refs.py

# P10: Zahlenpruefung fail-closed VOR dem Bau (ohne PDF), Bau (pdflatex+bibtex), danach Zahlen + Seitenzahl (mit PDF).
# R2/Q2: pruefe_zahlen.py braucht PAIEC_WORK (lokale Datenbasis: Zustandsdateien, paare.parquet); fehlt sie, ist das Ergebnis rc 1.
#        Ausdruecklich ohne diese Pruefungen: make pdf PRUEF=--ohne-zustand
pdf: refs
	$(PY) pruefe_abbildungen.py
	$(PY) pruefe_zahlen.py --ohne-pdf $(PRUEF)
	$(LATEX) $(TEX).tex > /dev/null
	bibtex $(TEX) > /dev/null
	$(LATEX) $(TEX).tex > /dev/null
	$(LATEX) $(TEX).tex > /dev/null
	$(PY) pruefe_zahlen.py $(PRUEF)
	@pdfinfo $(TEX).pdf | grep Pages

check-pages:
	$(PY) pruefe_zahlen.py $(PRUEF)

# S3: effektive Schriftgroesse jeder eingebetteten Abbildung (Figurgroesse/Einbaubreite), < 6 pt = Fehler
check-druck:
	$(PY) pruefe_abbildungen.py

figs:
	$(PY) plots_v2.py --aus $(ABB)
	@$(MAKE) --no-print-directory check-figs
	$(PY) pruefe_abbildungen.py

tabs:
	$(PY) tabellen_v2.py --aus $(TAB)
	@$(MAKE) --no-print-directory check-tabs

check: check-figs check-tabs

check-figs:
	@fehlt=0; for f in $(FIGS); do test -s $(ABB)/$$f.pdf || { echo "FEHLT: $(ABB)/$$f.pdf"; fehlt=1; }; done; \
	 test -s $(ABB)/quellen_abbildungen.tex || { echo "FEHLT: $(ABB)/quellen_abbildungen.tex"; fehlt=1; }; \
	 test $$fehlt -eq 0 && echo "figs: $(words $(FIGS)) PDF vorhanden" || exit 1

check-tabs:
	@fehlt=0; for f in $(TABS); do test -s $(TAB)/$$f.tex || { echo "FEHLT: $(TAB)/$$f.tex"; fehlt=1; }; done; \
	 test $$fehlt -eq 0 && echo "tabs: $(words $(TABS)) TeX vorhanden" || exit 1

clean:
	rm -f $(ABB)/*.pdf $(ABB)/quellen_abbildungen.tex $(ABB)/preview/*.png $(TAB)/*.tex $(TEX).aux $(TEX).bbl $(TEX).blg $(TEX).log $(TEX).out $(TEX).mainend
