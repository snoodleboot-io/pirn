"""``LogNormalizer`` — depth-resample and unit-normalise a LAS curve set."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LogNormalizer(Knot):
    """Resample LAS curves onto a uniform depth grid and normalise units."""

    def __init__(
        self,
        *,
        las_file: Knot,
        target_depth_step: float,
        target_depth_unit: str = "m",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_depth_step, (int, float)):
            raise TypeError(
                "LogNormalizer: target_depth_step must be numeric"
            )
        if target_depth_step <= 0.0:
            raise ValueError(
                "LogNormalizer: target_depth_step must be positive"
            )
        if target_depth_unit not in ("m", "ft"):
            raise ValueError(
                "LogNormalizer: target_depth_unit must be 'm' or 'ft'"
            )
        self._target_depth_step = float(target_depth_step)
        self._target_depth_unit = target_depth_unit
        super().__init__(las_file=las_file, _config=_config, **kwargs)

    async def process(self, las_file: LASFile, **_: Any) -> LASFile:
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves,
            depth_unit=self._target_depth_unit,
        )
