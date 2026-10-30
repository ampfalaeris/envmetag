#!/usr/bin/env python3
"""Build assets/cycdb/canonical_families.tsv from the audit tables and curation_overrides.tsv.

Defaults: a family keeps its own name as canonical family (same-name families in
different databases merge); the KO comes from the family name suffix or from at
least 5 target headers agreeing at >= 80%; cycle is the source database's cycle,
or `none` for role `core` or `other`. Role has no default: every canonical family
needs a `role` override, so a new family in a database update fails the build instead
of entering the headline. Every other value comes from curation_overrides.tsv
(scope row | split | canonical | link), each with a reason and source; only
`role = dissimilatory` may omit them.

A `split` override divides one source family by the ontology groups on each
sequence's own target headers: sequences carrying a group in `keep_ontologies` keep
the row's canonical family, all others go to `rest_canonical`. The table then has two
rows for that source family, told apart by `selector` (`ontology:<groups>` or `rest`);
assign_shared_sequences.py lists the moved sequences. The rest family's KO comes only
from an override.

`marker_step` names the cycle step for which a family is the reported marker (one
marker per step, in copies per genome equivalent); other families are shown in the
cycle's detail block. `group_cycle` is where a marker read left unresolved within its
ambiguity group is shown: the members' common cycle when every member has that cycle
(sulfur, methane, nitrogen or c1) and role `dissimilatory`, otherwise nowhere but the
unresolved/ambiguous line. Families are never summed into a cycle total.

`header_evidence = insufficient` marks a family whose header ontology groups do not
identify its sequences (multi-domain Fe-S proteins whose COG tags come from shared
domains); assign_shared_sequences.py then ignores header groups for any sequence
carrying that family.

`fusion = declared` marks a family that is itself a fusion of two domains (e.g. cysN_cysC);
place_unresolved.py then keeps its references even when they carry another family's
signature and are long for their family (the fusion-reference rule).

Fails, rather than writing a table, when:
- an override names a family or canonical family that does not exist, or is unused;
- a canonical family has no role;
- a canonical family drawn from databases of different cycles has no cycle override;
- `cycle_detail` is missing for `cycle = shared`, or given for another cycle;
- two canonical families share at least MIN_STRONG_SHARED sequences (and that is at
  least MIN_STRONG_FRACTION of the smaller) but are neither in one ambiguity group
  nor listed as a link resolved at sequence level;
- two canonical families share a KO but are not in one ambiguity group.

Standard library only.

Usage: build_canonical_families.py families.tsv family_pairs.tsv curation_overrides.tsv out.tsv
"""
import collections
import csv
import sys

CYCLE = {"SCycDB": "sulfur", "MCycDB": "methane", "NCyc": "nitrogen"}
CYCLES = {"sulfur", "methane", "nitrogen", "c1", "shared", "none"}
COUNTED_CYCLES = {"sulfur", "methane", "nitrogen", "c1"}
ROLES = {"dissimilatory", "assimilatory", "transport", "accessory", "core", "other"}
FIELDS = {"row": {"canonical_family"},
          "split": {"keep_ontologies", "rest_canonical"},
          "canonical": {"ko", "ambiguity_group", "cycle", "cycle_detail", "role", "marker_step", "header_evidence",
                        "fusion"},
          "link": {"resolution"}}
MIN_KO_HEADERS = 5
MIN_STRONG_SHARED, MIN_STRONG_FRACTION = 10, 0.01
COLUMNS = ["source_db", "source_family", "selector", "canonical_family", "ko", "ambiguity_group", "group_cycle",
           "marker_step", "header_evidence", "fusion", "source_databases", "cycle", "cycle_detail", "role", "n_sequences",
           "cog", "reason", "source"]


