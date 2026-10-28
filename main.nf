#!/usr/bin/env nextflow
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ampfalaeris/envmetag
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Github : https://github.com/ampfalaeris/envmetag
----------------------------------------------------------------------------------------
*/

nextflow.enable.types = true

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT FUNCTIONS / MODULES / SUBWORKFLOWS / WORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { ENVMETAG                   } from './workflows/envmetag'
include { SINGLEM_PREPAREMETAPACKAGE } from './modules/local/singlem/preparemetapackage'
include { PIPELINE_INITIALISATION    } from './subworkflows/local/utils_nfcore_envmetag_pipeline'
include { PIPELINE_COMPLETION        } from './subworkflows/local/utils_nfcore_envmetag_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PARAMETERS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Types only. Defaults live in nextflow.config (a config value overrides a default declared
    here, so declaring both would let them drift apart). Descriptions live in nextflow_schema.json.
    `input` is a String, not a Path: the template's params JSON dump recurses forever on a Path
    (DECISIONS.md); nf-schema still checks that the file exists.
----------------------------------------------------------------------------------------
*/

params {
    input: String
    outdir: String

    phix_fasta: String
    hostile_index: String

    singlem_metapackage: String?
    singlem_metapackage_url: String
    singlem_db_cache: String?

    multiqc_config: String?
    multiqc_logo: String?
    multiqc_methods_description: String?

    email: String?
    email_on_fail: String?
    plaintext_email: Boolean
    monochrome_logs: Boolean
    version: Boolean
    validate_params: Boolean
    help: Boolean
    help_full: Boolean
    show_hidden: Boolean
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow {

    main:
    //
    // SUBWORKFLOW: Run initialisation tasks (parameter + samplesheet validation via nf-schema)
    //
    def init = PIPELINE_INITIALISATION(
        params.version,
        params.validate_params,
        params.monochrome_logs,
        args,
        params.outdir,
        params.input,
        params.help,
        params.help_full,
        params.show_hidden
    )

    // legacy tuple(meta, reads) -> Sample record; the schema guarantees paired-end and unique sample ids
    def samples = init.samplesheet.map { meta, reads ->
        if (reads.size() != 2) {
            error("Sample '${meta.id}' has ${reads.size()} read files; envmetag v0.1 takes exactly one paired-end pair per sample")
        }
        record(id: meta.id, r1: reads[0], r2: reads[1])
    }

    //
    // SingleM metapackage: an existing extracted copy, or a download of --singlem_metapackage_url, kept in
    // --singlem_db_cache when set and otherwise extracted in the work directory for this run (DECISIONS.md)
    //
    if (!params.singlem_metapackage && !params.singlem_db_cache) {
        log.warn("Neither --singlem_metapackage nor --singlem_db_cache is set: downloading ${params.singlem_metapackage_url} and extracting it in the work directory (the default GlobDB r232 archive is a 3.8 GB download, 17 GB extracted). A fresh run downloads it again; set --singlem_db_cache to keep one copy.")
    }
    def metapackage = params.singlem_metapackage
        ? channel.value(file(params.singlem_metapackage, checkIfExists: true))
        : SINGLEM_PREPAREMETAPACKAGE(channel.value(file(params.singlem_metapackage_url)))

    def multiqc_config = params.multiqc_config
        ? file(params.multiqc_config, checkIfExists: true)
        : file("${projectDir}/assets/multiqc_config.yml", checkIfExists: true)
    def multiqc_methods = params.multiqc_methods_description
        ? file(params.multiqc_methods_description, checkIfExists: true)
        : file("${projectDir}/assets/methods_description_template.yml", checkIfExists: true)
    def multiqc_logo = params.multiqc_logo ? file(params.multiqc_logo, checkIfExists: true) : null
    def report_template = file("${projectDir}/assets/report", checkIfExists: true)

    //
    // WORKFLOW: Run main workflow
    //
    def run = ENVMETAG(
        samples,
        channel.value(file(params.phix_fasta)),
        channel.value(params.hostile_index),
        metapackage,
        multiqc_config,
        multiqc_logo,
        multiqc_methods,
        report_template
    )

    //
    // SUBWORKFLOW: Run completion tasks
    //
    PIPELINE_COMPLETION(
        params.email,
        params.email_on_fail,
        params.plaintext_email,
        params.outdir,
        params.monochrome_logs,
        run.multiqc_report
    )

    publish:
    clean_reads = run.clean_reads
    singlem_profiles = run.singlem_profiles
    singlem_fractions = run.singlem_fractions
    singlem_summary = run.singlem_summary
    envmetag_report = run.envmetag_report
    software_versions = run.software_versions
    multiqc_report = run.multiqc_report
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    OUTPUTS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Users and downstream pipelines read the index files, never by globbing these directories. Steps in
    this run (including the report) take records from channels; no channel carries the index files.
----------------------------------------------------------------------------------------
*/

output {
    clean_reads {
        path { r ->
            r.r1 >> "preprocess/clean_reads/${r.id}/"
            r.r2 >> "preprocess/clean_reads/${r.id}/"
        }
        index {
            path 'preprocess/clean_reads.csv'
            header true
        }
    }
    singlem_profiles {
        path { r ->
            r.profile >> "singlem/profiles/"
            r.archive_otu_table >> "singlem/archive_otu_tables/"
        }
        index {
            path 'singlem/profiles.csv'
            header true
        }
    }
    singlem_fractions {
        path { r -> r.fraction >> "singlem/prokaryotic_fraction/" }
        index {
            path 'singlem/prokaryotic_fraction.csv'
            header true
        }
    }
    singlem_summary {
        path 'singlem/summary'
        index {
            path 'singlem/summary.json'
        }
    }
    envmetag_report {
        // MultiQC and Krona links in the report are relative to report/ (conf/modules.config)
        path { r ->
            r.report >> 'report/'
            r.data >> 'report/'
        }
    }
    software_versions {
        path 'pipeline_info'
    }
    multiqc_report {
        path 'multiqc'
    }
}
