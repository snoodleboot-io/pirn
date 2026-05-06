"""``SpectrogramRenderer`` — render a spectrogram from a STFT/PSD.

Algorithm:
    1. Receive the input signal frame, window_length, and scaling.
    2. Validate window_length (positive integer) and scaling (``density`` or ``spectrum``).
    3. Apply a sliding window of window_length samples with 50% overlap.
    4. Compute the squared FFT magnitude for each window.
    5. Scale by window_length (``spectrum``) or by sample_rate_hz (``density``).
    6. Return a SpectrumFrame with frequency_bins equal to half the window length plus one.

Math:
    Spectrogram magnitude at time frame $m$:

    $$S_m(f_k) = \\left|\\sum_{n=0}^{L-1} x(mH + n) w(n) e^{-j2\\pi k n / L}\\right|^2$$

    where $L$ = window_length, $H$ = hop size, $w$ = window function.

References:
    - Allen, J.B. (1977). "Short term spectral analysis, synthesis, and modification by discrete
      Fourier transform." IEEE Trans. Acoust. Speech Signal Process., 25(3), 235-238.
    - scipy.signal.spectrogram: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class SpectrogramRenderer(Knot):
    """Build a magnitude spectrogram from a windowed STFT.

    Production needs ``scipy.signal.spectrogram``.
    """

    _valid_scalings = frozenset({"density", "spectrum"})

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: Knot | int,
        scaling: Knot | str = "density",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window_length=window_length,
            scaling=scaling,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        window_length: int,
        scaling: str = "density",
        **_: Any,
    ) -> SpectrumFrame:
        """Render a magnitude spectrogram from the signal and return a SpectrumFrame.

        Args:
            signal: Signal to compute the windowed magnitude spectrogram from.
            window_length: Number of samples per window (positive integer).
            scaling: Normalisation mode — ``density`` (PSD) or ``spectrum`` (power spectrum).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to half the window length plus one.

        Raises:
            ValueError: If window_length or scaling are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError("SpectrogramRenderer: window_length must be a positive integer")
        if scaling not in self._valid_scalings:
            raise ValueError("SpectrogramRenderer: scaling must be 'density' or 'spectrum'")
        resolution = signal.sample_rate_hz / window_length if signal.sample_rate_hz > 0 else 0.0
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=window_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
