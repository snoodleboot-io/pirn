"""``VEPAnnotator`` — Ensembl Variant Effect Predictor annotator.

Production version invokes the VEP CLI or REST API; this stub
validates inputs and returns the annotated VCF path.
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
        vcf_path: str,
        cache_dir: str,
        output_vcf_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("vcf_path", vcf_path),
            ("cache_dir", cache_dir),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"VEPAnnotator: {label} must be a string")
            if not value:
                raise ValueError(f"VEPAnnotator: {label} must be non-empty")
        self._vcf_path = vcf_path
        self._cache_dir = cache_dir
        self._output_vcf_path = output_vcf_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_vcf_path
