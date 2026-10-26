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

**Decision:** Build the test dataset from two public ENA runs, subsample them with a fixed seed, spike in simulated PhiX and human mitochondrial reads, and deposit the result on Zenodo (CC BY 4.0) with two tiers: `full` (1M read pairs per sample, for the `test_full` profile with the full GlobDB metapackage) and `tiny` (~10k–20k pairs, for CI: nf-test module tests and the `test` profile). A build script in this repo records every step; no reads are committed.

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

**SRR35816318 check (same setup, first 1M pairs, 2026-10-25):** exit 0, 270 s, 7 profile taxa, no warnings; see the SingleM modules entry below. Both runs now pass, so nothing SingleM-related blocks the deposit.

**Sources:**
- ENA/INSDC policies — https://ena-browser-docs.readthedocs.io/en/latest/about/policies.html
- nf-core/test-datasets `mag` — https://github.com/nf-core/test-datasets/tree/mag
- nf-core/test-datasets `taxprofiler` — https://github.com/nf-core/test-datasets/blob/taxprofiler/README.md

---

## 2026-10-25 — CI runs real SingleM against a 3-marker GlobDB subset; the full metapackage runs before each release

**Decision:**
- **`test` (CI):** `tiny` reads + a CI metapackage built from 3 GlobDB r232 packages (S3.1 rplB, S3.2 rplC, S3.5 rpsB), no nucleotide SDB, with `--assignment-method diamond` set in `conf/test.config`.
- **`test_full` (before every release, locally or on a manual larger-runner job):** `full` reads + the full GlobDB metapackage and the default assignment method, with species-level regression assertions. Each run is noted in `CHANGELOG.md`.
- **Hosting:** the CI metapackage gets its own Zenodo record under CC BY-SA 4.0, separate from the CC BY 4.0 test-reads record.

**Why:**
- The full metapackage does not fit a free GitHub runner. The documented SSD storage is 14 GB for standard Linux runners (public and private repos); the metapackage is 17 GB extracted plus a 3.8 GB archive.
- `-stub` only checks that the stub writes its own headers. A real run against a small database checks the flags, staging, the `sample` column, the real output headers, `prokaryotic_fraction`, and every downstream parser.
- CI cannot build the subset itself: building needs the full metapackage, and GlobDB distributes it as a single `.tar.gz`.

**Evidence (tested locally 2026-10-25, SingleM 0.21.4 `quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`, `--threads 4`, `--memory=4g`, first 200k pairs of SRR12174148):**
- Built with `singlem metapackage --singlem-packages <3 spkgs> --no-nucleotide-sdb --taxon-genome-lengths <GlobDB taxon_genome_lengths TSV> --taxonomy-database-name GlobDB --taxonomy-database-version r232`: exit 0, 59 s, 992 MB, `singlem_metapackage_version: 6`.
- `singlem pipe` with the default assignment method **fails** on it (exit 1, `TypeError` in `SequenceDatabase.acquire`; the manifest has `"nucleotide_sdb": null`). With `--assignment-method diamond`: exit 0, 33 s.
- With the default method, the full metapackage gives species-level *Methanococcus* MOTU40_004873 (12.15), *M. maripaludis* (5.52), and *Oleidesulfovibrio alaskensis* (2.50), with ~94% species assignment. The CI metapackage gives genus-level *Methanococcus* (21.98) and *Oleidesulfovibrio* (2.20), 0% species assignment, plus one Patescibacteriota family (0.55) the full run did not report.
- Determinism: three runs produced byte-identical profiles (md5 `dec91e422dc83e4778d6021b1557dd5d`). OTU tables differed in row order only; they were identical after sorting.

**Consequences:**
- CI asserts: non-empty profile containing `g__Methanococcus` and `g__Oleidesulfovibrio`, exact headers, `sample == id`, profile md5, sorted OTU table. CI profiles are never read as biological results.
- The default smafa + nucleotide-SDB path is tested only by `test_full`; a bug specific to it will not show up in CI.
- The Zenodo record must state the changes from GlobDB r232 (3 of ~59 packages kept, nucleotide SDB removed, prefilter rebuilt), the build command, the SingleM version, and the attribution and license link required by CC BY-SA 4.0. Rebuild and publish a new version if SingleM's metapackage format changes.

**Not yet verified:** the `tiny` tier on the CI metapackage (fewer reads and 3 markers may give an empty profile), and `prokaryotic_fraction` against the CI metapackage.

