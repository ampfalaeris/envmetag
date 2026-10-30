#!/usr/bin/env python3
"""Pfam domain test for fusion proteins: a candidate rule, measured against the length rule.

The rule is fixed in DECISIONS.md (2026-10-30, "Read caller: latent-class model planned;
Pfam domains for fusions") before the full run; this script implements it and nothing
it does is tuned on the results.

resolve: reads `hmmsearch --cut_ga --domtblout` output (run with fixed -Z and --domZ, so
domain E-values rank as hmmscan's do) and resolves overlaps as pfam_scan.pl does
(remove_overlaps_by_clan): hits on a sequence in order of i-Evalue; a hit is dropped if it
overlaps, in alignment coordinates, a kept hit of the same clan, unless Pfam declares the
pair nested (`#=GF NE` in Pfam-A.hmm.dat, either direction). Hits of different clans, or
of models without a clan, never remove each other.

call: builds per-pair signatures and calls fusions.
  - Unit: the clan; a model without a clan is its own unit (`--unit model` for the
    diagnostic).
  - Signature references: clean references (`set` loo or extra in the manifest) of typical
    length, 0.75-1.25 x their family's median length over all clean references in --refs.
  - A unit is a signature of family A against B if it occurs in >= 50% of A's signature
    references, in <= 5% of B's, and its summed aligned length per protein (median over
    A's signature references carrying it) is >= 25% of A's median length.
  - A sequence is a fusion of A and B if it carries a signature unit of A against B and
    one of B against A. A pair where either side has no signature is undecidable.
  - A family whose band keeps under 50% of its clean references (more than one length
    form) has no signatures, so its pairs are undecidable, until it is reviewed
    (`--reviewed`).
  - Pairs tested: for a shared query, every pair of its candidate families (--similarity);
    for a dropped fusion reference, its family against each partner (--dropped); for a
    clean reference, its family against every family it is paired with above.
  - For the open partial-domain guard, each call reports the query's summed aligned length
    on the partner's signature units as a share of the partner's median for those units.
  Diagnostics (signature sets only, never calls): all clean references instead of the band,
  10% instead of 5%, and model instead of clan units; pairs whose decidability changes are
  listed.

Standard library only.

scoped: writes the sequences the curation decision needs, with a manifest (name, set): the
leave-one-out sample (loo), every clean reference of --extra-family (extra), the shared
queries (query) and the fusion references `prepare` left out (dropped, fetched from the
source FASTAs by md5 of the uppercase sequence).

Usage:
    pfam_domains.py scoped --loo loo_q.faa --refs final_r.faa --extra-family gs_K00266 \
        --queries final_q.faa --dropped fusion_refs.tsv --sources SCYC.faa MCYC.faa NCYC.faa \
        --out-faa scoped.faa --manifest manifest.tsv
    pfam_domains.py resolve --domtbl scoped.domtbl --pfam PFAM_DIR --out resolved.tsv
    pfam_domains.py call --resolved resolved.tsv --faa scoped.faa \
        --manifest manifest.tsv --refs final_r.faa --similarity final_similarity.tsv \
        --dropped dropped.tsv --assignments sequence_assignments.tsv --out-prefix pfam
"""
import argparse
import collections
import csv
import gzip
import hashlib
import itertools
import statistics
import sys

BAND = (0.75, 1.25)
MIN_PRESENT = 0.50
MAX_OTHER = 0.05
MIN_SHARE = 0.25
MIN_BAND_KEPT = 0.50
CLEAN_SETS = {"loo", "extra"}


def read_pfam(pfam_dir):
    """Model name -> clan, accession; nested pairs (both directions)."""
    clan, acc, nested = {}, {}, collections.defaultdict(set)
    with gzip.open(f"{pfam_dir}/Pfam-A.hmm.dat.gz", "rt") as fh:
        name = None
        for line in fh:
            if line.startswith("#=GF ID"):
                name = line.split()[2]
            elif line.startswith("#=GF AC"):
                acc[name] = line.split()[2].split(".")[0]
            elif line.startswith("#=GF CL"):
                clan[name] = line.split()[2]
            elif line.startswith("#=GF NE"):
                other = line.split()[2]
                nested[name].add(other)
                nested[other].add(name)
    return clan, acc, nested


def read_fasta(path):
    name, buf = None, []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if name is not None:
                    yield name, "".join(buf)
                parts = line[1:].split()  # MCycDB has 24 records with an empty header
                name, buf = (parts[0] if parts else ""), []
            else:
                buf.append(line)
    if name is not None:
        yield name, "".join(buf)


