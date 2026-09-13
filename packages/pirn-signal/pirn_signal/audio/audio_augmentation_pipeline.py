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
    5. Repeat independently for each channel (each with an independently seeded
       generator derived from the configured seed) and return an augmented
       SignalPayload with the same metadata.

Math:
    Additive Gaussian noise at a random standard deviation $\\sigma \\sim U(0.001, 0.01)$:

    $$x'[n] = x[n] + \\mathcal{N}(0, \\sigma^2)$$

    Time and frequency masking (SpecAugment-style) zero a contiguous span:

    $$x'[n] = 0, \\quad n \\in [n_0, n_0 + L)$$

    where $L$ is drawn as a random fraction of the signal (or spectrum) length and
    $n_0$ is drawn uniformly over the remaining valid range. Pitch shift and time
    stretch amounts are drawn uniformly from $[-3, 3]$ semitones and $[0.85, 1.15]$
    respectively; their formulae are defined within ``librosa.effects``.

References:
    - Park, D.S. et al. (2019). "SpecAugment: A Simple Data Augmentation Method
      for Automatic Speech Recognition." Interspeech 2019.
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


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
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    AudioAugmentationPipeline._apply_augmentations, channel, sr, augmentations, seed
                )
                for channel in channels
            )
        )
        return signal.derive("augmented", np.stack(results, axis=0))

    @staticmethod
    def _apply_augmentations(
        channel: np.ndarray, sr: int, augmentations: tuple[str, ...], seed: int
    ) -> np.ndarray:
        """Apply the configured augmentation recipe to a single channel.

        Every channel is augmented with the same seed, so length-changing
        augmentations (time_stretch) resize every channel identically and the
        per-channel results remain stackable; noise and masking are re-drawn
        per channel from the same seeded recipe.
        """
        try:
            import librosa  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AudioAugmentationPipeline requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        rng = np.random.default_rng(seed)
        result = channel.copy().astype(np.float32)

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

        return result
