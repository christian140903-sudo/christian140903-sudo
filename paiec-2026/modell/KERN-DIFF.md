# KERN-DIFF — v2.0-core gegenüber v1 (`modell/`)

Angelegt: 2026-10-20T20:16Z (`date -u`). Entstanden mit KI-Codierunterstützung; alleiniger Autor
Christian Bucher. v1 unangetastet: `modell/`, `modell/dist/paiec_hier.zip` (sha256 f6e9d4eb…3d4e). Kopie nach
`modell/` (ohne `dist/`, `__pycache__`); `paket/state_final.json` byteidentisch (sha256 046e55c5…3bae4).
Wird abschnittsweise ergänzt; Zahlen tragen ihre Quelle (Datei). [belegt] = aus Datei/Lauf; [Vermutung] = Schätzung.

## 0. Vorab festgelegte Regel für F7 (geschrieben VOR dem Lauf der verschachtelten Stufenwahl, 20:16Z)
v1 wählte die Platt-Stufenmenge {0, 1, 3, 7} auf ALLEN Falten (kreuzangepasste Brier-Senkung je Stufe über die
gepoolten Testfalten; `auswertung.py` → `kalibrierung_stufen`, REVIEW SOLL S1). Verschachtelt heißt hier: je äußerer
Falte f wird die Stufenmenge NUR aus den anderen 9 Falten bestimmt (innere Leave-one-fold-out-Platt: Parameter aus 8
Falten, angewandt auf die 9. — Stufe behalten, wenn der innere kreuzangepasste Brier der Stufe den unkalibrierten um
> 1e-6 unterschreitet, dieselbe Schwelle wie v1). Phase 2 der CV nutzt je Falte f diese verschachtelte Stufenmenge mit
den v1-Parametern der Falte (`platt_je_falte[f]`).
**Paketregel (vorab):** Stufe s bleibt im Paket genau dann, wenn s in der v1-Gesamtwahl liegt UND in der
verschachtelten Stufenmenge JEDER der 10 Falten. Ergibt das {0, 1, 3, 7}, bleibt `state_final.json` unverändert und
die Bitgleichheit zu v1 gilt. Weicht es ab, wird das Paket mit der kleineren Menge neu gebaut und die Abweichung
(je Falte) hier dokumentiert; Zahlen der Phase 2 ändern sich dann nur in den betroffenen Falten/Stufen.
Kehrseite: Diese Regel ist konservativ (Schnitt über Falten); eine Mehrheitsregel könnte eine Stufe behalten, die hier
fällt. Beides wird berichtet, entschieden wird nach der Schnittregel.

