"""``SphericalDivergenceGain`` — apply spherical divergence gain correction to seismic amplitudes."""

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
        velocity_m_s: float,
        t_power: float = 2.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(velocity_m_s, (int, float)):
            raise TypeError("SphericalDivergenceGain: velocity_m_s must be numeric")
        if velocity_m_s <= 0:
            raise ValueError("SphericalDivergenceGain: velocity_m_s must be positive")
        if not isinstance(t_power, (int, float)):
            raise TypeError("SphericalDivergenceGain: t_power must be numeric")
        if t_power <= 0:
            raise ValueError("SphericalDivergenceGain: t_power must be positive")
        self._velocity_m_s = float(velocity_m_s)
        self._t_power = float(t_power)
        super().__init__(data=data, _config=_config, **kwargs)

    async def process(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Apply spherical divergence gain correction to each trace.

        Args:
            data: Dict with ``traces`` (list of dicts with ``samples`` and
                ``two_way_time_ms``).

        Returns:
            Dict with same structure as input with corrected samples.
        """
        if not isinstance(data, dict):
            raise TypeError("SphericalDivergenceGain: data must be a dict")
        corrected_traces: list[dict[str, Any]] = []
        for trace in data.get("traces", []):
            twt_ms = float(trace.get("two_way_time_ms", 1.0) or 1.0)
            twt_s = twt_ms / 1000.0
            gain = (self._velocity_m_s * twt_s) ** self._t_power
            samples = [s * gain for s in trace.get("samples", [])]
            corrected_traces.append({**trace, "samples": samples})
        return {**data, "traces": corrected_traces}
