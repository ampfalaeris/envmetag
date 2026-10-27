# Decisions log

Dated record of design decisions for `ampfalaeris/envmetag`, with the evidence or public source each one rests on. Newest entries at the bottom.

---

## 2026-10-25 — Target Nextflow 26.10 with static typing

**Decision:** Require Nextflow `>=26.10.0`; new code uses strict syntax, records, and typed processes/workflows (`nextflow.enable.types = true`).

**Why:** 26.10 is the first release where static typing is stable rather than a preview (preview in 25.10 and 26.04). Typed records give compile-time checks on sample metadata fields, which removes a class of silent metadata-loss bugs in channel joins.

**Consequences:**
- `manifest.nextflowVersion` set to `'!>=26.10.0'`.
- CI matrix tests `26.10.0` and `latest-everything` (the template default of `25.10.4` cannot run typed code).
- All local evidence in this log was gathered on Nextflow 26.10.3. CI tests the minimum supported version, 26.10.0, which has not been run anywhere yet (2026-10-26); the first CI run is the first check that 26.10.0 actually works.

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
- SingleM runs on raw reads, per the `singlem pipe` docs ("Please use **raw** metagenomic reads, not quality trimmed reads, if possible"). **Superseded 2026-10-26:** SingleM runs on the fastp-trimmed reads (see "2026-10-26 — SingleM runs on fastp-trimmed reads, before PhiX and host removal").

**Sources:**
- GlobDB downloads — https://globdb.org/downloads
- GlobDB paper — https://doi.org/10.1093/bioadv/vbaf280
- CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
- SingleM metapackage selection — https://wwood.github.io/singlem/tools/data
- SingleM pipe input guidance — https://wwood.github.io/singlem/tools/pipe

---

## 2026-10-25 — Test data: two public carbon-steel corrosion metagenomes (coupon biofilm, APB enrichment), subsampled and spiked, hosted on Zenodo

**Decision:** Build the test dataset from two public ENA runs, subsample them with a fixed seed, spike in simulated PhiX and human mitochondrial reads, and deposit the result on Zenodo (CC BY 4.0) with two tiers: `full` (1M read pairs per sample, for the `test_full` profile with the full GlobDB metapackage) and `tiny` (~10k–20k pairs, for CI: nf-test module tests and the `test` profile; 100k pairs since 2026-10-26, see "Tiny test tier is 100,000 read pairs"). A build script in this repo records every step; no reads are committed.

| Run | BioProject | Sample | Instrument | Study |
|---|---|---|---|---|
| SRR12174148 | PRJNA644413 | carbon steel coupon biofilm exposed to oil field production water (BioSample SAMN15459511, `MIC098`); likely a laboratory corrosion-reactor biofilm, not confirmed | HiSeq 4000, 2×150 | https://doi.org/10.1128/aem.01819-20 |
| SRR35816318 | PRJNA1346464 | enrichment biofilm on a carbon steel coupon: corroded crude-pipeline debris enriched for acid-producing bacteria (APB) for 21 days (BioSample SAMN52836159, `APB-CP`) | NovaSeq X Plus, 2×151 | https://doi.org/10.3389/fmicb.2026.1771929 |

Sample descriptions corrected 2026-10-25 from the BioSample records (earlier text called SRR35816318 "debris from corroded crude oil transporting pipeline", which is only its inoculum source).
- SAMN52836159 `description`: "Debris from corroded crude oil transporting pipeline was enriched for acid producing bacteria for 21 days; biofilm grown on carbon steel coupon was used for analysis." The paper's abstract reports that "the highest corrosion activities were observed in enrichments dominated by acid-producing bacteria (APB) and hydrogen-utilizing bacteria". The abstract describes the field samples as from natural gas infrastructure, while the BioSample says crude oil pipeline; the BioSample is quoted here.
- SAMN15459511 says only "biofilm from carbon steel corrosion coupon exposed to oil field production water". The AEM abstract states MIC "was reproduced in the laboratory, both under stagnant conditions and in customized corrosion reactors simulating pipeline flow", and the *M. maripaludis* genome came "from a highly corrosive mixed biofilm"; mapping `MIC098` to a specific experiment needs the paper's methods/supplement.

