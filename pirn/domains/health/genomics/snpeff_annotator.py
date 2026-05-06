"""``SnpEffAnnotator`` — SnpEff variant-effect annotator.

Production version invokes ``snpEff`` via subprocess; this stub
validates inputs and returns an annotated VCF path.

Algorithm:
    1. Receive vcf_path, genome_db, and output_vcf_path strings.
    2. Validate that all are non-empty strings.
    3. Run snpEff ann using the configured genome database.
    4. Write annotated records to output_vcf_path.
    5. Return the output VCF path.


References:
    - Cingolani et al. (2012) A program for annotating and predicting the effects of single nucleotide polymorphisms (SnpEff).
    - SnpEff: https://pcingola.github.io/SnpEff/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SnpEffAnnotator(Knot):
    """Annotate a VCF with SnpEff and return the annotated VCF path."""

    def __init__(
        self,
        *,
        vcf_path: Knot | str,
        genome_db: Knot | str,
        output_vcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            vcf_path=vcf_path,
            genome_db=genome_db,
            output_vcf_path=output_vcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        vcf_path: str,
        genome_db: str,
        output_vcf_path: str,
        **_: Any,
    ) -> str:
        """Annotate the VCF with SnpEff using the configured genome database and return the annotated VCF path.

        Args:
            vcf_path: Non-empty path to the input VCF file.
            genome_db: Non-empty SnpEff genome database identifier.
            output_vcf_path: Non-empty path for the annotated output VCF file.

        Returns:
            Path string for the SnpEff-annotated VCF output file.

        Raises:
            TypeError: If any argument is not a string.
            ValueError: If any argument is empty.
        """
        for label, value in (
            ("vcf_path", vcf_path),
            ("genome_db", genome_db),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"SnpEffAnnotator: {label} must be a string")
            if not value:
                raise ValueError(f"SnpEffAnnotator: {label} must be non-empty")
        return output_vcf_path
