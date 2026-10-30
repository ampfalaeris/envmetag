# Cycling-database curation

Curation tools for the canonical-family table, `assets/cycdb/canonical_families.tsv`, and the per-sequence assignments, `assets/cycdb/sequence_assignments.tsv`. They are not pipeline steps: the pipeline reads only the checked-in files. CI cannot rebuild them, because SCycDB, MCycDB and NCyc have no license and are never stored here (see the license table in `CLAUDE.md`), so CI runs `check_canonical_families.py` on the checked-in files instead. The design and its evidence are in `DECISIONS.md` (2026-10-28 entries).

Every hand decision lives in `curation_overrides.tsv`, one value per row, with a reason and a source:

| scope       | key                        | fields                                                                                                |
| ----------- | -------------------------- | ----------------------------------------------------------------------------------------------------- |
| `row`       | `<db>:<source_family>`     | `canonical_family`                                                                                    |
| `split`     | `<db>:<source_family>`     | `keep_ontologies`, `rest_canonical`                                                                   |
| `canonical` | canonical family           | `ko`, `ambiguity_group`, `cycle`, `cycle_detail`, `role`, `marker_step`, `header_evidence`, `fusion`  |
| `link`      | `<canonical>\|<canonical>` | `resolution` (`sequence`: shared sequences are assigned per sequence by `assign_shared_sequences.py`) |

Values:

- `cycle`: `sulfur`, `methane` (methanogenesis, AOM, aerobic methane oxidation), `nitrogen`, `c1` (methylotrophy and other C1 compounds), `shared` (with `cycle_detail`, e.g. `methane;sulfur`) or `none`.
- `role`: `dissimilatory`, `assimilatory`, `transport`, `accessory` (needed by a cycle pathway but not specific to it: cofactors, chaperones, widespread electron-transfer complexes), `core` (central metabolism found in most genomes) or `other` (no cycle role, e.g. antibiotic resistance). Families of every role stay in the search database as competitors.
- `marker_step`: the one family reported for a cycle step, in copies per genome equivalent. Families are never summed into a cycle total.
- `group_cycle` (computed): where a marker read left unresolved within its ambiguity group is shown. It is set only when every member has that cycle and role `dissimilatory`; otherwise such reads appear only on the unresolved/ambiguous line.
- `split`: sequences of the source family whose own target headers carry a `keep_ontologies` group keep the row's canonical family; the rest go to `rest_canonical`. The table then has two rows for the source family (`selector` = `ontology:<groups>` or `rest`).
- `header_evidence = insufficient`: header ontology groups do not identify this family's sequences (multi-domain Fe-S proteins), so header evidence is ignored for any sequence carrying it.
- `fusion = declared`: the family is itself a fusion of two domains (e.g. _cysN_cysC_), so the fusion rules below never apply to it.

Fusion rules (DECISIONS.md, shared sequences): a sequence at least 1.25 × the median reference length of a family, whose own headers (homolog headers included) carry another candidate family's signature COG/KO, is a fusion. `place_unresolved.py prepare` leaves such sequences out of the reference sets (`--dropped` lists them), and `assign_shared_sequences.py --refs` labels a shared sequence that is a fusion for all its candidates `unresolved:` (basis `fusion`). Both change only the curation reference sets and the assignments; every sequence stays in the search database.

Defaults, used where no override applies: the canonical family is the source family's own name (same-name families in different databases merge); the KO comes from a `-K#####`/`_K#####` name suffix or from at least 5 target headers agreeing at 80% or more; `cycle` is the source database's cycle, or `none` for roles `core` and `other`. `role` has no default: every canonical family needs a `role` row, so a family added by a database update fails the build instead of entering the headline. Rows with `role = dissimilatory` may leave `reason` empty; 362 were seeded on 2026-10-28 from the earlier default and say so in `source`, and 355 remain. `check_canonical_families.py --overrides` fails if that count rises.

