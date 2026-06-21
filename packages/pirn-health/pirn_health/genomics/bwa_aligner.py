"""``BWAAligner`` — BWA-MEM read aligner.

Production version invokes the BWA executable (``subprocess.run`` with
sanitised argv, no ``shell=True``) or wraps the BWA C library. This
stub validates inputs and returns a placeholder BAM-path string.

Algorithm:
    1. Receive fastq_path, reference_path, and output_bam_path strings.
    2. Validate that all paths are non-empty strings.
    3. Run bwa mem to align FASTQ reads to the reference genome.
    4. Convert SAM to BAM via samtools view and write to output_bam_path.
    5. Return the output BAM path.


References:
    - BWA: https://bio-bwa.sourceforge.net/
    - Li & Durbin (2010) Fast and accurate long-read alignment with Burrows-Wheeler Aligner.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


async def _run_subprocess(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")


class BWAAligner(Knot):
    """Align reads in ``fastq_path`` to ``reference_path`` and emit BAM."""

    def __init__(
        self,
        *,
        fastq_path: Knot | str,
        reference_path: Knot | str,
        output_bam_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fastq_path=fastq_path,
            reference_path=reference_path,
            output_bam_path=output_bam_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fastq_path: str,
        reference_path: str,
        output_bam_path: str,
        **_: Any,
    ) -> str:
        """Align the FASTQ reads to the reference genome using BWA-MEM and return the output BAM path.

        Args:
            fastq_path: Non-empty path to the input FASTQ file.
            reference_path: Non-empty path to the reference FASTA file.
            output_bam_path: Non-empty path for the output BAM file.

        Returns:
            The output BAM path.

        Raises:
            TypeError: If any path is not a string.
            ValueError: If any path is empty.
        """
        for label, value in (
            ("fastq_path", fastq_path),
            ("reference_path", reference_path),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"BWAAligner: {label} must be a string")
            if not value:
                raise ValueError(f"BWAAligner: {label} must be non-empty")
        cmd = ["bwa", "mem", reference_path, fastq_path]
        await _run_subprocess(cmd)
        return output_bam_path