**Why:**
- Both are MIC-relevant carbon steel coupon biofilms tied to peer-reviewed studies of oil/gas corrosion, the pipeline's target use case.
- Their communities do not overlap: a methanogen + sulfate-reducer corrosion biofilm (*Methanococcus*, *Oleidesulfovibrio*) and a Bacillota APB enrichment dominated by *Sporolactobacillus nakayamae* (a lactic-acid-producing genus, consistent with an APB enrichment). That contrast is useful for the profile report and for v0.3's methane/sulfur marker modules.
- **Limitation:** both are low-diversity biofilms (about 4–7 dominant taxa in SingleM). Neither exercises a high-diversity field community; add one if profile-level behaviour (e.g. many low-abundance taxa, long rank tables) needs testing.
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
- The methanogen + sulfate-reducer community matches the linked study's finding that methanogenic archaea drive the corrosion, and should give MCycDB and SCycDB hits for the marker module (v0.2 since 2026-10-26).
- SingleM takes the `sample` column from the forward-read filename (`SRR12174148_1M_1.fq.gz` → `SRR12174148_1M_1`), not from any sample ID. The module must control staged filenames or rewrite that column, and a test must assert `sample` equals the record `id`.

**Build script (`tests/testdata/build_testdata.sh`, 2026-10-25):** verifies the raw runs against ENA's MD5s; samples 1,000,000 pairs per run with `seqtk sample -s 20261025` (same seed for R1 and R2, pairing checked read by read); simulates 10,000 PhiX (ENA J02482.1) and 10,000 human-mitochondrion (ENA J01415.2, rCRS, 16,569 bp) pairs per sample with InSilicoSeq using the run's instrument model (HiSeq: 126 bp reads; NovaSeq: 151 bp); samples the tiny tier (20,000 pairs) from the full tier with the same seed; writes samplesheets, `MANIFEST.tsv` (pairs and spike pairs per file), `md5sums.txt`, and `PROVENANCE.txt`. Evidence:
- InSilicoSeq 2.0.1 output is identical for the same `--seed` **and** `--cpus` (two runs with `--cpus 2` matched; `--cpus 1` differed), so the script pins `--cpus 1`. `--n_reads` counts reads, not pairs (1,000 → 500 pairs). Reference headers are replaced with plain names because InSilicoSeq copies them into read names (ENA headers contain `|`).
- Trial on SRR35816318: 3 min 10 s; full tier 1,020,000 pairs (10,000 + 10,000 spikes); tiny tier 20,000 pairs with 185 PhiX and 172 human-mito pairs. A second build into a separate directory gave identical `md5sums.txt` for all six files.

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

**Resolved (2026-10-26):** both items left open here were since tested. `prokaryotic_fraction` runs on the CI metapackage but caps `read_fraction` at 100 with a warning, so CI does not assert the value (see "SingleM split into three modules"). The `tiny` tier did give an empty profile at 20,000 seeded pairs, so it is now 100,000 pairs (see "2026-10-26 — Tiny test tier is 100,000 read pairs").

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
- `SINGLEM_PIPE` (per sample): reads (raw at the time; fastp-trimmed since 2026-10-26) → condensed profile (`-p`) plus archive OTU table (`--archive-otu-table`), so profiles can be re-condensed or re-annotated without re-searching reads. Condensing happens inside `pipe`; no separate `condense` step.
- `SINGLEM_SUMMARISE` (all samples in one task): profiles → report tables.
- `SINGLEM_PROKARYOTIC_FRACTION` (per sample): profile + the same reads → prokaryotic fraction.
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
- CI metapackage at 20k pairs (`--assignment-method diamond`): SRR12174148 → `g__Methanococcus` 2.75, `g__Oleidesulfovibrio` 0.55; SRR35816318 → `g__Sporolactobacillus` 1.09. Non-empty for both, so 20k pairs is enough for the `tiny` tier. **Superseded 2026-10-26:** this was the first 20k reads streamed from ENA; the seeded 20k build from `build_testdata.sh` gave an empty SRR35816318 profile (see "2026-10-26 — Tiny test tier is 100,000 read pairs").

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

