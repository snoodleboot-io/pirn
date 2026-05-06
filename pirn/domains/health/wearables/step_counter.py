"""``StepCounter`` — derive step count from accelerometer data.

Production version uses peak detection over filtered acceleration
magnitude. This stub returns 0 so downstream logic can be wired.

Algorithm:
    1. Receive signal (SignalFrame) and threshold float.
    2. Validate signal is a SignalFrame and threshold is non-negative.
    3. Compute the acceleration magnitude envelope from the tri-axial signal.
    4. Detect peaks above the threshold using a windowed peak finder.
    5. Return the total number of detected peaks as the step count.

Math:
    Acceleration magnitude:

    $$a = \\sqrt{a_x^2 + a_y^2 + a_z^2}$$

References:
    - Weinberg, H. (2002). Using the ADXL202 in Pedometer and Personal Navigation Applications.
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
        signal: Knot | SignalFrame,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        signal: SignalFrame,
        threshold: float,
        **_: Any,
    ) -> int:
        """Count steps by detecting acceleration peaks above the threshold.

        Args:
            signal: SignalFrame containing the tri-axial accelerometer recording.
            threshold: Minimum peak height threshold (must be >= 0).

        Returns:
            Total number of steps detected in the accelerometer signal.

        Raises:
            TypeError: If signal is not a SignalFrame.
            ValueError: If threshold is negative.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("StepCounter: signal must be a SignalFrame")
        if not isinstance(threshold, (int, float)) or float(threshold) < 0:
            raise ValueError("StepCounter: threshold must be a non-negative number")
        return 0
