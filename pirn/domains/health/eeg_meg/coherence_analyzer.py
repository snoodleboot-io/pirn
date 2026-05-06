"""``CoherenceAnalyzer`` — magnitude-squared coherence between channel pairs.

Production version uses ``scipy.signal.coherence`` or
``mne_connectivity.spectral_connectivity_epochs``. This stub returns a
mapping ``(channel_a, channel_b) -> coherence`` with all-zero values.

Algorithm:
    1. Receive a SignalFrame, channel_pairs, band_low_hz, and band_high_hz.
    2. Validate types and that band limits are positive with low < high.
    3. Segment the signal into windows and compute Fourier transforms.
    4. Compute magnitude-squared coherence for each channel pair in the band.
    5. Return a mapping of channel pair to mean coherence value.

Math:
    $$C_{xy}(f) = \\frac{|P_{xy}(f)|^2}{P_{xx}(f)\\, P_{yy}(f)}$$

References:
    - Welch coherence: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.coherence.html
    - mne-connectivity: https://mne.tools/mne-connectivity/stable/
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
        signal: Knot | SignalFrame,
        channel_pairs: Knot | Sequence[tuple[str, str]],
        band_low_hz: Knot | float,
        band_high_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            channel_pairs=channel_pairs,
            band_low_hz=band_low_hz,
            band_high_hz=band_high_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        channel_pairs: Sequence[tuple[str, str]],
        band_low_hz: float,
        band_high_hz: float,
        **_: Any,
    ) -> Mapping[tuple[str, str], float]:
        """Compute magnitude-squared coherence for each channel pair in the configured frequency band.

        Args:
            signal: The SignalFrame to analyze.
            channel_pairs: Sequence of (channel_a, channel_b) string tuples.
            band_low_hz: Lower frequency bound in Hz (positive).
            band_high_hz: Upper frequency bound in Hz (positive, must exceed band_low_hz).

        Returns:
            A mapping from (channel_a, channel_b) tuples to their magnitude-squared coherence values.

        Raises:
            TypeError: If signal is not SignalFrame, channel_pairs is not list/tuple, or pairs are invalid.
            ValueError: If band limits are non-positive or band_low_hz >= band_high_hz.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("CoherenceAnalyzer: signal must be a SignalFrame")
        if not isinstance(channel_pairs, (list, tuple)):
            raise TypeError("CoherenceAnalyzer: channel_pairs must be list/tuple")
        for pair in channel_pairs:
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not all(isinstance(p, str) for p in pair)
            ):
                raise TypeError("CoherenceAnalyzer: every channel pair must be (str, str)")
        if not isinstance(band_low_hz, (int, float)) or band_low_hz <= 0:
            raise ValueError("CoherenceAnalyzer: band_low_hz must be a positive number")
        if not isinstance(band_high_hz, (int, float)) or band_high_hz <= 0:
            raise ValueError("CoherenceAnalyzer: band_high_hz must be a positive number")
        if float(band_low_hz) >= float(band_high_hz):
            raise ValueError("CoherenceAnalyzer: band_low_hz must be < band_high_hz")
        return {pair: 0.0 for pair in channel_pairs}
