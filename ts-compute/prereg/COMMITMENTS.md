# Hash commitments (public timestamps before blind tests)

Each line commits to a file by its SHA-256 without publishing its content yet.
The files will be published later; anyone can then check that they are
unchanged since the time of this commit. Purpose: show that predictions and
candidate lists were fixed before the data that tests them became available.

## W3 — gray secular fading of Sun-like stars, Hipparcos 1991 → Gaia 2016

Blind test: Gaia DR4 (archive opens 2026-12-02). Predictions resolve 2026-12-31.

| SHA-256 | File | Content |
|---|---|---|
| `18e7712493f418617411c66bc8d11bc9073596f018d9b42355bbcb44f0a6e3d9` | `PRAEREG-W3.md` (part before `## Einfrieren`) | Preregistration, frozen 2026-10-12 22:28 UTC |
| `42950578d1f28524c21c7e5e8a92b8a5df5c56843ddabce2146eb237a26a3078` | `KANDIDATEN-W3.csv` | Candidate list with DR4 predictions |
| `151ad8927e1b05417b2b8c1ab355a36c2559a36b2fb940f13b0ffb5016b65e81` | `SPIEGEL-W3.csv` | Mirror sample (brightening stars), null reference for DR4 |
| `404f9144aa5eb0c4481f3717ae62a605e70c0b87ddaed58b2dc0aa3f43e6a0b8` | `INJEKTION-W3.csv` | Injection-recovery table behind the rate limit |
| `3843f8ca2f21ff707c61b8c67498fe136fa12baddffa8c5d4cc111d96c1e164a` | `PRAEREG-W3.md` (whole file incl. addendum 5, 2026-10-13 00:06 UTC) | Added DR4 tests fixed before release: color slope Δ(BP−RP)/ΔG and 1–30 d periodogram per candidate |

A candidate on this list is a star whose brightness changed more than the
measurement model expects. It is not a claim of anything artificial; natural
explanations are open until tested.

## W1 — laser-line search in DESI DR1 stellar spectra

Rules were tuned only on 30 tuning tiles; the pilot gate was measured blind on
60 test tiles (false-alarm rate 40 / 72,574 = 5.5e-4 per spectrum, gate 1e-3).
Rule version v2 below adds two vetoes found after the gate measurement; its
first blind test is wave 1 (all DESI DR1 main/bright stars), started with this
commit. The job file `jobs/current.json` in this commit embeds the full rules.

| SHA-256 | File | Content |
|---|---|---|
| `fdcb015efc4fb2b5c6b44d8f8182cecc3d87ec0e82de30e3815200eb090b38e8` | `rules_frozen_v1.json` | Rules frozen 2026-10-13 00:22:40 UTC before the test tiles were evaluated |
| `30f7c6d9c14d91499924ce32a464b8e2e034f131f9d9daf51e6892e0a8ba78a8` | `rules_v2.json` | v2 = v1 + point-source cut + single-exposure mask veto (fixed 2026-10-13T01:44 UTC, before wave 1) |
| `392bc0c51de81943fb0e3a47862b6345655d279fd923960d68f0b9e819190013` | `ts-compute/jobs/current.json` | Wave-1 job configuration with embedded rules |

Survivors of the search are candidates for further vetting, not detections.

## L1 — Earth-shadow test of POSS-I transients (within-plate, preregistered)

Frozen preregistration (v1.0, 2026-10-13T01:49:05Z), committed before any
transient count on a plate with Earth shadow was computed. The file includes
the SHA-256 of the analysis code (`978dd630fd67ba8f70773bd531dff931dfbc1b0e0d4ea800f8b86da672c8c40f`)
and of 28 input files; the unblinding script refuses to run if any differs.

| SHA-256 | File | Content |
|---|---|---|
| `206390d0ee4b53a3e3fc72bce67bee3d3acab67a636971a703381c4a8c60405a` | `analysis/L1-poss-shadow/PRAEREG.md` | Frozen preregistration v1.0 (private repo commit e2501bf) |

Declared in advance: the only claim this test can refute with probability ≥ 0.5
if there is no effect is the 20,000–25,000 km shell claim; no claim can be
supported with probability ≥ 0.5.
