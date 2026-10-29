#!/usr/bin/env python3
"""Audit SCycDB / MCycDB FASTA headers against their id2gene maps.

Recomputes every count used in the email to the database authors and writes
the underlying ID lists. Standard library only.

Usage:
    cycdb_audit.py --name SCycDB --fasta SCycDB_2020Mar.faa \
        --map id2gene.2020Mar.map [--map2 id2gene.map.2021] --outdir audit/
"""
import argparse
import collections
import re
import sys
from pathlib import Path

HOMOLOG_RE = re.compile(r"description=(\S+) homolog\b")
GENE_RE = re.compile(r"\bgene=([^,\]\s]+)")


def read_records(fasta):
    """Return (records, empty_header_count).

    records: {id: [(annotation, md5 of sequence), ...]}, one entry per FASTA
    record, so duplicated IDs keep every annotation and sequence.
    """
    import hashlib

    records = collections.defaultdict(list)
    empty = 0
    sid = ann = None
    seq = []

    def flush():
        if sid is not None:
            records[sid].append((ann, hashlib.md5("".join(seq).encode()).hexdigest()))

    with open(fasta) as fh:
        for line in fh:
            if line.startswith(">"):
                flush()
                parts = line[1:].rstrip("\n").split(None, 1)
                seq = []
                if not parts:
                    empty += 1
                    sid = None
                    continue
                sid = parts[0]
                ann = parts[1] if len(parts) > 1 else ""
            elif sid is not None:
                seq.append(line.strip())
        flush()
    return records, empty


def read_map(path):
    """Return (row count, {id: family}, duplicate-ID count) from an id2gene map."""
    rows, fam, dup = 0, {}, 0
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 2:
                continue
            rows += 1
            if f[0] in fam:
                dup += 1
            fam.setdefault(f[0], f[1])
    return rows, fam, dup


def header_class(a):
    if HOMOLOG_RE.search(a):
        return "homolog"
    if GENE_RE.search(a):
        return "target-style gene="
    if "description=" in a:
        return "description (non-homolog)"
    return "none" if not a else "other"


def write_ids(path, rows):
    with open(path, "w") as fh:
        fh.write("seq_id\tvalue\theader\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--fasta", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--map2", help="second map to compare against --map")
    p.add_argument("--outdir", required=True)
    a = p.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    records, empty = read_records(a.fasta)
    uniq = set(records)
    nrec = sum(len(v) for v in records.values())
    # first annotation per ID, used for the per-ID classification below
    ann = {i: v[0][0] for i, v in records.items()}
    rows, fam, mapdup = read_map(a.map)
    targets = set(fam)

    print(f"== {a.name}")
    print(f"FASTA records (with an ID):      {nrec:>9,}")
    print(f"FASTA headers with no ID:        {empty:>9,}")
    print(f"FASTA unique IDs:                {len(uniq):>9,}")
    dups = {i: v for i, v in records.items() if len(v) > 1}
    same_seq = sum(1 for v in dups.values() if len({m for _, m in v}) == 1)
    mixed = sorted(i for i, v in dups.items()
                   if len({header_class(x) for x, _ in v}) > 1)
    print(f"IDs occurring more than once:    {len(dups):>9,}  "
          f"(identical sequence: {same_seq:,}; different sequences: {len(dups) - same_seq:,})")
    print(f"  ...annotated both target-style and homolog: {len(mixed):,} "
          f"(in map as target: {len(set(mixed) & targets):,})")
    write_ids(out / f"{a.name}_duplicate_ids_mixed_annotation.tsv",
              [(i, fam.get(i, "NOT_IN_MAP"), " || ".join(x for x, _ in records[i]))
               for i in mixed])
    print(f"map rows / unique IDs / dup rows:{rows:>9,} / {len(targets):,} / {mapdup:,}")
    print(f"map IDs missing from FASTA:      {len(targets - uniq):>9,}")
    print(f"FASTA IDs absent from map:       {len(uniq - targets):>9,}  (homologs by the map rule)")

    cls = collections.Counter(header_class(ann[i]) for i in targets & uniq)
    print("header annotation of map targets:")
    for k, v in cls.most_common():
        print(f"  {k:<28}{v:>9,}")

    conflict = sorted(i for i in targets & uniq if header_class(ann[i]) == "homolog")
    write_ids(out / f"{a.name}_map_target_header_homolog.tsv",
              [(i, fam[i], ann[i]) for i in conflict])
    print(f"CONFLICT map target, header homolog: {len(conflict):,} unique IDs")

    unmapped_gene = sorted(i for i in uniq - targets
                           if header_class(ann[i]) == "target-style gene=")
    write_ids(out / f"{a.name}_header_target_not_in_map.tsv",
              [(i, GENE_RE.search(ann[i]).group(1), ann[i]) for i in unmapped_gene])
    genes = collections.Counter(GENE_RE.search(ann[i]).group(1) for i in unmapped_gene)
    print(f"CONFLICT header gene=, not in map:   {len(unmapped_gene):,} unique IDs, "
          f"{len(genes)} genes; top: "
          + ", ".join(f"{g} ({n:,})" for g, n in genes.most_common(5)))

    mism = sorted(i for i in targets & uniq
                  if GENE_RE.search(ann[i]) and GENE_RE.search(ann[i]).group(1) != fam[i])
    print(f"map family != header gene= label:     {len(mism):,}")

    if a.map2:
        rows2, fam2, dup2 = read_map(a.map2)
        t2 = set(fam2)
        dropped = sorted(targets - t2)
        added = sorted(t2 - targets)
        relabel = sum(1 for i in targets & t2 if fam[i] != fam2[i])
        fams1, fams2 = set(fam.values()), set(fam2.values())
        print(f"-- {Path(a.map2).name} vs {Path(a.map).name}")
        print(f"map2 unique IDs: {len(t2):,}; in FASTA: {len(t2 & uniq):,}")
        print(f"IDs dropped in map2: {len(dropped):,}; added: {len(added):,}; "
              f"relabelled: {relabel:,}")
        print(f"families: {len(fams1)} -> {len(fams2)}; "
              f"new: {sorted(fams2 - fams1)}; removed: {sorted(fams1 - fams2)}")
        dc = collections.Counter(fam[i] for i in dropped)
        print("dropped IDs by family (top 10 of "
              f"{len(dc)}): " + ", ".join(f"{g} ({n:,})" for g, n in dc.most_common(10)))
        write_ids(out / f"{a.name}_map2_dropped.tsv",
                  [(i, fam[i], ann.get(i, "")) for i in dropped])
    return 0


if __name__ == "__main__":
    sys.exit(main())
