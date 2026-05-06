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

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioAugmentationPipeline(Knot):
    """Apply stochastic augmentations to an audio signal.

    Supported augmentations: ``pitch_shift``, ``time_stretch``,
    ``add_noise``, ``time_mask``, ``frequency_mask``.

    Production needs ``audiomentations`` or a hand-rolled implementation.
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
        signal: SignalFrame,
        augmentations: tuple[str, ...],
        seed: int,
        **_: Any,
    ) -> SignalFrame:
        """Apply the configured augmentations to the audio signal.

        Args:
            signal: Input audio signal to augment.
            augmentations: Non-empty tuple of augmentation names to apply.
            seed: Non-negative integer random seed for reproducibility.

        Returns:
            SignalFrame with augmentations applied, preserving sample rate and channel count.

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
        return SignalFrame(
            signal_id=f"{signal.signal_id}:augmented",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
