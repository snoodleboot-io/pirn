"""``ECGRPeakDetector`` — detect R-peaks in an ECG signal.

Production version uses Pan-Tompkins / NeuroKit2 / wfdb. This stub
validates inputs and returns an empty tuple of peak sample indices.
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
        signal: SignalFrame,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "ECGRPeakDetector: signal must be a SignalFrame"
            )
        if method not in ("pan_tompkins", "neurokit", "elgendi"):
            raise ValueError(
                "ECGRPeakDetector: method must be one of pan_tompkins/neurokit/elgendi"
            )
        self._signal = signal
        self._method = method
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[int, ...]:
        return ()
