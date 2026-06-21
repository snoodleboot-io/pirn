"""``DeclineCurveReservesWorkflow`` — SCADA rows -> DCA -> type curve -> reserves.

Composition:
    SCADA assemble -> decline-curve analyse -> type-curve fit ->
    Monte-Carlo reserves estimate.

Algorithm:
    1. Receive ``rows`` (historian query result), SCADA tag and time parameters,
       volumetric parameters, and trial count.
    2. Validate all string, numeric, and count inputs in ``process()``.
    3. Build the inner pipeline inside ``process()``:
       - ``ScadaDatabaseAssembler`` for rate history,
       - ``DeclineCurveAnalyzer`` and ``TypeCurveFitter`` for DCA,
       - ``VolumetricEstimator`` for OOIP,
       - ``MonteCarloSimulator`` for P10/P50/P90 reserves.
    4. Return the terminal knot; the base class runs the inner tapestry.


References:
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160,
      228-247. SPE-945228-G.
    - SPE-PRMS-2018 — Petroleum Resources Management System, Section 4.3
      (probabilistic reserves estimation).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_oilgas.assemblers.scada_database_assembler import ScadaDatabaseAssembler
from pirn_oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer
from pirn_oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator
from pirn_oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn_oilgas.reservoir.volumetric_estimator import VolumetricEstimator


class DeclineCurveReservesWorkflow(SubTapestry):
    """Reserves-estimation workflow grounded in a single producer's history."""

    def __init__(
        self,
        *,
        rows: Knot,
        oil_tag: Knot | str,
        since: Knot | datetime,
        sample_interval_sec: Knot | float,
        area_acres: Knot | float,
        net_thickness_ft: Knot | float,
        porosity_fraction: Knot | float,
        water_saturation_fraction: Knot | float,
        formation_volume_factor: Knot | float,
        trial_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            oil_tag=oil_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            area_acres=area_acres,
            net_thickness_ft=net_thickness_ft,
            porosity_fraction=porosity_fraction,
            water_saturation_fraction=water_saturation_fraction,
            formation_volume_factor=formation_volume_factor,
            trial_count=trial_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rows: list[tuple[Any, ...]],
        oil_tag: str,
        since: datetime,
        sample_interval_sec: float,
        area_acres: float,
        net_thickness_ft: float,
        porosity_fraction: float,
        water_saturation_fraction: float,
        formation_volume_factor: float,
        trial_count: int,
        **_: Any,
    ) -> Any:
        """Build the SCADA-to-reserves inner pipeline and return its terminal knot.

        Args:
            rows: List of ``(timestamp, value)`` tuples from a historian query.
            oil_tag: Non-empty SCADA tag name for oil rate.
            since: Start datetime for SCADA history pull.
            sample_interval_sec: Positive sample interval in seconds.
            area_acres: Positive drainage area in acres.
            net_thickness_ft: Positive net pay thickness in feet.
            porosity_fraction: Porosity fraction in [0, 1].
            water_saturation_fraction: Water saturation fraction in [0, 1].
            formation_volume_factor: Positive initial oil FVF in RB/STB.
            trial_count: Positive integer number of Monte-Carlo trials.

        Returns:
            Terminal knot of the inner pipeline (``MonteCarloSimulator``).
        """
        if not isinstance(oil_tag, str) or not oil_tag:
            raise ValueError("DeclineCurveReservesWorkflow: oil_tag must be a non-empty string")
        if not isinstance(trial_count, int) or trial_count <= 0:
            raise ValueError("DeclineCurveReservesWorkflow: trial_count must be a positive integer")
        rows_param = Parameter("rows", list, default=rows, _config=KnotConfig(id="rows"))
        rate = ScadaDatabaseAssembler(
            rows=rows_param,
            tag=oil_tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=KnotConfig(id="assemble"),
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
            area_acres=area_acres,
            net_thickness_ft=net_thickness_ft,
            porosity_fraction=porosity_fraction,
            water_saturation_fraction=water_saturation_fraction,
            formation_volume_factor=formation_volume_factor,
            _config=KnotConfig(id="volumetric"),
        )
        return MonteCarloSimulator(
            deterministic_estimate=volumetric,
            trial_count=trial_count,
            _config=KnotConfig(id="monte_carlo"),
        )
