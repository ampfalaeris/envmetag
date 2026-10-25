# Decisions log

Dated record of design decisions for `ampfalaeris/envmetag`, with the evidence or public source each one rests on. Newest entries at the bottom.

---

## 2026-10-25 — Target Nextflow 26.10 with static typing

**Decision:** Require Nextflow `>=26.10.0`; new code uses strict syntax, records, and typed processes/workflows (`nextflow.enable.types = true`).

**Why:** 26.10 is the first release where static typing is stable rather than a preview (preview in 25.10 and 26.04). Typed records give compile-time checks on sample metadata fields, which removes a class of silent metadata-loss bugs in channel joins.

**Consequences:**
- `manifest.nextflowVersion` set to `'!>=26.10.0'`.
- CI matrix tests `26.10.0` and `latest-everything` (the template default of `25.10.4` cannot run typed code).

**Sources:**
- Nextflow 26.10.0 changelog — https://docs.seqera.io/changelog/nextflow/v26.10.0
- Static typing docs — https://docs.seqera.io/nextflow/static-typing

---

## 2026-10-25 — Start from the nf-core template (tools 4.2.0) with a custom prefix

**Decision:** Generated with `nf-core pipelines create`, prefix `ampfalaeris`, name `envmetag`, `is_nfcore: false`, skipping iGenomes and nf-core/configs.

**Why:** Keeps nf-core conventions (nf-test, nf-schema, CI, module layout) and leaves open contributing modules or subworkflows upstream later. Not proposed as an nf-core pipeline: the preprocess → classify → assemble → bin backbone overlaps nf-core/mag and nf-core/taxprofiler, and nf-core requires one pipeline per data and analysis type.

**Sources:**
- nf-core workflow specificity guideline — https://nf-co.re/docs/guidelines/pipelines/requirements/workflow_specificity
- Using nf-core resources outside nf-core — https://nf-co.re/docs/guidelines/external_use

---

## 2026-10-25 — Typing scope: typed entry workflow and new code; template plumbing stays legacy for now

**Decision:** `main.nf` and all new subworkflows and modules are typed. The template's inner workflow (`workflows/envmetag.nf`) keeps its legacy software-versions and MultiQC collation block until it is rewritten.

**Evidence (tested locally on Nextflow 26.10.0, build 14055):**
- Enabling types on the untouched template gives 5 lint errors, all from `Process.out.x` / `Workflow.out.x` access. Switching to assignment syntax (`def fq = FASTQC(...)`; `fq.zip`) clears all of them in `main.nf`.
- The typed entry workflow lints clean while calling the template's legacy `PIPELINE_INITIALISATION` and `PIPELINE_COMPLETION` subworkflows.
- The template's versions/MultiQC block does not pass typed lint: `distinct` on `Channel`, `collectFile` on `Value`, a mixed-type list passed to MultiQC, and `flatten` (discouraged with static typing). It needs a rewrite, not a flag flip.

---

## 2026-10-25 — Legacy nf-core modules are called from typed workflows via a tuple adapter

**Decision:** Samples are carried as records. When calling an untyped nf-core module, convert the record to `tuple(meta, reads)` at the call site, and convert the outputs back to records immediately after.

**Evidence:** A typed workflow built `Sample` records from a samplesheet, adapted them to `tuple([id:, single_end:], [r1, r2])`, called `modules/nf-core/fastqc` (legacy), and consumed `.zip`/`.html` by assignment. It passed lint and a `-stub` run (2/2 tasks succeeded).

**Caveat:** Outputs from legacy processes are untyped, so type checking does not cover that boundary; errors there show up at runtime. Keep adapters thin and test them.

---

## 2026-10-25 — Keep `ext.args` / `ext.prefix` in `conf/modules.config`

**Decision:** Tool arguments stay in `modules.config` via `withName` + `ext.args` closures, as in nf-core convention.

**Evidence:** A typed process with a record input (`s: Sample`) received `ext.args = { "--min-len 50 --threads ${task.cpus}" }` and `ext.prefix = { "${s.id}_trimmed" }` correctly. The closure can read record fields by the process input name. It passed lint and ran 2/2 tasks.

**Watch:** nf-core is still settling its static-typing guidelines, and passing tool arguments as explicit process inputs has been floated. Revisit if nf-core/modules adopts that.

- nf-core hackathon Barcelona 2026: static typing — https://nf-co.re/hackathon-projects/hackathon-barcelona-2026/static-typing

---

## 2026-10-25 — SingleM uses the GlobDB r232 metapackage, downloaded at runtime

**Decision:** Profile with SingleM against `GlobDB_r232.metapackage_v4.smpkg.tar.gz`, passed via `--metapackage`, instead of the SingleM default (GTDB R226). The pipeline downloads it at runtime and never bundles or redistributes it.

**Why:** GlobDB includes many more genomes than the GTDB metapackage, which gives better practical coverage for the environmental samples this pipeline targets (remediation sites, MIC).

