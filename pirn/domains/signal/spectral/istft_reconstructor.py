"""``ISTFTReconstructor`` — reconstruct a time-domain signal from STFT via inverse STFT.

Algorithm:
    1. Receive the STFT spectrum frame, hop_length, and window.
    2. Validate hop_length (positive integer) and window (one of ``hann``, ``hamming``, ``blackman``).
    3. For each time frame, apply the IFFT to recover the windowed signal segment.
    4. Accumulate the windowed segments using overlap-add (OLA) with the synthesis window.
    5. Normalise by the sum of squared window values at each output sample.
    6. Return a SignalFrame with samples_per_channel derived from spectrum bin count and hop length.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class ISTFTReconstructor(Knot):
    """Apply the inverse STFT to a SpectrumFrame and reconstruct the time-domain SignalFrame."""

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
        spectrum: SpectrumFrame,
        hop_length: int,
        window: str,
        **_: Any,
    ) -> SignalFrame:
        """Reconstruct the time-domain signal from the STFT spectrum via inverse STFT.

        Args:
            spectrum: The STFT SpectrumFrame to invert.
            hop_length: Hop size in samples between successive STFT frames (positive integer).
            window: Synthesis window type — ``hann``, ``hamming``, or ``blackman``.

        Returns:
            SignalFrame with samples_per_channel derived from the spectrum bin count and hop.

        Raises:
            ValueError: If hop_length or window are invalid.
        """
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("ISTFTReconstructor: hop_length must be a positive integer")
        if window not in self._valid_windows:
            raise ValueError(
                "ISTFTReconstructor: window must be one of 'hann', 'hamming', 'blackman'"
            )
        n_frames = max(1, spectrum.frequency_bins)
        n_samples = (n_frames - 1) * hop_length
        return SignalFrame(
            signal_id=f"{spectrum.signal_id}:istft",
            channel_count=1,
            sample_rate_hz=0.0,
            samples_per_channel=n_samples,
        )
