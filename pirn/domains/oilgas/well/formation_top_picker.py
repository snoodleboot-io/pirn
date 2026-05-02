"""``FormationTopPicker`` — pick a single formation top from a LAS file."""

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
        formation_name: str,
        depth_md: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._formation_name = formation_name
        self._depth_md = float(depth_md)
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> FormationTop:
        return FormationTop(
            well_id=las_file.well_id,
            formation_name=self._formation_name,
            depth_md=self._depth_md,
        )
