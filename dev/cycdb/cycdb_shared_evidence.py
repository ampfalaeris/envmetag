#!/usr/bin/env python3
"""For chosen family pairs, show what each shared sequence's own headers say.

A sequence labelled with two families (multi_family_sequences.tsv) carries one
or more header records per database, each with `description=<gene>` and
`ontology=<group>`. Tabulating the ontology on each side tells a synonym
(both sides collected it by the same group) from a mislabel (one side collected
a sequence of the other family's group). Standard library only.

Usage:
    cycdb_shared_evidence.py --multi multi_family_sequences.tsv \
        --db NAME HEADER_FASTA [--db ...] --pair DB:FAM DB:FAM [--pair ...] [--out per_seq.tsv]
"""
import argparse
import collections
import re
import sys

ONT = re.compile(r"ontology=(\S+?)[\s\]]")
DESC = re.compile(r"description=(\S+?)[\s\]]")
FAM = re.compile(r"([^;\[]+)\[([^\]]+)\]")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--multi", required=True)
    p.add_argument("--db", nargs=2, action="append", required=True, metavar=("NAME", "HEADER_FASTA"))
    p.add_argument("--pair", nargs=2, action="append", required=True, metavar=("DB:FAM", "DB:FAM"))
    p.add_argument("--out")
    a = p.parse_args()

    pairs = [tuple(tuple(x.split(":", 1)) for x in pr) for pr in a.pair]
    wanted = {}
    with open(a.multi) as fh:
        next(fh)
        for line in fh:
            md5, _, fams, ids = line.rstrip("\n").split("\t")
            fs = {(d, f) for f, ds in FAM.findall(fams) for d in ds.split(",")}
            hit = [pr for pr in pairs if pr[0] in fs and pr[1] in fs]
            if hit:
                wanted[md5] = (hit, ids.split(","))
    need = collections.defaultdict(set)
    for _, ids in wanted.values():
        for i in ids:
            d, sid = i.split("|", 1)
            need[d].add(sid)

    ann = collections.defaultdict(list)  # (db, id) -> [(description, ontology, homolog)]
    for name, fa in a.db:
        with open(fa) as fh:
            for line in fh:
                if not line.startswith(">"):
                    continue
                sid, _, rest = line[1:].rstrip("\n").partition(" ")
                if sid in need[name]:
                    d, o = DESC.search(rest + " "), ONT.search(rest + " ")
                    ann[(name, sid)].append((d.group(1) if d else "", o.group(1) if o else "",
                                             " homolog " in f" {rest} "))

    out = open(a.out, "w") if a.out else None
    if out:
        out.write("pair\tseq_md5\tids\tannotations\n")
    for pr in pairs:
        tag = f"{pr[0][0]}:{pr[0][1]} ~ {pr[1][0]}:{pr[1][1]}"
        side = {pr[0]: collections.Counter(), pr[1]: collections.Counter()}
        n = 0
        for md5, (hit, ids) in wanted.items():
            if pr not in hit:
                continue
            n += 1
            recs = []
            for i in ids:
                d, sid = i.split("|", 1)
                for desc, ont, hom in ann.get((d, sid), []):
                    recs.append(f"{d}:{desc}:{ont}{':homolog' if hom else ''}")
                    for k in side:
                        if k[0] == d and desc.startswith(k[1]) and not hom:
                            side[k][ont or "-"] += 1
            if out:
                out.write(f"{tag}\t{md5}\t{','.join(ids)}\t{';'.join(sorted(set(recs)))}\n")
        print(f"{tag}: {n} shared sequences")
        for k, c in side.items():
            print(f"    {k[0]}:{k[1]} header groups: " + ", ".join(f"{g} {v}" for g, v in c.most_common(5)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
