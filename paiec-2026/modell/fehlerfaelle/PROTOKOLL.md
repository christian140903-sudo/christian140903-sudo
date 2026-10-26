## Lauf 2026-10-20T20:21:36Z
| Fall | Seite | Kommando (gekürzt) | rc | Soll | Ergebnis |
|---|---|---|---:|---|---|
| F1 | rot | v1-Paket: tests.test_haertung TestF1 | 1 | !=0 | erfuellt |
| F1 | gruen | v2core: TestF1 (injizierte Ausnahme -> BB-Wert, Zähler; Kette bis 0,5) | 0 | 0 | erfuellt |
| F2 | rot | v1-Paket: TestF2 (true/yes/None) | 1 | !=0 | erfuellt |
| F2 | gruen | v2core: TestF2 (Labelformen bitgleich, None übersprungen) | 0 | 0 | erfuellt |
| F3 | rot | v1-Paket: TestF3 (Zähler fehlen / 0,5 statt BB) | 1 | !=0 | erfuellt |
| F3 | gruen | v2core: TestF3 (1e4 Eingaben 0 Fallbacks; gebrochener Zustand 1e4 BB; 1e3 Konstante) | 0 | 0 | erfuellt |
| F4 | rot | v2core OHNE Sperre (PAIEC_OHNE_SPERRE=1), 8 Threads | 1 | !=0 | erfuellt |
| F4 | gruen | v2core mit Sperre, 8 Threads = sequenzielle Referenz | 0 | 0 | erfuellt |
| F5 | rot | frischer_prozess.py auf leerem Verzeichnis (fail-closed, rc 2) | 2 | !=0 | erfuellt |
| F5 | gruen | frischer_prozess.py v2core 1e5/3e5 Labels, 20 Aufrufe, Median erster predict < 5 s | 0 | 0 | erfuellt |
| F6 | rot | speicher.py --limit-mb 1 (Grenze verletzt, rc 1) | 1 | !=0 | erfuellt |
| F6 | gruen | speicher.py v2core 3e5 Labels < 500 MB | 0 | 0 | erfuellt |
| F7 | rot | pruefe_platt_wahl.py auf v1 cv_A/auswertung.json (Stufenwahl nicht verschachtelt) | 1 | !=0 | erfuellt |
| F7 | gruen | pruefe_platt_wahl.py auf cv_V2K1 + state_v2core.json | 0 | 0 | erfuellt |

Ergebnis des Laufs 2026-10-20T20:21:36Z: GESAMT=0 (0 = alle 7 Fälle rot UND grün wie gefordert). Log: fehlerfaelle/protokoll.log

