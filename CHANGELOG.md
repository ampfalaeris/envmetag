# ampfalaeris/envmetag: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.1 - [2026-10-30]

Report fix for the SingleM prokaryotic fraction, plus curation work for v0.2. The cycling-database tables and scripts below (`assets/cycdb/`, `dev/cycdb/`) are not yet read by the pipeline.

### `Added`

- envmetag report: each sample's share of overlapping read pairs in the sample overview, and mean read lengths and median insert size (from fastp) in a collapsed "Sequencing details" table; all in `report_data.json` (`schema_version` 2). The overview explains, in plain words, that the SingleM prokaryotic fraction runs low when mates overlap (SingleM counts a pair once where both mates cover a marker window but divides by both reads' bases), so fractions should be compared only between samples with similar overlap, and that it is least reliable in simple communities of species missing from the reference database.

### `Fixed`

- envmetag report: the "How to read the numbers" card is shorter and scrolls on its own when the window is too short; on screens narrower than 768 px it stays in the page instead of disappearing with Quarto's hidden sidebar. Tables scroll inside their section instead of overhanging it.
- Canonical-family table for SCycDB, MCycDB and NCyc (`assets/cycdb/canonical_families.tsv`) and per-sequence assignments for sequences carrying more than one family (`assets/cycdb/sequence_assignments.tsv`), with the curation scripts and rebuild instructions in `dev/cycdb/`. Not yet used by the pipeline (v0.2).
- CI check of the two tables (`.github/workflows/cycdb-check.yml`), including a field-count check; `.tsv` files are excluded from the trailing-whitespace hook, which stripped empty last fields.
- Fusion rules in the cycling-database curation: fusion proteins are left out of the curation reference sets, and shared sequences that are fusions are labelled `unresolved:` (basis `fusion`) instead of taking one family's label. The canonical-family table gains a `fusion` column (`declared` for families that are themselves fusions, e.g. _cysN_cysC_).
- Pfam domain test for fusion proteins in the curation (`dev/cycdb/pfam_domains.py`, rebuild step 4b): `hmmsearch --cut_ga` with Pfam 38.2, clan resolution as in `pfam_scan.pl`, per-pair signature domains, and fusion calls reported beside the current ones. Its signature table is checked in as `assets/cycdb/pfam_signatures.tsv`. It does not change any assignment yet.

### `Changed`

- Curation reference sets are built for every family that co-occurs on a shared sequence, independent of grouping, and _cysN_/_cysN_cysC_ form the ambiguity group `cysN_cysNC`. `sequence_assignments.tsv` changed in 280 rows (262 fusions, 14 _cysN_ group, 4 moved because the fusion references they had matched are gone); see DECISIONS.md.
- Pfam fusion calls are added to the shared-sequence assignments (`assign_shared_sequences.py --pfam-calls`; additions only, on pairs Pfam can decide). `sequence_assignments.tsv` changed in 27 rows: _cysJ_/_narB_ fusions whose headers do not name the partner, now `unresolved:cysJ|narB` (basis `pfam fusion`) instead of _cysJ_.

### `Tests`

- 2026-10-30: `test_full` (1M read pairs per sample, full GlobDB r232, default SingleM assignment) passed on the release commit: same dominant species and prokaryotic fractions as 0.1.0 (58.43% and 77.72%), PhiX and host spikes removed (~1% each), and the new report columns match fastp (median insert of overlapping pairs 135 and 185 bp; 90.3% and 74.0% of pairs overlap). Details in `DECISIONS.md`.

## v0.1.0 - [2026-10-28]

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
- Per-process CPU, memory and time sized from the first `test_full` run (`conf/base.config`): e.g. PhiX alignment no longer requests 72 GB, and SingleM (4 GB) and Hostile (6 GB) fit an 8 GB machine.
- Containers only: `-profile conda` and `-profile mamba` now stop at startup with an error, because the local SingleM and report modules have no conda environments (previously tasks failed mid-run with `command not found`). CI no longer runs a conda leg, and the README conda badge is removed.
- Without `--singlem_metapackage` or `--singlem_db_cache`, the metapackage is downloaded and extracted in the work directory with a warning (previously an error). `-profile test` downloads the CI metapackage from Zenodo and needs no environment variables.

### `Dependencies`

| Tool                      | Version |
| ------------------------- | ------- |
| SingleM                   | 0.21.4  |
| fastp                     | 1.4.0   |
| bowtie2                   | 2.5.5   |
| Hostile                   | 2.0.2   |
| FastQC                    | 0.13.0  |
| MultiQC                   | 1.35    |
| Quarto                    | 1.9.38  |
| Plotly                    | 7.1.0   |
| Python (report container) | 3.13.16 |

### `Tests`

- 2026-10-27: `test_full` (1M read pairs per sample, full GlobDB r232, default SingleM assignment) passed after the Hostile fix: expected dominant species in both samples, 92–95% of coverage resolved to species, PhiX and host spikes removed (~1% each). Details in `DECISIONS.md`.

### `Deprecated`
