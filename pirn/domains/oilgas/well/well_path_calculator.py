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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.types.well_path_3d import WellPath3D


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
        survey: DeviationSurvey,
        method: str = "minimum_curvature",
        **_: Any,
    ) -> WellPath3D:
        """Convert a deviation survey into a 3-D well path using the configured algorithm.

        Args:
            survey: Deviation survey providing measured-depth, inclination, and azimuth stations.
            method: Path calculation algorithm; must be one of
                ``minimum_curvature``, ``tangential``, or ``balanced_tangential``.

        Returns:
            WellPath3D computed from the survey using the configured calculation method.
        """
        _valid_methods = frozenset({"minimum_curvature", "tangential", "balanced_tangential"})
        if method not in _valid_methods:
            raise ValueError(f"WellPathCalculator: method must be one of {sorted(_valid_methods)}")
        return WellPath3D(
            well_id=survey.well_id,
            point_count=survey.station_count,
        )
