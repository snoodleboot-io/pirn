"""``StepCounter`` — derive step count from accelerometer data.

Production version uses peak detection over filtered acceleration
magnitude. This stub returns 0 so downstream logic can be wired.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class StepCounter(Knot):
    """Count steps from a tri-axial accelerometer signal."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("StepCounter: signal must be a SignalFrame")
        if not isinstance(threshold, (int, float)) or float(threshold) < 0:
            raise ValueError(
                "StepCounter: threshold must be a non-negative number"
            )
        self._signal = signal
        self._threshold = float(threshold)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> int:
        """Count steps by detecting acceleration peaks above the configured threshold and return the total.

        Returns:
            Total number of steps detected in the accelerometer signal.
        """
        return 0