`build_canonical_families.py` fails instead of writing the table when an override is unused or names an unknown family, when a canonical family has no role, when a canonical family drawn from databases of different cycles has no `cycle`, or when two canonical families share 10 or more sequences (and at least 1% of the smaller family) or a KO but are neither in one ambiguity group nor listed as a resolved link.

`assign_shared_sequences.py` writes one row per sequence (md5 of the uppercase sequence) that carries more than one canonical family, or that a split moved. Its docstring gives the rule: structural group, fragment, fusion, then header and similarity evidence, each deciding or silent, with every outcome counted.

## Rebuild

Database versions are pinned by commit (DECISIONS.md, 2026-10-28):

| Database | Repository                   | Commit                                     |
| -------- | ---------------------------- | ------------------------------------------ |
| SCycDB   | github.com/qichao1984/SCycDB | `f107be1aec71dd87cafb5e0eb9fdbb0c7f3ffad6` |
| MCycDB   | github.com/qichao1984/MCycDB | `ceba218716fa07f016ab91c7575dae68a0e08c6e` |
| NCyc     | github.com/qichao1984/NCyc   | `4ee9aad986264d79e0763933b4d05b05c31125fe` |

SCycDB and MCycDB FASTAs ship as split zips; extract them with `splitzip_extract.py`, which checks each entry's size and CRC32 against the archive's own record. NCyc's `NCyc_100_2019Jul.7z` is read with `py7zr` (`uv run --with py7zr==0.22.0`). The similarity steps use DIAMOND 2.1.10 and MMseqs2 release 18-8cc5c (`mmseqs-linux-avx2.tar.gz`, SHA-256 `bd9b0234da5949ad528d5b5f9ea4cda9c1e23dce14b46c0791d4d919a76e61ce`), both static release binaries. On a small machine, run DIAMOND in chunks of a few hundred queries with `-b 0.1 -c 1` and a memory cap (`ulimit -v`); a whole-set run took down an 8 GB WSL VM. The checked-in files were rebuilt from scratch on 2026-10-29 (assignments rewritten 2026-10-30 from the same hits, with `--refs`) with chunks of 500 (step 3, first search), 250 (step 3, `-k 2000` rerun) and 100 (`--top 67` runs) queries, `--threads 2`, under `ulimit -v 2500000` (DECISIONS.md, 2026-10-28, shared sequences). MMseqs2 clustering peaked at 1.1 GB.

`T` points at the checked-in files, so a rebuild overwrites them; check the result with `git diff`, or set `T` to another directory and compare.

