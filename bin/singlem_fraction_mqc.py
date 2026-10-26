#!/usr/bin/env python3
"""Turn `singlem prokaryotic_fraction` TSVs into one MultiQC General Statistics file.

Each input has a header row and exactly one result row. The output is a MultiQC
custom-content TSV (`*_mqc.tsv`) with `plot_type: generalstats`. Column descriptions
state what the numbers are: estimates from raw reads, based on genome sizes, not
counts of classified reads.
"""

import argparse
import csv
import sys
from pathlib import Path

HEADER = """\
# id: 'singlem_prokaryotic_fraction'
# section_name: 'SingleM prokaryotic fraction'
# plot_type: 'generalstats'
# pconfig:
#     - read_fraction:
#         title: 'Prokaryotic %'
#         description: 'SingleM estimate of the percentage of raw-read bases from Bacteria and Archaea (genome-size based, capped at 100). Not a count of classified reads.'
#         max: 100
#         min: 0
#         suffix: '%'
#         format: '{:,.1f}'
#     - average_bacterial_archaeal_genome_size:
#         title: 'Avg genome (Mbp)'
#         description: 'SingleM estimate of the average bacterial/archaeal genome size in the sample'
#         format: '{:,.2f}'
#     - warning:
#         title: 'SingleM warning'
#         description: 'Warning emitted by singlem prokaryotic_fraction; when present, treat the estimate with caution'
"""

REQUIRED = ("sample", "read_fraction", "average_bacterial_archaeal_genome_size", "warning")


def read_fraction(path: Path) -> dict:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        sys.exit(f"ERROR: {path} has {len(rows)} result rows; expected exactly 1")
    missing = [column for column in REQUIRED if column not in rows[0]]
    if missing:
        sys.exit(f"ERROR: {path} is missing column(s): {', '.join(missing)}")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fractions", nargs="+", type=Path, help="prokaryotic_fraction TSVs")
    parser.add_argument("--output", required=True, type=Path, help="output *_mqc.tsv")
    args = parser.parse_args()

    rows = sorted((read_fraction(path) for path in args.fractions), key=lambda row: row["sample"])
    samples = [row["sample"] for row in rows]
    duplicates = sorted({sample for sample in samples if samples.count(sample) > 1})
    if duplicates:
        sys.exit(f"ERROR: duplicate sample(s) across inputs: {', '.join(duplicates)}")

    with args.output.open("w", newline="") as handle:
        handle.write(HEADER)
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["Sample", "read_fraction", "average_bacterial_archaeal_genome_size", "warning"])
        for row in rows:
            genome_mbp = float(row["average_bacterial_archaeal_genome_size"]) / 1e6
            writer.writerow([row["sample"], row["read_fraction"], f"{genome_mbp:.2f}", row["warning"]])


if __name__ == "__main__":
    main()
