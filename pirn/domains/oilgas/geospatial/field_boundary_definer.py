"""``FieldBoundaryDefiner`` — define a field boundary from a vertex list."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FieldBoundaryDefiner(Knot):
    """Construct a closed-polygon field boundary from a vertex list."""

    def __init__(
        self,
        *,
        field_id: str,
        vertices: Sequence[tuple[float, float]],
        crs: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._field_id = field_id
        self._vertices = tuple((float(x), float(y)) for x, y in vertex_tuple)
        self._crs = crs
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Construct the closed-polygon boundary from the configured vertices and return the field boundary record.

        Returns:
            Dict with ``field_id``, ``vertices`` (list of (x, y) tuples),
            ``crs``, and ``vertex_count``.
        """
        return {
            "field_id": self._field_id,
            "vertices": list(self._vertices),
            "crs": self._crs,
            "vertex_count": len(self._vertices),
        }
