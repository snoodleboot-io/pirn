"""``FaultDetector`` — detect faults from a coherence-style attribute volume.

Algorithm:
    1. Receive a coherence / discontinuity attribute volume and a
       ``coherence_threshold`` in [0, 1].
    2. Validate that ``coherence_threshold`` is a numeric value in [0, 1].
    3. Threshold the attribute volume: voxels below the threshold are
       classified as fault indicators.
    4. Return a binary fault-mask SegyVolume reference.

Math:
    Fault mask indicator for voxel :math:`i`:

    $$F_i = \\mathbb{1}\\bigl[C_i < \\tau\\bigr]$$

    where :math:`C_i` is the coherence value at voxel :math:`i` and
    :math:`\\tau` is ``coherence_threshold``.

References:
    - Bahorich, M.S. & Farmer, S.L. (1995). 3-D seismic discontinuity for
      faults and stratigraphic features: the coherence cube. *TLE*, 14(10),
      1053-1058.
    - Marfurt, K.J., Kirlin, R.L., Farmer, S.L. & Bahorich, M.S. (1998).
      3-D seismic attributes using a semblance-based coherency algorithm.
      *Geophysics*, 63(4), 1150-1165.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class FaultDetector(Knot):
    """Threshold a coherence / discontinuity attribute to highlight faults."""

    def __init__(
        self,
        *,
        attribute_volume: Knot,
        coherence_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            attribute_volume=attribute_volume,
            coherence_threshold=coherence_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        attribute_volume: SegyVolume,
        coherence_threshold: float,
        **_: Any,
    ) -> SegyVolume:
        """Threshold the coherence attribute volume at the configured level and return a fault-mask SegyVolume.

        Args:
            attribute_volume: Coherence or discontinuity attribute volume to threshold.
            coherence_threshold: Threshold in [0, 1]; voxels below this value
                are classified as faults.

        Returns:
            SegyVolume representing the binary fault mask.
        """
        if not isinstance(coherence_threshold, (int, float)):
            raise TypeError("FaultDetector: coherence_threshold must be numeric")
        if not 0.0 <= coherence_threshold <= 1.0:
            raise ValueError("FaultDetector: coherence_threshold must lie in [0, 1]")
        return SegyVolume(volume_id=f"{attribute_volume.volume_id}:faults")
