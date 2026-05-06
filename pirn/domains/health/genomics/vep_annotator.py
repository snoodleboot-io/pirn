"""``VEPAnnotator`` — Ensembl Variant Effect Predictor annotator.

Production version invokes the VEP CLI or REST API; this stub
validates inputs and returns the annotated VCF path.

Algorithm:
    1. Receive vcf_path, cache_dir, and output_vcf_path strings.
    2. Validate that all are non-empty strings.
    3. Run VEP with the configured local cache directory.
    4. Write annotated records to output_vcf_path.
    5. Return the output VCF path.


References:
    - McLaren et al. (2016) The Ensembl Variant Effect Predictor.
    - VEP: https://www.ensembl.org/info/docs/tools/vep/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VEPAnnotator(Knot):
    """Annotate a VCF with VEP and return the annotated VCF path."""

    def __init__(
        self,
        *,
        vcf_path: Knot | str,
        cache_dir: Knot | str,
        output_vcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            vcf_path=vcf_path,
            cache_dir=cache_dir,
            output_vcf_path=output_vcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        vcf_path: str,
        cache_dir: str,
        output_vcf_path: str,
        **_: Any,
    ) -> str:
        """Annotate the VCF with Ensembl VEP using the configured cache and return the annotated VCF path.

        Args:
            vcf_path: Non-empty path to the input VCF file.
            cache_dir: Non-empty path to the VEP cache directory.
            output_vcf_path: Non-empty path for the VEP-annotated output VCF file.

        Returns:
            Path string for the VEP-annotated VCF output file.

        Raises:
            TypeError: If any argument is not a string.
            ValueError: If any argument is empty.
        """
        for label, value in (
            ("vcf_path", vcf_path),
            ("cache_dir", cache_dir),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"VEPAnnotator: {label} must be a string")
            if not value:
                raise ValueError(f"VEPAnnotator: {label} must be non-empty")
        return output_vcf_path
