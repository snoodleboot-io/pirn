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
    uv run python -m examples.domain_formats.genomics_batch_qc

Working with real FASTQ data
-----------------------------
This example uses synthetic FASTQ records generated in-process.  To
process a real ``.fastq`` / ``.fastq.gz`` file, swap
``GenomicsBatchQc._synthetic_reads`` for the ``FastqFormat`` connector::

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

import random
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.map import Map
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.zip_map import ZipMap
from pirn.tapestry import Tapestry

from examples.domain_formats.genomics_batch_qc.fastq_read import FastqRead
from examples.domain_formats.genomics_batch_qc.knots import (
    align_read,
    qc_read,
    summarise_run,
    trim_adapters,
)
from examples.domain_formats.genomics_batch_qc.run_summary import RunSummary
from examples.domain_formats.genomics_batch_qc.sequencing_config import SequencingConfig


class GenomicsBatchQc:
    """Builds and runs the per-read QC, trim and alignment tapestry for a run."""

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire reads_batch → Map(qc) → ZipMap(trim) → Map(align) → summary."""
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

    @staticmethod
    def _synthetic_reads(run_name: str, n_reads: int) -> list[FastqRead]:
        """Generate realistic synthetic FASTQ records for testing."""
        normal_bases = SequencingConfig.called_bases()
        reads: list[FastqRead] = []

        for i in range(n_reads):
            seq_id = f"{run_name}.{i + 1:04d}"
            read_rng = random.Random(seq_id)

            read_length = read_rng.randint(80, 120)
            variant = read_rng.random()

            if variant < 0.10:
                # High-N read — will fail QC
                seq = "".join(
                    read_rng.choice(SequencingConfig.no_call_base * 6 + normal_bases)
                    for _ in range(read_length)
                )
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
                adapter = SequencingConfig.known_adapter
                seq = adapter + seq[: read_length - len(adapter)]
                adapter_qual = "".join(
                    chr(read_rng.randint(20, 35) + 33) for _ in range(len(adapter))
                )
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

    @classmethod
    async def main(cls) -> None:
        """Run two sequencing batches through the tapestry and print their summaries."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        run_a_reads = cls._synthetic_reads(run_name="RUN001", n_reads=12)
        run_b_reads = cls._synthetic_reads(run_name="RUN002", n_reads=8)

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
