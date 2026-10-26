# L9-Abgleich: 0,0065 (C-FEHLERANALYSE Z. 133/173) gegen 0,0229 (wiederholung.json `orakel_kn_alle_zellen`)

Angelegt 2026-10-20T20:42Z (P8, BAUPLAN-V2 §1.3 Nr. 8). Werkzeug-Output für Christian Bucher. Quelle aller Zahlen:
`curation/wiederholung_b.json` (zweiter Rechenweg, pandas-only, Roh-Antworten) und, zum Vergleich,
`v2-plan/d-wissenschaft/wiederholung.json` (Erstweg), `v2-plan/c-fehleranalyse/leiter.py` Z. 36–38, 114, 257.

## 1. Ergebnis in einem Satz
**Beide Zahlen sind dasselbe Maß — das k/n-Orakel k(n−k)/n je Zelle (Subjekt, Item), antwortgewichtet innerhalb der Einheit —
auf verschiedenen Populationen mit verschiedener Gewichtung:** 0,0065 ist das Mittel über 2 142 Testpaare (jedes Paar gleich
gewichtet, wie die Wettbewerbsmetrik; nur Bewertungs-Items), 0,0229 ist das Mittel über alle 68,3 M Antworten der 156
Trainingsbenchmarks (jede Antwort gleich gewichtet; monkey_power_laws allein stellt 42 % dieser Antworten). Kein Widerspruch,
aber zwei verschiedene Fragen. Keine der beiden ist L10.

## 2. Definitionen (je Zahl)
| Zahl | Formel | Einheit der Mittelung | Population | Quelle / Reproduktion |
|---|---|---|---|---|
| **L9 = 0,0065** | je Paar: Σ_i k_i(n_i−k_i)/n_i / Σ_i n_i über die Bewertungs-Items i des Paares (`brier_items(k/n, n, k)`), dann Mittel über Paare × Saaten | **Paar** (2 142 Testpaare nach 30er-Kappung, 3 Saaten) | Testpaare ≥ 80 Items, nur Bewertungs-Hälfte | `leiter.py` Z. 114/257 → `leiter.md` „L9 … 0.00652"; Zweitweg (alle Items statt Bewertungs-Hälfte): **0,00649** (`wiederholung_b.json → l9_abgleich.kn_paargewichtet_testpaare_alle_items`) |
| **0,0229** | Σ_Zellen k(n−k)/n / Σ_Zellen n | **Antwort** | alle 31 389 917 Zellen der 156 Benchmarks (68 268 267 Antworten) | `wiederholung.py` Z. 17–18; Zweitweg identisch **0,022928** |
| L10 = 0,0444 | Σ n·k(n−k)/(n(n−1)) / Σ n, nur Zellen mit n ≥ 2 (unverzerrt für p(1−p)) | Antwort | 3 144 967 Wdh-Zellen (10,0 % der Zellen, 58,6 % der Antworten) | `wiederholung.json`/`wiederholung_b.json` `schranke_antwortgewichtet_nur_wdh` |
| L10 Median je Bm = 0,0488 (IQR 0,0106–0,0881) | wie L10, je Benchmark, dann Quantile | Benchmark | 62 Benchmarks mit ≥ 100 Wdh-Zellen | dto. `schranke_je_bm_quantile` |

## 3. Zerlegung des Unterschieds (dieselbe Formel k(n−k)/n, nur Population/Gewichtung variiert; Zweitweg)
| Schritt | Wert | Was sich ändert |
|---|---:|---|
| k/n-Orakel, antwortgewichtet, alle 156 Benchmarks | **0,02293** | = wiederholung.json |
| … ohne monkey_power_laws (28,8 M Antworten, max_trial 10 000) | 0,01402 | ein Benchmark trägt 39 % der Zahl |
| … nur Paare ≥ 80 Items (12 918 Paare, 142 Bm), antwortgewichtet | 0,02291 | Paar-Auswahl ändert fast nichts |
| … dieselben 12 918 Paare, **paargewichtet** | 0,00382 | Gewichtung je Paar statt je Antwort: Faktor 6 |
| … nur die 2 142 Testpaare (Kappung 30/Bm), paargewichtet, alle Items | **0,00649** | Kappung hebt kleine Benchmarks an (alignment_faking 4 278 → 30 Paare) |
| … Testpaare, antwortgewichtet | 0,02766 | zum Vergleich: dieselben Paare, andere Gewichtung |
| C-Fassung: Testpaare, paargewichtet, nur Bewertungs-Items, 3 Saaten | 0,00652 | Bewertungs-Hälfte vs alle Items: Δ 0,00003 |
| **L10** (unverzerrt, nur n ≥ 2), paargewichtet über die 813 Testpaare mit Wdh-Zellen | 0,03775 | zeigt, wie stark n = 1 → 0 die k/n-Zahl nach unten zieht |