def scoped(a):
    recs = {}

    def add(name, seq, kind):
        if name in recs and recs[name][0] != seq:
            sys.exit(f"name {name} with two sequences")
        recs.setdefault(name, (seq, kind))

    for n, s in read_fasta(a.loo):
        add(n, s, "loo")
    extra = set(a.extra_family)
    for n, s in read_fasta(a.refs):
        if n.split("|", 1)[0] in extra:
            add(n, s, "extra")
    for n, s in read_fasta(a.queries):
        add(n, s, "query")
    with open(a.dropped) as fh:
        want = {r["seq_md5"]: r["family"] for r in csv.DictReader(fh, delimiter="\t")}
    found = {}
    for src in a.sources:
        for _, s in read_fasta(src):
            s = s.upper()
            m = hashlib.md5(s.encode()).hexdigest()
            if m in want:
                found.setdefault(m, s)
    if set(want) - set(found):
        sys.exit(f"{len(set(want) - set(found))} dropped md5s not found in the source FASTAs")
    for m, s in sorted(found.items()):
        add(f"{want[m]}|{m}", s, "dropped")
    with open(a.out_faa, "w") as fa, open(a.manifest, "w") as mf:
        mf.write("name\tset\n")
        for n, (s, k) in recs.items():
            fa.write(f">{n}\n{s}\n")
            mf.write(f"{n}\t{k}\n")
    c = collections.Counter(k for _, k in recs.values())
    print(f"sequences {len(recs)} ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))}); "
          f"residues {sum(len(s) for s, _ in recs.values())}")


def resolve(a):
    clan, acc, nested = read_pfam(a.pfam)
    hits = collections.defaultdict(list)
    n_rows = 0
    with open(a.domtbl) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            c = line.split()
            # domtblout: 0 target, 3 query (model), 12 i-Evalue, 13 domain score, 17-18 ali from/to
            hits[c[0]].append((float(c[12]), c[3], int(c[17]), int(c[18]), float(c[13])))
            n_rows += 1
    if n_rows == 0:
        sys.exit(f"no domain rows in {a.domtbl}")
    kept_total = 0
    with open(a.out, "w", newline="") as out:
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        w.writerow(["name", "model", "accession", "clan", "ali_from", "ali_to", "i_evalue", "bits"])
        for name in sorted(hits):
            kept = []
            for ev, model, start, end, bits in sorted(hits[name]):
                if model not in acc:
                    sys.exit(f"model {model} not in Pfam-A.hmm.dat")
                clash = False
                for _, m2, s2, e2, _ in kept:
                    same_clan = model in clan and clan.get(m2) == clan[model]
                    if same_clan and start <= e2 and s2 <= end and m2 not in nested[model]:
                        clash = True
                        break
                if not clash:
                    kept.append((ev, model, start, end, bits))
            for ev, model, start, end, bits in sorted(kept, key=lambda k: k[2]):
                w.writerow([name, model, acc[model], clan.get(model, ""), start, end, f"{ev:.3g}", bits])
            kept_total += len(kept)
    print(f"sequences {len(hits)}; domain rows {n_rows}; kept after clan resolution {kept_total}")


def read_fasta_lengths(path):
    lengths, name = {}, None
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                name = line[1:].split()[0]
                lengths[name] = 0
            else:
                lengths[name] += len(line.strip())
    return lengths


def units_per_sequence(resolved, unit):
    """name -> {unit: summed aligned length}."""
    per = collections.defaultdict(lambda: collections.defaultdict(int))
    with open(resolved) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            u = r["accession"] if unit == "model" else (r["clan"] or r["accession"])
            per[r["name"]][u] += int(r["ali_to"]) - int(r["ali_from"]) + 1
    return per


def signatures(fams, sig_refs, per, median_len, pairs, max_other):
    """(A, B) -> {unit: (freq in A, freq in B, share of A's median)} for each pair."""
    freq, share = {}, {}
    for f in fams:
        refs = sig_refs.get(f, []) if f in median_len else []
        counts, lens = collections.Counter(), collections.defaultdict(list)
        for n in refs:
            for u, length in per.get(n, {}).items():
                counts[u] += 1
                lens[u].append(length)
        freq[f] = {u: c / len(refs) for u, c in counts.items()} if refs else {}
        share[f] = {u: statistics.median(v) / median_len[f] for u, v in lens.items()}
    out = {}
    for x, y in pairs:
        for p, q in ((x, y), (y, x)):
            out[(p, q)] = {
                u: (fp, freq[q].get(u, 0.0), share[p][u])
                for u, fp in freq[p].items()
                if fp >= MIN_PRESENT and freq[q].get(u, 0.0) <= max_other and share[p][u] >= MIN_SHARE
            }
    return out


