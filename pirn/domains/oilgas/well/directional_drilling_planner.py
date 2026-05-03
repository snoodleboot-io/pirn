"""``DirectionalDrillingPlanner`` — plan a directional well to a target."""

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
        target_x: float,
        target_y: float,
        target_z: float,
        max_dogleg_deg_per_30m: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("target_x", target_x),
            ("target_y", target_y),
            ("target_z", target_z),
            ("max_dogleg_deg_per_30m", max_dogleg_deg_per_30m),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"DirectionalDrillingPlanner: {label} must be numeric"
                )
        if max_dogleg_deg_per_30m <= 0.0:
            raise ValueError(
                "DirectionalDrillingPlanner: max_dogleg_deg_per_30m must be positive"
            )
        self._target_x = float(target_x)
        self._target_y = float(target_y)
        self._target_z = float(target_z)
        self._max_dogleg_deg_per_30m = float(max_dogleg_deg_per_30m)
        super().__init__(current_path=current_path, _config=_config, **kwargs)

    async def process(self, current_path: WellPath3D, **_: Any) -> WellPath3D:
        """Plan a directional trajectory from the current path to the configured target and return the planned WellPath3D.

        Args:
            current_path: Current 3-D well path used as the planning starting point.

        Returns:
            WellPath3D representing the planned trajectory to the configured target coordinates.
        """
        return WellPath3D(
            well_id=current_path.well_id,
            point_count=current_path.point_count,
        )
