"""``FFTAnalyzer`` — forward FFT producing a one-sided complex spectrum.

Algorithm:
    1. Receive the input signal payload and n_fft.
    2. Validate n_fft (positive integer, power of two for radix-2 FFT).
    3. Apply ``np.fft.rfft`` to produce the one-sided complex spectrum.
    4. Return a SpectrumPayload with frequency_bins = n_fft // 2 + 1.

Math:
    Discrete Fourier transform:

    $$X[k] = \\sum_{n=0}^{N-1} x[n] e^{-j 2\\pi k n / N}, \\quad k = 0, 1, \\ldots, N/2$$

    Frequency resolution:

    $$\\Delta f = \\frac{f_s}{N}$$

References:
    - Cooley, J.W. & Tukey, J.W. (1965). "An algorithm for the machine computation of complex
      Fourier series." Math. Comp., 19(90), 297-301.
    - scipy.fft: https://docs.scipy.org/doc/scipy/reference/fft.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload


class FFTAnalyzer(Knot):
    """Forward FFT of a signal producing a one-sided complex spectrum."""

    def __init__(
        self,
        *,
        signal: Knot,
        n_fft: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            n_fft=n_fft,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        n_fft: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Compute the forward FFT of the signal and return a SpectrumPayload.

        Args:
            signal: Signal payload to transform into the frequency domain.
            n_fft: FFT size (positive integer, must be a power of two).

        Returns:
            SpectrumPayload with complex spectrum and ``frequency_bins`` equal to ``n_fft // 2 + 1``.

        Raises:
            ValueError: If n_fft is not a positive power-of-two integer.
        """
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("FFTAnalyzer: n_fft must be a positive integer")
        if n_fft & (n_fft - 1) != 0:
            raise ValueError("FFTAnalyzer: n_fft must be a power of two for radix-2 FFT")

        spectrum = await asyncio.to_thread(np.fft.rfft, signal.data, n=n_fft, axis=-1)
        freq_bins = n_fft // 2 + 1
        freq_res = signal.frame.sample_rate_hz / n_fft if signal.frame.sample_rate_hz > 0 else 0.0

        return SpectrumPayload(
            frame=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=spectrum,
        )
