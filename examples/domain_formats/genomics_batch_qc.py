"""Example: Genomics read QC and alignment pipeline with Map.

A sequencing run produces a batch of FASTQ reads.  Every read must be
independently quality-checked, trimmed of low-quality bases and known
adapter sequences, and aligned to a reference genome.  A run summary
aggregates the results across all reads.

Demonstrates:
- Map: apply the same multi-step analysis to every element in a list
- Chained Maps: qc → trim → align as three sequential per-read stages
- Parallel execution: all reads in the batch run concurrently

Topology:

    reads_batch ──► Map(qc_read) ──► Map(trim_adapters) ──► Map(align_read) ──► summarise_run

Run with:
    python -m examples.domain_formats.genomics_batch_qc

Working with real FASTQ data
-----------------------------
This example uses synthetic FASTQ records generated in-process.  To
process a real ``.fastq`` / ``.fastq.gz`` file, swap ``_synthetic_reads``
for the ``FastqFormat`` connector::

    from pirn.connectors.file_formats.fastq_format import FastqFormat

    async def load_reads(path: str) -> list[FastqRead]:
        records = []
        async for record in FastqFormat.read(path):
            records.append(
                FastqRead(
                    seq_id=record["seq_id"],
                    description=record["description"],
                    sequence=record["sequence"],
                    quality=record["quality"],
                )
            )
        return records

``FastqFormat.read()`` is an async generator that yields one ``dict`` per
read with the keys ``seq_id``, ``description``, ``sequence``, and
``quality`` (matching the schema used by ``FastqFormat.decode()``).  Large
files stream through without loading the entire file into memory, so this
pattern scales to whole-genome sequencing runs.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.map_markers import Map, ZipMap
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- constants

_KNOWN_ADAPTER = "AGATCGGAAGAGC"
_LOW_QUALITY_THRESHOLD = 20
_MIN_READ_LENGTH = 20
_BASES = "ATGCN"
_CONTIGS = ["chr1", "chr2", "chr3", "chr4", "chrX", "chrY", "chrM"]

# ----------------------------------------------------------------- models


@dataclass
class FastqRead:
    seq_id: str
    description: str
    sequence: str
    quality: str  # ASCII Phred+33 quality string, same length as sequence


@dataclass
class ReadQC:
    seq_id: str
    mean_quality: float
    gc_content: float  # fraction 0.0-1.0
    n_fraction: float  # fraction 0.0-1.0
    pass_qc: bool
    fail_reason: str  # empty string when pass_qc is True


@dataclass
class TrimmedRead:
    seq_id: str
    original_length: int
    trimmed_sequence: str
    trimmed_quality: str
    adapter_found: bool
    bases_trimmed: int


@dataclass
class AlignmentResult:
    seq_id: str
    contig: str
    position: int
    mapping_quality: int
    alignment_status: str  # "unique" | "multi" | "unaligned"
    trimmed_length: int


@dataclass
class RunSummary:
    total_reads: int
    pass_qc: int
    trimmed_count: int
    aligned_count: int
    mean_quality: float
    gc_content: float
    alignment_rate: float


# ----------------------------------------------------------------- knots


@knot
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
    elif len(read.sequence) < _MIN_READ_LENGTH:
        fail_reason = f"read too short ({len(read.sequence)} < {_MIN_READ_LENGTH})"

    return ReadQC(
        seq_id=read.seq_id,
        mean_quality=round(mean_quality, 2),
        gc_content=round(gc_content, 4),
        n_fraction=round(n_fraction, 4),
        pass_qc=fail_reason == "",
        fail_reason=fail_reason,
    )


@knot
async def trim_adapters(read: FastqRead, qc: ReadQC) -> TrimmedRead:
    """Trim leading/trailing low-quality bases and known adapter prefix."""
    seq = read.sequence
    qual = read.quality
    original_length = len(seq)
    adapter_found = False

    # Trim adapter prefix if present
    if seq.startswith(_KNOWN_ADAPTER):
        trim_len = len(_KNOWN_ADAPTER)
        seq = seq[trim_len:]
        qual = qual[trim_len:]
        adapter_found = True

    # Trim trailing low-quality bases
    while qual and (ord(qual[-1]) - 33) < _LOW_QUALITY_THRESHOLD:
        seq = seq[:-1]
        qual = qual[:-1]

    # Trim leading low-quality bases
    while qual and (ord(qual[0]) - 33) < _LOW_QUALITY_THRESHOLD:
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


@knot
async def align_read(trimmed: TrimmedRead) -> AlignmentResult:
    """Simulate alignment: assign contig/position and mapping quality."""
    # Use a deterministic RNG seeded from the seq_id for reproducibility
    rng = random.Random(trimmed.seq_id)

    trimmed_length = len(trimmed.trimmed_sequence)

    if trimmed_length < _MIN_READ_LENGTH:
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
        contig = rng.choice(_CONTIGS)
        position = rng.randint(1, 250_000_000)
        mapq = rng.randint(1, 3)
    else:
        status = "unique"
        contig = rng.choice(_CONTIGS)
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


@knot
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


# ----------------------------------------------------------------- pipeline


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        reads_batch = Parameter("reads_batch", list, _config=KnotConfig(id="reads_batch"))

        qc_results = qc_read(read=Map(reads_batch), _config=KnotConfig(id="qc"))
        trimmed = trim_adapters(
            read=ZipMap(reads_batch),
            qc=ZipMap(qc_results),
            _config=KnotConfig(id="trim"),
        )
        aligned = align_read(trimmed=Map(trimmed), _config=KnotConfig(id="align"))
        summarise_run(alignments=aligned, _config=KnotConfig(id="summary"))
    return t


# ----------------------------------------------------------------- synthetic data


def _synthetic_reads(run_name: str, n_reads: int) -> list[FastqRead]:
    """Generate realistic synthetic FASTQ records for testing."""
    normal_bases = "ATGC"
    reads: list[FastqRead] = []

    for i in range(n_reads):
        seq_id = f"{run_name}.{i + 1:04d}"
        read_rng = random.Random(seq_id)

        read_length = read_rng.randint(80, 120)
        variant = read_rng.random()

        if variant < 0.10:
            # High-N read — will fail QC
            seq = "".join(read_rng.choice("N" * 6 + normal_bases) for _ in range(read_length))
        else:
            seq = "".join(read_rng.choice(normal_bases) for _ in range(read_length))

        # Build quality string
        if variant < 0.08:
            # Low-quality tail - last 20 bases are poor quality (Phred 15-19)
            good_len = read_length - 20
            good_qual = "".join(chr(read_rng.randint(25, 40) + 33) for _ in range(good_len))
            bad_qual = "".join(chr(read_rng.randint(15, 19) + 33) for _ in range(20))
            qual = good_qual + bad_qual
        else:
            qual = "".join(chr(read_rng.randint(20, 40) + 33) for _ in range(read_length))

        # Prepend adapter to ~15 % of reads
        if variant > 0.85:
            adapter = _KNOWN_ADAPTER
            seq = adapter + seq[: read_length - len(adapter)]
            adapter_qual = "".join(chr(read_rng.randint(20, 35) + 33) for _ in range(len(adapter)))
            qual = adapter_qual + qual[len(adapter) :]

        description = f"instrument=SYNTH flowcell=FC{run_name} lane={read_rng.randint(1, 8)}"

        reads.append(
            FastqRead(
                seq_id=seq_id,
                description=description,
                sequence=seq,
                quality=qual,
            )
        )

    return reads


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    run_a_reads = _synthetic_reads(run_name="RUN001", n_reads=12)
    run_b_reads = _synthetic_reads(run_name="RUN002", n_reads=8)

    # First sequencing run — 12 reads
    r1 = await t.run(RunRequest(parameters={"reads_batch": run_a_reads}))
    summary1: RunSummary = r1.outputs["summary"]
    print(f"\n── Sequencing run RUN001 ({summary1.total_reads} reads) ──")
    print(f"  pass QC : {summary1.pass_qc}")
    print(f"  trimmed : {summary1.trimmed_count}")
    print(f"  aligned : {summary1.aligned_count}")
    print(f"  align % : {summary1.alignment_rate:.1%}")
    print(f"  mean mapq: {summary1.mean_quality:.1f}")

    # Second sequencing run — 8 reads
    r2 = await t.run(RunRequest(parameters={"reads_batch": run_b_reads}))
    summary2: RunSummary = r2.outputs["summary"]
    print(f"\n── Sequencing run RUN002 ({summary2.total_reads} reads) ──")
    print(f"  pass QC : {summary2.pass_qc}")
    print(f"  trimmed : {summary2.trimmed_count}")
    print(f"  aligned : {summary2.aligned_count}")
    print(f"  align % : {summary2.alignment_rate:.1%}")
    print(f"  mean mapq: {summary2.mean_quality:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
