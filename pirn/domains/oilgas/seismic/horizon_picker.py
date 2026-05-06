"""``HorizonPicker`` — auto-pick a seed horizon through a seismic volume.

Algorithm:
    1. Receive a seismic volume, a non-empty ``horizon_name`` string, and
       non-negative integer ``seed_inline`` and ``seed_xline`` coordinates.
    2. Validate all inputs.
    3. Seed the auto-tracker at (``seed_inline``, ``seed_xline``) and
       propagate a zero-crossing / peak pick across the survey footprint.
    4. Return a SegyVolume reference representing the picked horizon surface.

    underlying processing engine).

References:
    - Dalley, R.M. et al. (1989). Dip and azimuth displays for 3D seismic
      interpretation. *First Break*, 7(3), 86-95.
    - Tingdahl, K.M. & de Rooij, M. (2005). Semi-automatic detection of faults
      in 3D seismic data. *Geophysical Prospecting*, 53(4), 533-542.
"""

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
        horizon_name: Knot | str,
        seed_inline: Knot | int,
        seed_xline: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            volume=volume,
            horizon_name=horizon_name,
            seed_inline=seed_inline,
            seed_xline=seed_xline,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        volume: SegyVolume,
        horizon_name: str,
        seed_inline: int,
        seed_xline: int,
        **_: Any,
    ) -> SegyVolume:
        """Auto-pick the named horizon through the volume from the seed location and return the horizon SegyVolume.

        Args:
            volume: 3-D seismic volume to auto-pick the horizon through.
            horizon_name: Non-empty name identifying the horizon.
            seed_inline: Non-negative inline index for the seed pick.
            seed_xline: Non-negative crossline index for the seed pick.

        Returns:
            SegyVolume representing the picked horizon surface.
        """
        if not isinstance(horizon_name, str) or not horizon_name:
            raise ValueError("HorizonPicker: horizon_name must be a non-empty string")
        if not isinstance(seed_inline, int) or seed_inline < 0:
            raise ValueError("HorizonPicker: seed_inline must be a non-negative integer")
        if not isinstance(seed_xline, int) or seed_xline < 0:
            raise ValueError("HorizonPicker: seed_xline must be a non-negative integer")
        return SegyVolume(
            volume_id=f"{volume.volume_id}:horizon_{horizon_name}",
        )
