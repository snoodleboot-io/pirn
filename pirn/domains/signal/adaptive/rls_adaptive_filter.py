"""``RLSAdaptiveFilter`` — recursive least squares adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length and forgetting_factor.
    3. Initialise inverse correlation matrix: P(0) = delta^{-1} * I.
    4. For each sample n:
       a. Compute gain vector: k(n) = lambda^{-1} P(n-1) x(n) / (1 + lambda^{-1} x^T P(n-1) x(n)).
       b. Update weights: w(n) = w(n-1) + k(n) * e(n) where e(n) = d(n) - w^T(n-1) x(n).
       c. Update P: P(n) = lambda^{-1} (P(n-1) - k(n) x^T(n) P(n-1)).
    5. Return a SignalPayload of the RLS error signal.

Math:
    RLS Kalman gain and weight update:

    $$\\mathbf{k}(n) = \\frac{\\lambda^{-1} \\mathbf{P}(n-1) \\mathbf{x}(n)}{1 + \\lambda^{-1} \\mathbf{x}^T(n) \\mathbf{P}(n-1) \\mathbf{x}(n)}$$

    $$\\mathbf{w}(n) = \\mathbf{w}(n-1) + \\mathbf{k}(n) \\, e(n)$$

    where $\\lambda \\in (0,1]$ is the forgetting_factor controlling exponential weighting of past data.

References:
    - Haykin, S. (2002). "Adaptive Filter Theory" (4th ed.). Prentice Hall. Chapter 13.
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


def _rls(
    signal_data: np.ndarray,
    reference_data: np.ndarray,
    filter_length: int,
    forgetting_factor: float,
) -> np.ndarray:
    """Run the RLS adaptive filter loop and return the error signal."""
    n_samples = len(signal_data)
    lam_inv = 1.0 / forgetting_factor
    w = np.zeros(filter_length)
    P = np.eye(filter_length) * 1e4
    e_out = np.zeros(n_samples)
    for n in range(filter_length, n_samples):
        x = signal_data[n - filter_length : n][::-1]
        Px = P @ x
        denom = 1.0 + lam_inv * (x @ Px)
        k = (lam_inv * Px) / denom
        y = w @ x
        e = reference_data[n] - y
        w = w + k * e
        P = lam_inv * (P - np.outer(k, x) @ P)
        e_out[n] = e
    return e_out


class RLSAdaptiveFilter(Knot):
    """Exponentially-weighted RLS adaptive filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: Knot | int,
        forgetting_factor: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            filter_length=filter_length,
            forgetting_factor=forgetting_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        reference: SignalPayload,
        filter_length: int,
        forgetting_factor: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the exponentially-weighted RLS filter to the signal using the reference.

        Args:
            signal: Input signal payload to filter.
            reference: Reference signal payload used to drive the recursive weight update.
            filter_length: Number of adaptive taps (positive integer).
            forgetting_factor: Exponential weighting factor in (0, 1].

        Returns:
            SignalPayload containing the RLS error signal.

        Raises:
            ValueError: If filter_length or forgetting_factor are invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("RLSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(forgetting_factor, (int, float)) or not 0.0 < forgetting_factor <= 1.0:
            raise ValueError("RLSAdaptiveFilter: forgetting_factor must lie in (0, 1]")
        if signal.frame.sample_rate_hz != reference.frame.sample_rate_hz:
            raise ValueError("RLSAdaptiveFilter: signal and reference sample rates must match")

        sig_data = signal.data[0] if signal.data.ndim > 1 else signal.data
        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data

        result = await asyncio.to_thread(_rls, sig_data, ref_data, filter_length, forgetting_factor)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:rls",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
