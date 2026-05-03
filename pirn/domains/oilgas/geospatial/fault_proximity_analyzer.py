"""``FaultProximityAnalyzer`` — compute distance from each well to the nearest mapped fault."""

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
        buffer_m: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(buffer_m, (int, float)):
            raise TypeError("FaultProximityAnalyzer: buffer_m must be numeric")
        if buffer_m <= 0:
            raise ValueError("FaultProximityAnalyzer: buffer_m must be positive")
        self._buffer_m = float(buffer_m)
        super().__init__(wells=wells, faults=faults, _config=_config, **kwargs)

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
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compute nearest fault and distance for each well.

        Args:
            wells: List of well dicts with ``well_id``, ``x``, and ``y``.
            faults: List of fault dicts with ``fault_id`` and ``vertices``
                (list of [x, y] pairs).

        Returns:
            List of dicts with ``well_id``, ``nearest_fault_id``,
            ``distance_m``, and ``within_buffer``.
        """
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
                    "within_buffer": (
                        best_dist <= self._buffer_m
                        if best_fault_id is not None
                        else False
                    ),
                }
            )
        return results
