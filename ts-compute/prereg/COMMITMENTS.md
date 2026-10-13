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
| `64ee8ab88dc283e5189cad29c1105a8e2ebee7f9c7a84c4093b76c309dcf70b1` | `NACHTRAG-7-XP-VOLL.md` (2026-10-13) | Addendum 7: the preregistered XP method applied to all 9,444 stars with Gaia DR3 XP spectra; candidate classes, limits and DR4 predictions unchanged (committed files regenerated bit-identically) |
| `af137b74b62a388cfea53dba8860f3c486ab45a207be0a05239257fc9aebd124` | `BEOBACHTUNG-XP-W3.csv` | Watch list (not candidates): 22 clean stars with \|z1\| ≥ 4 in XP (9 fading, 13 brightening), fixed before DR4 |

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

**Rules v3 (2026-10-13, after two independent reviews of the pilot).** Review found that the v1/v2 narrowness
veto rejects bright real unresolved lines (60–99 % at S/N ≳ 50) and that the job discarded vetoed rows before
writing them. v3 recalibrates the shape vetoes on real unresolved lines (sky lines in frame files of two tuning
tiles), adds partner-line, meteor, airglow, lamp and extended stellar-line vetoes, and writes every row that fails
only checkable vetoes, so the rules can be re-applied after the run. Wave A (main/bright) starts with this commit;
no wave-1 or wave-A result has been looked at. The final rule freeze follows an adversarial review and precedes
any look at results; any change from the file below will be listed with its reason.

| SHA-256 | File | Content |
|---|---|---|
| `ad7e27a96dceb1de2812f305f4932a360ea742cdb504518522d5197e3de8f151` | `rules_v3.json` | Rules v3 as launched (candidate for final freeze) |
| `99d960dec984a4ed837a6deff6d014248f010dc8e70cf958d66cce2ee55fa593` | `ts-compute/tsjobs/desi_laser.py` | Job code (v3 logic active only for `rules.version >= 3`; v2 output bit-identical) |
| `275898c5b4cde88fc82b242b213fce66eaf195b63ffeca45cf1b3d601e83d63a` | `ts-compute/jobs/current.json` | Wave-A job configuration (main/bright, 50 shards, rules v3 embedded) |

**Final freeze of v3 (2026-10-13T03:34:46Z), after the adversarial review and before any result of run 4 (wave 1)
or run 5 (wave A) was looked at.** The vetoes are unchanged (`rules_v3.json` as above). The freeze adds evaluation
rules: CHI2PIX must have been computed for a clean survivor; two development tiles are excluded like pilot tiles;
three pre-declared null tests (camera mix of survivors versus sky-fibre survivors and injections, which estimates the
fraction of real lines; clustering per tile; a two-stage ranking). The false-alarm gate is expected to pass and says
nothing about the purity of the list.

| SHA-256 | File | Content |
|---|---|---|
| `861ae3aa573e9b318a07fe7a9b1fcae16b98f8b725b06e1b3dcdaba230f607c7` | `EINFRIEREN-V3.md` | Freeze record: hashes, evaluation addendum v3-A, predictions, known limits |
| `7fb28206a7b592a5e32af527b61814ca120a4264b2be5d5bcd6fb46bf829def7` | `welleA_eval.py` | Evaluation code for v3 runs |

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

**Restart of wave A (2026-10-13, after 03:40 UTC).** In run 4, data.desi.lbl.gov stopped accepting connections from
some runners between about 02:55 and 03:23 UTC (connect timeouts; shards 3 and 27 lost, shard 48 hung). To reduce
load on the DESI server, wave A was cancelled two minutes after it started and restarted with at most 8 parallel
shards (was 20) and 4 download threads per shard (was 6); the two small metadata tables are now read from the
repository, and failed requests are retried up to 8 times with growing pauses. The rules and the analysis code are
unchanged; no result of run 4 beyond its false-alarm count and of run 5 (no output) was used.