Lesart: Der Faktor 3,5 zwischen 0,0229 und 0,0065 entsteht aus der Gewichtung: Antwort- statt Paargewichtung allein macht
Faktor 6 (0,0229 → 0,0038), weil Benchmarks mit vielen Trials — monkey_power_laws, bridging_gap, adaptivestep mit n = 256 je Zelle —
die Antwortgewichtung dominieren, aber nur wenige Paare stellen; die 30er-Kappung je Benchmark hebt den paargewichteten Wert
wieder um Faktor 1,7 an (0,0038 → 0,0065), weil sie die vielen Paare von alignment_faking (4 278) und sib200 (3 341) — beide
mit sehr wenig Wiederholung — auf 30 kürzt. Beide Zahlen enthalten die Verzerrung
k(n−k)/n → 0 für n = 1 (90 % der Zellen): sie sind **keine** Schranke für irgendetwas, sondern beschreiben, wie viel
Wiederholungsvarianz in der jeweiligen Stichprobe *sichtbar* ist.

## 4. Was im Bericht steht (Empfehlung an P2/P10)
1. In der Schranken-Leiter (§3.3, Anhang A) **L9 streichen oder als „k/n-Orakel, verzerrt (n = 1 → 0), paargewichtet auf
   Testpaaren: 0,0065" ausweisen** — nie als „irreduzibel". Die irreduzible Schranke ist L10 (nur n ≥ 2, unverzerrt), und sie
   gilt auf der Teilmenge mit Wiederholungen: antwortgewichtet 0,044, Median je Benchmark 0,049 (IQR 0,011–0,088, 62 Bm).
2. Wird in der Varianzzerlegung (C §2.1, „darin Wiederholungsrauschen 0,0065, 2,6 %") eine paargewichtete Zahl gebraucht, ist die
   ehrliche Angabe: „k/n-Orakel 0,0065 (Untergrenze, da 90 % der Zellen nur eine Antwort tragen); unverzerrte Schranke auf den
   813 von 2 142 Testpaaren mit Wiederholungen 0,038."
3. `pruefe_zahlen.py` (P10) prüft Anhang↔Anhang: 0,0065 darf nur neben dem Wort „k/n-Orakel" bzw. „verzerrt" stehen; 0,0229 nur mit
   „antwortgewichtet, alle Zellen"; 0,044/0,049 nur mit „n ≥ 2" bzw. „Median je Benchmark".

## 5. Zwei Rechenwege L10 (Fertig-Kriterium „innerhalb 1 %")
| Größe | Weg A (numpy, agg.parquet) | Weg B (pandas, Roh-Antworten, var ddof = 1) | rel. Abw. |
|---|---:|---:|---:|
| Zellen / Antworten / Wdh-Zellen | 31 389 917 / 68 268 267 / 3 144 967 | identisch | 0 |
| L10 antwortgewichtet | 0,044385 | 0,044385 | 1,6e−16 |
| L10 zellgewichtet | 0,067141 | 0,067141 | 4,1e−16 |
| k/n-Orakel alle Zellen | 0,022928 | 0,022928 | 0 |
| Median / Q25 / Q75 je Bm (62 Bm) | 0,048821 / 0,010642 / 0,088086 | identisch | 0 |
| bm-balanciertes Mittel | 0,054183 | 0,054183 | 0 |
Rückgabecode `wiederholung_b.py`: 0 (Toleranz 1 %; Kontrollsummen gleich). Laufzeit 35 s, 1 Thread.

## 6. Kehrseite (unter welcher Bedingung ist dieser Abgleich falsch?)
Wenn der Erstweg und der Zweitweg denselben Auswahlfehler teilen (gleiche Ausschlusslisten F3/F4, gleiche Benchmark-Auswahl
binär+public+coverage > 0), bestätigt die Übereinstimmung nur die Rechnung, nicht die Population — dafür stehen die Kontrollsummen
gegen `daten_zusammenfassung.json` (31 389 917 / 68 268 267). Und: L10 ist eine Schranke **nur auf den 10 % der Zellen mit
Wiederholungen**; in den Benchmarks ohne Trials (bbq, mmlu, perumedqa haben Zellen mit n = 2 und Rauschen 0 — vermutlich greedy
dekodiert) kann das wahre irreduzible Rauschen anders liegen. Der Bericht darf L10 daher nur als „subset bound" führen.
