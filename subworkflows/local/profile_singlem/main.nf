//
// SingleM read-based taxonomic profiling on raw reads (SingleM docs: use raw, untrimmed reads)
//

nextflow.enable.types = true

include { SINGLEM_PIPE                } from '../../../modules/local/singlem/pipe'
include { SINGLEM_PROKARYOTICFRACTION } from '../../../modules/local/singlem/prokaryoticfraction'
include { SINGLEM_SUMMARISE           } from '../../../modules/local/singlem/summarise'
include { Sample                      } from '../../../types'

workflow PROFILE_SINGLEM {

    take:
    samples: Channel<Sample>   // raw reads, one record per sample
    metapackage: Value<Path>   // extracted SingleM metapackage directory (.smpkg)

    main:
    def pipe_results = SINGLEM_PIPE(samples, metapackage)

    // prokaryotic_fraction must see the same reads that produced each profile.
    // The process output is the receiver: a legacy channel (e.g. nf-test's input) rejects a typed one as join argument.
    def reads_with_profile = pipe_results
        .join(samples, by: 'id', remainder: true)
        .map { r ->
            if (r.r1 == null || r.profile == null) {
                error("PROFILE_SINGLEM: sample '${r.id}' is missing ${r.r1 == null ? 'its reads' : 'a SingleM profile'} -- every sample must have both")
            }
            record(id: r.id, r1: r.r1, r2: r.r2, profile: r.profile)
        }
    def fraction_results = SINGLEM_PROKARYOTICFRACTION(reads_with_profile, metapackage)

    def summary_result = SINGLEM_SUMMARISE(pipe_results.map { r -> r.profile }.collect())

    emit:
    profiles: Channel<Record> = pipe_results       // id, profile, archive_otu_table
    fractions: Channel<Record> = fraction_results  // id, fraction
    summary: Value<Record> = summary_result        // combined, extras, level_coverage, by_rank, krona
}