```bash
D=~/envmetag-dbs/cycdb   # pinned checkouts and extracted FASTAs
A=$D/audit               # output directory
P=$A/placement           # similarity work files
S=( --db SCycDB $D/extracted/SCycDB/SCycDB_2020Mar.faa $D/SCycDB/id2gene.2020Mar.map )
M=( --db MCycDB $D/extracted/MCycDB/MCycDB_2021.faa    $D/MCycDB/id2gene.map )
N=( --db NCyc   $D/extracted/NCyc_2019Jul/NCyc_100_2019Jul.faa $D/NCyc/data/id2gene.map.2019Jul )
NH=$D/extracted/NCyc/NCyc_100.faa   # NCyc headers (the 2019Jul FASTA has bare IDs; sequences are identical per ID)
H=( --db SCycDB ${S[2]} ${S[3]} --db MCycDB ${M[2]} ${M[3]} --db NCyc $NH ${N[3]} )   # header FASTAs + maps
T=../../assets/cycdb
mkdir -p $P

# 1. audit tables and the canonical-family table
python3 -I cycdb_overlap.py "${S[@]}" "${M[@]}" "${N[@]}" --outdir $A
python3 -I cycdb_family_summary.py \
  --db SCycDB ${S[2]} ${S[2]} ${S[3]} --db MCycDB ${M[2]} ${M[2]} ${M[3]} --db NCyc ${N[2]} $NH ${N[3]} \
  --summary $A/families.tsv --same-name $A/same_name.tsv
python3 -I cycdb_family_pairs.py --multi $A/multi_family_sequences.tsv \
  --db SCycDB ${S[2]} ${S[3]} --db MCycDB ${M[2]} ${M[3]} --db NCyc $NH ${N[3]} --out $A/family_pairs.tsv
python3 -I build_canonical_families.py $A/families.tsv $A/family_pairs.tsv curation_overrides.tsv $T/canonical_families.tsv

# 2. header-only assignments, then similarity queries and header-confirmed references
python3 -I assign_shared_sequences.py --multi $A/multi_family_sequences.tsv --table $T/canonical_families.tsv \
  "${H[@]}" --out $P/assign_header.tsv
python3 -I place_unresolved.py prepare --table $T/canonical_families.tsv --multi $A/multi_family_sequences.tsv --assignments $P/assign_header.tsv \
  "${H[@]}" --queries $P/final_q.faa --refs $P/final_r.faa --dropped $P/fusion_refs.tsv
# bug alarm: 238 fusion references were dropped on the pinned commits (DECISIONS.md); stop if the
# count leaves 200-320, and reset the band by a deliberate edit with a reason when a database changes
diamond makedb --in $P/final_r.faa -d $P/final_r

# 3. thresholds: leave-cluster-out on the references (chunk the query files on a small machine)
mmseqs easy-cluster $P/final_r.faa $P/refclu_0.95 $P/mmtmp --min-seq-id 0.95 -c 0.8 --threads 2 --split-memory-limit 2G
python3 -I loo_threshold.py sample --refs $P/final_r.faa --per-family 300 --out $P/loo_q.faa
diamond blastp -q $P/loo_q.faa -d $P/final_r -o $P/loo_hits.tsv --outfmt 6 qseqid sseqid pident length bitscore \
  --max-target-seqs 500 --sensitive -b 0.1 -c 1
# queries whose list is full may have lost their best competitor: rerun them with a larger cap,
# then rerun any still capped with --top (no cap; cut by score)
cut -f1 $P/loo_hits.tsv | uniq -c | awk '$1 >= 500 {print $2}' | sort -u > $P/loo_full.ids
awk 'NR==FNR {want[$1]; next} /^>/ {keep = (substr($1, 2) in want)} keep' $P/loo_full.ids $P/loo_q.faa > $P/loo_full_q.faa
diamond blastp -q $P/loo_full_q.faa -d $P/final_r -o $P/loo_hits_2000.tsv --outfmt 6 qseqid sseqid pident length bitscore \
  --max-target-seqs 2000 --sensitive -b 0.1 -c 1
cut -f1 $P/loo_hits_2000.tsv | uniq -c | awk '$1 >= 2000 {print $2}' | sort -u > $P/loo_full2.ids
awk 'NR==FNR {want[$1]; next} /^>/ {keep = (substr($1, 2) in want)} keep' $P/loo_full2.ids $P/loo_q.faa > $P/loo_full2_q.faa
diamond blastp -q $P/loo_full2_q.faa -d $P/final_r -o $P/loo_hits_top.tsv --outfmt 6 qseqid sseqid pident length bitscore \
  --top 67 --sensitive -b 0.1 -c 1
python3 -I loo_threshold.py score --multi $A/multi_family_sequences.tsv --table $T/canonical_families.tsv \
  --queries $P/loo_q.faa --hits $P/loo_hits.tsv 500 --hits $P/loo_hits_2000.tsv 2000 --hits $P/loo_hits_top.tsv top:67 \
  --clusters $P/refclu_0.95_cluster.tsv --out $P/loo_thresholds.tsv

# 4. similarity for the shared sequences, then the final assignments
diamond blastp -q $P/final_q.faa -d $P/final_r -o $P/final_hits.tsv --outfmt 6 qseqid sseqid pident length bitscore \
  --top 67 --sensitive -b 0.1 -c 1
python3 -I place_unresolved.py score --assignments $P/assign_header.tsv --hits $P/final_hits.tsv --top 67 \
  --out $P/final_similarity.tsv
python3 -I assign_shared_sequences.py --multi $A/multi_family_sequences.tsv --table $T/canonical_families.tsv \
  "${H[@]}" --similarity $P/final_similarity.tsv --threshold 1.25 --thresholds $P/loo_thresholds.tsv \
  --min-length 60 --refs $P/final_r.faa --out $T/sequence_assignments.tsv

# 5. checks (CI runs this line on the checked-in files)
python3 -I check_canonical_families.py $T/canonical_families.tsv \
  --assignments $T/sequence_assignments.tsv --overrides curation_overrides.tsv

# 6. fixed point: rerun steps 2-4 reading the final assignments instead of the header-only ones;
#    every file must come out byte-identical (no result may feed back into its own evidence)
F=$P/fixed_point; mkdir -p $F
python3 -I place_unresolved.py prepare --table $T/canonical_families.tsv --multi $A/multi_family_sequences.tsv --assignments $T/sequence_assignments.tsv \
  "${H[@]}" --queries $F/final_q.faa --refs $F/final_r.faa
python3 -I place_unresolved.py score --assignments $T/sequence_assignments.tsv --hits $P/final_hits.tsv --top 67 \
  --out $F/final_similarity.tsv
python3 -I loo_threshold.py score --multi $A/multi_family_sequences.tsv --table $T/canonical_families.tsv \
  --queries $P/loo_q.faa --hits $P/loo_hits.tsv 500 --hits $P/loo_hits_2000.tsv 2000 --hits $P/loo_hits_top.tsv top:67 \
  --clusters $P/refclu_0.95_cluster.tsv --out $F/loo_thresholds.tsv
python3 -I assign_shared_sequences.py --multi $A/multi_family_sequences.tsv --table $T/canonical_families.tsv \
  "${H[@]}" --similarity $F/final_similarity.tsv --threshold 1.25 --thresholds $F/loo_thresholds.tsv \
  --min-length 60 --refs $F/final_r.faa --out $F/sequence_assignments.tsv
for f in final_q.faa final_r.faa final_similarity.tsv loo_thresholds.tsv; do cmp $P/$f $F/$f; done
cmp $T/sequence_assignments.tsv $F/sequence_assignments.tsv && echo "fixed point: OK"
```

