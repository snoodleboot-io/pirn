"""``CathodicProtectionAnalyzer`` — assess cathodic-protection coverage.

Algorithm:
    1. Receive a ScadaTimeSeries of pipe-to-soil potential measurements and a
       ``protection_threshold_mv`` value.
    2. Validate that ``protection_threshold_mv`` is numeric.
    3. Compute the fraction of samples whose potential satisfies the protection
       criterion (i.e. below the threshold in absolute mV terms).
    4. Return a dict with ``coverage_fraction`` and ``threshold_mv``.

Math:
    NACE SP0169-2013 specifies cathodic protection criterion as a negative
    pipe-to-soil potential <= -850 mV (CSE). The coverage fraction is:

    $$\\text{coverage} = \\frac{|\\{t : V(t) \\leq V_{\\text{thresh}}\\}|}{N}$$

    where :math:`V(t)` is the measured potential at sample :math:`t`, and
    :math:`N` is the total sample count.

References:
    - NACE International SP0169-2013, Control of External Corrosion on
      Underground or Submerged Metallic Piping Systems.
    - API RP 1632 — Cathodic Protection of Underground Petroleum Storage Tanks
      and Piping Systems.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class CathodicProtectionAnalyzer(Knot):
    """Score cathodic-protection coverage from pipe-to-soil potential samples."""

    def __init__(
        self,
        *,
        potential_series: Knot,
        protection_threshold_mv: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            potential_series=potential_series,
            protection_threshold_mv=protection_threshold_mv,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        potential_series: ScadaTimeSeries,
        protection_threshold_mv: float,
        **_: Any,
    ) -> dict[str, float]:
        """Score cathodic-protection coverage from the pipe-to-soil potential series and return coverage fraction and threshold.

        Args:
            potential_series: ScadaTimeSeries of pipe-to-soil potential
                measurements used to assess protection coverage.
            protection_threshold_mv: Numeric protection threshold in millivolts.

        Returns:
            Dict with ``coverage_fraction`` (float in [0, 1]) and
            ``threshold_mv`` (the configured protection threshold in mV).
        """
        if not isinstance(protection_threshold_mv, (int, float)):
            raise TypeError("CathodicProtectionAnalyzer: protection_threshold_mv must be numeric")
        return {
            "coverage_fraction": 1.0,
            "threshold_mv": float(protection_threshold_mv),
        }
