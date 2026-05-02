"""``PorosityCalculator`` — derive a porosity curve from density / neutron logs."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class PorosityCalculator(Knot):
    """Derive a porosity curve and append it to the LAS curve set."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"density", "neutron", "density_neutron"}
    )

    def __init__(
        self,
        *,
        las_file: Knot,
        method: str,
        matrix_density: float,
        fluid_density: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"PorosityCalculator: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        for label, value in (
            ("matrix_density", matrix_density),
            ("fluid_density", fluid_density),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"PorosityCalculator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"PorosityCalculator: {label} must be positive"
                )
        if fluid_density >= matrix_density:
            raise ValueError(
                "PorosityCalculator: fluid_density must be less than "
                "matrix_density"
            )
        self._method = method
        self._matrix_density = float(matrix_density)
        self._fluid_density = float(fluid_density)
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves + (f"PHI_{self._method}",),
            depth_unit=las_file.depth_unit,
        )
