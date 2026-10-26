/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Record types shared across modules and subworkflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Record types are script-scoped: include them where used, e.g.
        include { Sample } from '../../types'
----------------------------------------------------------------------------------------
*/

nextflow.enable.types = true

// Paired-end reads for one sample. `id` is the samplesheet `sample` column.
record Sample {
    id: String
    r1: Path
    r2: Path
}

// fastp-trimmed reads joined with that sample's SingleM profile (input to prokaryotic_fraction,
// which must see the same reads that produced the profile).
record SampleProfile {
    id: String
    r1: Path
    r2: Path
    profile: Path
}