## 1. Was sich ändert — und was nicht (Übersicht)
| Datei (kern/) | Änderung gegenüber `modell/` | Mathematik von `predict` |
|---|---|---|
| `inferenz.py` | K4(b): `label_wert()`/`_label_zeichen()`; Fingerabdruck, Stichprobenschlüssel und `_bereite` nutzen sie statt `float(lab) >= 0.5`; unlesbare Labels (None/NaN/Text) werden übersprungen statt Ausnahme | unverändert (bitgleich belegt, §3) |
| `paket/baue_paket.py` | K4(a): `predict` mit Rückfallkette hier → Beta-Binomial (α, β aus `_STATE["baselines"]`, eigene Labels gezählt, tolerant gegen kaputte Einträge) → Konstante 0,5; Zähler `_ZAEHLER`, `diagnose()`; Klemmung `[1e-4, 1−1e-4]` (auf dem hier-Pfad No-op, da `kalibriere` schon klemmt); Standardname `paiec_v2core`; Kopf/README-Wortlaut (SOLL-5) | unverändert |
| `paket/pruefe_paket.py` | Prüfung 9: Zähler = 0 nach Normalbetrieb, Labelformen bitgleich, None übersprungen, kaputter Eintrag ⇒ genau 1 BB-Fallback | — |
| `paket/state_v2core.json` | NEU: = `state_final.json` (byteidentisch kopiert), nur `platt` auf Stufen {0, 1} reduziert (F7, §0-Regel), `version` 2, Feld `herkunft_v2core` mit alter Stufenmenge und Falten-Wahl | **ändert Vorhersagen nur bei n_eigen ∈ [3, 15)** (Platt-Stufen 3 und 7 entfallen) |
| `auswertung.py` | K4(f): `stufenwahl_verschachtelt()`; Feld `platt_stufenwahl_verschachtelt` (je Falte, Detail, Gesamt, Schnitt, Mehrheit, Abweichung); `platt_paket` folgt der Schnittregel | — |
| `kreuzvalidierung.py` | Phase 2 liest je Falte die verschachtelte Stufenmenge (falls vorhanden; sonst v1-Verhalten) | — |
| `tests/test_haertung.py`, `tests/test_label.py` | NEU: F1–F4 am gebauten Paket; Wertetabelle `label_wert` | — |
| `messungen/frischer_prozess.py`, `messungen/speicher.py` | NEU: F5, F6 (fail-closed, Rohdaten als JSON) | — |
| `pruefe_platt_wahl.py`, `vergleiche_saetze.py`, `vergleiche_v1_paket.py`, `platt_varianten.py`, `fehlerfaelle/protokoll.sh` | NEU: F7-Prüfung, Bitgleichheit CV, Paketvergleich in frischen Prozessen, Wirkung der Stufenwahl, Rot/Grün-Protokoll | — |
Unverändert: `merkmale.py`, `training.py`, `simulator.py`, `baselines.py`, `metrik.py`, `daten.py`, `basis/`, `tests/test_inferenz.py` (13/13 grün nach der Änderung), `paket/state_final.json` (v1-Referenz, sha256 046e55c5…).
Nicht gebaut (bewusst): Ablation „Hyperparameter fest auf Median" (D-ensemble K4g, zweiter Halbsatz) — nicht Teil des P1-Tests laut BAUPLAN §2.1/§7; die Klemmen sind dokumentiert (§5). Online-Fähigkeit K3, Stratum, Text: andere Pakete.

