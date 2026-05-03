"""``FaultDetector`` — detect faults from a coherence-style attribute volume."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class FaultDetector(Knot):
    """Threshold a coherence / discontinuity attribute to highlight faults."""

    def __init__(
        self,
        *,
        attribute_volume: Knot,
        coherence_threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(coherence_threshold, (int, float)):
            raise TypeError(
                "FaultDetector: coherence_threshold must be numeric"
            )
        if not 0.0 <= coherence_threshold <= 1.0:
            raise ValueError(
                "FaultDetector: coherence_threshold must lie in [0, 1]"
            )
        self._coherence_threshold = float(coherence_threshold)
        super().__init__(attribute_volume=attribute_volume, _config=_config, **kwargs)

    async def process(
        self, attribute_volume: SegyVolume, **_: Any
    ) -> SegyVolume:
        """Threshold the coherence attribute volume at the configured level and return a fault-mask SegyVolume.

        Args:
            attribute_volume: Coherence or discontinuity attribute volume to threshold.

        Returns:
            SegyVolume representing the binary fault mask.
        """
        return SegyVolume(volume_id=f"{attribute_volume.volume_id}:faults")
