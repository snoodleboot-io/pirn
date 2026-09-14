"""``ClockDriftCorrector`` — compensate for clock drift between synchronized sources.

Algorithm:
    1. Receive the input signal frame, reference_rate_hz, and measured_rate_hz.
    2. Validate both rates (positive floats).
    3. Compute the exact drift ratio reference_rate_hz / measured_rate_hz from the
       rates' decimal values (``1000 / 1000.4 = 2500 / 2501``) — never from their
       integer parts, which would erase a sub-hertz drift entirely.
    4. Resample by that ratio (``PolyResampling.resample_rate``): polyphase when the
       reduced factors are small, bandlimited interpolation at the exact ratio when a
       parts-per-million drift would need factors in the millions.
    5. Return a SignalPayload at the reference rate with corrected sample count.

Math:
    Drift correction ratio:

    $$\\alpha = \\frac{f_{\\text{ref}}}{f_{\\text{meas}}}$$

    Corrected sample count:

    $$N_{\\text{out}} = \\left\\lceil N_{\\text{in}} \\cdot \\alpha \\right\\rceil$$

References:
    - Zhu, W. et al. (2005). "Clock drift estimation and compensation for WSN time synchronization."
      IEEE SECON, 54-64.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.resampling._poly_resampling import PolyResampling
from pirn_signal.types.signal_payload import SignalPayload


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

        result = await asyncio.to_thread(
            PolyResampling.resample_rate,
            signal.data,
            float(measured_rate_hz),
            float(reference_rate_hz),
        )

        return signal.derive(
            "drift_corrected",
            result,
            sample_rate_hz=float(reference_rate_hz),
        )
