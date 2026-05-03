"""``Scope1EmissionsReporter`` — aggregate Scope 1 GHG emissions from flaring, venting, and combustion."""

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
        co2_eq_factors: dict[str, float] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if co2_eq_factors is None:
            co2_eq_factors = {"ch4": 25.0, "n2o": 298.0, "co2": 1.0}
        if not isinstance(co2_eq_factors, dict):
            raise TypeError(
                "Scope1EmissionsReporter: co2_eq_factors must be a dict"
            )
        self._co2_eq_factors = co2_eq_factors
        super().__init__(events=events, _config=_config, **kwargs)

    async def process(
        self, events: list[dict[str, Any]], **_: Any
    ) -> dict[str, Any]:
        """Aggregate GHG emissions from event records and return total CO2-equivalent.

        Args:
            events: List of event dicts, each with ``source_type`` (str),
                ``volume_mcf`` (float), and ``gas_type`` (str).

        Returns:
            Dict with ``total_co2e_tonnes`` (float), ``event_count`` (int),
            and ``sources`` (list of str).
        """
        total_co2e = 0.0
        sources: list[str] = []
        for event in events:
            gas_type: str = event.get("gas_type", "co2")
            volume_mcf: float = float(event.get("volume_mcf", 0.0))
            factor: float = self._co2_eq_factors.get(gas_type, 1.0)
            # Convert MCF to tonnes: approximate density factor
            total_co2e += volume_mcf * factor * 0.0192
            src = event.get("source_type", "unknown")
            if src not in sources:
                sources.append(src)
        return {
            "total_co2e_tonnes": total_co2e,
            "event_count": len(events),
            "sources": sources,
        }
