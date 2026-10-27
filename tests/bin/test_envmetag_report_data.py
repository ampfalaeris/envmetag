"""Unit tests for bin/envmetag_report_data.py.

Run from the repository root:  uv run --no-project --with pytest pytest tests/bin

`fixtures/ci_two_samples/` is real SingleM 0.21.4 output from `-profile test` (tiny reads,
3-marker CI metapackage, diamond assignment): genus is the deepest rank, there is no
species file, `unassigned` is 0 everywhere, and level_coverage uses level numbers.
The synthetic cases below cover what that run cannot: non-zero `unassigned`, a species
file, named levels, pooling into "Other", and malformed input.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CI = FIXTURES / "ci_two_samples"

spec = importlib.util.spec_from_file_location("envmetag_report_data", REPO / "bin" / "envmetag_report_data.py")
report_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_data)

SAMPLES = ["mic_coupon", "apb_enrichment"]  # deliberately unsorted


def ci_argv(samples=SAMPLES, output="unused.json", **files):
    """Command line for the CI fixture; keyword arguments replace one input's file list."""
    inputs = {
        "profiles": sorted(CI.glob("*.singlem_profile.tsv")),
        "fractions": sorted(CI.glob("*.singlem_prokaryotic_fraction.tsv")),
        "by_rank": sorted(CI.glob("singlem.by_rank-*.tsv")),
    } | files
    return [
        "--samples", *samples,
        "--profiles", *map(str, inputs["profiles"]),
        "--fractions", *map(str, inputs["fractions"]),
        "--by-rank", *map(str, inputs["by_rank"]),
        "--level-coverage", str(CI / "singlem.level_coverage.tsv"),
        "--pipeline-version", "0.1.0dev",
        "--metapackage", "GlobDB_r232_ci3.smpkg",
        "--assignment-method", "diamond",
        "--multiqc-link", "../multiqc/multiqc_report.html",
        "--krona-link", "../singlem/summary/singlem.krona.html",
        "--output", str(output),
    ]


def ci_args(**kwargs):
    return report_data.parse_args(ci_argv(**kwargs))


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def tsv(*rows) -> str:
    return "".join("\t".join(map(str, row)) + "\n" for row in rows)


# --- real SingleM output (CI metapackage) -------------------------------------------------


def test_ci_fixture_builds():
    data = report_data.build(ci_args())

    assert data["schema_version"] == 1
    assert [s["id"] for s in data["samples"]] == ["apb_enrichment", "mic_coupon"]
    assert data["run"]["metapackage"] == "GlobDB_r232_ci3.smpkg"

    mic = data["samples"][1]
    assert mic["read_fraction"] == 58.11
    assert mic["average_genome_size_bp"] == 2185522
    assert mic["warning"].startswith("WARNING: The most abundant taxons")


def test_ci_fixture_ranks():
    ranks = report_data.build(ci_args())["ranks"]

    # SingleM writes no species file when nothing is assigned at species level
    assert ranks["species"] == {"available": False}
    assert all(ranks[r]["available"] for r in ("domain", "phylum", "class", "order", "family", "genus"))

    genus = ranks["genus"]
    assert [t["label"] for t in genus["taxa"]] == ["Sporolactobacillus", "Methanococcus", "Oleidesulfovibrio", "JACCQO01"]
    assert genus["taxa"][1]["values"] == {"apb_enrichment": 0.0, "mic_coupon": 78.54}
    assert genus["unassigned"] == {"apb_enrichment": 0.0, "mic_coupon": 0.0}
    assert genus["other"] is None and genus["other_count"] == 0

    domain = {t["label"]: t["values"] for t in ranks["domain"]["taxa"]}
    assert domain["Archaea"] == {"apb_enrichment": 0.0, "mic_coupon": 78.54}


def test_ci_fixture_genus_sums_to_99_99_within_tolerance():
    # mic_coupon's genus column sums to 99.99 in real output (2-decimal rounding)
    genus = report_data.build(ci_args())["ranks"]["genus"]
    total = genus["unassigned"]["mic_coupon"] + sum(t["values"]["mic_coupon"] for t in genus["taxa"])
    assert total == pytest.approx(99.99)


