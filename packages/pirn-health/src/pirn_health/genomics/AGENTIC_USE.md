Processes NGS data through alignment, variant calling, expression quantification, and multi-omics integration — does NOT store sequence data; use BamFormat, FastaFormat, VcfFormat, or FastqFormat for I/O.

## Mental model

Each knot wraps a single bioinformatics tool or algorithm stage. Knots consume and produce file-path strings or in-memory byte buffers; they never open connections to sequence databases or LIMS systems. Pipeline topology is expressed as a pirn `Tapestry` — wire knots together rather than calling tools in sequence with subprocess.

The `GenomicsQcGate` knot acts as a quality checkpoint. It raises `GenomicsQcError` on quality failures so the tapestry fails loudly rather than propagating low-quality data silently. All other knots are unconditional transforms — quality decisions belong in the gate, not scattered across stages.

## Source map

```
pirn_health/genomics/
├── adapter_trimmer.py              AdapterTrimmer                  — trims adapter sequences from raw reads
├── bam_sort_indexer.py             BamSortIndexer                  — coordinate-sorts and indexes BAM files
├── bcftools_caller.py              BcftoolsCaller                  — variant calling via bcftools mpileup/call
├── bowtie2_aligner.py              Bowtie2Aligner                  — short-read alignment with Bowtie2
├── bulk_atac_seq_processor.py      BulkAtacSeqProcessor            — bulk ATAC-seq peak calling and QC
├── bwa_aligner.py                  BwaAligner                      — short-read alignment with BWA-MEM
├── cnv_detector.py                 CnvDetector                     — copy number variant detection
├── differential_expression_analyzer.py  DifferentialExpressionAnalyzer  — DESeq2/edgeR DE analysis
├── expression_quantifier.py        ExpressionQuantifier            — transcript-level quantification (RSEM/Salmon)
├── fastq_quality_controller.py     FastqQualityController          — per-base quality metrics via FastQC
├── gatk_caller.py                  GatkCaller                      — variant calling via GATK HaplotypeCaller
├── gene_set_enrichment_runner.py   GeneSetEnrichmentRunner         — GSEA/fgsea enrichment analysis
├── genomics_qc_error.py            GenomicsQcError                 — typed error for QC gate failures
├── genomics_qc_gate.py             GenomicsQcGate                  — quality gate; raises GenomicsQcError on failure
├── gvcf_combiner.py                GvcfCombiner                    — merges per-sample gVCFs for joint genotyping
├── methylation_array_processor.py  MethylationArrayProcessor       — Illumina EPIC/450K array normalisation
├── multi_omics_integrator.py       MultiOmicsIntegrator            — integrates expression, methylation, and variant data
├── pathway_enricher.py             PathwayEnricher                 — pathway over-representation analysis
├── pharmacogenomic_scorer.py       PharmacogenomicScorer           — CPIC-based drug-gene interaction scoring
├── single_cell_clusterer.py        SingleCellClusterer             — Leiden/Louvain clustering on AnnData
├── snpeff_annotator.py             SnpeffAnnotator                 — functional annotation via SnpEff
├── star_aligner.py                 StarAligner                     — splice-aware RNA-seq alignment with STAR
├── structural_variant_detector.py  StructuralVariantDetector       — SV detection via Manta/DELLY
├── vcf_filter.py                   VcfFilter                       — hard and soft variant filtering
├── vcf_merger.py                   VcfMerger                       — merges per-sample VCFs into a multi-sample VCF
└── vep_annotator.py                VepAnnotator                    — functional annotation via Ensembl VEP
```

## Canonical pattern

FASTQ QC → adapter trim → BWA align → sort/index → GATK variant call:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn_health.genomics.fastq_quality_controller import FastqQualityController
from pirn_health.genomics.adapter_trimmer import AdapterTrimmer
from pirn_health.genomics.bwa_aligner import BwaAligner
from pirn_health.genomics.bam_sort_indexer import BamSortIndexer
from pirn_health.genomics.gatk_caller import GatkCaller
from pirn.tapestry import Tapestry

