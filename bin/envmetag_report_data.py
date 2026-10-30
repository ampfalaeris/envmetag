#!/usr/bin/env python3
"""Collect SingleM outputs, and fastp's read and insert-size summary, into one JSON file for the envmetag report.

The report template (assets/envmetag_report.qmd) only renders; every number it shows
comes from the JSON written here. Inputs are the files staged by the ENVMETAG_REPORT
process, not the published index files. The script fails, rather than writing a partial
file, when a sample is missing from any input, a table is empty or malformed, or a
sample's per-rank relative abundances (including `unassigned`) do not sum to ~100%.

Abundances are shares of prokaryotic marker-gene coverage, not of reads; the report
states this next to every plot.

From fastp's JSON the report takes each sample's mean read lengths and its insert sizes:
the share of read pairs whose mates overlap, and the median insert of those pairs. With
paired input, SingleM 0.21.4 counts a fragment once where both mates cover a marker
window, while `prokaryotic_fraction` divides by the bases of both reads, so overlapping
mates make the fraction run low (DECISIONS.md, "First real-data check of SingleM's
prokaryotic fraction"). fastp measures insert sizes only for pairs whose mates overlap;
it counts the others as `unknown`.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 2  # 2: per-sample `library` (fastp read lengths and insert sizes)
RANKS = ("domain", "phylum", "class", "order", "family", "genus", "species")
# `singlem summarise --output-taxonomic-level-coverage` writes level numbers (1 = domain ...
# 7 = species; root is 0 and skipped) unless a sample has 7 or 8 distinct levels, in which
# case it writes names (SingleM 0.21.4, condense.py `taxonomic_level_coverage_table`).
LEVEL_NUMBERS = {str(i + 1): rank for i, rank in enumerate(RANKS)}
SUM_TOLERANCE = 0.5  # percentage points; SingleM rounds each value to 2 decimals
BY_RANK_NAME = re.compile(r"by_rank-([a-z]+)\.tsv$")

PROFILE_HEADER = ["sample", "coverage", "taxonomy"]
FRACTION_COLUMNS = (
    "sample",
    "bacterial_archaeal_bases",
    "metagenome_size",
    "read_fraction",
    "average_bacterial_archaeal_genome_size",
    "warning",
)
LEVEL_COVERAGE_HEADER = ["sample", "level", "coverage", "relative abundance (%)"]
EXTRAS_HEADER = ["sample", "coverage", "full_coverage", "relative_abundance", "level", "taxonomy"]
# `coverage` (assigned exactly at a node) and `full_coverage` (node plus descendants) are
# rounded to 2 decimals, so a parent and its children can disagree by ~0.005 per value
COVERAGE_TOLERANCE = 0.01


class InputError(Exception):
    """An input file is missing, malformed, or inconsistent with the sample list."""


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows:
        raise InputError(f"{path.name} is empty")
    return rows[0], rows[1:]


def to_float(value: str, path: Path, what: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise InputError(f"{path.name}: {what} is not a number: {value!r}") from None


def to_int(value: str, path: Path, what: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise InputError(f"{path.name}: {what} is not an integer: {value!r}") from None


def check_samples(found: list[str], expected: list[str], source: str) -> None:
    duplicates = sorted({s for s in found if found.count(s) > 1})
    if duplicates:
        raise InputError(f"{source}: duplicate sample(s): {', '.join(duplicates)}")
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    if missing or extra:
        raise InputError(
            f"{source}: samples do not match the samplesheet"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; unexpected: {', '.join(extra)}" if extra else "")
        )


def read_profiles(paths: list[Path], samples: list[str]) -> dict[str, list[dict]]:
    """Per-sample condensed profiles: one file per sample, sorted by coverage (descending)."""
    profiles: dict[str, list[dict]] = {}
    for path in paths:
        header, rows = read_tsv(path)
        if header != PROFILE_HEADER:
            raise InputError(f"{path.name}: expected header {PROFILE_HEADER}, found {header}")
        if not rows:
            raise InputError(f"{path.name}: no taxa; SingleM assigned nothing in this sample")
        names = {row[0] for row in rows}
        if len(names) != 1:
            raise InputError(f"{path.name}: expected one sample, found {sorted(names)}")
        sample = names.pop()
        if sample in profiles:
            raise InputError(f"profiles: duplicate sample: {sample}")
        taxa = [
            {"taxonomy": row[2], "lineage": pretty_lineage(row[2]), "coverage": to_float(row[1], path, "coverage")}
            for row in rows
        ]
        profiles[sample] = sorted(taxa, key=lambda t: (-t["coverage"], t["taxonomy"]))
    check_samples(list(profiles), samples, "profiles")
    return {sample: profiles[sample] for sample in samples}


def read_fractions(paths: list[Path], samples: list[str]) -> list[dict]:
    """`singlem prokaryotic_fraction` results, one row per file."""
    overview: dict[str, dict] = {}
    for path in paths:
        header, rows = read_tsv(path)
        missing = [column for column in FRACTION_COLUMNS if column not in header]
        if missing:
            raise InputError(f"{path.name}: missing column(s): {', '.join(missing)}")
        if len(rows) != 1:
            raise InputError(f"{path.name}: {len(rows)} result rows; expected exactly 1")
        row = dict(zip(header, rows[0]))
        sample = row["sample"]
        if sample in overview:
            raise InputError(f"prokaryotic fractions: duplicate sample: {sample}")
        overview[sample] = {
            "id": sample,
            "read_fraction": to_float(row["read_fraction"], path, "read_fraction"),
            "bacterial_archaeal_bases": to_int(row["bacterial_archaeal_bases"], path, "bacterial_archaeal_bases"),
            "metagenome_size": to_int(row["metagenome_size"], path, "metagenome_size"),
            "average_genome_size_bp": to_int(
                row["average_bacterial_archaeal_genome_size"], path, "average_bacterial_archaeal_genome_size"
            ),
            "warning": row["warning"].strip() or None,
        }
    check_samples(list(overview), samples, "prokaryotic fractions")
    return [overview[sample] for sample in samples]


def strip_rank_prefix(name: str) -> str:
    """`g__Methanococcus` -> `Methanococcus` (a bare or empty-named field is kept as is)."""
    name = name.strip()
    return name.split("__", 1)[1] if "__" in name and name.split("__", 1)[1] else name


def short_label(taxonomy: str) -> str:
    """`Root; d__Bacteria; p__Bacillota` -> `Bacillota`."""
    return strip_rank_prefix(taxonomy.split(";")[-1])


def pretty_lineage(taxonomy: str) -> str:
    """`Root; d__Bacteria; p__Bacillota` -> `Bacteria › Bacillota` (for display only)."""
    fields = [f.strip() for f in taxonomy.split(";")]
    if fields and fields[0] == "Root":
        fields = fields[1:]
    return " › ".join(strip_rank_prefix(f) for f in fields) or "Root"


def read_by_rank(path: Path, samples: list[str], top_n: int) -> dict:
    """One site-by-taxon table: top-N taxa by their highest abundance in any sample, the rest pooled."""
    header, rows = read_tsv(path)
    if not header or header[0] != "taxonomy":
        raise InputError(f"{path.name}: first column must be 'taxonomy', found {header[:1]}")
    columns = header[1:]
    check_samples(columns, samples, path.name)
    if not rows:
        raise InputError(f"{path.name}: no rows")

    unassigned = None
    taxa = []
    seen = set()
    for row in rows:
        if len(row) != len(header):
            raise InputError(f"{path.name}: row has {len(row)} fields; expected {len(header)}")
        name = row[0]
        if name in seen:
            raise InputError(f"{path.name}: duplicate taxon: {name}")
        seen.add(name)
        values = {s: to_float(v, path, f"{name} / {s}") for s, v in zip(columns, row[1:])}
        if name == "unassigned":
            unassigned = values
        else:
            taxa.append({"taxonomy": name, "values": values})
    if unassigned is None:
        raise InputError(f"{path.name}: no 'unassigned' row")

    for sample in samples:
        total = unassigned[sample] + sum(t["values"][sample] for t in taxa)
        if abs(total - 100.0) > SUM_TOLERANCE:
            raise InputError(
                f"{path.name}: relative abundances for {sample} sum to {total:.2f}%, not 100% "
                f"(tolerance {SUM_TOLERANCE})"
            )

    # Rank by the largest value in any one sample: a taxon that dominates a single sample
    # keeps its own colour even if it is absent elsewhere. Ties break on the full lineage.
    taxa.sort(key=lambda t: (-max(t["values"].values()), t["taxonomy"]))
    kept, pooled = taxa[:top_n], taxa[top_n:]

    short = [short_label(t["taxonomy"]) for t in kept]
    labels = [
        # same short name under different parents: add the parent to tell them apart
        f"{name} ({short_label(';'.join(taxon['taxonomy'].split(';')[:-1]))})" if short.count(name) > 1 else name
        for name, taxon in zip(short, kept)
    ]

    return {
        "available": True,
        "taxa": [
            {
                "taxonomy": t["taxonomy"],
                "lineage": pretty_lineage(t["taxonomy"]),
                "label": label,
                "values": {s: t["values"][s] for s in samples},
            }
            for t, label in zip(kept, labels)
        ],
        "other": (
            {s: round(sum(t["values"][s] for t in pooled), 4) for s in samples} if pooled else None
        ),
        "other_count": len(pooled),
        "unassigned": {s: unassigned[s] for s in samples},
    }


def read_ranks(paths: list[Path], samples: list[str], top_n: int) -> dict:
    """All ranks, domain to species. A rank without a file had no assignments in this run."""
    by_rank: dict[str, Path] = {}
    for path in paths:
        match = BY_RANK_NAME.search(path.name)
        if not match or match.group(1) not in RANKS:
            raise InputError(f"{path.name}: not a SingleM by_rank-<rank>.tsv file")
        rank = match.group(1)
        if rank in by_rank:
            raise InputError(f"two by_rank files for rank {rank}: {by_rank[rank].name}, {path.name}")
        by_rank[rank] = path
    if not by_rank:
        raise InputError("no by_rank files; SingleM assigned nothing at any rank")
    return {
        rank: read_by_rank(by_rank[rank], samples, top_n) if rank in by_rank else {"available": False}
        for rank in RANKS
    }


def read_level_coverage(path: Path, samples: list[str]) -> dict[str, dict]:
    """Coverage assigned at each rank (how far down SingleM resolved each sample)."""
    header, rows = read_tsv(path)
    if header != LEVEL_COVERAGE_HEADER:
        raise InputError(f"{path.name}: expected header {LEVEL_COVERAGE_HEADER}, found {header}")
    if not rows:
        raise InputError(f"{path.name}: no rows")
    table: dict[str, dict] = {}
    for row in rows:
        sample, level = row[0], row[1]
        if level == "root":
            continue
        rank = LEVEL_NUMBERS.get(level, level)
        if rank not in RANKS:
            raise InputError(f"{path.name}: unknown level {level!r}")
        per_sample = table.setdefault(sample, {})
        if rank in per_sample:
            raise InputError(f"{path.name}: {sample} has level {rank} twice")
        per_sample[rank] = {
            "coverage": to_float(row[2], path, "coverage"),
            "relative_abundance": to_float(row[3], path, "relative abundance"),
        }
    check_samples(list(table), samples, path.name)
    result = {}
    for sample in samples:
        # SingleM omits levels with no taxon nodes in a sample; those carry no coverage
        levels = {rank: table[sample].get(rank, {"coverage": 0.0, "relative_abundance": 0.0}) for rank in RANKS}
        total = sum(level["relative_abundance"] for level in levels.values())
        if abs(total - 100.0) > SUM_TOLERANCE:
            raise InputError(f"{path.name}: level shares for {sample} sum to {total:.2f}%, not 100%")
        result[sample] = levels
    return result


def sankey_flows(tree: dict[str, dict], sample: str, min_percent: float) -> dict:
    """Nodes and links for one sample's checked taxon tree (see `read_sankey`)."""
    levels = ("root",) + RANKS
    total = tree["Root"]["full"]
    nodes: list[dict] = []
    index: dict[str, int] = {}
    links: dict[tuple[int, int], float] = {}

    def node_id(key: str, label: str, rank: str, lineage: str) -> int:
        if key not in index:
            index[key] = len(nodes)
            nodes.append({"label": label, "rank": rank, "lineage": lineage})
        return index[key]

    def link(source: int, target: int, value: float) -> None:
        links[(source, target)] = links.get((source, target), 0.0) + value

    def visit(taxonomy: str, source: int) -> None:
        node = tree[taxonomy]
        rank_index = levels.index(node["level"])
        if node["coverage"] > 0 and rank_index < len(levels) - 1:
            if taxonomy == "Root":
                target = node_id("unresolved|root", "Unassigned at domain", "domain", "")
            else:
                target = node_id(
                    f"unresolved|{node['level']}", f"Unresolved below {node['level']}", levels[rank_index + 1], ""
                )
            link(source, target, node["coverage"] / total * 100)
        # children in a fixed order: largest first, ties by lineage
        for child in sorted(node["children"], key=lambda c: (-tree[c]["full"], c)):
            share = tree[child]["full"] / total * 100
            child_level = tree[child]["level"]
            if share >= min_percent:
                target = node_id(child, short_label(child), child_level, pretty_lineage(child))
                link(source, target, share)
                visit(child, target)
            else:
                other = node_id(f"other|{child_level}", f"Other {child_level} (<{min_percent:g}%)", child_level, "")
                link(source, other, share)

    visit("Root", node_id("Root", sample, "sample", ""))
    return {
        "nodes": nodes,
        "links": [{"source": s, "target": t, "value": round(v, 4)} for (s, t), v in links.items()],
    }


