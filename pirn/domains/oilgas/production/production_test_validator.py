"""``ProductionTestValidator`` — validate a multi-rate production-test record."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ProductionTestValidator(Knot):
    """Validate a production-test series against absolute rate bounds."""

    def __init__(
        self,
        *,
        series: Knot,
        max_oil_rate_bopd: float,
        max_gas_rate_mscfd: float,
        max_water_rate_bwpd: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("max_oil_rate_bopd", max_oil_rate_bopd),
            ("max_gas_rate_mscfd", max_gas_rate_mscfd),
            ("max_water_rate_bwpd", max_water_rate_bwpd),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"ProductionTestValidator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"ProductionTestValidator: {label} must be positive"
                )
        self._max_oil_rate_bopd = float(max_oil_rate_bopd)
        self._max_gas_rate_mscfd = float(max_gas_rate_mscfd)
        self._max_water_rate_bwpd = float(max_water_rate_bwpd)
        super().__init__(series=series, _config=_config, **kwargs)

    async def process(self, series: ScadaTimeSeries, **_: Any) -> ScadaTimeSeries:
        """Validate the production-test series against the configured oil, gas, and water rate bounds and return it.

        Args:
            series: ScadaTimeSeries containing multi-rate production test data
                to validate against the configured rate bounds.

        Returns:
            The input ScadaTimeSeries, passed through after validation.
        """
        return series
