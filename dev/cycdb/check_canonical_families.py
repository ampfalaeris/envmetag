#!/usr/bin/env python3
"""Check properties of the checked-in canonical-family table (CI cannot rebuild it).

- every row has a valid cycle and role;
- cycle_detail is present exactly when cycle = shared;
- every canonical-level field has one value per canonical family;
- every KO on the exception list maps to more than one canonical family, all in one ambiguity group;
- group_cycle is the members' common counted cycle when every member is dissimilatory, else empty;
- every non-default value (renamed canonical family, role other than dissimilatory,
  cycle other than the source database's, any ambiguity group) has a reason;
- a family whose name marks another cycle's gene (e.g. an MCycDB `nar*`) has a cycle with a reason;
- a split source family has exactly one `ontology:` row and one `rest` row;
- every marker family (marker_step) has a counted cycle (sulfur, methane, nitrogen, c1);
- every row of every input file has the header's field count.

With --assignments: every sequence appears once and is assigned to one of its own
families, an existing group, or an `unresolved:` label naming exactly its families; a
single-family row must come from a split.

With --overrides: the number of role rows seeded from the old default (not individually
reviewed) is at most MAX_SEEDED_ROLES. Lower the constant whenever rows are reviewed;
it may only go down.

Standard library only.
Usage: check_canonical_families.py canonical_families.tsv [--assignments sequence_assignments.tsv]
           [--overrides curation_overrides.tsv]
"""
import argparse
import collections
import csv
import sys

CYCLE = {"SCycDB": "sulfur", "MCycDB": "methane", "NCyc": "nitrogen"}
CYCLES = {"sulfur", "methane", "nitrogen", "c1", "shared", "none"}
COUNTED_CYCLES = {"sulfur", "methane", "nitrogen", "c1"}
ROLES = {"dissimilatory", "assimilatory", "transport", "accessory", "core", "other"}
# KOs that span different functions: never merged, always one ambiguity group (DECISIONS.md, 2026-10-28)
EXCEPTION_KOS = {"K10944", "K10945", "K10946", "K00370", "K00371", "K07235", "K07236", "K07237"}
CANONICAL_FIELDS = ("ko", "ambiguity_group", "group_cycle", "marker_step", "header_evidence", "source_databases",
                    "cycle", "cycle_detail", "role")
# Gene-name prefixes that belong to one cycle; a family in another cycle's database needs a stated cycle
CYCLE_PREFIXES = {"nitrogen": ("nap", "nar", "nir", "nor", "nos", "nrf", "nas", "nif", "amo", "hao", "hzs", "nxr"),
                  "methane": ("com", "mcr", "mtr", "fwd", "fmd", "ftr", "mer"),
                  "sulfur": ("dsr", "apr", "sox", "sqr", "qmo")}
MAX_SEEDED_ROLES = 355  # 2026-10-28; may only go down


