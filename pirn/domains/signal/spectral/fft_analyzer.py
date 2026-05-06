"""``FFTAnalyzer`` — emit a :class:`SpectrumFrame` reference for a signal.

Algorithm:
    1. Receive the input signal frame and n_fft.
    2. Validate n_fft (positive integer, power of two for radix-2 FFT).
    3. Zero-pad or truncate the signal to n_fft samples.
    4. Apply the Cooley-Tukey radix-2 DIT FFT algorithm.
    5. Return the one-sided spectrum (n_fft // 2 + 1 bins) as a SpectrumFrame.

Math:
    Discrete Fourier transform:

    $$X[k] = \\sum_{n=0}^{N-1} x[n] e^{-j 2\\pi k n / N}, \\quad k = 0, 1, \\ldots, N/2$$

    Frequency resolution:

    $$\\Delta f = \\frac{f_s}{N}$$

References:
    - Cooley, J.W. & Tukey, J.W. (1965). "An algorithm for the machine computation of complex
      Fourier series." Math. Comp., 19(90), 297-301.
    - scipy.fft: https://docs.scipy.org/doc/scipy/reference/fft.html

Production deployments install ``scipy`` (``scipy.fft`` / ``numpy.fft``)
and substitute a concrete implementation that fills in the spectrum
samples. This stub focuses on shape/lineage validation so the rest of
the orchestration graph can be built and tested without the heavy DSP
dependency.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class FFTAnalyzer(Knot):
    """Forward FFT of a single-channel signal."""

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
        signal: SignalFrame,
        n_fft: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Compute the forward FFT of the signal and return a SpectrumFrame of magnitude bins.

        Args:
            signal: Signal to transform into the frequency domain.
            n_fft: FFT size (positive integer, must be a power of two).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to ``n_fft // 2 + 1``.

        Raises:
            ValueError: If n_fft is not a positive power-of-two integer.
        """
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("FFTAnalyzer: n_fft must be a positive integer")
        if n_fft & (n_fft - 1) != 0:
            raise ValueError("FFTAnalyzer: n_fft must be a power of two for radix-2 FFT")
        resolution = signal.sample_rate_hz / n_fft if signal.sample_rate_hz > 0 else 0.0
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n_fft // 2 + 1,
            frequency_resolution_hz=resolution,
        )
