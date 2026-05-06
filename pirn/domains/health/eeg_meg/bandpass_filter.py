"""``BandpassFilter`` — bandpass filter an EEG/MEG signal frame.

Production version uses ``mne.filter.filter_data`` or
``scipy.signal.iirfilter`` + ``filtfilt``. This stub validates band
edges and returns the input :class:`SignalFrame` unchanged.

Algorithm:
    1. Receive a SignalFrame, low_hz, and high_hz cutoffs.
    2. Validate that signal is a SignalFrame and cutoffs are positive numbers with low_hz < high_hz.
    3. Design the bandpass filter (Butterworth IIR) at the specified cutoff frequencies.
    4. Apply zero-phase filtering via filtfilt.
    5. Return the filtered SignalFrame.


References:
    - MNE filter: https://mne.tools/stable/generated/mne.filter.filter_data.html
    - SciPy iirfilter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.iirfilter.html
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
        signal: Knot | SignalFrame,
        low_hz: Knot | float,
        high_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            low_hz=low_hz,
            high_hz=high_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        low_hz: float,
        high_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Bandpass-filter the signal frame between the configured frequency cutoffs and return the result.

        Args:
            signal: The SignalFrame to filter.
            low_hz: Lower cutoff frequency in Hz (positive number).
            high_hz: Upper cutoff frequency in Hz (positive number, must exceed low_hz).

        Returns:
            A SignalFrame with the bandpass filter applied.

        Raises:
            TypeError: If signal is not a SignalFrame.
            ValueError: If cutoffs are non-positive or low_hz >= high_hz.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("BandpassFilter: signal must be a SignalFrame")
        if not isinstance(low_hz, (int, float)) or float(low_hz) <= 0:
            raise ValueError("BandpassFilter: low_hz must be a positive number")
        if not isinstance(high_hz, (int, float)) or float(high_hz) <= 0:
            raise ValueError("BandpassFilter: high_hz must be a positive number")
        if float(low_hz) >= float(high_hz):
            raise ValueError("BandpassFilter: low_hz must be < high_hz")
        return signal
