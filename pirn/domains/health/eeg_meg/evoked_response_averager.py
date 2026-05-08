"""``EvokedResponseAverager`` — average epochs to produce an evoked response.

Algorithm:
    1. Receive a non-empty sequence of SignalPayloads and a condition string.
    2. Validate types and that epochs is non-empty and condition is non-empty.
    3. Average the signal data arrays across epochs sample-by-sample.
    4. Return a SignalPayload representing the trial-averaged evoked response.

Math:
    $$\\bar{x}[t] = \\frac{1}{N} \\sum_{i=1}^{N} x_i[t]$$

References:
    - MNE Evoked: https://mne.tools/stable/generated/mne.Evoked.html
    - Luck (2014) Introduction to ERP Technique.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload


def _average_epochs(arrays: list[np.ndarray]) -> np.ndarray:
    """Average a list of epoch arrays along the first (epoch) axis."""
    return np.mean(arrays, axis=0)


class EvokedResponseAverager(Knot):
    """Average a set of epoch :class:`SignalPayload` objects."""

    def __init__(
        self,
        *,
        epochs: Knot | Sequence[SignalPayload],
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
        epochs: Sequence[SignalPayload],
        condition: str,
        **_: Any,
    ) -> SignalPayload:
        """Average the supplied epoch SignalPayloads and return the evoked response.

        Args:
            epochs: Non-empty sequence of SignalPayloads (epochs) to average.
            condition: Non-empty string identifying the experimental condition.

        Returns:
            A SignalPayload whose data is the trial-averaged array and whose frame
            reflects the evoked response metadata.

        Raises:
            TypeError: If epochs is not list/tuple of SignalPayloads.
            ValueError: If epochs is empty or condition is empty.
        """
        if not isinstance(epochs, (list, tuple)):
            raise TypeError("EvokedResponseAverager: epochs must be list/tuple")
        if not epochs:
            raise ValueError("EvokedResponseAverager: epochs must be non-empty")
        for ep in epochs:
            if not isinstance(ep, SignalPayload):
                raise TypeError("EvokedResponseAverager: every epoch must be SignalPayload")
        if not isinstance(condition, str) or not condition:
            raise ValueError("EvokedResponseAverager: condition must be non-empty string")

        arrays = [ep.data for ep in epochs]
        averaged = await asyncio.to_thread(_average_epochs, arrays)
        first = epochs[0]
        frame = SignalFrame(
            signal_id=f"evoked-{condition}",
            channel_count=first.frame.channel_count,
            sample_rate_hz=first.frame.sample_rate_hz,
            samples_per_channel=averaged.shape[-1],
            fetched_at=first.frame.fetched_at,
        )
        return SignalPayload(frame=frame, data=averaged)
