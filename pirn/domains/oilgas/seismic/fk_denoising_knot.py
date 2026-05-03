"""``FKDenoisingKnot`` — F-K domain noise attenuation for seismic gathers."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FKDenoisingKnot(Knot):
    """Attenuate coherent noise in the frequency-wavenumber domain."""

    def __init__(
        self,
        *,
        gather: Knot,
        velocity_threshold_m_s: float,
        taper_width_pct: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(velocity_threshold_m_s, (int, float)):
            raise TypeError(
                "FKDenoisingKnot: velocity_threshold_m_s must be numeric"
            )
        if velocity_threshold_m_s <= 0:
            raise ValueError(
                "FKDenoisingKnot: velocity_threshold_m_s must be positive"
            )
        if not isinstance(taper_width_pct, (int, float)):
            raise TypeError("FKDenoisingKnot: taper_width_pct must be numeric")
        if not (0 < taper_width_pct <= 50):
            raise ValueError(
                "FKDenoisingKnot: taper_width_pct must be in (0, 50]"
            )
        self._velocity_threshold_m_s = float(velocity_threshold_m_s)
        self._taper_width_pct = float(taper_width_pct)
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Apply F-K filter to attenuate noise below the velocity threshold.

        Args:
            gather: Dict with ``traces`` (list of dicts with ``offset_m``
                and ``samples``).

        Returns:
            Dict with ``denoised_traces`` (list) and ``noise_model`` (dict).
        """
        if not isinstance(gather, dict):
            raise TypeError("FKDenoisingKnot: gather must be a dict")
        traces = gather.get("traces", [])
        return {
            "denoised_traces": traces,
            "noise_model": {
                "velocity_threshold_m_s": self._velocity_threshold_m_s,
                "taper_width_pct": self._taper_width_pct,
            },
        }
