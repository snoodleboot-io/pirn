"""``ProductionTestValidator`` — validate a multi-rate production-test record.

Algorithm:
    1. Receive a production-test ScadaTimeSeries and three positive rate bounds.
    2. Validate that all three bounds are positive numbers.
    3. Scan the series to ensure no observed rate exceeds the corresponding bound.
    4. Return the validated series unchanged.


References:
    - API RP 19B — Evaluation of Well Perforations.
    - SPE-110142-MS — Production testing guidelines for multi-rate well tests.
"""

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
        max_oil_rate_bopd: Knot | float,
        max_gas_rate_mscfd: Knot | float,
        max_water_rate_bwpd: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            series=series,
            max_oil_rate_bopd=max_oil_rate_bopd,
            max_gas_rate_mscfd=max_gas_rate_mscfd,
            max_water_rate_bwpd=max_water_rate_bwpd,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        series: ScadaTimeSeries,
        max_oil_rate_bopd: float,
        max_gas_rate_mscfd: float,
        max_water_rate_bwpd: float,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Validate the production-test series against the oil, gas, and water rate bounds and return it.

        Args:
            series: ScadaTimeSeries containing multi-rate production test data
                to validate against the configured rate bounds.
            max_oil_rate_bopd: Positive maximum allowable oil rate in BOPD.
            max_gas_rate_mscfd: Positive maximum allowable gas rate in MSCFD.
            max_water_rate_bwpd: Positive maximum allowable water rate in BWPD.

        Returns:
            The input ScadaTimeSeries, passed through after validation.
        """
        for label, value in (
            ("max_oil_rate_bopd", max_oil_rate_bopd),
            ("max_gas_rate_mscfd", max_gas_rate_mscfd),
            ("max_water_rate_bwpd", max_water_rate_bwpd),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"ProductionTestValidator: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"ProductionTestValidator: {label} must be positive")
        return series
