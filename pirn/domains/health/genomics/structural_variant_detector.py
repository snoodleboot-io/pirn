"""``StructuralVariantDetector`` — large structural-variant caller.

Production version uses Manta / Delly / GRIDSS; this stub validates
inputs and returns an empty tuple of SV-call dicts.

Algorithm:
    1. Receive bam_path, reference_path, and sample_id strings.
    2. Validate that all are non-empty strings.
    3. Compute discordant read pairs and split-read evidence.
    4. Segment and merge evidence into SV calls with breakpoint coordinates.
    5. Return a tuple of SV-call dicts.


References:
    - Chen et al. (2016) Manta: rapid detection of structural variants.
    - GRIDSS: https://github.com/PapenfussLab/gridss
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class StructuralVariantDetector(Knot):
    """Detect structural variants from BAM + reference."""

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
        """Detect large structural variants from the BAM against the reference and return a tuple of SV-call dicts.

        Args:
            bam_path: Non-empty path to the input BAM file.
            reference_path: Non-empty path to the reference FASTA file.
            sample_id: Non-empty sample identifier string.

        Returns:
            Tuple of SV-call dicts (empty at orchestration layer).

        Raises:
            ValueError: If any argument is empty or not a non-empty string.
        """
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("sample_id", sample_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"StructuralVariantDetector: {label} must be a non-empty string"
                )
        return ()
