# ./kuratierung — Zweitweg + Kuratierungswerkzeuge (P8, BAUPLAN-V2 §2.3)

Angelegt 2026-10-20 (P8). Werkzeug-Output; alleiniger Wettbewerbsautor ist Christian Bucher. Alles eigener Code, `python3 -I`,
Standardbibliothek + pandas/numpy/pyarrow; kein Netz, kein HF-Token, keine Item-Texte gelesen oder ausgegeben (nur IDs, Hashes,
Zählungen, Subjekt-Metadaten). v1 (`modell/`) unverändert. Umgebung: `PAIEC_WORK=$PAIEC_WORK`, `OMP_NUM_THREADS=1`.

| Datei | Zweck | Ergebnis (2026-10-20) |
|---|---|---|
| `wiederholung_b.py` → `wiederholung_b.json`, `noise_floor_by_benchmark.csv` | **Zweiter Rechenweg L10** (irreduzibles Antwortrauschen): pandas-only, aus den Roh-Antworten statt `agg.parquet`, Schätzer über `var(ddof=1)` statt Formel; vergleicht gegen Erstweg `v2-plan/d-wissenschaft/wiederholung.json` (Toleranz 1 %); enthält die L9-Abgleichstabelle | rc 0, 35 s; Population bitgleich (31 389 917 / 68 268 267 / 3 144 967); L10 0,044385 antwortgew., 0,067141 zellgew., Median je Bm 0,048821 (62 Bm) — rel. Abw. ≤ 4e−16 |
| `noise_floor_by_benchmark.csv` | Kuratierungs-Kennzahl je Benchmark (156 binäre public Benchmarks mit Daten): Zellen, Wdh-Zellen, Anteile, L10 (antwort-/zellgewichtet), k/n-Orakel, n-Median/Max | für Repo `curation/` (nur IDs/Zählungen) |
| `l9_abgleich.md` | Auflösung 0,0065 vs 0,0229: dieselbe k/n-Formel, Paar- vs Antwortgewichtung, Testpaare vs ganze DB; Empfehlung an P2/P10 | Zweitweg trifft C: 0,00649 vs 0,00652 |
| `b0lage.py` → `b0lage_b.json`, `b0lage_b.csv` | **B0-Negativbefund, eigener Weg**: LOBO über 142 Benchmarks, Ridge mit verschachteltem λ + kNN-Referenz, 50 textfreie Item-Aggregat-Merkmale | R² LOBO Ridge −0,033, kNN −0,255, Konstante −0,014 (Erstweg −0,024): Benchmark-Lage aus sichtbaren Nicht-Text-Merkmalen **nicht** vorhersagbar; 18 Extrembenchmarks bleiben bei ≈ 0,5 |
| `identitaet.py` → `identitaet_reparatur.csv`, `identitaet_zusammenfassung.json` | **Identitäts-Reparaturtabelle**: je namenlosem Subjekt (13 371 = 58,0 %) Bezeichner aus `subject_features_extra`, Normalisierung, Abgleich mit bekannten `normalized_name` (exact/contains), Verbreitung über Benchmarks | 8 930 (66,8 %) mit Bezeichner [D-merkmale §2.3 zählte 74 % mit weiterer Schlüsselmenge — Spanne 67–74 % berichten]; 2 092 verschiedene, 1 014 in ≥ 2 Benchmarks; 496 Vorschläge auf bekannte Namen (174 exact, 322 contains) |
| `mdb_check.py` | **Prüfwerkzeug** für eine lokale measurement-db-Basis: Schema/Katalog/Fremdschlüssel/Duplikate/{0,1}-Werte (Fehler → rc 1), Polarität, Identitäts-Duplikate (acht Felder), Loader-Abdeckung (Befunde → rc 0, mit `--streng` rc 1), Wiederholungs-Statistik; Datei fehlt/unlesbar → rc 2 (fail-closed) | volle Basis: **rc 0**, 1 min 39 s, 92 580 425 Antworten, 5 Befunde = F1/F8/Polarität exakt (96/156; 119 Subjekte, 25 Gruppen, 13 Bm; 7/5/2) → `mdb_check_basis.json` |
| `tests/test_mdb_check.py` → `tests/mdb_check_tests.log` | **Fehlerfälle**: Teilbasis (5 kleine Benchmarks) kopiert, 7 Verfälschungen | 9/9 wie erwartet (V0 rc 0; Antwort 2,0 / Spalte fehlt / Dublette / Polaritätswiderspruch rc 1; abgeschnittene Datei / fehlende Datei rc 2; Identitätsduplikat rc 0, mit `--streng` 1) |
| `fallbeispiele.py` → `fallbeispiele.json`; `bericht-v2/fallbeispiele.md` | Lernkurven je Benchmark aus den CV-Sätzen; zwei Fallbeispiele mit Ursache, Zahl, Datei | gelungen `nyu_ctf_bench` (S3 −0,0204 ± 0,0029; S1 −0,0038), misslungen `mind2web` (+0,0060; Gruppe 13 Ein-Paar-Bm +0,0032 ± 0,0006) |

