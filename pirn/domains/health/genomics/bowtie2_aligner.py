"""``Bowtie2Aligner`` — Bowtie2 read aligner.

Production version invokes ``bowtie2`` via subprocess with sanitised
argv. This stub validates inputs and returns a placeholder BAM path.
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
        fastq_path: str,
        index_prefix: str,
        output_bam_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("fastq_path", fastq_path),
            ("index_prefix", index_prefix),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"Bowtie2Aligner: {label} must be a string")
            if not value:
                raise ValueError(f"Bowtie2Aligner: {label} must be non-empty")
        self._fastq_path = fastq_path
        self._index_prefix = index_prefix
        self._output_bam_path = output_bam_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Align the FASTQ reads to the Bowtie2 index and return the output BAM path.

        Returns:
            The output BAM path.
        """
        return self._output_bam_path
