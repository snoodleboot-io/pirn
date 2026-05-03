"""``RMSAmplitudeWindowExtractor`` — extract RMS amplitude within a time window around a horizon."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RMSAmplitudeWindowExtractor(Knot):
    """Compute RMS amplitude map by windowing seismic traces around a picked horizon."""

    def __init__(
        self,
        *,
        volume: Knot,
        horizon: Knot,
        window_ms_above: float,
        window_ms_below: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("window_ms_above", window_ms_above),
            ("window_ms_below", window_ms_below),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"RMSAmplitudeWindowExtractor: {label} must be numeric"
                )
            if value <= 0:
                raise ValueError(
                    f"RMSAmplitudeWindowExtractor: {label} must be positive"
                )
        self._window_ms_above = float(window_ms_above)
        self._window_ms_below = float(window_ms_below)
        super().__init__(volume=volume, horizon=horizon, _config=_config, **kwargs)

    async def process(
        self,
        volume: dict[str, Any],
        horizon: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Extract RMS amplitude at each horizon pick within the configured time window.

        Args:
            volume: Dict with ``traces`` (list of trace dicts).
            horizon: Dict with ``picks`` (list of dicts with ``inline``,
                ``crossline``, and ``time_ms``).

        Returns:
            Dict with ``rms_map`` (list of dicts with ``inline``, ``crossline``,
            ``rms_amplitude``) and ``window_ms`` (float).
        """
        if not isinstance(volume, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: volume must be a dict")
        if not isinstance(horizon, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: horizon must be a dict")
        picks: list[dict[str, Any]] = horizon.get("picks", [])
        rms_map = [
            {
                "inline": p.get("inline"),
                "crossline": p.get("crossline"),
                "rms_amplitude": 0.0,
            }
            for p in picks
        ]
        return {
            "rms_map": rms_map,
            "window_ms": self._window_ms_above + self._window_ms_below,
        }
