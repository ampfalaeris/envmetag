//
// Read QC and cleaning: FastQC (raw) -> fastp -> FastQC (trimmed) -> PhiX removal (bowtie2) -> host removal (Hostile)
// Cleaned reads feed assembly and the marker-gene module. SingleM uses the fastp-trimmed reads, before PhiX and
// host removal, so its prokaryotic fraction is a share of all sequenced reads (DECISIONS.md, 2026-10-26).
//
// The nf-core modules here are legacy (untyped). Records are converted to tuple(meta, reads) right before each
// call and back to records right after; that boundary is not type-checked, so it is covered by this subworkflow's tests.
//

nextflow.enable.types = true

include { FASTQC as FASTQC_RAW     } from '../../../modules/nf-core/fastqc'
include { FASTQC as FASTQC_TRIMMED } from '../../../modules/nf-core/fastqc'
include { FASTP                    } from '../../../modules/nf-core/fastp'
include { BOWTIE2_BUILD            } from '../../../modules/nf-core/bowtie2/build'
include { BOWTIE2_ALIGN            } from '../../../modules/nf-core/bowtie2/align'
include { HOSTILE_FETCH            } from '../../../modules/nf-core/hostile/fetch'
include { HOSTILE_CLEAN            } from '../../../modules/nf-core/hostile/clean'
include { Sample                   } from '../../../types'

workflow PREPROCESS_READS {

    take:
    samples: Channel<Sample>        // raw reads, one record per sample
    phix_fasta: Value<Path>         // PhiX reference (FASTA)
    hostile_index: Value<String>    // Hostile index name, fetched at runtime

    main:
    // record -> legacy tuple(meta, [r1, r2])
    def raw_tuples = samples.map { s -> tuple([id: s.id, single_end: false], [s.r1, s.r2]) }

    def raw_qc = FASTQC_RAW(raw_tuples)

    def fastp_out = FASTP(raw_tuples.map { meta, reads -> tuple(meta, reads, []) }, false, false, false)

    def trimmed_qc = FASTQC_TRIMMED(fastp_out.reads)

    // legacy tuple -> record for SingleM; pick R1/R2 by name, never by position
    def trimmed_reads = fastp_out.reads.map { meta, reads ->
        def r1 = reads.find { f -> f.name.endsWith('_R1.fastp.fastq.gz') }
        def r2 = reads.find { f -> f.name.endsWith('_R2.fastp.fastq.gz') }
        if (r1 == null || r2 == null) {
            error("PREPROCESS_READS: fastp output for sample '${meta.id}' is not a read pair: ${reads*.name}")
        }
        record(id: meta.id, r1: r1, r2: r2)
    }

    def phix_index = BOWTIE2_BUILD(phix_fasta.map { fasta -> tuple([id: 'phix'], fasta) })
    def phix_out = BOWTIE2_ALIGN(fastp_out.reads, phix_index.index, tuple([id: 'phix'], []), true, false)

    def hostile_ref = HOSTILE_FETCH(hostile_index)
    def hostile_out = HOSTILE_CLEAN(phix_out.fastq, hostile_ref.reference)

    // legacy tuple -> record, immediately after the last call; pick R1/R2 by name, never by position
    def clean_reads = hostile_out.fastq.map { meta, reads ->
        def r1 = reads.find { f -> f.name.endsWith('_1.fastq.gz') }
        def r2 = reads.find { f -> f.name.endsWith('_2.fastq.gz') }
        if (r1 == null || r2 == null) {
            error("PREPROCESS_READS: Hostile output for sample '${meta.id}' is not a read pair: ${reads*.name}")
        }
        record(id: meta.id, r1: r1, r2: r2)
    }

    // every report MultiQC parses natively (FastQC zip, fastp JSON, bowtie2 log, Hostile JSON).
    // FastQC emits a List of zips for paired reads but a single Path when there is one (e.g. its stub);
    // normalise explicitly, because flatMap over a bare Path would iterate its path components.
    def qc_reports = raw_qc.zip.flatMap { _meta, zips -> zips instanceof Path ? [zips] : zips }
        .mix(trimmed_qc.zip.flatMap { _meta, zips -> zips instanceof Path ? [zips] : zips })
        .mix(fastp_out.json.map { _meta, json -> json })
        .mix(phix_out.log.map { _meta, log -> log })
        .mix(hostile_out.json.map { _meta, json -> json })

    emit:
    trimmed: Channel<Sample> = trimmed_reads   // fastp output (adapter-trimmed), input to SingleM
    clean: Channel<Sample> = clean_reads
    multiqc_files: Channel<Path> = qc_reports
}