## 2. Fehlerfälle F1–F7 (Regel 3: gebaut = Fehlerfall einmal ausgelöst) — `fehlerfaelle/PROTOKOLL.md`, `fehlerfaelle/protokoll.log`
| # | Fehlerfall | ROT (rc ≠ 0 gefordert) | GRÜN (rc 0 gefordert) | Beleg |
|---|---|---|---|---|
| F1 | Ausnahme im Kernpfad | v1-Paket: kein `diagnose()`, Rückgabe 0,5 statt BB → 3/3 Tests scheitern | injizierte Ausnahme ⇒ p = (α+2)/(α+β+3) ≠ 0,5, Zähler beta_binomial = 1; `item` kein Dict ⇒ Prior-Mittel α/(α+β) = 0,5187; Kette bis 0,5 bei kaputtem α | `tests/test_haertung.py::TestF1Ausnahme` |
| F2 | Labels "true"/"yes"/"1.0"/None | v1: `float("true")` wirft ⇒ 0,5 ⇒ 2/2 scheitern | 7 Labelformen bitgleich zu bool (assertEqual exakt); None/"n/a"/NaN übersprungen; 0 Fallbacks | `TestF2Labelformen`, `tests/test_label.py` (4 Tests) |
| F3 | Kette stumm (100 % Fallback) | v1: 3/3 scheitern (Zähler fehlen) | 10⁴ wettbewerbsförmige Eingaben: hier = 10 000, BB = 0, Konstante = 0; τ_c² = 0 (gebrochener Zustand): BB = 10 000; zusätzlich β kaputt: Konstante = 1 000, alle 0,5 | `TestF3Fallbackkette` |
| F4 | 8 Threads, gemischte Label-Mengen (4 Mengen, 40 × 31 > VOLL_BIS) | ohne Sperre (+ erzwungene Verschränkung in `_bereite`): **785/1 600 Ausgaben abweichend** | mit Sperre: 0/1 600 abweichend zur sequenziellen Referenz | `TestF4Threads`; v1 hatte die Sperre bereits (SOLL S6), der rote Fall ist die sperrlose Variante |
| F5 | frischer Prozess je Aufruf | leeres Verzeichnis ⇒ fail-closed rc 2 | 20 Prozesse je Größe, v2core: **10⁵ Labels: Import 7,7 ms, Labels laden 0,37 s (Plattformkosten), erster predict 0,31 s, Prozess gesamt 0,86 s; 3·10⁵: 5,9 ms / 1,02 s / 1,14 s / 2,77 s**; zweiter predict im selben Prozess 0,4 ms; Vorhersage über Prozesse deterministisch | `messungen/frischer_prozess.json` |
| F6 | Speicher bei 3·10⁵ Labels | `--limit-mb 1` ⇒ rc 1 | tracemalloc-Spitze Modell **62 MB**, RSS-Zuwachs **54 MB** (< 500 MB); Import 0,35 MB | `messungen/speicher.json` |
| F7 | Platt nicht verschachtelt gewählt | v1 `cv_A/auswertung.json`: Feld fehlt ⇒ rc 1 | verschachtelte Stufenwahl je Falte vorhanden; Zustand trägt Schnittmenge {0, 1} ⇒ rc 0; **7 von 10 Falten weichen von der Gesamtwahl {0,1,3,7} ab** (§4) | `ergebnisse_v2/platt_wahl_F7.json`, `pruefe_platt_wahl.py` |
Lesart F5 (Grenze benannt): Startet die Plattform je `predict` einen neuen Prozess, kostet jeder Aufruf ≈ 0,3 s (10⁵) bzw. ≈ 1,1 s (3·10⁵) nur für die Gruppierung — bei 150 000 Aufrufen je Checkpoint nicht einzuhalten; das träfe jede Einreichung gleich (die Veranstalter-Baseline zählt `labeled` ebenfalls je Aufruf), ist von uns nicht prüfbar (ABSCHLUSS-MODELL §5) und wird im Bericht als Restrisiko genannt. Innerhalb eines Prozesses gilt der O(64)-Schlüsselpfad (0,1–0,4 ms, §3).

## 3. Bitgleichheit zu v1 und Laufzeit (mechanisch)
- **Phase 1 (Design A, S1/S2/S3/S30, Saaten 0–2, 10 Falten), kern-Code gegen v1 `cv_REG1`:** `vergleiche_saetze.py cv_V2K1 cv_REG1` → **1 079 568 von 1 079 568 Sätzen, max |Δq| = 0, max |Δbrier| = 0, n_items_angepasst gleich, alle 10 Faltenzustände kanonisch gleich, rc 0** (`ergebnisse_v2/bitgleich_phase1.json`; je Prädiktor 154 224 Sätze, 0 ungleich: beta_binomial, empirischer_mittelwert, globale_quote, hier, hier_ohne_steigung, hier_ohne_subjekt, konstant_0.5). Das belegt: Label-Parsing (K4b) und alles Übrige in `inferenz.py` sind auf Wettbewerbs-Labels (int 0/1) bitgleich zu v1.
- **Gebautes Paket v2core gegen v1-Paket `paiec_hier.zip`** in frischen Prozessen (`vergleiche_v1_paket.py`, 2 720 Vorhersagen, 40 Benchmarks, S ∈ {1,2,3,5,12}, Budgets 0–31, bekannte/unbekannte/leere Namen): Stufen 0, 1, 15, 31 **max |Δp| = 0** (1 632 Vorhersagen); Stufen 3 und 7 abweichend wie erwartet (544 + 544 Vorhersagen, max |Δp| 0,0237 bzw. 0,0152) — das ist genau der Wegfall der Platt-Stufen 3/7 (§4). `ergebnisse_v2/vergleich_paket_v1_v2core.json`.
- **`paket/pruefe_paket.py ../dist/paiec_v2core.zip --state paket/state_v2core.json` → urteil ok, rc 0** (`ergebnisse_v2/pruefe_paket_v2core.json`): nur Standardbibliothek, keine Dateizugriffe, 296 Vergleiche zum Projektcode max |Δ| 0, Reihenfolge 0, Exaktpfad 0, Lauf 2 108 Labels > VOLL_BIS; Laufzeit 10⁵ Labels: gleiches Objekt Median 0,11 ms (p99 0,41), **frische Kopie je Aufruf Median 0,40 ms (< 2 ms), erster Aufruf 315 ms (< 5 s)**; Hochrechnung 150 000 Aufrufe × 10⁵ Labels (Kopie) ≈ 60 s. Härtung: 1 819 Aufrufe Normalbetrieb ⇒ 0 Fallbacks; kaputter Eintrag ⇒ genau 1 BB-Fallback (p = 0,571).
- Unit-Tests: `tests/test_inferenz.py` 13/13, `tests/test_label.py` 4/4, `tests/test_haertung.py` 9/9 (v2core), 0/8 bzw. 0/1 im roten Lauf (§2).

