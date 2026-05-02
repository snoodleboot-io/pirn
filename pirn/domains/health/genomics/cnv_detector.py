"""``CNVDetector`` — copy-number-variant detector.

Production version uses CNVkit / GATK gCNV; this stub returns an empty
tuple of CNV-call dicts so downstream knots see a typed input.
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
                    f"CNVDetector: {label} must be a non-empty string"
                )
        self._bam_path = bam_path
        self._reference_path = reference_path
        self._sample_id = sample_id
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[Mapping[str, Any], ...]:
        return ()
