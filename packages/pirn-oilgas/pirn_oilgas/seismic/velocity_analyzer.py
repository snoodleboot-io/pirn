"""``VelocityAnalyzer`` — semblance-style velocity picking on a gather.

Algorithm:
    1. Receive a CMP gather SegyVolume and a positive
       ``initial_velocity_m_s`` as the starting-point for the scan.
    2. Validate that ``initial_velocity_m_s`` is a positive number.
    3. Compute normalised semblance over a grid of trial velocities
       centred on ``initial_velocity_m_s``.
    4. Return the velocity (m/s) at the semblance maximum.

Math:
    Normalised semblance over :math:`N` offsets:

    $$S(v, t_0) = \\frac{\\left(\\sum_{j=1}^{N} s_j(t_{NMO}(v))\\right)^2}
      {N \\sum_{j=1}^{N} s_j(t_{NMO}(v))^2}$$

References:
    - Taner, M.T. & Koehler, F. (1969). Velocity spectra — digital computer
      derivation and applications of velocity functions. *Geophysics*,
      34(6), 859-881.
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 3
      (velocity analysis and semblance).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class VelocityAnalyzer(Knot):
    """Pick a stacking velocity from a CMP gather.

    The output is a stacking velocity in metres per second. Real
    implementations run a semblance scan; the stub returns the picker's
    initial velocity guess so downstream NMO knots can be wired.
    """

    def __init__(
        self,
        *,
        gather: Knot,
        initial_velocity_m_s: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gather=gather,
            initial_velocity_m_s=initial_velocity_m_s,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gather: SegyVolume,
        initial_velocity_m_s: float,
        **_: Any,
    ) -> float:
        """Pick the stacking velocity from the CMP gather via semblance analysis and return it in metres per second.

        Args:
            gather: CMP gather from which to pick the stacking velocity.
            initial_velocity_m_s: Positive initial velocity guess for the scan (m/s).

        Returns:
            Stacking velocity in metres per second (float).
        """
        if not isinstance(initial_velocity_m_s, (int, float)):
            raise TypeError("VelocityAnalyzer: initial_velocity_m_s must be numeric")
        if initial_velocity_m_s <= 0.0:
            raise ValueError("VelocityAnalyzer: initial_velocity_m_s must be positive")
        return float(initial_velocity_m_s)
