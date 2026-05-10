"""``LMSAdaptiveFilter`` — least-mean-squares adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal payloads.
    2. Validate filter_length and step_size.
    3. Verify that signal and reference have matching sample rates.
    4. For each sample n: compute output y(n) = w^T(n) * x(n).
    5. Compute error: e(n) = d(n) - y(n) where d(n) is the reference sample.
    6. Update weights: w(n+1) = w(n) + step_size * e(n) * x(n).
    7. Return a SignalPayload of the error signal.

Math:
    LMS weight update (Widrow-Hoff):

    $$\\mathbf{w}(n+1) = \\mathbf{w}(n) + \\mu \\, e(n) \\, \\mathbf{x}(n)$$

    where:
    - $\\mathbf{w}(n) \\in \\mathbb{R}^L$ are the adaptive tap weights (L = filter_length)
    - $\\mu > 0$ is the step_size
    - $e(n) = d(n) - \\mathbf{w}^T(n) \\mathbf{x}(n)$ is the instantaneous error

References:
    - Widrow, B. & Hoff, M.E. (1960). "Adaptive switching circuits." IRE WESCON Conv. Rec., 96-104.
    - Haykin, S. (2002). "Adaptive Filter Theory" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _lms(
    signal_data: np.ndarray,
    reference_data: np.ndarray,
    filter_length: int,
    step_size: float,
) -> np.ndarray:
    """Run the LMS adaptive filter loop and return the error signal."""
    n_samples = len(signal_data)
    output = np.zeros(n_samples)
    w = np.zeros(filter_length)
    for n in range(filter_length, n_samples):
        x = signal_data[n - filter_length : n][::-1]
        y = w @ x
        e = reference_data[n] - y
        w = w + step_size * e * x
        output[n] = e
    return output


class LMSAdaptiveFilter(Knot):
    """Stochastic-gradient LMS adaptive filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: Knot | int,
        step_size: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            filter_length=filter_length,
            step_size=step_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        reference: SignalPayload,
        filter_length: int,
        step_size: float,
        **_: Any,
    ) -> SignalPayload:
        """Adapt the LMS filter weights against the reference and return the error SignalPayload.

        Args:
            signal: Input signal payload to filter.
            reference: Reference signal payload used to compute the error and update weights.
            filter_length: Number of adaptive taps (positive integer).
            step_size: LMS step size (must be positive).

        Returns:
            SignalPayload containing the LMS error signal.

        Raises:
            ValueError: If filter_length or step_size are invalid, or sample rates differ.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("LMSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("LMSAdaptiveFilter: step_size must be positive")
        if signal.frame.sample_rate_hz != reference.frame.sample_rate_hz:
            raise ValueError("LMSAdaptiveFilter: signal and reference sample rates must match")

        sig_data = signal.data[0] if signal.data.ndim > 1 else signal.data
        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data

        result = await asyncio.to_thread(_lms, sig_data, ref_data, filter_length, step_size)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:lms",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
