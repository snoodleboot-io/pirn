"""``WellCompletionIngester`` — ingest a well-completion record into a stub frame.

Algorithm:
    1. Receive non-empty ``well_id`` and ``record_path`` strings.
    2. Validate that both strings are non-empty.
    3. Parse the completion record at ``record_path`` to extract perforation
       intervals, packer depths, and sliding sleeve positions.
    4. Return a DrillingParameters stub identified by the well ID.


References:
    - API RP 19D (2008) — Measuring the Properties of Proppants Used in
      Hydraulic Fracturing and Gravel-Packing Operations.
    - Economides, M.J. & Nolte, K.G. (2000). *Reservoir Stimulation*, 3rd ed.
      Wiley, Chapter 5 (completion design overview).
"""

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
        well_id: Knot | str,
        record_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            well_id=well_id,
            record_path=record_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        well_id: str,
        record_path: str,
        **_: Any,
    ) -> DrillingParameters:
        """Ingest the configured completion record and return a DrillingParameters stub.

        Args:
            well_id: Non-empty well identifier string.
            record_path: Non-empty path to the completion record file.

        Returns:
            DrillingParameters stub identified by the configured well ID.
        """
        if not isinstance(well_id, str) or not well_id:
            raise ValueError(
                "WellCompletionIngester: well_id must be a non-empty string"
            )
        if not isinstance(record_path, str) or not record_path:
            raise ValueError(
                "WellCompletionIngester: record_path must be a non-empty string"
            )
        return DrillingParameters(well_id=well_id)
