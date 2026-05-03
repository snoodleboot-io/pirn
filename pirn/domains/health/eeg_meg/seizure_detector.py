"""``SeizureDetector`` — detect seizure intervals in an EEG.

Production version uses a CNN classifier or a feature-engineering
pipeline (line-length, energy). This stub returns an empty tuple of
``(start_sec, end_sec)`` intervals.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class SeizureDetector(Knot):
    """Detect candidate seizure intervals in an EEG signal."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("SeizureDetector: signal must be a SignalFrame")
        if not isinstance(threshold, (int, float)):
            raise TypeError("SeizureDetector: threshold must be numeric")
        if float(threshold) < 0:
            raise ValueError(
                "SeizureDetector: threshold must be non-negative"
            )
        self._signal = signal
        self._threshold = float(threshold)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Sequence[tuple[float, float]]:
        """Detect seizure intervals in the EEG signal above the configured threshold and return (start_sec, end_sec) tuples.

        Returns:
            A sequence of (start_sec, end_sec) tuples representing detected seizure intervals.
        """
        return ()