| SHA-256 | File | Content |
|---|---|---|
| `8493efd54ebabd9a309e0b52dbd97f84163adf86d6f26be2c4afef7eae0139a4` | `ts-compute/tsjobs/desi_laser.py` | Job code: metadata from `ts-compute/meta/`, retry with backoff (no rule change) |
| `7a9d9250c616bd8adf0cae4c3e8579ad78f1a4a804b9a5df026084dbdbd82a7e` | `ts-compute/jobs/current.json` | Wave-A restart configuration (rules v3 embedded, threads 4) |
| `2039434085b74c26126a01899766a7bc93a739d9e59a4f081645b8337c85a61c` | `ts-compute/meta/tiles-iron.csv` | DESI DR1 tile table (public, copied 2026-10-13 03:40 UTC) |
| `f49d3438f0c44f4f176d8adc35bb566aa45e4615c1410001e2c78cd98ca5e2ab` | `ts-compute/meta/exposures-iron.csv` | DESI DR1 exposure table (public, copied 2026-10-13 03:40 UTC) |

**Stage-B tool frozen (2026-10-13, before any wave-A result was looked at).** Follow-up classification of survivors
(partner lines incl. the [O II] doublet, morphology, neighbouring fibres for bright lines, sky model of the own
exposure). Measured on injections: a real unresolved laser line is wrongly called natural in 0.8 % of cases
(95 %: 0.3–1.8 %); many natural cases stay "open", and "open" does not mean artificial.

| SHA-256 | File | Content |
|---|---|---|
| `88fb37e78233da7b778a2a8372fd609682de4e141ee5840c8864ca02c59ba1da` | `stage_b_v3.py` | Stage-B tool |
| `d10e69762387a5bcae4f0b56ce933b561600be0d14a26c3e849582a19a43b652` | `EINFRIEREN-V3.md` (with addendum 1) | Freeze record incl. stage B |

**Watchdog job code and rerun rule for wave A (fixed before run 6 has ended and before any run-6 result was looked
at).** Several run-6 shards (code `8493efd5…`) hung until the 340-min job limit. The job code below adds a watchdog:
if a process pool or the download threads deliver no result for a fixed time (900 s; 1800 s for the two download
passes), the running tasks are booked as failed (fail-closed: failed petals leave the denominator, candidates
without the single-exposure check count as unchecked), tasks never started are resumed once, and after 100 minutes a
shard starts no further work and writes its outputs. A petal whose measurement raises an exception is now booked as
failed instead of ok. Rules, vetoes and thresholds are unchanged; for runs without errors the outputs are identical
to `8493efd5…` (tested on three pilot tiles).

Rerun rule, applied mechanically after run 6 has ended by `ts-compute/tsjobs/nachlauf.py` (reads only job status and
times and execution metadata, never detections): a run-6 shard is rerun exactly once with the code below if
(J1) its job did not end in success, (J2) its job ran longer than 120 min, (M1) its metadata are missing, (M2) its
metadata report watchdog timeouts or the shard deadline, or (M3) its error list contains at least one exception of
the measurement pass. Ordinary download failures of single petals do not trigger a rerun. A rerun shard replaces the
run-6 shard completely, whatever it contains, and is never mixed petal by petal; there is no second rerun. Timeouts
in a rerun shard stay fail-closed, and the number of candidates left unchecked by timeouts is reported together with
the false-alarm rate. Checkpoint: if shard 29 or 32 ends successfully after more than 120 min, the 120-min limit is
re-examined before wave B.

| SHA-256 | File | Content |
|---|---|---|
| `a15f2fc2455bac6fc36daaef9e8b46eba9b92da28c7a1b8ba863249a6761ae9f` | `ts-compute/tsjobs/desi_laser.py` | Job code with watchdog (rules unchanged) |
| `860271cf1992c309bc474aaf1a3dcd85b158533484e49c28380ff41039c7ce7f` | `ts-compute/tsjobs/nachlauf.py` | Rerun list and one-source-per-shard merge |
| `9a44a0ba23735a30ecadf65ff1f75c85d9738135bfea98c6c2cf76d3aa324059` | `ts-compute/tsjobs/run.py` | Dispatcher (partial shard ends with exit code 3) |
| `522a7e6e7c1d091a7b2ff1e946d766d26d3b99515651cec70777dbf6b4216c35` | `.github/workflows/ts-compute.yml` | Workflow (job limit 120 min, `only_shards`) |
