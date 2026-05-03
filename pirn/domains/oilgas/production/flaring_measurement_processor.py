"""``FlaringMeasurementProcessor`` — process flaring measurement data to compute total gas flared and emissions."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FlaringMeasurementProcessor(Knot):
    """Compute total gas flared and CO2 emissions from flaring measurement records."""

    def __init__(
        self,
        *,
        measurements: Knot,
        gas_composition: dict[str, float],
        efficiency_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(gas_composition, dict):
            raise TypeError(
                "FlaringMeasurementProcessor: gas_composition must be a dict"
            )
        if not isinstance(efficiency_factor, (int, float)):
            raise TypeError(
                "FlaringMeasurementProcessor: efficiency_factor must be numeric"
            )
        if not (0 < efficiency_factor <= 1.0):
            raise ValueError(
                "FlaringMeasurementProcessor: efficiency_factor must be in (0, 1]"
            )
        self._gas_composition = gas_composition
        self._efficiency_factor = float(efficiency_factor)
        super().__init__(measurements=measurements, _config=_config, **kwargs)

    async def process(
        self, measurements: list[dict[str, Any]], **_: Any
    ) -> dict[str, Any]:
        """Process flaring measurement records to compute total flared volume and CO2 emissions.

        Args:
            measurements: List of dicts with ``start_iso``, ``end_iso``, and
                ``flow_rate_mmscfd`` for each flaring event.

        Returns:
            Dict with ``total_flared_mmscf`` (float), ``co2_tonnes`` (float),
            and ``event_count`` (int).
        """
        total_flared = 0.0
        for m in measurements:
            rate = float(m.get("flow_rate_mmscfd", 0.0))
            total_flared += rate
        co2_fraction = self._gas_composition.get("co2", 0.05)
        co2_tonnes = total_flared * co2_fraction * self._efficiency_factor * 53.07
        return {
            "total_flared_mmscf": total_flared,
            "co2_tonnes": co2_tonnes,
            "event_count": len(measurements),
        }
