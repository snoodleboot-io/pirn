"""``FlaringMeasurementProcessor`` — process flaring measurement data to compute total gas flared and emissions.

Algorithm:
    1. Receive a list of flaring measurement records, a ``gas_composition`` dict,
       and an ``efficiency_factor`` in (0, 1].
    2. Validate that ``gas_composition`` is a dict and ``efficiency_factor`` is
       numeric and in (0, 1].
    3. Sum flow rates across all measurement intervals.
    4. Multiply by the CO2 fraction and efficiency factor to obtain CO2 tonnes.
    5. Return total flared volume, CO2 tonnes, and event count.

Math:
    Total CO2 emitted:

    $$m_{\\text{CO2}} = V_{\\text{total}} \\times x_{\\text{CO2}} \\times \\eta \\times \\rho_{\\text{CO2}}$$

    where :math:`V_{\\text{total}}` is total flared volume (MMSCF),
    :math:`x_{\\text{CO2}}` is the CO2 mole fraction in the flare gas,
    :math:`\\eta` is the combustion efficiency factor, and
    :math:`\\rho_{\\text{CO2}} \\approx 53.07\\;\\text{t/MMSCF}` is the CO2
    density at standard conditions.

References:
    - API MPMS Chapter 14.9 — Measurement of Natural Gas by Coriolis Meter.
    - EPA AP-42, Chapter 13.5 — Industrial Flares (combustion efficiency).
    - IPIECA (2012). *Flaring and Venting in the Oil and Gas Exploration and
      Production Industry*.
"""

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
        gas_composition: Knot,
        efficiency_factor: Knot | float,
        flow_rate_field: Knot | str = "flow_rate_mmscfd",
        co2_component: Knot | str = "co2",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            measurements=measurements,
            gas_composition=gas_composition,
            efficiency_factor=efficiency_factor,
            flow_rate_field=flow_rate_field,
            co2_component=co2_component,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        measurements: list[dict[str, Any]],
        gas_composition: dict[str, float],
        efficiency_factor: float,
        flow_rate_field: str = "flow_rate_mmscfd",
        co2_component: str = "co2",
        **_: Any,
    ) -> dict[str, Any]:
        """Process flaring measurement records to compute total flared volume and CO2 emissions.

        Args:
            measurements: List of flaring event dicts containing flow rate readings.
            gas_composition: Dict mapping gas component names to mole fractions.
            efficiency_factor: Combustion efficiency as a fraction in (0, 1].
            flow_rate_field: Historian tag name for flow rate (MMSCFD) in each measurement.
            co2_component: Key for CO2 mole fraction in gas_composition dict.

        Returns:
            Dict with ``total_flared_mmscf`` (float), ``co2_tonnes`` (float),
            and ``event_count`` (int).

        Raises:
            KeyError: If any measurement dict is missing the flow_rate_field key,
                or gas_composition is missing the co2_component key.
        """
        if not isinstance(gas_composition, dict):
            raise TypeError("FlaringMeasurementProcessor: gas_composition must be a dict")
        if not isinstance(efficiency_factor, (int, float)):
            raise TypeError("FlaringMeasurementProcessor: efficiency_factor must be numeric")
        if not (0 < efficiency_factor <= 1.0):
            raise ValueError("FlaringMeasurementProcessor: efficiency_factor must be in (0, 1]")
        if co2_component not in gas_composition:
            raise KeyError(
                f"FlaringMeasurementProcessor: gas_composition missing required component "
                f"'{co2_component}'; got: {list(gas_composition)}"
            )
        total_flared = 0.0
        for i, m in enumerate(measurements):
            if flow_rate_field not in m:
                raise KeyError(
                    f"FlaringMeasurementProcessor: measurement[{i}] missing required field "
                    f"'{flow_rate_field}'; got: {list(m)}"
                )
            total_flared += float(m[flow_rate_field])
        co2_fraction = gas_composition[co2_component]
        co2_tonnes = total_flared * co2_fraction * efficiency_factor * 53.07
        return {
            "total_flared_mmscf": total_flared,
            "co2_tonnes": co2_tonnes,
            "event_count": len(measurements),
        }
