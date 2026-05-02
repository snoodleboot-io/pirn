"""``NmoCorrection`` — apply normal-move-out correction to a gather."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class NmoCorrection(Knot):
    """NMO-correct a CMP gather using a supplied stacking velocity."""

    def __init__(
        self,
        *,
        gather: Knot,
        stacking_velocity_m_s: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(stacking_velocity_m_s, (int, float)):
            raise TypeError(
                "NmoCorrection: stacking_velocity_m_s must be numeric"
            )
        if stacking_velocity_m_s <= 0.0:
            raise ValueError(
                "NmoCorrection: stacking_velocity_m_s must be positive"
            )
        self._stacking_velocity_m_s = float(stacking_velocity_m_s)
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(volume_id=f"{gather.volume_id}:nmo")
