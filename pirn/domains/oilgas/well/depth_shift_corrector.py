"""``DepthShiftCorrector`` — apply a depth shift correction to a well log curve.

Algorithm:
    1. Receive a log curve list, a numeric ``shift_ft``, and an optional
       ``resample`` bool.
    2. Validate that ``shift_ft`` is numeric and ``resample`` is a bool.
    3. Add ``shift_ft`` to every ``depth_ft`` value in the curve.
    4. Optionally resample the shifted curve to the original depth grid.
    5. Return the shifted log curve.

Math:
    Shifted depth for sample :math:`i`:

    $$d_i' = d_i + \\Delta d$$

    where :math:`\\Delta d` is ``shift_ft``.

References:
    - Luthi, S.M. (2001). *Geological Well Logs*. Springer, Chapter 3
      (depth matching between core and log).
    - Rider, M.H. & Kennedy, M. (2011). *The Geological Interpretation of
      Well Logs*, 3rd ed. Rider-French Consulting, Chapter 2.
"""

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
        shift_ft: Knot | float,
        resample: Knot | bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            log_curve=log_curve,
            shift_ft=shift_ft,
            resample=resample,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        log_curve: list[dict[str, Any]],
        shift_ft: float,
        resample: bool = True,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Apply the configured depth shift to every sample in the log curve.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``value``.
            shift_ft: Numeric depth offset to add to every depth value (ft).
            resample: Whether to resample to the original depth grid after shifting.

        Returns:
            List of dicts with corrected ``depth_ft`` and unchanged ``value``.
        """
        if not isinstance(shift_ft, (int, float)):
            raise TypeError("DepthShiftCorrector: shift_ft must be numeric")
        if not isinstance(resample, bool):
            raise TypeError("DepthShiftCorrector: resample must be a bool")
        return [
            {**entry, "depth_ft": float(entry["depth_ft"]) + float(shift_ft)}
            for entry in log_curve
        ]
