"""``CmgSsfileParser`` — parse a CMG simulation SSFILE summary."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class CmgSsfileParser(Knot):
    """Parse a CMG SSFILE-style summary into a stubbed time-series reference."""

    def __init__(
        self,
        *,
        ssfile_path: str,
        vector_name: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(ssfile_path, str) or not ssfile_path:
            raise ValueError(
                "CmgSsfileParser: ssfile_path must be a non-empty string"
            )
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError(
                "CmgSsfileParser: vector_name must be a non-empty string"
            )
        self._ssfile_path = ssfile_path
        self._vector_name = vector_name
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        """Parse the configured CMG SSFILE path and return a ScadaTimeSeries reference for the named vector.

        Returns:
            ScadaTimeSeries keyed by ``cmg:{vector_name}``.
        """
        return ScadaTimeSeries(sensor_id=f"cmg:{self._vector_name}")
