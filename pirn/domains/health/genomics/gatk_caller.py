"""``GATKCaller`` — GATK HaplotypeCaller variant caller.

Production version invokes the GATK CLI in safe mode; this stub
validates inputs and returns a VCF path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GATKCaller(Knot):
    """Call variants with GATK HaplotypeCaller and return the VCF path."""

    def __init__(
        self,
        *,
        bam_path: str,
        reference_path: str,
        output_vcf_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"GATKCaller: {label} must be a string")
            if not value:
                raise ValueError(f"GATKCaller: {label} must be non-empty")
        self._bam_path = bam_path
        self._reference_path = reference_path
        self._output_vcf_path = output_vcf_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Run GATK HaplotypeCaller on the BAM against the reference and return the output VCF path.

        Returns:
            Path string for the output VCF file.
        """
        return self._output_vcf_path
