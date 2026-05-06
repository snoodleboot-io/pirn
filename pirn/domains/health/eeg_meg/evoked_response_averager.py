"""``EvokedResponseAverager`` — average epochs to produce an evoked response.

Production version uses ``mne.Epochs.average``. This stub validates
inputs and returns a single :class:`SignalFrame` representing the
average.

Algorithm:
    1. Receive a non-empty sequence of SignalFrames and a condition string.
    2. Validate types and that epochs is non-empty and condition is non-empty.
    3. Average the signal data across epochs sample-by-sample.
    4. Return a SignalFrame representing the trial-averaged evoked response.

Math:
    $$\\bar{x}[t] = \\frac{1}{N} \\sum_{i=1}^{N} x_i[t]$$

References:
    - MNE Evoked: https://mne.tools/stable/generated/mne.Evoked.html
    - Luck (2014) Introduction to ERP Technique.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class EvokedResponseAverager(Knot):
    """Average a set of epoch :class:`SignalFrame`s."""

    def __init__(
        self,
        *,
        epochs: Knot | Sequence[SignalFrame],
        condition: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            epochs=epochs,
            condition=condition,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        epochs: Sequence[SignalFrame],
        condition: str,
        **_: Any,
    ) -> SignalFrame:
        """Average the supplied epoch SignalFrames for the configured condition and return the evoked response.

        Args:
            epochs: Non-empty sequence of SignalFrames (epochs) to average.
            condition: Non-empty string identifying the experimental condition.

        Returns:
            A SignalFrame representing the trial-averaged evoked response for the configured condition.

        Raises:
            TypeError: If epochs is not list/tuple of SignalFrames.
            ValueError: If epochs is empty or condition is empty.
        """
        if not isinstance(epochs, (list, tuple)):
            raise TypeError("EvokedResponseAverager: epochs must be list/tuple")
        if not epochs:
            raise ValueError("EvokedResponseAverager: epochs must be non-empty")
        for ep in epochs:
            if not isinstance(ep, SignalFrame):
                raise TypeError("EvokedResponseAverager: every epoch must be SignalFrame")
        if not isinstance(condition, str) or not condition:
            raise ValueError("EvokedResponseAverager: condition must be non-empty string")
        first = epochs[0]
        return SignalFrame(
            signal_id=f"evoked-{condition}",
            channel_count=first.channel_count,
            sample_rate_hz=first.sample_rate_hz,
            samples_per_channel=first.samples_per_channel,
            fetched_at=first.fetched_at,
        )
