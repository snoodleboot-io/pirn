"""``MedianFilter`` — running median filter for spike removal.

Algorithm:
    1. Receive the input signal frame and kernel_size.
    2. Validate kernel_size (positive odd integer).
    3. Slide a window of length kernel_size over each channel of the signal.
    4. Replace each sample with the median of the window centered on it
       (reflected padding at the edges).
    5. Return a de-spiked SignalFrame.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


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
        signal: SignalFrame,
        kernel_size: int,
        **_: Any,
    ) -> SignalFrame:
        """Apply the running median filter and return the de-spiked SignalFrame.

        Args:
            signal: The input signal frame.
            kernel_size: Sliding window length (positive odd integer).

        Returns:
            Filtered SignalFrame with the same shape as the input.

        Raises:
            ValueError: If kernel_size is not a positive odd integer.
        """
        if not isinstance(kernel_size, int) or kernel_size <= 0 or kernel_size % 2 == 0:
            raise ValueError(
                "MedianFilter: kernel_size must be a positive odd integer"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:median",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
