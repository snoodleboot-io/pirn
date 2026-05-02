"""``SnpEffAnnotator`` — SnpEff variant-effect annotator.

Production version invokes ``snpEff`` via subprocess; this stub
validates inputs and returns an annotated VCF path.
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
        vcf_path: str,
        genome_db: str,
        output_vcf_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("vcf_path", vcf_path),
            ("genome_db", genome_db),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"SnpEffAnnotator: {label} must be a string")
            if not value:
                raise ValueError(f"SnpEffAnnotator: {label} must be non-empty")
        self._vcf_path = vcf_path
        self._genome_db = genome_db
        self._output_vcf_path = output_vcf_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_vcf_path
