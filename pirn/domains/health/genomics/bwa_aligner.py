"""``BWAAligner`` — BWA-MEM read aligner.

Production version invokes the BWA executable (``subprocess.run`` with
sanitised argv, no ``shell=True``) or wraps the BWA C library. This
stub validates inputs and returns a placeholder BAM-path string.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BWAAligner(Knot):
    """Align reads in ``fastq_path`` to ``reference_path`` and emit BAM."""

    def __init__(
        self,
        *,
        fastq_path: str,
        reference_path: str,
        output_bam_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("fastq_path", fastq_path),
            ("reference_path", reference_path),
            ("output_bam_path", output_bam_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"BWAAligner: {label} must be a string")
            if not value:
                raise ValueError(f"BWAAligner: {label} must be non-empty")
        self._fastq_path = fastq_path
        self._reference_path = reference_path
        self._output_bam_path = output_bam_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_bam_path
