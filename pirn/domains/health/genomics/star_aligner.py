"""``STARAligner`` — STAR splice-aware aligner for RNA-seq.

Production version invokes the STAR executable; this stub validates
inputs and returns the requested BAM path.

Algorithm:
    1. Receive fastq_path, genome_dir, and output_bam_path strings.
    2. Validate that all are non-empty strings.
    3. Run STAR --runMode alignReads with the configured genome directory.
    4. Convert SAM output to sorted BAM at output_bam_path.
    5. Return the output BAM path.


References:
    - Dobin et al. (2013) STAR: ultrafast universal RNA-seq aligner.
    - STAR: https://github.com/alexdobin/STAR
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


class STARAligner(Knot):
    """Align RNA-seq reads with STAR and emit a BAM path."""

    def __init__(
        self,
        *,
        fastq_path: Knot | str,
        genome_dir: Knot | str,
        output_bam_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fastq_path=fastq_path,
            genome_dir=genome_dir,
            output_bam_path=output_bam_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fastq_path: str,
        genome_dir: str,
        output_bam_path: str,
        **_: Any,
    ) -> str:
        """Align RNA-seq reads with STAR using the configured genome directory and return the output BAM path.

        Args:
            fastq_path: Non-empty path to the input FASTQ file.
            genome_dir: Non-empty path to the STAR genome directory.
            output_bam_path: Non-empty path for the output BAM file.

        Returns:
            Path string for the aligned BAM output file.

        Raises:
            TypeError: If any argument is not a string.
            ValueError: If any argument is empty.
        """
        for label, value in (
            ("fastq_path", fastq_path),
            ("genome_dir", genome_dir),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"STARAligner: {label} must be a string")
            if not value:
                raise ValueError(f"STARAligner: {label} must be non-empty")
        cmd = [
            "STAR",
            "--runMode",
            "alignReads",
            "--genomeDir",
            genome_dir,
            "--readFilesIn",
            fastq_path,
            "--outSAMtype",
            "BAM",
            "SortedByCoordinate",
            "--outFileNamePrefix",
            output_bam_path.removesuffix(".bam"),
        ]
        await _run_subprocess(cmd)
        return output_bam_path
