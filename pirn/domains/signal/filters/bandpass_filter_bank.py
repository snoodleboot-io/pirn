"""``BandpassFilterBank`` — apply N parallel bandpass filters.

Algorithm:
    1. Receive the input signal payload, bands tuple, and filter order.
    2. Validate bands (non-empty, each (low_hz, high_hz) with 0 < low < high) and order.
    3. For each band (low_hz, high_hz): design a Butterworth bandpass filter of the
       given order and apply via sosfilt.
    4. Stack results: (n_bands, n_samples) for mono or (channels, n_bands, n_samples)
       for multi-channel.
    5. Return a single SignalPayload with the stacked band data.

Math:
    Each bandpass filter has the ideal passband:

    $$H_k(\\omega) = \\begin{cases} 1 & \\omega_{L,k} \\leq \\omega \\leq \\omega_{H,k} \\\\ 0 & \\text{otherwise} \\end{cases}$$

    for band $k$ with edges $(f_{L,k}, f_{H,k})$.

References:
    - scipy.signal.butter with btype='bandpass':
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


async def _filter_band(
    data: np.ndarray, low_hz: float, high_hz: float, order: int, fs: float
) -> np.ndarray:
    """Design and apply a single bandpass filter, returning the filtered data."""
    sos = await asyncio.to_thread(
        ss.butter, order, [low_hz, high_hz], btype="bandpass", fs=fs, output="sos"
    )
    return np.asarray(await asyncio.to_thread(ss.sosfilt, sos, data, axis=-1))


class BandpassFilterBank(Knot):
    """Apply a bank of parallel bandpass filters and return a single SignalPayload."""

    def __init__(
        self,
        *,
        signal: Knot,
        bands: Knot | tuple,
        order: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            bands=bands,
            order=order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        bands: tuple[tuple[float, float], ...],
        order: int,
        **_: Any,
    ) -> SignalPayload:
        """Apply parallel bandpass filters and return a stacked SignalPayload.

        Args:
            signal: The input signal payload.
            bands: Non-empty tuple of (low_hz, high_hz) pairs.
            order: Filter order for each bandpass filter (positive integer).

        Returns:
            SignalPayload with data stacked across bands.

        Raises:
            ValueError: If bands is empty, any band is malformed, or order is invalid.
        """
        if not isinstance(bands, tuple) or len(bands) == 0:
            raise ValueError(
                "BandpassFilterBank: bands must be a non-empty tuple of (low_hz, high_hz) pairs"
            )
        for i, band in enumerate(bands):
            if (
                not isinstance(band, tuple)
                or len(band) != 2
                or not all(isinstance(v, (int, float)) for v in band)
            ):
                raise ValueError(
                    f"BandpassFilterBank: bands[{i}] must be a (low_hz, high_hz) tuple"
                )
            low, high = band
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    f"BandpassFilterBank: bands[{i}] must satisfy 0 < low_hz < high_hz"
                )
        if not isinstance(order, int) or order <= 0:
            raise ValueError("BandpassFilterBank: order must be a positive integer")

        fs = signal.frame.sample_rate_hz
        band_outputs = await asyncio.gather(
            *[_filter_band(signal.data, low, high, order, fs) for low, high in bands]
        )
        stacked = np.stack(band_outputs, axis=0)
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:bp-bank",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=stacked,
        )
