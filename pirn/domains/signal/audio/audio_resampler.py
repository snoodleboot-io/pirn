"""``AudioResampler`` — resample an audio :class:`SignalFrame`."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioResampler(Knot):
    """Resample audio to a target sample rate.

    Production needs ``librosa.resample`` or ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        target_sample_rate_hz: float,
        quality: str = "kaiser_best",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if (
            not isinstance(target_sample_rate_hz, (int, float))
            or target_sample_rate_hz <= 0
        ):
            raise ValueError(
                "AudioResampler: target_sample_rate_hz must be positive"
            )
        if quality not in {"kaiser_best", "kaiser_fast", "linear", "polyphase"}:
            raise ValueError(
                "AudioResampler: quality must be 'kaiser_best', 'kaiser_fast', "
                "'linear', or 'polyphase'"
            )
        self._target_sample_rate_hz = float(target_sample_rate_hz)
        self._quality = quality
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def target_sample_rate_hz(self) -> float:
        return self._target_sample_rate_hz

    @property
    def quality(self) -> str:
        return self._quality

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        if signal.sample_rate_hz > 0:
            ratio = self._target_sample_rate_hz / signal.sample_rate_hz
            new_samples = int(signal.samples_per_channel * ratio)
        else:
            new_samples = signal.samples_per_channel
        return SignalFrame(
            signal_id=f"{signal.signal_id}:resampled",
            channel_count=signal.channel_count,
            sample_rate_hz=self._target_sample_rate_hz,
            samples_per_channel=new_samples,
        )
