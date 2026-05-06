"""``CNVDetector`` — copy-number-variant detector.

Production version uses CNVkit / GATK gCNV; this stub returns an empty
tuple of CNV-call dicts so downstream knots see a typed input.

Algorithm:
    1. Receive bam_path, reference_path, and sample_id strings.
    2. Validate that all are non-empty strings.
    3. Compute read-depth coverage across genomic bins.
    4. Segment the coverage profile and call CNVs.
    5. Return a tuple of CNV-call dicts.


References:
    - CNVkit: https://cnvkit.readthedocs.io/
    - GATK gCNV: https://gatk.broadinstitute.org/hc/en-us/articles/360035890311
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CNVDetector(Knot):
    """Detect copy-number variants from a coverage track."""

    def __init__(
        self,
        *,
        bam_path: Knot | str,
        reference_path: Knot | str,
        sample_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam_path=bam_path,
            reference_path=reference_path,
            sample_id=sample_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam_path: str,
        reference_path: str,
        sample_id: str,
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Detect copy-number variants from the BAM coverage track and return a tuple of CNV-call dicts.

        Args:
            bam_path: Non-empty path to the input BAM file.
            reference_path: Non-empty path to the reference FASTA file.
            sample_id: Non-empty sample identifier string.

        Returns:
            A tuple of CNV-call dicts, each containing variant coordinates and copy-number estimates.

        Raises:
            ValueError: If any path or sample_id is empty.
        """
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("sample_id", sample_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"CNVDetector: {label} must be a non-empty string")
        return ()
