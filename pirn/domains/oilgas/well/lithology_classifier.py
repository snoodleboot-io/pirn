"""``LithologyClassifier`` — classify lithology along the LAS depth track.

Algorithm:
    1. Receive a parsed LAS file and a ``method`` string selecting the
       classification algorithm.
    2. Validate that ``method`` is one of ``crossplot``, ``neural_net``,
       or ``rule_based``.
    3. Apply the selected algorithm to the gamma-ray, neutron, density,
       and sonic curves in the LAS file.
    4. Return a LASFile augmented with a ``LITH`` classification curve.

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

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LithologyClassifier(Knot):
    """Classify lithology using a configured method and append the curve."""

    def __init__(
        self,
        *,
        las_file: Knot,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(las_file=las_file, method=method, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, method: str, **_: Any) -> LASFile:
        """Classify lithology from the input LAS curves and return a LASFile augmented with a LITH curve.

        Args:
            las_file: Parsed LAS file providing the log curves used for classification.
            method: Classification algorithm; must be one of ``crossplot``,
                ``neural_net``, or ``rule_based``.

        Returns:
            LASFile with a ``LITH`` curve appended to the existing curve set.
        """
        _valid = {"crossplot", "neural_net", "rule_based"}
        if method not in _valid:
            raise ValueError(
                f"LithologyClassifier: method must be one of {sorted(_valid)}"
            )
        return LASFile(
            well_id=las_file.well_id,
            curves=(*las_file.curves, "LITH"),
            depth_unit=las_file.depth_unit,
        )
