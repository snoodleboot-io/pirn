"""``StructuralVariantDetector`` — large structural-variant caller.

Production version uses Manta / Delly / GRIDSS; this stub validates
inputs and returns an empty tuple of SV-call dicts.
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
        bam_path: str,
        reference_path: str,
        sample_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("sample_id", sample_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"StructuralVariantDetector: {label} must be a non-empty string"
                )
        self._bam_path = bam_path
        self._reference_path = reference_path
        self._sample_id = sample_id
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[Mapping[str, Any], ...]:
        return ()
