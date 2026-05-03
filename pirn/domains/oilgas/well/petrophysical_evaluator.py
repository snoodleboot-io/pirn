"""``PetrophysicalEvaluator`` — top-level petrophysics interpretation."""

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
        interpreted_curves = las_file.curves + ("VSH", "PHIE", "SW")
        return LASFile(
            well_id=las_file.well_id,
            curves=interpreted_curves,
            depth_unit=las_file.depth_unit,
        )
