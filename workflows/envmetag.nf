/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.types = true

include { PREPROCESS_READS       } from '../subworkflows/local/preprocess_reads'
include { PROFILE_SINGLEM        } from '../subworkflows/local/profile_singlem'
include { SINGLEM_FRACTIONMQC    } from '../modules/local/singlem/fractionmqc'
include { ENVMETAG_REPORT        } from '../modules/local/envmetag/report'
include { MULTIQC                } from '../modules/nf-core/multiqc/main'
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { paramsSummaryMultiqc   } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_envmetag_pipeline'
include { Sample                 } from '../types'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow ENVMETAG {

    take:
    samples: Channel<Sample>                // raw paired-end reads, one record per sample
    phix_fasta: Value<Path>                 // PhiX reference for bowtie2
    hostile_index: Value<String>            // Hostile index name
    metapackage: Value<Path>                // extracted SingleM metapackage
    multiqc_config: Path                    // MultiQC config (pipeline default or --multiqc_config)
    multiqc_logo: Path?                     // optional logo
    multiqc_methods_description: Path       // methods description template
    report_template: Path                   // assets/report: report template and theme files

    main:
    // Clean reads feed later assembly and marker steps; SingleM runs on the fastp-trimmed reads (DECISIONS.md)
    def preprocessed = PREPROCESS_READS(samples, phix_fasta, hostile_index)
    def singlem = PROFILE_SINGLEM(preprocessed.trimmed, metapackage)
    def fraction_mqc = SINGLEM_FRACTIONMQC(singlem.fractions.map { r -> r.fraction }.collect())

    //
    // envmetag report: SingleM community results. Inputs come from channels, not the published index files
    // (DECISIONS.md); the samplesheet ids are passed so the report fails if SingleM lost a sample.
    //
    def envmetag_report_out = ENVMETAG_REPORT(
        samples.map { s -> s.id }.collect(),
        singlem.profiles.map { r -> r.profile }.collect(),
        singlem.fractions.map { r -> r.fraction }.collect(),
        singlem.summary.map { s -> s.by_rank },
        singlem.summary.map { s -> s.level_coverage },
        singlem.summary.map { s -> s.extras },
        metapackage.map { m -> m.name },
        report_template
    )

    //
    // Collate software versions: every module emits tuple(process, tool, version) on the `versions` topic
    //
    // Topic items are untyped (index, don't destructure). Group per process in one closure rather than with
    // groupTuple (discouraged under static typing); flatMap turns the collected Value back into a Channel
    // because collectFile is only usable on a Channel.
    def versions_yaml = channel.topic('versions')
        .map { v -> [process: "${v[0]}".tokenize(':')[-1], line: "  ${v[1]}: ${v[2]}"] }
        .collect()
        .flatMap { entries ->
            def by_process = entries.groupBy { e -> e.process }
            by_process.keySet().toSorted().collect { p -> "${p}:\n" + by_process[p].collect { e -> e.line }.toUnique().toSorted().join('\n') }
        }
        .collectFile(name: 'envmetag_software_mqc_versions.yml', sort: true, newLine: true)

    def summary_yaml = channel.of(paramsSummaryMultiqc(paramsSummaryMap(workflow, parameters_schema: 'nextflow_schema.json')))
        .collectFile(name: 'workflow_summary_mqc.yaml')
    def methods_yaml = channel.of(methodsDescriptionText(multiqc_methods_description))
        .collectFile(name: 'methods_description_mqc.yaml')

    //
    // MultiQC: read QC and accounting only; community profiles go to the envmetag report
    //
    def multiqc_inputs = preprocessed.multiqc_files
        .mix(fraction_mqc)
        .mix(versions_yaml)
        .mix(summary_yaml)
        .mix(methods_yaml)
    def logo = multiqc_logo != null ? [multiqc_logo] : []
    def multiqc_out = MULTIQC(
        multiqc_inputs.collect().map { files ->
            tuple([id: 'envmetag'], files, multiqc_config, logo, [], [])
        }
    )

    emit:
    clean_reads: Channel<Sample> = preprocessed.clean
    singlem_profiles: Channel<Record> = singlem.profiles
    singlem_fractions: Channel<Record> = singlem.fractions
    singlem_summary: Value<Record> = singlem.summary
    envmetag_report: Value<Record> = envmetag_report_out   // report, data
    software_versions: Channel<Path> = versions_yaml
    multiqc_report: Value<Path> = multiqc_out.report.map { _meta, report -> report }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
