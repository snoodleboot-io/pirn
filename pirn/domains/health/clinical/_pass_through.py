"""Identity knot used to thread a tuple through subsequent filters."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class _PassThrough(Knot):
    """Identity knot used to thread a tuple through subsequent filters."""

    def __init__(
        self,
        *,
        records: tuple[ClinicalRecord, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self, records: tuple[ClinicalRecord, ...], **_: Any
    ) -> tuple[ClinicalRecord, ...]:
        return tuple(records)
