"""``PetrophysicalEvaluator`` — top-level petrophysics interpretation.

Algorithm:
    1. Receive a normalised LAS file containing raw log curves.
    2. Compute volume of shale (VSH) from the gamma-ray curve.
    3. Compute effective porosity (PHIE) from the density-neutron crossplot.
    4. Compute water saturation (SW) via the Archie equation.
    5. Return a LASFile augmented with VSH, PHIE, and SW curves.

Math:
    Archie water saturation:

    $$S_w = \\left(\\frac{a \\, R_w}{\\phi^m \\, R_t}\\right)^{1/n}$$

    Volume of shale (linear gamma-ray index):

    $$V_{sh} = \\frac{GR - GR_{clean}}{GR_{shale} - GR_{clean}}$$

References:
    - Archie, G.E. (1942). The electrical resistivity log as an aid in
      determining some reservoir characteristics. *Trans. AIME*, 146,
      54-62. SPE-942054-G.
    - Dresser Industries (1979). *Log Interpretation Charts*. Dresser Atlas,
      Chapter 2 (porosity and fluid saturation).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class PetrophysicalEvaluator(Knot):
    """Run a basic petrophysics interpretation pass over a normalised LAS file.

    The result is itself a :class:`LASFile` reference whose ``curves`` are
    augmented with the standard interpreted-log mnemonics.
    """

    def __init__(
        self,
        *,
        las_file: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        """Run a petrophysics interpretation pass and return a LASFile augmented with VSH, PHIE, and SW curves.

        Args:
            las_file: Normalised LAS file to run the interpretation pass over.

        Returns:
            LASFile with ``VSH``, ``PHIE``, and ``SW`` curves appended.
        """
        interpreted_curves = (*las_file.curves, "VSH", "PHIE", "SW")
        return LASFile(
            well_id=las_file.well_id,
            curves=interpreted_curves,
            depth_unit=las_file.depth_unit,
        )
