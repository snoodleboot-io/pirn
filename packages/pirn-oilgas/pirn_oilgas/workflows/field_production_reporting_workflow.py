"""``FieldProductionReportingWorkflow`` — SCADA rows -> validate -> KPI -> forecast.

Composition:
    SCADA assemble (oil, gas, water) -> production-test validation ->
    GOR / water-cut / decline-rate -> production forecast.

Algorithm:
    1. Receive a ``series`` tuple of :class:`ScadaSeriesSpec` (one entry
       labelled ``"oil"``, one ``"gas"``, one ``"water"``), the shared time
       parameters, and the KPI / forecast configuration.
    2. Key ``series`` by label, then validate that every label is present
       and every tag is a non-empty string in ``process()``.
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
from pirn_oilgas.types.scada_series_spec import ScadaSeriesSpec


class FieldProductionReportingWorkflow(SubTapestry):
    """Daily production-reporting pipeline for a single producer well."""

    def __init__(
        self,
        *,
        series: Knot | tuple[ScadaSeriesSpec, ...],
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
            series=series,
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
        series: tuple[ScadaSeriesSpec, ...],
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
            series: Tuple of :class:`ScadaSeriesSpec`, one each labelled
                ``"oil"``, ``"gas"``, and ``"water"``.
            since: Start datetime for SCADA history pull.
            sample_interval_sec: Positive sample interval in seconds.
            forecast_months: Positive number of months to forecast.
            max_oil_rate_bopd: Positive maximum allowable oil rate in BOPD.
            max_gas_rate_mscfd: Positive maximum allowable gas rate in MSCFD.
            max_water_rate_bwpd: Positive maximum allowable water rate in BWPD.
            decline_window_days: Positive rolling window for decline estimation in days.

        Returns:
            Terminal knot of the inner pipeline (``ProductionForecaster``).

        Raises:
            TypeError: If ``series`` is not a tuple of :class:`ScadaSeriesSpec`.
            ValueError: If ``series`` is missing the ``"oil"``, ``"gas"``, or
                ``"water"`` label, or a series tag is empty.
        """
        by_label = self._series_by_label(series)
        assemblers: dict[str, ScadaDatabaseAssembler] = {}
        for label, spec in by_label.items():
            row_param = Parameter(
                f"{label}_rows",
                list,
                default=spec.rows,
                _config=KnotConfig(id=f"{label}_rows"),
            )
            assemblers[label] = ScadaDatabaseAssembler(
                rows=row_param,
                tag=spec.tag,
                since=since,
                sample_interval_sec=sample_interval_sec,
                _config=KnotConfig(id=f"{label}_assemble"),
            )
        oil, gas, water = assemblers["oil"], assemblers["gas"], assemblers["water"]
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

    @staticmethod
    def _series_by_label(series: tuple[ScadaSeriesSpec, ...]) -> dict[str, ScadaSeriesSpec]:
        """Validate ``series`` and key it by label.

        Raises:
            TypeError: If ``series`` is not a tuple of :class:`ScadaSeriesSpec`.
            ValueError: If the ``"oil"``, ``"gas"``, or ``"water"`` label is
                missing, or a series tag is empty.
        """
        if not isinstance(series, tuple) or not all(
            isinstance(spec, ScadaSeriesSpec) for spec in series
        ):
            raise TypeError(
                "FieldProductionReportingWorkflow: series must be a tuple of ScadaSeriesSpec"
            )
        by_label = {spec.label: spec for spec in series}
        missing = {"oil", "gas", "water"} - by_label.keys()
        if missing:
            raise ValueError(
                f"FieldProductionReportingWorkflow: series is missing labels {sorted(missing)}"
            )
        for label, spec in by_label.items():
            if not spec.tag:
                raise ValueError(
                    f"FieldProductionReportingWorkflow: {label} series tag must be a non-empty string"
                )
        return by_label
