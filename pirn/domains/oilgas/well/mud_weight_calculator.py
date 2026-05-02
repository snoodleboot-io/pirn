"""``MudWeightCalculator`` — recommend a mud-weight window for a depth interval."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters


class MudWeightCalculator(Knot):
    """Recommend a mud-weight window from pore- and fracture-pressure inputs."""

    def __init__(
        self,
        *,
        drilling: Knot,
        pore_pressure_ppg: float,
        fracture_pressure_ppg: float,
        safety_margin_ppg: float = 0.5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("pore_pressure_ppg", pore_pressure_ppg),
            ("fracture_pressure_ppg", fracture_pressure_ppg),
            ("safety_margin_ppg", safety_margin_ppg),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"MudWeightCalculator: {label} must be numeric"
                )
            if value < 0.0:
                raise ValueError(
                    f"MudWeightCalculator: {label} must be non-negative"
                )
        if fracture_pressure_ppg <= pore_pressure_ppg:
            raise ValueError(
                "MudWeightCalculator: fracture_pressure_ppg must exceed "
                "pore_pressure_ppg"
            )
        self._pore_pressure_ppg = float(pore_pressure_ppg)
        self._fracture_pressure_ppg = float(fracture_pressure_ppg)
        self._safety_margin_ppg = float(safety_margin_ppg)
        super().__init__(drilling=drilling, _config=_config, **kwargs)

    async def process(self, drilling: DrillingParameters, **_: Any) -> dict[str, float]:
        return {
            "min_ppg": self._pore_pressure_ppg + self._safety_margin_ppg,
            "max_ppg": self._fracture_pressure_ppg - self._safety_margin_ppg,
        }