---

## 2026-10-26 — envmetag report: Quarto in `assets/`, data prepared in `bin/`, Plotly, ranks down to species

**Decision:**
- The report is a Quarto document, `assets/envmetag_report.qmd`, shipped with the pipeline and rendered by a local typed module (`ENVMETAG_REPORT`) to one self-contained HTML file (`embed-resources: true`) with the Jupyter/Python engine.
- The `.qmd` only renders. `bin/envmetag_report_data.py` reads the index files (`singlem/profiles.csv`, `singlem/prokaryotic_fraction.csv`, `singlem/summary.json`) and writes one `report_data.json`. It fails on samples missing from an index, empty tables, or per-rank abundances (including `unassigned`) that do not sum to ~100%.
- Sections (v0.1): header (pipeline version, metapackage, assignment method, links); how to read the numbers; sample overview (prokaryotic fraction, average genome size, SingleM `warning` shown verbatim); community composition; taxonomic resolution (`level_coverage`); per-sample profile tables; methods and GlobDB CC BY-SA 4.0 attribution. Later versions add sections; no empty placeholders.
- Composition plots use **Plotly**, with a rank selector from **domain down to species**. The top **15** taxa per rank (a param) get their own colour; the rest are pooled as "Other"; `unassigned` is always its own segment in a fixed neutral colour.
- A rank with no `by_rank-<rank>.tsv` file (SingleM writes none when nothing is assigned at that rank, e.g. species on the CI metapackage) is shown as "No <rank>-level assignments in this run", not as an error.
- Stacked bars are used up to a sample-count threshold (a param, default 15). Above it the layout changes (heatmap or similar); the fallback is designed after v0.1, once the plots have been seen on real data.
- MultiQC and Krona are separate files, linked by relative path with the path also printed, so the reader can find them if the HTML is moved. No MultiQC numbers are copied into the report; the prokaryotic fraction appears in both because both read it from the same SingleM output.

**Why:**
- A `.qmd` in `assets/` ships and is versioned with the pipeline. Keeping the calculations in `bin/` means the numbers are unit-tested and the JSON can be md5-snapshotted; Quarto HTML embeds generated IDs and is checked by properties only.
- Plotly makes the rank selector and hover values possible in one file, at the cost of ~4 MB of embedded JavaScript per report.
- Stacked bars become unreadable well before 30 samples.
- nf-core `quartonotebook` is deprecated (its script is `assert false`); `quarto/notebook` is tuple-based, runs papermill, and expects its container to be replaced. A small local typed module fits this repository's conventions. Quarto/Deno write caches under `$HOME`, which fails in read-only containers; the module points `XDG_CACHE_HOME`/`XDG_DATA_HOME` into the task directory (the same issue `quarto/notebook` handles).

**Evidence (2026-10-26):** nf-core/modules master checked for `quartonotebook` (deprecated) and `quarto/notebook` (current). conda-forge `quarto` latest is 1.9.38 (anaconda.org API); the exact build is pinned when the container is built. Not yet built or run.

**Sources:**
- Quarto HTML `embed-resources` — https://quarto.org/docs/output-formats/html-publishing.html
- nf-core `quarto/notebook` — https://github.com/nf-core/modules/tree/master/modules/nf-core/quarto/notebook

---

## 2026-10-26 — Tiny test tier is 100,000 read pairs

**Decision:** `build_testdata.sh` samples the `tiny` tier at 100,000 pairs per run (was 20,000). The full tier (1,000,000 pairs + spikes) is unchanged. Test assertions that depend on read or base counts were updated, and the snapshots regenerated from this build.

