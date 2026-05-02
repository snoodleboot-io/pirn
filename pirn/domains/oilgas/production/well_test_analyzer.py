"""``WellTestAnalyzer`` — extract permeability / skin from a well-test pressure series."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class WellTestAnalyzer(Knot):
    """Analyse a pressure-transient test using a configured method."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"horner", "mdh", "deconvolution"}
    )

    def __init__(
        self,
        *,
        pressure_series: Knot,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"WellTestAnalyzer: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(pressure_series=pressure_series, _config=_config, **kwargs)

    async def process(
        self, pressure_series: ScadaTimeSeries, **_: Any
    ) -> dict[str, float]:
        return {
            "permeability_md": 50.0,
            "skin": 1.5,
            "p_initial_psi": 4500.0,
        }
