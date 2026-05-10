"""``SubbandAdaptiveFilter`` — subband-decomposition adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal payloads.
    2. Validate subband_count, filter_length_per_band, and step_size.
    3. Decompose both signal and reference into subband_count subbands using
       np.array_split on the time axis.
    4. For each subband k: run an LMS adaptive filter of length filter_length_per_band
       with the given step_size.
    5. Concatenate the per-band error outputs to reconstruct the full signal.
    6. Return a SignalPayload of the reconstructed, adapted output.

Math:
    Per-band LMS update:

    $$\\mathbf{w}_k(n+1) = \\mathbf{w}_k(n) + \\mu \\, e_k(n) \\, \\mathbf{x}_k(n)$$

    for each subband $k = 0, \\ldots, K-1$ where $K$ = subband_count and
    $L$ = filter_length_per_band taps per band.

References:
    - Gilloire, A. & Vetterli, M. (1992). "Adaptive filtering in subbands with critical sampling."
      IEEE Trans. Signal Process., 40(8), 1862-1875.
    - Sayed, A.H. (2003). "Fundamentals of Adaptive Filtering." Wiley-IEEE Press.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _lms_band(
    x: np.ndarray,
    d: np.ndarray,
    filter_length: int,
    step_size: float,
) -> np.ndarray:
    """Run LMS adaptive filter on a single subband and return the error signal."""
    n = len(x)
    w = np.zeros(filter_length)
    e_out = np.zeros(n)
    for i in range(filter_length, n):
        x_buf = x[i - filter_length : i][::-1]
        y = w @ x_buf
        e = d[i] - y
        w = w + step_size * e * x_buf
        e_out[i] = e
    return e_out


def _subband_lms(
    signal_data: np.ndarray,
    reference_data: np.ndarray,
    num_subbands: int,
    filter_length: int,
    step_size: float,
) -> np.ndarray:
    """Split into subbands, run per-band LMS, concatenate results."""
    sig_bands = np.array_split(signal_data, num_subbands)
    ref_bands = np.array_split(reference_data, num_subbands)
    out_bands = [
        _lms_band(sig_bands[k], ref_bands[k], filter_length, step_size) for k in range(num_subbands)
    ]
    return np.concatenate(out_bands)


class SubbandAdaptiveFilter(Knot):
    """Subband adaptive filter — decompose, adapt per band, reconstruct."""

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        subband_count: Knot | int,
        filter_length_per_band: Knot | int,
        step_size: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            subband_count=subband_count,
            filter_length_per_band=filter_length_per_band,
            step_size=step_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        reference: SignalPayload,
        subband_count: int,
        filter_length_per_band: int,
        step_size: float,
        **_: Any,
    ) -> SignalPayload:
        """Decompose the signal into subbands, adapt each band, and return the reconstructed SignalPayload.

        Args:
            signal: Input signal payload to decompose and filter per band.
            reference: Reference signal payload used to drive per-band adaptive filtering.
            subband_count: Number of subbands (integer > 1).
            filter_length_per_band: Number of taps per subband filter (positive integer).
            step_size: LMS step size (must be positive).

        Returns:
            SignalPayload of the reconstructed subband-filtered output.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(subband_count, int) or subband_count <= 1:
            raise ValueError("SubbandAdaptiveFilter: subband_count must be an integer > 1")
        if not isinstance(filter_length_per_band, int) or filter_length_per_band <= 0:
            raise ValueError(
                "SubbandAdaptiveFilter: filter_length_per_band must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("SubbandAdaptiveFilter: step_size must be positive")
        if signal.frame.sample_rate_hz != reference.frame.sample_rate_hz:
            raise ValueError("SubbandAdaptiveFilter: signal and reference sample rates must match")

        sig_data = signal.data[0] if signal.data.ndim > 1 else signal.data
        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data

        result = await asyncio.to_thread(
            _subband_lms, sig_data, ref_data, subband_count, filter_length_per_band, step_size
        )

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:subband-adaptive",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
