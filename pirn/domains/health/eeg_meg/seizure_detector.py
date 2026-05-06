"""``SeizureDetector`` — detect seizure intervals in an EEG.

Production version uses a CNN classifier or a feature-engineering
pipeline (line-length, energy). This stub returns an empty tuple of
``(start_sec, end_sec)`` intervals.

Algorithm:
    1. Receive a SignalFrame and threshold float.
    2. Validate that signal is a SignalFrame and threshold is non-negative.
    3. Compute a seizure likelihood measure over sliding windows.
    4. Mark windows exceeding the threshold as candidate seizures.
    5. Return a tuple of (start_sec, end_sec) interval tuples.


References:
    - Shoeb & Guttag (2010) Application of Machine Learning to Epileptic Seizure Detection.
    - PhysioNet EEG seizure dataset: https://physionet.org/content/chbmit/1.0.0/
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
        signal: Knot | SignalFrame,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        threshold: float,
        **_: Any,
    ) -> Sequence[tuple[float, float]]:
        """Detect seizure intervals in the EEG signal above the configured threshold and return (start_sec, end_sec) tuples.

        Args:
            signal: The EEG SignalFrame to scan for seizures.
            threshold: Non-negative detection threshold value.

        Returns:
            A sequence of (start_sec, end_sec) tuples representing detected seizure intervals.

        Raises:
            TypeError: If signal is not a SignalFrame or threshold is not numeric.
            ValueError: If threshold is negative.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("SeizureDetector: signal must be a SignalFrame")
        if not isinstance(threshold, (int, float)):
            raise TypeError("SeizureDetector: threshold must be numeric")
        if float(threshold) < 0:
            raise ValueError(
                "SeizureDetector: threshold must be non-negative"
            )
        return ()
