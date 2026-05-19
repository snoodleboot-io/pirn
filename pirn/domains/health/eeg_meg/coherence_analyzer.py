"""``CoherenceAnalyzer`` — magnitude-squared coherence between channel pairs.

Algorithm:
    1. Receive a SignalPayload, channel_pairs, band_low_hz, and band_high_hz.
    2. Validate types and that band limits are positive with low < high.
    3. For each channel pair, compute magnitude-squared coherence via scipy.signal.coherence.
    4. Average coherence over the specified frequency band.
    5. Return a mapping of channel pair to mean coherence value.

Math:
    $$C_{xy}(f) = \\frac{|P_{xy}(f)|^2}{P_{xx}(f)\\, P_{yy}(f)}$$

References:
    - Welch coherence: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.coherence.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _band_coherence(
    channel_x: np.ndarray, channel_y: np.ndarray, fs: float, low: float, high: float
) -> float:
    freqs, cxy = ss.coherence(channel_x, channel_y, fs=fs)
    mask = (freqs >= low) & (freqs <= high)
    return float(np.mean(cxy[mask])) if mask.any() else 0.0


def _channel_index(name: str, n_channels: int) -> int:
    if name.startswith("ch"):
        try:
            idx = int(name[2:])
            return idx if 0 <= idx < n_channels else 0
        except ValueError:
            return 0
    return 0


def _compute_coherence(
    data: np.ndarray,
    channel_pairs: Sequence[tuple[str, str]],
    fs: float,
    low: float,
    high: float,
) -> dict[tuple[str, str], float]:
    n_channels = data.shape[0] if data.ndim > 1 else 1
    result: dict[tuple[str, str], float] = {}
    for pair in channel_pairs:
        idx_a = _channel_index(pair[0], n_channels)
        idx_b = _channel_index(pair[1], n_channels)
        if data.ndim > 1:
            channel_a = data[idx_a]
            channel_b = data[idx_b]
        else:
            channel_a = data
            channel_b = data
        result[pair] = _band_coherence(channel_a, channel_b, fs, low, high)
    return result


class CoherenceAnalyzer(Knot):
    """Compute coherence for the supplied channel pairs."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
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
        signal: SignalPayload,
        channel_pairs: Sequence[tuple[str, str]],
        band_low_hz: float,
        band_high_hz: float,
        **_: Any,
    ) -> Mapping[tuple[str, str], float]:
        """Compute magnitude-squared coherence for each channel pair in the configured frequency band.

        Args:
            signal: The SignalPayload to analyze.
            channel_pairs: Sequence of (channel_a, channel_b) string tuples.
            band_low_hz: Lower frequency bound in Hz (positive).
            band_high_hz: Upper frequency bound in Hz (positive, must exceed band_low_hz).

        Returns:
            A mapping from (channel_a, channel_b) tuples to mean coherence values in the band.

        Raises:
            TypeError: If signal is not SignalPayload, channel_pairs is not list/tuple, or pairs are invalid.
            ValueError: If band limits are non-positive or band_low_hz >= band_high_hz.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("CoherenceAnalyzer: signal must be a SignalPayload")
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

        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(
            _compute_coherence,
            signal.data,
            channel_pairs,
            fs,
            float(band_low_hz),
            float(band_high_hz),
        )
