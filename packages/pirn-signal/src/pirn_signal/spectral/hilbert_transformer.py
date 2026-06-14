"""``HilbertTransformer`` — analytic-signal construction via the Hilbert transform.

Algorithm:
    1. Receive the input signal payload.
    2. Apply ``scipy.signal.hilbert`` to compute the analytic (complex) signal.
    3. Return a SpectrumPayload with the complex analytic signal.

Math:
    Hilbert transform:

    $$\\hat{x}(t) = \\frac{1}{\\pi} \\text{P.V.} \\int_{-\\infty}^{\\infty} \\frac{x(\\tau)}{t - \\tau} d\\tau$$

    Analytic signal:

    $$x_a(t) = x(t) + j\\hat{x}(t)$$

References:
    - Gabor, D. (1946). "Theory of communication." J. IEE, 93(26), 429-457.
    - scipy.signal.hilbert: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.hilbert.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


class HilbertTransformer(Knot):
    """Compute the analytic signal (90-degree phase shift via FFT)."""

    def __init__(
        self,
        *,
        signal: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, _config=_config, **kwargs)

    async def process(self, signal: SignalPayload, **_: Any) -> SpectrumPayload:
        """Compute the analytic signal via the Hilbert transform and return a SpectrumPayload.

        Args:
            signal: Real-valued signal payload to convert to its analytic (complex) representation.

        Returns:
            SpectrumPayload with complex analytic signal and frequency_bins = samples_per_channel.
        """
        analytic: np.ndarray = await asyncio.to_thread(ss.hilbert, signal.data, axis=-1)  # type: ignore[assignment]
        freq_bins = signal.frame.samples_per_channel
        freq_res = (
            signal.frame.sample_rate_hz / freq_bins
            if freq_bins > 0 and signal.frame.sample_rate_hz > 0
            else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=f"{signal.frame.signal_id}:analytic",
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=analytic,
        )