**Why:** at 20,000 seeded pairs, the 3-marker CI metapackage gave an **empty** SRR35816318 (`apb_enrichment`) profile: 7 sequences after read extraction, then "No reads found", and the empty-profile check in `SINGLEM_PIPE` failed the run as intended. The earlier "20k is enough" result came from the first 20k reads streamed from ENA, a different (luckier) draw. A tier that depends on a dozen marker reads would break on any change to SingleM or the metapackage; choosing a seed until one passes was rejected as cherry-picking.

**Evidence (2026-10-26, SingleM 0.21.4, CI metapackage, `--assignment-method diamond`; Nextflow 26.10.3, nf-test 0.9.4, Docker, `NFT_MAX_MEMORY=7.GB`):**
- 20k seeded build: 11 of 16 nf-tests failed; all 5 not caused by memory limits were the empty `apb_enrichment` profile.
- 100k build: sequences after read extraction 47 (`apb_enrichment`) and 86 (`mic_coupon`); profiles `g__Sporolactobacillus` 3.83; `g__Methanococcus` 6.04, `g__Oleidesulfovibrio` 1.10, `g__JACCQO01` 0.55. All 16 nf-tests pass; 4 snapshots regenerated.
- `metagenome_size` expectations (29,909,616 and 30,200,000 bases) were counted independently with awk over R1 + R2; the spikes are 126 bp, so the count is not pairs × read length.
- Rebuilding gave a full tier byte-identical to the previous build (`md5sums.txt`); 7 min 57 s for both runs.