`--top 67` reports every alignment scoring at least about 33% of the query's best, so a candidate missing from the list scored below that edge. The edge in bitscore is fuzzy by about 0.001 × best (DIAMOND appears to apply `--top` to the raw score), so an absent candidate scores the edge plus a margin, 0.34 × best, not 0, and the ratio to it is at least about 2.94. That is applied in both `place_unresolved.py` and `loo_threshold.py` (`TOP_EDGE_MARGIN`), so thresholds are measured under the rule they are applied with. Size `--top` as top % ≥ 100 × (1 − 1/T_max) + 1; 67 covers thresholds up to 2.94, and a measured threshold above that only makes calls more conservative. DIAMOND 2.1.10 prints no option help; the `--top` semantics and its completeness against a `-k` run were checked directly (DECISIONS.md, shared sequences).

The thresholds use the 95% clusters. For a sensitivity check, score again with `--clusters` from a 90% clustering (`--min-seq-id 0.90`, same coverage) and compare; DECISIONS.md reports both.

`cycdb_audit.py` writes the per-database audit counts (duplicates, missing IDs, target/homolog conflicts). `cycdb_shared_evidence.py` shows the header groups of sequences shared by chosen family pairs. `cycdb_family_fasta.py` writes chosen families to FASTA for best-hit checks.