## 5. Hyperparameter-Klemmen (K4g, dokumentiert; Quelle `training.fit_hyper`, Zustände `cv_V2K1/state_f*.json` = `cv_REG1`)
`fit_hyper` optimiert (μ_c, λ, log τ_c², log τ_λ², log τ_v², log κ, log s²_unk) mit Nelder-Mead; die Log-Parameter sind auf [−12, 6] geklemmt (`exp()` nie 0/∞; eingeführt nach Absturz Falte 8, 2026-10-20), d. h. Wertebereich [6,1e−6, 403].
| Falte (Design A) | τ_λ² | κ | geklemmt |
|---|---:|---:|---|
| 0 | 0,0650 | 0,855 | — |
| 1 | 0,5711 | 7,093 | — |
| 2 | 0,3091 | 4,028 | — |
| 3 | 0,4443 | 7,261 | — |
| 4 | 0,2684 | 3,662 | — |
| 5 | 0,2203 | 2,689 | — |
| 6 | **6,1e−6** | 1,684 | **τ_λ² an der unteren Klemme** (Steigungsvarianz ≈ 0: alle Benchmarks der Falte teilen λ) |
| 7 | 0,3285 | 1,876 | — |
| 8 | **6,1e−6** | 1,690 | **τ_λ² an der unteren Klemme** |
| 9 | 0,3089 | 0,304 | — |
| Paket (156 Benchmarks) | 0,1635 | 3,217 | — |
Lesart: τ_λ² ist über Falten instabil (6e−6 … 0,57) und in 2/10 Falten an der Klemme; κ streut 0,30 … 7,26 (MODELL §12.3). Die Marginal-Likelihood ist in diesen Richtungen flach; die Vorhersage reagiert darauf schwach (hier − hier_ohne_steigung S3: −3e−5 ± 3e−5, `auswertung_V2K1.json`). Ablation „fest auf Median über Falten" ist nicht gerechnet (nicht P1-Test); sie wäre mit `kreuzvalidierung.py` Phase 1 und festem `hyp` ≈ 3 min Rechenzeit und gehört zu P4/P8, falls gewünscht.

## 6. Schnittstelle, Regeln, Platte
`predict([subject, item], labeled) -> float` unverändert; Standardbibliothek (`json`, `math`, `hashlib`, `re`, `threading`), kein Netz, keine Dateien, kein `labeling.py`, kein `models.txt`/`requirements.txt`; Zustand eingebettet (JSON-Text). Rückgabe immer `float`, endlich, in [1e−4, 1−1e−4]; `predict` wirft nie (Fehlercode 40 ausgeschlossen; 42 ausgeschlossen durch Klemmung). ZIP 31 888 Bytes (model.py 74 KB + README). Nichts hochgeladen; kein HF-Token benutzt (P1 braucht keine Daten außer dem lokalen `PAIEC_WORK`). Platte: `./` ≈ 2 MB + CV-Ordner im Scratch (cv_V2K1 13 MB, cv_V2K2 ≈ 12 MB) ≪ 1,5 GB.

