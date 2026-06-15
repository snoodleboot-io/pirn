"""``FieldProductionReportingWorkflow`` — SCADA rows -> validate -> KPI -> forecast.

Composition:
    SCADA assemble (oil, gas, water) -> production-test validation ->
    GOR / water-cut / decline-rate -> production forecast.

Algorithm:
    1. Receive historian query rows for oil, gas, and water rates, SCADA tags
       and time parameters, and KPI / forecast configuration.
    2. Validate all string and numeric inputs in ``process()``.
    3. Build the inner pipeline inside ``process()``:
       - ``ScadaDatabaseAssembler`` (x3) for oil, gas, and water rates,
       - ``ProductionTestValidator`` for rate QC,
       - ``GasOilRatioCalculator``, ``WaterCutTracker``, ``DeclineRateEstimator``,
       - ``DeclineCurveAnalyzer`` and ``ProductionForecaster``.
    4. Return the terminal knot; the base class runs the inner tapestry.


References:
    - API RP 44 (2nd ed., 2015) — Recommended Practice for Sampling
      Petroleum Reservoir Fluids (production rate QC context).
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160,
      228-247. SPE-945228-G.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_oilgas.assemblers.scada_database_assembler import ScadaDatabaseAssembler
from pirn_oilgas.production.decline_rate_estimator import DeclineRateEstimator
from pirn_oilgas.production.gas_oil_ratio_calculator import (
    GasOilRatioCalculator,
)
from pirn_oilgas.production.production_forecaster import ProductionForecaster
from pirn_oilgas.production.production_test_validator import (
    ProductionTestValidator,
)
from pirn_oilgas.production.water_cut_tracker import WaterCutTracker
from pirn_oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer


class FieldProductionReportingWorkflow(SubTapestry):
    """Daily production-reporting pipeline for a single producer well."""

    def __init__(
        self,
        *,
        oil_rows: Knot,
        gas_rows: Knot,
        water_rows: Knot,
        oil_tag: Knot | str,
        gas_tag: Knot | str,
        water_tag: Knot | str,
        since: Knot | datetime,
        sample_interval_sec: Knot | float,
        forecast_months: Knot | int,
        max_oil_rate_bopd: Knot | float,
        max_gas_rate_mscfd: Knot | float,
        max_water_rate_bwpd: Knot | float,
        decline_window_days: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            oil_rows=oil_rows,
            gas_rows=gas_rows,
            water_rows=water_rows,
            oil_tag=oil_tag,
            gas_tag=gas_tag,
            water_tag=water_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            forecast_months=forecast_months,
            max_oil_rate_bopd=max_oil_rate_bopd,
            max_gas_rate_mscfd=max_gas_rate_mscfd,
            max_water_rate_bwpd=max_water_rate_bwpd,
            decline_window_days=decline_window_days,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        oil_rows: list[tuple[Any, ...]],
        gas_rows: list[tuple[Any, ...]],
        water_rows: list[tuple[Any, ...]],
        oil_tag: str,
        gas_tag: str,
        water_tag: str,
        since: datetime,
        sample_interval_sec: float,
        forecast_months: int,
        max_oil_rate_bopd: float,
        max_gas_rate_mscfd: float,
        max_water_rate_bwpd: float,
        decline_window_days: int,
        **_: Any,
    ) -> Any:
        """Build the SCADA ingest-to-forecast inner pipeline and return its terminal knot.

        Args:
            oil_rows: Historian query rows for oil rate — list of ``(timestamp, value)`` tuples.
            gas_rows: Historian query rows for gas rate.
            water_rows: Historian query rows for water rate.
            oil_tag: Non-empty SCADA tag name for oil rate.
            gas_tag: Non-empty SCADA tag name for gas rate.
            water_tag: Non-empty SCADA tag name for water rate.
            since: Start datetime for SCADA history pull.
            sample_interval_sec: Positive sample interval in seconds.
            forecast_months: Positive number of months to forecast.
            max_oil_rate_bopd: Positive maximum allowable oil rate in BOPD.
            max_gas_rate_mscfd: Positive maximum allowable gas rate in MSCFD.
            max_water_rate_bwpd: Positive maximum allowable water rate in BWPD.
            decline_window_days: Positive rolling window for decline estimation in days.

        Returns:
            Terminal knot of the inner pipeline (``ProductionForecaster``).
        """
        for label, tag in (
            ("oil_tag", oil_tag),
            ("gas_tag", gas_tag),
            ("water_tag", water_tag),
        ):
            if not isinstance(tag, str) or not tag:
                raise ValueError(
                    f"FieldProductionReportingWorkflow: {label} must be a non-empty string"
                )
        oil_param = Parameter("oil_rows", list, default=oil_rows, _config=KnotConfig(id="oil_rows"))
        gas_param = Parameter("gas_rows", list, default=gas_rows, _config=KnotConfig(id="gas_rows"))
        water_param = Parameter(
            "water_rows", list, default=water_rows, _config=KnotConfig(id="water_rows")
        )
        oil = ScadaDatabaseAssembler(
            rows=oil_param,
            tag=oil_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=KnotConfig(id="oil_assemble"),
        )
        gas = ScadaDatabaseAssembler(
            rows=gas_param,
            tag=gas_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=KnotConfig(id="gas_assemble"),
        )
        water = ScadaDatabaseAssembler(
            rows=water_param,
            tag=water_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=KnotConfig(id="water_assemble"),
        )
        ProductionTestValidator(
            series=oil,
            max_oil_rate_bopd=max_oil_rate_bopd,
            max_gas_rate_mscfd=max_gas_rate_mscfd,
            max_water_rate_bwpd=max_water_rate_bwpd,
            _config=KnotConfig(id="validate"),
        )
        GasOilRatioCalculator(
            oil_rate=oil,
            gas_rate=gas,
            _config=KnotConfig(id="gor"),
        )
        WaterCutTracker(
            oil_rate=oil,
            water_rate=water,
            _config=KnotConfig(id="water_cut"),
        )
        DeclineRateEstimator(
            rate_series=oil,
            window_days=decline_window_days,
            _config=KnotConfig(id="decline_rate"),
        )
        decline = DeclineCurveAnalyzer(
            rate_series=oil,
            method="hyperbolic",
            _config=KnotConfig(id="decline_curve"),
        )
        return ProductionForecaster(
            decline_parameters=decline,
            forecast_months=forecast_months,
            _config=KnotConfig(id="forecast"),
        )