def call(a):
    lengths = read_fasta_lengths(a.faa)
    with open(a.manifest) as fh:
        kind = {r["name"]: r["set"] for r in csv.DictReader(fh, delimiter="\t")}
    if set(kind) != set(lengths):
        sys.exit("manifest and FASTA name different sequences")

    all_clean = collections.defaultdict(list)
    for n, ln in read_fasta_lengths(a.refs).items():
        all_clean[n.split("|", 1)[0]].append(ln)
    median_len = {f: statistics.median(v) for f, v in all_clean.items()}

    # Pairs and the sequences to call.
    to_call = []  # (name, set, [(A, B), ...])
    pairs = set()
    with open(a.similarity) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["seq_md5"] not in kind:
                sys.exit(f"query {r['seq_md5']} not in the scoped FASTA")
            ps = [tuple(sorted(p)) for p in itertools.combinations(sorted(r["candidates"].split(",")), 2)]
            pairs.update(ps)
            to_call.append((r["seq_md5"], "query", ps))
    queries_seen = {n for n, _, _ in to_call}
    missing_q = [n for n, k in kind.items() if k == "query" and n not in queries_seen]
    if missing_q:
        sys.exit(f"{len(missing_q)} shared queries have no row in {a.similarity}")
    with open(a.dropped) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            name = f"{r['family']}|{r['seq_md5']}"
            if kind.get(name) != "dropped":
                sys.exit(f"dropped reference {name} not in the scoped FASTA")
            ps = [tuple(sorted((r["family"], p))) for p in r["partners"].split(",")]
            pairs.update(ps)
            to_call.append((name, "dropped", ps))
    partners = collections.defaultdict(set)
    for x, y in pairs:
        partners[x].add(y)
        partners[y].add(x)
    for n, k in sorted(kind.items()):
        if k in CLEAN_SETS:
            f = n.split("|", 1)[0]
            ps = [tuple(sorted((f, p))) for p in sorted(partners.get(f, ()))]
            if ps:
                to_call.append((n, k, ps))

    fams = sorted({f for p in pairs for f in p})
    # Families with no clean reference (ddhB, nifW, nrfB on the pinned commits) have no
    # signatures, so every pair with them is undecidable; they are listed, not skipped.
    no_refs = [f for f in fams if f not in median_len]
    for f in no_refs:
        print(f"no clean references, pairs undecidable: {f}")

    clean = collections.defaultdict(list)
    for n, k in kind.items():
        if k in CLEAN_SETS:
            clean[n.split("|", 1)[0]].append(n)
    banded = {
        f: [n for n in v if BAND[0] * median_len[f] <= lengths[n] <= BAND[1] * median_len[f]]
        for f, v in clean.items()
    }
    # A family whose band keeps under half its clean references has more than one length
    # form, and the band may keep the wrong one (hdrA1, NR). Its pairs are undecidable
    # until the family is reviewed and listed in --reviewed.
    reviewed = set(a.reviewed.split(",")) if a.reviewed else set()
    thin = sorted(f for f in fams if f in clean and len(banded[f]) < MIN_BAND_KEPT * len(clean[f])
                  and f not in reviewed)
    for f in thin:
        print(f"band keeps {len(banded[f])} of {len(clean[f])} clean references, pairs undecidable: {f}")
        banded[f] = []

    per_clan = units_per_sequence(a.resolved, "clan")
    per_model = units_per_sequence(a.resolved, "model")
    primary = signatures(fams, banded, per_clan, median_len, pairs, MAX_OTHER)
    diagnostics = {
        "all_refs_5": signatures(fams, clean, per_clan, median_len, pairs, MAX_OTHER),
        "all_refs_10": signatures(fams, clean, per_clan, median_len, pairs, 0.10),
        "band_10": signatures(fams, banded, per_clan, median_len, pairs, 0.10),
        "model_units": signatures(fams, banded, per_model, median_len, pairs, MAX_OTHER),
    }

    # Signature table.
    with open(f"{a.out_prefix}_signatures.tsv", "w", newline="") as out:
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        w.writerow(["family", "against", "n_signature_refs", "n_against_refs", "median_len",
                    "units", "decidable_pair"] + [f"units_{d}" for d in diagnostics])
        for x, y in sorted(pairs):
            decidable = bool(primary[(x, y)]) and bool(primary[(y, x)])
            for p, q in ((x, y), (y, x)):
                fmt = lambda s: ";".join(
                    f"{u}:{fp:.2f}/{fq:.2f}/{sh:.2f}" for u, (fp, fq, sh) in sorted(s.items()))
                w.writerow([p, q, len(banded.get(p, [])), len(banded.get(q, [])), median_len.get(p, ""),
                            fmt(primary[(p, q)]), "yes" if decidable else "no"]
                           + [fmt(diagnostics[d][(p, q)]) for d in diagnostics])

    # Unit medians for the partial-domain report: per family, per unit, over signature refs.
    unit_median = collections.defaultdict(dict)
    for f in fams:
        lens = collections.defaultdict(list)
        for n in banded.get(f, []):
            for u, ln in per_clan.get(n, {}).items():
                lens[u].append(ln)
        unit_median[f] = {u: statistics.median(v) for u, v in lens.items()}

    # Current calls, for the cross-tabulation.
    with open(a.assignments) as fh:
        basis = {r["seq_md5"]: r["basis"] for r in csv.DictReader(fh, delimiter="\t")}

    counts = collections.Counter()
    with open(f"{a.out_prefix}_calls.tsv", "w", newline="") as out:
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        w.writerow(["name", "set", "length", "pair", "call", "units_a", "units_b",
                    "partner_cover_a", "partner_cover_b", "current"])
        for name, k, ps in to_call:
            units = per_clan.get(name, {})
            if k == "query":
                current = "fusion" if basis.get(name) == "fusion" else (basis.get(name) or "none")
            elif k == "dropped":
                current = "fusion"
            else:
                current = "clean"
            for x, y in ps:
                sx, sy = primary[(x, y)], primary[(y, x)]
                hx = sorted(u for u in sx if u in units)
                hy = sorted(u for u in sy if u in units)
                if not (sx and sy):
                    c = "undecidable"
                elif hx and hy:
                    c = "fusion"
                else:
                    c = "not_fusion"
                cover = lambda f, hs: (
                    f"{sum(units[u] for u in hs) / sum(unit_median[f][u] for u in hs):.2f}" if hs else "")
                w.writerow([name, k, lengths[name], f"{x}|{y}", c, ",".join(hx), ",".join(hy),
                            cover(x, hx), cover(y, hy), current])
                counts[(k, current, c)] += 1
    for key in sorted(counts):
        print("\t".join(key), counts[key], sep="\t")

    changed = [
        (d, x, y) for d, s in diagnostics.items() for x, y in sorted(pairs)
        if (bool(s[(x, y)]) and bool(s[(y, x)])) != (bool(primary[(x, y)]) and bool(primary[(y, x)]))
    ]
    print(f"pairs {len(pairs)}; decidable {sum(bool(primary[(x, y)]) and bool(primary[(y, x)]) for x, y in pairs)}")
    for d, x, y in changed:
        print(f"decidability differs under {d}: {x}|{y}")
    for f in fams:
        print(f"signature references {f}: {len(banded.get(f, []))} of {len(clean.get(f, []))} clean")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scoped")
    ps.add_argument("--loo", required=True, help="loo_threshold.py sample output")
    ps.add_argument("--refs", required=True, help="prepare --refs output")
    ps.add_argument("--extra-family", action="append", default=[],
                    help="add every clean reference of this family (repeatable)")
    ps.add_argument("--queries", required=True, help="prepare --queries output")
    ps.add_argument("--dropped", required=True, help="prepare --dropped output")
    ps.add_argument("--sources", nargs="+", required=True, help="source FASTAs, to fetch dropped references by md5")
    ps.add_argument("--out-faa", required=True)
    ps.add_argument("--manifest", required=True)
    pr = sub.add_parser("resolve")
    pr.add_argument("--domtbl", required=True)
    pr.add_argument("--pfam", required=True, help="directory with Pfam-A.hmm.dat.gz")
    pr.add_argument("--out", required=True)
    pc = sub.add_parser("call")
    pc.add_argument("--resolved", required=True)
    pc.add_argument("--faa", required=True, help="the scoped FASTA that was searched")
    pc.add_argument("--manifest", required=True, help="name, set (loo, extra, query, dropped)")
    pc.add_argument("--refs", required=True, help="all clean references (prepare --refs), for median lengths")
    pc.add_argument("--similarity", required=True, help="place_unresolved.py score output (candidates)")
    pc.add_argument("--dropped", required=True, help="prepare --dropped output")
    pc.add_argument("--assignments", required=True, help="sequence_assignments.tsv (current calls)")
    pc.add_argument("--reviewed", default="",
                    help="comma-separated families exempt from the under-half band rule after review")
    pc.add_argument("--out-prefix", required=True)
    a = ap.parse_args()
    {"scoped": scoped, "resolve": resolve, "call": call}[a.cmd](a)


if __name__ == "__main__":
    main()
