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

| Run         | BioProject   | Sample                                                                                                                                                                | Instrument            | Study                                      |
| ----------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | ------------------------------------------ |
| SRR12174148 | PRJNA644413  | carbon steel coupon biofilm exposed to oil field production water (BioSample SAMN15459511, `MIC098`); likely a laboratory corrosion-reactor biofilm, not confirmed    | HiSeq 4000, 2×150     | https://doi.org/10.1128/aem.01819-20       |
| SRR35816318 | PRJNA1346464 | enrichment biofilm on a carbon steel coupon: corroded crude-pipeline debris enriched for acid-producing bacteria (APB) for 21 days (BioSample SAMN52836159, `APB-CP`) | NovaSeq X Plus, 2×151 | https://doi.org/10.3389/fmicb.2026.1771929 |

Sample descriptions corrected 2026-10-25 from the BioSample records (earlier text called SRR35816318 "debris from corroded crude oil transporting pipeline", which is only its inoculum source).

- SAMN52836159 `description`: "Debris from corroded crude oil transporting pipeline was enriched for acid producing bacteria for 21 days; biofilm grown on carbon steel coupon was used for analysis." The paper's abstract reports that "the highest corrosion activities were observed in enrichments dominated by acid-producing bacteria (APB) and hydrogen-utilizing bacteria". The abstract describes the field samples as from natural gas infrastructure, while the BioSample says crude oil pipeline; the BioSample is quoted here.
- SAMN15459511 says only "biofilm from carbon steel corrosion coupon exposed to oil field production water". The AEM abstract states MIC "was reproduced in the laboratory, both under stagnant conditions and in customized corrosion reactors simulating pipeline flow", and the _M. maripaludis_ genome came "from a highly corrosive mixed biofilm"; mapping `MIC098` to a specific experiment needs the paper's methods/supplement.

**Why:**

- Both are MIC-relevant carbon steel coupon biofilms tied to peer-reviewed studies of oil/gas corrosion, the pipeline's target use case.
- Their communities do not overlap: a methanogen + sulfate-reducer corrosion biofilm (_Methanococcus_, _Oleidesulfovibrio_) and a Bacillota APB enrichment dominated by _Sporolactobacillus nakayamae_ (a lactic-acid-producing genus, consistent with an APB enrichment). That contrast is useful for the profile report and for v0.3's methane/sulfur marker modules.
- **Limitation:** both are low-diversity biofilms (about 4–7 dominant taxa in SingleM). Neither exercises a high-diversity field community; add one if profile-level behaviour (e.g. many low-abundance taxa, long rank tables) needs testing.
- The two runs differ in instrument and adapter load, so fastp is exercised in two regimes. Two samples also exercise multi-sample joins and the MultiQC aggregation.
- nf-core/test-datasets does not fit: the `mag` CI reads are simulated from a single _Bacteroides fragilis_ genome, and the `taxprofiler` CI reads are gut/ancient samples. Neither is environmental.
- Spikes give the PhiX and host-removal steps a known, nonzero target, so a zero count is a detectable failure, not a silent pass.

**Evidence (checked 2026-10-25, first 20k read pairs streamed from ENA):**

- Both runs are raw: every read has the same length (150 bp and 151 bp respectively). Adapter `AGATCGGAAGAGC` appears in ~8% (SRR12174148) and ~52% (SRR35816318) of reads. Quality is binned to 4 levels, not stripped.
- Rejected: SRR25293831 (one quality character, i.e., SRA-Lite with quality stripped); SRR32001353 (no linked publication found).
- SRR12174148 has `library_selection = PCR`; expect elevated duplication.
- Redistribution: the INSDC policy places "no restrictions or licensing fees ... on the redistribution or use of the database by any party." Submitters retain ownership, so the Zenodo record credits both runs, BioProjects, and papers.

**Depth check (2026-10-25, SingleM 0.21.4 `quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`, GlobDB r232 metapackage, `--threads 4`, container capped at `--memory=4g`):** first 1M / 500k / 200k pairs of SRR12174148, streamed from ENA.

| Pairs | Exit | Wall time | Profile taxa | OTU rows | Coverage: _Methanococcus_ MOTU40_004873 / _M. maripaludis_ / _Oleidesulfovibrio alaskensis_ |
| ----- | ---- | --------- | ------------ | -------- | ------------------------------------------------------------------------------------------- |
| 200k  | 0    | 137 s     | 7            | 129      | 12.15 / 5.52 / 2.50                                                                         |
| 500k  | 0    | 186 s     | 10           | 224      | 28.04 / 15.76 / 6.42                                                                        |
| 1M    | 0    | 218 s     | 12           | 355      | 59.79 / 33.95 / 13.35                                                                       |

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
- With the default method, the full metapackage gives species-level _Methanococcus_ MOTU40_004873 (12.15), _M. maripaludis_ (5.52), and _Oleidesulfovibrio alaskensis_ (2.50), with ~94% species assignment. The CI metapackage gives genus-level _Methanococcus_ (21.98) and _Oleidesulfovibrio_ (2.20), 0% species assignment, plus one Patescibacteriota family (0.55) the full run did not report.
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
- SRR35816318 full-GlobDB profile (1M pairs, 270 s, exit 0, no warnings): dominated by _Sporolactobacillus nakayamae_ (coverage 32.09) and _Clostridium_B luticellarii_ (3.28), 93% species-level, a Bacillota community distinct from SRR12174148's methanogen/sulfate-reducer biofilm.
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
- **Adapter gotcha:** the nf-core FastQC module emits a _List_ of zips for paired reads but a single _Path_ from its stub. Mixed into a channel declared `Channel<Path>`, the list passed lint (legacy boundary, untyped) and failed in the test (`ClassCastException: String cannot be cast to ArrayList`). Fixed with `flatMap { _meta, zips -> zips instanceof Path ? [zips] : zips }`; a plain `flatMap` over a bare `Path` would iterate its path components.
- Raw and trimmed FastQC are aliases of one module and would both write `<prefix>_1_fastqc.zip`; `ext.prefix` `<id>_raw` / `<id>_trimmed` keeps them apart.

**Sources:**

- Hostile — https://github.com/bede/hostile
- ENA browser API — https://www.ebi.ac.uk/ena/browser/api/

---

## 2026-10-25 — SingleM metapackage provisioning: local copy preferred, optional one-time download cached with `storeDir`

**Decision:**

- `--singlem_metapackage`: path to an already-extracted `.smpkg` directory. Preferred, and documented with the size (3.8 GB download, 17 GB extracted).
- Otherwise `SINGLEM_PREPAREMETAPACKAGE` takes `--singlem_metapackage_url` (default: GlobDB r232) as a staged `Path`, extracts it, checks for `<name>.smpkg/CONTENTS.json`, and stores the result in `--singlem_db_cache` via `storeDir`. If neither `--singlem_metapackage` nor `--singlem_db_cache` is set, the run errors; it never writes 17 GB to a location the user did not choose. **Superseded 2026-10-27:** the run now extracts into `work/` with a warning (see "Metapackage download without a cache directory extracts in `work/`").

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
- The `.qmd` only renders. `bin/envmetag_report_data.py` reads the index files (`singlem/profiles.csv`, `singlem/prokaryotic_fraction.csv`, `singlem/summary.json`) and writes one `report_data.json`. **Amended 2026-10-27:** it reads the staged SingleM files passed from channels, not the index files (see "envmetag report takes its inputs from channels"). It fails on samples missing from an index, empty tables, or per-rank abundances (including `unassigned`) that do not sum to ~100%.
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

**Evidence (2026-10-26):** nf-core/modules master checked for `quartonotebook` (deprecated) and `quarto/notebook` (current). conda-forge `quarto` latest is 1.9.38 (anaconda.org API); the exact build is pinned when the container is built. **Built and run 2026-10-27:** see "envmetag report container and offline rendering".

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

- Yu X, et al. (2021). SCycDB: a curated functional gene database for metagenomic profiling of sulphur cycling pathways. _Molecular Ecology Resources_ 21(3):924–940. https://doi.org/10.1111/1755-0998.13306
- Berg M, Reiter T, Emerson J, Brown CT, Roux S (2025). Comparison of short-read and long-read metagenome assemblies in a natural soil community highlights systematic bias in recovery of high-diversity populations. _NAR Genomics and Bioinformatics_ 7(4):lqaf163. https://doi.org/10.1093/nargab/lqaf163
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
- Test reads published 2026-10-27 as https://doi.org/10.5281/zenodo.23679308 (Dataset, CC BY 4.0, version 1), built at commit `b7d4a48` with reads byte-identical to the tested local build. The record's API lists 15 files whose md5s all match the deposit build. The full nf-test suite (16 tests) then passed with no local test data, staging the tiny-tier reads from the record's URLs; no snapshot changed.
- CI metapackage published 2026-10-27 as https://doi.org/10.5281/zenodo.23679677 (Dataset, `cc-by-sa-4.0`, version 1), built with `--deposit` at commit `b8ce08e`. The API lists 3 files (`GlobDB_r232_ci3.smpkg.tar.gz` 194,810,030 bytes, md5 `489596e61aa1353d1577c6fb99843d3a`; `md5sums.txt`; `PROVENANCE.txt`) whose md5s match the deposit build, and the archive downloads directly from `https://zenodo.org/records/23679677/files/GlobDB_r232_ci3.smpkg.tar.gz`. Related works: derived from GlobDB (doi:10.1093/bioadv/vbaf280), supplemented by the repository and by the test-reads record. The test-reads record was then edited (metadata only; still version 1, 15 files) to link both ENA runs (derived from), the repository and the metapackage record (supplemented by), and the two source studies (cites).

