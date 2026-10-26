# ampfalaeris/envmetag: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.0.0dev - [unreleased<!-- TODO nf-core: replace with date on release -->]

Initial release of ampfalaeris/envmetag, created with the [nf-core](https://nf-co.re/) template.

### `Added`

- Typed entry workflow (`main.nf`) with a typed `params` block, and a typed `ENVMETAG` workflow.
- Read preprocessing (`PREPROCESS_READS`): FastQC (raw/trimmed), fastp, PhiX removal with bowtie2 (ENA J02482.1), host removal with Hostile (`human-t2t-hla-argos985-mycob140`).
- SingleM profiling on raw reads (`PROFILE_SINGLEM`): `pipe`, `prokaryotic_fraction`, `summarise`, with the GlobDB r232 metapackage via `--singlem_metapackage` or a one-time cached download (`--singlem_db_cache`).
- Workflow `output {}` block with index files for clean reads, SingleM profiles, prokaryotic fraction, and the SingleM summary.
- MultiQC General Statistics columns for the SingleM prokaryotic-fraction estimate (`bin/singlem_fraction_mqc.py`).

### `Fixed`

### `Changed`

- Samplesheet requires `fastq_2` (paired-end only) and unique `sample` values.
- Outputs are published by the workflow `output {}` block; the template's `publishDir` defaults were removed.

### `Dependencies`

| Tool    | Version |
| ------- | ------- |
| SingleM | 0.21.4  |
| fastp   | 1.4.0   |
| bowtie2 | 2.5.5   |
| Hostile | 2.0.2   |
| FastQC  | 0.13.0  |

### `Deprecated`