**Finding: R2 adapter read-through inflates DIAMOND prefilter hits.** In every build, R2 had far more prefilter hits than R1 (CI metapackage: `apb_enrichment` 54 vs 4,558 at 100k, 535 vs 46,813 on the 1M full tier; `mic_coupon` 83 vs 510). Checks:
- Swapping `-1`/`-2` and running each file alone: the hits follow the R2 file, not its position. Present in the unspiked, unsampled first-20k reads too, so it is not caused by the spikes, subsampling, or the download (the raw files pass ENA's MD5s).
- 99.2% of R2 prefilter hits (kept with `--working-directory`) contain the read-through adapter `AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT`, vs 42.1% of R1 hits (library background: ~46% of `apb_enrichment` reads carry adapter, a short-insert library).
- **Cause: an adapter-contaminated reference entry.** Rerunning DIAMOND with SingleM's prefilter parameters (from `singlem/diamond_spkg_searcher.py`: `--evalue 0.01 --frameshift 15 --range-culling --range-cover 1 --max-target-seqs 1`) on the 46,813 R2 hit reads: 46,296 hit one subject, `ribosomal_protein_S2_rpsB~GB_GCA_937897625.1`, a 62-residue fragment. The alignments are ~15 aa at 86% identity, 99% have e-values between 1e-5 and 0.01, and 46,185 span the insert/adapter junction. The matched reference segment is `VRSEERRVGKEC` (positions 45–56), and the frame-0 translation of the R2 adapter is `RSEERRVGKEC`. The R1 adapter translates to `RSEEHTSELQS` and never hit (0 of 362,899 R1 adapter tails). The insert alone (199 of 46,405) or the adapter alone (219 of 46,376) rarely hit: the match needs the codon before the adapter to pass the e-value cutoff. Most likely the source assembly kept adapter at a contig end and the gene call ran into it.
- **Full GlobDB r232 metapackage:** the same entry is in its prefilter (`prefilter.fna.dmnd`, 134,118 proteins, dumped with `diamond getseq`). Scanning every protein for exact ≥10 aa runs of the six-frame translations of both TruSeq adapters found **8 entries from 8 genomes**, all short fragments (38–69 aa): rpsB `GCA_937897625.1`, rpsS `GCA_913009475.1`, rplE `GCA_964443115.1` and `GCA_937968025.1`, TruB `GCA_937889205.1`, pheT `GCA_913009695.1`, recR `GCA_947040435.1`, trmD `GCA_937915475.1`; 4 match the R2/P5 adapter and 4 the R1/P7 adapter. Against the full prefilter, 43,046 of the 46,813 R2 hit reads hit again, mostly the rpsS entry (40,889). Exact 10-mers are a lower bound; diverged adapter-derived stretches are not counted.
- On adapter-trimmed reads the excess disappears: 51 vs 46 hits (first measured on the pipeline's PhiX/host-removed reads; the fastp output alone gives the same counts and the same 41 sequences after extraction). With the full GlobDB, the raw-read ratio is 3.0× (8,605 vs 25,824), identical for the default and `diamond` assignment methods (the prefilter runs before assignment).
- Effect on the profile: the adapter hits are discarded at read extraction (4,558 hits → 47 sequences); raw and trimmed reads give the same taxon. **Coverage:** `g__Sporolactobacillus` 3.83 on raw reads, 4.20 on the fastp output. (An earlier 6.77 came from the Hostile output and is a read-naming artefact, not trimming; see "SingleM runs on fastp-trimmed reads, before PhiX and host removal".)

**Sources:**
- SingleM pipe (input reads, `--working-directory`) — https://wwood.github.io/singlem/tools/pipe

---

## 2026-10-26 — SingleM runs on fastp-trimmed reads, before PhiX and host removal

**Decision:** `PREPROCESS_READS` emits the fastp output as `trimmed` (records, R1/R2 picked by name), and `ENVMETAG` passes it to `PROFILE_SINGLEM`. `SINGLEM_PIPE` and `SINGLEM_PROKARYOTICFRACTION` both see these reads. PhiX- and host-removed reads (`clean`) still feed assembly and the marker module. This replaces "SingleM runs on raw reads" (GlobDB entry, 2026-10-25).

**Why (in order of weight):**
1. **Coverage on short-insert libraries, possibly more accurate.** SingleM 0.21.4 computes coverage per read: each hit adds `fl / (fl - aligned_length + 1)`, where `fl` is that read's own nucleotide length (`coverage_increment` in `singlem/sequence_classes.py`, summed per OTU in `singlem/pipe.py:1060`), the per-read form of the FAQ's `coverage = num_hits * L / (L - k + 1)`. A raw read with adapter read-through has `fl = 151` although only its insert can carry marker sequence, so raw reads in a short-insert library may understate coverage. Observed (CI metapackage, 100k pairs): `apb_enrichment` (~46% of reads carry adapter) `g__Sporolactobacillus` 3.83 raw → 4.20 trimmed; `mic_coupon` (~7.6%) unchanged (`g__Methanococcus` 6.04, `g__Oleidesulfovibrio` 1.10, `g__JACCQO01` 0.55). That the trimmed value is closer to the truth is a reading of the formula, **not measured** against reads simulated at a known depth.
2. **Less spurious prefilter work.** `apb_enrichment` R2 prefilter hits 4,558 raw → 46 trimmed (100k pairs); 46,813 R2 hits on the 1M-pair full tier.
3. **Not depending on the database being clean.** The GlobDB r232 metapackage prefilter holds 8 proteins with translated TruSeq adapter (see "Tiny test tier is 100,000 read pairs"). In our data they do **not** change the profile: the adapter hits are discarded at read extraction and raw and trimmed reads give the same taxa. They are a reason not to feed the database adapter, not evidence of a wrong profile.

**Constraints that come with it:**
- SingleM's docs warn against **quality** trimming ("can make them too short for SingleM to use, particularly if they are trimmed to be shorter than 100 bp") and say "Adapter trimming is unlikely to be detrimental, but is not needed." `fastp --help` (1.4.0, the pinned container): adapter trimming is on by default, poly-G trimming is automatic for NextSeq/NovaSeq, and the quality filter drops whole reads; the sliding-window trimmers (`--cut_front`, `--cut_tail`, `--cut_right`) are off unless requested, and `conf/modules.config` sets none. **Do not add `--cut_*` to fastp without revisiting this decision.**
- Before host removal, so `prokaryotic_fraction` keeps host reads in its denominator: a host-rich sample must show a low prokaryotic fraction, not a high one. PhiX adds well under 1% of reads to the denominator.

**Finding: Hostile breaks SingleM's mate pairing.** Hostile 2.0.2 rewrites read headers from `@SRR35816318.24169622 LH00160:...:14795/1` (fastp and bowtie2 keep this; both mates share the ID) to `@SRR35816318.24169622/1` (the mates' IDs now differ). SingleM pairs mates by identical IDs: on the same Hostile reads, `g__Sporolactobacillus` coverage was **6.77** as written and **4.20** after stripping `/1`/`/2` from the IDs, which equals the fastp-only result; prefilter hits (51/46) and extracted sequences (41) were identical. So on Hostile output SingleM counts mates of one fragment separately and inflates coverage ~1.6×. SingleM no longer reads Hostile output, but the marker module (v0.2) and assembly (v0.3) read the clean reads. **Resolved below** ("Hostile writes Casava 1.8+ headers"). SingleM's FASTQ reader keeps only the first whitespace token as the read name (`partition(" ")[0]` in `SeqReader.readfq`, `singlem/sequence_classes.py`), which is why the `/1` / `/2` suffix matters.

**Tests:** the SingleM module and subworkflow tests feed SingleM fastp-trimmed reads too, produced in nf-test `setup` by the nf-core `FASTP` module with the pipeline's arguments (none set), rather than depositing trimmed reads with the test data, so the tests follow any change to fastp's version or arguments. Verified with nf-test 0.9.4 (2026-10-26):
- A legacy `FASTP` setup feeds a typed process in `when` (`FASTP.out.reads.map { meta, reads -> record(...) }`), and setups chain: `run("FASTP")` then `run("SINGLEM_PIPE")` reading `FASTP.out` both ran.
- Setup outputs are **not** visible in `then`: `FASTP.out` there fails with `MissingPropertyException: No such property: FASTP for class: com.askimed.nf.test.lang.process.ProcessContext`, which nf-test reports only as "1 of 6 assertions failed" (the message shows with `--verbose`). Expected values that depend on setup output, such as `metagenome_size`, are therefore hardcoded with a comment: fastp-output bases 28,922,250 (`mic_coupon`) and 24,819,804 (`apb_enrichment`); fastp's JSON `after_filtering.total_bases`, an awk count, and SingleM's `metagenome_size` agree.

**Sources:**
- SingleM pipe (input reads) — https://wwood.github.io/singlem/tools/pipe
- SingleM FAQ (coverage formula) — https://wwood.github.io/singlem/FAQ
- SingleM 0.21.4 source in `quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`: `singlem/sequence_classes.py` (`coverage_increment`, `SeqReader.readfq`), `singlem/pipe.py`

---

## 2026-10-26 — Hostile writes Casava 1.8+ headers (`--casava`)

**Decision:** `HOSTILE_CLEAN` runs with `ext.args = '--casava'` (`conf/modules.config`), so the clean reads carry `@<id> 1:N:0:0` / `@<id> 2:N:0:0` headers and both mates share the same ID. The `PREPROCESS_READS` test asserts that R1 and R2 IDs match read by read and that headers end in `1:N:0:0` / `2:N:0:0`, so a Hostile change to its header format fails the test.

**Why:** by default Hostile writes `@<id>/1` / `@<id>/2`, so mate IDs differ, and tools that pair mates by ID count both ends of a fragment (SingleM: 1.6× coverage, see "SingleM runs on fastp-trimmed reads"). The clean reads feed the marker module (v0.2) and assembly (v0.3), which may use such tools. Fixing it with Hostile's own option keeps it a tool argument in `conf/modules.config`; a post-hoc regex rewrite would need its own module and script and another pass over every read file. Reordering the steps (fastp → Hostile → PhiX) would not help: Hostile rewrites headers wherever it runs, and bowtie2 passes headers through unchanged (its PhiX output kept fastp's headers).

