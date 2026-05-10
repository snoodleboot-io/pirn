"""``ISTFTReconstructor`` — reconstruct a time-domain signal from STFT via inverse STFT.

Algorithm:
    1. Receive the STFT spectrum payload, hop_length, and window.
    2. Validate hop_length (positive integer) and window (one of ``hann``, ``hamming``, ``blackman``).
    3. Apply ``scipy.signal.istft`` to recover the time-domain signal.
    4. Return a SignalPayload with the reconstructed samples.

Math:
    Overlap-add synthesis:

    $$x(n) = \\frac{\\sum_m w_s(n - m H) \\cdot \\text{IFFT}\\{X_m\\}(n - mH)}{\\sum_m w_s^2(n - mH)}$$

    where $H$ = hop_length and $w_s$ = synthesis window.

References:
    - Griffin, D.W. & Lim, J.S. (1984). "Signal estimation from modified short-time Fourier transform."
      IEEE Trans. Acoust. Speech Signal Process., 32(2), 236-243.
    - scipy.signal.istft: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.istft.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload


class ISTFTReconstructor(Knot):
    """Apply the inverse STFT to a SpectrumPayload and reconstruct the time-domain SignalPayload."""

    _valid_windows = frozenset({"hann", "hamming", "blackman"})

    def __init__(
        self,
        *,
        spectrum: Knot,
        hop_length: Knot | int,
        window: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            spectrum=spectrum,
            hop_length=hop_length,
            window=window,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        spectrum: SpectrumPayload,
        hop_length: int,
        window: str,
        **_: Any,
    ) -> SignalPayload:
        """Reconstruct the time-domain signal from the STFT spectrum via inverse STFT.

        Args:
            spectrum: The STFT SpectrumPayload to invert.
            hop_length: Hop size in samples between successive STFT frames (positive integer).
            window: Synthesis window type — ``hann``, ``hamming``, or ``blackman``.

        Returns:
            SignalPayload with reconstructed time-domain samples.

        Raises:
            ValueError: If hop_length or window are invalid.
        """
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("ISTFTReconstructor: hop_length must be a positive integer")
        if window not in self._valid_windows:
            raise ValueError(
                "ISTFTReconstructor: window must be one of 'hann', 'hamming', 'blackman'"
            )

        n_fft = (spectrum.frame.frequency_bins - 1) * 2
        overlap = n_fft - hop_length
        freq_res = spectrum.frame.frequency_resolution_hz
        sample_rate = freq_res * n_fft if freq_res > 0 else 1.0

        _, samples = await asyncio.to_thread(
            ss.istft,
            spectrum.data,
            fs=sample_rate,
            window=window,
            nperseg=n_fft,
            noverlap=overlap,
            freq_axis=-2,
            time_axis=-1,
        )

        signal_id = f"{spectrum.frame.signal_id}:istft"

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=signal_id,
                channel_count=1,
                sample_rate_hz=sample_rate,
                samples_per_channel=samples.shape[-1],
            ),
            data=samples,
        )
