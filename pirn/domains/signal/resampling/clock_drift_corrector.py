"""``ClockDriftCorrector`` — compensate for clock drift between synchronized sources.

Algorithm:
    1. Receive the input signal frame, reference_rate_hz, and measured_rate_hz.
    2. Validate both rates (positive floats).
    3. Compute the drift ratio: reference_rate_hz / measured_rate_hz.
    4. Apply polyphase resampling to stretch/compress the signal by the drift ratio.
    5. Return a SignalFrame at the reference rate with corrected sample count.

Math:
    Drift correction ratio:

    $$\\alpha = \\frac{f_{\\text{ref}}}{f_{\\text{meas}}}$$

    Corrected sample count:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\alpha \\right\\rfloor$$

References:
    - Zhu, W. et al. (2005). "Clock drift estimation and compensation for WSN time synchronization."
      IEEE SECON, 54-64.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

import asyncio
from math import gcd
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _resample_poly(data: np.ndarray, up: int, down: int) -> np.ndarray:
    return np.asarray(ss.resample_poly(data, up, down, axis=-1))


class ClockDriftCorrector(Knot):
    """Compensate for clock drift by resampling to the reference rate.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference_rate_hz: Knot | float,
        measured_rate_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference_rate_hz=reference_rate_hz,
            measured_rate_hz=measured_rate_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        reference_rate_hz: float,
        measured_rate_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Correct clock drift by resampling from the measured rate to the reference rate.

        Args:
            signal: Signal captured at the drifted measured rate.
            reference_rate_hz: True reference sample rate in Hz (positive float).
            measured_rate_hz: Observed (drifted) sample rate in Hz (positive float).

        Returns:
            SignalPayload resampled to the reference rate with drift corrected.

        Raises:
            ValueError: If reference_rate_hz or measured_rate_hz are not positive.
        """
        if not isinstance(reference_rate_hz, (int, float)) or reference_rate_hz <= 0:
            raise ValueError("ClockDriftCorrector: reference_rate_hz must be positive")
        if not isinstance(measured_rate_hz, (int, float)) or measured_rate_hz <= 0:
            raise ValueError("ClockDriftCorrector: measured_rate_hz must be positive")

        common = gcd(int(reference_rate_hz), int(measured_rate_hz))
        up = int(reference_rate_hz) // common
        down = int(measured_rate_hz) // common

        result = await asyncio.to_thread(_resample_poly, signal.data, up, down)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:drift_corrected",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=float(reference_rate_hz),
                samples_per_channel=result.shape[-1],
            ),
            data=result,
        )
