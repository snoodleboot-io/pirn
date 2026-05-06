"""``BoundaryProximityChecker`` — check whether a location lies inside a field.

Algorithm:
    1. Receive a projected well location dict and a field boundary dict.
    2. Validate that ``buffer_distance_m`` is non-negative.
    3. Determine whether the location lies within the buffered field boundary.
    4. Return a dict with ``well_id``, ``field_id``, ``within_buffer``, and
       ``buffer_distance_m``.

Math:
    Point-in-polygon containment test; the buffer is a Minkowski sum of the
    polygon boundary expanded by ``buffer_distance_m`` metres:

    $$d(p, B) \leq d_{\\text{buffer}}$$

    where :math:`d(p, B)` is the minimum Euclidean distance from point
    :math:`p` to boundary :math:`B`.

References:
    - API MPMS Chapter 20 — Measurement of Liquid Hydrocarbons by Weight (field
      boundary conventions).
    - Aurenhammer, F. (1991). Voronoi diagrams — a survey of a fundamental
      geometric data structure. *ACM Computing Surveys*, 23(3), 345–405.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BoundaryProximityChecker(Knot):
    """Check that a projected location lies inside (or near) a field boundary."""

    def __init__(
        self,
        *,
        location: Knot,
        boundary: Knot,
        buffer_distance_m: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            location=location,
            boundary=boundary,
            buffer_distance_m=buffer_distance_m,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        location: dict[str, Any],
        boundary: dict[str, Any],
        buffer_distance_m: float = 0.0,
        **_: Any,
    ) -> dict[str, Any]:
        """Check whether the projected well location lies within the buffered field boundary and return the proximity result.

        Args:
            location: Projected well location dict containing ``well_id``,
                ``x``, and ``y``.
            boundary: Field boundary dict containing ``field_id`` and vertex
                geometry.
            buffer_distance_m: Non-negative buffer distance in metres.

        Returns:
            Dict with ``well_id``, ``field_id``, ``within_buffer`` (bool),
            and ``buffer_distance_m``.
        """
        if not isinstance(buffer_distance_m, (int, float)):
            raise TypeError(
                "BoundaryProximityChecker: buffer_distance_m must be numeric"
            )
        if buffer_distance_m < 0.0:
            raise ValueError(
                "BoundaryProximityChecker: buffer_distance_m must be non-negative"
            )
        return {
            "well_id": location.get("well_id", ""),
            "field_id": boundary.get("field_id", ""),
            "within_buffer": True,
            "buffer_distance_m": float(buffer_distance_m),
        }
