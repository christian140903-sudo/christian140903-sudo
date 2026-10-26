# analyse/ - Entdeckungs-Skripte hinter Tabelle 9 (Pfad A der Zweitrechnungen)

`wiederholung.py` (L10, geschlossener Schaetzer auf agg.parquet), `split.py` (Naeherung des Split-Terms) und `leiter.py` (Orakel-Leiter, L9) wurden in der
Entdeckungsphase gefahren; ihre Ergebnisdateien liegen in `report/src/daten/` bzw. `curation/`/`theorie/referenz/`. Hier stehen sie unveraendert bis auf die
Pfadkonstanten: das Original las und schrieb in einem sitzungsgebundenen Arbeitsordner; jetzt lesen sie `$PAIEC_WORK/modell` (lokale Datenbasis, README Schritt 0),
`leiter.py` den Code in `modell/`, und schreiben neben das Skript bzw. in den aktuellen Ordner. Sie sind nicht an `make` angeschlossen. Nach der Pfadanpassung neu gelaufen und mit dem Ergebnis des Entdeckungslaufs verglichen: `wiederholung.py` (15 s) und
`split.py` liefern JSON-Ausgaben, die dem Original entsprechen; `leiter.py` ist nach der Pfadanpassung nicht neu gelaufen, seine Ergebnisse stammen aus dem Lauf vom 2026-10-20/21. SHA-256 der Originale (vor der Pfadanpassung):

- `wiederholung.py`: 0192794e34891251c43a86f1c5000654e0d2d5af2c72d684509dc71eb883e507
- `split.py`: 99ed98948fa423a3f1090f498d3eb83f1cb2fb1144ed36fad30235a3018cff0b
- `leiter.py`: a295170d79b9c533dcffaccc7caf08caae06406154f96c8afb0fb172289b4e5c
