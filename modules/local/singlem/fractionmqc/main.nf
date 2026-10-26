nextflow.enable.types = true

process SINGLEM_FRACTIONMQC {
    label 'process_single'

    // bin/singlem_fraction_mqc.py uses only the Python standard library; python3 ships in this container
    container 'quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2'

    input:
    fractions: Bag<Path>

    output:
    file('singlem_prokaryotic_fraction_mqc.tsv')

    script:
    """
    singlem_fraction_mqc.py ${fractions.toSorted { f -> f.name }.join(' ')} --output singlem_prokaryotic_fraction_mqc.tsv
    """

    stub:
    """
    printf '# id: singlem_prokaryotic_fraction\\n# plot_type: generalstats\\nSample\\tread_fraction\\taverage_bacterial_archaeal_genome_size\\twarning\\nstub\\t0.00\\t0.00\\t\\n' > singlem_prokaryotic_fraction_mqc.tsv
    """
}
