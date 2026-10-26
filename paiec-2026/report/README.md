# report/

`paiec_report_v2.pdf`: the technical report (CC BY 4.0, `LICENSE-CC-BY-4.0`). `src/`: its LaTeX source (`paiec_report_v2.tex`,
`refs.bib`, `neurips_2026.sty`), generated tables (`tabellen/`, from `tabellen_v2.py`), figures (`abbildungen/`, from `plots_v2.py`),
the small data files they read (`daten/`, provenance in `daten/HERKUNFT.md`; `daten/hyperparameter_je_falte_roh.json` holds the full-precision fold hyperparameters behind Table 7),
`analyse/` (the discovery scripts behind path A of Table 9, see `analyse/README.md`), `ZAHLEN-QUELLEN-v2.md` (every number of the report -> file/field),
`baue_refs.py` (bibliography table) and `pruefe_zahlen.py` (fail-closed number check, run before every PDF build).

Rebuild tables and figures from the repository root: `make report-tabs`, `make report-figs` (needs numpy, matplotlib). Checked on a fresh clone:
the regenerated tables are byte-identical to the committed ones; the regenerated figure PDFs differ only in embedded metadata (matplotlib creation
date), so `make hash-check` reports them afterwards (`git checkout -- report/src/abbildungen` restores the committed files). `pruefe_zahlen.py` and
`src/Makefile` target `pdf` additionally read files of the author's working tree that are not part of this repository (the data-quality report
with record excerpts, the pre-registration hash file, the submitted package `paiec_v2core_final.zip` at its working-tree path); they are
included for inspection. The PDF was built from this source on 2026-10-26 (25 pages; main text 7.48 pages by the marker the check script reads; the script also checks the PDF text for German words and clock times, the cited paths, the table cells against their sources and every sentence with an all-word). Without the local data base (`PAIEC_WORK`: fold states, `paare.parquet`) the check script returns 1 unless `--ohne-zustand` is given explicitly (`make pdf PRUEF=--ohne-zustand`).
The code in the rest of the repository is MIT (`../LICENSE`).
