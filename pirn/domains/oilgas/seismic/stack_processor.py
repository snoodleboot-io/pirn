"""``StackProcessor`` — sum traces in a CMP gather to produce a stacked trace."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class StackProcessor(Knot):
    """Stack a corrected CMP gather to a single (inline, xline) trace volume."""

    def __init__(
        self,
        *,
        gather: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(volume_id=f"{gather.volume_id}:stacked")
