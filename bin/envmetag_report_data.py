#!/usr/bin/env python3
"""Collect SingleM outputs into one JSON file for the envmetag report.

The report template (assets/envmetag_report.qmd) only renders; every number it shows
comes from the JSON written here. Inputs are the files staged by the ENVMETAG_REPORT
process, not the published index files. The script fails, rather than writing a partial
file, when a sample is missing from any input, a table is empty or malformed, or a
sample's per-rank relative abundances (including `unassigned`) do not sum to ~100%.

Abundances are shares of prokaryotic marker-gene coverage, not of reads; the report
states this next to every plot.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
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
            {"taxonomy": row[2], "coverage": to_float(row[1], path, "coverage")}
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


def short_label(taxonomy: str) -> str:
    """`Root; d__Bacteria; p__Bacillota` -> `Bacillota` (falls back to the raw last field)."""
    last = taxonomy.split(";")[-1].strip()
    return last.split("__", 1)[1] if "__" in last and last.split("__", 1)[1] else last


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
            {"taxonomy": t["taxonomy"], "label": label, "values": {s: t["values"][s] for s in samples}}
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


def build(args: argparse.Namespace) -> dict:
    samples = sorted(args.samples)
    if not samples:
        raise InputError("no samples given")
    check_samples(list(args.samples), samples, "--samples")
    if args.top_n < 1:
        raise InputError("--top-n must be at least 1")
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "pipeline_version": args.pipeline_version,
            "metapackage": args.metapackage,
            "assignment_method": args.assignment_method,
            "top_n": args.top_n,
            "stacked_bar_max_samples": args.stacked_bar_max_samples,
        },
        "samples": read_fractions(args.fractions, samples),
        "ranks": read_ranks(args.by_rank, samples, args.top_n),
        "level_coverage": read_level_coverage(args.level_coverage, samples),
        "profiles": read_profiles(args.profiles, samples),
        "links": {"multiqc": args.multiqc_link, "krona": args.krona_link},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", nargs="+", required=True, help="sample ids from the samplesheet")
    parser.add_argument("--profiles", nargs="+", required=True, type=Path, help="per-sample SingleM profiles")
    parser.add_argument("--fractions", nargs="+", required=True, type=Path, help="prokaryotic_fraction TSVs")
    parser.add_argument("--by-rank", nargs="+", required=True, type=Path, help="singlem summarise by_rank-*.tsv")
    parser.add_argument("--level-coverage", required=True, type=Path, help="singlem summarise level coverage TSV")
    parser.add_argument("--pipeline-version", required=True)
    parser.add_argument("--metapackage", required=True, help="metapackage name shown in the report")
    parser.add_argument("--assignment-method", default=None, help="SingleM --assignment-method, if not the default")
    parser.add_argument("--top-n", type=int, default=15, help="taxa per rank with their own colour")
    parser.add_argument("--stacked-bar-max-samples", type=int, default=15)
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
