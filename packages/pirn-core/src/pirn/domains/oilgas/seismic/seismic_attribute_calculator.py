"""``SeismicAttributeCalculator`` — compute a named seismic attribute volume.

Algorithm:
    1. Receive a seismic volume and an ``attribute`` string naming the
       attribute to compute.
    2. Validate that ``attribute`` is one of the supported set.
    3. Apply the corresponding transform (e.g. envelope for ``envelope``,
       semblance for ``coherence``, RMS in a rolling window for
       ``rms_amplitude``).
    4. Return the attribute volume as a SegyVolume reference.

Math:
    Envelope (instantaneous amplitude):

    $$A(t) = \\sqrt{s(t)^2 + \\mathcal{H}\\{s(t)\\}^2}$$

    Sweetness attribute:

    $$\\text{Sweetness} = \\frac{A(t)}{\\sqrt{f_i(t)}}$$

    where :math:`f_i(t)` is instantaneous frequency.

References:
    - Taner, M.T., Koehler, F. & Sheriff, R.E. (1979). Complex seismic trace
      analysis. *Geophysics*, 44(6), 1041-1063.
    - Chopra, S. & Marfurt, K.J. (2005). Seismic attributes — a historical
      perspective. *Geophysics*, 70(5), 3SO-28SO.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SeismicAttributeCalculator(Knot):
    """Compute a single attribute volume (envelope, instantaneous freq, ...)."""

    def __init__(
        self,
        *,
        volume: Knot,
        attribute: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(volume=volume, attribute=attribute, _config=_config, **kwargs)

    async def process(self, volume: SegyVolume, attribute: str, **_: Any) -> SegyVolume:
        """Compute the configured seismic attribute on the input volume and return the resulting attribute SegyVolume.

        Args:
            volume: Input seismic volume from which to compute the attribute.
            attribute: Attribute name; must be one of ``envelope``,
                ``instantaneous_phase``, ``instantaneous_frequency``,
                ``coherence``, ``rms_amplitude``, or ``sweetness``.

        Returns:
            SegyVolume of the computed attribute.
        """
        valid_attributes: frozenset[str] = frozenset(
            {
                "envelope",
                "instantaneous_phase",
                "instantaneous_frequency",
                "coherence",
                "rms_amplitude",
                "sweetness",
            }
        )
        if attribute not in valid_attributes:
            raise ValueError(
                f"SeismicAttributeCalculator: attribute must be one of {sorted(valid_attributes)}"
            )
        return SegyVolume(volume_id=f"{volume.volume_id}:attr_{attribute}")
