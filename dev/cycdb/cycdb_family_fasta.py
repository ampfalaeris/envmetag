#!/usr/bin/env python3
"""Write the target sequences of chosen families to FASTA as `db|family|id`.

Used for best-hit checks between families. Standard library only.

Usage:
    cycdb_family_fasta.py --db NAME SEQ_FASTA MAP FAMILY[,FAMILY...] [--db ...] --out out.faa
"""
import argparse
import collections
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", nargs=4, action="append", required=True, metavar=("NAME", "SEQ_FASTA", "MAP", "FAMILIES"))
    p.add_argument("--out", required=True)
    a = p.parse_args()
    n = collections.Counter()
    with open(a.out, "w") as out:
        for name, fa, mp, fams in a.db:
            want = set(fams.split(","))
            fam = collections.defaultdict(set)
            with open(mp) as fh:
                for line in fh:
                    f = line.rstrip("\n").split("\t")
                    if len(f) >= 2 and f[1] in want:
                        fam[f[0]].add(f[1])
            seen = set()
            sid, buf = None, []

            def flush():
                if sid in fam and sid not in seen:
                    seen.add(sid)
                    for f in sorted(fam[sid]):
                        out.write(f">{name}|{f}|{sid}\n{''.join(buf)}\n")
                        n[(name, f)] += 1

            with open(fa) as fh:
                for line in fh:
                    if line.startswith(">"):
                        flush()
                        parts = line[1:].split(None, 1)
                        sid, buf = (parts[0] if parts else None), []
                    else:
                        buf.append(line.strip())
                flush()
    for k, v in sorted(n.items()):
        print(f"{k[0]}\t{k[1]}\t{v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