def read_tsv(path):
    """Rows as dicts; every row must have the header's field count (a stripped trailing tab drops a field)."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    if len(rows) < 2:
        sys.exit(f"{path}: no data rows")
    head = rows[0]
    bad = [i for i, r in enumerate(rows[1:], 2) if len(r) != len(head)]
    if bad:
        sys.exit(f"{path}: {len(bad)} rows do not have {len(head)} fields (first: line {bad[0]})")
    return [dict(zip(head, r)) for r in rows[1:]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("table")
    p.add_argument("--assignments")
    p.add_argument("--overrides")
    a = p.parse_args()
    rows = read_tsv(a.table)
    errors = []
    by_canon = collections.defaultdict(list)
    selectors = collections.defaultdict(list)
    for r in rows:
        name = f"{r['source_db']}:{r['source_family']}"
        by_canon[r["canonical_family"]].append(r)
        selectors[name].append(r["selector"])
        if r["cycle"] not in CYCLES:
            errors.append(f"{name}: invalid cycle {r['cycle']!r}")
        if r["role"] not in ROLES:
            errors.append(f"{name}: invalid role {r['role']!r}")
        if (r["cycle"] == "shared") != bool(r["cycle_detail"]):
            errors.append(f"{name}: cycle_detail must be given exactly when cycle = shared")
        if r["marker_step"] and r["cycle"] not in COUNTED_CYCLES:
            errors.append(f"{name}: marker family with cycle {r['cycle']!r}")
        default_cycle = "none" if r["role"] in ("core", "other") else CYCLE[r["source_db"]]
        renamed = r["canonical_family"] != r["source_family"]
        need = {"rest_canonical" if r["selector"] == "rest" else "canonical_family": renamed,
                "role": r["role"] != "dissimilatory",
                "cycle": r["cycle"] != default_cycle and len(r["source_databases"].split(",")) == 1,
                "ambiguity_group": bool(r["ambiguity_group"])}
        for cyc, prefixes in CYCLE_PREFIXES.items():
            if cyc != CYCLE[r["source_db"]] and r["source_family"].lower().startswith(prefixes):
                need["cycle"] = True
        for field, nondefault in need.items():
            if nondefault and f"{field}:" not in r["reason"]:
                errors.append(f"{name}: non-default {field} without a reason")
        if r["reason"] and not r["source"]:
            errors.append(f"{name}: reason without a source")
    for name, sels in selectors.items():
        if sels != [""] and sorted(s.split(":")[0] for s in sels) != ["ontology", "rest"]:
            errors.append(f"{name}: expected one whole-family row, or one ontology: row and one rest row; got {sels}")
    for c, rs in by_canon.items():
        for field in CANONICAL_FIELDS:
            if len({r[field] for r in rs}) > 1:
                errors.append(f"{c}: rows disagree on {field}")
    members = collections.defaultdict(list)
    for c, rs in by_canon.items():
        if rs[0]["ambiguity_group"]:
            members[rs[0]["ambiguity_group"]].append(rs[0])
    for g, ms in members.items():
        cycles = {m["cycle"] for m in ms}
        expect = next(iter(cycles)) if (len(cycles) == 1 and cycles <= COUNTED_CYCLES
                                         and all(m["role"] == "dissimilatory" for m in ms)) else ""
        if any(m["group_cycle"] != expect for m in ms):
            errors.append(f"group {g}: group_cycle should be {expect!r}")
    by_ko = collections.defaultdict(set)
    for r in rows:
        if r["ko"]:
            by_ko[r["ko"]].add((r["canonical_family"], r["ambiguity_group"]))
    for ko in sorted(EXCEPTION_KOS):
        fams = by_ko.get(ko, set())
        groups = {g for _, g in fams}
        if len(fams) < 2 or len(groups) != 1 or "" in groups:
            errors.append(f"exception KO {ko}: expected >1 canonical family in one ambiguity group, got {sorted(fams)}")

    n_assign = 0
    if a.assignments:
        seen = set()
        for s in read_tsv(a.assignments):
            n_assign += 1
            fams = s["canonical_families"].split(",")
            kind, _, value = s["assignment"].rpartition(":")
            if s["seq_md5"] in seen:
                errors.append(f"sequence {s['seq_md5']} assigned twice")
            seen.add(s["seq_md5"])
            if any(f not in by_canon for f in fams):
                errors.append(f"sequence {s['seq_md5']}: unknown family in {fams}")
            elif len(fams) < 2 and not (s["basis"].startswith("split") and s["assignment"] == fams[0]):
                errors.append(f"sequence {s['seq_md5']}: single family {fams} without a split basis")
            elif kind == "group" and value not in members:
                errors.append(f"sequence {s['seq_md5']}: unknown group {value}")
            elif kind == "unresolved" and value.split("|") != sorted(fams):
                errors.append(f"sequence {s['seq_md5']}: unresolved label does not match its families")
            elif not kind and value not in fams:
                errors.append(f"sequence {s['seq_md5']}: assigned to {value}, not one of its families")

    n_seeded = None
    if a.overrides:
        n_seeded = sum(1 for o in read_tsv(a.overrides) if o["source"].startswith("seeded"))
        if n_seeded > MAX_SEEDED_ROLES:
            errors.append(f"{n_seeded} seeded role rows; the count may only go down (max {MAX_SEEDED_ROLES})")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"ok: {len(rows)} rows, {len(by_canon)} canonical families"
          + (f", {n_assign} sequence assignments" if a.assignments else "")
          + (f", {n_seeded} seeded role rows" if n_seeded is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
