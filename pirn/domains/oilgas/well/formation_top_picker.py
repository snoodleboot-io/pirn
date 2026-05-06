"""``FormationTopPicker`` — pick a single formation top from a LAS file.

Algorithm:
    1. Receive a parsed LAS file, a non-empty ``formation_name`` string, and
       a non-negative ``depth_md`` measured depth.
    2. Validate that ``formation_name`` is non-empty, ``depth_md`` is numeric
       and non-negative.
    3. Register the formation top at the specified measured depth within the
       well.
    4. Return a FormationTop referencing the well, formation name, and depth.


References:
    - North American Stratigraphic Code (2005). *AAPG Bulletin*, 89(11),
      1547-1591 (formation nomenclature and correlation).
    - Vail, P.R. et al. (1977). Seismic stratigraphy and global changes of
      sea level. *AAPG Memoir 26*, Chapter 1 (stratigraphic surface picking).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.formation_top import FormationTop
from pirn.domains.oilgas.types.las_file import LASFile


class FormationTopPicker(Knot):
    """Pick one formation top at a configured measured depth."""

    def __init__(
        self,
        *,
        las_file: Knot,
        formation_name: Knot | str,
        depth_md: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            las_file=las_file,
            formation_name=formation_name,
            depth_md=depth_md,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        las_file: LASFile,
        formation_name: str,
        depth_md: float,
        **_: Any,
    ) -> FormationTop:
        """Accept a parsed LAS file and return a FormationTop at the configured depth.

        Args:
            las_file: Parsed LAS file providing well identity and depth context.
            formation_name: Non-empty name identifying the formation top.
            depth_md: Non-negative measured depth of the formation top (ft or m).

        Returns:
            FormationTop at the configured measured depth and formation name.
        """
        if not isinstance(formation_name, str) or not formation_name:
            raise ValueError(
                "FormationTopPicker: formation_name must be a non-empty string"
            )
        if not isinstance(depth_md, (int, float)):
            raise TypeError(
                "FormationTopPicker: depth_md must be numeric"
            )
        if depth_md < 0.0:
            raise ValueError(
                "FormationTopPicker: depth_md must be non-negative"
            )
        return FormationTop(
            well_id=las_file.well_id,
            formation_name=formation_name,
            depth_md=float(depth_md),
        )
