# P5 — Akquise-Simulator und Politikvergleich (Befund für Bericht §6.8, Anhang A/D)

Angelegt: 2026-10-20 . Entstanden mit KI-Codierunterstützung; alleiniger
Wettbewerbsautor: Christian Bucher. Paketmodell in dieser Messung: **v1** (`modell/`, hier_item = Paar-Posterior + Item-Stufe +
verschachtelte Platt-Stufen 0/1/3/7), weil P1 (v2.0-core) beim Start nicht fertig war; v2.0-core ist laut P1 bitgleich in
Phase 1, der Wechsel ist ein Pfadparameter (`PAIEC_MODELL`). **Kein `labeling.py` im Paket** (BAUPLAN-V2 §2.2 P5, Gate §1.3 Nr. 11).
Kennzeichnung: [belegt] = Datei; [A] = Annahme des Simulators; [Vermutung].

## 1. Was gemessen wird
Frage: Kann eine Kaufregel (`labeling.py`-Schnittstelle: Kandidaten einzeln in fester Zufallsreihenfolge, `True` kauft,
`False` überspringt endgültig) den Brier-ALC des Paketmodells senken — und unter welchen Protokollbedingungen?
Referenz ist die **exakte Replik der Plattform-Zufallsregel** (`streaming_ingestion.py`, Zweig `hook.mode == "random"`:
`u = sha256(json.dumps([context, input], sort_keys, separators))[:8]/2^64`, kaufen ⇔ `u < min(1, labels_remaining/items_remaining)`).
Alle Politiken ziehen dieselbe Uniforme; Antworten je Item sind feste Zufallszahlen (gemeinsame Zufallszahlen) ⇒ die
gepaarte Paar-Differenz misst nur die Wirkung der Auswahl.

### 1.1 Rang-Gewicht (eigene Rechnung, metrik.GEWICHTE)
Das j-te gekaufte Label liegt in allen Budgets B ≥ j: W(j) = Σ_{B≥j} w_B = 0,9 (j=1) · 0,7 (2–3) · 0,5 (4–7) · 0,3 (8–15) · 0,1 (16–31);
Σ W = 8,3; Labels 1–7 tragen 52 %, 16–31 nur 19 %. Zwangskäufe am Stromende sind fast kostenlos.

### 1.2 Lemmata (D-akquise §2.1; Prüfung mechanisch)
- **Lemma 1 (Rückfall auf Zufall).** Ohne Fremdlabels im Benchmark (S1; erstes Paar bei paarweiser Ordnung) sind alle
  Kandidaten austauschbar; `abdeckung`, `leicht_zuerst`, `information_naiv` sind dann **bit-identisch** zur Replik
  (Test H4: 15 000 Kandidaten, 0 Abweichungen; im Volllauf S1: Zähler je Lauf in `tabelle_politiken.json → zaehler`).
- **Lemma 2 (Ignorierbarkeit, Rubin 1976 — Zitat erst nach Crossref-Prüfung, P2/P10).** Hängt die Kaufentscheidung nur
  von Größen ab, die bedingt auf den Pool vom eigenen Ergebnis unabhängig sind (Fremdlabel vorhanden ja/nein, `context`,
  Uniforme, **eigene bisherige Labels**), bleibt die gekaufte Menge eine ergebnisunabhängige Teilmenge → (k, n)-Likelihood
  der Paarrate unverzerrt. Folge, vorab notiert: Unsicherheits-Sampling mit **paar-konstanter** Vorhersage (Empirical Mean)
  ist ignorierbar (nur Stoppregel, kein Item-Bezug) — die Veranstalter-Warnung trifft erst, wenn die Vorhersage je Item
  variiert (BLE-Modell, unsere Item-Stufe). Auswahl nach Fremdlabel-**Werten** (leicht_zuerst, information_naiv) verletzt
  Lemma 2 → Verzerrung, solange die Likelihood nicht auf die Schwierigkeit bedingt.

