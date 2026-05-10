"""``ANCPipeline`` — active noise control pipeline using LMS-based adaptive filter.

Algorithm:
    1. Receive the reference and error signal payloads.
    2. Validate step_size is in (0, 1] and filter_length is a positive integer.
    3. Verify that reference and error have matching sample rates.
    4. For each sample: compute anti-noise output y(n) = w^T * x(n).
    5. Update filter weights: w(n+1) = w(n) + step_size * e(n) * x(n).
    6. Return a SignalPayload containing the anti-noise output (error signal).

Math:
    LMS weight update:

    $$\\mathbf{w}(n+1) = \\mathbf{w}(n) + \\mu \\, e(n) \\, \\mathbf{x}(n)$$

    where:
    - $\\mathbf{w}(n) \\in \\mathbb{R}^L$ are the adaptive filter coefficients
    - $\\mu \\in (0, 1]$ is the step_size
    - $e(n)$ is the error signal sample (residual noise)
    - $\\mathbf{x}(n)$ is the reference signal buffer

References:
    - Widrow, B. & Stearns, S.D. (1985). "Adaptive Signal Processing." Prentice-Hall.
    - Kuo, S.M. & Morgan, D.R. (1996). "Active Noise Control Systems." Wiley.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _lms_anc(
    reference_data: np.ndarray,
    error_data: np.ndarray,
    filter_length: int,
    step_size: float,
) -> np.ndarray:
    """Run LMS-based active noise control and return the residual error signal."""
    n_samples = len(reference_data)
    w = np.zeros(filter_length)
    e_out = np.zeros(n_samples)
    for n in range(filter_length, n_samples):
        x = reference_data[n - filter_length : n][::-1]
        y = w @ x
        e = error_data[n] - y
        w = w + step_size * e * x
        e_out[n] = e
    return e_out


class ANCPipeline(Knot):
    """Active noise control pipeline using LMS-based adaptive filtering."""

    def __init__(
        self,
        *,
        reference: Knot,
        error: Knot,
        step_size: Knot | float,
        filter_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            reference=reference,
            error=error,
            step_size=step_size,
            filter_length=filter_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        reference: SignalPayload,
        error: SignalPayload,
        step_size: float,
        filter_length: int,
        **_: Any,
    ) -> SignalPayload:
        """Compute the anti-noise output by adapting LMS filter weights against the error signal.

        Args:
            reference: Reference signal payload capturing the noise source.
            error: Error signal payload (residual noise at the cancellation point).
            step_size: LMS step size in (0, 1].
            filter_length: Number of filter taps (positive integer).

        Returns:
            SignalPayload containing the residual error (anti-noise output).

        Raises:
            ValueError: If step_size or filter_length are invalid, or sample rates differ.
        """
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError("ANCPipeline: step_size must be in range (0, 1]")
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("ANCPipeline: filter_length must be a positive integer")
        if reference.frame.sample_rate_hz != error.frame.sample_rate_hz:
            raise ValueError("ANCPipeline: reference and error sample_rate_hz must match")

        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data
        err_data = error.data[0] if error.data.ndim > 1 else error.data

        result = await asyncio.to_thread(_lms_anc, ref_data, err_data, filter_length, step_size)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{reference.frame.signal_id}:anc",
                channel_count=1,
                sample_rate_hz=reference.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
