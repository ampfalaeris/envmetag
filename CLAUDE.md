# envmetag

Shotgun metagenomic profiling of environmental samples, with curated marker genes for sulfur, methane, and nitrogen cycling and hydrocarbon degradation. Built for remediation sites, microbially influenced corrosion (MIC), and general environmental monitoring. Public portfolio project: code quality, tests, and documented decisions matter as much as features.

## Roadmap (build in this order; don't jump ahead)

1. **v0.1 (released as `0.1.0`, 2026-10-28)**: read preprocessing → SingleM profiling → HTML report.
2. **v0.2**: read-based marker quantification with SCycDB, MCycDB and NCyc, combined into one DIAMOND database through a curated canonical-family table, searched with `blastx` on the clean reads. Each read is called target / homolog / ambiguous from the target-vs-homolog score margin and per-family thresholds derived from the database itself, then assigned to a family or an ambiguity group. Abundance is normalized to genome equivalents from SingleM `prokaryotic_fraction` and checked with a single-copy calibrator. Read-based counts are the primary quantification.
3. **v0.2.x**: ROCkOut models for a short list of markers where homolog or clade confusion matters most: _dsrAB_ (reductive vs oxidative, with placement), _mcrA_ (methanogen vs ANME), _amoA_ vs _pmoA_ (one KEGG KO, K10944), _bssA_/_assA_ (vs other glycyl radical enzymes; no read-level database covers them). ROCkOut is GPL-3.0 from commit `d701c05` (2026-10-29); pin that commit or later.
4. **v0.3**: assembly (MEGAHIT) → gene calls (pyrodigal) → CANT-HYD (`hmmsearch --cut_tc`) and the cycling databases on predicted proteins; optional PCycDB (ORF-level); binning → CheckM2; GTDB-Tk optional and off by default (R232 needs ~140 GB RAM). Contig-based calls are supporting evidence, not the primary number.
5. **v0.4**: index files that feed nf-core/funcscan (`sample,fasta[,protein,gbk[,gff]]`); needs v0.3 contigs.

**Out of scope for this repository:** HMM-guided targeted assembly on an FM-index of reads. That is a separate research project; envmetag's v0.2 hits are its seeds and its read-based counts are its baseline.

Order changed 2026-10-26 (markers before assembly) and 2026-10-28 (CANT-HYD and PCycDB to v0.3; ROCkOut short list as v0.2.x); see DECISIONS.md.

Centrifuger is an optional cloud-only profile (comprehensive indexes need tens of GB of RAM). SingleM runs locally (<4 GB RAM by default).

- SingleM uses the GlobDB r232 metapackage (`--metapackage`), downloaded at runtime: 3.8 GB compressed, 17 GB extracted. Never bundled; CC BY-SA 4.0 with attribution.
- SingleM runs on the **fastp-trimmed** reads, before PhiX and host removal (DECISIONS.md, 2026-10-26): raw-read adapter sequence hits adapter-contaminated GlobDB proteins, and the host reads stay in the prokaryotic-fraction denominator. fastp must not quality-trim (`--cut_*`); SingleM's docs warn that short, quality-trimmed reads fail. Clean (PhiX/host-removed) reads feed assembly and the marker module.
- SingleM names samples from the forward-read filename; stage files as `${id}_R1...` or rewrite the column, and test that `sample == id`.
- `test` profile (CI) = tiny reads + a 3-marker GlobDB CI metapackage (rplB, rplC, rpsB; no nucleotide SDB; ~1 GB) with `--assignment-method diamond` set in `conf/test.config`. It tests plumbing and formats, not biology (genus level only). Assert on known genera, headers, `sample == id`, and the profile md5 (deterministic); compare OTU tables only after sorting (row order varies).
- The CI metapackage is a GlobDB adaptation: its own Zenodo record under CC BY-SA 4.0, separate from the CC BY 4.0 test-reads record, stating the changes and the SingleM version that built it. Rebuild it if SingleM's metapackage format changes.
- `test_full` = 1M-pair reads + full GlobDB with the default assignment method (too big for free runners: 14 GB disk). Run it before every release (locally or via a manual larger-runner job), assert the known species, and note the run in `CHANGELOG.md`. It is the only test of the default smafa + nucleotide-SDB path.

## Environment