def read_sankey(path: Path, samples: list[str], min_percent: float) -> dict[str, dict]:
    """Per-sample flows from domain down to the deepest rank, from `profile_extras.tsv`.

    A link's value is the child's share of the sample's coverage (child plus descendants).
    Children below `min_percent` flow into one "Other" node per rank; coverage assigned
    exactly at a node (not resolved deeper) flows into an "Unresolved below <rank>" node.
    A taxon never has more coverage than its parent, so a kept taxon's parent is always
    kept, and every sample's flows out of the root sum to 100%.
    """
    header, rows = read_tsv(path)
    if header != EXTRAS_HEADER:
        raise InputError(f"{path.name}: expected header {EXTRAS_HEADER}, found {header}")
    if not rows:
        raise InputError(f"{path.name}: no rows")
    levels = ("root",) + RANKS
    nodes_by_sample: dict[str, dict[str, dict]] = {}
    for row in rows:
        sample, level, taxonomy = row[0], row[4], row[5]
        if level not in levels:
            raise InputError(f"{path.name}: unknown level {level!r}")
        per_sample = nodes_by_sample.setdefault(sample, {})
        if taxonomy in per_sample:
            raise InputError(f"{path.name}: {sample} has {taxonomy} twice")
        per_sample[taxonomy] = {
            "level": level,
            "coverage": to_float(row[1], path, "coverage"),
            "full": to_float(row[2], path, "full_coverage"),
            "children": [],
        }
    check_samples(list(nodes_by_sample), samples, path.name)

    result = {}
    for sample in samples:
        tree = nodes_by_sample[sample]
        if "Root" not in tree or tree["Root"]["full"] <= 0:
            raise InputError(f"{path.name}: {sample} has no Root row with coverage")
        for taxonomy, node in tree.items():
            if taxonomy == "Root":
                continue
            parent = ";".join(taxonomy.split(";")[:-1]).strip()
            if parent not in tree:
                raise InputError(f"{path.name}: {sample}: parent of {taxonomy} is missing")
            tree[parent]["children"].append(taxonomy)
        for taxonomy, node in tree.items():
            below = sum(tree[c]["full"] for c in node["children"])
            if abs(node["full"] - below - node["coverage"]) > COVERAGE_TOLERANCE * (len(node["children"]) + 1):
                raise InputError(
                    f"{path.name}: {sample}: {taxonomy} full_coverage {node['full']} != its own coverage "
                    f"{node['coverage']} + children {below:.2f}"
                )

        result[sample] = sankey_flows(tree, sample, min_percent)
    return result


