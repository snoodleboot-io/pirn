"""``BandpassFilter`` — bandpass filter an EEG/MEG signal frame.

Production version uses ``mne.filter.filter_data`` or
``scipy.signal.iirfilter`` + ``filtfilt``. This stub validates band
edges and returns the input :class:`SignalFrame` unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class BandpassFilter(Knot):
    """Bandpass-filter an EEG/MEG signal between two cutoff frequencies."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        low_hz: float,
        high_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("BandpassFilter: signal must be a SignalFrame")
        if not isinstance(low_hz, (int, float)) or float(low_hz) <= 0:
            raise ValueError(
                "BandpassFilter: low_hz must be a positive number"
            )
        if not isinstance(high_hz, (int, float)) or float(high_hz) <= 0:
            raise ValueError(
                "BandpassFilter: high_hz must be a positive number"
            )
        if float(low_hz) >= float(high_hz):
            raise ValueError("BandpassFilter: low_hz must be < high_hz")
        self._signal = signal
        self._low_hz = float(low_hz)
        self._high_hz = float(high_hz)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SignalFrame:
        return self._signal
