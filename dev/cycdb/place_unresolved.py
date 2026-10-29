#!/usr/bin/env python3
"""Score multi-family sequences by similarity to clean references of their candidate families.

The queries are every sequence in sequence_assignments.tsv that carries more than one
canonical family, except those whose families are all in one ambiguity group (structural,
basis `one ambiguity group`) and split rows. The candidates are its canonical families.
assign_shared_sequences.py --similarity combines this with the header evidence.

prepare: writes the query sequences (named by md5) and a reference set:
every sequence of the candidate canonical families that carries exactly one canonical
family (no row in sequence_assignments.tsv, or a `split` row) and whose own target
headers carry that family's KO or dominant COG, named `<family>|<md5>`. The header
filter matters: several source families hold mislabelled sequences of a neighbouring
family (e.g. GltD-like proteins in MCycDB rnfB), and a query similar to those would
otherwise be placed in the wrong family.

HEADER_FASTA must carry the annotations (for NCyc, NCyc_100.faa; its sequences are
identical per ID to the 2019Jul FASTA).

score: reads DIAMOND blastp output (outfmt 6 qseqid sseqid pident length bitscore) and,
per query, takes the best bitscore against each candidate family (a candidate with no hit
scores 0; if the list was cut, it scores the bound it fell under: the window edge,
best * (1 - top/100 + 0.01), for a --top run, or the lowest reported score for a full -k list) and
writes the best
family, the runner-up, their ratio, and every candidate's score (`scores`). The `placement` column applies MARGIN only as a
summary; assign_shared_sequences.py applies the measured threshold.

Standard library only.

Usage:
    place_unresolved.py prepare --table canonical_families.tsv --assignments sequence_assignments.tsv \
        --db NAME HEADER_FASTA MAP [--db ...] --queries q.faa --refs refs.faa
    diamond makedb --in refs.faa -d refs
    diamond blastp -q q.faa -d refs -o hits.tsv --outfmt 6 qseqid sseqid pident length bitscore \
        --top 67 --sensitive
    place_unresolved.py score --assignments sequence_assignments.tsv --hits hits.tsv --top 67 \
        --out placements.tsv
"""
import argparse
import collections
import csv
import hashlib
import re
import sys

ONT = re.compile(r"ontology=(\S+?)[\s\]]")

MARGIN = 1.1
# DIAMOND's --top edge, in bitscore, is fuzzy by about 0.001 x best (absent families scored up to
# 0.3299 x best at --top 67, 2026-10-29); the floor adds this margin so it stays an upper bound
TOP_EDGE_MARGIN = 0.01


def is_query(r):
    return r["basis"] != "one ambiguity group" and not r["basis"].startswith("split")


def read_assignments(path):
    with open(path, newline="") as fh:
        return {r["seq_md5"]: r for r in csv.DictReader(fh, delimiter="\t")}


