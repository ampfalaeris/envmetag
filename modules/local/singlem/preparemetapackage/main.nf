nextflow.enable.types = true

process SINGLEM_PREPAREMETAPACKAGE {
    tag "${archive.name}"
    label 'process_single'

    container 'quay.io/biocontainers/singlem:0.21.4--pyhdfd78af_2'

    // storeDir is set in conf/modules.config from --singlem_db_cache: the extracted metapackage is kept
    // once per machine and later runs skip this task (and do not re-download the archive)

    input:
    archive: Path   // <name>.smpkg.tar.gz, e.g. GlobDB_r232.metapackage_v4.smpkg.tar.gz

    output:
    file(archive.name.replaceAll(/\.tar\.gz$/, ''))

    topic:
    tuple(task.process, 'singlem', eval('singlem --version')) >> 'versions'

    script:
    def metapackage = archive.name.replaceAll(/\.tar\.gz$/, '')
    """
    tar -xzf ${archive}

    if [ ! -f ${metapackage}/CONTENTS.json ]; then
        echo "ERROR: ${archive.name} did not extract to a SingleM metapackage (no ${metapackage}/CONTENTS.json)" >&2
        exit 1
    fi
    """

    stub:
    def metapackage = archive.name.replaceAll(/\.tar\.gz$/, '')
    """
    mkdir ${metapackage}
    echo '{"singlem_metapackage_version": 6, "singlem_packages": []}' > ${metapackage}/CONTENTS.json
    """
}
