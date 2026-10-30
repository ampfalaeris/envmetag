# ampfalaeris/envmetag: Output

## Introduction

This document describes the output produced by the pipeline. All paths are relative to the top-level results directory (`--outdir`).

Each result set has an **index file** (CSV or JSON) listing one entry per sample, with columns named after the record fields and absolute paths to the published files. Read these index files in downstream analyses; do not rely on globbing the directories. Row order in index files is not guaranteed; sort by `id`.

## Pipeline overview

- [Read preprocessing](#read-preprocessing): FastQC (raw) → fastp → FastQC (trimmed) → PhiX removal (bowtie2) → host removal (Hostile)
- [SingleM profiling](#singlem-profiling): read-based taxonomic profiles and prokaryotic fraction, computed on the **fastp-trimmed** reads
- [envmetag report](#envmetag-report): community composition from the SingleM results, as one HTML file
- [MultiQC](#multiqc): read QC and read accounting across all samples
- [Pipeline information](#pipeline-information): run metrics and parameters

### Read preprocessing

<details markdown="1">
<summary>Output files</summary>

- `preprocess/clean_reads.csv`: index with columns `id,r1,r2`.
- `preprocess/clean_reads/<id>/`
  - `*.clean_1.fastq.gz`, `*.clean_2.fastq.gz`: reads after adapter and poly-G trimming (fastp; no sliding-window quality trimming), PhiX removal, and host removal.

</details>

Cleaned reads are the input to later assembly and marker-gene steps. Their headers use the Casava 1.8+ format (`@<read id> 1:N:0:0` / `@<read id> 2:N:0:0`, written by Hostile with `--casava`), so both mates of a pair share one read ID; the original header description is not kept. FastQC, fastp, bowtie2, and Hostile reports are summarised in MultiQC rather than published separately.

### SingleM profiling

SingleM runs on the fastp-trimmed reads (adapters and poly-G tails removed, no sliding-window quality trimming), before PhiX and host removal. Untrimmed adapter sequence matches a few adapter-contaminated proteins in the GlobDB r232 metapackage (see `DECISIONS.md`). All abundances below are **read-based estimates from marker genes**, not counts of classified reads.

<details markdown="1">
<summary>Output files</summary>

- `singlem/profiles.csv`: index with columns `id,profile,archive_otu_table`.
- `singlem/profiles/<id>.singlem_profile.tsv`: condensed taxonomic profile (`sample`, `coverage`, `taxonomy`). `coverage` is marker-gene coverage, not read count.
- `singlem/archive_otu_tables/<id>.singlem_archive_otu_table.json`: archive OTU table, so profiles can be re-condensed or re-annotated without searching the reads again.
- `singlem/prokaryotic_fraction.csv`: index with columns `id,fraction`.
- `singlem/prokaryotic_fraction/<id>.singlem_prokaryotic_fraction.tsv`: `singlem prokaryotic_fraction` output. `read_fraction` is an estimate (genome-size based, capped at 100) of the percentage of trimmed-read bases (host and PhiX reads included) from Bacteria and Archaea; the remainder may be eukaryotic, viral, or unknown. Check the `warning` column.
- `singlem/summary.json`: index of the cross-sample summary files below.
- `singlem/summary/`
  - `singlem.profiles.tsv`: all samples' profiles in one table.
  - `singlem.profile_extras.tsv`: per taxon `coverage`, `full_coverage` (including descendants), `relative_abundance`, `level`.
  - `singlem.level_coverage.tsv`: how much coverage was assigned at each taxonomic level.
  - `singlem.by_rank-<rank>.tsv`: site-by-taxon relative abundance, one table per rank. **A rank with no assignments has no file.** The first row, `unassigned`, is coverage not resolved at that rank.
  - `singlem.krona.html`: interactive Krona plot.

</details>

`relative_abundance` is a share of **prokaryotic marker-gene coverage**, not of all reads; read it together with `read_fraction`. Taxon presence is not evidence of activity.

### envmetag report

<details markdown="1">
<summary>Output files</summary>

- `report/envmetag_report.html`: self-contained HTML report (about 7.5 MB; opens offline, no external scripts or fonts).
- `report/report_data.json`: every number shown in the report, in one JSON file (`schema_version` 2): run metadata, per-sample prokaryotic fraction and library summary from fastp (`library`: mean read lengths, share of read pairs whose mates overlap, median insert of those pairs), per-rank composition (top taxa, `Other`, `unassigned`), taxonomic flow (Sankey nodes and links; taxa under 1% of a sample pooled as `Other`), taxonomic resolution, and the per-sample profiles.

</details>

The report shows the SingleM results: a sample overview (prokaryotic fraction, share of overlapping read pairs from fastp, and SingleM's warning verbatim on hover, with read bases, read lengths, insert sizes and average genome size in a collapsed "Sequencing details" table), community composition from domain to species with a rank selector, a taxonomic flow (Sankey) diagram per sample, how far down each sample was resolved, and each sample's full profile. The prokaryotic fraction runs low when mates overlap: with paired reads, SingleM counts a read pair once where both mates cover the same marker window, but divides by the bases of both reads. The overview explains this in plain words and shows each sample's share of overlapping pairs, so fractions are compared only between samples with similar overlap (DECISIONS.md, "First real-data check of SingleM's prokaryotic fraction"). It follows the reader's light or dark system setting and has a toggle. Percentages are shares of **prokaryotic marker-gene coverage** (read-based), and coverage unresolved at a rank is always shown as _unassigned_. At each rank, the `--report_top_n` taxa (default 15) with the highest abundance in any one sample get their own colour; the rest are pooled as _Other_. A rank with no assignments in the run is listed as such. The report links to MultiQC and the Krona plot by relative path, so keep the output directory layout when moving it.

### MultiQC

<details markdown="1">
<summary>Output files</summary>

- `multiqc/multiqc_report.html`: standalone HTML report.

</details>

[MultiQC](http://multiqc.info) summarises FastQC (raw and trimmed), fastp, bowtie2 (PhiX), and Hostile, plus the SingleM prokaryotic-fraction estimate and its warning as General Statistics columns, and the software versions used. Community profiles are not in MultiQC; they are in the SingleM outputs and the envmetag report above.

### Pipeline information

<details markdown="1">
<summary>Output files</summary>

- `pipeline_info/`
  - Reports generated by Nextflow: `execution_report_<timestamp>.html`, `execution_timeline_<timestamp>.html`, `execution_trace_<timestamp>.txt`, `pipeline_dag_<timestamp>.html`.
  - Parameters used by the run: `params_<timestamp>.json`.
  - Software versions per process: `envmetag_software_mqc_versions.yml` (the same table as in the MultiQC report).
  - `pipeline_report.html` / `pipeline_report.txt`: only when `--email` / `--email_on_fail` is used.

</details>