def test_ci_fixture_level_numbers_map_to_ranks():
    levels = report_data.build(ci_args())["level_coverage"]
    assert levels["mic_coupon"]["genus"] == {"coverage": 7.69, "relative_abundance": 100.0}
    assert levels["mic_coupon"]["domain"]["coverage"] == 0.0
    # level 7 (species) is absent from the file and filled with zero
    assert levels["apb_enrichment"]["species"] == {"coverage": 0.0, "relative_abundance": 0.0}


def test_ci_fixture_profiles_sorted_by_coverage():
    profiles = report_data.build(ci_args())["profiles"]
    assert [t["coverage"] for t in profiles["mic_coupon"]] == [6.04, 1.1, 0.55]


def test_output_is_deterministic(tmp_path):
    # input order must not matter: the second run gets every file list reversed
    report_data.main(ci_argv(output=tmp_path / "a.json"))
    report_data.main(ci_argv(
        samples=SAMPLES[::-1],
        output=tmp_path / "b.json",
        profiles=sorted(CI.glob("*.singlem_profile.tsv"))[::-1],
        fractions=sorted(CI.glob("*.singlem_prokaryotic_fraction.tsv"))[::-1],
        by_rank=sorted(CI.glob("singlem.by_rank-*.tsv"))[::-1],
    ))
    a, b = (tmp_path / "a.json").read_bytes(), (tmp_path / "b.json").read_bytes()
    assert a == b
    assert json.loads(a)["samples"][0]["id"] == "apb_enrichment"


# --- synthetic cases ----------------------------------------------------------------------


def test_unassigned_species_and_named_levels(tmp_path):
    species = write(
        tmp_path / "singlem.by_rank-species.tsv",
        tsv(
            ["taxonomy", "s1"],
            ["unassigned", 40.0],
            ["Root; d__Bacteria; p__P; c__C; o__O; f__F; g__G; s__G alpha", 60.0],
        ),
    )
    levels = write(
        tmp_path / "level_coverage.tsv",
        tsv(
            ["sample", "level", "coverage", "relative abundance (%)"],
            ["s1", "root", 0.0, 0.0],
            ["s1", "genus", 2.0, 40.0],
            ["s1", "species", 3.0, 60.0],
        ),
    )
    ranks = report_data.read_ranks([species], ["s1"], top_n=15)
    assert ranks["species"]["unassigned"] == {"s1": 40.0}
    assert ranks["species"]["taxa"][0]["label"] == "G alpha"
    assert ranks["genus"] == {"available": False}

    coverage = report_data.read_level_coverage(levels, ["s1"])
    assert coverage["s1"]["species"]["relative_abundance"] == 60.0
    assert coverage["s1"]["domain"]["relative_abundance"] == 0.0


def test_top_n_ranks_by_max_and_pools_the_rest(tmp_path):
    # `Even` has the highest mean (20) but `Spike` dominates one sample (70): Spike is kept
    table = write(
        tmp_path / "singlem.by_rank-genus.tsv",
        tsv(
            ["taxonomy", "a", "b"],
            ["unassigned", 10.0, 10.0],
            ["Root; d__B; g__Even", 20.0, 20.0],
            ["Root; d__B; g__Spike", 0.0, 70.0],
            ["Root; d__B; g__Big", 50.0, 0.0],
            ["Root; d__B; g__Small", 20.0, 0.0],
        ),
    )
    genus = report_data.read_by_rank(table, ["a", "b"], top_n=2)
    assert [t["label"] for t in genus["taxa"]] == ["Spike", "Big"]
    assert genus["other"] == {"a": 40.0, "b": 20.0}
    assert genus["other_count"] == 2


def test_duplicate_short_names_get_parent(tmp_path):
    table = write(
        tmp_path / "singlem.by_rank-genus.tsv",
        tsv(
            ["taxonomy", "a"],
            ["unassigned", 0.0],
            ["Root; d__B; f__One; g__Same", 60.0],
            ["Root; d__B; f__Two; g__Same", 40.0],
        ),
    )
    labels = [t["label"] for t in report_data.read_by_rank(table, ["a"], top_n=15)["taxa"]]
    assert labels == ["Same (One)", "Same (Two)"]


