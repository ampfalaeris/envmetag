#!/usr/bin/env bash
#
# Build the envmetag test dataset from public ENA runs (see DECISIONS.md, "Test data").
#
#   full tier: 1,000,000 read pairs sampled from each run + simulated PhiX and human-mitochondrion spikes
#   tiny tier: 20,000 read pairs sampled from the full tier (spikes included at the same rate)
#
# Every step is seeded and every tool runs from a pinned container, so a rebuild on another machine
# gives byte-identical files (checked against md5sums.txt). Reads are never committed to the repository;
# the output is deposited on Zenodo.
#
# Usage: build_testdata.sh <raw_dir> <out_dir> [base_url]
#   raw_dir   directory with the full ENA FASTQs (<run>_1.fastq.gz, <run>_2.fastq.gz); verified by MD5
#   out_dir   output directory (created; must not already contain a build)
#   base_url  prefix written into the samplesheets (default: absolute out_dir). For the Zenodo deposit,
#             pass the record's file URL prefix, e.g. https://zenodo.org/records/<id>/files
#
# Requires: docker, curl, md5sum, gzip, awk.

set -euo pipefail

SEED=20261025
FULL_PAIRS=1000000
TINY_PAIRS=20000
SPIKE_PAIRS=10000   # per spike organism per sample in the full tier (~1% each)

SEQTK=quay.io/biocontainers/seqtk:1.5--h577a1d6_1
ISS=quay.io/biocontainers/insilicoseq:2.0.1--pyh7cba7a3_0

# run  sample_id  ISS error model (matches the run's instrument)  ENA MD5 R1  ENA MD5 R2
RUNS=(
    "SRR12174148 mic_coupon      HiSeq   2b8fa343f43b91876eacd6c09924954f 58ce2e7e9812b6077d45cc6af5bb949f"
    "SRR35816318 apb_enrichment NovaSeq 40ffee1dd7192ed0790aceb1e23fe376 13750760783f241d1af392b85b007022"
)

# reference  ENA accession  plain FASTA header (InSilicoSeq copies the header into read names)
REFS=(
    "phix     J02482.1 spike_phix_J02482.1"
    "human_mt J01415.2 spike_human_mt_J01415.2"
)

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[$(date +%H:%M:%S)] $*" >&2; }

