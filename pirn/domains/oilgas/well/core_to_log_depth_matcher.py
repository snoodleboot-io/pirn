"""``CoreToLogDepthMatcher`` — match core sample depths to wireline log depths accounting for depth shift."""

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
        max_shift_ft: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_shift_ft, (int, float)):
            raise TypeError("CoreToLogDepthMatcher: max_shift_ft must be numeric")
        if max_shift_ft <= 0:
            raise ValueError("CoreToLogDepthMatcher: max_shift_ft must be positive")
        self._max_shift_ft = float(max_shift_ft)
        super().__init__(core_data=core_data, log_data=log_data, _config=_config, **kwargs)

    async def process(
        self,
        core_data: list[dict[str, Any]],
        log_data: list[dict[str, Any]],
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Match each core sample depth to the nearest log depth within max_shift_ft.

        Args:
            core_data: List of dicts with ``depth_ft`` and ``value``.
            log_data: List of dicts with ``depth_ft`` and ``value``.

        Returns:
            List of dicts with ``core_depth_ft``, ``matched_log_depth_ft``,
            ``shift_ft``, and ``value``.
        """
        results: list[dict[str, Any]] = []
        log_depths = [float(l["depth_ft"]) for l in log_data]
        for sample in core_data:
            core_depth = float(sample["depth_ft"])
            if not log_depths:
                continue
            matched_depth = min(log_depths, key=lambda d: abs(d - core_depth))
            shift = matched_depth - core_depth
            if abs(shift) <= self._max_shift_ft:
                results.append(
                    {
                        "core_depth_ft": core_depth,
                        "matched_log_depth_ft": matched_depth,
                        "shift_ft": shift,
                        "value": sample.get("value"),
                    }
                )
        return results
