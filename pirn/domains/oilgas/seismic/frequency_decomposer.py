"""``FrequencyDecomposer`` — decompose a volume into frequency sub-bands."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class FrequencyDecomposer(Knot):
    """Decompose a seismic volume into a configured set of frequency bands."""

    def __init__(
        self,
        *,
        volume: Knot,
        center_frequencies_hz: Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        freq_tuple = tuple(center_frequencies_hz)
        if not freq_tuple:
            raise ValueError(
                "FrequencyDecomposer: center_frequencies_hz must be non-empty"
            )
        for f in freq_tuple:
            if not isinstance(f, (int, float)) or f <= 0.0:
                raise ValueError(
                    "FrequencyDecomposer: every centre frequency must be positive"
                )
        self._center_frequencies_hz = tuple(float(f) for f in freq_tuple)
        super().__init__(volume=volume, _config=_config, **kwargs)

    @property
    def center_frequencies_hz(self) -> tuple[float, ...]:
        return self._center_frequencies_hz

    async def process(self, volume: SegyVolume, **_: Any) -> tuple[SegyVolume, ...]:
        """Decompose the seismic volume into frequency-band sub-volumes and return one SegyVolume per configured centre frequency.

        Args:
            volume: 3-D seismic volume to decompose into frequency bands.

        Returns:
            Tuple of SegyVolumes, one per configured centre frequency in Hz.
        """
        return tuple(
            SegyVolume(volume_id=f"{volume.volume_id}:band_{f:.1f}hz")
            for f in self._center_frequencies_hz
        )