**Evidence (Hostile 2.0.2, `community.wave.seqera.io/library/hostile:2.0.2--a7f5e5d341b6b94b`, 2026-10-26):**
- `hostile clean --help`: `-c, --casava  use Casava 1.8+ read header format (default: False)`; also `--rename` (integer names) and `--reorder` ("ensure deterministic output order"), not used. `--reorder` may matter once marker or assembly outputs are snapshotted (v0.2, v0.3).
- On 1,000 pairs of `apb_enrichment` fastp output with `--index test-human-mit`: default → `@SRR35816318.24169622/1` and `/2`; `--casava` → `@SRR35816318.24169622 1:N:0:0` and `2:N:0:0`.
- On the full 100k-pair fastp output with `--casava`, SingleM (CI metapackage, `--assignment-method diamond`) gave `g__Sporolactobacillus` **4.20**, identical to the fastp output itself, with the same prefilter hits (51/46) and 41 sequences after extraction. Without `--casava` the same reads gave 6.77.

---

## 2026-10-26 — Roadmap: read-based marker module (v0.2) before assembly and binning (v0.3)

**Decision:** The curated marker-gene module (CANT-HYD, SCycDB, MCycDB, NCycDB) moves to v0.2; assembly → binning → CheckM2 moves to v0.3. Marker genes are quantified from the clean (PhiX- and host-removed) reads and normalized to genome equivalents; when assembly arrives, contig-based marker calls are supporting evidence, not the primary number. The nf-core/funcscan index files stay at v0.4, because funcscan takes contigs.

