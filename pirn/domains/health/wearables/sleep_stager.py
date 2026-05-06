"""``SleepStager`` — stage sleep epochs as wake / N1 / N2 / N3 / REM.

Production version uses YASA / a CNN classifier. This stub returns
the requested number of placeholder ``wake`` stages.

Algorithm:
    1. Receive signal (SignalFrame) and epoch_length_sec float.
    2. Validate signal is a SignalFrame and epoch_length_sec is positive numeric.
    3. Compute total recording duration from samples_per_channel / sample_rate_hz.
    4. Divide duration into fixed-length epochs.
    5. Return a tuple of stage labels, one per epoch.

Math:
    Number of epochs:

    $$N_{\\text{epochs}} = \\left\\lfloor \\frac{T_{\\text{total}}}{T_{\\text{epoch}}} \\right\\rfloor$$

    where $T_{\\text{total}} = \\text{samples\\_per\\_channel} / \\text{sample\\_rate\\_hz}$.

References:
    - Rechtschaffen, A. & Kales, A. (1968). A Manual of Standardized Terminology.
    - YASA: https://raphaelvallat.com/yasa/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class SleepStager(Knot):
    """Stage sleep from a long PSG / single-channel EEG signal."""

    def __init__(
        self,
        *,
        signal: Knot | SignalFrame,
        epoch_length_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, epoch_length_sec=epoch_length_sec, _config=_config, **kwargs)

    async def process(
        self,
        signal: SignalFrame,
        epoch_length_sec: float,
        **_: Any,
    ) -> tuple[str, ...]:
        """Stage the signal into sleep epochs of the configured length and return a tuple of stage labels.

        Args:
            signal: SignalFrame containing the PSG or EEG recording.
            epoch_length_sec: Epoch duration in seconds (must be positive).

        Returns:
            Tuple of stage label strings (e.g. ``"wake"``, ``"n1"``, ``"rem"``) one per epoch.

        Raises:
            TypeError: If signal is not a SignalFrame or epoch_length_sec is not numeric.
            ValueError: If epoch_length_sec is not positive.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("SleepStager: signal must be a SignalFrame")
        if not isinstance(epoch_length_sec, (int, float)):
            raise TypeError("SleepStager: epoch_length_sec must be numeric")
        if float(epoch_length_sec) <= 0:
            raise ValueError("SleepStager: epoch_length_sec must be positive")
        total_sec = signal.samples_per_channel / max(signal.sample_rate_hz, 1.0)
        n_epochs = max(1, int(total_sec / epoch_length_sec))
        return tuple("wake" for _ in range(n_epochs))
