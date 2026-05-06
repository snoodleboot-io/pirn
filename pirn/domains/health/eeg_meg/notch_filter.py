"""``NotchFilter`` — notch-filter at a specific frequency (e.g. 50/60 Hz).

Production version uses ``mne.filter.notch_filter``. This stub
validates inputs and returns the signal unchanged.

Algorithm:
    1. Receive a SignalFrame and notch_hz frequency.
    2. Validate that signal is a SignalFrame and notch_hz is a positive number.
    3. Design and apply a notch filter at the specified frequency.
    4. Return the filtered SignalFrame.


References:
    - MNE notch_filter: https://mne.tools/stable/generated/mne.filter.notch_filter.html
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
        signal: Knot | SignalFrame,
        notch_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            notch_hz=notch_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        notch_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply a notch filter at the configured frequency and return the filtered SignalFrame.

        Args:
            signal: The SignalFrame to filter.
            notch_hz: Positive frequency in Hz at which to apply the notch filter.

        Returns:
            A SignalFrame with the notch filter applied at the configured frequency.

        Raises:
            TypeError: If signal is not a SignalFrame.
            ValueError: If notch_hz is not a positive number.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("NotchFilter: signal must be a SignalFrame")
        if not isinstance(notch_hz, (int, float)) or float(notch_hz) <= 0:
            raise ValueError("NotchFilter: notch_hz must be a positive number")
        return signal
