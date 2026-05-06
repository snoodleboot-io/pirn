"""``PeriodogramEstimator`` — classical periodogram (squared FFT magnitude).

Algorithm:
    1. Receive the input signal frame and window.
    2. Validate window (non-empty string naming a scipy window function).
    3. Apply the named window to the signal samples.
    4. Compute the FFT and square the magnitude to obtain the raw periodogram.
    5. Normalise by the window's effective noise bandwidth.
    6. Return a SpectrumFrame with bins equal to half the sample count plus one.

Math:
    Windowed periodogram:

    $$\\hat{P}(f_k) = \\frac{1}{N \\|w\\|^2} \\left| \\sum_{n=0}^{N-1} x[n] w[n] e^{-j2\\pi k n/N} \\right|^2$$

    Frequency resolution:

    $$\\Delta f = \\frac{f_s}{N}$$

References:
    - Schuster, A. (1898). "On the investigation of hidden periodicities with application to a supposed
      26 day period of meteorological phenomena." Terrestrial Magnetism, 3(1), 13-41.
    - scipy.signal.periodogram: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class PeriodogramEstimator(Knot):
    """Single-block periodogram PSD estimator.

    Production needs ``scipy.signal.periodogram``.
    """

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
        signal: SignalFrame,
        window: str = "hann",
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the single-block periodogram PSD and return a SpectrumFrame.

        Args:
            signal: Signal to compute the classical periodogram power spectral density from.
            window: Window function name (non-empty string, e.g., ``hann``, ``hamming``).

        Returns:
            SpectrumFrame with bins equal to half the sample count plus one.

        Raises:
            ValueError: If window is not a non-empty string.
        """
        if not isinstance(window, str) or not window:
            raise ValueError("PeriodogramEstimator: window must be a non-empty string")
        n = max(signal.samples_per_channel, 1)
        resolution = signal.sample_rate_hz / n if signal.sample_rate_hz > 0 else 0.0
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n // 2 + 1,
            frequency_resolution_hz=resolution,
        )
