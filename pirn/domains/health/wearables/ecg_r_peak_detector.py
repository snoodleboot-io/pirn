"""``ECGRPeakDetector`` — detect R-peaks in an ECG signal.

Production version uses Pan-Tompkins / NeuroKit2 / wfdb. This stub
validates inputs and returns an empty tuple of peak sample indices.

Algorithm:
    1. Receive signal (SignalFrame) and method string.
    2. Validate signal is a SignalFrame and method is one of pan_tompkins/neurokit/elgendi.
    3. Apply bandpass filter to isolate QRS complex frequency band.
    4. Detect peaks above a dynamic threshold using the selected method.
    5. Return a tuple of sample indices corresponding to R-peak positions.


References:
    - Pan, J. & Tompkins, W.J. (1985). A real-time QRS detection algorithm.
    - NeuroKit2: https://neuropsychology.github.io/NeuroKit/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class ECGRPeakDetector(Knot):
    """Detect R-peaks in an ECG signal."""

    def __init__(
        self,
        *,
        signal: Knot | SignalFrame,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, method=method, _config=_config, **kwargs)

    async def process(
        self,
        signal: SignalFrame,
        method: str,
        **_: Any,
    ) -> tuple[int, ...]:
        """Detect R-peak sample indices in the ECG signal using the configured method.

        Args:
            signal: SignalFrame containing the ECG recording.
            method: One of pan_tompkins, neurokit, elgendi.

        Returns:
            Tuple of integer sample indices corresponding to detected R-peaks.

        Raises:
            TypeError: If signal is not a SignalFrame.
            ValueError: If method is not one of the supported options.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("ECGRPeakDetector: signal must be a SignalFrame")
        if method not in ("pan_tompkins", "neurokit", "elgendi"):
            raise ValueError(
                "ECGRPeakDetector: method must be one of pan_tompkins/neurokit/elgendi"
            )
        return ()
