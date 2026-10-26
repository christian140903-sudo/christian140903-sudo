# Failure cases of `make smoke` (each triggered once on a fresh clone of tag v2.0-paiec, 2026-10-21)

A check counts as built only if its failure case was triggered. Exit codes are those of `make`/the script.

| Case | Manipulation | Expected | Observed |
|---|---|---|---|
| F1 | one digit of `modell/paket/state_final.json` changed | `make hash-check` and `make smoke` fail | `state_final.json: FAILED`, rc 2 (both); after restoring the file rc 0 |
| F2 | one reference prediction changed by +1e-6 | `smoke_vergleich.py` reports a deviation | verdict `ABWEICHUNG`, rc 1 |
| F3 | new-predictions file missing | fail-closed | verdict `FEHLER` (FileNotFoundError), rc 2 |
| F4 | `PAIEC_WORK` without a data base | `make fold0` stops with a message | `FEHLT: .../modell/agg.parquet ...`, rc 2 |
| F5 | one byte appended to `modell/dist/paiec_v2core.zip` | `make hash-check` fails | `paiec_v2core.zip: FAILED`, rc 2; after restoring rc 0 |

Green run on the unmodified clone: `make smoke` rc 0, fold 0 max |dq| = 0 and max |dBrier| = 0 against `reference/`, 26 tests OK, about 70 s wall time on one core.
Limitation: all checks compare the code with the author's stored outputs; they cannot detect an error that is present in both.
