"""``FieldBoundaryDefiner`` — define a field boundary from a vertex list.

Algorithm:
    1. Receive ``field_id``, ``vertices`` (sequence of (x, y) tuples), and ``crs``.
    2. Validate that ``field_id`` is a non-empty string, vertices has at least 3
       entries, each vertex is a 2-tuple of numbers, and ``crs`` is non-empty.
    3. Convert all coordinates to floats and form a closed polygon.
    4. Return a dict with ``field_id``, ``vertices``, ``crs``, and ``vertex_count``.


References:
    - OGC 06-103r4, OpenGIS Implementation Standard for Geographic Information —
      Simple feature access — Part 1: Common architecture (polygon topology).
    - API Bulletin D16 — Nomenclature for Petroleum Reservoirs and Field Areas.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FieldBoundaryDefiner(Knot):
    """Construct a closed-polygon field boundary from a vertex list."""

    def __init__(
        self,
        *,
        field_id: Knot | str,
        vertices: Knot | Sequence[tuple[float, float]],
        crs: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            field_id=field_id,
            vertices=vertices,
            crs=crs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        field_id: str,
        vertices: Sequence[tuple[float, float]],
        crs: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Construct the closed-polygon boundary from the vertices and return the field boundary record.

        Args:
            field_id: Non-empty identifier for this field.
            vertices: Sequence of at least 3 (x, y) tuples defining the boundary.
            crs: Non-empty CRS identifier string (e.g. ``"EPSG:4326"``).

        Returns:
            Dict with ``field_id``, ``vertices`` (list of (x, y) tuples),
            ``crs``, and ``vertex_count``.
        """
        if not isinstance(field_id, str) or not field_id:
            raise ValueError(
                "FieldBoundaryDefiner: field_id must be a non-empty string"
            )
        vertex_tuple = tuple(vertices)
        if len(vertex_tuple) < 3:
            raise ValueError(
                "FieldBoundaryDefiner: at least 3 vertices required"
            )
        for vertex in vertex_tuple:
            if (
                not isinstance(vertex, tuple)
                or len(vertex) != 2
                or not all(isinstance(c, (int, float)) for c in vertex)
            ):
                raise ValueError(
                    "FieldBoundaryDefiner: every vertex must be a (x, y) tuple"
                )
        if not isinstance(crs, str) or not crs:
            raise ValueError(
                "FieldBoundaryDefiner: crs must be a non-empty string"
            )
        converted = tuple((float(x), float(y)) for x, y in vertex_tuple)
        return {
            "field_id": field_id,
            "vertices": list(converted),
            "crs": crs,
            "vertex_count": len(converted),
        }
