nextflow.enable.types = true

include { Sample } from '../../../../types'

process SINGLEM_PIPE {
    tag "${s.id}"
    label 'process_medium'

    container 'quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2'

    input:
    s: Sample
    metapackage: Path

    stage:
    // SingleM takes the `sample` column from the R1 basename, so R1 is staged as `<id>.fastq.gz`
    stageAs s.r1, "${s.id}.fastq.gz"
    stageAs s.r2, "${s.id}_R2.fastq.gz"

    output:
    record(
        id: s.id,
        profile: file("${s.id}.singlem_profile.tsv"),
        archive_otu_table: file("${s.id}.singlem_archive_otu_table.json")
    )

    topic:
    tuple(task.process, 'singlem', eval('singlem --version')) >> 'versions'

    script:
    def args = task.ext.args ?: ''
    """
    singlem pipe \\
        -1 ${s.id}.fastq.gz \\
        -2 ${s.id}_R2.fastq.gz \\
        --metapackage ${metapackage} \\
        --threads ${task.cpus} \\
        -p ${s.id}.singlem_profile.tsv \\
        --archive-otu-table ${s.id}.singlem_archive_otu_table.json \\
        ${args}

    if [ "\$(wc -l < ${s.id}.singlem_profile.tsv)" -lt 2 ]; then
        echo "ERROR: SingleM found no marker genes for sample '${s.id}'; the profile is empty" >&2
        exit 1
    fi
    """

    stub:
    """
    printf 'sample\\tcoverage\\ttaxonomy\\n${s.id}\\t1.0\\tRoot; d__Bacteria\\n' > ${s.id}.singlem_profile.tsv
    cat > ${s.id}.singlem_archive_otu_table.json <<'END_ARCHIVE'
    {"version": 4, "alignment_hmm_sha256s": [], "singlem_package_sha256s": [], "fields": ["gene", "sample", "sequence", "num_hits", "coverage", "taxonomy", "read_names", "nucleotides_aligned", "taxonomy_by_known?", "read_unaligned_sequences", "equal_best_hit_taxonomies", "taxonomy_assignment_method"], "otus": []}
    END_ARCHIVE
    """
}
