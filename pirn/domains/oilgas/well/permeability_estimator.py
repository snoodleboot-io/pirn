"""``PermeabilityEstimator`` — estimate permeability from porosity / Sw curves."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class PermeabilityEstimator(Knot):
    """Estimate a permeability curve using a configured correlation."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"timur", "coates", "wyllie_rose"}
    )

    def __init__(
        self,
        *,
        las_file: Knot,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"PermeabilityEstimator: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves + (f"K_{self._method}",),
            depth_unit=las_file.depth_unit,
        )
