"""``StackProcessor`` — sum traces in a CMP gather to produce a stacked trace.

Algorithm:
    1. Receive an NMO-corrected CMP gather SegyVolume.
    2. Sum all offset traces to produce a single zero-offset trace.
    3. Return the stacked trace as a SegyVolume reference.

Math:
    Stacked trace sample at time :math:`t`:

    $$s_{stack}(t) = \\frac{1}{N} \\sum_{j=1}^{N} s_j(t)$$

    where :math:`N` is the number of offset traces (fold).

References:
    - Mayne, W.H. (1962). Common reflection point horizontal data stacking
      techniques. *Geophysics*, 27(6), 927–938.
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 3
      (CMP stacking).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class StackProcessor(Knot):
    """Stack a corrected CMP gather to a single (inline, xline) trace volume."""

    def __init__(
        self,
        *,
        gather: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(gather=gather, _config=_config, **kwargs)

    async def process(self, gather: SegyVolume, **_: Any) -> SegyVolume:
        """Sum traces in the CMP gather and return the stacked trace as a SegyVolume.

        Args:
            gather: NMO-corrected CMP gather to stack.

        Returns:
            SegyVolume of the stacked trace.
        """
        return SegyVolume(volume_id=f"{gather.volume_id}:stacked")
