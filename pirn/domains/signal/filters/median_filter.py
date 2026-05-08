"""``MedianFilter`` — running median filter for spike removal.

Algorithm:
    1. Receive the input signal payload and kernel_size.
    2. Validate kernel_size (positive odd integer).
    3. Apply scipy.ndimage.median_filter with size adapted to data dimensionality.
    4. Return a de-spiked SignalPayload.

Math:
    Running median:

    $$y(n) = \\text{median}\\left\\{ x(n - \\lfloor K/2 \\rfloor), \\ldots, x(n + \\lfloor K/2 \\rfloor) \\right\\}$$

    where $K$ = kernel_size (odd). The median filter is non-linear and has
    no closed-form frequency response, but it suppresses impulsive noise
    (salt-and-pepper spikes) while preserving step edges.

References:
    - Tukey, J.W. (1977). "Exploratory Data Analysis." Addison-Wesley.
    - scipy.ndimage.median_filter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.median_filter.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy.ndimage import median_filter

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _apply_median_filter(data: np.ndarray, kernel_size: int) -> np.ndarray:
    """Apply scipy.ndimage.median_filter with size matched to data shape."""
    if data.ndim == 1:
        return median_filter(data, size=kernel_size)
    return median_filter(data, size=(1, kernel_size))


class MedianFilter(Knot):
    """Apply a running median filter to suppress impulsive noise spikes."""

    def __init__(
        self,
        *,
        signal: Knot,
        kernel_size: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            kernel_size=kernel_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        kernel_size: int,
        **_: Any,
    ) -> SignalPayload:
        """Apply the running median filter and return the de-spiked SignalPayload.

        Args:
            signal: The input signal payload.
            kernel_size: Sliding window length (positive odd integer).

        Returns:
            Filtered SignalPayload with the same shape as the input.

        Raises:
            ValueError: If kernel_size is not a positive odd integer.
        """
        if not isinstance(kernel_size, int) or kernel_size <= 0 or kernel_size % 2 == 0:
            raise ValueError("MedianFilter: kernel_size must be a positive odd integer")

        filtered = await asyncio.to_thread(_apply_median_filter, signal.data, kernel_size)
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:median",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
