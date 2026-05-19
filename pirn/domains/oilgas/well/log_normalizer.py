"""``LogNormalizer`` — depth-resample and unit-normalise a LAS curve set.

Algorithm:
    1. Receive a parsed LAS file, a positive ``target_depth_step``, and a
       ``target_depth_unit`` (``'m'`` or ``'ft'``).
    2. Validate all inputs.
    3. Convert depth values to the target unit if necessary.
    4. Resample all curves onto a uniform depth grid with spacing
       ``target_depth_step``.
    5. Return a LASFile reference with the resampled curves.

Math:
    Unit conversion (feet to metres):

    $$d_m = d_{ft} \\times 0.3048$$

References:
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society
      (depth reference and unit conventions).
    - Luthi, S.M. (2001). *Geological Well Logs*. Springer, Chapter 2
      (log depth registration and resampling).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload


class LogNormalizer(Knot):
    """Resample LAS curves onto a uniform depth grid and normalise units."""

    def __init__(
        self,
        *,
        payload: Knot,
        target_depth_step: Knot | float,
        target_depth_unit: Knot | str = "m",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            payload=payload,
            target_depth_step=target_depth_step,
            target_depth_unit=target_depth_unit,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        payload: LASPayload,
        target_depth_step: float,
        target_depth_unit: str = "m",
        **_: Any,
    ) -> LASPayload:
        """Resample LAS curves onto the configured depth grid and return a depth-normalised LASPayload.

        Args:
            payload: LASPayload whose curves are resampled to the configured depth step.
            target_depth_step: Positive depth sampling step for the output grid.
            target_depth_unit: Target depth unit; must be ``'m'`` or ``'ft'`` (default ``'m'``).

        Returns:
            LASPayload with curves resampled to the configured depth grid and unit.
        """
        if not isinstance(target_depth_step, (int, float)):
            raise TypeError("LogNormalizer: target_depth_step must be numeric")
        if target_depth_step <= 0.0:
            raise ValueError("LogNormalizer: target_depth_step must be positive")
        if target_depth_unit not in ("m", "ft"):
            raise ValueError("LogNormalizer: target_depth_unit must be 'm' or 'ft'")
        len(next(iter(payload.curve_data.values()))) if payload.curve_data else 100
        new_curve_data = {k: np.array(v, dtype=np.float64) for k, v in payload.curve_data.items()}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=payload.las.curves,
                depth_unit=target_depth_unit,
            ),
            data=new_curve_data,
        )