---

## 2026-10-27 — Metapackage download without a cache directory extracts in `work/`; `-profile test` needs no setup

**Decision:**

- If neither `--singlem_metapackage` nor `--singlem_db_cache` is set, the pipeline no longer stops: it downloads `--singlem_metapackage_url`, extracts it in the work directory, and logs a warning with the default archive's size. This supersedes the "never writes 17 GB to a location the user did not choose" rule in "SingleM metapackage provisioning" (2026-10-25); `--singlem_metapackage` stays the preferred option and `--singlem_db_cache` the way to keep one download across runs.
- `conf/test.config` sets `singlem_metapackage_url` to the CI metapackage on Zenodo (record 23679677), so `-profile test` runs with no environment variables, as other Nextflow pipelines' test profiles do. `ENVMETAG_SINGLEM_CI_METAPACKAGE` remains an optional override pointing at an extracted copy.
- CI (`.github/actions/nf-test/action.yml`) downloads the archive once, checks its md5 (`489596e61aa1353d1577c6fb99843d3a`), extracts it, caches it with `actions/cache` (v6.1.0, pinned by SHA; key = record id + md5), and sets `ENVMETAG_SINGLEM_CI_METAPACKAGE`. The SingleM module and subworkflow tests read the metapackage path directly, so without the cache each of them would download 195 MB.

**Why:** `work/` is where users expect intermediate files and is easy to delete; nf-core pipelines extract their databases there. Requiring an environment variable for `-profile test` was a setup step no other pipeline asks for. The cost of the default (re-downloading 3.8 GB per fresh run) is stated in the warning and the docs rather than enforced.

**Evidence (2026-10-27, Nextflow 26.10.3, Docker):**

- Zenodo archive downloaded fresh: md5 matches the record's API and the local deposit build; all 44 extracted files match the record's `md5sums.txt`; `diff -r` against the local CI metapackage shows no differences.
- The CI action's download and env steps, extracted from `action.yml` and run with a scratch `$HOME`: exit 0, md5 OK, 992 MB extracted, variable written to `$GITHUB_ENV`. (The `actions/cache` step itself only runs on GitHub.)
- `nf-test test --profile=+docker --ci` with the variable pointing at that download and no `ENVMETAG_TESTDATA_BASE` (reads from Zenodo): 16/16 passed, no snapshot changed.
- `nextflow run . -profile test,docker` from an empty directory with no `ENVMETAG_*` variables: warning logged, `SINGLEM_PREPAREMETAPACKAGE` ran once in `work/`, 20 tasks succeeded; a null `storeDir` created no extra directory; the `mic_coupon` profile md5 (`39d5969df28cb937727cf7db5ccf8357`) matches the pipeline-test snapshot.

**Sources:**

- `actions/cache` releases — https://github.com/actions/cache/releases
- CI metapackage record — https://doi.org/10.5281/zenodo.23679677

---

## 2026-10-27 — envmetag report takes its inputs from channels; data script details

**Decision:**

- `ENVMETAG_REPORT` receives the SingleM files as staged inputs from channels (per-sample profiles and prokaryotic-fraction TSVs, the `summarise` by-rank and level-coverage tables) plus the sample ids. It does not read the published index files. Index files remain the interface for users and downstream pipelines; CLAUDE.md, `main.nf` and `docs/output.md` were reworded to match.
- `bin/envmetag_report_data.py` (standard library only) writes `report_data.json` (`schema_version` 1): run metadata, per-sample overview from `prokaryotic_fraction`, per-rank composition, level coverage, per-sample profiles, and relative links to MultiQC and Krona. Samples are sorted by id and input order does not change the output, so the JSON can be md5-snapshotted.
- Per-rank sums (taxa + `unassigned`) and per-sample level shares must be 100 ± 0.5 percentage points, or the script fails.
- Top-N per rank is chosen by each taxon's **largest value in any one sample**, not its mean, so a taxon that dominates one sample is not pooled into "Other". Ties break on the full lineage. Plot labels are the last lineage field without its rank prefix; if two kept taxa share one, the parent is added.
- A sample whose profile has no taxa is an error, not an empty bar.

**Why:**

- The output block writes index files when it publishes outputs; no channel inside the run carries them, and their absolute `outdir` paths are not staged into a task. A process that read them would depend on publishing order, which nothing guarantees.
- The ±0.5 tolerance: real output already sums to 99.99 (mic_coupon, genus, CI run), because SingleM rounds each value to 2 decimals.
- Pooling by mean would hide exactly the sample-specific dominants (e.g. a sulfate reducer in one corrosion coupon) the report is meant to show.
- An empty profile has several possible causes (failed library, wrong reads, a true blank); failing makes the user look, per CLAUDE.md ("an unexplained empty result is a bug"). **Open:** extraction blanks are a legitimate use case and may need an explicit opt-in later.

**Evidence (2026-10-27):**

- SingleM 0.21.4 source (`quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2`, `condense.py`, `CondensedCommunityProfile.taxonomic_level_coverage_table`): level numbers count from root (0, skipped), so 1 = domain … 7 = species. SingleM replaces the numbers with names **only when a sample has 7 or 8 distinct levels**; otherwise it writes numbers. The CI run's file uses numbers (6 levels, deepest genus); a full-GlobDB run with species assignments will use names. The script accepts both and rejects anything else.
- 22 pytest tests (`tests/bin/`) pass on Python 3.10, 3.13 (3.13.14 from uv) and 3.14 (pytest 9.1.1, via `uv run --no-project`). Fixtures in `tests/bin/fixtures/ci_two_samples/` are the real SingleM outputs of a `-profile test,docker` run (profiles byte-identical to the pipeline-test snapshot). Synthetic cases cover non-zero `unassigned`, a species table, named levels, pooling, duplicate labels, and malformed input. One test caught a bug in the first version (only the first of two taxa sharing a short name was relabelled).
- CI runs these tests in `.github/workflows/bin-tests.yml` on Python 3.13, the minor version of the report container (python=3.13.16; uv has no 3.13.16 build, so the CI patch version can differ). Not yet run on GitHub.

---

## 2026-10-27 — envmetag report container and offline rendering

**Decision:**

