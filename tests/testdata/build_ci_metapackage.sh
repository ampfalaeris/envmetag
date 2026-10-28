#!/usr/bin/env bash
#
# Build the 3-marker GlobDB CI metapackage for the `test` profile (see DECISIONS.md, "CI runs real SingleM
# against a 3-marker GlobDB subset").
#
#   input:  the extracted GlobDB r232 SingleM metapackage (GlobDB_r232.metapackage_v4.smpkg, CC BY-SA 4.0)
#   output: GlobDB_r232_ci3.smpkg/ and a reproducible GlobDB_r232_ci3.smpkg.tar.gz, with md5sums.txt and
#           PROVENANCE.txt stating the changes from GlobDB, the command, and the SingleM version
#
# Changes from GlobDB r232: 3 of its SingleM packages kept (S3.1 rplB, S3.2 rplC, S3.5 rpsB), the nucleotide
# SingleM database omitted (--no-nucleotide-sdb, so pipe needs --assignment-method diamond), and the DIAMOND
# prefilter rebuilt from the 3 packages by `singlem metapackage`.
#
# Usage: build_ci_metapackage.sh <globdb_smpkg_dir> <out_dir> [--deposit]
#   globdb_smpkg_dir  extracted GlobDB_r232.metapackage_v4.smpkg directory
#   out_dir           output directory (created; must not already contain a build)
#   --deposit         refuse to run unless this script is committed unchanged (builds for Zenodo)
#
# Requires: docker, GNU tar, gzip, md5sum, git.

set -euo pipefail

SINGLEM=quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2
NAME=GlobDB_r232_ci3
PACKAGES=(S3.1.ribosomal_protein_L2_rplB.spkg S3.2.ribosomal_protein_L3_rplC.spkg S3.5.ribosomal_protein_S2_rpsB.spkg)
GLOBDB_URL=https://fileshare.lisc.univie.ac.at/globdb/globdb_r232/taxonomic_profiling/GlobDB_r232.metapackage_v4.smpkg.tar.gz
TAR_MTIME='2026-10-25 00:00:00Z'   # fixed, so the archive is byte-identical across rebuilds

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[$(date +%H:%M:%S)] $*" >&2; }

[ $# -ge 2 ] || die "usage: $0 <globdb_smpkg_dir> <out_dir> [--deposit]"
SRC=$(cd "$1" && pwd)
mkdir -p "$2"
OUT=$(cd "$2" && pwd)
DEPOSIT=${3:-}
[ -z "$DEPOSIT" ] || [ "$DEPOSIT" = --deposit ] || die "unknown option '$DEPOSIT'"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
COMMIT=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null) || die "cannot read the git commit of $SCRIPT_DIR"
DIRTY=""
if ! git -C "$SCRIPT_DIR" ls-files --error-unmatch -- "$(basename "$0")" > /dev/null 2>&1; then
    DIRTY=" (this script is not committed)"
elif ! git -C "$SCRIPT_DIR" diff --quiet HEAD -- "$(basename "$0")"; then
    DIRTY=" (with uncommitted changes to this script)"
fi
[ -z "$DEPOSIT" ] || [ -z "$DIRTY" ] || die "--deposit: commit $(basename "$0") first, so the record can cite the exact script"

[ -f "$SRC/CONTENTS.json" ] || die "$SRC is not a SingleM metapackage (no CONTENTS.json)"
[ -e "$OUT/md5sums.txt" ] && die "$OUT already contains a build (md5sums.txt); use an empty directory"
for p in "${PACKAGES[@]}"; do [ -d "$SRC/$p" ] || die "$SRC has no package $p"; done
lengths=("$SRC"/taxon_genome_lengths*.tsv)
[ ${#lengths[@]} -eq 1 ] && [ -f "${lengths[0]}" ] || die "expected exactly one taxon_genome_lengths*.tsv in $SRC"

log "building $NAME from $(basename "$SRC") with $SINGLEM"
docker run --rm --user "$(id -u):$(id -g)" -v "$SRC:/mp:ro" -v "$OUT:/out" -w /out "$SINGLEM" \
    singlem metapackage --metapackage "/out/$NAME.smpkg" \
        --singlem-packages "${PACKAGES[@]/#//mp/}" \
        --no-nucleotide-sdb \
        --taxon-genome-lengths "/mp/$(basename "${lengths[0]}")" \
        --taxonomy-database-name GlobDB --taxonomy-database-version r232 \
        --threads 1 \
    > "$OUT/build.log" 2>&1 || { tail -20 "$OUT/build.log" >&2; die "singlem metapackage failed (see $OUT/build.log)"; }
[ -f "$OUT/$NAME.smpkg/CONTENTS.json" ] || die "singlem metapackage wrote no CONTENTS.json"

log "packing $NAME.smpkg.tar.gz"
tar --sort=name --mtime="$TAR_MTIME" --owner=0 --group=0 --numeric-owner -C "$OUT" -cf - "$NAME.smpkg" \
    | gzip -n > "$OUT/$NAME.smpkg.tar.gz"

(cd "$OUT" && { find "$NAME.smpkg" -type f | LC_ALL=C sort | xargs md5sum; md5sum "$NAME.smpkg.tar.gz"; } > md5sums.txt)
{
    echo "$NAME SingleM metapackage, built $(date -u +%Y-%m-%d) by tests/testdata/build_ci_metapackage.sh"
    echo "repository: https://github.com/ampfalaeris/envmetag, commit $COMMIT$DIRTY"
    echo "singlem=$SINGLEM"
    echo "adapted from: GlobDB r232 SingleM metapackage ($GLOBDB_URL)"
    echo "  CONTENTS.json md5 $(md5sum < "$SRC/CONTENTS.json" | cut -d' ' -f1)"
    echo "changes: kept 3 of GlobDB's SingleM packages (${PACKAGES[*]}); no nucleotide SingleM database"
    echo "  (--no-nucleotide-sdb: use 'singlem pipe --assignment-method diamond'); DIAMOND prefilter rebuilt from the 3 packages"
    echo "command: singlem metapackage --singlem-packages <3 packages> --no-nucleotide-sdb --taxon-genome-lengths $(basename "${lengths[0]}")"
    echo "  --taxonomy-database-name GlobDB --taxonomy-database-version r232 --threads 1"
    echo "license: CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/), as GlobDB; cite GlobDB"
    echo "  (https://doi.org/10.1093/bioadv/vbaf280) and its underlying sources (https://globdb.org/citations)"
    echo "purpose: CI plumbing tests only. Genus-level assignments at best; not for biological interpretation."
} > "$OUT/PROVENANCE.txt"
log "done: $OUT"
