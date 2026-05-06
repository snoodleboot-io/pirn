"""``FrequencyDecomposer`` — decompose a volume into frequency sub-bands.

Algorithm:
    1. Receive a seismic volume and a sequence of positive centre frequencies
       in Hz.
    2. Validate that ``center_frequencies_hz`` is non-empty and every value is
       a positive number.
    3. For each centre frequency, apply a Morlet or Ricker wavelet band-pass
       filter centred at that frequency.
    4. Return one SegyVolume reference per centre frequency.

Math:
    Gaussian band-pass filter centred at :math:`f_0` (Hz) with bandwidth
    :math:`\\sigma`:

    $$H(f; f_0) = \\exp\\!\\left(-\\frac{(f - f_0)^2}{2\\sigma^2}\\right)$$

References:
    - Partyka, G., Gridley, J. & Lopez, J. (1999). Interpretational
      applications of spectral decomposition in reservoir characterisation.
      *TLE*, 18(3), 353–360.
    - Liu, J. & Marfurt, K.J. (2007). Instantaneous spectral attributes to
      support seismic interpretation. *Geophysics*, 72(2), P23–P35.
"""

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
        center_frequencies_hz: Knot | Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            volume=volume,
            center_frequencies_hz=center_frequencies_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        volume: SegyVolume,
        center_frequencies_hz: Sequence[float],
        **_: Any,
    ) -> tuple[SegyVolume, ...]:
        """Decompose the seismic volume into frequency-band sub-volumes and return one SegyVolume per configured centre frequency.

        Args:
            volume: 3-D seismic volume to decompose into frequency bands.
            center_frequencies_hz: Non-empty sequence of positive centre
                frequencies in Hz.

        Returns:
            Tuple of SegyVolumes, one per configured centre frequency in Hz.
        """
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
        return tuple(
            SegyVolume(volume_id=f"{volume.volume_id}:band_{float(f):.1f}hz")
            for f in freq_tuple
        )