**Sources:**
- GitHub-hosted runner specs — https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- `singlem metapackage` — https://wwood.github.io/singlem/advanced/metapackage
- CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/

---

## 2026-10-25 — nf-test 0.9.4 supports typed processes, typed subworkflows, and records; record types live in `types/main.nf`

**Decision:** Test typed modules and subworkflows with nf-test 0.9.4 as normal. All record types are declared in one shared file, `types/main.nf`, and `include`d wherever they are used. Local variables in a workflow never share a name with an `emit:` output.

**Evidence (spike outside the repo, Nextflow 26.10.3 build 14229, nf-test 0.9.4; `nextflow lint` clean):**
- A typed process with a `Sample` record input (`id`, `r1`, `r2`) and a `record(...)` output ran under `nextflow run` and under nf-test. `stage: stageAs s.r1, "${s.id}_R1.fastq.gz"` renamed the staged file as intended (this is the fix for SingleM's filename-derived `sample` column).
- In nf-test, `input[0] = channel.of(record(...))` works in the `process {}` / `workflow {}` blocks. Process output arrives as `process.out[0]`, a list of records; typed subworkflow emits arrive by name (`workflow.out.ids`). Record fields and file contents can be read in assertions (`path(r.listing).readLines()`).
- `snapshot()` of records produces `"listing": "<name>:md5,<hash>"`, and a second run matched it.
- `options "-stub"` runs the typed process's `stub:` block.
- Record types are script-scoped: using `Sample` in a subworkflow without `include { Sample } from ...` fails lint with "`Sample` is not defined". Including it from a file that holds only record types works.

**Gotcha found:** a typed emit with the same name as a local `def` variable (`def ids = ...` then `ids: Channel<String> = ids`) **passes `nextflow lint`** but fails at runtime with `MissingValueException: Missing workflow output parameter: ids` (thrown in `WorkflowDef.collectOutputs`). Renaming the local variable was the only change needed.

- Legacy nf-core module through the adapter under nf-test: a typed subworkflow mapped `Sample` records to `tuple([id:, single_end: false], [r1, r2], [])`, called `modules/nf-core/fastp` (fastp 1.4.0, Docker) as `FASTP(ch, false, false, false)`, and mapped `reads` and `json` back to records immediately after. The test asserted the record `id`, the output filenames, non-empty reads, and `summary.before_filtering.total_reads == 2000` from the fastp JSON (1k read pairs in). The `-stub` variant also passed.
- In nf-test assertions, `path(x)` returns a plain `java.nio.file.Path`: use `.fileName.toString()`, not the Nextflow `.name` extension (`MissingPropertyException`).

---

## 2026-10-25 — Strict joins: `remainder: true` plus an inline null check

**Decision:** Every join of record channels is written as `a.join(b, by: 'id', remainder: true)` followed by a `map` that calls `error(...)` inline when any field from either side is null, then returns the record.

**Evidence (Nextflow 26.10.3, typed script, `nextflow lint` clean unless noted):**
- `a.join(b, by: 'id')` on record channels works and merges fields (`[id:s1, r1:a1, profile:p1]`).
- Without options, unmatched keys are **dropped silently** (only the matched `s2` was emitted), even though the operator reference says `failOnMismatch` defaults to `true` "in strict mode".
- `failOnMismatch: true` / `failOnDuplicate: true` are rejected: lint error, and at runtime `Unknown argument 'failOnMismatch' for operator 'join' -- Possible arguments: by, remainder`.
- `remainder: true` emits unmatched records with the other side's fields absent (`[id:s1, r1:a1]`, `profile == null`), so a null check detects them.
- Calling `error()` from an `include`d helper function aborts the run, but the console shows only `Unexpected error [InvocationTargetException]`; the message appears only in `.nextflow.log`. Calling `error()` inline in the operator closure prints the message: `[ERROR] TEST_JOIN: sample 's1' is missing a profile -- ...`.
- Typed records cannot be indexed by a dynamic field name (`r[f]`: "The `[` operator is not defined for operands with types Record and String"), and `Map.findAll` is not in the typed stdlib (documented Map methods: `any`, `containsKey`, `containsValue`, `each`, `entrySet`, `every`, `isEmpty`, `keySet`, `size`, `subMap`, `values`).

- **Receiver must be the typed channel.** In the `PROFILE_SINGLEM` nf-test, `samples.join(pipe_results, ...)` failed with `Invalid operator 'join' argument [nextflow.dataflow.ChannelImpl] -- it must be a channel type`: nf-test's generated wrapper is untyped, so `samples` arrived as a legacy channel, which rejects a typed `ChannelImpl` argument. `pipe_results.join(samples, ...)` (typed process output as receiver) passed. Lint did not flag either form.
- `collect()` on a typed channel yields `Bag<Path>` (unordered), not `List<Path>`; a process input declared `List<Path>` fails lint ("Argument with type Bag<Path> is not compatible"). Declare `Bag<Path>` and sort inside the process if order matters.

**Sources:**
- Operator reference (`join`) — https://docs.seqera.io/nextflow/reference/operator
- Map stdlib type — https://docs.seqera.io/nextflow/reference/stdlib-types/map

---

## 2026-10-25 — SingleM split into three modules: `pipe`, `summarise`, `prokaryotic_fraction`

**Decision:**
- `SINGLEM_PIPE` (per sample): raw reads → condensed profile (`-p`) plus archive OTU table (`--archive-otu-table`), so profiles can be re-condensed or re-annotated without re-searching reads. Condensing happens inside `pipe`; no separate `condense` step.
- `SINGLEM_SUMMARISE` (all samples in one task): profiles → report tables.
- `SINGLEM_PROKARYOTIC_FRACTION` (per sample): profile + the same raw reads → prokaryotic fraction.
- R1 is staged as `${id}.fastq.gz` so SingleM's `sample` column equals the record `id`.

**Evidence (SingleM 0.21.4 `quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`, 2026-10-25):**
- `singlem -h` lists no `classify` subcommand. `pipe` is the read-classification step; its help says condensing "is often more straightforward to invoke ... by specifying -p / --taxonomic-profile when running pipe mode". `pipe` has no sample-name option.
- Sample naming: R1 staged as `SRR12174148.fastq.gz` gave `sample = SRR12174148` (earlier, `SRR12174148_1M_1.fq.gz` gave `SRR12174148_1M_1`).
- `summarise` accepts **exactly one output type per call** (`Exception: Exactly 1 output type must be specified, sorry, 5 were provided`), so the module calls it once per output. Output headers from a real run:
  - `--output-taxonomic-profile-with-extras`: `sample coverage full_coverage relative_abundance level taxonomy`
  - `--output-taxonomic-level-coverage`: `sample level coverage relative abundance (%)`
  - `--output-species-by-site-relative-abundance-prefix P`: one `P-<rank>.tsv` per rank, header `taxonomy <sample...>`, first row `unassigned`. **Only ranks with at least one assignment get a file**: full GlobDB wrote all seven (domain … species); the 3-marker CI metapackage, which assigns nothing at species level, wrote six (no `-species.tsv`). Consumers must treat a missing rank file as "no assignments at this rank", not as an error or as seven guaranteed files.
- `relative_abundance` is a percentage of **prokaryotic marker-gene coverage**, not of reads, and the `unassigned` row is coverage not resolved at that rank, not unclassified reads. The non-prokaryotic share comes only from `prokaryotic_fraction`. The report must label these accordingly.
- `prokaryotic_fraction` counts bases from the reads itself ("Counting bases in sample ..."); with no `--input-metagenome-sizes` it reported `metagenome_size = 6000000` for 20k pairs, matching an independent count. Output header: `sample bacterial_archaeal_bases metagenome_size read_fraction average_bacterial_archaeal_genome_size warning` then per-rank `*_relative_abundance`.
- Full GlobDB, first 1M pairs: SRR12174148 `read_fraction` 77.03, SRR35816318 44.42, no warnings. On the 3-marker CI metapackage, `read_fraction` is capped at 100.00 and SingleM writes a warning (genus-only assignments), so CI must not assert the value.
- Archive OTU table is JSON `version: 4` with keys `alignment_hmm_sha256s`, `singlem_package_sha256s`, `fields` (12 names), `otus`.
- SRR35816318 full-GlobDB profile (1M pairs, 270 s, exit 0, no warnings): dominated by *Sporolactobacillus nakayamae* (coverage 32.09) and *Clostridium_B luticellarii* (3.28), 93% species-level, a Bacillota community distinct from SRR12174148's methanogen/sulfate-reducer biofilm.
- CI metapackage at 20k pairs (`--assignment-method diamond`): SRR12174148 → `g__Methanococcus` 2.75, `g__Oleidesulfovibrio` 0.55; SRR35816318 → `g__Sporolactobacillus` 1.09. Non-empty for both, so 20k pairs is enough for the `tiny` tier.

**Sources:**
- SingleM pipe — https://wwood.github.io/singlem/tools/pipe
- SingleM prokaryotic_fraction — https://wwood.github.io/singlem/tools/prokaryotic_fraction

---

## 2026-10-25 — Read preprocessing: nf-core modules, PhiX from ENA, Hostile mycobacteria-masked index, paired-end only

**Decision:**
- v0.1 accepts **paired-end reads only**, one samplesheet row per sample.
- `PREPROCESS_READS` = FastQC (raw) → fastp → FastQC (trimmed) → bowtie2 against PhiX (keep unaligned pairs) → Hostile, all nf-core modules (fastp 1.4.0, bowtie2/samtools, Hostile 2.0.2) called through the record ↔ tuple adapter.
- PhiX reference: `--phix_fasta` defaults to ENA `J02482.1` (https://www.ebi.ac.uk/ena/browser/api/fasta/J02482.1), indexed at runtime by `BOWTIE2_BUILD`.
- Host index: `--hostile_index` defaults to `human-t2t-hla-argos985-mycob140`, fetched at runtime by `HOSTILE_FETCH`; the `test` profile uses `test-human-mit`.
- fastp runs with its defaults plus the nf-core module's built-in `--detect_adapter_for_pe` (no extra `ext.args`). Decided 2026-10-25 to keep defaults for v0.1; revisit only with evidence from the spiked test data or real runs.

**Why:**
- PhiX: J02482.1 is the INSDC record RefSeq NC_001422.1 is derived from; both return the same 5,386 bp phiX174 genome (checked 2026-10-25). The ENA URL has no query string, so the staged file gets a usable name (`J02482.1`).
- Hostile index: the mycobacteria-masked variant is masked against 985 bacterial genomes plus 140 mycobacterial genomes, so environmental mycobacteria are less likely to be removed as host. Both names were confirmed with `hostile index list` (Hostile 2.0.2): `human-t2t-hla`, `-argos985`, `-argos985-mycob140`, two viral/phage-masked variants, `mouse-mm39`, `test-human-mit`.
- Hostile runs `clean` with `--airplane` in the nf-core module, so no task downloads anything except `HOSTILE_FETCH`.

**Evidence (nf-test, Nextflow 26.10.3, Docker; provisional tiny reads = first 20k pairs per run):**
- All 12 tasks succeed for two samples. For SRR12174148, Hostile reported `reads_in 39308` (19,654 pairs after fastp + PhiX), `reads_removed 0`. Zero is expected: the provisional reads carry no human spike, which is why the real `tiny` tier must.
- **Adapter gotcha:** the nf-core FastQC module emits a *List* of zips for paired reads but a single *Path* from its stub. Mixed into a channel declared `Channel<Path>`, the list passed lint (legacy boundary, untyped) and failed in the test (`ClassCastException: String cannot be cast to ArrayList`). Fixed with `flatMap { _meta, zips -> zips instanceof Path ? [zips] : zips }`; a plain `flatMap` over a bare `Path` would iterate its path components.
- Raw and trimmed FastQC are aliases of one module and would both write `<prefix>_1_fastqc.zip`; `ext.prefix` `<id>_raw` / `<id>_trimmed` keeps them apart.

**Sources:**
- Hostile — https://github.com/bede/hostile
- ENA browser API — https://www.ebi.ac.uk/ena/browser/api/

---

## 2026-10-25 — SingleM metapackage provisioning: local copy preferred, optional one-time download cached with `storeDir`

**Decision:**
- `--singlem_metapackage`: path to an already-extracted `.smpkg` directory. Preferred, and documented with the size (3.8 GB download, 17 GB extracted).
- Otherwise `SINGLEM_PREPAREMETAPACKAGE` takes `--singlem_metapackage_url` (default: GlobDB r232) as a staged `Path`, extracts it, checks for `<name>.smpkg/CONTENTS.json`, and stores the result in `--singlem_db_cache` via `storeDir`. If neither `--singlem_metapackage` nor `--singlem_db_cache` is set, the run errors; it never writes 17 GB to a location the user did not choose.

**Why:** SingleM reads the metapackage from a local directory; it cannot read one in place from object storage, so every run needs a local copy. Re-downloading and re-extracting 3.8 GB → 17 GB per run is wasteful. The user's local extraction of the GlobDB archive took under ~8 minutes.

**Evidence (Nextflow 26.10.3, 2026-10-25):**
- `storeDir` with a remote `Path` input (spike, 5.5 kB ENA file): run 1 staged the file ("Copying foreign file") and ran the task; run 2 printed `[skipping] Stored process` and logged no foreign-file copy. So once stored, the archive is **not** downloaded again.
- First-run disk cost: Nextflow stages the archive in `work/` (3.8 GB) before the task extracts 17 GB; the stored copy then lives in `--singlem_db_cache`.
- SingleM 0.21.4 container has `curl`, `wget`, and busybox `tar` 1.36.1. Module tests (synthetic 1-file archives): valid archive extracts; an archive without `CONTENTS.json` fails with "did not extract to a SingleM metapackage"; stub passes.

---

## 2026-10-25 — Reports: MultiQC for read QC and accounting; separate envmetag report for profiles

**Decision:** MultiQC carries the basic per-sample metrics: FastQC, fastp, bowtie2 (PhiX), Hostile, and the SingleM prokaryotic-fraction estimate as General Statistics columns. A separate envmetag HTML report carries the SingleM community results (profiles, per-rank tables, Krona) and, later, the assembly/binning and marker-gene results.

**Evidence (real `-profile test,docker` run on the provisional tiny reads, 2026-10-25):** MultiQC found 2 reports each for bowtie2, Hostile, and fastp, FastQC for raw and trimmed, the SingleM General Statistics columns, and a per-process software-versions table (e.g. `BOWTIE2_ALIGN`: bowtie2 2.5.5, pigz 2.8, samtools 1.24). **Open polish:** sample names split across rows (`mic_coupon`, `mic_coupon_phix`, `mic_coupon_raw_1`, ...); needs `extra_fn_clean_exts` and separate raw/trimmed FastQC sections in `assets/multiqc_config.yml`.

**Why:** MultiQC already parses the QC tools natively and is where users expect read accounting. Community profiles need caveats MultiQC custom content cannot carry well: relative abundance is of prokaryotic marker-gene coverage, `unassigned` is coverage unresolved at a rank, and marker presence is not activity. Keeping one home for each kind of number avoids two reports disagreeing.

---

## 2026-10-25 — Typed `params` block: types in `main.nf`, defaults in `nextflow.config`, `input` as `String`

**Decision:** `main.nf` declares every parameter it references with a type and **no default**; defaults stay in `nextflow.config` (read by nf-schema and the template), descriptions in `nextflow_schema.json`. `input` is declared `String`, not `Path`. Optional strings are `String?`.

**Evidence (scratch copy of the repo, Nextflow 26.10.3, nf-schema 2.7.3):**
- With a `params` block present, lint rejects any `params.x` not declared in it ("Unrecognized parameter `version`"), so it is all-or-nothing for the entry workflow.
- Precedence: a value in `nextflow.config` overrides the block's default; a profile overrides the config; the CLI overrides both. (Block default `BLOCK_DEFAULT` + config `CONFIG_DEFAULT` → `CONFIG_DEFAULT`; `-profile test` → `test-human-mit`; `--hostile_index CLI_VALUE` → `CLI_VALUE`.) A default in both places would silently lose to the config.
- `input: Path` crashed every run with `StackOverflowError` in Groovy's `DefaultJsonGenerator.writeIterator`: the template's params-to-JSON dump iterates a `Path` (each component is itself a `Path`). `input: String` works; nf-schema still validates the samplesheet path (`format: file-path`, `exists: true`) and its contents.
- An undeclared CLI parameter now fails the run: `Parameter 'hostile_indx' was specified on the command line or params file but is not declared in the script or config` (the template only warned).
- nf-schema enforces the new samplesheet rules: a single-end row → `Entry 1: Missing required field(s): fastq_2`; a duplicate sample → `Entry 2: Detected duplicate entries: [sample:mic_coupon]`.

**Also from this rewrite (lint, Nextflow 26.10.3):** `channel.topic(...)` items are untyped, so closures must index them (`v[0]`), not destructure; `groupTuple` and `collectFile` are "discouraged from use with static typing" (warnings). Versions are grouped in one closure after `collect()`, and `flatMap` turns the collected `Value` back into a `Channel` so `collectFile` can run (on a `Value` it is a lint error). The three remaining `collectFile` warnings are accepted for now.
