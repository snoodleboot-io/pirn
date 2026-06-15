"""Identity knot used to thread a tuple through subsequent filters.

Algorithm:
    1. Receive a tuple of ClinicalRecord objects from an upstream Knot.
    2. Return the tuple unchanged.

"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_record import ClinicalRecord


class _PassThrough(Knot):
    """Identity knot used to thread a tuple through subsequent filters."""

    def __init__(
        self,
        *,
        records: Knot | tuple[ClinicalRecord, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self, records: tuple[ClinicalRecord, ...], **_: Any
    ) -> tuple[ClinicalRecord, ...]:
        """Return the input records tuple unchanged.

        Args:
            records: The upstream tuple of ClinicalRecords to pass through.

        Returns:
            The same tuple of ClinicalRecords, unchanged.
        """
        return tuple(records)