- `ENVMETAG_REPORT` uses one Seqera Containers image (Docker format), `community.wave.seqera.io/library/python_quarto_plotly_ipykernel_pruned:3bfdf2df398a5458` (build `bd-3bfdf2df398a5458_1`; digest `sha256:2f0013f3f51a6c7b47b8758de7929e97551e822eac045a94d1f37e458fe49def`), built from conda-forge `python=3.13.16 quarto=1.9.38 plotly=7.1.0 ipykernel=7.4.0 nbclient=0.11.0 pyyaml=6.0.3`. Singularity/Apptainer users get Nextflow's conversion of the Docker image, as for the SingleM modules; a native `.sif` build can be added if conversion is slow on HPC.
- The module sources the image's conda activation scripts (`quarto.sh`, `deno_dom.sh`), sets `QUARTO_DENO_DOM` from `DENO_DOM_PLUGIN`, points `HOME`/`XDG_*` into the task directory, writes a minimal `_quarto.yml`, and renders a copy of the template rather than the staged symlink.
- The report must open offline. Each Plotly figure is written with `fig.to_html(full_html=False)` inside a raw-HTML block (` ```{=html} `), with plotly.js inlined in the first figure only; MathJax is off (`html-math-method: plain`). The module fails if the HTML loads any `<script>` or `<link>` from `http(s)://`.
- `--report_top_n` and `--report_stacked_bar_max_samples` (default 15 each) are pipeline parameters, passed to the data script through `conf/modules.config`.

**Why / evidence (2026-10-27, Docker, renders run with `--network none --memory=3g`):**

- A first image without `pyyaml` cannot render: Quarto's Jupyter runner (`share/quarto/jupyter/notebook.py`) imports `yaml`. `quarto check jupyter` still printed "OK" after that traceback, so only a real render is a valid test.
- Plain `docker run` does not run conda activation scripts, so `quarto` cannot find its share directory or `deno` until `quarto.sh` is sourced (nf-core `quarto/notebook` does the same). `quarto.sh` sets `QUARTO_DENO_DOM` to a path in conda's build environment (`/home/conda/feedstock_root/...`), which logs "Error loading deno-dom-native"; the library is at `/opt/conda/lib/deno_dom.so`.
- Plotly's notebook renderer (`fig.show()`) leaves jQuery, RequireJS, plotly.js and MathJax as CDN `<script src>` tags. Pandoc then tries to fetch them for `embed-resources` and fails (the image has no CA certificates; offline compute nodes would fail regardless).
- Printing the inlined plotly.js with `output: asis` but **without** a raw-HTML block makes Pandoc parse ~4.5 MB of JavaScript as Markdown: killed at the 3 GB cap (exit 137). The same render without a cap exhausted WSL's 7.7 GB and stopped Docker Desktop.
- With the raw-HTML block on the final image: exit 0 offline, one 6.05 MB HTML, 0 remote scripts or stylesheets, one plotly.js copy. The module's nf-test asserts the same properties on the real CI fixtures and md5-snapshots `report_data.json` (`16b642d60f53d932fdd17540e4f5de67`, identical in a hand run, the module test, and the pipeline test). The full-pipeline `-stub` run passes (20 tasks).
- All package versions were first published on conda-forge more than two weeks before the build (anaconda.org API): quarto 1.9.38 2026-05-26, plotly 7.1.0 2026-09-22, ipykernel 7.4.0 2026-09-29, nbclient 0.11.0 2026-06-05, pyyaml 6.0.3 2025-09-26, python 3.13.16 2026-10-06 (3.13.17 and 3.13.18 were newer than that).
- Python 3.10 is not possible in this image: plotly 7.1.0 and ipykernel 7.4.0 require Python ≥3.11 on conda-forge.

**Sources:**

- Quarto HTML `embed-resources` — https://quarto.org/docs/output-formats/html-publishing.html
- Pandoc raw attribute (` ```{=html} `) — https://pandoc.org/MANUAL.html#extension-raw_attribute
- nf-core `quarto/notebook` — https://github.com/nf-core/modules/tree/master/modules/nf-core/quarto/notebook
- Wave build — https://wave.seqera.io/view/builds/bd-3bfdf2df398a5458_1

---

## 2026-10-27 — Hostile fetches only the Bowtie2 index (`--bowtie2`)

**Decision:** `HOSTILE_FETCH` runs `hostile index fetch --bowtie2` (`ext.args` in `conf/modules.config`).

**Why:** `hostile clean` aligns these paired short reads with Bowtie2 (MultiQC's Hostile table reports `aligner bowtie2`). Without a flag, `hostile index fetch` downloads the Bowtie2 index **and** the reference FASTA, from which it builds a Minimap2 `.mmi` that is never used.

**Evidence (Hostile 2.0.2, `community.wave.seqera.io/library/hostile:2.0.2--a7f5e5d341b6b94b`, 2026-10-27):**

- `test_full` with the default index `human-t2t-hla-argos985-mycob140` failed in `HOSTILE_FETCH`: after downloading the 940 MB FASTA (checksum verified), `minimap2 -x map-ont -d ….mmi` was killed (exit 137) under a 7 GB memory limit. CI never reached this: the `test-human-mit` index builds in seconds.
- `hostile index fetch --name test-human-mit` wrote the `.bt2` files plus `test-human-mit.fa.gz` and `test-human-mit.mmi`; with `--bowtie2` it wrote only the six `.bt2` files.
- With `--bowtie2`, the `PREPROCESS_READS` nf-test passes with no snapshot change, and `test_full` passes (`HOSTILE_FETCH` 3 min 28 s, 78 MB peak RSS).

---

## 2026-10-27 — envmetag report: Sankey flow, light/dark theme, layout

**Decision:**

- **Taxonomic flow (Sankey).** Built in `bin/envmetag_report_data.py` from `singlem summarise --output-taxonomic-profile-with-extras` (per-taxon `coverage` and `full_coverage`), one diagram per sample behind a menu. Taxa below 1% of a sample (`--sankey-min-percent`) flow into one "Other <rank>" node per rank; coverage assigned exactly at a node flows into "Unresolved below <rank>". A taxon never has more coverage than its parent, so a kept taxon's parent is always kept and each sample sums to 100%. The script checks `full_coverage ≈ coverage + Σ children` (2-decimal rounding tolerance) and fails otherwise.
- **Labels.** Lineages are shown without rank prefixes (`Archaea › AGJL01 › … › Methanococcus`); the raw strings stay in the JSON. Sankey node labels: species as `M. maripaludis`, then names over 16 characters cut in the middle (`Sporolacto…aceae`), keeping the rank-bearing ending; full lineage on hover.
- **Layout.** Table of contents on the left; the "How to read the numbers" callout is moved by inline JavaScript into Quarto's sticky right sidebar (it stays in the body without JavaScript). SingleM warnings appear verbatim on hover or keyboard focus of a badge in the overview table. The Sankey uses `column: page`; Quarto's own script hides the side panels while a full-width element is on screen.
- **Theme.** The template is a folder, `assets/report/` (`envmetag_report.qmd`, `theme-light.scss`, `theme-dark.scss`), rendered with Quarto's light/dark pair and `respect-user-color-scheme: true`. Both themes set `$web-font-path: false`. Plotly figures and their menus are recoloured from the theme's CSS variables when the scheme changes.

**Why:** requested after viewing the first renders (2026-10-27): the plain layout was hard to scan; long names overlapped in the Sankey; dark mode made the Plotly menus unreadable. Middle truncation was chosen over a plain cut because Desulfovibrionaceae and Desulfovibrionales would both become `Desulfovibriona…` in adjacent columns.

**Evidence (2026-10-27):**

- Quarto 1.9.38 themes: cosmo, flatly, darkly, cyborg and superhero import Google Fonts through `$web-font-path` (slate does not); `margin-header` exists only for websites, not single documents; `quarto.js` hides overlapped sidebars for `column-*` elements. All read from the report container.
- Rendered HTML (module test and `test_full`): both theme stylesheets embedded (`--em-page` `#edf1f5` / `#0f141a`), no `googleapis` and no remote `@import`; 0 remote scripts or stylesheets (the module's offline check now also rejects remote CSS `@import`). Viewed by the user in a browser, light and dark.
- Unit tests: 29 pass, including Sankey flows on the CI fixture (mic_coupon: Archaea 78.54%, flows from the root sum to 100%), 1% pooling, unresolved flows, and the consistency check. The `profile_extras` fixture was produced by `singlem summarise` 0.21.4 from the fixture profiles.

---

## 2026-10-27 — First `test_full` run

**Run:** `-profile test_full,docker`, 1M-pair tier (local build `build_v3`, identical to Zenodo record 23679308), full GlobDB r232 metapackage, SingleM default assignment method, Nextflow 26.10.3, tasks capped at 4 CPUs / 7 GB. Code: `dev` at `9a80354` plus the uncommitted report, Hostile and Sankey changes committed with this entry.

**Results:**

|                                           | apb_enrichment                       | mic_coupon                                                                                        |
| ----------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Dominant taxa (share of profile coverage) | _Sporolactobacillus nakayamae_ 84.9% | _Methanococcus_ MOTU40_004873 51.8%, _M. maripaludis_ 30.4%, _Oleidesulfovibrio alaskensis_ 10.9% |
| Taxa in profile                           | 5                                    | 12                                                                                                |
| Coverage resolved to species              | 92.5%                                | 95.2%                                                                                             |
| Prokaryotic fraction                      | 58.43% (SingleM warning)             | 77.72%                                                                                            |
| PhiX reads removed (bowtie2)              | 0.99%                                | 0.99%                                                                                             |
| Host reads removed (Hostile)              | 0.99%                                | 1.02%                                                                                             |

- Taxa match the depth checks on raw reads (2026-10-25); removal rates match the 10,000 spiked PhiX and human-mitochondrion pairs per sample.
- apb_enrichment's prokaryotic fraction is 58.43% on trimmed reads against 44.42% on raw reads in the earlier 1M-pair check. That run has ~52% adapter-containing reads; trimming removes those bases from the denominator. Consistent with "SingleM runs on fastp-trimmed reads", but large enough to state.
- `level_coverage` used level **names** (7 levels present), the first real test of that path; the per-rank tables included `species` and non-zero `unassigned` (7.52% and 4.80% at species).
- Peak RSS per task: Hostile clean 2.9 GB, FastQC/fastp ≤1.3 GB, SingleM pipe 1.0 GB (full GlobDB), report 0.86 GB, MultiQC 1.0 GB. Longest tasks: SingleM pipe 3–3.6 min, Hostile fetch 3.5 min (download). `conf/base.config` defaults are not yet tuned from this.

---

## 2026-10-27 — Process resources sized from the first `test_full` run

**Decision:** keep the nf-core label defaults in `conf/base.config`, and override by name the seven processes whose label is far from measured use:

| Process                     | Label request                | Peak RSS (test_full) | Now              |
| --------------------------- | ---------------------------- | -------------------- | ---------------- |
| BOWTIE2_BUILD (PhiX)        | process_high: 12 CPU, 72 GB  | 10 MB                | 1 CPU, 1 GB, 1 h |
| BOWTIE2_ALIGN (PhiX)        | process_high: 12 CPU, 72 GB  | 125 MB               | 4 CPU, 2 GB, 4 h |
| FASTP                       | process_medium: 6 CPU, 36 GB | 1.3 GB               | 4 CPU, 4 GB, 4 h |
| FASTQC_RAW / FASTQC_TRIMMED | process_low: 2 CPU, 12 GB    | 0.74 GB              | 2 CPU, 4 GB      |
| HOSTILE_CLEAN               | process_low: 2 CPU, 12 GB    | 2.9 GB               | 4 CPU, 6 GB, 8 h |
| SINGLEM_PIPE                | process_medium: 6 CPU, 36 GB | 1.0 GB               | 4 CPU, 4 GB, 8 h |
| SINGLEM_PROKARYOTICFRACTION | process_low: 2 CPU, 12 GB    | 0.23 GB              | 2 CPU, 2 GB      |

Memory and time are multiplied by `task.attempt`; the existing `errorStrategy` retries once on exit codes 130–145 (137 = killed for memory), so a first miss gets double. Processes already close to their label (MultiQC, the report, SingleM summarise, metapackage preparation, Hostile fetch) are unchanged.

**Why:**

- A 72 GB request to align reads to a 5 kb genome waits in cluster queues for no reason, and oversized requests limit how many tasks run at once on a workstation.
- Nextflow's local executor refuses a task that requests more memory than the machine has. Keeping SingleM at 4 GB and Hostile at 6 GB lets the pipeline run on an 8 GB laptop, as CLAUDE.md intends for SingleM.
- Time limits allow ~50x the test_full depth (1M pairs), since run time grows with read count (SingleM 3.6 min per 1M pairs → ~3 h at 50M).

**Evidence (2026-10-27):** peak RSS and run times from the `test_full` trace ("First `test_full` run"). A `-stub` run of `-profile test` recorded the requested resources per task, all as in the table (time shows the test profile's 1 h cap), and completed on this 7.7 GB machine **without** a memory-limit override; before this change it failed with "Task requirement exceeds available memory -- req: 15 GB". The full nf-test suite (`--ci`, Docker) then passed 18/18 with no snapshot change and **without** `NFT_MAX_MEMORY`, which every earlier local run on this machine needed.

**Not measured:** memory on samples much deeper than 1M pairs. Bowtie2/Hostile and SingleM memory is dominated by the index or metapackage, but fastp and SingleM have not been profiled on, e.g., 20M+ pairs. Revisit with a real deep sample.

---

## 2026-10-28 — Containers only for v0.1; conda and mamba profiles stop at startup

**Decision:** v0.1 supports container profiles only. `PIPELINE_INITIALISATION` calls `error()` when `-profile` includes `conda` or `mamba`, before any task runs. The CI matrix drops the conda leg, the README conda badge is removed, and `docs/usage.md` says conda is not supported yet. Conda support can return as its own change, with an `environment.yml` per local module.

**Why:** the five local modules (`SINGLEM_PIPE`, `SINGLEM_PROKARYOTICFRACTION`, `SINGLEM_SUMMARISE`, `SINGLEM_PREPAREMETAPACKAGE`, `ENVMETAG_REPORT`) declare a `container` but no `conda` directive, so under conda their tools are simply absent from the task environment. The template still advertised conda, and a run failed deep into the pipeline with `command not found`. Failing at startup with a clear message follows "fail loudly". Adding conda now would mean SingleM and Quarto environments that cannot be tested on the development machine (no conda installed) and a separate code path in the report module, which sources activation scripts from the container's `/opt/conda`.

**Evidence (2026-10-28):**

- First PR run to `master` (PR #1; conda and Singularity run only on PRs to `master`): all 7 `conda | 26.10.0` shards failed with exit 127, `singlem: command not found` and `quarto: command not found`. Docker and Singularity on 26.10.0 passed all 14 shards. The `latest-everything` leg shows green regardless, because it runs with `continue-on-error`.
- After the change: `nextflow run . -profile test,conda -stub` and `-profile test,mamba -stub` both exit 1 with the new message and `completed=0`. `nextflow lint .` has no errors; `nf-core pipelines lint --release` reports no new failure.

**Not covered:** `-with-conda` on the command line without a conda profile is not caught by the profile check.

---

## 2026-10-28 — Cycling database audit: what the files contain and where they disagree

**Decision:** use SCycDB (`SCycDB_2020Mar.faa` + `id2gene.2020Mar.map`), MCycDB (`MCycDB_2021.faa` + `id2gene.map`) and NCyc (`NCyc_100_2019Jul.faa` + `id2gene.map.2019Jul`, with homolog labels from `NCyc_100.faa.gz` headers), downloaded from pinned commits, with the preparation rules in CLAUDE.md ("Marker module (v0.2) rules").

**Evidence (2026-10-28, this machine; standard-library scripts `cycdb_audit.py`, `splitzip_extract.py`, `cycdb_overlap.py`, `cycdb_family_pairs.py`, kept outside the repository with the downloads):** commits SCycDB `f107be1a` (2025-04-01), MCycDB `ceba2187` (2026-01-12), NCyc `4ee9aad9` (2020-12-30). None of the repositories has a license file or license wording.

|                                                  | SCycDB             | MCycDB                   | NCyc (2019Jul) |
| ------------------------------------------------ | ------------------ | ------------------------ | -------------- |
| FASTA records                                    | 911,805            | 923,847 (+24 with no ID) | 273,501        |
| Unique IDs                                       | 906,636            | 851,188                  | 273,501        |
| Duplicate IDs (all identical sequence)           | 5,169              | 71,519                   | 0              |
| Map targets                                      | 579,056            | 610,147                  | 219,091        |
| FASTA IDs absent from map (homologs by map rule) | 327,580            | 241,041                  | 54,410         |
| Families in map                                  | 207                | 275 (README: 298)        | 69             |
| Header says target (`gene=`) but not in map      | 0                  | 40,875 (219 genes)       | 0              |
| Duplicate IDs annotated both target and homolog  | 3,980 (all in map) | 2,162 (2,161 in map)     | 0              |

- **Extraction:** inflating each split-zip entry from the central directory matched the archive's size and CRC32 exactly (SCycDB 364,058,792 B, `298f37da`; MCycDB 380,449,265 B, `753c621e`). The NCyc 7z entry also matches its CRC32 (`cb5dc65b`). That Info-ZIP `unzip` leaves a partial SCycDB FASTA and Python's `zipfile` refuses the archive was observed in the claude.ai planning session, not rechecked here.
- **NCyc files:** `NCyc_100.faa.gz` and `id2gene.map` are the original release (committed 2018-04-23). The 7z ("Duplicated records removed", 2019-07-28) and `id2gene.map.2019Jul` (2019-07-29) are the authors' cleanup. Both FASTAs hold the same 273,501 IDs with identical sequences; the 2018 file adds annotation headers and 441 duplicate records, the 2019 file has bare IDs. The 2018 map lists 99,288 IDs absent from the FASTA and gives 81 IDs two families; the 2019Jul map covers exactly the FASTA's targets, one family each, and adds `nasC`. Of single-label IDs, 243 changed from 2018 to 2019: `pmoA` → `amoA_B` 192, `amoA_A` → `amoA_B` 29, `amoA_B` → `pmoA` 22. The README and `NCycProfiler.PL` still point at the 2018 files.
- **Map targets labelled homolog:** 18 IDs in the 2019Jul map have only `homolog` headers in `NCyc_100.faa` (e.g. `ureA homolog`, `nirS homolog`). By the map rule they are targets. SCycDB and MCycDB have none.
- **Mixed-annotation duplicates are not conflicts:** SCycDB and MCycDB IDs that occur twice with the same sequence, once as a target and once as a homolog of the same gene under a different orthology group, are listed in the map as targets. One MCycDB exception, `59538.XP_005978769.1` (_fbp_), is in neither.
- **SCycDB maps:** `id2gene.map.2021` drops 49,084 IDs across 192 families from `id2gene.2020Mar.map` and adds or relabels none (same 207 families). The README documents only 2020Mar.
- **ID types** (share of unique IDs): UniProt accessions 7.2% / 20.2% / 65.8% (SCycDB / MCycDB / NCyc); RefSeq `WP_` 38.1% / 31.6% / 0; eggNOG `taxid.locus` 28.6% / 25.0% / 9.1%.
- **Cross-database overlap** (identical IDs; target in both / one only / homolog in both): SCycDB–MCycDB 76,543 (43,447 / 12,576 / 20,520); MCycDB–NCyc 41,128 (39,867 / 579 / 682); SCycDB–NCyc 3,530 (1,429 / 1,792 / 309). By identical sequence: 73,683, 49,631 and 9,421. 29 shared IDs (14 MCycDB–NCyc, 15 SCycDB–NCyc) carry different sequences.

**Open (emailed to the authors 2026-10-28; no reply yet):** license, or permission to use a small attributed subset as test data; whether the 40,875 MCycDB `gene=` sequences are targets missing from the map (README 298 families and 610,208 sequences vs map 275 and 610,147); the 24 ID-less MCycDB records and `59538.XP_005978769.1`; which SCycDB map is current; whether the NCyc 2019Jul pair is the current release, and whether its family moves (192 IDs pmoA → amoA_B, 29 amoA_A → amoA_B, 22 amoA_B → pmoA) are corrections; the 18 NCyc targets labelled homolog; where PCycDB's database FASTA is and under what license; split-zip extraction (suggested a single `.gz` or published checksums).

**Sources:**

- SCycDB — https://github.com/qichao1984/SCycDB
- MCycDB — https://github.com/qichao1984/MCycDB
- NCyc — https://github.com/qichao1984/NCyc

---

## 2026-10-28 — One combined DIAMOND database for the three cycling databases

**Decision:** search SCycDB, MCycDB and NCyc as one database: IDs prefixed by source, identical sequences collapsed with labels merged, target status winning over homolog across sources. A read is counted once per family; totals are never summed across cycles.

**Why:** with separate searches a read can count in two databases. A combined database makes them compete for each read, and every database's homologs act as extra decoys for the others. The audit's overlap counts show the rules are needed: 12,576 SCycDB–MCycDB sequences are a target in one and only a homolog in the other, and 29 IDs mean different sequences in different databases.

**Not yet verified:** that the combined database recovers each target family at least as well as its own database alone, on the positive controls. Check before v0.2 ships.

---

## 2026-10-28 — Canonical-family table keyed by (database, family); ambiguity groups

**Decision:** families from the three databases are joined through a curated table in the repository, keyed by `(source_db, source_family)`. Each row gives a canonical family (KO-level where a KO exists), an ambiguity group, the cycles, a `core_metabolism` flag, and a note with the evidence. A shared KO is a candidate merge, except K10944–K10946 (copper membrane monooxygenase: methane and ammonia) and K00370/K00371 (nitrate reductase and nitrite oxidoreductase), whose families stay separate. Sequences carry a set of families; reads are resolved to one family, or counted once for the ambiguity group, as in CLAUDE.md.

**Why:**

- Names are not keys. MCycDB `mdh` (methanol dehydrogenase, COG1454) and `mdh-K00024` (malate dehydrogenase) differ; so do MCycDB `fdhA` (formate DH) and `fdhA-K00148` (formaldehyde DH). The KO suffixes exist to separate them, and NCyc splits `gdh` and `gs` into four KOs each.
- Collapsing identical sequences leaves 48,763 of 1,711,123 sequences with two or more target families (114 within one database). Of the 171 family pairs that share sequences, 61 share at least 10 sequences and 1% of the smaller family (49,008 links); the other 110 (339 links) look like single mislabels and are resolved to one family in the table.
- Of those 49,008 links, 76% join synonyms: one enzyme under two names (SCycDB `mdh` = MCycDB `mdh-K00024`, 25,853; MCycDB `amoA` = NCyc `amoA_B`, 8,207; SCycDB `gdh` = NCyc `gdh_K00262`, 2,278; _narG_/_narZ_; _narH_/_narY_). The rest form 14 groups of different enzymes on shared sequences, which labels cannot separate: the COG0437 Fe-S subunits (_ttrB_, _dmsB_, _phsB_, _psrB_, _soeB_, _nrfC_, ...), COG0243 molybdopterin subunits, _acs_/_prpE_, _acdB_/_dmdC_, _serA_/_slcC_, _sudA_/_gltD_, _torC_/_napC_, _nirA_/_sir_, and smaller ones.
- Housekeeping families (malate and glutamate dehydrogenase, glutamate synthase) are large and nearly universal, so their abundance says little about a cycle; they are flagged and kept out of the cycle headline numbers.

**Evidence (2026-10-28):** `cycdb_overlap.py` and `cycdb_family_pairs.py` on the files in the audit entry; dominant orthology groups per family from FASTA target headers; KO names and pathway links looked up once in the KEGG REST API. KEGG REST is "made available only for academic use by academic users", so the pipeline never calls it and the repository stores KO identifiers only. Working notes, the cluster chart, and the open questions are in the Claude Doc "envmetag cycling databases: gene family comparison".

**To do:** build the table from the 21 clusters and the 339 weak links, recording each decision; confirm MCycDB `mdh` as K00093 from a sample of sequences; check the 1,653 SCycDB `gdh` sequences shared with no NCyc family.

**Superseded in part (2026-10-28):** the `cycles` and `core_metabolism` columns, the KO exception list and the handling of weak links are replaced by "Canonical-family table: roles, cycles, one marker per step" and "Shared sequences: assigned per sequence from header groups and similarity" below.

**Sources:**

- KEGG REST API — https://www.kegg.jp/kegg/rest/

---

## 2026-10-28 — Read calls: score margin plus database-derived thresholds; ROCkOut for a short list

**Decision:**

- Every read hitting the combined database is called **target / homolog / ambiguous** from the margin between its best target and best homolog bitscore (DIAMOND `--top`), with per-family thresholds; reads whose target hits span families in one ambiguity group use a family-vs-family margin with per-group thresholds.
- Thresholds are generated from the database itself during preparation: target and homolog proteins are cut into read-length fragments with simulated substitutions, aligned with the production DIAMOND settings excluding each fragment's own 95% cluster (MMseqs2), and the cutoff is chosen from the resulting score distributions. This adapts ROCker's approach without hand-curated genomes.
- ROCkOut models (ROCker's Python successor) only for _dsrAB_, _mcrA_, _amoA_ vs _pmoA_, and _bssA_/_assA_ (v0.2.x).

**Why:**

- An e-value cannot separate a target from its homolog: both align with tiny e-values. ROCker reported ~60× lower false-discovery rate than fixed e-values, and for bacterial _amoA_ only ~10% of reads landed in the correct clade without negative references vs 81% with them (from the claude.ai planning session; not rechecked here).
- Hand-built models for ~570 families would be unmaintainable; database-derived thresholds are rebuilt automatically when the database changes.
- Protein fragments miss frame shifts, sequencing errors, and reads from non-coding flanks, so the derived thresholds are checked against genome-simulated control reads for 2–3 markers.
- _amoA_ vs _pmoA_ joins the ROCkOut list because one KEGG KO (K10944) covers both, and the NCyc 2019 relabelling (243 IDs among `pmoA`, `amoA_A` and `amoA_B`) shows the curators correcting exactly this confusion.

**Deferred:** a per-read posterior from a mixture model on margins. Bracken-style redistribution is rejected: it pushes reads from lineages missing in the database onto their nearest neighbour, inflating them.

**Sources:**

- ROCker (NAR, 2017) — https://academic.oup.com/nar/article/45/3/e14/2972200
- ROCkOut — https://github.com/KGerhardt/ROCkOut
- ROCkIn v1.0 — https://zenodo.org/records/14707993

---

## 2026-10-28 — Quantification unit, mate handling, and the single-copy calibrator

**Decision:** marker abundance is gene coverage (aligned bases / gene length) divided by genome equivalents (`bacterial_archaeal_bases / average_bacterial_archaeal_genome_size` from SingleM). Mates are handled the same way SingleM handles them when it computes coverage. A universal single-copy gene (e.g. _rplB_ or _rpoB_) is searched alongside the markers with identical steps and must come out at about 1 copy per genome equivalent.

**Why:** SingleM's coverage depends on how it pairs mates (coverage rose ~1.6× when Hostile's `/1` `/2` headers broke pairing), and that flows into the denominator. A numerator with a different pair convention biases copies per genome by up to ~2×, varying with insert size. Pair merging changes query length and merge rate by library, so it is tested, not assumed: run the calibrator with and without merging and keep the version that holds near 1 on both test libraries.

**To do before coding:** read how SingleM 0.21.4 combines mates in its coverage calculation.

---

## 2026-10-28 — CANT-HYD and PCycDB move to v0.3 (protein level)

**Decision:** CANT-HYD and PCycDB are used on predicted proteins from assemblies (v0.3), not on reads.

**Evidence (claude.ai planning session, 2026-10-28; not rechecked in this repository):**

- CANT-HYD (last commit 2022-07-14, GPL-3.0): 37 HMMs, each with a trusted (TC) and noise (NC) cutoff; the README runs `hmmsearch --cut_tc` / `--cut_nc` on protein FASTA. The cutoffs are full-length-protein bitscores (e.g. TmoA_BmoA TC 900, NC 810) that a ~50 aa read fragment cannot reach.
- PCycDB: the paper assembled reads (MEGAHIT), called ORFs (Prodigal), and tuned its cutoffs on a simulated gene set and a 50-genome mock community. Its GitHub repository holds scripts and examples but no database FASTA, and no license.

**Consequence:** until v0.3, anaerobic hydrocarbon activation markers (_bssA_, _assA_) have no read-level quantification unless the v0.2.x ROCkOut models exist.

**Sources:**

- CANT-HYD — https://github.com/dgittins/CANT-HYD-HydrocarbonBiodegradation
- PCycDB paper — https://doi.org/10.1186/s40168-022-01292-1
- PCycDB repository — https://github.com/ZengJiaxiong/Phosphorus-cycling-database

---

## 2026-10-28 — ROCkOut integration design (v0.2.x; license resolved 2026-10-29)

**Decision:**

- Model building (ROCkIn curation, then ROCkOut `download → build → refine`) is offline work in a build script, one model per marker, versioned and deposited; never a pipeline step.
- The pipeline runs ROCkOut `align → filter → place` as **one module per sample**, placement switched by a parameter.
- Inputs: clean reads converted to FASTA (`seqtk seq -a`); reads shorter than a model's shortest training read length are dropped (parameter, recorded per model).

**Why one module:** `align` creates `alignments/` and `original_reads/` in the filter directory, `filter` writes `ROCkOut_passing_read_fastas/` into it, and `place` writes there too. Split across processes, a later task would write into an earlier task's work directory, breaking caching and resume. All three steps only read the model directory, so a shared cached copy is safe (confirm with a read-only mount in the module test).

**Module must handle (from the ROCkOut source, read in the claude.ai planning session 2026-10-28; recheck before coding):**

- `place` runs MAFFT, pplacer and guppy through `os.system()` without checking exit codes: the module checks every expected output exists and is non-empty.
- ROCkOut treats each mate as a separate read: passing reads are collapsed by read ID so each fragment counts once.
- `align` writes a second copy of the reads into the filter directory (disk on deep samples).
- No releases: the container pins a commit hash, at or after `d701c05` (the first licensed commit).

**License (resolved 2026-10-29):** ROCkOut had no license file (last commit 2025-07-02), which ruled out a public container image, a pinned copy, or deposited models. Asked in https://github.com/KGerhardt/ROCkOut/issues/1, suggesting the licenses of its relatives (ROCker Artistic-2.0, ROCkIn GPL-3.0). The author added GPL-3.0 the same day (commit `d701c053878867acc3d7145448a5ab0f6cf8030d`: `LICENSE` plus a README License section; GitHub detects GPL-3.0) and replied on the issue, which we then closed. Citation: the repository with its commit, as the author suggested; a paper is in preparation, so recheck before each release. The license of deposited models is decided when they are built: they also contain reference sequences, whose own terms apply (UniProt: CC BY 4.0).

**Placement confidence:** report clade counts with pplacer's likelihood weight ratio cutoff and the unplaced fraction; the cutoff and per-position accuracy are measured on simulated reads with known clades. Soft counts (likelihood weight summed per clade subtree) are the default; a placement agreeing with the DIAMOND best-hit clade is the confidence check.

---

## 2026-10-28 — Targeted assembly research stays outside envmetag

**Decision:** HMM-guided targeted assembly on an FM-index of reads is a separate research repository. envmetag provides its seeds (v0.2 hits) and baseline (read-based counts). The headline comparison is PathRacer (shipped with SPAdes 4.0); Xander and MegaGTA are compared through the published results of the 2019 gene-targeted assembly review on its datasets, not rebuilt.

**Why:** MegaGTA's last commit is 2016-06-16 and it depends on UCHIME (USEARCH, proprietary), RDPTools (Java) and per-gene Xander-format HMM resources; it is a comparator, not a component. PathRacer is maintained and directly tests graph search against index search.

**Sources:**

- Gene-targeted assembly review (Frontiers in Genetics, 2019) — https://doi.org/10.3389/fgene.2019.00957
- PathRacer in SPAdes 4.0 — https://github.com/ablab/spades/releases/tag/v4.0.0
- MegaGTA — https://github.com/HKU-BAL/megagta

---

## 2026-10-28 — Canonical-family table: roles, cycles, one marker per step

**Decision:** the table (`assets/cycdb/canonical_families.tsv`) is built by `dev/cycdb/build_canonical_families.py` from the audit tables and `dev/cycdb/curation_overrides.tsv`, in which every hand decision is one row with a reason and a source. It replaces the draft's `cycles` and `core_metabolism` columns with:

- `source_databases` (provenance only);
- `cycle`: `sulfur`, `methane` (methanogenesis, AOM, aerobic methane oxidation), `nitrogen`, `c1` (methylotrophy and other C1 compounds), `shared` (with `cycle_detail`, e.g. `methane;sulfur`) or `none`;
- `role`: `dissimilatory`, `assimilatory`, `transport`, `accessory` (needed by a cycle pathway but not specific to it: cofactors, chaperones, widespread electron-transfer complexes), `core` (central metabolism found in most genomes; its presence says nothing about a cycle process) or `other` (no cycle role, e.g. antibiotic resistance);
- `marker_step`: the one family reported per cycle step, in copies per genome equivalent (nitrogen: _amoA_, _nxrA_, _napA_/_narG_, _nirK_/_nirS_, _norB_, _nosZ_, _nrfA_, _nifH_, _hzsA_; sulfur: _dsrA_, _aprA_, _soxB_, _sqr_; methane: _mcrA_, _pmoA_/_mmoX_; plus _ureC_ for a separate ureolysis row). Families are never summed into a cycle total: summing would count multi-subunit enzymes several times and let long pathways outweigh one-gene steps;
- `group_cycle` (computed): where a marker read left unresolved within its ambiguity group is shown. It is set only when every member has that cycle and role `dissimilatory`; otherwise such reads appear only on the unresolved/ambiguous line;
- `selector`: a source family split by the ontology groups on each sequence's own headers (below);
- `header_evidence`: `insufficient` for families whose header ontology groups do not identify their sequences (next entry).

Families of every role stay in the search database as competitors: removing, say, the trimethoprim-resistance `dfrA` sequences would send their reads to `folA`.

Calls made in review (each with its reason in the overrides file):

- The source database's cycle is provenance, not biology: MCycDB carries _amoA_, _narG_, _nirK_/_nirS_, _nrfA_, _nxrA_, _napH_, _nrfH_ (nitrogen), SCycDB carries _comA_–_comE_ (coenzyme M biosynthesis: methane, accessory), and MCycDB _nod_ is `shared` methane;nitrogen. A check flags any family whose name marks another cycle's gene.
- Assimilatory sulfur genes (_cysDNCHJI_, _sir_, _sat_, _tauD_, _ssuD_, ...) are among SCycDB's largest families (_cysK_ 32,047 sequences, _cysE_ 21,382, _cysC_ 20,875 against _dsrA_ 5,453 and _aprA_ 307); they are `assimilatory`, `transport` or `core`, never headline.
- 39 MCycDB methylotrophy and C1 families (_mxa_, _xoxF_, _mau_, _mgs_, _mgd_, _hxl_, ...), _pqqA_–_F_ and the serine-cycle _mtkA_/_mtkB_ (47 in all) move to `c1`, so a methylotroph's _xoxF_ is not reported as methane cycling.
- Urease (_ureABC_): nitrogen, `assimilatory`, its own ureolysis row with _ureC_ as marker. In most bacteria it supplies nitrogen for growth and it is not a redox step; it is shown because ureolysis raises pH and drives carbonate precipitation (relevant to MIC), with the usual "presence is not activity" wording. NCyc lists it under organic degradation and synthesis.
- _nirB_/_nirD_: `assimilatory`, departing from NCyc, which lists them under dissimilatory nitrate reduction; _nrfA_ is the respiratory DNRA marker.
- Families collected with a broader COG are split by each sequence's own header: MCycDB _mtkA_ keeps its 48 K14067 sequences and _mtkB_ its 44 K08692 sequences, the rest (2,044 and 2,822, collected via the SucC/SucD COGs) become `sucC`/`sucD` (`core`), each pair in an ambiguity group; _acdA_ keeps its 144 arCOG01707 sequences and 10,188 acyl-CoA dehydrogenases (COG1960) move to `acyl_coa_dh` (`core`), as does all of _acdB_.
- _fpoL_/_M_/_N_ are `accessory`: they resemble complex I NuoL/M/N and Mrp antiporter subunits, and MCycDB's competitors include Nuo/Ndh but only 6 Mrp-type records.
- KOs that span different functions are never merged and always one ambiguity group: K10944–K10946, K00370/K00371, and K07235–K07237 (DsrEFH vs TusBCD).
- Same name, different gene systems: SCycDB _mccA_ is the octaheme cytochrome c sulfite reductase (13 of 15 sequences carry 7 CXXCH plus 1 CX15CH heme motifs, matching the structure in Hermann et al. 2015) and stays sulfur `dissimilatory`; SCycDB _mccB_ (1,238 sequences, no heme motifs) is the _B. subtilis_ cystathionine lyase of methionine-to-cysteine conversion (Hullo et al. 2007) and is `core`, grouped with _metB_/_metC_. The collision is written into both reasons so neither is "fixed" to match the other.

**Role required:** every canonical family needs a `role` row, so a family added by a database update fails the build instead of entering the headline. The 362 families that previously took `dissimilatory` by default were seeded as explicit rows marked "not individually reviewed"; 355 remain. The check fails if that count rises.

**Not yet resolved:** whether the large broad-COG families are the whole list (a sweep of families whose dominant header group is a different enzyme is planned); _hdrD_, _hdrE_ and _tmm_ cycles (source organisms of the SCycDB copies unchecked); _comB_ size (3,311); _mcl_ vs citrate lyase; a source for _betC_; MCycDB _mdh_ as K00093.

**Sources:**

- Lücker et al. 2010, PNAS 107:13479 (two NXR types) — https://pmc.ncbi.nlm.nih.gov/articles/PMC2922143
- Cao et al. 2018, eLife 7:e37439 (Hdr-like complex in sulfur oxidizers) — https://elifesciences.org/articles/37439
- Cort et al. 2008, J Mol Biol 382:692 (DsrEFH–TusBCD) — https://pmc.ncbi.nlm.nih.gov/articles/PMC2637153
- Grein, Pereira & Dahl 2010, J Bacteriol 192:6369 (DsrK related to HdrD) — https://pmc.ncbi.nlm.nih.gov/articles/PMC3008517
- Wu et al. 2022, PNAS 119:e2207190119 (CoM biosynthesis) — https://pmc.ncbi.nlm.nih.gov/articles/PMC9457059
- Stockdreher et al. 2014, J Biol Chem 289:12390 (TusA in _A. vinosum_) — https://pmc.ncbi.nlm.nih.gov/articles/PMC4007435
- Hullo et al. 2007, J Bacteriol 189:187 (MccA/MccB in _B. subtilis_; abstract) — https://doi.org/10.1128/jb.01273-06
- Hermann et al. 2015, Nature 520:706 (octaheme MccA sulfite reductase; abstract) — https://doi.org/10.1038/nature14109
- Tu et al. 2019, Bioinformatics 35:1040 (NCycDB categories) — https://academic.oup.com/bioinformatics/article/35/6/1040/5085377
- IUBMB EC 2.1.1.251 (MtsA/MtsB) — https://iubmb.qmul.ac.uk/enzyme/EC2/1/1/251.html

---

## 2026-10-28 — Shared sequences: assigned per sequence from header groups and similarity

**Decision:** `dev/cycdb/assign_shared_sequences.py` writes `assets/cycdb/sequence_assignments.tsv`: one row per sequence (md5 of the uppercase sequence) that carries more than one canonical family, plus the sequences moved by a split. `CYCDB_PREPARE` reads it so that no sequence keeps two family labels. In order:

1. all of a sequence's families are in one ambiguity group → that group;
2. shorter than 60 amino acids → unresolved (a fragment is never given a family, but stays in the search database as a competitor);
3. two lines of evidence, each of which decides or is silent:
   - **header**: the KO/COG on the sequence's own target headers matches exactly one candidate's signature (or several in one group). Silent when any candidate has `header_evidence = insufficient`;
   - **similarity**: DIAMOND blastp against header-confirmed, single-family references of the candidate families; candidates in one ambiguity group compete as one unit; decides when the best unit scores at least T times the runner-up, with T measured per family pair (below);
4. both decide and agree, or only one decides → that call; both decide and disagree, or neither decides → `unresolved:<a>|<b>`, which counts toward no family, group or cycle and is reported on the unresolved/ambiguous line, never dropped.

Pairs with the same role and cycle whose scores stay close (_cysK_/_cysM_, _metB_/_metC_/_mccB_, _narJ_/_narW_) are ambiguity groups instead: ambiguity there is a family-level property, and read-length fragments will not separate them either. They are moderately diverged paralogs, not near-identical sequences.

**Header groups alone are not enough evidence for Fe-S and other multi-domain families.** Similarity to header-confirmed references put the _rnfB_/_sudA_ and _porD_/_gs_K00266_ sequences in _rnfB_ and _porD_ (score ratio about 2) although their headers carry COG0493: the COG tags come from shared Fe-S/NADH-binding domains. For _cooF_, similarity agreed with the header call on 47 of 53 sequences and disagreed on 6. These three families have `header_evidence = insufficient`. Header calls agreed with similarity elsewhere: 226 _narB_ → _cysJ_ and 144 _narH_ → _narJ_ relabels were confirmed.

**Threshold, measured (leave-cluster-out, 2026-10-29):** `dev/cycdb/loo_threshold.py` took up to 300 header-confirmed references per family as queries (22,561 queries, 95 families) and searched them against the full reference set (157,220 sequences). Hits to the query and to members of its own family in its 95% cluster are left out (34,045 hits), so near-identical relatives cannot vouch for it; members of other families in that cluster stay, as they would compete for a real query. Clusters: MMseqs2 release 18-8cc5c, `easy-cluster --min-seq-id 0.95 -c 0.8` (116,569 clusters, largest 96 members). For every pair of canonical families that occur together on a sequence in `multi_family_sequences.tsv`, it finds the lowest score ratio (0.05 grid, 1.00–3.00) at which misassigned/placed ≤ 1%; a tie is never placed.

- **Which pairs:** all 128 co-occurring pairs, each on at least 20 queries (smallest 26). The pair set comes from the databases and the table only. Until 2026-10-29 it came from the assignments (pairs still unresolved after the header step), which made the result depend on itself: feeding the final assignments back in flipped 48 rows on every pass between two states (76 and 92 unresolved sequences). README step 6 now reruns steps 2–4 on the final assignments and requires byte-identical output.
- **Pooled:** at 1.0, 549 of 55,501 queries misassigned (0.99%, 99% placed); at 1.25, 187 of 53,282 (0.35%).
- **Above 1.25, with the share of queries placed at that threshold:**

  | Pair                | T    | Placed | Units                         |
  | ------------------- | ---- | ------ | ----------------------------- |
  | _nrfC_/_phsB_       | 2.4  | 9%     | both in `fes_subunit_cog0437` |
  | _fdhA_K00148_/_fdm_ | 2.15 | 11%    | different                     |
  | _hdrC1_/_hdrC2_     | 2.0  | 20%    | different                     |
  | _nao_/_nmo_         | 1.65 | 78%    | different                     |
  | _nrfC_/_psrB_       | 1.65 | 27%    | both in `fes_subunit_cog0437` |
  | _cysN_/_cysN_cysC_  | 1.6  | 26%    | different                     |
  | _cysK_/_cysM_       | 1.55 | 68%    | both in `cysK_cysM`           |
  | _fdhA_/_nasA_       | 1.3  | 97%    | both in `mo_bispgd_reductase` |
  | _nirA_/_sir_        | 1.3  | 64%    | both in `siroheme_cog0155`    |

- **Never under 1%** (similarity never decides): _dmsB_/_nrfC_, _nrfC_/_ttrB_, _gs_K00266_/_sudA_, _hdrA1_/_hdrA2_, _narB_/_nasA_. All five are inside one ambiguity group already, where members compete as one unit, so leave-cluster-out added no new group. In the first (leave-one-out) run, _mccB_/_metB_ never reached 1% and _mccB_/_metC_ needed 2.15; _mccB_ then joined _metB_/_metC_.
- **Group candidates, not grouped:** _fdhA_K00148_/_fdm_, _hdrC1_/_hdrC2_ and _cysN_/_cysN_cysC_ have the same role and cycle and separate only by placing 11–26% of queries. Only 17 database sequences carry one of these pairs (15 unresolved, 2 assigned to _cysN_cysC_ by similarity), so grouping changes little here; whether they are grouped is decided on the simulated controls at read length, with the other merge-or-not calls.
- **Sensitivity, 90% clusters** (93,977 clusters, largest 202; 102,427 hits left out): 3 of 128 thresholds change, none by more than 0.2 (_nao_/_nmo_ 1.65 → 1.85, _cooF_/_gs_K00266_ 1.05 → 1.1, _pfkA_/_pfp_ 1.0 → 1.05); pooled 426 misassigned at 1.05, 197 of 53,118 at 1.25. The 95% thresholds are used.
- **Mixed-family clusters:** 59 of the 95% clusters hold header-confirmed references of two families (111 at 90%), all in hard pairs. Twelve such pairs are already in one ambiguity group (most: _gs_K00266_/_sudA_ 17 clusters, _narB_/_nasA_ 7, _cysK_/_cysM_ 6, _nrfC_/_ttrB_ 5). Six are not: _fdhA_K00148_/_fdm_ (6 clusters), _cooF_/_gs_K00266_ (2), and one each for _cysN_/_cysN_cysC_, _cysJ_/_narB_, _fdhA_/_gs_K00266_ and _pfkA_/_pfp_. At 95% identity the two labels are either the same enzyme under two names or a mislabelled sequence; the cross-cycle cases (_cysJ_/_narB_, _cooF_/_gs_K00266_) are to be checked by hand before the simulated controls.
- **Hit lists:** a fixed hit count can cut off a competitor, so queries whose list was full were rerun: 18,655 of 22,561 returned the full 500 hits and were rerun with `-k 2000`; 10,808 of those were still full and were rerun with `--top 67`. The threshold table records, per pair, how many queries came from each run (`query_modes`); 121 of 128 pairs mix them.
- **Slightly conservative:** under `--top`, the leave-cluster-out floor is 0.34 × the best hit as DIAMOND reported it, which is usually the self-hit or a near-identical cluster member. After those are left out, the best remaining own-family hit is lower than a real neighbour would be, so ratios against an absent competitor come out lower than at assignment time, and the measured thresholds are somewhat stricter than the assignment step needs. Matching them exactly would mean searching a database with each query's cluster physically removed.

**Similarity search with `--top`:** step 4 now uses DIAMOND `--top 67` instead of `--max-target-seqs 500`, matching the read-level rule in CLAUDE.md. `--top` keeps every alignment within a percentage of the query's best score, with no count limit.

- **Semantics, tested 2026-10-29 on DIAMOND 2.1.10,** whose binary prints no option help (`blastp --help` is rejected). With `--top 10`, three queries returned 9, 2 and 5 hits, all at ≥ 0.907 × best: a percentage window, not a hit count.
- **Completeness:** compared with `-k` runs of the same queries (step 4 against `-k 500`, 807 queries; leave-one-out against `-k 2000`, 10,808 queries), no family's best score was lower in the `--top 67` run.
- **Fuzzy edge:** in bitscore the edge is fuzzy by about 0.001 × best. Families absent from `--top` scored at most 0.3299 × best; families present scored as low as 0.3288 × best. DIAMOND appears to apply `--top` to the raw score.
- **Floor:** a family absent from a cut list scores the bound it fell under, not 0: the window edge plus a margin (0.34 × best) for `--top`, the lowest reported score for a full `-k` list. Every candidate scores at least that floor, so "below the window" means the same whether or not DIAMOND reported the hit. Both `place_unresolved.py` and `loo_threshold.py` apply this, so thresholds are measured under the rule they are applied with. A ratio against the floor is at most about 2.94, so a measured threshold above 2.94 means similarity never decides that pair; the highest finite threshold measured is 2.4.
- **Effect of the old cap:** 580 of the 768 shared-sequence queries with hits had full 500-hit lists. None of the 26 similarity calls made against a runner-up scoring 0 was on a full list: the lowest-reported floor already covered those. The cap could only make ratios look smaller and silence calls, not invent them. Switching to `--top 67` changed no assignment.

**Ties and thin margins:** a measured threshold of 1.0 means any higher score decides; an exact tie never does (fixed 2026-10-29, after a _porD_/_sudA_ tie at 719 bits had gone to _porD_ by name order). Pairs measured on fewer than 20 queries use the stricter of their measurement and 1.25 (none are, at present); unmeasured pairs use 1.25. A floor on T (measured thresholds may only raise the 1.25 default) was simulated and rejected: it unresolved 45 more sequences but made 33 calls _more_ specific (28 `group:narJ_narW` → _narJ_, one `unresolved:nirK|nirS` → _nirS_), because a silent similarity leaves the header call to decide alone. Fourteen similarity decisions rest on a unit score ratio below 1.05, nearly all among Fe-S/NADH and Mo-bisPGD multi-domain families (_sudA_, _gs_K00266_, _fdhA_, _porD_, _dsrL_) and _narH_narY_/_narW_; most land in groups shown only on the unresolved line.

**Result (rebuilt from scratch 2026-10-29, leave-cluster-out thresholds, `--top 67`):** of 26,839 rows, 15,054 come from splits and 10,978 are structural groups. Of the other 807: 402 decided by both methods agreeing, 319 by similarity only, 10 by header only; 3 unresolved because the methods disagreed, 43 because neither decided, and 30 as fragments. 76 sequences on 49 labels stay unresolved. Leave-cluster-out, the all-pairs measurement and `--top` changed no assignment against the intermediate leave-one-out, `-k 500` run: the thresholds that decide cross-unit calls moved little, and the pairs whose thresholds rose most are inside groups.

**Reproducibility (2026-10-29):** the README commands, run from the pinned archives (SHA-256 checked) into a new directory, reproduced `canonical_families.tsv` byte for byte. DIAMOND 2.1.10 with the README settings (query chunks of 500, 250 and 100 at `--threads 2`) gave identical scores for every shared-sequence query common to the 2026-10-28 run. The README step-6 fixed-point check passed: steps 2–4 rerun on the final assignments gave byte-identical queries, references, similarity scores, thresholds and assignments. Against the 2026-10-28 file, `sequence_assignments.tsv` changed in two rows:

- **A stale threshold file:** the 2026-10-28 assignments had been written from leave-one-out thresholds scored before the _mccB_ merge, so the _cooF_/_nrfC_ pair was unmeasured and a _cooF_/_nrfC_/_ttrB_ sequence stayed unresolved; it is now in `fes_subunit_cog0437`.
- **The tie above:** the _porD_/_sudA_ tie became unresolved.

**Caveat:** This separates **database sequences**, which are full-length proteins. Reads are 30–50 amino acids, and many families that separate here won't separate at read level. That's the job of the planned simulation, so these assignments mark which family a sequence belongs to, not which reads can be told apart.

**Provisional:** the 60-aa minimum length (chosen to catch fragments shorter than about two reads; to be revisited on the simulated controls, which are small) and the 1.25 default for unmeasured pairs.

---

## 2026-10-28 — Full-depth showcase runs do not fit this workstation; SingleM memory at depth

**Decision:** the showcase report is built from 5M-pair subsamples of the two full samples (seqtk 1.4 `sample -s 20261028`, fractions 0.0689 and 0.1654; mates verified to stay paired by read name). Full-depth runs belong on a larger machine.

**Evidence:** at full depth (72.6M and 30.2M pairs), `SINGLEM_PIPE` on `apb_enrichment` was killed by its container's 4 GB limit (`constraint=CONSTRAINT_MEMCG`, DIAMOND inside SingleM at 1.87 GB RSS) after about 5 hours. SingleM caught the kill and exited 1, so the template's retry-with-more-memory (exit codes 130–145) did not trigger. A second attempt at 7 GB, and a later 4-thread DIAMOND job, took down the 8–10 GB WSL VM. At 5M pairs every task fit its default resources (20 of 20 succeeded).

**To do (v0.2):** retry `SINGLEM_PIPE` on memory exhaustion even when SingleM exits 1 (detect the kill in its log), and size its memory from a deep run on a larger machine.

---

## 2026-10-28 — First real-data check of SingleM's prokaryotic fraction (provisional)

**Finding:** on the 5M-pair `apb_enrichment` showcase sample, SingleM's `prokaryotic_fraction` reports 58.4%, but at least ~73% of the reads are prokaryotic. The headline number is at least ~15 points low on this sample. The cause of the remaining ~27% is open.

**Evidence (2026-10-28):**

- Host DNA is ruled out: SingleM runs before host removal, and Hostile removed 254 of 9,908,760 reads.
- A genome-size error is ruled out as the main cause: _S. nakayamae_ has no species entry in the GlobDB r232 metapackage's `taxon_genome_lengths` table, so SingleM used the _Sporolactobacillus_ genus mean (3.34 Mbp); the type-strain genome (GCF_900113325.1) is 3.54 Mbp, about 6% larger.
- bowtie2 (pipeline container, default end-to-end) mapped 67.8% of the clean reads to the _S. nakayamae_ and _C. luticellarii_ type strains (GCF_900113325.1, GCF_002995845.1): 61.5% and 6.3%. If SingleM's 58.4% were right, about 54% should map (0.584 × the two species' 84.5% + 8.3% of coverage).
- SingleM 0.21.4 on the 1,630,967 unmapped pairs gives 16.9% prokaryotic, mostly _Clostridium_ spp. with no reference genome here: about 5.4% of all reads.

**Why the rest stays open:** SingleM counts single-copy markers, and those were mapped away with the rest of each genome. Reads from strain-specific genes, or reads too divergent for end-to-end alignment, look marker-free although they are prokaryotic; phage, plasmid or contamination would look the same.

**Consequences:**

- The report gets a "less reliable in simple communities" caveat, shown when a few taxa hold most of the coverage. SingleM's own warning cannot fire here, because 94–98% of coverage is resolved to species. SingleM's documentation says the estimate is least reliable in simple communities.
- Next check: assemble the unmapped pairs (MEGAHIT), split contigs by coverage and GC, and identify the largest by BLAST. Contigs at the _S. nakayamae_ coverage (~170×) would mean strain DNA and a wrong headline; a separate cluster would be a finding about the sample.

**Sources:**

- SingleM `prokaryotic_fraction` — https://wwood.github.io/singlem/tools/prokaryotic_fraction
- _S. nakayamae_ ATCC 700379 — https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_900113325.1/
- _C. luticellarii_ DSM 29923 — https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_002995845.1/
