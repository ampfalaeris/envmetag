#!/usr/bin/env python3
"""One row per (database, family): size, dominant KO and COG from target headers.

Also lists family names that occur in more than one database, with both sides'
dominant groups and their shared-sequence count, so same-name families can be
checked for being the same enzyme. Standard library only.

Usage:
    cycdb_family_summary.py --db NAME SEQ_FASTA HEADER_FASTA MAP [--db ...] \
        --summary families.tsv --same-name same_name.tsv
SEQ_FASTA gives sequences (for shared-sequence counts); HEADER_FASTA gives
annotations (they differ only for NCyc, whose 2019Jul FASTA has bare IDs).
"""
import argparse
import collections
import hashlib
import itertools
import re
import sys

ONT = re.compile(r"ontology=(\S+?)[\s\]]")
KO_RE = re.compile(r"^K\d{5}$")
COG_RE = re.compile(r"^(?:COG|arCOG)\d{4,5}$")
NAME_KO = re.compile(r"[-_](K\d{5})$")


def read_map(path):
    fam = collections.defaultdict(set)
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                fam[f[0]].add(f[1])
    return fam


def seq_hashes(path, wanted):
    out = collections.defaultdict(set)
    sid, buf = None, []

    def flush():
        if sid in wanted:
            out[sid].add(hashlib.md5("".join(buf).upper().encode()).hexdigest())

    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                flush()
                parts = line[1:].split(None, 1)
                sid, buf = (parts[0] if parts else None), []
            else:
                buf.append(line.strip())
        flush()
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", nargs=4, action="append", required=True,
                   metavar=("NAME", "SEQ_FASTA", "HEADER_FASTA", "MAP"))
    p.add_argument("--summary", required=True)
    p.add_argument("--same-name", required=True)
    a = p.parse_args()

    rows = {}
    seqs_by_family = {}
    for name, seq_fa, hdr_fa, mp in a.db:
        fam = read_map(mp)
        ko = collections.defaultdict(collections.Counter)
        cog = collections.defaultdict(collections.Counter)
        seen = set()
        with open(hdr_fa) as fh:
            for line in fh:
                if not line.startswith(">"):
                    continue
                sid, _, ann = line[1:].rstrip("\n").partition(" ")
                if sid not in fam or sid in seen or " homolog " in f" {ann} ":
                    continue
                seen.add(sid)
                m = ONT.search(ann)
                for f in fam[sid]:
                    if m and KO_RE.match(m.group(1)):
                        ko[f][m.group(1)] += 1
                    elif m and COG_RE.match(m.group(1)):
                        cog[f][m.group(1)] += 1
        hashes = seq_hashes(seq_fa, set(fam))
        members = collections.defaultdict(set)
        for sid, fs in fam.items():
            for f in fs:
                members[f] |= hashes.get(sid, set())
        for f in members:
            name_ko = NAME_KO.search(f)
            kc, cc = ko[f], cog[f]
            top_ko = name_ko.group(1) if name_ko else (kc.most_common(1)[0][0] if kc else "")
            ko_share = (kc[top_ko] / sum(kc.values())) if kc and top_ko in kc else (1.0 if name_ko else 0.0)
            top_cog = cc.most_common(1)[0][0] if cc else ""
            cog_share = cc[top_cog] / sum(cc.values()) if cc else 0.0
            other_kos = ",".join(k for k, _ in kc.most_common(4) if k != top_ko)
            rows[(name, f)] = (len(members[f]), top_ko, ko_share, sum(kc.values()), other_kos, top_cog, cog_share)
            seqs_by_family[(name, f)] = members[f]

    with open(a.summary, "w") as out:
        out.write("source_db\tsource_family\tn_sequences\tko\tko_share\tko_headers\tother_kos\tcog\tcog_share\n")
        for (d, f), r in sorted(rows.items()):
            out.write(f"{d}\t{f}\t{r[0]}\t{r[1]}\t{r[2]:.2f}\t{r[3]}\t{r[4]}\t{r[5]}\t{r[6]:.2f}\n")

    by_name = collections.defaultdict(list)
    for d, f in rows:
        by_name[f.lower()].append((d, f))
    n_agree = n_differ = 0
    with open(a.same_name, "w") as out:
        out.write("family\tdb_a\tko_a\tcog_a\tn_a\tdb_b\tko_b\tcog_b\tn_b\tshared\tverdict\n")
        for name, keys in sorted(by_name.items()):
            for x, y in itertools.combinations(sorted(keys), 2):
                rx, ry = rows[x], rows[y]
                shared = len(seqs_by_family[x] & seqs_by_family[y])
                same_ko = rx[1] and rx[1] == ry[1]
                same_cog = rx[5] and rx[5] == ry[5]
                verdict = "same" if (same_ko or (not (rx[1] and ry[1]) and same_cog)) else "CHECK"
                n_agree += verdict == "same"
                n_differ += verdict != "same"
                out.write(f"{x[1]}\t{x[0]}\t{rx[1]}\t{rx[5]}\t{rx[0]}\t{y[0]}\t{ry[1]}\t{ry[5]}\t{ry[0]}\t{shared}\t{verdict}\n")
    print(f"families: {len(rows)}; same-name pairs across databases: {n_agree + n_differ} "
          f"(groups agree: {n_agree}; check: {n_differ})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