[ $# -ge 2 ] || die "usage: $0 <raw_dir> <out_dir> [base_url]"
RAW=$(cd "$1" && pwd)
mkdir -p "$2"
OUT=$(cd "$2" && pwd)
BASE=${3:-$OUT}
[ -e "$OUT/md5sums.txt" ] && die "$OUT already contains a build (md5sums.txt); use an empty directory"
WORK="$OUT/.work"
mkdir -p "$WORK" "$OUT/full" "$OUT/tiny" "$OUT/references"

docker_run() {  # image, then command; mounts RAW (read-only) and OUT, runs as the calling user
    local image=$1; shift
    docker run --rm --user "$(id -u):$(id -g)" -v "$RAW:$RAW:ro" -v "$OUT:$OUT" -w "$WORK" "$image" "$@"
}

count_pairs() { echo $(( $(gzip -dc "$1" | wc -l) / 4 )); }

# read IDs (first token, without /1 or /2) must match line by line, or the pairs are broken
check_paired() {
    local r1=$1 r2=$2
    if ! cmp -s <(gzip -dc "$r1" | awk 'NR % 4 == 1 { sub(/\/[12]$/, "", $1); print $1 }') \
                <(gzip -dc "$r2" | awk 'NR % 4 == 1 { sub(/\/[12]$/, "", $1); print $1 }'); then
        die "$r1 and $r2 are not in the same read order"
    fi
}

count_spike() {  # pairs in R1 whose name starts with the spike header
    gzip -dc "$1" | awk -v p="@$2" 'NR % 4 == 1 && index($1, p) == 1 { n++ } END { print n + 0 }'
}

#
# 1. Verify the raw ENA downloads
#
for entry in "${RUNS[@]}"; do
    read -r run _id _model md5_1 md5_2 <<< "$entry"
    log "verifying $run against ENA MD5s"
    (cd "$RAW" && printf '%s  %s\n%s  %s\n' "$md5_1" "${run}_1.fastq.gz" "$md5_2" "${run}_2.fastq.gz" | md5sum -c --quiet -) \
        || die "$run does not match ENA's MD5s; re-download it"
done

#
# 2. Spike references, with plain headers
#
for entry in "${REFS[@]}"; do
    read -r name acc header <<< "$entry"
    log "fetching $acc"
    curl -fsSL --retry 5 "https://www.ebi.ac.uk/ena/browser/api/fasta/$acc" | awk -v h=">$header" 'NR == 1 { print h; next } { print }' > "$OUT/references/$name.fa"
    [ "$(grep -c '^>' "$OUT/references/$name.fa")" -eq 1 ] || die "$acc did not download as a single FASTA record"
done

#
# 3. Per run: subsample, simulate spikes, assemble the full tier, subsample the tiny tier
#
manifest="$OUT/MANIFEST.tsv"
printf 'tier\tsample\trun\tpairs\tphix_pairs\thuman_mt_pairs\tr1\tr2\n' > "$manifest"
for tier in full tiny; do printf 'sample,fastq_1,fastq_2\n' > "$OUT/$tier/samplesheet.csv"; done

for entry in "${RUNS[@]}"; do
    read -r run id model _md5_1 _md5_2 <<< "$entry"

    # Same seed for R1 and R2 keeps mates paired (seqtk sample)
    log "$run: sampling $FULL_PAIRS pairs (seed $SEED)"
    for m in 1 2; do
        docker_run "$SEQTK" sh -c "seqtk sample -s $SEED '$RAW/${run}_$m.fastq.gz' $FULL_PAIRS | gzip -n > '$WORK/${run}_sub_$m.fastq.gz'"
    done
    check_paired "$WORK/${run}_sub_1.fastq.gz" "$WORK/${run}_sub_2.fastq.gz"

    # InSilicoSeq output depends on both --seed and --cpus, so both are pinned
    spike_seed=$SEED
    for ref in "${REFS[@]}"; do
        read -r name _acc _header <<< "$ref"
        spike_seed=$((spike_seed + 1))
        log "$run: simulating $SPIKE_PAIRS $name pairs ($model model, seed $spike_seed)"
        docker_run "$ISS" iss generate --genomes "$OUT/references/$name.fa" --n_reads $((2 * SPIKE_PAIRS)) \
            --model "$model" --seed "$spike_seed" --cpus 1 --output "$WORK/${run}_$name" > "$WORK/${run}_$name.iss.log" 2>&1
        for m in 1 2; do gzip -n -f "$WORK/${run}_${name}_R$m.fastq"; done
    done

    for m in 1 2; do
        cat "$WORK/${run}_sub_$m.fastq.gz" "$WORK/${run}_phix_R$m.fastq.gz" "$WORK/${run}_human_mt_R$m.fastq.gz" \
            > "$OUT/full/${run}_full_R$m.fastq.gz"
    done
    check_paired "$OUT/full/${run}_full_R1.fastq.gz" "$OUT/full/${run}_full_R2.fastq.gz"

    log "$run: sampling $TINY_PAIRS pairs for the tiny tier"
    for m in 1 2; do
        docker_run "$SEQTK" sh -c "seqtk sample -s $SEED '$OUT/full/${run}_full_R$m.fastq.gz' $TINY_PAIRS | gzip -n > '$OUT/tiny/${run}_tiny_R$m.fastq.gz'"
    done
    check_paired "$OUT/tiny/${run}_tiny_R1.fastq.gz" "$OUT/tiny/${run}_tiny_R2.fastq.gz"

    for tier in full tiny; do
        r1="$OUT/$tier/${run}_${tier}_R1.fastq.gz"
        r2="$OUT/$tier/${run}_${tier}_R2.fastq.gz"
        pairs=$(count_pairs "$r1")
        phix=$(count_spike "$r1" spike_phix_)
        human=$(count_spike "$r1" spike_human_mt_)
        [ "$phix" -gt 0 ] && [ "$human" -gt 0 ] || die "$tier/$run has no spike reads (phix=$phix human_mt=$human)"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$tier" "$id" "$run" "$pairs" "$phix" "$human" "$(basename "$r1")" "$(basename "$r2")" >> "$manifest"
        printf '%s,%s/%s/%s,%s/%s/%s\n' "$id" "$BASE" "$tier" "$(basename "$r1")" "$BASE" "$tier" "$(basename "$r2")" >> "$OUT/$tier/samplesheet.csv"
    done
done

#
# 4. Checksums and provenance
#
rm -rf "$WORK"
(cd "$OUT" && find full tiny references -type f -name '*.gz' -o -type f -name '*.fa' | LC_ALL=C sort | xargs md5sum > md5sums.txt)
{
    echo "envmetag test data, built $(date -u +%Y-%m-%d) by tests/testdata/build_testdata.sh"
    echo "seed=$SEED full_pairs=$FULL_PAIRS tiny_pairs=$TINY_PAIRS spike_pairs_per_organism=$SPIKE_PAIRS"
    echo "seqtk=$SEQTK"
    echo "insilicoseq=$ISS"
    echo "sources: SRR12174148 (PRJNA644413, BioSample SAMN15459511): carbon steel coupon biofilm exposed to oil field"
    echo "           production water; https://doi.org/10.1128/aem.01819-20"
    echo "         SRR35816318 (PRJNA1346464, BioSample SAMN52836159): carbon steel coupon biofilm from a 21-day"
    echo "           acid-producing-bacteria enrichment of corroded crude-pipeline debris; https://doi.org/10.3389/fmicb.2026.1771929"
    echo "         spikes simulated from ENA J02482.1 (phiX174) and J01415.2 (human mitochondrion, rCRS)"
} > "$OUT/PROVENANCE.txt"
log "done: $OUT"
cat "$manifest"
