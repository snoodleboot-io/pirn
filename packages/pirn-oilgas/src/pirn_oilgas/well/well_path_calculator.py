"""``WellPathCalculator`` — compute a 3-D well path from a deviation survey.

Algorithm:
    1. Receive a deviation survey and a ``method`` string selecting the
       path calculation algorithm.
    2. Validate that ``method`` is one of ``minimum_curvature``,
       ``tangential``, or ``balanced_tangential``.
    3. Apply the selected algorithm to compute Cartesian (X, Y, TVD)
       coordinates from measured-depth, inclination, and azimuth stations.
    4. Return a WellPath3D reference.

Math:
    Minimum curvature method dog-leg factor:

    $$RF = \\frac{2}{\\Delta MD \\, \\delta}
      \\tan\\!\\left(\\frac{\\delta}{2}\\right)$$

    North, East, and TVD increments:

    $$\\Delta N = \\frac{\\Delta MD}{2} RF
      (\\sin I_1 \\cos A_1 + \\sin I_2 \\cos A_2)$$

References:
    - Craig, J.T. & Randall, B.V. (1976). Directional survey calculation.
      *Petroleum Engineer*, March, 38-54.
    - API RP 11V10 (2004) — Design of Pumping Facilities (directional survey
      computation methods).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.deviation_survey_payload import DeviationSurveyPayload
from pirn_oilgas.types.well_path_3d import WellPath3D
from pirn_oilgas.types.well_path_3d_payload import WellPath3DPayload


def _minimum_curvature(stations: np.ndarray) -> np.ndarray:
    station_count = len(stations)
    points = np.zeros((station_count, 3), dtype=np.float64)
    inc = np.deg2rad(stations[:, 1])
    azi = np.deg2rad(stations[:, 2])
    for station_idx in range(1, station_count):
        delta_md = stations[station_idx, 0] - stations[station_idx - 1, 0]
        inc1, inc2 = inc[station_idx - 1], inc[station_idx]
        azi1, azi2 = azi[station_idx - 1], azi[station_idx]
        dl = np.arccos(
            np.cos(inc2 - inc1) - np.sin(inc1) * np.sin(inc2) * (1 - np.cos(azi2 - azi1))
        )
        rf = (2 / dl) * np.tan(dl / 2) if dl > 1e-6 else 1.0
        dN = (delta_md / 2) * rf * (np.sin(inc1) * np.cos(azi1) + np.sin(inc2) * np.cos(azi2))
        dE = (delta_md / 2) * rf * (np.sin(inc1) * np.sin(azi1) + np.sin(inc2) * np.sin(azi2))
        dTVD = (delta_md / 2) * rf * (np.cos(inc1) + np.cos(inc2))
        points[station_idx] = points[station_idx - 1] + [dN, dE, dTVD]
    return points


def _tangential(stations: np.ndarray) -> np.ndarray:
    station_count = len(stations)
    points = np.zeros((station_count, 3), dtype=np.float64)
    inc = np.deg2rad(stations[:, 1])
    azi = np.deg2rad(stations[:, 2])
    for station_idx in range(1, station_count):
        delta_md = stations[station_idx, 0] - stations[station_idx - 1, 0]
        points[station_idx] = points[station_idx - 1] + delta_md * np.array(
            [
                np.sin(inc[station_idx]) * np.cos(azi[station_idx]),
                np.sin(inc[station_idx]) * np.sin(azi[station_idx]),
                np.cos(inc[station_idx]),
            ]
        )
    return points


def _balanced_tangential(stations: np.ndarray) -> np.ndarray:
    station_count = len(stations)
    points = np.zeros((station_count, 3), dtype=np.float64)
    inc = np.deg2rad(stations[:, 1])
    azi = np.deg2rad(stations[:, 2])
    for station_idx in range(1, station_count):
        delta_md = stations[station_idx, 0] - stations[station_idx - 1, 0]
        mid_inc = (inc[station_idx - 1] + inc[station_idx]) / 2
        mid_azi = (azi[station_idx - 1] + azi[station_idx]) / 2
        points[station_idx] = points[station_idx - 1] + delta_md * np.array(
            [
                np.sin(mid_inc) * np.cos(mid_azi),
                np.sin(mid_inc) * np.sin(mid_azi),
                np.cos(mid_inc),
            ]
        )
    return points


_algorithms = {
    "minimum_curvature": _minimum_curvature,
    "tangential": _tangential,
    "balanced_tangential": _balanced_tangential,
}


class WellPathCalculator(Knot):
    """Convert a deviation survey into a 3-D well-path reference."""

    def __init__(
        self,
        *,
        survey: Knot,
        method: Knot | str = "minimum_curvature",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(survey=survey, method=method, _config=_config, **kwargs)

    async def process(
        self,
        survey: DeviationSurveyPayload,
        method: str = "minimum_curvature",
        **_: Any,
    ) -> WellPath3DPayload:
        """Convert a deviation survey into a 3-D well path using the configured algorithm.

        Args:
            survey: DeviationSurveyPayload providing measured-depth, inclination, and azimuth stations.
            method: Path calculation algorithm; must be one of
                ``minimum_curvature``, ``tangential``, or ``balanced_tangential``.

        Returns:
            WellPath3DPayload computed from the survey using the configured calculation method.
        """
        if not isinstance(survey, DeviationSurveyPayload):
            raise TypeError("WellPathCalculator: survey must be a DeviationSurveyPayload")
        _valid_methods = frozenset(_algorithms)
        if method not in _valid_methods:
            raise ValueError(f"WellPathCalculator: method must be one of {sorted(_valid_methods)}")
        algo = _algorithms[method]
        points = await asyncio.to_thread(algo, survey.stations)
        return WellPath3DPayload(
            metadata=WellPath3D(
                well_id=survey.survey.well_id,
                point_count=len(points),
            ),
            data=points.astype(np.float64),
        )
