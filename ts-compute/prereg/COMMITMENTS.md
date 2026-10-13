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
