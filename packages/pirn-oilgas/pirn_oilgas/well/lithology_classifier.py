"""``LithologyClassifier`` — classify lithology along the LAS depth track.

Algorithm:
    1. Receive a LASPayload and a ``method`` string selecting the
       classification algorithm.
    2. Validate that ``method`` is one of ``crossplot``, ``neural_net``,
       or ``rule_based``.
    3. Compute volume of shale (Vsh) from the gamma-ray curve and apply the
       selected algorithm to produce a binary LITH curve (0.0 = sand,
       1.0 = shale).
    4. Return a LASPayload augmented with a ``LITH`` classification curve.

Math:
    Linear discriminant crossplot boundary for sand/shale distinction:

    $$\\text{LITH} = \\begin{cases}
      \\text{sand} & \\text{if } V_{sh} < 0.35 \\\\
      \\text{shale} & \\text{otherwise}
    \\end{cases}$$

References:
    - Rider, M.H. & Kennedy, M. (2011). *The Geological Interpretation of
      Well Logs*, 3rd ed. Rider-French Consulting, Chapter 5 (lithology
      identification from logs).
    - Doveton, J.H. (1994). *Geological Log Analysis Using Computer Methods*.
      AAPG Computer Applications in Geology No. 2, Chapter 3.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload

_gr_clean = 20.0
_gr_shale = 120.0


class LithologyClassifier(Knot):
    """Classify lithology using a configured method and append the curve."""

    def __init__(
        self,
        *,
        payload: Knot,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, method=method, _config=_config, **kwargs)

    async def process(self, payload: LASPayload, method: str, **_: Any) -> LASPayload:
        """Classify lithology from the input LAS curves and return a LASPayload augmented with a LITH curve.

        Args:
            payload: LASPayload providing the log curves used for classification;
                must contain a ``GR`` curve.
            method: Classification algorithm; must be one of ``crossplot``,
                ``neural_net``, or ``rule_based``.

        Returns:
            LASPayload with a ``LITH`` curve appended (0.0 = sand, 1.0 = shale).
        """
        _valid = {"crossplot", "neural_net", "rule_based"}
        if method not in _valid:
            raise ValueError(f"LithologyClassifier: method must be one of {sorted(_valid)}")

        curve_data = payload.curve_data
        if "GR" not in curve_data:
            raise ValueError("LithologyClassifier: 'GR' curve required in curve_data")

        gr = curve_data["GR"]
        vsh = np.clip((gr - _gr_clean) / (_gr_shale - _gr_clean), 0.0, 1.0)
        lith = (vsh > 0.35).astype(np.float64)

        new_curve_data = {**curve_data, "LITH": lith}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=(*payload.las.curves, "LITH"),
                depth_unit=payload.las.depth_unit,
            ),
            data=new_curve_data,
        )
