"""``CmpGatherExtractor`` — extract a common-mid-point gather from a volume.

Algorithm:
    1. Receive a SEG-Y volume and non-negative integer ``cmp_inline`` and
       ``cmp_xline`` coordinates.
    2. Validate that ``cmp_inline`` and ``cmp_xline`` are non-negative integers.
    3. Locate the CMP gather at the specified inline / xline coordinates.
    4. Return a SegyVolume reference describing the extracted CMP gather.


References:
    - Sheriff, R.E. & Geldart, L.P. (1995). *Exploration Seismology*, 2nd ed.
      Cambridge University Press, Chapter 7 (CMP method).
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 1
      (CMP stacking).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class CmpGatherExtractor(Knot):
    """Extract a CMP gather from a 3-D :class:`SegyVolume`.

    The output is itself a :class:`SegyVolume` reference describing the
    extracted sub-cube (still 3-D but folded along the offset axis).
    """

    def __init__(
        self,
        *,
        volume: Knot,
        cmp_inline: Knot | int,
        cmp_xline: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            volume=volume,
            cmp_inline=cmp_inline,
            cmp_xline=cmp_xline,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, volume: SegyVolume, cmp_inline: int, cmp_xline: int, **_: Any
    ) -> SegyVolume:
        """Extract the CMP gather at the configured inline / xline from the volume and return it as a SegyVolume.

        Args:
            volume: Source 3-D SEG-Y volume to extract the CMP gather from.
            cmp_inline: Non-negative inline index of the CMP gather.
            cmp_xline: Non-negative crossline index of the CMP gather.

        Returns:
            SegyVolume representing the extracted CMP gather sub-cube.
        """
        if not isinstance(cmp_inline, int) or cmp_inline < 0:
            raise ValueError("CmpGatherExtractor: cmp_inline must be a non-negative integer")
        if not isinstance(cmp_xline, int) or cmp_xline < 0:
            raise ValueError("CmpGatherExtractor: cmp_xline must be a non-negative integer")
        return SegyVolume(
            volume_id=f"{volume.volume_id}:cmp_{cmp_inline}_{cmp_xline}",
        )
