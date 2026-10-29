#!/usr/bin/env python3
"""Measure the similarity-placement threshold by leaving each reference's cluster out.

sample: from a reference FASTA written by `place_unresolved.py prepare` (names
`<family>|<md5>`, header-confirmed single-family sequences), take up to N sequences per
family (lowest md5 first, so the sample is deterministic) as queries.

score: reads DIAMOND blastp of those queries against the same reference set. Hits to the
query itself are left out, and with --clusters (MMseqs2 cluster TSV) so are hits to members
of the query's cluster in the query's own family, so near-identical relatives cannot vouch
for it. Members of other families in that cluster stay: they would compete for a real query. The family
pairs measured are every pair of canonical families that occur together on a sequence in
multi_family_sequences.tsv (mapped through the canonical-family table); they depend only on
the databases and the table, never on assignments. Each query of either family is scored as
place_unresolved.py does: best bitscore per family, an absent family scoring 0 unless the
list was cut, in which case it scores the bound it fell under: the window edge
best * (1 - top/100 + 0.01) for a --top run, or the lowest reported score for a -k list that
reached its cap (size, best and lowest are taken before any hit is left out). At threshold
T a query is placed when best/second >= T and the scores differ, and misassigned when
placed in the other family. For each pair, and pooled over all pairs, the lowest T on a
0.05 grid from 1.00 to 3.00 at which misassigned / placed <= MAX_ERROR is reported, with
the share of queries placed at that T.

--hits takes a file and how DIAMOND was run (the -k value, e.g. 500, or top:<percent>),
and may be repeated: a later file replaces earlier ones for the queries it contains
(reruns of capped lists with a larger -k or --top).

Standard library only.

Usage:
    loo_threshold.py sample --refs refs.faa --per-family 300 --out queries.faa
    diamond blastp -q queries.faa -d refs -o hits.tsv --outfmt 6 qseqid sseqid pident length bitscore \
        --max-target-seqs 500 --sensitive
    loo_threshold.py score --multi multi_family_sequences.tsv --table canonical_families.tsv \
        --queries queries.faa --hits hits.tsv 500 [--hits rerun.tsv top:67] [--clusters clusters.tsv] \
        --out thresholds.tsv
"""
import argparse
import collections
import csv
import itertools
import os
import re
import sys

MAX_ERROR = 0.01
TOP_EDGE_MARGIN = 0.01  # as in place_unresolved.py: keeps the --top floor an upper bound
GRID = [round(1 + 0.05 * i, 2) for i in range(41)]
FAM = re.compile(r"([^;\[]+)\[([^\]]+)\]")  # multi_family_sequences.tsv: family[db,db];family[db]


def sample(a):
    seqs = collections.defaultdict(list)
    with open(a.refs) as fh:
        name = None
        for line in fh:
            if line.startswith(">"):
                name = line[1:].strip()
            else:
                seqs[name.split("|", 1)[0]].append((name, line.strip()))
    with open(a.out, "w") as out:
        for fam in sorted(seqs):
            for name, seq in sorted(seqs[fam])[: a.per_family]:
                out.write(f">{name}\n{seq}\n")
    print(f"families {len(seqs)}; queries {sum(min(len(v), a.per_family) for v in seqs.values())}")


def threshold(rows):
    """rows: (correct?, ratio). Lowest T with error <= MAX_ERROR, and placed share.
    A tie (ratio 1) is never placed, as in assign_shared_sequences.py."""
    for t in GRID:
        placed = [ok for ok, r in rows if r >= t and r > 1]
        if placed and placed.count(False) / len(placed) <= MAX_ERROR:
            return t, len(placed) / len(rows), placed.count(False)
    return None, 0.0, 0


def cooccurring_pairs(multi, table):
    """Canonical-family pairs that occur together on a multi-family sequence. A split source
    family contributes both of its canonical families, so this may include a few pairs that no
    sequence carries; their thresholds are never looked up."""
    canon = collections.defaultdict(set)
    with open(table, newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            canon[(r["source_db"], r["source_family"])].add(r["canonical_family"])
    pairs = set()
    with open(multi) as fh:
        next(fh)
        for line in fh:
            fams = line.rstrip("\n").split("\t")[2]
            cs = set()
            for f, ds in FAM.findall(fams):
                for d in ds.split(","):
                    if (d, f) not in canon:
                        sys.exit(f"{d}:{f} is not in the canonical-family table")
                    cs |= canon[(d, f)]
            pairs |= set(itertools.combinations(sorted(cs), 2))
    return pairs


def stream_lines(path, every=1 << 20):
    """Lines of a large file, dropping its pages from the page cache as it is read (on this
    WSL2 workstation, multi-GB reads that fill the cache have crashed the VM)."""
    with open(path) as fh:
        fd = fh.fileno()
        for n, line in enumerate(fh, 1):
            yield line
            if n % every == 0 and hasattr(os, "posix_fadvise"):
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)


