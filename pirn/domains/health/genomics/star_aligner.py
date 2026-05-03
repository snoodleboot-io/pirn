"""``STARAligner`` — STAR splice-aware aligner for RNA-seq.

Production version invokes the STAR executable; this stub validates
inputs and returns the requested BAM path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class STARAligner(Knot):
    """Align RNA-seq reads with STAR and emit a BAM path."""

    def __init__(
        self,
        *,
        fastq_path: str,
        genome_dir: str,
        output_bam_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("fastq_path", fastq_path),
            ("genome_dir", genome_dir),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"STARAligner: {label} must be a string")
            if not value:
                raise ValueError(f"STARAligner: {label} must be non-empty")
        self._fastq_path = fastq_path
        self._genome_dir = genome_dir
        self._output_bam_path = output_bam_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Align RNA-seq reads with STAR using the configured genome directory and return the output BAM path.

        Returns:
            Path string for the aligned BAM output file.
        """
        return self._output_bam_path
