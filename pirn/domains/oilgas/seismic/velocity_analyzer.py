"""``VelocityAnalyzer`` — semblance-style velocity picking on a gather."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class VelocityAnalyzer(Knot):
    """Pick a stacking velocity from a CMP gather.

    The output is a stacking velocity in metres per second. Real
    implementations run a semblance scan; the stub returns the picker's
    initial velocity guess so downstream NMO knots can be wired.
    """

    def __init__(
        self,
        *,
        gather: Knot,
        initial_velocity_m_s: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(initial_velocity_m_s, (int, float)):
            raise TypeError(
                "VelocityAnalyzer: initial_velocity_m_s must be numeric"
            )
        if initial_velocity_m_s <= 0.0:
            raise ValueError(
                "VelocityAnalyzer: initial_velocity_m_s must be positive"
            )
        self._initial_velocity_m_s = float(initial_velocity_m_s)
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: SegyVolume, **_: Any) -> float:
        return self._initial_velocity_m_s
