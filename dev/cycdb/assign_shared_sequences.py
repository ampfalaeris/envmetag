#!/usr/bin/env python3
"""Assign every sequence whose canonical family is not given by its table row alone.

Writes assets/cycdb/sequence_assignments.tsv, which CYCDB_PREPARE reads so that no
sequence keeps two family labels. Sequences are keyed by the md5 of the uppercase
sequence with whitespace removed (as in cycdb_overlap.py). Every sequence stays in the
search database whatever its assignment; an unassigned sequence still competes for reads.

A sequence in a split family (table `selector` column) takes the family's main
canonical family if one of its own target headers carries a `keep` ontology group,
else the rest family. A sequence that then carries one canonical family gets a row
only if that differs from a table row's default (basis `split`).

A sequence carrying more than one canonical family is decided in this order:

1. structural: all its families are in one ambiguity group -> `group:<name>`.
2. fragment: shorter than --min-length amino acids -> `unresolved:` (basis `fragment`).
   A fragment is never given a family.
3. fusion (with --refs): at least FUSION_LENGTH x the median reference length of every
   candidate, and its own headers (target or homolog) carry the signatures of at least two
   candidate units (a family, or an ambiguity group) -> `unresolved:` (basis `fusion`).
   Neither line of evidence below decides a fusion: whichever family it got, reads from its
   other domain would be counted for the wrong one. Families marked `fusion = declared`
   are exempt, as in place_unresolved.py; a family without references never flags.
3b. Pfam fusion (with --pfam-calls, from pfam_domains.py call): the Pfam domain test calls
   it a fusion of a pair it can decide -> `unresolved:` (basis `pfam fusion (<pair>)`).
   This rule only adds fusion calls. A Pfam "not fusion" never overrides the length rule,
   because a wrong removal puts reads under the wrong family (DECISIONS 2026-10-30).
4. Two lines of evidence, each of which either decides or is silent:
   - header: the ontology groups (KO, COG) on its own target headers match the signature
     (canonical KO + each source row's dominant COG) of exactly one candidate family ->
     that family; of several candidates all in one group -> that group; otherwise silent.
     Silent also when any candidate has `header_evidence = insufficient`.
   - similarity (--similarity, from place_unresolved.py score): the best candidate family
     scores at least T times the runner-up, and strictly more (a tie never decides) -> that
     family; otherwise silent. Candidates in
     one ambiguity group compete as one unit with their best score, so the call may be
     `group:<name>`. T is the strictest measured threshold (loo_threshold.py, --thresholds)
     over the family pairs between the two leading units; a pair whose misassignment never fell under the target means
     similarity never decides; a pair measured on fewer than MIN_PAIR_QUERIES queries uses
     the stricter of its measurement and --threshold, and an unmeasured pair uses --threshold.
   Combined:
   - both decide and agree (a header group agrees when it contains the similarity
     family) -> the similarity family (basis `both`);
   - header decides, similarity silent -> header result (basis `header only`);
   - similarity decides, header silent -> similarity family (basis `similarity only`);
   - both decide and disagree -> `unresolved:` (basis `disagree`);
   - neither decides -> `unresolved:` (basis `neither`).

`unresolved:<a>|<b>...` counts toward no family, group or cycle and is reported per
label on the unresolved/ambiguous line.

Standard library only.

Usage:
    assign_shared_sequences.py --multi multi_family_sequences.tsv --table canonical_families.tsv \
        --db NAME HEADER_FASTA MAP [--db ...] --out sequence_assignments.tsv \
        [--similarity placements.tsv --threshold T [--thresholds thresholds.tsv]] [--min-length L] \
        [--refs final_r.faa] [--pfam-calls pfam_calls.tsv]
"""
import argparse
import collections
import csv
import hashlib
import itertools
import re
import statistics
import sys

