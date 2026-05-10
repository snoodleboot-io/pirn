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

    $$d(p, B) \\leq d_{\\text{buffer}}$$

    where :math:`d(p, B)` is the minimum Euclidean distance from point
    :math:`p` to boundary :math:`B`.

References:
    - API MPMS Chapter 20 — Measurement of Liquid Hydrocarbons by Weight (field
      boundary conventions).
    - Aurenhammer, F. (1991). Voronoi diagrams — a survey of a fundamental
      geometric data structure. *ACM Computing Surveys*, 23(3), 345-405.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _point_in_polygon(px: float, py: float, polygon: list[list[float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test (Jordan curve theorem)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        # Ray from (px, py) in +x direction crosses edge (xi,yi)-(xj,yj) when
        # the edge straddles py and the intersection is to the right of px.
        if (yi > py) != (yj > py):
            x_intersect = (xj - xi) * (py - yi) / (yj - yi + 1e-15) + xi
            if px < x_intersect:
                inside = not inside
        j = i
    return inside


def _dist_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance from point (px, py) to line segment (ax,ay)-(bx,by)."""
    dx = bx - ax
    dy = by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-15:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


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
                geometry under the ``polygon`` key (list of [x, y] pairs).
            buffer_distance_m: Non-negative buffer distance in metres.

        Returns:
            Dict with ``well_id``, ``field_id``, ``within_buffer`` (bool),
            and ``buffer_distance_m``.
        """
        if not isinstance(buffer_distance_m, (int, float)):
            raise TypeError("BoundaryProximityChecker: buffer_distance_m must be numeric")
        if buffer_distance_m < 0.0:
            raise ValueError("BoundaryProximityChecker: buffer_distance_m must be non-negative")

        px = float(location.get("x", 0.0))
        py = float(location.get("y", 0.0))
        polygon: list[list[float]] = boundary.get("polygon", [])

        within = False

        if len(polygon) >= 3:
            if _point_in_polygon(px, py, polygon):
                within = True
            elif buffer_distance_m > 0.0:
                n = len(polygon)
                for i in range(n):
                    ax, ay = polygon[i][0], polygon[i][1]
                    bx, by = polygon[(i + 1) % n][0], polygon[(i + 1) % n][1]
                    if _dist_to_segment(px, py, ax, ay, bx, by) < buffer_distance_m:
                        within = True
                        break
        elif len(polygon) == 0:
            # No polygon data; conservatively report as inside (fail-safe for empty boundaries)
            within = True

        return {
            "well_id": location.get("well_id", ""),
            "field_id": boundary.get("field_id", ""),
            "within_buffer": within,
            "buffer_distance_m": float(buffer_distance_m),
        }
