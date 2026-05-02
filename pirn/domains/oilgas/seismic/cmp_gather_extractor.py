"""``CmpGatherExtractor`` — extract a common-mid-point gather from a volume."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class CmpGatherExtractor(Knot):
    """Extract a CMP gather from a 3-D :class:`SegyVolume`.

    The output is itself a :class:`SegyVolume` reference describing the
    extracted sub-cube (still 3-D but folded along the offset axis).
    """

    def __init__(
        self,
        *,
        volume: Knot,
        cmp_inline: int,
        cmp_xline: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(cmp_inline, int) or cmp_inline < 0:
            raise ValueError(
                "CmpGatherExtractor: cmp_inline must be a non-negative integer"
            )
        if not isinstance(cmp_xline, int) or cmp_xline < 0:
            raise ValueError(
                "CmpGatherExtractor: cmp_xline must be a non-negative integer"
            )
        self._cmp_inline = cmp_inline
        self._cmp_xline = cmp_xline
        super().__init__(volume=volume, _config=_config, **kwargs)

    async def process(self, volume: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(
            volume_id=f"{volume.volume_id}:cmp_{self._cmp_inline}_{self._cmp_xline}",
        )
