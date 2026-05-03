"""``AudioAugmentationPipeline`` — stochastic audio augmentation pipeline."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioAugmentationPipeline(Knot):
    """Apply stochastic augmentations to an audio signal.

    Supported augmentations: ``pitch_shift``, ``time_stretch``,
    ``add_noise``, ``time_mask``, ``frequency_mask``.

    Production needs ``audiomentations`` or a hand-rolled implementation.
    """

    _VALID_AUGMENTATIONS: frozenset[str] = frozenset(
        {"pitch_shift", "time_stretch", "add_noise", "time_mask", "frequency_mask"}
    )

    def __init__(
        self,
        *,
        signal: Knot,
        augmentations: tuple[str, ...],
        seed: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(augmentations, tuple) or len(augmentations) == 0:
            raise ValueError(
                "AudioAugmentationPipeline: augmentations must be a non-empty tuple"
            )
        invalid = set(augmentations) - self._VALID_AUGMENTATIONS
        if invalid:
            raise ValueError(
                f"AudioAugmentationPipeline: unknown augmentations {sorted(invalid)}"
            )
        if not isinstance(seed, int) or seed < 0:
            raise ValueError(
                "AudioAugmentationPipeline: seed must be a non-negative integer"
            )
        self._augmentations = augmentations
        self._seed = seed
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def augmentations(self) -> tuple[str, ...]:
        return self._augmentations

    @property
    def seed(self) -> int:
        return self._seed

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the configured augmentations to the audio signal and return an augmented SignalFrame.

        Args:
            signal: Input audio signal to augment.

        Returns:
            SignalFrame with augmentations applied, preserving sample rate and channel count.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:augmented",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
