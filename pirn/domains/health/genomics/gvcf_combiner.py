"""``GVCFCombiner`` — combine per-sample GVCFs into a multi-sample GVCF.

Production version uses ``GATK CombineGVCFs`` or
``bcftools merge --gvcf``; this stub validates inputs and returns the
output path.

Algorithm:
    1. Receive gvcf_paths sequence, reference_path, and output_gvcf_path strings.
    2. Validate gvcf_paths is a non-empty list/tuple of non-empty strings.
    3. Validate reference_path and output_gvcf_path are non-empty strings.
    4. Merge per-sample GVCF records across shared genomic sites.
    5. Return the path to the combined multi-sample GVCF.


References:
    - GATK CombineGVCFs: https://gatk.broadinstitute.org/hc/en-us/articles/360036883491
    - bcftools merge: https://samtools.github.io/bcftools/bcftools.html#merge
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GVCFCombiner(Knot):
    """Combine multiple GVCF paths into a single combined GVCF."""

    def __init__(
        self,
        *,
        gvcf_paths: Knot | Sequence[str],
        reference_path: Knot | str,
        output_gvcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gvcf_paths=gvcf_paths,
            reference_path=reference_path,
            output_gvcf_path=output_gvcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gvcf_paths: Sequence[str],
        reference_path: str,
        output_gvcf_path: str,
        **_: Any,
    ) -> str:
        """Merge the per-sample GVCFs against the reference and return the combined GVCF output path.

        Args:
            gvcf_paths: Non-empty list or tuple of non-empty GVCF file path strings.
            reference_path: Non-empty path to the reference FASTA file.
            output_gvcf_path: Non-empty path for the combined GVCF output file.

        Returns:
            Path string for the combined GVCF output file.

        Raises:
            TypeError: If gvcf_paths is not list/tuple.
            ValueError: If gvcf_paths is empty, contains empty strings, or reference/output paths are empty.
        """
        if not isinstance(gvcf_paths, (list, tuple)):
            raise TypeError("GVCFCombiner: gvcf_paths must be list/tuple")
        if not gvcf_paths:
            raise ValueError("GVCFCombiner: gvcf_paths must be non-empty")
        for path in gvcf_paths:
            if not isinstance(path, str) or not path:
                raise ValueError("GVCFCombiner: every gvcf path must be a non-empty string")
        for label, value in (
            ("reference_path", reference_path),
            ("output_gvcf_path", output_gvcf_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"GVCFCombiner: {label} must be a non-empty string")
        return output_gvcf_path