- WSL2; repo lives in the Linux filesystem (`~/...`), never `/mnt/c` (executable bits and Docker mounts break there).
- Nextflow `>=26.10.0` (`manifest.nextflowVersion = '!>=26.10.0'`). Strict syntax is the default parser.
- Template: nf-core/tools 4.2.0, custom prefix `ampfalaeris`, `is_nfcore: false`. Not an nf-core pipeline; never call it `nf-core/envmetag`.
- nf-test 0.9.4 in CI and locally (`~/.local/bin/nf-test`). Typed processes, typed subworkflows, record inputs, snapshots, `-stub`, and legacy nf-core modules through the record adapter all verified 2026-10-25 (see DECISIONS.md). In assertions, `path(x)` is a plain Java `Path`: use `.fileName.toString()`, not `.name`.
- `uv` manages Python for local development of `bin/` scripts only. It does not provide runtime dependencies inside pipeline tasks.
- Container profiles only: `-profile conda` and `mamba` stop at startup, because local modules have no conda environments (DECISIONS.md, 2026-10-28). CI tests Docker on every PR and Singularity only on PRs into `master`.
- Releases: tags without a "v" (`0.1.0`), matching the MultiQC report link; the GitHub release title may read `v0.1.0`. Merge release PRs with a merge commit, then fast-forward `dev` to `master`.

## Commands

```bash
nextflow lint .                                  # run before every commit; must be error-free
nf-test test                                     # all tests
nf-test test modules/local/<name>/tests/         # one module
nextflow run . -profile test,docker --outdir results
nextflow run . -profile test,docker -stub --outdir results_stub   # stubs still run version commands, so they need a container
nf-core pipelines lint                           # template checks; some nf-core-only rules are disabled in .nf-core.yml
```

## Nextflow language rules

- All new scripts start with `nextflow.enable.types = true`. A typed script cannot also contain legacy process or workflow definitions.
- Never use `PROCESS.out.x` or `WORKFLOW.out.x`. Assign the call: `def fq = FASTP(samples)`, then `fq.reads`.
- Carry samples as **records** with named fields, not positional tuples or loose meta maps. Declare record types for every data shape that crosses a process boundary, all in `types/main.nf`, and `include` them where used (record types are script-scoped).
- Never give a local variable the same name as an `emit:` output. Lint passes, but the run fails with `Missing workflow output parameter`.
- Annotate types on every workflow `take:` input, process input/output, and the `params` block.
- Static-typing operator semantics: `map` does not drop nulls; `join` requires `by:`; `mix` takes one argument per call. Avoid `set`, `tap`, implicit `it`, `flatten`, and `.out`. `distinct` and `collectFile` on a `Value` failed typed lint in this repo.
- **Legacy nf-core modules** (untyped) are allowed. Call them through a thin adapter: record → `tuple(meta, files)` before the call, outputs back to records immediately after. That boundary is not type-checked, so test it.
- `workflows/envmetag.nf` still has the template's legacy software-versions/MultiQC block. Leave it untyped until it is deliberately rewritten. Don't "fix" it piecemeal.
- Pipeline outputs go through the workflow `output {}` block with **index files** (CSV/JSON). Users and downstream pipelines (e.g. funcscan) read index files, never by globbing output directories. Steps inside the same run, including the report, take records from channels: the index files are written when outputs are published, and no channel carries them.

## Module conventions

- Local modules: one process per directory, `modules/local/<name>/main.nf`, each with `tests/main.nf.test`.
- Tool arguments live in `conf/modules.config` via alias-specific `withName` selectors and `ext.args` / `ext.prefix` closures. Never hardcode tool arguments in module files. (Verified: `ext.*` closures work with typed processes and can read record input fields.)
- Includes are padded so the `}` braces align in a column.
- Logic beyond calling a tool goes in `bin/` scripts, not in module script blocks. `bin/` scripts: shebang, executable, standard library first; any third-party dependency must be in that process's container.
- Pin every container (BioContainers or Seqera Containers) to an exact version.

## Marker module (v0.2) rules

Database preparation (`CYCDB_PREPARE`, once per database version, cached):

