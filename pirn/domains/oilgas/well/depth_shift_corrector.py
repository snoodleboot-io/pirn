"""``DepthShiftCorrector`` — apply a depth shift correction to a well log curve."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DepthShiftCorrector(Knot):
    """Shift all depth values in a well log curve by a constant offset."""

    def __init__(
        self,
        *,
        log_curve: Knot,
        shift_ft: float,
        resample: bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(shift_ft, (int, float)):
            raise TypeError("DepthShiftCorrector: shift_ft must be numeric")
        if not isinstance(resample, bool):
            raise TypeError("DepthShiftCorrector: resample must be a bool")
        self._shift_ft = float(shift_ft)
        self._resample = resample
        super().__init__(log_curve=log_curve, _config=_config, **kwargs)

    async def process(
        self, log_curve: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Apply the configured depth shift to every sample in the log curve.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``value``.

        Returns:
            List of dicts with corrected ``depth_ft`` and unchanged ``value``.
        """
        return [
            {**entry, "depth_ft": float(entry["depth_ft"]) + self._shift_ft}
            for entry in log_curve
        ]