**Evidence (checked 2026-10-25):**
- An HTTP HEAD request on the download URL returned `Content-Length: 3845940734` (~3.8 GB compressed). That is too large to download on every CI run; real-database SingleM tests need caching or a separate job.
- Extracted locally with `tar -xzf`: 17 GB on disk (`du -sh`), 65 top-level entries in `GlobDB_r232.metapackage_v4.smpkg/`. CI runners must have room for the archive plus the extracted copy; check the runner's free disk before designing that job.
- License from globdb.org: "the GlobDB propagates the licenses of the underlying data sources, and is licensed under CC BY-SA 4.0." Attribution is required. ShareAlike applies to adaptations of the database, not to pipeline code that downloads it unmodified. Any derived subset we publish (e.g., a trimmed test metapackage) must be CC BY-SA 4.0 and credit GlobDB and its underlying sources.

**Consequences:**
- README credits GlobDB (paper below) and links the license; cite underlying sources per https://globdb.org/citations.
- SingleM runs on raw reads, per the `singlem pipe` docs ("Please use **raw** metagenomic reads, not quality trimmed reads, if possible").

**Sources:**
- GlobDB downloads — https://globdb.org/downloads
- GlobDB paper — https://doi.org/10.1093/bioadv/vbaf280
- CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
- SingleM metapackage selection — https://wwood.github.io/singlem/tools/data
- SingleM pipe input guidance — https://wwood.github.io/singlem/tools/pipe

---

## 2026-10-25 — Test data: two public MIC / produced-water metagenomes, subsampled and spiked, hosted on Zenodo

**Decision:** Build the test dataset from two public ENA runs, subsample them with a fixed seed, spike in simulated PhiX and human mitochondrial reads, and deposit the result on Zenodo (CC BY 4.0) with two tiers: `full` (1M read pairs per sample, for the `test` profile and real-database CI) and `tiny` (~10k–20k pairs, for nf-test module tests). A build script in this repo records every step; no reads are committed.

| Run | BioProject | Sample | Instrument | Study |
|---|---|---|---|---|
| SRR12174148 | PRJNA644413 | biofilm from carbon steel corrosion coupon exposed to oil field production water | HiSeq 4000, 2×150 | https://doi.org/10.1128/aem.01819-20 |
| SRR35816318 | PRJNA1346464 | debris from corroded crude oil transporting pipeline | NovaSeq X Plus, 2×151 | https://doi.org/10.3389/fmicb.2026.1771929 |

**Why:**
- Both are MIC samples from oil/gas infrastructure, the pipeline's target use case, and both are tied to peer-reviewed studies.
- The two runs differ in instrument and adapter load, so fastp is exercised in two regimes. Two samples also exercise multi-sample joins and the MultiQC aggregation.
- nf-core/test-datasets does not fit: the `mag` CI reads are simulated from a single *Bacteroides fragilis* genome, and the `taxprofiler` CI reads are gut/ancient samples. Neither is environmental.
- Spikes give the PhiX and host-removal steps a known, nonzero target, so a zero count is a detectable failure, not a silent pass.

**Evidence (checked 2026-10-25, first 20k read pairs streamed from ENA):**
- Both runs are raw: every read has the same length (150 bp and 151 bp respectively). Adapter `AGATCGGAAGAGC` appears in ~8% (SRR12174148) and ~52% (SRR35816318) of reads. Quality is binned to 4 levels, not stripped.
- Rejected: SRR25293831 (one quality character, i.e., SRA-Lite with quality stripped); SRR32001353 (no linked publication found).
- SRR12174148 has `library_selection = PCR`; expect elevated duplication.
- Redistribution: the INSDC policy places "no restrictions or licensing fees ... on the redistribution or use of the database by any party." Submitters retain ownership, so the Zenodo record credits both runs, BioProjects, and papers.

**Depth check (2026-10-25, SingleM 0.21.4 `quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`, GlobDB r232 metapackage, `--threads 4`, container capped at `--memory=4g`):** first 1M / 500k / 200k pairs of SRR12174148, streamed from ENA.

| Pairs | Exit | Wall time | Profile taxa | OTU rows | Coverage: *Methanococcus* MOTU40_004873 / *M. maripaludis* / *Oleidesulfovibrio alaskensis* |
|---|---|---|---|---|---|
| 200k | 0 | 137 s | 7 | 129 | 12.15 / 5.52 / 2.50 |
| 500k | 0 | 186 s | 10 | 224 | 28.04 / 15.76 / 6.42 |
| 1M | 0 | 218 s | 12 | 355 | 59.79 / 33.95 / 13.35 |

- All depths give a non-empty profile with the same dominant taxa; coverage scales ~linearly with depth. 1M adds low-abundance Bacteroidales. No warnings in the logs. No run exceeded the 4 GB cap (peak memory not measured).
- Runtime is dominated by fixed overhead (presumably metapackage loading), so 1M pairs costs little more than 200k.
- The methanogen + sulfate-reducer community matches the linked study's finding that methanogenic archaea drive the corrosion, and should give MCycDB and SCycDB hits for v0.3.
- SingleM takes the `sample` column from the forward-read filename (`SRR12174148_1M_1.fq.gz` → `SRR12174148_1M_1`), not from any sample ID. The module must control staged filenames or rewrite that column, and a test must assert `sample` equals the record `id`.

**Still to verify before depositing:** the same check on SRR35816318.

**Sources:**
- ENA/INSDC policies — https://ena-browser-docs.readthedocs.io/en/latest/about/policies.html
- nf-core/test-datasets `mag` — https://github.com/nf-core/test-datasets/tree/mag
- nf-core/test-datasets `taxprofiler` — https://github.com/nf-core/test-datasets/blob/taxprofiler/README.md
