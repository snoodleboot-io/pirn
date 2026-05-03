"""``VelocityModelBuilder`` — build a 3D velocity model from semblance picks and well control."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VelocityModelBuilder(Knot):
    """Interpolate a 3D velocity model from semblance picks constrained by well velocities."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"kriging", "idw", "natural_neighbor"}
    )

    def __init__(
        self,
        *,
        semblance_picks: Knot,
        well_velocities: Knot,
        interpolation_method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if interpolation_method not in self.valid_methods:
            raise ValueError(
                f"VelocityModelBuilder: interpolation_method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._interpolation_method = interpolation_method
        super().__init__(
            semblance_picks=semblance_picks,
            well_velocities=well_velocities,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        semblance_picks: list[dict[str, Any]],
        well_velocities: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Build a velocity model by interpolating semblance picks with well velocity control.

        Args:
            semblance_picks: List of velocity pick dicts from semblance analysis.
            well_velocities: List of well-derived velocity control point dicts.

        Returns:
            Dict with ``velocity_model`` (dict with ``nodes`` (int),
            ``min_vel_m_s`` (float), ``max_vel_m_s`` (float)) and ``method`` (str).
        """
        all_vels: list[float] = [
            float(p.get("velocity_m_s", 2000.0))
            for p in semblance_picks + well_velocities
            if "velocity_m_s" in p
        ] or [2000.0]
        return {
            "velocity_model": {
                "nodes": len(semblance_picks) + len(well_velocities),
                "min_vel_m_s": min(all_vels),
                "max_vel_m_s": max(all_vels),
            },
            "method": self._interpolation_method,
        }