## 4. F7-Ergebnis und Phase 2 (Stand 20:28Z)
Verschachtelte Stufenwahl je Falte (S3, `auswertung_V2K1.json` → `platt_stufenwahl_verschachtelt`): F0 {0,1,3,7,15}, F1 {0,1,3},
F2 {0,1,3}, F3 {0,1,3,7}, F4 {0,1,3,7}, F5 {0,1,7}, F6 {0,1,3,7,15,31}, F7 {0,1,3,7}, F8 {0,1,7}, F9 {0,1,3}. Stufen 0 und 1 in
10/10 Falten (innerer Gewinn 0,0037–0,0057 bzw. 0,0007–0,0014), Stufe 3 in 8/10, Stufe 7 in 7/10 (Gewinne ±1e-4, Rauschen).
v1-Gesamtwahl {0,1,3,7}; Mehrheitsregel ergäbe {0,1,3,7}; **Schnittregel (§0, vorab) ⇒ Paket {0,1}** — angewendet, nicht
nachjustiert. Wirkung (Phase-1-Sätze, `ergebnisse_v2/platt_varianten_V2K1.json`, Paar-ALC {0,1} − v1): S1 +7,8e-5 ± 1,0e-4,
S2 +3,1e-5 ± 8,0e-5, S3 +7,6e-6 ± 6,8e-5, S30 −5,6e-5 ± 3,3e-5 — nirgends ein Unterschied belegt; die Stufenwahl ist eine
Verfahrensfrage, kein Score-Hebel.
**Phase 2 (`cv_V2K2`, je Falte verschachtelte Stufenmenge, Regime S1/S2/S3/S30/kompakt10) lief bei Abgabe dieses Standes noch
(6/10 Falten, CPU durch Nachbarstränge geteilt, Lastmittel 12 auf 4 Kernen).** Offener Schritt (zwei Befehle, kern/):
`python3 -I auswertung.py --design V2K2 --phase 2` und
`python3 -I vergleiche_saetze.py cv_V2K2 cv_REG2 --erlaubt hier_kal,hier_item,hier_item_t05,hier_item_t2 --aus ergebnisse_v2/bitgleich_phase2.json`.
Erwartung (vorab): konstant_0.5/empirischer_mittelwert/beta_binomial bitgleich (max |Δq| = 0); hier_kal/hier_item nur in
Falten/Stufen abweichend, deren verschachtelte Stufenmenge ≠ {0,1,3,7} ist (F0, F1, F2, F5, F6, F8, F9). Trifft die Erwartung
nicht ein, gilt P1 als NICHT fertig (Rückgabecode ≠ 0 des Vergleichs).

**Ergebnis Phase 2 (2026-10-21, Lauf `cv_V2K2` beendet 20:31:00Z mit 10/10 Falten, `status.json` fertig=10; beide Befehle
06:35Z, rc 0; Logs `logs/auswertung_V2K2.log`, `logs/bitgleich_phase2.log`):** Erwartung EINGETROFFEN.
- `vergleiche_saetze.py` (`ergebnisse_v2/bitgleich_phase2.json`, 1 214 136 Sätze, rc 0): konstant_0.5, empirischer_mittelwert,
  beta_binomial max |Δq| = 0 (0 ungleiche Zeilen); hier_kal/hier_item/_t05/_t2 je 24 504 von 173 448 Zeilen ungleich,
  max |Δq| = 0,0246 (F8), max |Δbrier| = 0,0264. Je Falte max |Δq| = 0 genau in F3, F4, F7 (verschachtelte Menge = {0,1,3,7});
  ≠ 0 genau in F0, F1, F2, F5, F6, F8, F9 — exakt die vorab genannten Falten. `max_dq_ohne_erlaubte` = 0 in 10/10 Falten.
