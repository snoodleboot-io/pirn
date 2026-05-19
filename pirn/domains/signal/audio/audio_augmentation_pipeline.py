"""``AudioAugmentationPipeline`` — stochastic audio augmentation pipeline.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate augmentations (non-empty tuple of known names) and seed.
    3. Seed the random number generator with seed.
    4. For each augmentation in augmentations (in order):
       - pitch_shift: shift pitch by a random semitone amount.
       - time_stretch: stretch or compress time by a random rate factor.
       - add_noise: add Gaussian noise at a random SNR.
       - time_mask: zero out a random contiguous time segment.
       - frequency_mask: zero out a random contiguous frequency band.
    5. Return an augmented SignalFrame with the same metadata.

    from uniform distributions; specific formulae depend on the chosen
    augmentation library.

References:
    - Park, D.S. et al. (2019). "SpecAugment: A Simple Data Augmentation Method
      for Automatic Speech Recognition." Interspeech 2019.
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _apply_augmentations(
    data: np.ndarray, sr: int, augmentations: tuple[str, ...], seed: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mono = data[0] if data.ndim > 1 else data
    result = mono.copy().astype(np.float32)

    for aug in augmentations:
        if aug == "add_noise":
            noise_std = float(rng.uniform(0.001, 0.01))
            result = result + rng.normal(0, noise_std, size=result.shape).astype(np.float32)
        elif aug == "pitch_shift":
            steps = float(rng.uniform(-3.0, 3.0))
            result = librosa.effects.pitch_shift(result, sr=sr, n_steps=steps)
        elif aug == "time_stretch":
            rate = float(rng.uniform(0.85, 1.15))
            result = librosa.effects.time_stretch(result, rate=rate)
        elif aug == "time_mask":
            mask_len = int(rng.integers(1, max(2, len(result) // 10)))
            start = int(rng.integers(0, max(1, len(result) - mask_len)))
            result[start : start + mask_len] = 0.0
        elif aug == "frequency_mask":
            fft = np.fft.rfft(result)
            n_bins = len(fft)
            mask_start = int(rng.integers(0, max(1, n_bins - 1)))
            mask_end = min(n_bins, mask_start + int(rng.integers(1, max(2, n_bins // 10))))
            fft[mask_start:mask_end] = 0.0
            result = np.fft.irfft(fft, n=len(result)).astype(np.float32)

    if data.ndim > 1:
        return result[np.newaxis, :]
    return result


class AudioAugmentationPipeline(Knot):
    """Apply stochastic augmentations to an audio signal.

    Supported augmentations: ``pitch_shift``, ``time_stretch``,
    ``add_noise``, ``time_mask``, ``frequency_mask``.
    """

    _valid_augmentations: ClassVar[frozenset[str]] = frozenset(
        {"pitch_shift", "time_stretch", "add_noise", "time_mask", "frequency_mask"}
    )

    def __init__(
        self,
        *,
        signal: Knot,
        augmentations: Knot | tuple,
        seed: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            augmentations=augmentations,
            seed=seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        augmentations: tuple[str, ...],
        seed: int,
        **_: Any,
    ) -> SignalPayload:
        """Apply the configured augmentations to the audio signal.

        Args:
            signal: Input audio signal to augment.
            augmentations: Non-empty tuple of augmentation names to apply.
            seed: Non-negative integer random seed for reproducibility.

        Returns:
            SignalPayload with augmentations applied, preserving sample rate and channel count.

        Raises:
            ValueError: If augmentations is empty, contains unknown names, or seed is negative.
        """
        if not isinstance(augmentations, tuple) or len(augmentations) == 0:
            raise ValueError("AudioAugmentationPipeline: augmentations must be a non-empty tuple")
        invalid = set(augmentations) - self._valid_augmentations
        if invalid:
            raise ValueError(f"AudioAugmentationPipeline: unknown augmentations {sorted(invalid)}")
        if not isinstance(seed, int) or seed < 0:
            raise ValueError("AudioAugmentationPipeline: seed must be a non-negative integer")
        sr = int(signal.frame.sample_rate_hz)
        result = await asyncio.to_thread(_apply_augmentations, signal.data, sr, augmentations, seed)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:augmented",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[-1],
            ),
            data=np.asarray(result),
        )
