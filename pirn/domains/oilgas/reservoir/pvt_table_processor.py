"""``PvtTableProcessor`` — assemble a :class:`PVTTable` from raw inputs.

Algorithm:
    1. Receive ``fluid_id``, ``pressure_count``, and ``temperature_count`` inputs.
    2. Validate all inputs: ``fluid_id`` is non-empty, both counts are positive integers.
    3. Build a pressure-temperature grid of size
       ``pressure_count x temperature_count``.
    4. Return a PVTTable reference.


References:
    - Standing, M.B. (1977). *Volumetric and Phase Behavior of Oil Field
      Hydrocarbon Systems*, 9th printing. SPE, Dallas (PVT correlation basis).
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Chapter 2 (PVT correlations).
"""

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
        fluid_id: Knot | str,
        pressure_count: Knot | int,
        temperature_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fluid_id=fluid_id,
            pressure_count=pressure_count,
            temperature_count=temperature_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fluid_id: str,
        pressure_count: int,
        temperature_count: int,
        **_: Any,
    ) -> PVTTable:
        """Assemble the PVT lookup table from the fluid and grid parameters and return a PVTTable reference.

        Args:
            fluid_id: Non-empty fluid identifier string.
            pressure_count: Positive number of pressure grid points.
            temperature_count: Positive number of temperature grid points.

        Returns:
            PVTTable built from the configured fluid ID and pressure/temperature
            grid sizes.
        """
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
        return PVTTable(
            fluid_id=fluid_id,
            pressure_count=pressure_count,
            temperature_count=temperature_count,
        )
