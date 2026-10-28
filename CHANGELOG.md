# ampfalaeris/envmetag: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0dev - [unreleased<!-- TODO nf-core: replace with date on release -->]

Initial release of ampfalaeris/envmetag, created with the [nf-core](https://nf-co.re/) template.

### `Added`

- Typed entry workflow (`main.nf`) with a typed `params` block, and a typed `ENVMETAG` workflow.
- Read preprocessing (`PREPROCESS_READS`): FastQC (raw/trimmed), fastp, PhiX removal with bowtie2 (ENA J02482.1), host removal with Hostile (`human-t2t-hla-argos985-mycob140`), writing Casava 1.8+ read headers (`--casava`) so mates share a read ID.
- SingleM profiling on fastp-trimmed reads, before PhiX and host removal (`PROFILE_SINGLEM`): `pipe`, `prokaryotic_fraction`, `summarise`, with the GlobDB r232 metapackage via `--singlem_metapackage` or a one-time cached download (`--singlem_db_cache`).
- Workflow `output {}` block with index files for clean reads, SingleM profiles, prokaryotic fraction, and the SingleM summary.
- MultiQC General Statistics columns for the SingleM prokaryotic-fraction estimate (`bin/singlem_fraction_mqc.py`).
- Software versions per process published to `pipeline_info/envmetag_software_mqc_versions.yml` and snapshotted in the pipeline test.
- Citations for fastp, Bowtie 2, Hostile, SingleM, and GlobDB in `CITATIONS.md` and the MultiQC methods description.
- CI downloads the SingleM CI metapackage from Zenodo (record 23679677), checks its md5, and caches it.
- envmetag report (`ENVMETAG_REPORT`): one self-contained HTML file (`report/envmetag_report.html`) rendered with Quarto from `report/report_data.json`, which `bin/envmetag_report_data.py` builds from the SingleM outputs. New parameters `--report_top_n` and `--report_stacked_bar_max_samples`.
- Unit tests for `bin/` scripts (`tests/bin`, pytest), run in CI by `.github/workflows/bin-tests.yml`.
- envmetag report: taxonomic flow (Sankey) per sample, light/dark theme following the system setting, sticky "How to read" panel, SingleM warnings on hover. The template is now a folder, `assets/report/`.

### `Fixed`

- MultiQC shows one General Statistics row per sample, with separate FastQC sections for raw and trimmed reads (previously six rows per sample).
- `HOSTILE_FETCH` fetches only the Bowtie2 index (`--bowtie2`). Without it, Hostile also built an unused Minimap2 index of the human reference, which was killed for memory in `test_full`.

### `Changed`

- Samplesheet requires `fastq_2` (paired-end only) and unique `sample` values.
- Outputs are published by the workflow `output {}` block; the template's `publishDir` defaults were removed.
- Without `--singlem_metapackage` or `--singlem_db_cache`, the metapackage is downloaded and extracted in the work directory with a warning (previously an error). `-profile test` downloads the CI metapackage from Zenodo and needs no environment variables.

### `Dependencies`

| Tool    | Version |
| ------- | ------- |
| SingleM | 0.21.4  |
| fastp   | 1.4.0   |
| bowtie2 | 2.5.5   |
| Hostile | 2.0.2   |
| FastQC  | 0.13.0  |
| MultiQC | 1.35    |
| Quarto  | 1.9.38  |
| Plotly  | 7.1.0   |
| Python (report container) | 3.13.16 |

### `Tests`

- 2026-10-27: `test_full` (1M read pairs per sample, full GlobDB r232, default SingleM assignment) passed after the Hostile fix: expected dominant species in both samples, 92–95% of coverage resolved to species, PhiX and host spikes removed (~1% each). Details in `DECISIONS.md`.

### `Deprecated`