**Why:**
- The clean reads have no downstream consumer in v0.1; the marker module is the first.
- The marker databases are designed for read-level searches. SCycDB's case study merged read pairs with PEAR (`-q 30`) and searched the merged reads with DIAMOND (`-k 1 -e 0.0001`), without assembly (Yu et al. 2021, §2.3), and the paper states profiles "can be generated by searching raw reads, predicted genes or protein sequences". SCycDB includes 20,761 homologous orthology groups "to reduce false positive sequence assignments", addressing the "small database" problem of specialised databases. **Checked for SCycDB only;** MCycDB, NCycDB and CANT-HYD are to be checked before the module is designed, along with each database's license (CLAUDE.md).
- It is the part of the pipeline that sets envmetag apart. nf-core/mag already covers assembly (MEGAHIT, SPAdes), binning (MetaBAT2, MaxBin2, CONCOCT, COMEBin, MetaBinner, SemiBin2), bin QC (BUSCO, CheckM, CheckM2, GUNC) and bin taxonomy (GTDB-Tk, CAT); its page describes gene prediction on assemblies but no read-based functional-marker quantification (nf-co.re/mag, checked 2026-10-26).
- Short-read assemblies miss low-coverage, high-diversity regions. Berg et al. (2025) compared short- and long-read assemblies of one soil community: "low coverage and high sequence diversity are the two main factors leading to misassemblies in short-read data", and the missed regions are enriched in mobile-element and defense genes. The paper does not assess gene-level quantification; that read-based counts should be the primary quantification is **our inference** from it, not its finding.
- Expected to run on a laptop and in CI, where assembly does not fit comfortably. **Not measured yet:** database sizes, DIAMOND memory, and runtime on the tiny tier are to be checked when the module is designed.

**Normalization: inputs exist; the calculation does not.** SingleM's `prokaryotic_fraction` output already gives `bacterial_archaeal_bases` and `average_bacterial_archaeal_genome_size` per sample (on the fastp reads), so genome equivalents = `bacterial_archaeal_bases / average_bacterial_archaeal_genome_size`. Nothing computes this yet. Using it to normalize marker hits counted on the **clean** reads assumes PhiX and host removal drop (almost) no prokaryotic reads. That is plausible (Hostile's index is masked against 985 bacterial and 140 mycobacterial genomes) but **unmeasured**: check it by running `prokaryotic_fraction` on both read sets and comparing `bacterial_archaeal_bases`. On the CI metapackage these values are not meaningful (DECISIONS, SingleM split), so CI can test the plumbing only; the value is checked in `test_full`.

