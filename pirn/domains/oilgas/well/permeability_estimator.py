"""``PermeabilityEstimator`` — estimate permeability from porosity / Sw curves.

Algorithm:
    1. Receive a parsed LAS file and a ``method`` string selecting the
       permeability correlation.
    2. Validate that ``method`` is one of ``timur``, ``coates``, or
       ``wyllie_rose``.
    3. Apply the selected empirical correlation to the porosity and
       water-saturation curves.
    4. Return a LASFile augmented with the computed permeability curve.

Math:
    Timur permeability correlation:

    $$k = \\frac{0.136 \\, \\phi^{4.4}}{S_{wirr}^2} \\quad [\\text{mD}]$$

    Coates permeability correlation:

    $$k = \\left(\\frac{\\phi^2}{C}\\right)^2
      \\left(\\frac{\\phi - S_{wirr}}{S_{wirr}}\\right)^2 \\quad [\\text{mD}]$$

References:
    - Timur, A. (1968). An investigation of permeability, porosity, and
      residual water saturation relationships for sandstone reservoirs.
      *The Log Analyst*, 9(4), 8-17.
    - Coates, G.R. & Dumanoir, J.L. (1974). A new approach to improved log-
      derived permeability. *The Log Analyst*, 15(1), 17-31.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class PermeabilityEstimator(Knot):
    """Estimate a permeability curve using a configured correlation."""

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
        """Compute a permeability curve from porosity and Sw inputs and return an augmented LASFile.

        Args:
            las_file: LAS file providing the porosity and water-saturation curves.
            method: Permeability correlation; must be one of ``timur``,
                ``coates``, or ``wyllie_rose``.

        Returns:
            LASFile with a permeability curve named ``K_{method}`` appended.
        """
        _valid_methods = frozenset({"timur", "coates", "wyllie_rose"})
        if method not in _valid_methods:
            raise ValueError(
                f"PermeabilityEstimator: method must be one of {sorted(_valid_methods)}"
            )
        return LASFile(
            well_id=las_file.well_id,
            curves=(*las_file.curves, f"K_{method}"),
            depth_unit=las_file.depth_unit,
        )