def read_tsv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main():
    fam_tsv, pairs_tsv, over_tsv, out_tsv = sys.argv[1:5]
    fams = {(r["source_db"], r["source_family"]): r for r in read_tsv(fam_tsv)}
    errors = []

    over = collections.defaultdict(dict)  # (scope, key) -> field -> (value, reason, source)
    for r in read_tsv(over_tsv):
        if r["field"] not in FIELDS.get(r["scope"], ()):
            errors.append(f"override: field {r['field']!r} not allowed for scope {r['scope']!r}")
        plain = r["field"] == "role" and r["value"] == "dissimilatory"
        if not plain and (not r["reason"] or not r["source"]):
            errors.append(f"override without reason or source: {r['scope']} {r['key']} {r['field']}")
        key = r["key"]
        if r["scope"] == "link":
            key = "|".join(sorted(key.split("|")))
        if r["field"] in over[(r["scope"], key)]:
            errors.append(f"duplicate override: {r['scope']} {key} {r['field']}")
        over[(r["scope"], key)][r["field"]] = (r["value"], r["reason"], r["source"])
    used = set()

    def get(scope, key, field, default=None):
        o = over.get((scope, key), {}).get(field)
        if o is None:
            return default
        used.add((scope, key, field))
        return o[0]

    canon = {k: get("row", f"{k[0]}:{k[1]}", "canonical_family", k[1]) for k in fams}
    by_canon = collections.defaultdict(list)
    for k, c in canon.items():
        by_canon[c].append(k)
    split = {}  # source family -> (keep ontologies, rest canonical)
    for scope, key in list(over):
        if scope != "split":
            continue
        k = tuple(key.split(":", 1))
        keep, rest = get("split", key, "keep_ontologies"), get("split", key, "rest_canonical")
        if k not in fams or not keep or not rest:
            errors.append(f"split {key}: needs a known family, keep_ontologies and rest_canonical")
            continue
        split[k] = (keep, rest)
        by_canon[rest].append(k)
    split_rest = {(rest, k) for k, (_, rest) in split.items()}

    def ko_of(k):
        r = fams[k]
        if r["ko"] and (k[1].endswith(f"-{r['ko']}") or k[1].endswith(f"_{r['ko']}")):
            return r["ko"]
        if r["ko"] and int(r["ko_headers"]) >= MIN_KO_HEADERS and float(r["ko_share"]) >= 0.8:
            return r["ko"]
        return ""

    out = {}
    for c, keys in by_canon.items():
        kos = sorted({ko_of(k) for k in keys if (c, k) not in split_rest} - {""})
        if len(kos) > 1 and "ko" not in over.get(("canonical", c), {}):
            errors.append(f"{c}: merged rows disagree on KO {kos}")
        ko = get("canonical", c, "ko", kos[0] if len(kos) == 1 else "")
        role = get("canonical", c, "role", "")
        if not role:
            errors.append(f"{c}: no role override")
        db_cycles = {CYCLE[d] for d, _ in keys}
        default_cycle = "none" if role in ("core", "other") else (db_cycles.pop() if len(db_cycles) == 1 else None)
        cycle = get("canonical", c, "cycle", default_cycle)
        detail = get("canonical", c, "cycle_detail", "")
        if cycle is None:
            errors.append(f"{c}: sources span cycles {sorted({CYCLE[d] for d, _ in keys})}; needs a cycle override")
        elif cycle not in CYCLES:
            errors.append(f"{c}: unknown cycle {cycle!r}")
        if role and role not in ROLES:
            errors.append(f"{c}: unknown role {role!r}")
        if (cycle == "shared") != bool(detail):
            errors.append(f"{c}: cycle_detail must be given exactly when cycle = shared")
        if get("canonical", c, "fusion", "") not in ("", "declared"):
            errors.append(f"{c}: fusion must be empty or 'declared'")
        out[c] = {"ko": ko, "ambiguity_group": get("canonical", c, "ambiguity_group", ""),
                  "marker_step": get("canonical", c, "marker_step", ""),
                  "header_evidence": get("canonical", c, "header_evidence", ""),
                  "fusion": get("canonical", c, "fusion", ""),
                  "source_databases": ",".join(sorted({d for d, _ in keys})),
                  "cycle": cycle or "", "cycle_detail": detail, "role": role}

    for (scope, key), fields in over.items():
        if scope == "row" and tuple(key.split(":", 1)) not in fams:
            errors.append(f"override for unknown family {key}")
        if scope == "canonical" and key not in by_canon:
            errors.append(f"override for unknown canonical family {key}")
        if scope == "link":
            for c in key.split("|"):
                if c not in by_canon:
                    errors.append(f"link override names unknown canonical family {c}")

    group = {c: v["ambiguity_group"] for c, v in out.items()}
    unexplained = collections.Counter()
    for r in read_tsv(pairs_tsv):
        a, b = (r["db_a"], r["family_a"]), (r["db_b"], r["family_b"])
        n = int(r["shared"])
        smaller = min(int(r["size_a"]), int(r["size_b"])) or 1
        if n < MIN_STRONG_SHARED or n / smaller < MIN_STRONG_FRACTION:
            continue
        ca, cb = canon[a], canon[b]
        if ca == cb or (group[ca] and group[ca] == group[cb]):
            continue
        link = "|".join(sorted((ca, cb)))
        if get("link", link, "resolution"):
            continue
        unexplained[link] += n
    for link, n in sorted(unexplained.items()):
        errors.append(f"strong link {link} ({n} shared sequences) is in no group and has no link resolution")

    by_ko = collections.defaultdict(set)
    for c, v in out.items():
        if v["ko"]:
            by_ko[v["ko"]].add(c)
    for ko, cs in sorted(by_ko.items()):
        if len(cs) > 1 and (len({group[c] for c in cs}) > 1 or not group[next(iter(cs))]):
            errors.append(f"KO {ko} is shared by {sorted(cs)} but they are not in one ambiguity group")

    for scope, key in over:
        for field in over[(scope, key)]:
            if (scope, key, field) not in used:
                errors.append(f"unused override: {scope} {key} {field}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} error(s); no table written", file=sys.stderr)
        return 1

    groups = collections.defaultdict(list)
    for c, g in group.items():
        if g:
            groups[g].append(c)
    group_cycle = {}
    for g, cs in groups.items():
        cycles_g = {out[c]["cycle"] for c in cs}
        same = len(cycles_g) == 1 and cycles_g <= COUNTED_CYCLES and all(out[c]["role"] == "dissimilatory" for c in cs)
        group_cycle[g] = cycles_g.pop() if same else ""

    with open(out_tsv, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(COLUMNS)
        for k in sorted(fams):
            name = f"{k[0]}:{k[1]}"
            parts = [("", canon[k])]
            if k in split:
                parts = [(f"ontology:{split[k][0]}", canon[k]), ("rest", split[k][1])]
            for selector, c in parts:
                notes = [(f, o) for f, o in (over.get(("row", name), {}) | over.get(("split", name), {})
                                             | over.get(("canonical", c), {})).items() if o[1]]
                reason = "; ".join(f"{f}: {o[1]}" for f, o in notes)
                source = "; ".join(dict.fromkeys(o[2] for _, o in notes))
                v = out[c]
                w.writerow([k[0], k[1], selector, c, v["ko"], v["ambiguity_group"],
                            group_cycle.get(v["ambiguity_group"], ""), v["marker_step"], v["header_evidence"], v["fusion"],
                            v["source_databases"],
                            v["cycle"], v["cycle_detail"], v["role"], fams[k]["n_sequences"], fams[k]["cog"],
                            reason, source])

    roles = collections.Counter(v["role"] for v in out.values())
    cycles = collections.Counter(v["cycle"] for v in out.values())
    print(f"rows {len(fams)}; canonical families {len(out)}; merged {sum(len(k) > 1 for k in by_canon.values())}; "
          f"with KO {sum(1 for v in out.values() if v['ko'])}; ambiguity groups {len(groups)}")
    print("role: " + ", ".join(f"{k} {v}" for k, v in roles.most_common()))
    print("cycle: " + ", ".join(f"{k} {v}" for k, v in cycles.most_common()))
    for g in sorted(groups):
        print(f"  {g} [{group_cycle[g] or 'unresolved line only'}]: {' '.join(sorted(groups[g]))}")
    steps = collections.defaultdict(list)
    for c, v in out.items():
        if v["marker_step"]:
            steps[(v["cycle"], v["marker_step"])].append(c)
    for (cyc, step), cs in sorted(steps.items()):
        print(f"  marker {cyc} / {step}: {' '.join(sorted(cs))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
