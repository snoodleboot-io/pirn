"""``FieldProductionReportingWorkflow`` — SCADA -> validate -> KPI -> forecast.

Composition:
    SCADA ingest -> production-test validation -> GOR / water-cut /
    decline-rate -> production forecast.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.production.decline_rate_estimator import DeclineRateEstimator
from pirn.domains.oilgas.production.gas_oil_ratio_calculator import (
    GasOilRatioCalculator,
)
from pirn.domains.oilgas.production.production_forecaster import ProductionForecaster
from pirn.domains.oilgas.production.production_test_validator import (
    ProductionTestValidator,
)
from pirn.domains.oilgas.production.scada_historian_ingester import (
    ScadaHistorianIngester,
)
from pirn.domains.oilgas.production.water_cut_tracker import WaterCutTracker
from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection
from pirn.domains.oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class FieldProductionReportingWorkflow(SubTapestry):
    """Daily production-reporting pipeline for a single producer well."""

    def __init__(
        self,
        *,
        connection: HistorianConnection,
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
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(connection, HistorianConnection):
            raise TypeError(
                "FieldProductionReportingWorkflow: connection must be a HistorianConnection"
            )
        for label, tag in (
            ("oil_tag", oil_tag),
            ("gas_tag", gas_tag),
            ("water_tag", water_tag),
        ):
            if not isinstance(tag, str) or not tag:
                raise ValueError(
                    f"FieldProductionReportingWorkflow: {label} must be a non-empty string"
                )
        self._connection = connection
        self._oil_tag = oil_tag
        self._gas_tag = gas_tag
        self._water_tag = water_tag
        self._since = since
        self._sample_interval_sec = float(sample_interval_sec)
        self._forecast_months = int(forecast_months)
        self._max_oil_rate_bopd = float(max_oil_rate_bopd)
        self._max_gas_rate_mscfd = float(max_gas_rate_mscfd)
        self._max_water_rate_bwpd = float(max_water_rate_bwpd)
        self._decline_window_days = int(decline_window_days)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        """Build and execute the SCADA ingest-to-forecast inner tapestry and return its RunResult.

        Returns:
            RunResult from the inner pipeline spanning SCADA ingest through production forecast.
        """
        with Tapestry() as inner:
            oil = ScadaHistorianIngester(
                connection=self._connection,
                tag=self._oil_tag,
                since=self._since,
                sample_interval_sec=self._sample_interval_sec,
                _config=KnotConfig(id="oil_ingest"),
            )
            gas = ScadaHistorianIngester(
                connection=self._connection,
                tag=self._gas_tag,
                since=self._since,
                sample_interval_sec=self._sample_interval_sec,
                _config=KnotConfig(id="gas_ingest"),
            )
            water = ScadaHistorianIngester(
                connection=self._connection,
                tag=self._water_tag,
                since=self._since,
                sample_interval_sec=self._sample_interval_sec,
                _config=KnotConfig(id="water_ingest"),
            )
            ProductionTestValidator(
                series=oil,
                max_oil_rate_bopd=self._max_oil_rate_bopd,
                max_gas_rate_mscfd=self._max_gas_rate_mscfd,
                max_water_rate_bwpd=self._max_water_rate_bwpd,
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
                window_days=self._decline_window_days,
                _config=KnotConfig(id="decline_rate"),
            )
            decline = DeclineCurveAnalyzer(
                rate_series=oil,
                method="hyperbolic",
                _config=KnotConfig(id="decline_curve"),
            )
            ProductionForecaster(
                decline_parameters=decline,
                forecast_months=self._forecast_months,
                _config=KnotConfig(id="forecast"),
            )
        return await self._run_inner(inner)