- Download SCycDB, MCycDB and NCyc from **pinned commit hashes**. Never bundle or redistribute them (no license; see Data, licensing, and provenance).
- SCycDB and MCycDB ship as split zips. Standard `unzip` produces a **partial** FASTA with only error messages, and Python's `zipfile` refuses the archive. Inflate each entry from the central directory, then **check size and CRC32 against the archive's own record, and the record count**; fail on any mismatch.
- SCycDB: `SCycDB_2020Mar.faa` + `id2gene.2020Mar.map` (the 2021 map is a strict subset).
- NCyc: sequences and targets from the **2019Jul pair** (`NCyc_100_2019Jul.7z` + `id2gene.map.2019Jul`, the authors' cleanup). Its headers are bare IDs, so `decoy_for` and orthology groups come from `NCyc_100.faa.gz` headers; check that every ID has the identical sequence in both files.
- Target status comes from the gene map. `decoy_for` and the orthology group of homologs come from FASTA headers (`[description=<gene> homolog ontology=<group> source=<db>]`). A sequence listed in the map is a target even if a duplicate record of it, or its only header, says homolog.
- Collapse duplicate IDs (all duplicates found have identical sequences). Drop records with no ID and count them (MCycDB has 24). The audit counts are test assertions, so any change in them fails.
- Combined database: prefix IDs by source (`scyc|`, `mcyc|`, `ncyc|`; 29 IDs occur in two databases with different sequences), collapse **identical sequences**, not IDs, and merge labels; **target wins over homolog** across sources.
- Families are joined through a curated **canonical-family table** in the repository, keyed by `(source_db, source_family)`, never by gene name alone (MCycDB `mdh` is methanol dehydrogenase, SCycDB `mdh` is malate dehydrogenase). It gives each family a canonical family (KO-level where a KO exists), an ambiguity group, a `cycle`, a `role` (`dissimilatory`, `assimilatory`, `transport`, `accessory`, `core`, `other`) and, for one family per cycle step, a `marker_step`. It is built by `dev/cycdb/build_canonical_families.py` from `dev/cycdb/curation_overrides.tsv` (every hand decision with a reason and source; see `dev/cycdb/README.md`), and `dev/cycdb/check_canonical_families.py` must pass on the checked-in files. A shared KO is a candidate merge, except for KOs that span different functions: K10944–K10946 (methane and ammonia monooxygenase), K00370/K00371 (nitrate reductase and nitrite oxidoreductase) and K07235–K07237 (DsrEFH and TusBCD).
- Write one annotation table: `seq_id, source_db, status, families, canonical_families, ambiguity_group, decoy_for, ontology_group, conflict_flag`. A sequence may carry a **set** of families; `assets/cycdb/sequence_assignments.tsv` (by sequence md5) resolves it to one family, one group, or an `unresolved:` label, so no sequence keeps two family labels.
- Per-family thresholds (target vs homolog) and per-group thresholds (family vs family) are generated in this step and stored with a hash of the database; the search step refuses thresholds whose hash does not match.
- The search database is built from the source databases, never from the curation reference sets (`dev/cycdb/place_unresolved.py prepare`). Sequences the fusion rule leaves out of those sets stay in the search database under their `sequence_assignments.tsv` or table label, as competitors.

Search and quantification:

- DIAMOND `blastx` with `--top <X>`, not `-k 1`, so the best target, best homolog, and best hit from each competing family are all available.
- Each read is target / homolog / ambiguous. Ambiguous counts are reported per family and never assigned in the primary counts. A model-based redistribution (EM over candidate families) may be reported **only as a separate estimate**, labelled experimental (not yet checked against the simulated controls), with an interval, beside the primary counts and the unresolved/ambiguous line, never in place of them.
- A target read whose best hits span several canonical families goes to the best family only if its margin clears the group threshold; otherwise it counts once for the ambiguity group. A read is never counted for two families. If the families span cycles (e.g. _nirA_/_sir_), the read counts toward neither cycle's total.
- Count each **fragment** once (mates share IDs via Hostile `--casava`); never add totals across cycles.
- The cycle headline is one marker per step (`marker_step`), in copies per genome equivalent; families are never summed into a cycle total. Other roles (`assimilatory`, `transport`, `accessory`, `core`, `other`) are reported separately and kept out of the headline. Reads on `unresolved:` labels and group-only reads are always shown on an unresolved/ambiguous line.
- The quantification unit and mate handling must match SingleM's coverage convention. A single-copy calibrator gene run through the same steps must give about 1 copy per genome equivalent; the report shows it per sample.
- Decide Hostile `--reorder` before any marker output is md5-snapshotted.

## Testing

- Every module and subworkflow gets nf-test coverage before it is wired into the main workflow.
- **Stubs must be realistic**: create every declared output with the real filename and minimally valid content (correct headers for TSVs), so downstream parsers are exercised in `-stub` runs. A bare `touch` is not acceptable.
- Snapshot `md5` only for deterministic outputs. For assemblers and other non-deterministic tools, snapshot properties: file exists, line/record counts, header line.
- Test data is tiny and public. The marker module needs **simulated controls with known answers**: reads from genomes known to carry target markers (_dsrAB_, _mcrA_, a nitrogen gene), at least one genome carrying their close homologs but not the targets, one genome carrying neither, a single-copy calibrator gene, and genomes for the ambiguity groups that matter most (COG0437 Fe-S subunits, _nirA_/_sir_, _sudA_/_gltD_, and _dsrL_ against the GltD-like families: DsrL shares their COG0493 domain family, and _dsrL_/_sudA_ never co-occur, so no full-length threshold exists for that pair). Thresholds, merge-or-not, group calls, and the calibrator check are all decided on these controls.
- The CI marker database is a small set of target and homolog sequences fetched from UniProt by accession (CC BY 4.0), not a subset of the cycling databases' files.
- CI runs on PRs from `dev` into `master`. Work on `dev`.

## Failure handling

Fail loudly; never degrade silently. Validate inputs against schemas, error on empty or malformed outputs, and use explicit checks. Typed `join` rejects `failOnMismatch` (only `by` and `remainder`) and silently drops unmatched items, so every join is `join(other, by: 'id', remainder: true)` followed by an inline `map` that calls `error(...)` when a field from either side is null. Call `error()` inline, not from an included function: from a function the message is hidden behind `InvocationTargetException`. Make a process output the `join` receiver (`proc_out.join(take_input, ...)`): nf-test feeds subworkflows legacy channels, which reject a typed channel as the join argument. An unexplained empty result is a bug.

## Data, licensing, and provenance

- Public data only. Reference datasets by accession, download them at runtime, credit the original study in the README, and never commit reads.
- All code is written fresh for this repository. Do not paste in or adapt code, configs, or report layouts from other private pipelines.
- License status of every external resource (check before bundling, containerizing, or depositing anything derived from it):

| Resource                | License                                                                                 | What we may do                                                                                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GlobDB r232 metapackage | CC BY-SA 4.0                                                                            | Download at runtime; derived subsets published under CC BY-SA 4.0 with attribution                                                                                                                 |
| CANT-HYD HMMs           | GPL-3.0                                                                                 | Bundle the HMM file with attribution and GPL notice                                                                                                                                                |
| SCycDB, MCycDB, NCyc    | **none stated**                                                                         | Download at runtime only; no redistribution, including CI subsets. CI subsets are built from UniProt accessions (CC BY 4.0) instead. License requested from the authors 2026-10-28 (no reply yet). |
| PCycDB                  | none stated; database file location unknown                                             | Not used until both are resolved                                                                                                                                                                   |
| KEGG REST API           | academic use by academic users only                                                     | Never called by the pipeline; the repository stores KO identifiers only, not KEGG names or pathway text                                                                                            |
| Pfam / InterPro data    | CC0 1.0 (InterProScan software: Apache; bundled tools and member signatures may differ) | Use Pfam data (e.g. domain coordinates for fusion proteins, v0.2.x); check each bundled tool's license before containerizing InterProScan                                                          |
| ROCkIn                  | GPL-3.0                                                                                 | Use for curating reference sets                                                                                                                                                                    |
| ROCkOut                 | GPL-3.0 (from commit `d701c05`, 2026-10-29)                                             | Container pinned to a licensed commit, with attribution and GPL notice; cite the repository with its commit (paper in preparation). Model license decided at deposit (reference data terms apply)  |
| Read sets from ENA/SRA  | INSDC: no redistribution restrictions                                                   | Subsample and deposit with credit                                                                                                                                                                  |

## Documentation

- `DECISIONS.md` (repo root): add a dated entry for every non-trivial design choice, giving the decision, why, the evidence (what was tested, on which version), and public sources. Read it before proposing changes that touch an existing decision. It is not auto-imported, to keep context small.
- Update `CHANGELOG.md` and `docs/output.md` alongside any change to outputs.
- Report text states what numbers mean: read-based percentages are labelled as such, unclassified reads are always shown, and presence of a marker gene is never presented as proof of activity or corrosion.
