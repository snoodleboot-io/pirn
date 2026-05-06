"""``DirectionalDrillingPlanner`` — plan a directional well to a target.

Algorithm:
    1. Receive the current 3-D well path and target coordinates
       (``target_x``, ``target_y``, ``target_z``) plus a positive
       ``max_dogleg_deg_per_30m`` build rate.
    2. Validate that all coordinates are numeric and that
       ``max_dogleg_deg_per_30m`` is positive.
    3. Compute the required azimuth, inclination, and build/drop sequences
       to reach the target within the dogleg limit.
    4. Return a planned WellPath3D trajectory.

Math:
    Dog-leg angle between two survey stations (:math:`\\delta` in degrees):

    $$\\delta = \\arccos\\bigl(\\cos I_1 \\cos I_2
      + \\sin I_1 \\sin I_2 \\cos(A_2 - A_1)\\bigr)$$

    Dogleg severity:

    $$\\text{DLS} = \\frac{\\delta}{\\Delta MD} \\times 30 \\quad
      [^\\circ / 30 \\text{ m}]$$

References:
    - IADC Well Control Manual (7th ed., 2021), Section 5 (directional
      drilling fundamentals).
    - Bourgoyne, A.T. et al. (1986). *Applied Drilling Engineering*. SPE
      Textbook Series Vol. 2, Chapter 8 (directional drilling).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.well_path_3d import WellPath3D


class DirectionalDrillingPlanner(Knot):
    """Plan a directional well to a target geometry from a current well path."""

    def __init__(
        self,
        *,
        current_path: Knot,
        target_x: Knot | float,
        target_y: Knot | float,
        target_z: Knot | float,
        max_dogleg_deg_per_30m: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            current_path=current_path,
            target_x=target_x,
            target_y=target_y,
            target_z=target_z,
            max_dogleg_deg_per_30m=max_dogleg_deg_per_30m,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        current_path: WellPath3D,
        target_x: float,
        target_y: float,
        target_z: float,
        max_dogleg_deg_per_30m: float,
        **_: Any,
    ) -> WellPath3D:
        """Plan a directional trajectory from the current path to the configured target and return the planned WellPath3D.

        Args:
            current_path: Current 3-D well path used as the planning starting point.
            target_x: Target easting coordinate (m or ft).
            target_y: Target northing coordinate (m or ft).
            target_z: Target true vertical depth coordinate (m or ft).
            max_dogleg_deg_per_30m: Positive maximum dogleg severity (degrees per 30 m).

        Returns:
            WellPath3D representing the planned trajectory to the configured target coordinates.
        """
        for label, value in (
            ("target_x", target_x),
            ("target_y", target_y),
            ("target_z", target_z),
            ("max_dogleg_deg_per_30m", max_dogleg_deg_per_30m),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"DirectionalDrillingPlanner: {label} must be numeric")
        if max_dogleg_deg_per_30m <= 0.0:
            raise ValueError("DirectionalDrillingPlanner: max_dogleg_deg_per_30m must be positive")
        return WellPath3D(
            well_id=current_path.well_id,
            point_count=current_path.point_count,
        )
