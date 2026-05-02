"""``HorizonPicker`` — auto-pick a seed horizon through a seismic volume."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class HorizonPicker(Knot):
    """Auto-pick a horizon through a volume from a seed inline / xline."""

    def __init__(
        self,
        *,
        volume: Knot,
        horizon_name: str,
        seed_inline: int,
        seed_xline: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(horizon_name, str) or not horizon_name:
            raise ValueError(
                "HorizonPicker: horizon_name must be a non-empty string"
            )
        if not isinstance(seed_inline, int) or seed_inline < 0:
            raise ValueError(
                "HorizonPicker: seed_inline must be a non-negative integer"
            )
        if not isinstance(seed_xline, int) or seed_xline < 0:
            raise ValueError(
                "HorizonPicker: seed_xline must be a non-negative integer"
            )
        self._horizon_name = horizon_name
        self._seed_inline = seed_inline
        self._seed_xline = seed_xline
        super().__init__(volume=volume, _config=_config, **kwargs)

    @property
    def horizon_name(self) -> str:
        return self._horizon_name

    async def process(self, volume: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(
            volume_id=f"{volume.volume_id}:horizon_{self._horizon_name}",
        )