## Beispielaufrufe
```bash
export PAIEC_WORK=$PAIEC_WORK OMP_NUM_THREADS=1
python3 -I wiederholung_b.py                      # rc 0 = zwei Wege innerhalb 1 %
python3 -I b0lage.py && python3 -I identitaet.py && python3 -I fallbeispiele.py
python3 -I mdb_check.py --basis "$PAIEC_WORK/basis" --aus mdb_check_basis.json          # rc 0 erwartet
python3 -I tests/test_mdb_check.py                 # baut Fixture unter $PAIEC_WORK/p8-work/fixture, 9 Varianten
```

## Beispielausgabe `mdb_check.py` (volle Basis, 2026-10-20)
```
mdb_check .../paiec-data/basis: rc=0  Fehler=0  Befunde=5
  BEFUND  Polarität: 7 binäre Benchmarks lower_is_better (1 = unerwünscht): ['advprompter', 'crow', 'emoji_attack', 'harmbench', 'jailbreakbench', 'llmail_inject', 'wmt_mqm']
  BEFUND  Polarität: 5 binäre Benchmarks unordered: ['alignment_faking', 'braveguard', 'dbpa', 'safeagentbench', 'tensortrust']
  BEFUND  Polarität: 2 binäre Benchmarks ohne direction: ['os_harm', 'researchcodebench']
  BEFUND  Identität: 119 Subjekte in 25 Gruppen (13 Benchmarks) erhalten identischen Wettbewerbs-Input (alle acht Felder gleich); ...
  BEFUND  Loader-Abdeckung: 96 von 156 eligible Benchmarks außerhalb der Sichtbarkeit des Baseline-Loaders (Spalte seen_by_baseline_script)
  INFO    benchmarks = 281 · subjects = 23048 · antworten_gepruefte_benchmarks = 92580425
```

## Grenzen
- Die Wiederholungs-Statistik in `mdb_check.py` läuft auf der **rohen** Basis (alle binären Benchmarks inkl. 3 withheld, ohne die
  Modell-Ausschlüsse F3/F4); ihr Median über Benchmarks mit ≥ 100 Wdh-Zellen ist deshalb 0,04932 (63 Bm) statt 0,04882 (62 Bm) —
  die Differenz ist genau der withheld-Benchmark `swe_together` (geprüft 20:50Z: je Benchmark identische Werte). Die Modellzahl
  steht in `wiederholung_b.json`.
- `mdb_check.py` prüft das **lokale** Ablageformat von `build_basis.py` (`responses/benchmark=<bm>/part-0.parquet`, Codes statt IDs); das
  Original-HF-Layout (`<bm>/formatted_tables/*.parquet` mit `subject_id`/`item_id`-Strings) ist **nicht** implementiert und nicht getestet —
  im Repo ist deshalb `modell/basis/build_basis.py` Schritt 0, der dieses lokale Format erzeugt.
- Identitätstabelle: Klasse `contains` ist ein Kuratoren-Hinweis (Verwechslungsgefahr gpt4/gpt4o), keine Zuordnung; Score-Wirkung einer
  Reparatur < 0,001 ALC (C §5).
- Alle Fallbeispiel-Zahlen sind discovery (Saaten 0–2); Konfirmation P4 steht aus.
- Kehrseite des Pakets: Zwei Rechenwege, die dieselbe Auswahl (binär/public/coverage, F3/F4-Ausschlüsse) teilen, prüfen die Rechnung,
  nicht die Auswahl — dafür stehen die Kontrollsummen gegen `daten_zusammenfassung.json`.

## Notes for this repository

The scripts read the local data base built by Step 0 (`$PAIEC_WORK/basis`) and write their outputs next to the script (the shipped
outputs are the author's run of 2026-10-20). `wiederholung_b.py` also compares against a first-path file (`--erstweg`) that is not
included. Item text is not read or published. See `../LIZENZ-PRUEFUNG.md`.