def prepare(a):
    assign = read_assignments(a.assignments)
    queries = {m for m, r in assign.items() if is_query(r)}
    cands = set()
    for m in queries:
        cands |= set(assign[m]["canonical_families"].split(","))
    canon = {}
    sig = collections.defaultdict(set)
    with open(a.table, newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["selector"] != "rest":
                canon[(r["source_db"], r["source_family"])] = r["canonical_family"]
                sig[r["canonical_family"]] |= {x for x in (r["ko"], r["cog"]) if x}
            if r["selector"].startswith("ontology:"):
                sig[r["canonical_family"]] |= set(r["selector"].split(":", 1)[1].split(","))
    q_seen, r_seen = set(), set()
    n = collections.Counter()
    unconfirmed = collections.Counter()
    with open(a.queries, "w") as qo, open(a.refs, "w") as ro:
        for name, fa, mp in a.db:
            fam = collections.defaultdict(set)
            with open(mp) as fh:
                for line in fh:
                    f = line.rstrip("\n").split("\t")
                    if len(f) >= 2 and (name, f[1]) in canon:
                        fam[f[0]].add(canon[(name, f[1])])
            sid, buf, onts = None, [], set()

            def flush():
                if sid not in fam:
                    return
                seq = "".join(buf).upper()
                m = hashlib.md5(seq.encode()).hexdigest()
                if m in queries and m not in q_seen:
                    q_seen.add(m)
                    qo.write(f">{m}\n{seq}\n")
                    return
                r = assign.get(m)
                if r is not None and not r["basis"].startswith("split"):
                    return
                c = r["assignment"] if r is not None else next(iter(fam[sid])) if len(fam[sid]) == 1 else None
                if c in cands and m not in r_seen:
                    if not sig[c] & onts:
                        unconfirmed[c] += 1
                        return
                    r_seen.add(m)
                    ro.write(f">{c}|{m}\n{seq}\n")
                    n[c] += 1

            with open(fa) as fh:
                for line in fh:
                    if line.startswith(">"):
                        parts = line[1:].rstrip("\n").split(None, 1)
                        nid = parts[0] if parts else None
                        if nid != sid:
                            flush()
                            sid, buf, onts = nid, [], set()
                        elif buf:
                            buf = []  # duplicate record of the same ID: identical sequence, re-read it
                        ann = parts[1] if len(parts) > 1 else ""
                        mo = ONT.search(ann + " ")
                        if mo and " homolog " not in f" {ann} ":
                            onts.add(mo.group(1))
                    else:
                        buf.append(line.strip())
                flush()
    missing = queries - q_seen
    if missing:
        sys.exit(f"{len(missing)} query sequences not found in the FASTAs")
    print(f"queries {len(q_seen)}; candidate families {len(cands)}; reference sequences {sum(n.values())}; "
          f"dropped without a confirming header {sum(unconfirmed.values())}")
    for c in sorted(cands - set(n)):
        print(f"  no single-family reference sequences for {c}")


def score(a):
    assign = read_assignments(a.assignments)
    best = collections.defaultdict(dict)  # query -> family -> (bitscore, pident)
    n_hits = collections.Counter()
    low, top = {}, {}
    with open(a.hits) as fh:
        for line in fh:
            q, s, pid, _, bits = line.rstrip("\n").split("\t")
            c = s.split("|", 1)[0]
            n_hits[q] += 1
            low[q] = min(low.get(q, float(bits)), float(bits))
            top[q] = max(top.get(q, float(bits)), float(bits))
            if float(bits) > best[q].get(c, (0.0, 0.0))[0]:
                best[q][c] = (float(bits), float(pid))
    # An absent candidate scores 0 unless the hit list was cut: with --top it scored below the
    # window edge (best * (1 - top/100), plus TOP_EDGE_MARGIN); with a full -k list, no higher
    # than the lowest reported score. Every candidate scores at least that floor, so below it
    # means the same whether or not DIAMOND reported the hit.
    if a.top is not None:
        floor = {q: top[q] * (1 - a.top / 100 + TOP_EDGE_MARGIN) for q in n_hits}
    else:
        floor = {q: low[q] for q in n_hits if n_hits[q] >= a.max_target_seqs}
    full = set(floor)
    kinds = collections.Counter()
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["seq_md5", "candidates", "placement", "best_family", "best_bitscore", "best_pident",
                    "runner_up", "runner_up_bitscore", "ratio", "scores"])
        for m, r in sorted(assign.items()):
            if not is_query(r):
                continue
            cands = r["canonical_families"].split(",")
            fl = floor[m] if m in full else 0.0
            scores = sorted((((b, p) if b >= fl else (fl, 0.0), c)
                             for c in cands for b, p in [best[m].get(c, (0.0, 0.0))]), reverse=True)
            (b1, p1), c1 = scores[0]
            (b2, _), c2 = scores[1]
            ratio = b1 / b2 if b2 else float("inf")
            if b1 == 0:
                kind = "no hits"
            elif ratio >= MARGIN:
                kind = "placed"
            else:
                kind = "not placed"
            kinds[kind] += 1
            w.writerow([m, ",".join(cands), kind, c1 if b1 else "", f"{b1:.1f}", f"{p1:.1f}", c2, f"{b2:.1f}",
                        "inf" if ratio == float("inf") else f"{ratio:.2f}",
                        ";".join(f"{c}:{b:.1f}" for (b, _), c in scores)])
    print(", ".join(f"{k} {v}" for k, v in kinds.most_common()))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--table", required=True)
    pp.add_argument("--assignments", required=True)
    pp.add_argument("--db", nargs=3, action="append", required=True, metavar=("NAME", "SEQ_FASTA", "MAP"))
    pp.add_argument("--queries", required=True)
    pp.add_argument("--refs", required=True)
    ps = sub.add_parser("score")
    ps.add_argument("--assignments", required=True)
    ps.add_argument("--hits", required=True)
    ps.add_argument("--out", required=True)
    ps.add_argument("--max-target-seqs", type=int, default=500, help="the -k value given to diamond")
    ps.add_argument("--top", type=float, help="the --top value given to diamond (replaces --max-target-seqs)")
    a = p.parse_args()
    prepare(a) if a.cmd == "prepare" else score(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
