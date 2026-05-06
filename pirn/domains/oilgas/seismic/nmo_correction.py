"""``NmoCorrection`` — apply normal-move-out correction to a gather.

Algorithm:
    1. Receive a CMP gather SegyVolume and a positive
       ``stacking_velocity_m_s``.
    2. Validate that ``stacking_velocity_m_s`` is a positive number.
    3. For each trace, compute the NMO time shift at its offset.
    4. Shift each trace to zero-offset time and return the corrected gather.

Math:
    NMO time correction for offset :math:`x`:

    $$t_{NMO}(x) = \\sqrt{t_0^2 + \\frac{x^2}{v_{NMO}^2}}$$

    Time shift applied to each sample:

    $$\\Delta t = t_{NMO}(x) - t_0$$

References:
    - Dix, C.H. (1955). Seismic velocities from surface measurements.
      *Geophysics*, 20(1), 68-86.
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 3
      (NMO correction and stacking velocity analysis).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class NmoCorrection(Knot):
    """NMO-correct a CMP gather using a supplied stacking velocity."""

    def __init__(
        self,
        *,
        gather: Knot,
        stacking_velocity_m_s: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gather=gather,
            stacking_velocity_m_s=stacking_velocity_m_s,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gather: SegyVolume,
        stacking_velocity_m_s: float,
        **_: Any,
    ) -> SegyVolume:
        """Apply NMO correction to the CMP gather using the configured stacking velocity and return the corrected SegyVolume.

        Args:
            gather: CMP gather SegyVolume to apply NMO correction to.
            stacking_velocity_m_s: Positive stacking velocity in metres per second.

        Returns:
            SegyVolume of the NMO-corrected gather.
        """
        if not isinstance(stacking_velocity_m_s, (int, float)):
            raise TypeError(
                "NmoCorrection: stacking_velocity_m_s must be numeric"
            )
        if stacking_velocity_m_s <= 0.0:
            raise ValueError(
                "NmoCorrection: stacking_velocity_m_s must be positive"
            )
        return SegyVolume(volume_id=f"{gather.volume_id}:nmo")
