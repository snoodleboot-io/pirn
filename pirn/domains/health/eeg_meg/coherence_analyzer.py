"""``CoherenceAnalyzer`` — magnitude-squared coherence between channel pairs.

Production version uses ``scipy.signal.coherence`` or
``mne_connectivity.spectral_connectivity_epochs``. This stub returns a
mapping ``(channel_a, channel_b) -> coherence`` with all-zero values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class CoherenceAnalyzer(Knot):
    """Compute coherence for the supplied channel pairs."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        channel_pairs: Sequence[tuple[str, str]],
        band_low_hz: float,
        band_high_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("CoherenceAnalyzer: signal must be a SignalFrame")
        if not isinstance(channel_pairs, (list, tuple)):
            raise TypeError(
                "CoherenceAnalyzer: channel_pairs must be list/tuple"
            )
        for pair in channel_pairs:
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not all(isinstance(p, str) for p in pair)
            ):
                raise TypeError(
                    "CoherenceAnalyzer: every channel pair must be (str, str)"
                )
        if not isinstance(band_low_hz, (int, float)) or band_low_hz <= 0:
            raise ValueError(
                "CoherenceAnalyzer: band_low_hz must be a positive number"
            )
        if not isinstance(band_high_hz, (int, float)) or band_high_hz <= 0:
            raise ValueError(
                "CoherenceAnalyzer: band_high_hz must be a positive number"
            )
        if float(band_low_hz) >= float(band_high_hz):
            raise ValueError(
                "CoherenceAnalyzer: band_low_hz must be < band_high_hz"
            )
        self._signal = signal
        self._channel_pairs = tuple(channel_pairs)
        self._band_low = float(band_low_hz)
        self._band_high = float(band_high_hz)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[tuple[str, str], float]:
        return {pair: 0.0 for pair in self._channel_pairs}
