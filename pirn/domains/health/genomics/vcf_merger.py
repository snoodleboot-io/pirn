"""``VCFMerger`` — merge per-sample VCFs into a cohort VCF.

Production version uses ``bcftools merge`` or ``pysam`` to align
sites across samples; this stub validates inputs and returns the
target output path.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VCFMerger(Knot):
    """Merge multiple VCF paths into a single cohort VCF."""

    def __init__(
        self,
        *,
        vcf_paths: Sequence[str],
        output_vcf_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(vcf_paths, (list, tuple)):
            raise TypeError("VCFMerger: vcf_paths must be list/tuple")
        if not vcf_paths:
            raise ValueError("VCFMerger: vcf_paths must be non-empty")
        for path in vcf_paths:
            if not isinstance(path, str) or not path:
                raise ValueError(
                    "VCFMerger: every vcf path must be a non-empty string"
                )
        if not isinstance(output_vcf_path, str) or not output_vcf_path:
            raise ValueError(
                "VCFMerger: output_vcf_path must be a non-empty string"
            )
        self._vcf_paths = tuple(vcf_paths)
        self._output_vcf_path = output_vcf_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Merge the per-sample VCF paths into a cohort VCF and return the output path.

        Returns:
            Path string for the merged cohort VCF output file.
        """
        return self._output_vcf_path
