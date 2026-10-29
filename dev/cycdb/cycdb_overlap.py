#!/usr/bin/env python3
"""Cross-database checks for SCycDB, MCycDB and NCyc. Standard library only.

1. ID types per database (UniProt accession, RefSeq WP_, eggNOG taxid.locus, other).
2. Overlap between each pair of databases, by identical ID and by identical
   sequence, split by map status (target in both / target in one only / homolog in both).
3. Multi-family sequences: identical sequences collapsed across all databases
   (as the combined database will do) and their target families merged. A
   sequence with more than one target family is listed, split into within-one-
   database and across-database cases, with the family pairs counted.

Target status and family come from each database's id2gene map; everything
else in a FASTA is a homolog (the map rule).

Usage:
    cycdb_overlap.py --db NAME FASTA MAP [--db ...] --outdir DIR
"""
import argparse
import collections
import hashlib
import itertools
import re
import sys
from pathlib import Path

ID_TYPES = [
    ("uniprot", re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$")),
    ("refseq_WP", re.compile(r"^WP_\d+(?:\.\d+)?$")),
    ("eggnog_taxid.locus", re.compile(r"^\d+\.\S+$")),
]


def id_type(sid):
    for name, rx in ID_TYPES:
        if rx.match(sid):
            return name
    return "other"


def read_fasta(path):
    """Return {id: md5 of sequence}; duplicate IDs must have identical sequences."""
    seqs = {}
    sid, buf = None, []

    def flush():
        if sid is None:
            return
        h = hashlib.md5("".join(buf).upper().encode()).hexdigest()
        if seqs.setdefault(sid, h) != h:
            sys.exit(f"{path}: ID {sid} occurs with different sequences")

    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                flush()
                parts = line[1:].split(None, 1)
                sid, buf = (parts[0] if parts else None), []
            elif sid is not None:
                buf.append(line.strip())
        flush()
    return seqs


def read_map(path):
    fam = collections.defaultdict(set)
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                fam[f[0]].add(f[1])
    return fam


def status_split(ids, ta, tb):
    both = sum(1 for i in ids if i in ta and i in tb)
    one = sum(1 for i in ids if (i in ta) != (i in tb))
    return both, one, len(ids) - both - one


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", nargs=3, action="append", metavar=("NAME", "FASTA", "MAP"), required=True)
    p.add_argument("--outdir", required=True)
    a = p.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    dbs = {}
    for name, fasta, mp in a.db:
        seqs = read_fasta(fasta)
        fam = read_map(mp)
        targets = {i: fam[i] for i in seqs if i in fam}
        dbs[name] = (seqs, targets)
        print(f"== {name}: {len(seqs):,} unique IDs, {len(targets):,} map targets in FASTA, "
              f"{len(set(seqs.values())):,} distinct sequences")
        types = collections.Counter(id_type(i) for i in seqs)
        print("   ID types: " + ", ".join(
            f"{k} {v:,} ({100 * v / len(seqs):.1f}%)" for k, v in types.most_common()))

    print("\n== Pairwise overlap (target both / target in one only / homolog both)")
    for x, y in itertools.combinations(dbs, 2):
        sx, tx = dbs[x]
        sy, ty = dbs[y]
        ids = set(sx) & set(sy)
        b, o, h = status_split(ids, tx, ty)
        print(f"{x}-{y} by ID:       {len(ids):>8,}  ({b:,} / {o:,} / {h:,})")
        same_id_diff_seq = sum(1 for i in ids if sx[i] != sy[i])
        if same_id_diff_seq:
            print(f"   shared IDs with different sequences: {same_id_diff_seq:,}")
        hx = {h_: i for i, h_ in sx.items()}
        common = set(hx) & set(sy.values())
        print(f"{x}-{y} by sequence: {len(common):>8,} distinct sequences")

    # Collapse identical sequences across all databases and merge target families.
    by_seq = collections.defaultdict(lambda: {"ids": [], "fams": collections.defaultdict(set)})
    for name, (seqs, targets) in dbs.items():
        for i, h in seqs.items():
            e = by_seq[h]
            e["ids"].append(f"{name}|{i}")
            for f in targets.get(i, ()):
                e["fams"][f].add(name)

    multi = [(h, e) for h, e in by_seq.items() if len(e["fams"]) > 1]
    within = [m for m in multi if len({d for s in m[1]["fams"].values() for d in s}) == 1]
    within_h = {h for h, _ in within}
    across = [m for m in multi if m[0] not in within_h]
    print(f"\n== Combined: {len(by_seq):,} distinct sequences, "
          f"{sum(1 for e in by_seq.values() if e['fams']):,} with a target family")
    print(f"Multi-family sequences: {len(multi):,} "
          f"(families from one database only: {len(within):,}; across databases: {len(across):,})")
    for label, group in (("within one database", within), ("across databases", across)):
        pairs = collections.Counter()
        for _, e in group:
            for f1, f2 in itertools.combinations(sorted(e["fams"]), 2):
                pairs[(f1, f2)] += 1
        print(f"  top family pairs, {label}: " + ", ".join(
            f"{f1}+{f2} ({n:,})" for (f1, f2), n in pairs.most_common(10)))

    with open(out / "multi_family_sequences.tsv", "w") as fh:
        fh.write("seq_md5\tscope\tfamilies\tids\n")
        for h, e in sorted(multi, key=lambda m: sorted(m[1]["fams"])):
            scope = "within" if h in within_h else "across"
            fams = ";".join(f"{f}[{','.join(sorted(d))}]" for f, d in sorted(e["fams"].items()))
            fh.write(f"{h}\t{scope}\t{fams}\t{','.join(e['ids'])}\n")
    print(f"\nwrote {out / 'multi_family_sequences.tsv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
