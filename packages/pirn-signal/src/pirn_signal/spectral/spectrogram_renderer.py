"""``SpectrogramRenderer`` — render a spectrogram from a STFT/PSD.

Algorithm:
    1. Receive the input signal payload, window_length, overlap, and scaling.
    2. Validate window_length (positive integer) and scaling (``density`` or ``spectrum``).
    3. Apply ``scipy.signal.spectrogram`` to compute the time-frequency power matrix.
    4. Return a SpectrumPayload with Sxx as data and frequency_bins = len(freqs).

Math:
    Spectrogram magnitude at time frame $m$:

    $$S_m(f_k) = \\left|\\sum_{n=0}^{L-1} x(mH + n) w(n) e^{-j2\\pi k n / L}\\right|^2$$

References:
    - Allen, J.B. (1977). "Short term spectral analysis, synthesis, and modification by discrete
      Fourier transform." IEEE Trans. Acoust. Speech Signal Process., 25(3), 235-238.
    - scipy.signal.spectrogram: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html
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


class SpectrogramRenderer(Knot):
    """Build a magnitude spectrogram from a windowed STFT."""

    _valid_scalings = frozenset({"density", "spectrum"})

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: Knot | int,
        overlap: Knot | int = 0,
        scaling: Knot | str = "density",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window_length=window_length,
            overlap=overlap,
            scaling=scaling,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        window_length: int,
        overlap: int = 0,
        scaling: str = "density",
        **_: Any,
    ) -> SpectrumPayload:
        """Render a magnitude spectrogram from the signal and return a SpectrumPayload.

        Args:
            signal: Signal payload to compute the windowed magnitude spectrogram from.
            window_length: Number of samples per window (positive integer).
            overlap: Number of overlapping samples between windows (non-negative integer).
            scaling: Normalisation mode — ``density`` (PSD) or ``spectrum`` (power spectrum).

        Returns:
            SpectrumPayload with Sxx data and ``frequency_bins`` equal to len(freqs).

        Raises:
            ValueError: If window_length or scaling are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError("SpectrogramRenderer: window_length must be a positive integer")
        if scaling not in self._valid_scalings:
            raise ValueError("SpectrogramRenderer: scaling must be 'density' or 'spectrum'")

        freqs, _, sxx = await asyncio.to_thread(
            ss.spectrogram,
            signal.data,
            fs=signal.frame.sample_rate_hz,
            window="hann",
            nperseg=window_length,
            noverlap=overlap,
            scaling=scaling,
            axis=-1,
        )

        freq_bins = len(freqs)
        freq_res = (
            signal.frame.sample_rate_hz / window_length if signal.frame.sample_rate_hz > 0 else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=sxx,
        )