**Consequences:**
- CLAUDE.md roadmap reordered; version references in this log updated.
- Clean-read header format matters now, not later: the marker module reads Hostile output (see "Hostile writes Casava 1.8+ headers").
- The marker module still needs positive and negative control genomes (CLAUDE.md, Testing).

**Sources:**
- Yu X, et al. (2021). SCycDB: a curated functional gene database for metagenomic profiling of sulphur cycling pathways. *Molecular Ecology Resources* 21(3):924–940. https://doi.org/10.1111/1755-0998.13306
- Berg M, Reiter T, Emerson J, Brown CT, Roux S (2025). Comparison of short-read and long-read metagenome assemblies in a natural soil community highlights systematic bias in recovery of high-diversity populations. *NAR Genomics and Bioinformatics* 7(4):lqaf163. https://doi.org/10.1093/nargab/lqaf163
- nf-core/mag — https://nf-co.re/mag

---

## 2026-10-26 — Zenodo deposits: flat layout, samplesheets in the repository, build scripts cite their commit

**Decision:**
- `build_testdata.sh` writes a **flat** directory: the reads, `phix.fa`, `human_mt.fa`, `samplesheet_full.csv`, `samplesheet_tiny.csv`, `MANIFEST.tsv`, `md5sums.txt` and `PROVENANCE.txt` (was `full/`, `tiny/`, `references/`). A flat list of files is what a Zenodo web upload is sure to support, so the local layout now matches the deposit and the same `base + filename` works for both.
- The pipeline reads the samplesheets from the **repository** (`tests/testdata/samplesheet_{tiny,full}.csv`, written by the deposit build with the record's URL prefix), not from the record. A wrong URL or a moved file is then fixed by a commit, not by a new Zenodo version. `ENVMETAG_TESTDATA_BASE` still points the `test` and `test_full` profiles at a local build.
- Both build scripts write the repository commit into `PROVENANCE.txt`. A deposit build (`build_testdata.sh` with a `base_url`, `build_ci_metapackage.sh --deposit`) refuses to run unless the script is committed unchanged, so each record can cite the exact code that made it.
- The CI metapackage is built by `tests/testdata/build_ci_metapackage.sh` (previously by hand, recorded only in a local `build.log`) and deposited as one reproducible `GlobDB_r232_ci3.smpkg.tar.gz` (`tar --sort=name`, fixed mtime, numeric owner, `gzip -n`), with `md5sums.txt` and a `PROVENANCE.txt` stating the changes from GlobDB, the command, the SingleM version and the CC BY-SA 4.0 attribution.
- `conf/test_full.config` now uses the full tier and the full metapackage (it still pointed at the template's viralrecon test data).

**Evidence (2026-10-26):**
- `build_ci_metapackage.sh` run twice into separate directories: identical `md5sums.txt`, including the `.tar.gz` (194,810,030 bytes), 4 min 20 s each with `--threads 1`. Every file in the package also matched, by md5, the hand-built `globdb_r232_ci3` package that all CI-metapackage evidence in this log was gathered on.
- File URLs, checked on a public record (23679385, 2026-10-27): `https://zenodo.org/records/<id>/files/<key>` returns the file directly (HTTP 206 to a range request, `application/octet-stream`, no redirect), with or without `?download=1`. That record's key is `SciML/JumpProcesses.jl-v10.0.1.zip`, so keys **can** contain `/` (it came from the GitHub integration; whether the web upload allows it was not checked). Flat names are kept anyway: they need no assumption about upload paths, and a staged file's name is the last URL segment either way.
- Zenodo drafts, including a reserved DOI, stay editable and deletable until published, so the real draft (record 23679308) served as the dry run instead of sandbox.zenodo.org.
