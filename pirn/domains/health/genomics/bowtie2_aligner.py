"""``Bowtie2Aligner`` — Bowtie2 read aligner.

Production version invokes ``bowtie2`` via subprocess with sanitised
argv. This stub validates inputs and returns a placeholder BAM path.

Algorithm:
    1. Receive fastq_path, index_prefix, and output_bam_path strings.
    2. Validate that all paths are non-empty strings.
    3. Run bowtie2 to align FASTQ reads to the reference index.
    4. Convert SAM output to BAM and write to output_bam_path.
    5. Return the output BAM path.


References:
    - Bowtie2: https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml
    - Langmead & Salzberg (2012) Fast gapped-read alignment with Bowtie 2.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class Bowtie2Aligner(Knot):
    """Align reads with Bowtie2 and emit a BAM path."""

    def __init__(
        self,
        *,
        fastq_path: Knot | str,
        index_prefix: Knot | str,
        output_bam_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fastq_path=fastq_path,
            index_prefix=index_prefix,
            output_bam_path=output_bam_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fastq_path: str,
        index_prefix: str,
        output_bam_path: str,
        **_: Any,
    ) -> str:
        """Align the FASTQ reads to the Bowtie2 index and return the output BAM path.

        Args:
            fastq_path: Non-empty path to the input FASTQ file.
            index_prefix: Non-empty path prefix for the Bowtie2 index.
            output_bam_path: Non-empty path for the output BAM file.

        Returns:
            The output BAM path.

        Raises:
            TypeError: If any path is not a string.
            ValueError: If any path is empty.
        """
        for label, value in (
            ("fastq_path", fastq_path),
            ("index_prefix", index_prefix),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"Bowtie2Aligner: {label} must be a string")
            if not value:
                raise ValueError(f"Bowtie2Aligner: {label} must be non-empty")
        return output_bam_path
