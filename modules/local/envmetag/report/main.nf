nextflow.enable.types = true

process ENVMETAG_REPORT {
    label 'process_single'

    // Seqera Containers build bd-3bfdf2df398a5458_1: python=3.13.16 quarto=1.9.38 plotly=7.1.0 ipykernel=7.4.0
    // nbclient=0.11.0 pyyaml=6.0.3, all conda-forge (DECISIONS.md)
    container 'community.wave.seqera.io/library/python_quarto_plotly_ipykernel_pruned:3bfdf2df398a5458'

    input:
    sample_ids: Bag<String>    // samplesheet ids; every input table must have exactly these samples
    profiles: Bag<Path>        // per-sample SingleM profiles
    fractions: Bag<Path>       // per-sample `singlem prokaryotic_fraction` TSVs
    by_rank: Bag<Path>         // `singlem summarise` by_rank-<rank>.tsv (one per rank with assignments)
    level_coverage: Path       // `singlem summarise` taxonomic level coverage
    extras: Path               // `singlem summarise` profile with extras (per-taxon full coverage)
    metapackage_name: String   // shown in the report header and methods
    template_dir: Path         // assets/report: envmetag_report.qmd and its light/dark theme files

    output:
    record(
        report: file('envmetag_report.html'),
        data: file('report_data.json')
    )

    topic:
    tuple(task.process, 'quarto', eval('. /opt/conda/etc/conda/activate.d/quarto.sh 2>/dev/null; quarto --version')) >> 'versions'
    tuple(task.process, 'plotly', eval("python -c 'import plotly; print(plotly.__version__)'")) >> 'versions'

    script:
    def args = task.ext.args ?: ''
    def ids = sample_ids.toSorted().join(' ')
    """
    envmetag_report_data.py \\
        --samples ${ids} \\
        --profiles ${profiles.toSorted { f -> f.name }.join(' ')} \\
        --fractions ${fractions.toSorted { f -> f.name }.join(' ')} \\
        --by-rank ${by_rank.toSorted { f -> f.name }.join(' ')} \\
        --level-coverage ${level_coverage} \\
        --extras ${extras} \\
        --pipeline-version '${workflow.manifest.version}' \\
        --metapackage '${metapackage_name}' \\
        ${args} \\
        --output report_data.json

    # Quarto writes caches under \$HOME, which is read-only in many containers
    export HOME="\$PWD/.home" XDG_CACHE_HOME="\$PWD/.xdg_cache" XDG_DATA_HOME="\$PWD/.xdg_data"
    # The image does not run conda activation scripts; Quarto needs the paths they set. The deno_dom
    # path in quarto.sh points into conda's build environment, so take it from deno_dom.sh instead.
    set +u
    for script in /opt/conda/etc/conda/activate.d/quarto.sh /opt/conda/etc/conda/activate.d/deno_dom.sh; do
        if [ -f "\$script" ]; then . "\$script"; fi
    done
    if [ -n "\${DENO_DOM_PLUGIN:-}" ]; then export QUARTO_DENO_DOM="\$DENO_DOM_PLUGIN"; fi
    set -u

    # Render copies: Quarto resolves staged symlinks and could write next to the originals.
    # Without a _quarto.yml here, Quarto searches parent directories for a project.
    mkdir render
    cp -L ${template_dir}/* render/
    cp report_data.json render/
    printf 'project:\\n  type: default\\n' > render/_quarto.yml
    (cd render && quarto render envmetag_report.qmd --output envmetag_report.html)
    mv render/envmetag_report.html .

    # The report must open offline: fail if it loads any script or stylesheet from the network
    if grep -q -E '<(script|link)[^>]+(src|href)="https?://|@import url\\(["'"'"']?https?://' envmetag_report.html; then
        echo "ERROR: envmetag_report.html loads remote resources; it must be self-contained" >&2
        exit 1
    fi
    """

    stub:
    def ids = sample_ids.toSorted().collect { id -> "{\"id\": \"${id}\"}" }.join(', ')
    """
    printf '{"schema_version": 1, "samples": [${ids}]}\\n' > report_data.json
    printf '<!DOCTYPE html>\\n<html><head><title>envmetag report</title></head><body></body></html>\\n' > envmetag_report.html
    """
}