## 2. Simulator (eigener Code, `simulator_strom.py`; Annahmen [A])
| Element | Umsetzung | Status |
|---|---|---|
| Paare, Split 50/50 je Paar, Saat | wie v1 `simulator._paar` (gleiche Permutation) | [belegt: Wortlaut Z. 400] |
| Split je Item (Szenario) | sha-Bit je (Saat, Benchmark, Item), für alle Subjekte gleich → ρ = 0 | [A], Protokoll offen |
| Kandidatenstrom | Permutation der Akquise-Hälfte, **Kappe 200** je Paar; `context` wie Plattform | [A] Pool-Größe unbekannt |
| Antworten | eine feste Uniforme je Item, y = u < k/n (gemeinsame Zufallszahlen) | — |
| Koordinator-Ordnung | `paar` (Paar 1 komplett, dann Paar 2 …), `rr` (Round-Robin), `zufall` (verschränkt) | [A] Plattform unbekannt |
| `labeled` beim Kauf | alle bisher gekauften Labels aller Paare des Laufs, Kaufreihenfolge | [belegt: `labeled = event["labeled"]`] |
| Bewertung je Budget | erste B Käufe je Paar (verschachtelt), Brier itemgenau wie v1 `bewerte_lauf` | wie v1 [A] |
| Leck-Wächter F6 | `len(labeled) == Käufe` vor jeder Entscheidung; `--leck` → `LeckFehler` | ausgelöst (Test) |
| Fallback F5 | jede Ausnahme in einer Politik → Replik, Zähler | ausgelöst (Test) |
| Typprüfung F3 | Replik von `AcquisitionHook.__call__` (`type(result) is not bool`) | ausgelöst (Test) |

Zustände/Falten/Testpaare: identisch zu v1 cv_REG2 (10 Falten, `faltenzuteilung` Saat 1234, Kappe 30 Paare je Benchmark,
`cv_REG1/state_f*.json` + verschachtelte Platt-Parameter). Regime: S1, S3, S30 (alle Items), kompakt10 (10 Subjekte,
100 gemeinsame Items; Pools ≈ 50). Saaten 0–2 (Regel aus Pilot, §4).

## 3. Politiken (`politiken.py`, nur Standardbibliothek)
| Politik | Regel | Zweck |
|---|---|---|
| zufall | Plattform-Replik | Referenz |
| abdeckung (Stufe 1) | Kandidaten ohne Fremdlabel bevorzugen; zweistufige budgettreue Regel mit f̂ = (frei gesehen + 1)/(gesehen + 1); ohne Fremdlabels exakt Replik | Kandidat (D §2.2) |
| unsicherheit_0.15 | BLE-Regel: Zwangskauf oder \|p − 0,5\| ≤ 0,15 mit **Itemvorhersage des Paketmodells** | Veranstalter-Politik, F1-Mechanismus mit Item-Variation |
| unsicherheit_em | dieselbe Regel mit Empirical-Mean-Vorhersage (0,5 ohne eigene Labels) | Veranstalter-Baseline-Paar; Lemma-2-Vorhersage: ≈ 0 |
| information_naiv | Items mit Fremdlabels bevorzugen, deren σ(b̂ + d̂_i) nahe 0,5 (b̂ aus eigenen, d̂ aus Fremdlabels), **ohne** bedingte Likelihood | Fehlerfall F2 (muss schaden) |
| leicht_zuerst | Items bevorzugen, deren Fremdlabels alle 1 sind | Verzerrungs-Demonstration (muss schaden) |
| orakel_d | bekannte LOO-Schwierigkeit d_i (alle Subjekte der Datenbank), b̂ Laplace-Modus; kaufen, wenn \|b̂ + d_i\| unter den k kleinsten der verbleibenden Pool-Items | Obergrenze eigener Hebel **im Strom** (ohne Rückgriff), Gegenstück zu C §3.3 (mit Rückgriff) |

Bewertungs-Prädiktoren: hier_item (Paket), empirischer_mittelwert, beta_binomial, orakel_d-Prädiktor (b ~ N(μ_c, τ_c² + s²_unk),
Likelihood σ(b + d_i), Vorhersage probit-korrigiert; nur für zufall/orakel_d).

## 4. Pilot und Betriebskennlinie (vor dem Volllauf; `kennlinie.json`)
Siehe `kennlinie.json`. Regel vorab (D §6.2): MDE kompakt10 > 0,0025 → 5 Saaten. Ergebnis: MDE 0,00034 (projiziert; aus nur
5 Clustern, daher selbst unsicher) → **3 Saaten**. P(fälschlich „besser" | Nulleffekt) = 1 − Φ(2) = 2,3 % je Zelle.

## 5. Ergebnisse
(wird nach dem Volllauf aus `tabelle_politiken.json` eingetragen — nicht vorher)

## 6. Kehrseite
(wird mit den Ergebnissen eingetragen)
