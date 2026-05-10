"""``AudioResampler`` — resample an audio :class:`SignalFrame`.

Algorithm:
    1. Receive the input signal frame, target_sample_rate_hz, and quality.
    2. Validate target_sample_rate_hz (positive) and quality (known string).
    3. Compute resampling ratio: ratio = target_sample_rate_hz / signal.sample_rate_hz.
    4. Apply the chosen resampling algorithm (polyphase, Kaiser, or linear interpolation).
    5. Update sample count: new_samples = int(samples_per_channel * ratio).
    6. Return a resampled SignalFrame at target_sample_rate_hz.

Math:
    Resampled sample count:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\frac{f_{\\text{target}}}{f_{\\text{in}}} \\right\\rfloor$$

    Polyphase resampling by rational factor $P/Q$:
    upsample by $P$, low-pass filter at $\\min(f_{\\text{in}}, f_{\\text{target}})/2$,
    then downsample by $Q$.

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing."
      Prentice-Hall.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _resample(data: np.ndarray, orig_sr: int, target_sr: int, res_type: str) -> np.ndarray:
    if data.ndim == 1:
        return librosa.resample(data, orig_sr=orig_sr, target_sr=target_sr, res_type=res_type)
    return np.stack(
        [
            librosa.resample(ch, orig_sr=orig_sr, target_sr=target_sr, res_type=res_type)
            for ch in data
        ]
    )


class AudioResampler(Knot):
    """Resample audio to a target sample rate using ``librosa.resample``."""

    def __init__(
        self,
        *,
        signal: Knot,
        target_sample_rate_hz: Knot | float,
        quality: Knot | str = "kaiser_best",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            target_sample_rate_hz=target_sample_rate_hz,
            quality=quality,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        target_sample_rate_hz: float,
        quality: str = "kaiser_best",
        **_: Any,
    ) -> SignalPayload:
        """Resample the input signal to the configured target rate.

        Args:
            signal: Audio signal to resample.
            target_sample_rate_hz: Positive target sample rate in Hz.
            quality: Resampling algorithm: ``kaiser_best``, ``kaiser_fast``,
                ``linear``, or ``polyphase``.

        Returns:
            SignalPayload at the configured target sample rate with an adjusted sample count.

        Raises:
            ValueError: If target_sample_rate_hz or quality are invalid.
        """
        if not isinstance(target_sample_rate_hz, (int, float)) or target_sample_rate_hz <= 0:
            raise ValueError("AudioResampler: target_sample_rate_hz must be positive")
        if quality not in {"kaiser_best", "kaiser_fast", "linear", "polyphase"}:
            raise ValueError(
                "AudioResampler: quality must be 'kaiser_best', 'kaiser_fast', "
                "'linear', or 'polyphase'"
            )
        orig_sr = int(signal.frame.sample_rate_hz)
        target_sr = int(target_sample_rate_hz)
        result = await asyncio.to_thread(_resample, signal.data, orig_sr, target_sr, quality)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:resampled",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=float(target_sample_rate_hz),
                samples_per_channel=result.shape[-1],
            ),
            data=np.asarray(result),
        )
