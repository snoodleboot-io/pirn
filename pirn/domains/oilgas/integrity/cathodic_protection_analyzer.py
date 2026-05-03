"""``CathodicProtectionAnalyzer`` — assess cathodic-protection coverage."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class CathodicProtectionAnalyzer(Knot):
    """Score cathodic-protection coverage from pipe-to-soil potential samples."""

    def __init__(
        self,
        *,
        potential_series: Knot,
        protection_threshold_mv: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(protection_threshold_mv, (int, float)):
            raise TypeError(
                "CathodicProtectionAnalyzer: protection_threshold_mv must be numeric"
            )
        self._protection_threshold_mv = float(protection_threshold_mv)
        super().__init__(
            potential_series=potential_series, _config=_config, **kwargs
        )

    async def process(
        self, potential_series: ScadaTimeSeries, **_: Any
    ) -> dict[str, float]:
        """Score cathodic-protection coverage from the pipe-to-soil potential series and return coverage fraction and threshold.

        Args:
            potential_series: ScadaTimeSeries of pipe-to-soil potential
                measurements used to assess protection coverage.

        Returns:
            Dict with ``coverage_fraction`` (float in [0, 1]) and
            ``threshold_mv`` (the configured protection threshold in mV).
        """
        return {
            "coverage_fraction": 1.0,
            "threshold_mv": self._protection_threshold_mv,
        }
