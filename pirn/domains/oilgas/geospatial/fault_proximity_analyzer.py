"""``FaultProximityAnalyzer`` — compute distance from each well to the nearest mapped fault.

Algorithm:
    1. Receive a list of well location dicts and a list of fault dicts with vertex geometry.
    2. Validate that ``buffer_m`` is a positive number.
    3. For each well, iterate over every fault segment and compute the
       point-to-segment Euclidean distance.
    4. Record the nearest fault ID and distance.
    5. Return one result dict per well with ``well_id``, ``nearest_fault_id``,
       ``distance_m``, and ``within_buffer``.

Math:
    Point-to-segment distance for well :math:`p = (p_x, p_y)` and segment
    :math:`\\overline{AB}` where :math:`A=(a_x, a_y)`, :math:`B=(b_x, b_y)`:

    $$t^* = \\operatorname{clamp}\\!\\left(\\frac{(p-A)\\cdot(B-A)}{\\|B-A\\|^2},\\, 0, 1\\right)$$

    $$d(p, \\overline{AB}) = \\|p - (A + t^*(B-A))\\|$$

References:
    - Sunday, D. (2012). *Geometry Algorithms: Distance from a Point to a Line*.
      http://geomalgorithms.com/a02-_lines.html
    - SEG Technical Standards Committee (2017). *SEG-Y Revision 2.0*, Section 9
      (coordinate encoding for fault polygons).
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FaultProximityAnalyzer(Knot):
    """Compute distance from each well to the nearest mapped fault segment."""

    def __init__(
        self,
        *,
        wells: Knot,
        faults: Knot,
        buffer_m: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            wells=wells,
            faults=faults,
            buffer_m=buffer_m,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _point_to_segment_dist(
        px: float,
        py: float,
        ax: float,
        ay: float,
        bx: float,
        by: float,
    ) -> float:
        dx, dy = bx - ax, by - ay
        if dx == 0.0 and dy == 0.0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    async def process(
        self,
        wells: list[dict[str, Any]],
        faults: list[dict[str, Any]],
        buffer_m: float,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compute nearest fault and distance for each well.

        Args:
            wells: List of well dicts with ``well_id``, ``x``, and ``y``.
            faults: List of fault dicts with ``fault_id`` and ``vertices``
                (list of [x, y] pairs).
            buffer_m: Positive buffer distance in metres used to flag proximity.

        Returns:
            List of dicts with ``well_id``, ``nearest_fault_id``,
            ``distance_m``, and ``within_buffer``.
        """
        if not isinstance(buffer_m, (int, float)):
            raise TypeError("FaultProximityAnalyzer: buffer_m must be numeric")
        if buffer_m <= 0:
            raise ValueError("FaultProximityAnalyzer: buffer_m must be positive")
        buf = float(buffer_m)
        results: list[dict[str, Any]] = []
        for well in wells:
            wx, wy = float(well["x"]), float(well["y"])
            best_dist = float("inf")
            best_fault_id = None
            for fault in faults:
                vertices: list[list[float]] = fault["vertices"]
                for i in range(len(vertices) - 1):
                    ax, ay = float(vertices[i][0]), float(vertices[i][1])
                    bx, by = float(vertices[i + 1][0]), float(vertices[i + 1][1])
                    d = self._point_to_segment_dist(wx, wy, ax, ay, bx, by)
                    if d < best_dist:
                        best_dist = d
                        best_fault_id = fault["fault_id"]
            results.append(
                {
                    "well_id": well["well_id"],
                    "nearest_fault_id": best_fault_id,
                    "distance_m": best_dist if best_fault_id is not None else 0.0,
                    "within_buffer": (best_dist <= buf if best_fault_id is not None else False),
                }
            )
        return results
