"""``CoreToLogDepthMatcher`` — match core sample depths to wireline log depths accounting for depth shift.

Algorithm:
    1. Receive core sample data, wireline log data, and a positive
       ``max_shift_ft`` tolerance.
    2. Validate that ``max_shift_ft`` is a positive number.
    3. For each core sample, find the nearest log depth using a linear scan.
    4. Accept the match only if ``|shift| <= max_shift_ft``.
    5. Return a list of matched records with depth shift values.

Math:
    Depth shift for core sample :math:`i` matched to log depth
    :math:`d_j^*`:

    $$\\Delta d_i = d_j^* - d_i^{core}, \\quad
      d_j^* = \\arg\\min_j |d_j^{log} - d_i^{core}|$$

References:
    - Doveton, J.H. (1994). *Theory and Applications of Vertical Variability
      Measures from Markov Chain Analysis*. KGS Bulletin, Chapter 1 (core-log
      depth matching).
    - Luthi, S.M. (2001). *Geological Well Logs*. Springer, Chapter 3
      (core-log integration).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CoreToLogDepthMatcher(Knot):
    """Match core samples to the nearest wireline log depth within a maximum permitted shift."""

    def __init__(
        self,
        *,
        core_data: Knot,
        log_data: Knot,
        max_shift_ft: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            core_data=core_data,
            log_data=log_data,
            max_shift_ft=max_shift_ft,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        core_data: list[dict[str, Any]],
        log_data: list[dict[str, Any]],
        max_shift_ft: float,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Match each core sample depth to the nearest log depth within max_shift_ft.

        Args:
            core_data: List of dicts with ``depth_ft`` and ``value``.
            log_data: List of dicts with ``depth_ft`` and ``value``.
            max_shift_ft: Positive maximum acceptable depth shift in feet.

        Returns:
            List of dicts with ``core_depth_ft``, ``matched_log_depth_ft``,
            ``shift_ft``, and ``value``.
        """
        if not isinstance(max_shift_ft, (int, float)):
            raise TypeError("CoreToLogDepthMatcher: max_shift_ft must be numeric")
        if max_shift_ft <= 0:
            raise ValueError("CoreToLogDepthMatcher: max_shift_ft must be positive")
        results: list[dict[str, Any]] = []
        log_depths = [float(entry["depth_ft"]) for entry in log_data]
        for sample in core_data:
            core_depth = float(sample["depth_ft"])
            if not log_depths:
                continue
            matched_depth = min(log_depths, key=lambda d: abs(d - core_depth))
            shift = matched_depth - core_depth
            if abs(shift) <= float(max_shift_ft):
                results.append(
                    {
                        "core_depth_ft": core_depth,
                        "matched_log_depth_ft": matched_depth,
                        "shift_ft": shift,
                        "value": sample.get("value"),
                    }
                )
        return results