# --- failures -----------------------------------------------------------------------------


@pytest.mark.parametrize("value, ok", [(99.6, True), (99.4, False), (100.4, True), (100.6, False)])
def test_sum_tolerance(tmp_path, value, ok):
    table = write(
        tmp_path / "singlem.by_rank-genus.tsv",
        tsv(["taxonomy", "a"], ["unassigned", 0.0], ["Root; d__B; g__X", value]),
    )
    if ok:
        report_data.read_by_rank(table, ["a"], top_n=15)
    else:
        with pytest.raises(report_data.InputError, match="sum to"):
            report_data.read_by_rank(table, ["a"], top_n=15)


def test_missing_sample_in_fractions():
    args = ci_args(fractions=[CI / "mic_coupon.singlem_prokaryotic_fraction.tsv"])
    with pytest.raises(report_data.InputError, match="missing: apb_enrichment"):
        report_data.build(args)


def test_sample_not_in_samplesheet():
    # the by_rank tables still have an apb_enrichment column
    args = ci_args(
        samples=["mic_coupon"],
        profiles=[CI / "mic_coupon.singlem_profile.tsv"],
        fractions=[CI / "mic_coupon.singlem_prokaryotic_fraction.tsv"],
    )
    with pytest.raises(report_data.InputError, match="unexpected: apb_enrichment"):
        report_data.build(args)


def test_empty_profile_fails(tmp_path):
    empty = write(tmp_path / "a.singlem_profile.tsv", tsv(["sample", "coverage", "taxonomy"]))
    with pytest.raises(report_data.InputError, match="no taxa"):
        report_data.read_profiles([empty], ["a"])


def test_profile_wrong_header_fails(tmp_path):
    bad = write(tmp_path / "a.singlem_profile.tsv", tsv(["sample", "cov", "taxonomy"], ["a", 1.0, "Root"]))
    with pytest.raises(report_data.InputError, match="expected header"):
        report_data.read_profiles([bad], ["a"])


def test_missing_unassigned_row_fails(tmp_path):
    table = write(tmp_path / "singlem.by_rank-genus.tsv", tsv(["taxonomy", "a"], ["Root; d__B; g__X", 100.0]))
    with pytest.raises(report_data.InputError, match="no 'unassigned' row"):
        report_data.read_by_rank(table, ["a"], top_n=15)


def test_unknown_level_fails(tmp_path):
    levels = write(
        tmp_path / "level_coverage.tsv",
        tsv(["sample", "level", "coverage", "relative abundance (%)"], ["a", "8", 1.0, 100.0]),
    )
    with pytest.raises(report_data.InputError, match="unknown level"):
        report_data.read_level_coverage(levels, ["a"])


def test_bad_by_rank_filename_fails(tmp_path):
    table = write(tmp_path / "singlem.by_rank-strain.tsv", tsv(["taxonomy", "a"], ["unassigned", 100.0]))
    with pytest.raises(report_data.InputError, match="not a SingleM by_rank"):
        report_data.read_ranks([table], ["a"], top_n=15)


def test_duplicate_rank_files_fail(tmp_path):
    (tmp_path / "x").mkdir()
    one = write(tmp_path / "singlem.by_rank-genus.tsv", tsv(["taxonomy", "a"], ["unassigned", 100.0]))
    two = write(tmp_path / "x" / "singlem.by_rank-genus.tsv", tsv(["taxonomy", "a"], ["unassigned", 100.0]))
    with pytest.raises(report_data.InputError, match="two by_rank files"):
        report_data.read_ranks([one, two], ["a"], top_n=15)


def test_cli_reports_error_and_exits(tmp_path, capsys):
    argv = ci_argv(output=tmp_path / "out.json", fractions=[CI / "mic_coupon.singlem_prokaryotic_fraction.tsv"])
    with pytest.raises(SystemExit) as exit_info:
        report_data.main(argv)
    assert "ERROR: prokaryotic fractions: samples do not match" in str(exit_info.value)
    assert not (tmp_path / "out.json").exists()
