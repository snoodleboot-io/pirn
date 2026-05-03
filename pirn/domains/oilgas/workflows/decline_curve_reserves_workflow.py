"""``DeclineCurveReservesWorkflow`` — SCADA -> DCA -> type curve -> reserves.

Composition:
    SCADA ingest -> decline-curve analyse -> type-curve fit ->
    Monte-Carlo reserves estimate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.production.scada_historian_ingester import (
    ScadaHistorianIngester,
)
from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection
from pirn.domains.oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer
from pirn.domains.oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator
from pirn.domains.oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn.domains.oilgas.reservoir.volumetric_estimator import VolumetricEstimator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DeclineCurveReservesWorkflow(SubTapestry):
    """Reserves-estimation workflow grounded in a single producer's history."""

    def __init__(
        self,
        *,
        connection: HistorianConnection,
        oil_tag: str,
        since: datetime,
        sample_interval_sec: float,
        area_acres: float,
        net_thickness_ft: float,
        porosity_fraction: float,
        water_saturation_fraction: float,
        formation_volume_factor: float,
        trial_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(connection, HistorianConnection):
            raise TypeError(
                "DeclineCurveReservesWorkflow: connection must be a HistorianConnection"
            )
        if not isinstance(oil_tag, str) or not oil_tag:
            raise ValueError(
                "DeclineCurveReservesWorkflow: oil_tag must be a non-empty string"
            )
        self._connection = connection
        self._oil_tag = oil_tag
        self._since = since
        self._sample_interval_sec = float(sample_interval_sec)
        self._area_acres = float(area_acres)
        self._net_thickness_ft = float(net_thickness_ft)
        self._porosity_fraction = float(porosity_fraction)
        self._water_saturation_fraction = float(water_saturation_fraction)
        self._formation_volume_factor = float(formation_volume_factor)
        self._trial_count = int(trial_count)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        """Build and execute the SCADA-to-reserves inner tapestry and return its RunResult.

        Returns:
            RunResult from the inner pipeline spanning SCADA ingest through Monte-Carlo reserves estimation.
        """
        with Tapestry() as inner:
            rate = ScadaHistorianIngester(
                connection=self._connection,
                tag=self._oil_tag,
                since=self._since,
                sample_interval_sec=self._sample_interval_sec,
                _config=KnotConfig(id="ingest"),
            )
            DeclineCurveAnalyzer(
                rate_series=rate,
                method="hyperbolic",
                _config=KnotConfig(id="decline"),
            )
            TypeCurveFitter(
                rate_series=rate,
                _config=KnotConfig(id="type_curve"),
            )
            volumetric = VolumetricEstimator(
                area_acres=self._area_acres,
                net_thickness_ft=self._net_thickness_ft,
                porosity_fraction=self._porosity_fraction,
                water_saturation_fraction=self._water_saturation_fraction,
                formation_volume_factor=self._formation_volume_factor,
                _config=KnotConfig(id="volumetric"),
            )
            MonteCarloSimulator(
                deterministic_estimate=volumetric,
                trial_count=self._trial_count,
                _config=KnotConfig(id="monte_carlo"),
            )
        return await self._run_inner(inner)
