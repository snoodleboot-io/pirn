"""``StaticCorrection`` — apply elevation / weathering static corrections."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class StaticCorrection(Knot):
    """Apply elevation / weathering statics to a gather or volume."""

    def __init__(
        self,
        *,
        gather: Knot,
        datum_elevation_m: float,
        replacement_velocity_m_s: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(datum_elevation_m, (int, float)):
            raise TypeError(
                "StaticCorrection: datum_elevation_m must be numeric"
            )
        if not isinstance(replacement_velocity_m_s, (int, float)):
            raise TypeError(
                "StaticCorrection: replacement_velocity_m_s must be numeric"
            )
        if replacement_velocity_m_s <= 0.0:
            raise ValueError(
                "StaticCorrection: replacement_velocity_m_s must be positive"
            )
        self._datum_elevation_m = float(datum_elevation_m)
        self._replacement_velocity_m_s = float(replacement_velocity_m_s)
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(volume_id=f"{gather.volume_id}:static")
