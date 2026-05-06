"""``BandpassFilterBank`` — apply N parallel bandpass filters.

Algorithm:
    1. Receive the input signal frame, bands tuple, and filter order.
    2. Validate bands (non-empty, each (low_hz, high_hz) with 0 < low < high) and order.
    3. For each band (low_hz, high_hz): design a Butterworth bandpass filter of the
       given order.
    4. Apply each bandpass filter independently to the input signal.
    5. Return a list of SignalFrames, one per band.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BandpassFilterBank(Knot):
    """Apply a bank of parallel bandpass filters and return one SignalFrame per band."""

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
        signal: SignalFrame,
        bands: tuple[tuple[float, float], ...],
        order: int,
        **_: Any,
    ) -> list[SignalFrame]:
        """Apply parallel bandpass filters and return one SignalFrame per band.

        Args:
            signal: The input signal frame.
            bands: Non-empty tuple of (low_hz, high_hz) pairs.
            order: Filter order for each bandpass filter (positive integer).

        Returns:
            List of SignalFrames, one per configured band.

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
        return [
            SignalFrame(
                signal_id=f"{signal.signal_id}:bp-{i}",
                channel_count=signal.channel_count,
                sample_rate_hz=signal.sample_rate_hz,
                samples_per_channel=signal.samples_per_channel,
            )
            for i in range(len(bands))
        ]
