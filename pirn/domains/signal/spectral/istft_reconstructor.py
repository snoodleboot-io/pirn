"""``ISTFTReconstructor`` — reconstruct a time-domain signal from STFT via inverse STFT."""

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
        hop_length: int,
        window: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("ISTFTReconstructor: hop_length must be a positive integer")
        if window not in self._valid_windows:
            raise ValueError(
                "ISTFTReconstructor: window must be one of 'hann', 'hamming', 'blackman'"
            )
        self._hop_length = hop_length
        self._window = window
        super().__init__(spectrum=spectrum, _config=_config, **kwargs)

    @property
    def hop_length(self) -> int:
        return self._hop_length

    @property
    def window(self) -> str:
        return self._window

    async def process(self, spectrum: SpectrumFrame, **_: Any) -> SignalFrame:
        """Reconstruct the time-domain signal from the STFT spectrum via inverse STFT.

        Args:
            spectrum: The STFT SpectrumFrame to invert.

        Returns:
            SignalFrame with samples_per_channel derived from the spectrum bin count and hop.
        """
        n_frames = max(1, spectrum.frequency_bins)
        n_samples = (n_frames - 1) * self._hop_length
        return SignalFrame(
            signal_id=f"{spectrum.signal_id}:istft",
            channel_count=1,
            sample_rate_hz=0.0,
            samples_per_channel=n_samples,
        )
