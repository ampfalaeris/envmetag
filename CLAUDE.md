# envmetag

Shotgun metagenomic profiling of environmental samples, with curated marker genes for sulfur, methane, and nitrogen cycling and hydrocarbon degradation. Built for remediation sites, microbially influenced corrosion (MIC), and general environmental monitoring. Public portfolio project: code quality, tests, and documented decisions matter as much as features.

## Roadmap (build in this order; don't jump ahead)

1. **v0.1**: read preprocessing → SingleM profiling → HTML report. Typed, tested, CI green.
2. **v0.2**: assembly → binning → CheckM2. GTDB-Tk optional and off by default (R232 needs ~140 GB RAM).
3. **v0.3**: curated marker-gene module (CANT-HYD, SCycDB, MCycDB, NCycDB), read-based abundance normalized to genome equivalents.
4. **v0.4**: write index files that feed nf-core/funcscan (`sample,fasta[,protein,gbk[,gff]]`).

Centrifuger is an optional cloud-only profile (comprehensive indexes need tens of GB of RAM). SingleM runs locally (<4 GB RAM by default).

## Environment

- WSL2; repo lives in the Linux filesystem (`~/...`), never `/mnt/c` (executable bits and Docker mounts break there).
- Nextflow `>=26.10.0` (`manifest.nextflowVersion = '!>=26.10.0'`). Strict syntax is the default parser.
- Template: nf-core/tools 4.2.0, custom prefix `ampfalaeris`, `is_nfcore: false`. Not an nf-core pipeline; never call it `nf-core/envmetag`.
- nf-test 0.9.4 in CI. Its handling of typed processes and record inputs is **unverified**; check before relying on it.
- `uv` manages Python for local development of `bin/` scripts only. It does not provide runtime dependencies inside pipeline tasks.

## Commands

```bash
nextflow lint .                                  # run before every commit; must be error-free
nf-test test                                     # all tests
nf-test test modules/local/<name>/tests/         # one module
nextflow run . -profile test,docker --outdir results
nextflow run . -profile test -stub --outdir results_stub
nf-core pipelines lint                           # template checks; some nf-core-only rules are disabled in .nf-core.yml
```

## Nextflow language rules

- All new scripts start with `nextflow.enable.types = true`. A typed script cannot also contain legacy process or workflow definitions.
- Never use `PROCESS.out.x` or `WORKFLOW.out.x`. Assign the call: `def fq = FASTP(samples)`, then `fq.reads`.
- Carry samples as **records** with named fields, not positional tuples or loose meta maps. Declare record types for every data shape that crosses a process boundary.
- Annotate types on every workflow `take:` input, process input/output, and the `params` block.
- Static-typing operator semantics: `map` does not drop nulls; `join` requires `by:`; `mix` takes one argument per call. Avoid `set`, `tap`, implicit `it`, `flatten`, and `.out`. `distinct` and `collectFile` on a `Value` failed typed lint in this repo.
- **Legacy nf-core modules** (untyped) are allowed. Call them through a thin adapter: record → `tuple(meta, files)` before the call, outputs back to records immediately after. That boundary is not type-checked, so test it.
- `workflows/envmetag.nf` still has the template's legacy software-versions/MultiQC block. Leave it untyped until it is deliberately rewritten. Don't "fix" it piecemeal.
- Pipeline outputs go through the workflow `output {}` block with **index files** (CSV/JSON). Downstream steps and the report read index files, never by globbing output directories.

## Module conventions

- Local modules: one process per directory, `modules/local/<name>/main.nf`, each with `tests/main.nf.test`.
- Tool arguments live in `conf/modules.config` via alias-specific `withName` selectors and `ext.args` / `ext.prefix` closures. Never hardcode tool arguments in module files. (Verified: `ext.*` closures work with typed processes and can read record input fields.)
- Includes are padded so the `}` braces align in a column.
- Logic beyond calling a tool goes in `bin/` scripts, not in module script blocks. `bin/` scripts: shebang, executable, standard library first; any third-party dependency must be in that process's container.
- Pin every container (BioContainers or Seqera Containers) to an exact version.

## Testing

- Every module and subworkflow gets nf-test coverage before it is wired into the main workflow.
- **Stubs must be realistic**: create every declared output with the real filename and minimally valid content (correct headers for TSVs), so downstream parsers are exercised in `-stub` runs. A bare `touch` is not acceptable.
- Snapshot `md5` only for deterministic outputs. For assemblers and other non-deterministic tools, snapshot properties: file exists, line/record counts, header line.
- Test data is tiny and public. The marker-gene module needs **positive and negative controls**: reads simulated from genomes known to carry target markers (e.g., *bssA*, *dsrAB*) plus one genome carrying neither.
- CI runs on PRs from `dev` into `master`. Work on `dev`.

## Failure handling

Fail loudly; never degrade silently. Validate inputs against schemas, error on empty or malformed outputs, and use explicit checks (e.g., `failOnMismatch` on joins). An unexplained empty result is a bug.

## Data, licensing, and provenance

- Public data only. Reference datasets by accession, download them at runtime, credit the original study in the README, and never commit reads.
- Check and record the license and redistribution terms of every reference database (CANT-HYD, SCycDB, MCycDB, NCycDB, SingleM metapackages, GTDB) before bundling anything.
- All code is written fresh for this repository. Do not paste in or adapt code, configs, or report layouts from other private pipelines.

## Documentation

- `DECISIONS.md` (repo root): add a dated entry for every non-trivial design choice, giving the decision, why, the evidence (what was tested, on which version), and public sources. Read it before proposing changes that touch an existing decision. It is not auto-imported, to keep context small.
- Update `CHANGELOG.md` and `docs/output.md` alongside any change to outputs.
- Report text states what numbers mean: read-based percentages are labelled as such, unclassified reads are always shown, and presence of a marker gene is never presented as proof of activity or corrosion.