- Zusätzliche Stufen-Ebene (nicht vorab als Befehl festgelegt, aber Teil der Erwartung „Falten/Stufen";
  `ergebnisse_v2/bitgleich_phase2_stufen.json`, `logs/bitgleich_phase2_stufen.log`, rc 0; Stufe = `inferenz.stufe(n_eigen)`):
  hier_* weicht je Falte NUR in den Stufen ab, in denen verschachtelte Menge und {0,1,3,7} sich unterscheiden —
  F0 {15}, F1 {7}, F2 {7}, F5 {3}, F6 {15, 31}, F8 {3}, F9 {7}; F3/F4/F7 keine; Baselines je Falte max |Δq| = 0.
- Wirkung auf die Phase-2-Zahlen (Paar-ALC, `tabelle_alle`, V2K2 − v1 `cv_A_p2_…kompakt10`): hier_kal/hier_item +7e-5 (S1),
  +6e-5 (S2), +4e-5/+5e-5 (S3), +2e-5 (S30, kompakt10); beta_binomial 0 in allen Regimen. Richtung: v2-Zahlen minimal
  schlechter (verschachtelte Wahl entfernt den leichten Optimismus der gepoolten v1-Stufenwahl); Größenordnung ≪ 1 SE (S3 SE
  ≈ 7e-4). Alle Paarvergleiche hier vs. Baselines behalten ihr Urteil (`logs/auswertung_V2K2.log`).
- Testsuite nach Neustart: `python3 -I -m unittest discover -s tests -t .` 26 Tests OK (`logs/tests_abschluss.log`);
  `sha256sum -c SHA256SUMS` OK (paiec_v2core.zip 7883867c…e012 unverändert).
**Folge (Annahme-Regel §0/STATUS): Phase-2-Beleg erbracht ⇒ `./dist/paiec_v2core.zip` ist v2.0-core (Paketkandidat);
`modell/dist/paiec_hier.zip` bleibt unangetastet als Rückfall.** Hinweis für den Bericht: die im Bericht zu nennenden
CV-Zahlen des Pakets sind die von `cv_V2K2` (`ergebnisse_v2/auswertung_V2K2.json`), nicht die v1-Zahlen; die
Platt-Stufen des Pakets sind {0,1} (Schnittregel), die CV-Zahlen nutzen je Falte die verschachtelte Menge — das ist die
ehrliche (leicht pessimistische) Schätzung für das Paket, kein exakter Paket-Nachlauf [belegt: Differenz ≤ 7e-5].
Kehrseite: falsch, wenn `vergleiche_saetze.py` selbst fehlerhaft wäre — gegengeprüft nur durch die unabhängige Stufen-Ebene
oben (eigener Merge über alle Schlüsselspalten, Zeilenzahl geprüft), nicht durch einen zweiten Prüfer.

## 7. Kehrseite (unter welcher Bedingung ist v2.0-core die falsche Wahl?)
- Falsch, wenn die Plattform Labels nie als Text liefert und nie Ausnahmen im Kernpfad auftreten: dann ist die Härtung wertlos
  (Erwartungswert 0) und der einzige Unterschied zu v1 ist der Wegfall der Platt-Stufen 3/7 — ein Nulleffekt (S3 +8e-6 ± 7e-5),
  der aber Konfirmationslauf P4 für v2core statt v1 nötig macht (Regel R1).
- Falsch, wenn die Beta-Binomial-Rückfallstufe systematisch greift (Zähler > 0 auf der Plattform, lokal 0/11 819): dann sähe
  der Score wie „nur BB" aus, ohne dass man es von außen sieht — nur der Codabench-Smoke (P14) und die lokalen Zähler prüfen das.
- Falsch, wenn die Schnittregel zu konservativ war: eine Mehrheitsregel hätte {0,1,3,7} behalten (= v1-Zahlen); der Unterschied
  ist unter jeder Entscheidungsschwelle, aber die CV-Zahlen der Phase 2 ändern sich in 7 Falten um ~1e-5.
- Falsch, wenn die Plattform je Aufruf einen neuen Prozess startet (F5: 0,3–1,1 s je Aufruf) — nicht prüfbar, trifft alle gleich.
