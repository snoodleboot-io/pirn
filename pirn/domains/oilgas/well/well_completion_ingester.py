"""``WellCompletionIngester`` — ingest a well-completion record into a stub frame."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters


class WellCompletionIngester(Knot):
    """Ingest a well-completion record (perforations, packers, sliding sleeves)."""

    def __init__(
        self,
        *,
        well_id: str,
        record_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(well_id, str) or not well_id:
            raise ValueError(
                "WellCompletionIngester: well_id must be a non-empty string"
            )
        if not isinstance(record_path, str) or not record_path:
            raise ValueError(
                "WellCompletionIngester: record_path must be a non-empty string"
            )
        self._well_id = well_id
        self._record_path = record_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DrillingParameters:
        """Ingest the configured completion record and return a DrillingParameters stub.

        Returns:
            DrillingParameters stub identified by the configured well ID.
        """
        return DrillingParameters(well_id=self._well_id)