ONT = re.compile(r"ontology=(\S+?)[\s\]]")
MIN_PAIR_QUERIES = 20  # pairs measured on fewer queries use the stricter of their threshold and --threshold
FUSION_LENGTH = 1.25  # as in place_unresolved.py (DECISIONS 2026-10-29)
FAM = re.compile(r"([^;\[]+)\[([^\]]+)\]")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--multi", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--db", nargs=3, action="append", required=True, metavar=("NAME", "HEADER_FASTA", "MAP"))
    p.add_argument("--out", required=True)
    p.add_argument("--similarity")
    p.add_argument("--threshold", type=float)
    p.add_argument("--thresholds")
    p.add_argument("--min-length", type=int, default=0)
    p.add_argument("--refs", help="reference FASTA from place_unresolved.py prepare (fusion lengths)")
    p.add_argument("--pfam-calls", help="pfam_domains.py call output (adds Pfam fusion calls only)")
    a = p.parse_args()
    if (a.similarity or a.thresholds) and a.threshold is None:
        p.error("--similarity and --thresholds need --threshold")

    canon, group, keep, rest = {}, {}, {}, {}
    weak_header, declared = set(), set()
    sig = collections.defaultdict(set)
    fsig = collections.defaultdict(set)  # fusion signatures: sig plus split selectors, as in place_unresolved.py
    with open(a.table, newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            k, c = (r["source_db"], r["source_family"]), r["canonical_family"]
            if r["selector"] == "rest":
                rest[k] = c
            else:
                canon[k] = c
                if r["selector"].startswith("ontology:"):
                    keep[k] = set(r["selector"].split(":", 1)[1].split(","))
                    fsig[c] |= keep[k]
                sig[c] |= {x for x in (r["ko"], r["cog"]) if x}
                fsig[c] |= sig[c]
            group[c] = r["ambiguity_group"]
            if r["header_evidence"] == "insufficient":
                weak_header.add(c)
            if r["fusion"] == "declared":
                declared.add(c)

    median = {}
    if a.refs:
        lengths, fam, n = collections.defaultdict(list), None, 0
        with open(a.refs) as fh:
            for line in fh:
                if line.startswith(">"):
                    if fam is not None:
                        lengths[fam].append(n)
                    fam, n = line[1:].split("|", 1)[0], 0
                else:
                    n += len(line.strip())
        if fam is not None:
            lengths[fam].append(n)
        median = {c: statistics.median(v) for c, v in lengths.items()}

    sim = {}
    if a.similarity:
        with open(a.similarity, newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                sim[r["seq_md5"]] = {c: float(b) for c, b in (x.rsplit(":", 1) for x in r["scores"].split(";"))}
    pfam_fusion = collections.defaultdict(list)  # md5 -> pairs Pfam calls a fusion (decidable pairs only)
    if a.pfam_calls:
        with open(a.pfam_calls, newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if r["set"] == "query" and r["call"] == "fusion":
                    pfam_fusion[r["name"]].append(r["pair"])
        if not pfam_fusion:
            sys.exit(f"no Pfam fusion calls on shared queries in {a.pfam_calls}")
    pair_t = {}
    if a.thresholds:
        with open(a.thresholds, newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                t = float("inf") if r["threshold"] == "none" else float(r["threshold"])
                # too few queries to relax the default, but enough to tighten it
                if int(r["n_queries"]) < MIN_PAIR_QUERIES:
                    t = max(t, a.threshold)
                pair_t[tuple(sorted((r["family_a"], r["family_b"])))] = t

    multi = {}
    need = collections.defaultdict(set)
    with open(a.multi) as fh:
        next(fh)
        for line in fh:
            md5, _, fams, ids = line.rstrip("\n").split("\t")
            fs = {(d, f) for f, ds in FAM.findall(fams) for d in ds.split(",")}
            multi[md5] = (fs, ids.split(","))
            for i in ids.split(","):
                d, sid = i.split("|", 1)
                need[d].add(sid)
    split_ids = collections.defaultdict(set)  # (db, id) -> split families it belongs to
    for name, _, mp in a.db:
        with open(mp) as fh:
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) >= 2 and (name, f[1]) in keep:
                    split_ids[(name, f[0])].add((name, f[1]))
                    need[name].add(f[0])

    onts = collections.defaultdict(set)  # target headers
    all_onts = collections.defaultdict(set)  # target and homolog headers (fusion test)
    md5_of, length = {}, {}
    for name, fa, _ in a.db:
        sid, buf = None, []

        def flush():
            if sid is not None and sid in need[name]:
                seq = "".join(buf).upper()
                length[(name, sid)] = len(seq)
                if (name, sid) in split_ids:
                    md5_of[(name, sid)] = hashlib.md5(seq.encode()).hexdigest()

        with open(fa) as fh:
            for line in fh:
                if line.startswith(">"):
                    flush()
                    sid, _, ann = line[1:].rstrip("\n").partition(" ")
                    buf = []
                    m = ONT.search(ann + " ") if sid in need[name] else None
                    if m:
                        all_onts[(name, sid)].add(m.group(1))
                        if " homolog " not in f" {ann} ":
                            onts[(name, sid)].add(m.group(1))
                else:
                    buf.append(line.strip())
            flush()

    def canonical(k, ids):
        if k not in keep:
            return canon[k]
        seen = set().union(*(onts.get(tuple(i.split("|", 1)), set()) for i in ids if i.startswith(k[0] + "|")))
        return canon[k] if seen & keep[k] else rest[k]

    def is_fusion(cs, ids, seq_len):
        if not median or declared & set(cs) or any(c not in median for c in cs):
            return False
        if any(seq_len < FUSION_LENGTH * median[c] for c in cs):
            return False
        seen = set().union(*(all_onts.get(tuple(i.split("|", 1)), set()) for i in ids))
        return len({group[c] or c for c in cs if fsig[c] & seen}) >= 2

    todo = {md5: v for md5, v in multi.items()}
    for (d, sid), fs in split_ids.items():
        md5 = md5_of.get((d, sid))
        if md5 is None:
            sys.exit(f"split family member {d}|{sid} has no sequence in the FASTA")
        if md5 not in todo:
            todo[md5] = (fs, [f"{d}|{sid}"])

    def header_call(cs, seen):
        if weak_header & set(cs):
            return None
        match = sorted(c for c in cs if sig[c] & seen)
        if len(match) == 1:
            return match[0]
        mgs = {group[c] for c in match}
        if match and len(mgs) == 1 and "" not in mgs:
            return f"group:{mgs.pop()}"
        return None

    def similarity_call(md5, cs):
        if md5 not in sim:
            return None
        # candidates in one ambiguity group compete as one unit (their best score), so an
        # inseparable pair inside a group does not stop a decision between the group and others
        units = collections.defaultdict(list)
        for c in cs:
            units[f"group:{group[c]}" if group[c] else c].append(c)
        if len(units) < 2:
            return None
        score = sorted(((max(sim[md5].get(c, 0.0) for c in ms), u) for u, ms in units.items()), reverse=True)
        (b1, u1), (b2, u2) = score[0], score[1]
        if b1 == 0:
            return None
        # strictest threshold over family pairs across the two leading units; a measured pair
        # that never reaches the error target (inf) means similarity never decides
        t = max(pair_t.get(tuple(sorted(pr)), a.threshold) for pr in itertools.product(units[u1], units[u2]))
        # a measured T can be 1.0, so require a strictly higher score: a tie never decides
        return u1 if b1 > b2 and (b2 == 0 or b1 / b2 >= t) else None

    kinds = collections.Counter()
    unresolved = collections.Counter()
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["seq_md5", "canonical_families", "assignment", "basis"])
        for md5 in sorted(todo):
            fs, ids = todo[md5]
            per_row = {k: canonical(k, ids) for k in fs}
            cs = sorted(set(per_row.values()))
            if len(cs) == 1:
                moved = [f"{k[0]}:{k[1]}" for k, c in per_row.items() if c != canon[k]]
                if moved:
                    kinds["split"] += 1
                    keeps = sorted(set().union(*(keep[tuple(m.split(":", 1))] for m in moved)))
                    w.writerow([md5, cs[0], cs[0], f"split {','.join(sorted(moved))}: no {'/'.join(keeps)} header"])
                continue
            gs = {group[c] for c in cs}
            seq_len = max(length.get(tuple(i.split("|", 1)), 0) for i in ids)
            unres = "unresolved:" + "|".join(cs)
            if len(gs) == 1 and "" not in gs:
                assign, basis = f"group:{gs.pop()}", "one ambiguity group"
            elif seq_len < a.min_length:
                assign, basis = unres, f"fragment ({seq_len} aa < {a.min_length})"
            elif is_fusion(cs, ids, seq_len):
                assign, basis = unres, "fusion"
            elif md5 in pfam_fusion:
                assign, basis = unres, f"pfam fusion ({','.join(sorted(pfam_fusion[md5]))})"
            else:
                seen = set().union(*(onts.get(tuple(i.split("|", 1)), set()) for i in ids))
                h, s = header_call(cs, seen), similarity_call(md5, cs) if a.similarity else None
                if h and s:
                    hg = h.split(":", 1)[1] if h.startswith("group:") else group[h]
                    sg = s.split(":", 1)[1] if s.startswith("group:") else group[s]
                    agree = h == s or (h.startswith("group:") and hg == sg) or (s.startswith("group:") and hg == sg)
                    assign, basis = (s, "both") if agree else (unres, f"disagree (header {h}, similarity {s})")
                elif h:
                    assign, basis = h, "header only"
                elif s:
                    assign, basis = s, "similarity only"
                else:
                    assign, basis = unres, "neither"
            kinds[basis.split(" (")[0]] += 1
            if assign.startswith("unresolved:"):
                unresolved[assign] += 1
            w.writerow([md5, ",".join(cs), assign, basis])

    print(f"assigned sequences: {sum(kinds.values())}; " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    print(f"unresolved labels: {len(unresolved)} ({sum(unresolved.values())} sequences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
