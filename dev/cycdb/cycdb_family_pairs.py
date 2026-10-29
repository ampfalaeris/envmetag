#!/usr/bin/env python3
"""Characterise family pairs that share sequences in the combined database.

For every (database, family) the dominant orthology groups of its TARGET
records are taken from FASTA headers (`ontology=<group> source=<db>`). For each
family pair in multi_family_sequences.tsv (written by cycdb_overlap.py), print
the shared-sequence count, the size of each family, and each side's top groups,
so synonyms (same gene, different name) can be told from different genes that
share sequences. Standard library only.

Usage:
    cycdb_family_pairs.py --multi multi_family_sequences.tsv \
        --db NAME HEADER_FASTA MAP [--db ...] --out pairs.tsv [--top N]
"""
import argparse
import collections
import itertools
import re
import sys

ONT = re.compile(r"ontology=(\S+?)[\s\]]")


def family_groups(fasta, mp):
    fam = collections.defaultdict(set)
    with open(mp) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                fam[f[0]].add(f[1])
    groups = collections.defaultdict(collections.Counter)
    size = collections.Counter()
    seen = set()
    with open(fasta) as fh:
        for line in fh:
            if not line.startswith(">"):
                continue
            sid, _, ann = line[1:].rstrip("\n").partition(" ")
            if sid not in fam or " homolog " in f" {ann} ":
                continue
            m = ONT.search(ann)
            for f in fam[sid]:
                if sid not in seen:
                    size[f] += 1
                if m:
                    groups[f][m.group(1)] += 1
            seen.add(sid)
    return groups, size


def top(counter, n=3):
    tot = sum(counter.values())
    if not tot:
        return "no ontology in headers"
    return ", ".join(f"{g} {100 * c / tot:.0f}%" for g, c in counter.most_common(n))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--multi", required=True)
    p.add_argument("--db", nargs=3, action="append", metavar=("NAME", "HEADER_FASTA", "MAP"), required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--top", type=int, default=40)
    a = p.parse_args()

    info = {}
    for name, fasta, mp in a.db:
        g, s = family_groups(fasta, mp)
        for f in s:
            info[(name, f)] = (s[f], g[f])

    pairs = collections.Counter()
    with open(a.multi) as fh:
        next(fh)
        for line in fh:
            fams = line.split("\t")[2].split(";")
            keys = []
            for item in fams:
                f, dbs = item[:-1].split("[")
                for d in dbs.split(","):
                    keys.append((d, f))
            for x, y in itertools.combinations(sorted(set(keys)), 2):
                if x[1] != y[1]:
                    pairs[(x, y)] += 1

    with open(a.out, "w") as out:
        out.write("db_a\tfamily_a\tsize_a\tgroups_a\tdb_b\tfamily_b\tsize_b\tgroups_b\tshared\n")
        for (x, y), n in pairs.most_common():
            sa, ga = info.get(x, (0, collections.Counter()))
            sb, gb = info.get(y, (0, collections.Counter()))
            out.write(f"{x[0]}\t{x[1]}\t{sa}\t{top(ga)}\t{y[0]}\t{y[1]}\t{sb}\t{top(gb)}\t{n}\n")
    for (x, y), n in pairs.most_common(a.top):
        sa, ga = info.get(x, (0, collections.Counter()))
        sb, gb = info.get(y, (0, collections.Counter()))
        print(f"{n:>6}  {x[0]}:{x[1]} (n={sa}; {top(ga, 2)})  <>  {y[0]}:{y[1]} (n={sb}; {top(gb, 2)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
