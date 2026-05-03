"""``WaveletDenoiser`` — threshold-based wavelet denoising."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class WaveletDenoiser(Knot):
    """Denoise a signal by thresholding wavelet coefficients."""

    _valid_modes = frozenset({"soft", "hard"})

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet: str,
        level: int,
        threshold_mode: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("WaveletDenoiser: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("WaveletDenoiser: level must be a positive integer")
        if threshold_mode not in self._valid_modes:
            raise ValueError(
                "WaveletDenoiser: threshold_mode must be one of 'soft', 'hard'"
            )
        self._wavelet = wavelet
        self._level = level
        self._threshold_mode = threshold_mode
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def wavelet(self) -> str:
        return self._wavelet

    @property
    def threshold_mode(self) -> str:
        return self._threshold_mode

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Denoise the signal via wavelet thresholding and return the cleaned SignalFrame.

        Args:
            signal: The noisy input signal frame.

        Returns:
            Denoised SignalFrame with the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:denoised-{self._threshold_mode}",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
