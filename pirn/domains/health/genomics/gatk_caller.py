"""``GATKCaller`` — GATK HaplotypeCaller variant caller.

Production version invokes the GATK CLI in safe mode; this stub
validates inputs and returns a VCF path.

Algorithm:
    1. Receive bam_path, reference_path, and output_vcf_path strings.
    2. Validate that all paths are non-empty strings.
    3. Run GATK HaplotypeCaller in GVCF mode against the reference.
    4. Genotype the GVCF to produce a final VCF at output_vcf_path.
    5. Return the output VCF path.


References:
    - GATK: https://gatk.broadinstitute.org/
    - McKenna et al. (2010) The Genome Analysis Toolkit.
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
        bam_path: Knot | str,
        reference_path: Knot | str,
        output_vcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam_path=bam_path,
            reference_path=reference_path,
            output_vcf_path=output_vcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam_path: str,
        reference_path: str,
        output_vcf_path: str,
        **_: Any,
    ) -> str:
        """Run GATK HaplotypeCaller on the BAM against the reference and return the output VCF path.

        Args:
            bam_path: Non-empty path to the input BAM file.
            reference_path: Non-empty path to the reference FASTA file.
            output_vcf_path: Non-empty path for the output VCF file.

        Returns:
            Path string for the output VCF file.

        Raises:
            TypeError: If any path is not a string.
            ValueError: If any path is empty.
        """
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"GATKCaller: {label} must be a string")
            if not value:
                raise ValueError(f"GATKCaller: {label} must be non-empty")
        return output_vcf_path
