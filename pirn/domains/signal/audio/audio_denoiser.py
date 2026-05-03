"""``AudioDenoiser`` — spectral-subtraction noise reduction."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioDenoiser(Knot):
    """Spectral-subtraction noise reduction for audio signals.

    Production needs ``librosa`` or a hand-rolled STFT-based implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        noise_estimate_frames: int,
        over_subtraction_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(noise_estimate_frames, int) or noise_estimate_frames <= 0:
            raise ValueError(
                "AudioDenoiser: noise_estimate_frames must be a positive integer"
            )
        if not isinstance(over_subtraction_factor, (int, float)) or over_subtraction_factor < 1.0:
            raise ValueError(
                "AudioDenoiser: over_subtraction_factor must be >= 1.0"
            )
        self._noise_estimate_frames = noise_estimate_frames
        self._over_subtraction_factor = float(over_subtraction_factor)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def noise_estimate_frames(self) -> int:
        return self._noise_estimate_frames

    @property
    def over_subtraction_factor(self) -> float:
        return self._over_subtraction_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply spectral subtraction to reduce background noise and return a denoised SignalFrame.

        Args:
            signal: Noisy audio signal to denoise.

        Returns:
            SignalFrame with reduced background noise.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:denoised",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
