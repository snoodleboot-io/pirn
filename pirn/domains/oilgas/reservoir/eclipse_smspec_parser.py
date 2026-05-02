"""``EclipseSmspecParser`` — parse an Eclipse SMSPEC summary file."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class EclipseSmspecParser(Knot):
    """Parse an Eclipse SMSPEC + UNSMRY pair into a stubbed time-series."""

    def __init__(
        self,
        *,
        smspec_path: str,
        vector_name: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(smspec_path, str) or not smspec_path:
            raise ValueError(
                "EclipseSmspecParser: smspec_path must be a non-empty string"
            )
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError(
                "EclipseSmspecParser: vector_name must be a non-empty string"
            )
        self._smspec_path = smspec_path
        self._vector_name = vector_name
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id=f"eclipse:{self._vector_name}")
