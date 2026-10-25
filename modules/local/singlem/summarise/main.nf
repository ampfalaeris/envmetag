nextflow.enable.types = true

process SINGLEM_SUMMARISE {
    label 'process_single'

    container 'quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2'

    input:
    profiles: List<Path>

    output:
    record(
        combined: file('singlem.profiles.tsv'),
        extras: file('singlem.profile_extras.tsv'),
        level_coverage: file('singlem.level_coverage.tsv'),
        by_rank: files('singlem.by_rank-*.tsv'),
        krona: file('singlem.krona.html')
    )

    topic:
    tuple(task.process, 'singlem', eval('singlem --version')) >> 'versions'

    script:
    def args = task.ext.args ?: ''
    def inputs = profiles.toSorted { p -> p.name }.join(' ')
    // `singlem summarise` accepts exactly one output type per call
    """
    singlem summarise --input-taxonomic-profiles ${inputs} --output-taxonomic-profile singlem.profiles.tsv ${args}
    singlem summarise --input-taxonomic-profiles ${inputs} --output-taxonomic-profile-with-extras singlem.profile_extras.tsv ${args}
    singlem summarise --input-taxonomic-profiles ${inputs} --output-taxonomic-level-coverage singlem.level_coverage.tsv ${args}
    singlem summarise --input-taxonomic-profiles ${inputs} --output-species-by-site-relative-abundance-prefix singlem.by_rank ${args}
    singlem summarise --input-taxonomic-profiles ${inputs} --output-taxonomic-profile-krona singlem.krona.html ${args}
    """

    stub:
    """
    printf 'sample\\tcoverage\\ttaxonomy\\nstub\\t1.0\\tRoot; d__Bacteria\\n' > singlem.profiles.tsv
    printf 'sample\\tcoverage\\tfull_coverage\\trelative_abundance\\tlevel\\ttaxonomy\\nstub\\t1.0\\t1.0\\t100.0\\tdomain\\tRoot; d__Bacteria\\n' > singlem.profile_extras.tsv
    printf 'sample\\tlevel\\tcoverage\\trelative abundance (%%)\\nstub\\tdomain\\t1.0\\t100.0\\n' > singlem.level_coverage.tsv
    for rank in domain phylum class order family genus species; do
        printf 'taxonomy\\tstub\\nunassigned\\t0.0\\nRoot; d__Bacteria\\t100.0\\n' > singlem.by_rank-\$rank.tsv
    done
    printf '<!DOCTYPE html>\\n<html><head><title>stub</title></head><body></body></html>\\n' > singlem.krona.html
    """
}
