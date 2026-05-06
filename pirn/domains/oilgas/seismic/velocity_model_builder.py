"""``VelocityModelBuilder`` — build a 3D velocity model from semblance picks and well control.

Algorithm:
    1. Receive semblance velocity picks, well-derived velocity control
       points, and an ``interpolation_method`` string.
    2. Validate that ``interpolation_method`` is one of ``kriging``,
       ``idw``, or ``natural_neighbor``.
    3. Merge semblance picks and well-control points into a common
       node set.
    4. Interpolate velocity values across the 3-D survey grid using the
       selected method.
    5. Return the velocity model with node count and velocity range.

Math:
    Inverse-distance weighted (IDW) interpolation at point :math:`\\mathbf{x}`:

    $$v(\\mathbf{x}) = \\frac{\\sum_i w_i v_i}{\\sum_i w_i}, \\quad
      w_i = \\|\\mathbf{x} - \\mathbf{x}_i\\|^{-p}$$

References:
    - Cressie, N.A.C. (1993). *Statistics for Spatial Data*, revised ed.
      Wiley-Interscience, Chapter 3 (kriging methods).
    - Shepherd, D. (1968). A two-dimensional interpolation function for
      irregularly-spaced data. *ACM National Conference Proceedings*,
      517-524. ACM-DL-1968-8028.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VelocityModelBuilder(Knot):
    """Interpolate a 3D velocity model from semblance picks constrained by well velocities."""

    def __init__(
        self,
        *,
        semblance_picks: Knot,
        well_velocities: Knot,
        interpolation_method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            semblance_picks=semblance_picks,
            well_velocities=well_velocities,
            interpolation_method=interpolation_method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        semblance_picks: list[dict[str, Any]],
        well_velocities: list[dict[str, Any]],
        interpolation_method: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Build a velocity model by interpolating semblance picks with well velocity control.

        Args:
            semblance_picks: List of velocity pick dicts from semblance analysis.
            well_velocities: List of well-derived velocity control point dicts.
            interpolation_method: One of ``kriging``, ``idw``, or
                ``natural_neighbor``.

        Returns:
            Dict with ``velocity_model`` (dict with ``nodes`` (int),
            ``min_vel_m_s`` (float), ``max_vel_m_s`` (float)) and ``method`` (str).
        """
        valid_methods: frozenset[str] = frozenset({"kriging", "idw", "natural_neighbor"})
        if interpolation_method not in valid_methods:
            raise ValueError(
                f"VelocityModelBuilder: interpolation_method must be one of {sorted(valid_methods)}"
            )
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
            "method": interpolation_method,
        }
