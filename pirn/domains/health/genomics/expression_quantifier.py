"""``ExpressionQuantifier`` — RNA-seq expression quantifier.

Production version uses Salmon / Kallisto / featureCounts. This stub
returns an empty mapping ``gene_id -> count`` so downstream knots see
a typed input.

Algorithm:
    1. Receive bam_path, annotation_path, and sample_id strings.
    2. Validate that all are non-empty strings.
    3. Load BAM alignments and gene annotation from annotation_path.
    4. Count reads overlapping each annotated gene region.
    5. Return a mapping of gene_id to raw read count.


References:
    - Salmon: https://combine-lab.github.io/salmon/
    - Liao et al. (2014) featureCounts: an efficient general purpose program for assigning reads to genomic features.
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
        bam_path: Knot | str,
        annotation_path: Knot | str,
        sample_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam_path=bam_path,
            annotation_path=annotation_path,
            sample_id=sample_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam_path: str,
        annotation_path: str,
        sample_id: str,
        **_: Any,
    ) -> Mapping[str, float]:
        """Quantify RNA-seq expression from the BAM and annotation and return a gene-id-to-count mapping.

        Args:
            bam_path: Non-empty path to the input BAM file.
            annotation_path: Non-empty path to the gene annotation file.
            sample_id: Non-empty sample identifier string.

        Returns:
            Mapping of gene_id to expression count (empty at orchestration layer).

        Raises:
            ValueError: If any argument is empty or not a non-empty string.
        """
        for label, value in (
            ("bam_path", bam_path),
            ("annotation_path", annotation_path),
            ("sample_id", sample_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ExpressionQuantifier: {label} must be a non-empty string"
                )
        return {}
