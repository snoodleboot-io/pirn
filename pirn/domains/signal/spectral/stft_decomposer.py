"""``STFTDecomposer`` — short-time Fourier transform.

Algorithm:
    1. Receive the input signal frame, window_length, and hop_length.
    2. Validate window_length and hop_length (positive integers, hop_length <= window_length).
    3. Apply a sliding Hann window of window_length samples advanced by hop_length each step.
    4. Compute the FFT for each window position to produce a time-frequency matrix.
    5. Return a SpectrumFrame with frequency_bins equal to half the window length plus one.

Math:
    STFT:

    $$X_m(k) = \\sum_{n=0}^{L-1} x(n + mH) w(n) e^{-j2\\pi kn/L}$$

    where $L$ = window_length, $H$ = hop_length, and $w$ = analysis window.

References:
    - Allen, J.B. & Rabiner, L.R. (1977). "A unified approach to short-time Fourier analysis and synthesis."
      Proc. IEEE, 65(11), 1558-1564.
    - scipy.signal.stft: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.stft.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class STFTDecomposer(Knot):
    """Sliding-window FFT producing a time-frequency representation.

    Production needs ``scipy.signal.stft``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: Knot | int,
        hop_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window_length=window_length,
            hop_length=hop_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        window_length: int,
        hop_length: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Compute the short-time Fourier transform of the signal and return a SpectrumFrame.

        Args:
            signal: Signal to decompose into a time-frequency representation via sliding-window FFT.
            window_length: Analysis window length in samples (positive integer).
            hop_length: Hop size between successive windows in samples (positive integer,
                must not exceed window_length).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to half the window length plus one.

        Raises:
            ValueError: If window_length or hop_length are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError(
                "STFTDecomposer: window_length must be a positive integer"
            )
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "STFTDecomposer: hop_length must be a positive integer"
            )
        if hop_length > window_length:
            raise ValueError(
                "STFTDecomposer: hop_length must not exceed window_length"
            )
        resolution = (
            signal.sample_rate_hz / window_length
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=window_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
