"""``PeriodogramEstimator`` — classical periodogram (squared FFT magnitude).

Algorithm:
    1. Receive the input signal payload and window.
    2. Validate window (non-empty string naming a scipy window function).
    3. Apply ``scipy.signal.periodogram`` to estimate the PSD.
    4. Return a SpectrumPayload with the power spectral density estimate.

Math:
    Windowed periodogram:

    $$\\hat{P}(f_k) = \\frac{1}{N \\|w\\|^2} \\left| \\sum_{n=0}^{N-1} x[n] w[n] e^{-j2\\pi k n/N} \\right|^2$$

References:
    - Schuster, A. (1898). "On the investigation of hidden periodicities." Terrestrial Magnetism, 3(1), 13-41.
    - scipy.signal.periodogram: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


class PeriodogramEstimator(Knot):
    """Single-block periodogram PSD estimator."""

    def __init__(
        self,
        *,
        signal: Knot,
        window: Knot | str = "hann",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window=window,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        window: str = "hann",
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the single-block periodogram PSD and return a SpectrumPayload.

        Args:
            signal: Signal payload to compute the classical periodogram power spectral density from.
            window: Window function name (non-empty string, e.g., ``hann``, ``hamming``).

        Returns:
            SpectrumPayload with PSD data and frequency_bins = len(freqs).

        Raises:
            ValueError: If window is not a non-empty string.
        """
        if not isinstance(window, str) or not window:
            raise ValueError("PeriodogramEstimator: window must be a non-empty string")

        freqs, pxx = await asyncio.to_thread(
            ss.periodogram,
            signal.data,
            fs=signal.frame.sample_rate_hz,
            window=window,
            axis=-1,
        )

        freq_bins = len(freqs)

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=float(freqs[1]) if freq_bins > 1 else 0.0,
            ),
            data=pxx,
        )
