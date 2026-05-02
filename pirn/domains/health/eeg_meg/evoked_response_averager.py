"""``EvokedResponseAverager`` — average epochs to produce an evoked response.

Production version uses ``mne.Epochs.average``. This stub validates
inputs and returns a single :class:`SignalFrame` representing the
average.
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
        epochs: Sequence[SignalFrame],
        condition: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(epochs, (list, tuple)):
            raise TypeError(
                "EvokedResponseAverager: epochs must be list/tuple"
            )
        if not epochs:
            raise ValueError(
                "EvokedResponseAverager: epochs must be non-empty"
            )
        for ep in epochs:
            if not isinstance(ep, SignalFrame):
                raise TypeError(
                    "EvokedResponseAverager: every epoch must be SignalFrame"
                )
        if not isinstance(condition, str) or not condition:
            raise ValueError(
                "EvokedResponseAverager: condition must be non-empty string"
            )
        self._epochs = tuple(epochs)
        self._condition = condition
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SignalFrame:
        first = self._epochs[0]
        return SignalFrame(
            signal_id=f"evoked-{self._condition}",
            channel_count=first.channel_count,
            sample_rate_hz=first.sample_rate_hz,
            samples_per_channel=first.samples_per_channel,
            fetched_at=first.fetched_at,
        )
