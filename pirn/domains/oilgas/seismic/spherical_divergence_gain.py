"""``SphericalDivergenceGain`` — apply spherical divergence gain correction to seismic amplitudes.

Algorithm:
    1. Receive a seismic data dict, a positive ``velocity_m_s``, and a
       positive ``t_power`` exponent (default 2.0).
    2. Validate that both numeric inputs are positive.
    3. For each trace, compute the two-way travel time and apply a
       time-and-velocity gain factor.
    4. Return the data dict with corrected trace samples.

Math:
    Spherical divergence gain factor for trace at two-way time :math:`t`:

    $$G(t) = (v \\cdot t)^{n}$$

    where :math:`v` is the RMS velocity, :math:`t` is two-way time, and
    :math:`n` is ``t_power`` (typically 2).

References:
    - Newman, P. (1973). Divergence effects in a layered earth. *Geophysics*,
      38(3), 481-488.
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 2
      (amplitude corrections and gain recovery).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SphericalDivergenceGain(Knot):
    """Correct seismic amplitudes for geometric spreading (spherical divergence)."""

    def __init__(
        self,
        *,
        data: Knot,
        velocity_m_s: Knot | float,
        t_power: Knot | float = 2.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            data=data,
            velocity_m_s=velocity_m_s,
            t_power=t_power,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        data: dict[str, Any],
        velocity_m_s: float,
        t_power: float = 2.0,
        **_: Any,
    ) -> dict[str, Any]:
        """Apply spherical divergence gain correction to each trace.

        Args:
            data: Dict with ``traces`` (list of dicts with ``samples`` and
                ``two_way_time_ms``).
            velocity_m_s: Positive RMS velocity in metres per second.
            t_power: Positive time exponent for the gain function (default 2.0).

        Returns:
            Dict with same structure as input with corrected samples.
        """
        if not isinstance(velocity_m_s, (int, float)):
            raise TypeError("SphericalDivergenceGain: velocity_m_s must be numeric")
        if velocity_m_s <= 0:
            raise ValueError("SphericalDivergenceGain: velocity_m_s must be positive")
        if not isinstance(t_power, (int, float)):
            raise TypeError("SphericalDivergenceGain: t_power must be numeric")
        if t_power <= 0:
            raise ValueError("SphericalDivergenceGain: t_power must be positive")
        if not isinstance(data, dict):
            raise TypeError("SphericalDivergenceGain: data must be a dict")
        corrected_traces: list[dict[str, Any]] = []
        for trace in data.get("traces", []):
            twt_ms = float(trace.get("two_way_time_ms", 1.0) or 1.0)
            twt_s = twt_ms / 1000.0
            gain = (float(velocity_m_s) * twt_s) ** float(t_power)
            samples = [s * gain for s in trace.get("samples", [])]
            corrected_traces.append({**trace, "samples": samples})
        return {**data, "traces": corrected_traces}
