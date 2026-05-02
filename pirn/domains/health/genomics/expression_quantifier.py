"""``ExpressionQuantifier`` — RNA-seq expression quantifier.

Production version uses Salmon / Kallisto / featureCounts. This stub
returns an empty mapping ``gene_id -> count`` so downstream knots see
a typed input.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ExpressionQuantifier(Knot):
    """Quantify RNA-seq expression from a BAM and gene annotation."""

    def __init__(
        self,
        *,
        bam_path: str,
        annotation_path: str,
        sample_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("bam_path", bam_path),
            ("annotation_path", annotation_path),
            ("sample_id", sample_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ExpressionQuantifier: {label} must be a non-empty string"
                )
        self._bam_path = bam_path
        self._annotation_path = annotation_path
        self._sample_id = sample_id
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        return {}
