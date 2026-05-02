"""``WaterSaturationCalculator`` — derive a water-saturation curve."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class WaterSaturationCalculator(Knot):
    """Compute a water-saturation curve using a configured saturation model."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"archie", "simandoux", "indonesia", "waxman_smits"}
    )

    def __init__(
        self,
        *,
        las_file: Knot,
        method: str,
        rw: float,
        a: float = 1.0,
        m: float = 2.0,
        n: float = 2.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"WaterSaturationCalculator: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        for label, value in (("rw", rw), ("a", a), ("m", m), ("n", n)):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"WaterSaturationCalculator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"WaterSaturationCalculator: {label} must be positive"
                )
        self._method = method
        self._rw = float(rw)
        self._a = float(a)
        self._m = float(m)
        self._n = float(n)
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves + (f"SW_{self._method}",),
            depth_unit=las_file.depth_unit,
        )
