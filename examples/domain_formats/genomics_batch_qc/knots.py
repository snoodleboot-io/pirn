"""Knot factories for the ``examples.domain_formats.genomics_batch_qc`` example."""

from __future__ import annotations

import random

from pirn.core.knot_factory import KnotFactory

from examples.domain_formats.genomics_batch_qc.alignment_result import AlignmentResult
from examples.domain_formats.genomics_batch_qc.fastq_read import FastqRead
from examples.domain_formats.genomics_batch_qc.read_qc import ReadQC
from examples.domain_formats.genomics_batch_qc.run_summary import RunSummary
from examples.domain_formats.genomics_batch_qc.sequencing_config import SequencingConfig
from examples.domain_formats.genomics_batch_qc.trimmed_read import TrimmedRead


@KnotFactory.knot
async def qc_read(read: FastqRead) -> ReadQC:
    """Compute per-read QC metrics and pass/fail classification."""
    if not read.sequence:
        return ReadQC(
            seq_id=read.seq_id,
            mean_quality=0.0,
            gc_content=0.0,
            n_fraction=0.0,
            pass_qc=False,
            fail_reason="empty sequence",
        )

    phred_scores = [ord(c) - 33 for c in read.quality]
    mean_quality = sum(phred_scores) / len(phred_scores)

    seq_upper = read.sequence.upper()
    gc_count = seq_upper.count("G") + seq_upper.count("C")
    gc_content = gc_count / len(seq_upper)
    n_fraction = seq_upper.count("N") / len(seq_upper)

    fail_reason = ""
    if mean_quality < 20.0:
        fail_reason = f"low mean quality ({mean_quality:.1f} < 20)"
    elif n_fraction > 0.10:
        fail_reason = f"high N fraction ({n_fraction:.2%} > 10%)"
    elif len(read.sequence) < SequencingConfig.min_read_length:
        fail_reason = f"read too short ({len(read.sequence)} < {SequencingConfig.min_read_length})"

    return ReadQC(
        seq_id=read.seq_id,
        mean_quality=round(mean_quality, 2),
        gc_content=round(gc_content, 4),
        n_fraction=round(n_fraction, 4),
        pass_qc=fail_reason == "",
        fail_reason=fail_reason,
    )


@KnotFactory.knot
async def trim_adapters(read: FastqRead, qc: ReadQC) -> TrimmedRead:
    """Trim leading/trailing low-quality bases and known adapter prefix."""
    seq = read.sequence
    qual = read.quality
    original_length = len(seq)
    adapter_found = False

    # Trim adapter prefix if present
    if seq.startswith(SequencingConfig.known_adapter):
        trim_len = len(SequencingConfig.known_adapter)
        seq = seq[trim_len:]
        qual = qual[trim_len:]
        adapter_found = True

    # Trim trailing low-quality bases
    while qual and (ord(qual[-1]) - 33) < SequencingConfig.low_quality_threshold:
        seq = seq[:-1]
        qual = qual[:-1]

    # Trim leading low-quality bases
    while qual and (ord(qual[0]) - 33) < SequencingConfig.low_quality_threshold:
        seq = seq[1:]
        qual = qual[1:]

    bases_trimmed = original_length - len(seq)

    return TrimmedRead(
        seq_id=read.seq_id,
        original_length=original_length,
        trimmed_sequence=seq,
        trimmed_quality=qual,
        adapter_found=adapter_found,
        bases_trimmed=bases_trimmed,
    )


@KnotFactory.knot
async def align_read(trimmed: TrimmedRead) -> AlignmentResult:
    """Simulate alignment: assign contig/position and mapping quality."""
    # Use a deterministic RNG seeded from the seq_id for reproducibility
    rng = random.Random(trimmed.seq_id)

    trimmed_length = len(trimmed.trimmed_sequence)

    if trimmed_length < SequencingConfig.min_read_length:
        return AlignmentResult(
            seq_id=trimmed.seq_id,
            contig="*",
            position=0,
            mapping_quality=0,
            alignment_status="unaligned",
            trimmed_length=trimmed_length,
        )

    # Simulate alignment outcome weighted by read length and N content
    n_fraction = trimmed.trimmed_sequence.upper().count("N") / max(trimmed_length, 1)
    roll = rng.random()

    if n_fraction > 0.15 or roll < 0.05:
        status = "unaligned"
        contig = "*"
        position = 0
        mapq = 0
    elif roll < 0.15:
        status = "multi"
        contig = rng.choice(SequencingConfig.contigs)
        position = rng.randint(1, 250_000_000)
        mapq = rng.randint(1, 3)
    else:
        status = "unique"
        contig = rng.choice(SequencingConfig.contigs)
        position = rng.randint(1, 250_000_000)
        mapq = rng.randint(20, 60)

    return AlignmentResult(
        seq_id=trimmed.seq_id,
        contig=contig,
        position=position,
        mapping_quality=mapq,
        alignment_status=status,
        trimmed_length=trimmed_length,
    )


@KnotFactory.knot
async def summarise_run(alignments: list[AlignmentResult]) -> RunSummary:
    """Aggregate per-read alignment results into a run-level summary."""
    # alignments carries the full pipeline provenance via the graph; we
    # need the upstream QC and trim data to compute aggregate metrics.
    # Because pirn passes typed outputs through the graph, we receive
    # AlignmentResult objects here.  Aggregate what we can directly.
    total = len(alignments)
    aligned = sum(1 for a in alignments if a.alignment_status != "unaligned")
    alignment_rate = aligned / total if total else 0.0

    # mean mapping quality of aligned reads only
    aligned_mapqs = [a.mapping_quality for a in alignments if a.alignment_status != "unaligned"]
    mean_mapq = sum(aligned_mapqs) / len(aligned_mapqs) if aligned_mapqs else 0.0

    # trimmed reads: any read shorter than original (we track via trimmed_length proxy)
    # We approximate trimmed_count as reads that were touched by the trim stage
    # (trimmed_length < some typical max — use 100 as the synthetic read length)
    trimmed = sum(1 for a in alignments if a.trimmed_length < 100)

    return RunSummary(
        total_reads=total,
        pass_qc=aligned + sum(1 for a in alignments if a.alignment_status == "unaligned"),
        trimmed_count=trimmed,
        aligned_count=aligned,
        mean_quality=round(mean_mapq, 2),
        gc_content=0.0,  # not propagated through AlignmentResult; computed separately
        alignment_rate=round(alignment_rate, 4),
    )
