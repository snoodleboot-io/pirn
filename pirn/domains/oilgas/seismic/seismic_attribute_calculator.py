"""``SeismicAttributeCalculator`` — compute a named seismic attribute volume."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SeismicAttributeCalculator(Knot):
    """Compute a single attribute volume (envelope, instantaneous freq, ...)."""

    valid_attributes: ClassVar[frozenset[str]] = frozenset(
        {
            "envelope",
            "instantaneous_phase",
            "instantaneous_frequency",
            "coherence",
            "rms_amplitude",
            "sweetness",
        }
    )

    def __init__(
        self,
        *,
        volume: Knot,
        attribute: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if attribute not in self.valid_attributes:
            raise ValueError(
                f"SeismicAttributeCalculator: attribute must be one of "
                f"{sorted(self.valid_attributes)}"
            )
        self._attribute = attribute
        super().__init__(volume=volume, _config=_config, **kwargs)

    @property
    def attribute(self) -> str:
        return self._attribute

    async def process(self, volume: SegyVolume, **_: Any) -> SegyVolume:
        """Compute the configured seismic attribute on the input volume and return the resulting attribute SegyVolume.

        Args:
            volume: Input seismic volume from which to compute the attribute.

        Returns:
            SegyVolume of the computed attribute.
        """
        return SegyVolume(volume_id=f"{volume.volume_id}:attr_{self._attribute}")
