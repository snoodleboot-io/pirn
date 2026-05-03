"""``PvtTableProcessor`` — assemble a :class:`PVTTable` from raw inputs."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.pvt_table import PVTTable


class PvtTableProcessor(Knot):
    """Build a PVT lookup-table reference from configured grid sizes."""

    def __init__(
        self,
        *,
        fluid_id: str,
        pressure_count: int,
        temperature_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(fluid_id, str) or not fluid_id:
            raise ValueError(
                "PvtTableProcessor: fluid_id must be a non-empty string"
            )
        for label, value in (
            ("pressure_count", pressure_count),
            ("temperature_count", temperature_count),
        ):
            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"PvtTableProcessor: {label} must be a positive integer"
                )
        self._fluid_id = fluid_id
        self._pressure_count = pressure_count
        self._temperature_count = temperature_count
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> PVTTable:
        """Assemble the PVT lookup table from the configured fluid and grid parameters and return a PVTTable reference.

        Returns:
            PVTTable built from the configured fluid ID and pressure/temperature grid sizes.
        """
        return PVTTable(
            fluid_id=self._fluid_id,
            pressure_count=self._pressure_count,
            temperature_count=self._temperature_count,
        )
