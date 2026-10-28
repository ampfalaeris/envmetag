# ampfalaeris/envmetag

[![GitHub Actions CI Status](https://github.com/ampfalaeris/envmetag/actions/workflows/nf-test.yml/badge.svg)](https://github.com/ampfalaeris/envmetag/actions/workflows/nf-test.yml)
[![GitHub Actions Linting Status](https://github.com/ampfalaeris/envmetag/actions/workflows/linting.yml/badge.svg)](https://github.com/ampfalaeris/envmetag/actions/workflows/linting.yml)
[![nf-test](https://img.shields.io/badge/unit_tests-nf--test-337ab7.svg)](https://www.nf-test.com)

[![Nextflow](https://img.shields.io/badge/version-%E2%89%A526.10.0-green?style=flat&logo=nextflow&logoColor=white&color=%230DC09D&link=https%3A%2F%2Fnextflow.io)](https://www.nextflow.io/)
[![nf-core template version](https://img.shields.io/badge/nf--core_template-4.2.0-green?style=flat&logo=nfcore&logoColor=white&color=%2324B064&link=https%3A%2F%2Fnf-co.re)](https://github.com/nf-core/tools/releases/tag/4.2.0)
[![run with conda](http://img.shields.io/badge/run%20with-conda-3EB049?labelColor=000000&logo=anaconda)](https://docs.conda.io/en/latest/)
[![run with docker](https://img.shields.io/badge/run%20with-docker-0db7ed?labelColor=000000&logo=docker)](https://www.docker.com/)
[![run with singularity](https://img.shields.io/badge/run%20with-singularity-1d355c.svg?labelColor=000000)](https://sylabs.io/docs/)

## Introduction

**ampfalaeris/envmetag** profiles shotgun metagenomes from environmental samples: remediation sites, microbially influenced corrosion (MIC), and general environmental monitoring. It takes paired-end Illumina reads, cleans them, and estimates which Bacteria and Archaea are present and what share of the reads they account for. Later versions add curated marker genes for sulfur, methane, and nitrogen cycling and hydrocarbon degradation.

envmetag is built from the nf-core template but is not an nf-core pipeline.

Current steps (v0.1, in development):

1. Read QC of the raw reads ([FastQC](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/))
2. Adapter and poly-G trimming ([fastp](https://github.com/OpenGene/fastp)), followed by FastQC on the trimmed reads
3. Taxonomic profiling of the trimmed reads ([SingleM](https://github.com/wwood/singlem) with the [GlobDB](https://globdb.org) r232 metapackage), including SingleM's estimate of the prokaryotic fraction of the reads
4. PhiX removal ([Bowtie 2](https://github.com/BenLangmead/bowtie2)) and host-read removal ([Hostile](https://github.com/bede/hostile)) to produce clean reads for later steps
5. Read QC and read accounting across samples ([MultiQC](https://multiqc.info))
6. A self-contained HTML report of the community profiles ([Quarto](https://quarto.org), [Plotly](https://plotly.com/python/))

Planned: read-based marker-gene abundance (v0.2); assembly, binning, and CheckM2 (v0.3); index files for nf-core/funcscan (v0.4).

## Usage

> [!NOTE]
> If you are new to Nextflow, see [this page](https://nf-co.re/docs/get_started/environment_setup/overview) for setting it up. Test your setup with `-profile test` before running the pipeline on real data. envmetag needs Nextflow 26.10.0 or later.

Prepare a samplesheet with one row per sample and one pair of gzipped FASTQ files per row (paired-end reads only):

```csv title="samplesheet.csv"
sample,fastq_1,fastq_2
site_a,/data/site_a_R1.fastq.gz,/data/site_a_R2.fastq.gz
```

SingleM needs the GlobDB r232 metapackage (3.8 GB download, 17 GB extracted). Either point the pipeline at an extracted copy:

```bash
nextflow run ampfalaeris/envmetag \
   -profile docker \
   --input samplesheet.csv \
   --singlem_metapackage /path/to/GlobDB_r232.metapackage_v4.smpkg \
   --outdir results
```

or let it download the metapackage once into a cache directory with `--singlem_db_cache /path/to/cache` (the first run needs about 21 GB free there and in `work/`). With neither option, the pipeline downloads and extracts it in `work/` on every fresh run.

See the [usage documentation](docs/usage.md) for all options and the [output documentation](docs/output.md) for what each result file means.

> [!WARNING]
> Provide pipeline parameters on the command line or with `-params-file`. Config files passed with `-c` can set anything **except** parameters; see the [nf-core docs](https://nf-co.re/docs/running/run-pipelines#using-parameter-files).

## Test data

The `test` and `test_full` profiles use reads subsampled from two public carbon-steel corrosion metagenomes, with simulated PhiX and human-mitochondrion reads added so the removal steps have a known target:

| Run | BioProject | Sample | Study |
| --- | --- | --- | --- |
| [SRR12174148](https://www.ebi.ac.uk/ena/browser/view/SRR12174148) | PRJNA644413 | Carbon steel coupon biofilm exposed to oil field production water | [doi:10.1128/aem.01819-20](https://doi.org/10.1128/aem.01819-20) |
| [SRR35816318](https://www.ebi.ac.uk/ena/browser/view/SRR35816318) | PRJNA1346464 | Acid-producing-bacteria enrichment biofilm on a carbon steel coupon | [doi:10.3389/fmicb.2026.1771929](https://doi.org/10.3389/fmicb.2026.1771929) |

- Test reads: Zenodo record [23679308](https://zenodo.org/records/23679308) (CC BY 4.0), built by [`tests/testdata/build_testdata.sh`](tests/testdata/build_testdata.sh).
- CI metapackage: Zenodo record [23679677](https://zenodo.org/records/23679677) (CC BY-SA 4.0), a 3-marker subset of the GlobDB r232 SingleM metapackage. It tests the pipeline's plumbing and file formats, not biology.

`-profile test` downloads both from Zenodo and needs no other parameters (the CI metapackage is 195 MB, about 1 GB extracted in `work/`).

## Licences

The pipeline code is MIT-licensed. The GlobDB metapackage is downloaded at runtime, never bundled, and is licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); please cite GlobDB and its [underlying data sources](https://globdb.org/citations).

## Credits

ampfalaeris/envmetag was written by Adam M. Partin.

## Contributions and Support

If you would like to contribute to this pipeline, please see the [contributing guidelines](docs/CONTRIBUTING.md). Design decisions and the evidence behind them are recorded in [`DECISIONS.md`](DECISIONS.md).

## Citations

A pipeline DOI will be added at the first release.

References for the tools and data used by the pipeline are listed in [`CITATIONS.md`](CITATIONS.md).

This pipeline uses code and infrastructure developed and maintained by the [nf-core](https://nf-co.re) community, reused here under the [MIT license](https://github.com/nf-core/tools/blob/main/LICENSE).

> **The nf-core framework for community-curated bioinformatics pipelines.**
>
> Philip Ewels, Alexander Peltzer, Sven Fillinger, Harshil Patel, Johannes Alneberg, Andreas Wilm, Maxime Ulysse Garcia, Paolo Di Tommaso & Sven Nahnsen.
>
> _Nat Biotechnol._ 2020 Feb 13. doi: [10.1038/s41587-020-0439-x](https://dx.doi.org/10.1038/s41587-020-0439-x).
