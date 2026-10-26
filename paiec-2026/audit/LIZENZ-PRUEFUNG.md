# Licence check of the audit lists

Scope: what in `audit/` may be published, and why. Reviewed by the author (not by a lawyer).

Derived from: measurement-db revision `54074453da7b9911be0f48e4c560be547bc84d21` (gated dataset; each benchmark keeps its own upstream terms).

Included (identifiers, hashes, counts, model/benchmark names, short categorical labels):

| File | Data rows |
|---|---:|
| `F1_baseline_payload_coverage.csv` | 280 |
| `F3a_bird_sql_configurations.csv` | 120 |
| `F4_swebench_live_subjects.csv` | 65 |
| `F5a_ikp_merged_configurations.csv` | 30 |
| `F5b_reasoning_setting_only_in_label.csv` | 218 |
| `F6_icpc2_gpt4o_trials.csv` | 435 |
| `F7a_winogrande_collapsed_pairs_bridging_gap.csv` | 172 |
| `F7b_winogrande_collapsed_pairs_helm_afr.csv` | 92 |
| `F8_identical_input_subject_groups.csv` | 119 |
| `F9a_public_folders_outside_card_checkpoint.csv` | 26 |
| `F9c_stale_data_manifests.csv` | 126 |
| `F9d_benchmark_inventory_match.csv` | 277 |
| `F9e_test_condition_by_benchmark.csv` | 175 |
| `F9f_harness_spelling_variants.csv` | 14 |
| `F9g_cross_benchmark_shared_items.csv` | 45 |

Excluded:
- `F3b` (question and SQL text), `F9b` (licence and hold texts): contain upstream text excerpts under their own terms.
- `F2` (archive finding) and one benchmark-folder row from F1, F9c, F9d, F9e: left out of the public repository.
- The narrative report and the analysis scripts: not part of this release.

Residual risk: benchmark and model names, `F7*` item identifiers and `upstream_qids` are identifiers of third-party datasets. Short free-text
cells such as `note` (F1) and `harness_value` (F9f) were not individually reviewed for upstream terms [Vermutung: harmless]. This is
not legal advice; if a rights holder objects, remove the file.
