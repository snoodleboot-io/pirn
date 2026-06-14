"""``STFTDecomposer`` — short-time Fourier transform.

Algorithm:
    1. Receive the input signal payload, window_length, and hop_length.
    2. Validate window_length and hop_length (positive integers, hop_length <= window_length).
    3. Apply ``scipy.signal.stft`` with the given parameters.
    4. Return a SpectrumPayload with frequency_bins = window_length // 2 + 1.

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

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


class STFTDecomposer(Knot):
    """Sliding-window FFT producing a time-frequency representation."""

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
        signal: SignalPayload,
        window_length: int,
        hop_length: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Compute the short-time Fourier transform and return a SpectrumPayload.

        Args:
            signal: Signal payload to decompose into a time-frequency representation.
            window_length: Analysis window length in samples (positive integer).
            hop_length: Hop size between successive windows in samples (positive integer,
                must not exceed window_length).

        Returns:
            SpectrumPayload with data shape (channels, freq_bins, time_frames) or
            (freq_bins, time_frames) and frequency_bins = window_length // 2 + 1.

        Raises:
            ValueError: If window_length or hop_length are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError("STFTDecomposer: window_length must be a positive integer")
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("STFTDecomposer: hop_length must be a positive integer")
        if hop_length > window_length:
            raise ValueError("STFTDecomposer: hop_length must not exceed window_length")

        overlap = window_length - hop_length
        sample_rate = signal.frame.sample_rate_hz

        _, _, stft_data = await asyncio.to_thread(
            ss.stft,
            signal.data,
            fs=sample_rate,
            window="hann",
            nperseg=window_length,
            noverlap=overlap,
            axis=-1,
        )

        freq_bins = window_length // 2 + 1
        freq_res = sample_rate / window_length if sample_rate > 0 else 0.0

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=stft_data,
        )