def read_clusters(path):
    """MMseqs2 cluster TSV (representative, member) -> member: representative."""
    rep = {}
    with open(path) as fh:
        for line in fh:
            r, m = line.rstrip("\n").split("\t")
            rep[m] = r
    return rep


def score(a):
    pairs = cooccurring_pairs(a.multi, a.table)
    rep = read_clusters(a.clusters) if a.clusters else {}
    # later --hits files replace earlier ones for the queries they contain (reruns with a larger cap or
    # --top): read the files last to first, once each, and skip queries a later file already gave
    mode = {i: ("top", float(how[4:])) if how.startswith("top:") else ("k", int(how))
            for i, (_, how) in enumerate(a.hits)}
    source = {}
    best = collections.defaultdict(dict)
    n_hits, low, high = collections.Counter(), {}, {}
    dropped = 0
    for i in reversed(range(len(a.hits))):
        here = set()
        for line in stream_lines(a.hits[i][0]):
            q, s, _, _, bits = line.rstrip("\n").split("\t")
            if q in source:
                continue
            here.add(q)
            b = float(bits)
            # list size, lowest and best score as DIAMOND reported them, before any hit is left out
            n_hits[q] += 1
            low[q] = min(low.get(q, b), b)
            high[q] = max(high.get(q, b), b)
            c = s.split("|", 1)[0]
            # leave out the query's own-family relatives in its cluster; other families' members
            # of that cluster stay, as they would compete for a real query
            if q == s or (rep and rep[q] == rep[s] and c == q.split("|", 1)[0]):
                dropped += q != s
                continue
            best[q][c] = max(best[q].get(c, 0.0), b)
        source.update(dict.fromkeys(here, i))
    # an absent family scores 0 unless the list was cut: below the window edge for --top,
    # no higher than the lowest reported score for a full -k list (as in place_unresolved.py)
    floor = {}
    for q, n in n_hits.items():
        kind, v = mode[source[q]]
        if kind == "top":
            floor[q] = high[q] * (1 - v / 100 + TOP_EDGE_MARGIN)
        elif n >= v:
            floor[q] = low[q]
    capped = sum(1 for q, n in n_hits.items() if mode[source[q]][0] == "k" and n >= mode[source[q]][1])
    print(f"queries with hits {len(n_hits)}; at a -k cap {capped}; from --top runs "
          f"{sum(1 for q in n_hits if mode[source[q]][0] == 'top')}; own-cluster hits left out {dropped}")
    queries = collections.defaultdict(list)
    with open(a.queries) as fh:
        for line in fh:
            if line.startswith(">"):
                q = line[1:].strip()
                queries[q.split("|", 1)[0]].append(q)
    pooled = []
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["family_a", "family_b", "n_queries", "threshold", "placed_share", "misassigned_at_threshold",
                    "misassigned_at_1.25", "query_modes"])
        for fa, fb in sorted(pairs):
            rows = []
            modes = collections.Counter()
            for own, other in ((fa, fb), (fb, fa)):
                for q in queries.get(own, []):
                    if q not in n_hits:
                        continue
                    # below the floor means the same whether or not DIAMOND reported the hit
                    absent = floor.get(q, 0.0)
                    so, sx = max(best[q].get(own, 0.0), absent), max(best[q].get(other, 0.0), absent)
                    if so == 0 and sx == 0:
                        continue
                    hi, lo = max(so, sx), min(so, sx)
                    rows.append((so >= sx, hi / lo if lo else float("inf")))
                    kind, v = mode[source[q]]
                    modes[f"top:{v:g}" if kind == "top" else f"k{v}"] += 1
            if not rows:
                continue
            pooled += rows
            t, share, wrong = threshold(rows)
            at125 = sum(1 for ok, r in rows if r >= 1.25 and not ok)
            # which DIAMOND run each query's hits came from (a cascade can leave a mix)
            w.writerow([fa, fb, len(rows), t if t else "none", f"{share:.2f}", wrong, at125,
                        ";".join(f"{k}={n}" for k, n in sorted(modes.items()))])
    t, share, wrong = threshold(pooled)
    print(f"pairs scored; pooled queries {len(pooled)}: threshold {t} (placed {share:.0%}, misassigned {wrong}); "
          f"misassigned at 1.25: {sum(1 for ok, r in pooled if r >= 1.25 and not ok)} of "
          f"{sum(1 for _, r in pooled if r >= 1.25)} placed")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("sample")
    ps.add_argument("--refs", required=True)
    ps.add_argument("--per-family", type=int, default=300)
    ps.add_argument("--out", required=True)
    pc = sub.add_parser("score")
    pc.add_argument("--multi", required=True)
    pc.add_argument("--table", required=True)
    pc.add_argument("--queries", required=True)
    pc.add_argument("--hits", nargs=2, action="append", required=True, metavar=("TSV", "K_OR_TOP"),
                    help="DIAMOND output and how it was run: the -k value (e.g. 500) or top:<percent>")
    pc.add_argument("--clusters")
    pc.add_argument("--out", required=True)
    a = p.parse_args()
    sample(a) if a.cmd == "sample" else score(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