def read_fastp(paths: list[Path], samples: list[str]) -> dict[str, dict]:
    """Read lengths and insert sizes from fastp's JSON report, named `<sample>.fastp.json`."""
    library: dict[str, dict] = {}
    for path in paths:
        if not path.name.endswith(".fastp.json"):
            raise InputError(f"{path.name}: expected a file named <sample>.fastp.json")
        sample = path.name[: -len(".fastp.json")]
        if sample in library:
            raise InputError(f"fastp reports: duplicate sample: {sample}")
        try:
            report = json.loads(path.read_text())
            after = report["summary"]["after_filtering"]
            r1, r2 = after["read1_mean_length"], after["read2_mean_length"]
            histogram, unknown = report["insert_size"]["histogram"], report["insert_size"]["unknown"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise InputError(f"{path.name}: not a paired-end fastp JSON report ({err})") from None
        overlapping = sum(histogram)
        if overlapping + unknown == 0:
            raise InputError(f"{path.name}: no read pairs in the insert-size estimate")
        median = None
        if overlapping:
            seen = 0
            for size, count in enumerate(histogram):
                seen += count
                if seen >= overlapping / 2:
                    median = size
                    break
        library[sample] = {
            "read1_mean_length": r1,
            "read2_mean_length": r2,
            "overlapping_pairs_percent": round(100 * overlapping / (overlapping + unknown), 1),
            "median_insert_overlapping": median,
        }
    check_samples(list(library), samples, "fastp reports")
    return library


def build(args: argparse.Namespace) -> dict:
    samples = sorted(args.samples)
    if not samples:
        raise InputError("no samples given")
    check_samples(list(args.samples), samples, "--samples")
    if args.top_n < 1:
        raise InputError("--top-n must be at least 1")
    if not 0 < args.sankey_min_percent < 100:
        raise InputError("--sankey-min-percent must be between 0 and 100")
    overview = read_fractions(args.fractions, samples)
    library = read_fastp(args.fastp, samples)
    for row in overview:
        row["library"] = library[row["id"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "pipeline_version": args.pipeline_version,
            "metapackage": args.metapackage,
            "assignment_method": args.assignment_method,
            "top_n": args.top_n,
            "stacked_bar_max_samples": args.stacked_bar_max_samples,
            "sankey_min_percent": args.sankey_min_percent,
        },
        "samples": overview,
        "ranks": read_ranks(args.by_rank, samples, args.top_n),
        "level_coverage": read_level_coverage(args.level_coverage, samples),
        "sankey": read_sankey(args.extras, samples, args.sankey_min_percent),
        "profiles": read_profiles(args.profiles, samples),
        "links": {"multiqc": args.multiqc_link, "krona": args.krona_link},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--samples", nargs="+", required=True, help="sample ids from the samplesheet")
    parser.add_argument("--profiles", nargs="+", required=True, type=Path, help="per-sample SingleM profiles")
    parser.add_argument("--fractions", nargs="+", required=True, type=Path, help="prokaryotic_fraction TSVs")
    parser.add_argument("--by-rank", nargs="+", required=True, type=Path, help="singlem summarise by_rank-*.tsv")
    parser.add_argument("--level-coverage", required=True, type=Path, help="singlem summarise level coverage TSV")
    parser.add_argument("--extras", required=True, type=Path, help="singlem summarise profile_extras TSV")
    parser.add_argument("--fastp", nargs="+", required=True, type=Path, help="fastp JSON reports, <sample>.fastp.json")
    parser.add_argument("--pipeline-version", required=True)
    parser.add_argument("--metapackage", required=True, help="metapackage name shown in the report")
    parser.add_argument("--assignment-method", default=None, help="SingleM --assignment-method, if not the default")
    parser.add_argument("--top-n", type=int, default=15, help="taxa per rank with their own colour")
    parser.add_argument("--stacked-bar-max-samples", type=int, default=15)
    parser.add_argument(
        "--sankey-min-percent", type=float, default=1.0,
        help="taxa below this share of a sample's coverage are pooled as Other in the Sankey diagram",
    )
    parser.add_argument("--multiqc-link", required=True, help="relative path from the report to MultiQC")
    parser.add_argument("--krona-link", required=True, help="relative path from the report to the Krona plot")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        data = build(args)
    except InputError as error:
        sys.exit(f"ERROR: {error}")
    with args.output.open("w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
