"""``FieldProductionReportingWorkflow`` — SCADA rows -> validate -> KPI -> forecast.

Composition:
    SCADA assemble (oil, gas, water) -> production-test validation ->
    GOR / water-cut / decline-rate -> production forecast.

Algorithm:
    1. Receive either a ``series`` tuple of :class:`ScadaSeriesSpec` (one
       entry labelled ``"oil"``, one ``"gas"``, one ``"water"``) or the
       legacy ``oil_rows``/``gas_rows``/``water_rows`` +
       ``oil_tag``/``gas_tag``/``water_tag`` keyword groups, plus shared
       SCADA tags and time parameters and KPI / forecast configuration.
    2. Resolve exactly one of the two input shapes into a per-label mapping
       of :class:`ScadaSeriesSpec`, then validate all string and numeric
       inputs in ``process()``.
    3. Build the inner pipeline inside ``process()``:
       - ``ScadaDatabaseAssembler`` (x3) for oil, gas, and water rates,
       - ``ProductionTestValidator`` for rate QC,
       - ``GasOilRatioCalculator``, ``WaterCutTracker``, ``DeclineRateEstimator``,
       - ``DeclineCurveAnalyzer`` and ``ProductionForecaster``.
    4. Return the terminal knot; the base class runs the inner tapestry.

Note:
    The ``oil_rows``/``gas_rows``/``water_rows``/``oil_tag``/``gas_tag``/
    ``water_tag`` keywords are kept working for one deprecation cycle
    alongside the new ``series`` input (PIR-856). Pass exactly one of the
    two shapes; passing both, or neither, raises ``ValueError``. New callers
    should prefer ``series``.

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
        oil_rows: Knot | None = None,
        gas_rows: Knot | None = None,
        water_rows: Knot | None = None,
        oil_tag: Knot | str | None = None,
        gas_tag: Knot | str | None = None,
        water_tag: Knot | str | None = None,
        series: Knot | tuple[ScadaSeriesSpec, ...] | None = None,
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
        oil_rows: list[tuple[Any, ...]] | None,
        gas_rows: list[tuple[Any, ...]] | None,
        water_rows: list[tuple[Any, ...]] | None,
        oil_tag: str | None,
        gas_tag: str | None,
        water_tag: str | None,
        since: datetime,
        sample_interval_sec: float,
        forecast_months: int,
        max_oil_rate_bopd: float,
        max_gas_rate_mscfd: float,
        max_water_rate_bwpd: float,
        decline_window_days: int,
        series: tuple[ScadaSeriesSpec, ...] | None = None,
        **_: Any,
    ) -> Any:
        """Build the SCADA ingest-to-forecast inner pipeline and return its terminal knot.

        Args:
            oil_rows: Legacy: historian query rows for oil rate — list of
                ``(timestamp, value)`` tuples. Deprecated alongside ``series``.
            gas_rows: Legacy: historian query rows for gas rate.
            water_rows: Legacy: historian query rows for water rate.
            oil_tag: Legacy: non-empty SCADA tag name for oil rate.
            gas_tag: Legacy: non-empty SCADA tag name for gas rate.
            water_tag: Legacy: non-empty SCADA tag name for water rate.
            since: Start datetime for SCADA history pull.
            sample_interval_sec: Positive sample interval in seconds.
            forecast_months: Positive number of months to forecast.
            max_oil_rate_bopd: Positive maximum allowable oil rate in BOPD.
            max_gas_rate_mscfd: Positive maximum allowable gas rate in MSCFD.
            max_water_rate_bwpd: Positive maximum allowable water rate in BWPD.
            decline_window_days: Positive rolling window for decline estimation in days.
            series: Preferred: tuple of :class:`ScadaSeriesSpec`, one each
                labelled ``"oil"``, ``"gas"``, and ``"water"``. Mutually
                exclusive with the legacy ``*_rows``/``*_tag`` keywords.

        Returns:
            Terminal knot of the inner pipeline (``ProductionForecaster``).
        """
        by_label = self._resolve_series(
            oil_rows=oil_rows,
            gas_rows=gas_rows,
            water_rows=water_rows,
            oil_tag=oil_tag,
            gas_tag=gas_tag,
            water_tag=water_tag,
            series=series,
        )
        for label, spec in by_label.items():
            if not isinstance(spec.tag, str) or not spec.tag:
                raise ValueError(
                    f"FieldProductionReportingWorkflow: {label}_tag must be a non-empty string"
                )
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
    def _resolve_series(
        *,
        oil_rows: list[tuple[Any, ...]] | None,
        gas_rows: list[tuple[Any, ...]] | None,
        water_rows: list[tuple[Any, ...]] | None,
        oil_tag: str | None,
        gas_tag: str | None,
        water_tag: str | None,
        series: tuple[ScadaSeriesSpec, ...] | None,
    ) -> dict[str, ScadaSeriesSpec]:
        """Resolve the legacy keywords or ``series`` into a per-label spec mapping.

        Exactly one of the two input shapes must be supplied: the legacy
        ``oil_rows``/``gas_rows``/``water_rows`` + ``oil_tag``/``gas_tag``/
        ``water_tag`` keywords, or ``series``.

        Raises:
            ValueError: If both shapes, or neither shape, are supplied; if
                ``series`` is missing the ``"oil"``, ``"gas"``, or ``"water"``
                label; or if a legacy keyword is only partially supplied.
        """
        legacy_values = (oil_rows, gas_rows, water_rows, oil_tag, gas_tag, water_tag)
        legacy_given = any(value is not None for value in legacy_values)
        if series is not None and legacy_given:
            raise ValueError(
                "FieldProductionReportingWorkflow: pass either 'series' or the legacy "
                "oil_rows/gas_rows/water_rows/oil_tag/gas_tag/water_tag keywords, not both"
            )
        if series is not None:
            by_label = {spec.label: spec for spec in series}
            missing = {"oil", "gas", "water"} - by_label.keys()
            if missing:
                raise ValueError(
                    f"FieldProductionReportingWorkflow: series is missing labels {sorted(missing)}"
                )
            return by_label
        if not legacy_given:
            raise ValueError(
                "FieldProductionReportingWorkflow: must supply 'series' or the legacy "
                "oil_rows/gas_rows/water_rows/oil_tag/gas_tag/water_tag keywords"
            )
        missing_legacy = [
            name
            for name, value in (
                ("oil_rows", oil_rows),
                ("gas_rows", gas_rows),
                ("water_rows", water_rows),
                ("oil_tag", oil_tag),
                ("gas_tag", gas_tag),
                ("water_tag", water_tag),
            )
            if value is None
        ]
        if missing_legacy:
            raise ValueError(
                f"FieldProductionReportingWorkflow: legacy keywords missing {missing_legacy}"
            )
        assert oil_rows is not None
        assert gas_rows is not None
        assert water_rows is not None
        assert oil_tag is not None
        assert gas_tag is not None
        assert water_tag is not None
        return {
            "oil": ScadaSeriesSpec(label="oil", rows=oil_rows, tag=oil_tag),
            "gas": ScadaSeriesSpec(label="gas", rows=gas_rows, tag=gas_tag),
            "water": ScadaSeriesSpec(label="water", rows=water_rows, tag=water_tag),
        }