with Tapestry() as t:
    fastq_r1 = Parameter("fastq_r1", bytes)
    fastq_r2 = Parameter("fastq_r2", bytes)
    reference = Parameter("reference", str)   # path to reference genome index

    qc = FastqQualityController(
        fastq_r1=fastq_r1,
        fastq_r2=fastq_r2,
        _config=KnotConfig(id="qc"),
    )
    trimmed = AdapterTrimmer(
        fastq_r1=fastq_r1,
        fastq_r2=fastq_r2,
        qc_report=qc,
        _config=KnotConfig(id="trim"),
    )
    aligned = BwaAligner(
        fastq_r1=trimmed,
        reference=reference,
        _config=KnotConfig(id="align"),
    )
    sorted_bam = BamSortIndexer(
        bam=aligned,
        _config=KnotConfig(id="sort"),
    )
    GatkCaller(
        bam=sorted_bam,
        reference=reference,
        _config=KnotConfig(id="gatk"),
    )

result = await t.run(RunRequest(parameters={
    "fastq_r1": open("sample_R1.fastq.gz", "rb").read(),
    "fastq_r2": open("sample_R2.fastq.gz", "rb").read(),
    "reference": "/refs/hg38/bwa_index/hg38",
}))
vcf_bytes = result.outputs["gatk"]
```

## Anti-patterns

**Skipping the QC gate and trimming step** — passing raw FASTQ directly to an aligner without `FastqQualityController` and `AdapterTrimmer` degrades alignment rates and inflates false-positive variant calls. Always run QC and trimming before alignment.

**Running joint genotyping in a single-sample tapestry** — `GvcfCombiner` expects multiple per-sample gVCF files. Calling it with one sample produces a degenerate joint-call VCF that GATK tools will reject downstream. Use `GatkCaller` alone for single-sample pipelines; reserve `GvcfCombiner` for cohort workflows.

**Passing reference genome paths across execution boundaries** — reference indices are large filesystem artefacts. Pass paths that are valid on the worker executing the knot; do not embed absolute host paths in `RunRequest` parameters when running on distributed infra.

## Constraints and gotchas

- All knots require the wrapped tool binary on `PATH` (bwa, samtools, gatk, STAR, etc.); pirn does not bundle or manage tool installations. Use `pirn[genomics]` for Python SDK dependencies only.
- `GatkCaller` spawns a JVM subprocess. Ensure `JAVA_HOME` is set and at least 4 GB of heap is available (`-Xmx4g` is the default; override via `KnotConfig.extra`).
- `SingleCellClusterer` loads a full `AnnData` object into memory. For large atlases (>500k cells) ensure the worker has sufficient RAM before wiring this knot.
- `GenomicsQcGate` raises `GenomicsQcError` — catch it at the tapestry call site if downstream steps should proceed on partial data rather than halt.
- `MultiOmicsIntegrator` expects all omics layers to be pre-aligned to the same sample identifiers. Mismatched sample IDs cause a `ValueError` at process time, not at wiring time.
- Install: `pip install pirn[genomics]`

## Quick reference

| Task | How |
|---|---|
| Raw FASTQ → aligned BAM | `FastqQualityController` → `AdapterTrimmer` → `BwaAligner` or `StarAligner` → `BamSortIndexer` |
| Single-sample SNV/indel calling | `GatkCaller` on sorted BAM |
| Multi-sample joint genotyping | `GatkCaller` (gVCF mode) per sample → `GvcfCombiner` → GATK GenotypeGVCFs |
| Annotate variants | `SnpeffAnnotator` or `VepAnnotator` after VCF filtering |
| RNA-seq DE analysis | `StarAligner` → `ExpressionQuantifier` → `DifferentialExpressionAnalyzer` |
| Single-cell clustering | `SingleCellClusterer` on AnnData bytes |
| Pathway enrichment | `GeneSetEnrichmentRunner` or `PathwayEnricher` on DE gene lists |
| Copy number variants | `CnvDetector` on BAM; structural variants via `StructuralVariantDetector` |
| Methylation array | `MethylationArrayProcessor` on raw IDAT bytes |
| Pharmacogenomics | `PharmacogenomicScorer` on annotated VCF |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
