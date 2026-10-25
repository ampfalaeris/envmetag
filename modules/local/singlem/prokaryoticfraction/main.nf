nextflow.enable.types = true

include { SampleProfile } from '../../../../types'

process SINGLEM_PROKARYOTICFRACTION {
    tag "${s.id}"
    label 'process_low'

    container 'quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2'

    input:
    s: SampleProfile
    metapackage: Path

    stage:
    // Same staging as SINGLEM_PIPE so the profile's `sample` column matches these reads
    stageAs s.r1, "${s.id}.fastq.gz"
    stageAs s.r2, "${s.id}_R2.fastq.gz"

    output:
    record(
        id: s.id,
        fraction: file("${s.id}.singlem_prokaryotic_fraction.tsv")
    )

    topic:
    tuple(task.process, 'singlem', eval('singlem --version')) >> 'versions'

    script:
    def args = task.ext.args ?: ''
    """
    singlem prokaryotic_fraction \\
        -p ${s.profile} \\
        -1 ${s.id}.fastq.gz \\
        -2 ${s.id}_R2.fastq.gz \\
        --metapackage ${metapackage} \\
        --output-tsv ${s.id}.singlem_prokaryotic_fraction.tsv \\
        ${args}

    if [ "\$(wc -l < ${s.id}.singlem_prokaryotic_fraction.tsv)" -ne 2 ]; then
        echo "ERROR: expected one result row for sample '${s.id}' from singlem prokaryotic_fraction" >&2
        exit 1
    fi
    """

    stub:
    """
    printf 'sample\\tbacterial_archaeal_bases\\tmetagenome_size\\tread_fraction\\taverage_bacterial_archaeal_genome_size\\twarning\\tdomain_relative_abundance\\tphylum_relative_abundance\\tclass_relative_abundance\\torder_relative_abundance\\tfamily_relative_abundance\\tgenus_relative_abundance\\tspecies_relative_abundance\\n' > ${s.id}.singlem_prokaryotic_fraction.tsv
    printf '${s.id}\\t0\\t1\\t0.00\\t0\\t\\t0.00\\t0.00\\t0.00\\t0.00\\t0.00\\t0.00\\t0.00\\n' >> ${s.id}.singlem_prokaryotic_fraction.tsv
    """
}
