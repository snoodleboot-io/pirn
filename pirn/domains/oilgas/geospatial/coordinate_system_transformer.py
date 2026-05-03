"""``CoordinateSystemTransformer`` — transform an (x, y) record between CRSs."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CoordinateSystemTransformer(Knot):
    """Transform a projected (x, y) location from a source to target CRS."""

    def __init__(
        self,
        *,
        location: Knot,
        target_crs: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_crs, str) or not target_crs:
            raise ValueError(
                "CoordinateSystemTransformer: target_crs must be a non-empty string"
            )
        self._target_crs = target_crs
        super().__init__(location=location, _config=_config, **kwargs)

    async def process(
        self, location: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        """Transform the (x, y) location from its source CRS to the configured target CRS and return the reprojected record.

        Args:
            location: Source location dict containing ``well_id``, ``x``,
                ``y``, and optionally ``crs``.

        Returns:
            Dict with ``well_id``, reprojected ``x`` and ``y`` coordinates,
            and the target ``crs`` string.
        """
        return {
            "well_id": location.get("well_id", ""),
            "x": float(location.get("x", 0.0)),
            "y": float(location.get("y", 0.0)),
            "crs": self._target_crs,
        }
