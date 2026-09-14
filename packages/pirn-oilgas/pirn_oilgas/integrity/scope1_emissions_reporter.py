"""``Scope1EmissionsReporter`` — aggregate Scope 1 GHG emissions from flaring, venting, and combustion.

Algorithm:
    1. Receive a list of upstream emission event dicts and ``co2_eq_factors``.
    2. For each event, retrieve ``gas_type``, ``volume_mcf``, and the
       CO2-equivalent factor for that gas type.
    3. Convert MCF to tonnes using an approximate density factor.
    4. Sum total CO2e and collect unique source types.
    5. Return total CO2e, event count, and source list.

Math:
    CO2-equivalent mass for one event:

    $$m_{\\text{CO2e}} = V_{\\text{MCF}} \\times f_{\\text{CO2e}} \\times \\rho_{\\text{MCF\\to t}}$$

    where :math:`V_{\\text{MCF}}` is volume in thousand cubic feet,
    :math:`f_{\\text{CO2e}}` is the global warming potential factor
    (e.g. 25 for CH4, 298 for N2O), and
    :math:`\\rho_{\\text{MCF\\to t}} \\approx 0.0192\\;\\text{t/MCF}` for methane
    at standard conditions.

References:
    - IPCC (2014). *Fifth Assessment Report*, Working Group I, Annex II
      (GWP values for GHGs).
    - EPA 40 CFR Part 98, Subpart W — Petroleum and Natural Gas Systems.
    - GHG Protocol Corporate Standard (WRI/WBCSD, 2015), Chapter 5.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class Scope1EmissionsReporter(Knot):
    """Aggregate Scope 1 GHG emissions from upstream event records."""

    def __init__(
        self,
        *,
        events: Knot,
        co2_eq_factors: Knot | dict[str, float] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            events=events,
            co2_eq_factors=co2_eq_factors,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        events: list[dict[str, Any]],
        co2_eq_factors: dict[str, float] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Aggregate GHG emissions from event records and return total CO2-equivalent.

        Args:
            events: List of event dicts, each with ``source_type`` (str),
                ``volume_mcf`` (float), and ``gas_type`` (str).
            co2_eq_factors: Optional dict mapping gas type to CO2-equivalent
                factor. Defaults to ``{"ch4": 25.0, "n2o": 298.0, "co2": 1.0}``.

        Returns:
            Dict with ``total_co2e_tonnes`` (float), ``event_count`` (int),
            and ``sources`` (list of str).
        """
        if co2_eq_factors is None:
            co2_eq_factors = {"ch4": 25.0, "n2o": 298.0, "co2": 1.0}
        if not isinstance(co2_eq_factors, dict):
            raise TypeError("Scope1EmissionsReporter: co2_eq_factors must be a dict")
        total_co2e = 0.0
        sources: list[str] = []
        for event in events:
            gas_type: str = event.get("gas_type", "co2")
            volume_mcf: float = float(event.get("volume_mcf", 0.0))
            factor: float = co2_eq_factors.get(gas_type, 1.0)
            total_co2e += volume_mcf * factor * 0.0192
            src = event.get("source_type", "unknown")
            if src not in sources:
                sources.append(src)
        return {
            "total_co2e_tonnes": total_co2e,
            "event_count": len(events),
            "sources": sources,
        }
