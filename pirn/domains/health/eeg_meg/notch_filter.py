"""``NotchFilter`` — notch-filter at a specific frequency (e.g. 50/60 Hz).

Production version uses ``mne.filter.notch_filter``. This stub
validates inputs and returns the signal unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class NotchFilter(Knot):
    """Apply a notch filter at the line-noise frequency."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        notch_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("NotchFilter: signal must be a SignalFrame")
        if not isinstance(notch_hz, (int, float)) or float(notch_hz) <= 0:
            raise ValueError(
                "NotchFilter: notch_hz must be a positive number"
            )
        self._signal = signal
        self._notch_hz = float(notch_hz)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SignalFrame:
        return self._signal
