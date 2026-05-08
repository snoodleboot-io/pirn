"""``AffineProjectionFilter`` — affine projection adaptive filter (APA).

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length, projection_order, and step_size.
    3. Construct the input data matrix X of shape (projection_order, filter_length).
    4. Compute the APA weight update:
       w(n+1) = w(n) + step_size * X^T * (X * X^T + delta*I)^{-1} * e(n)
       where e(n) is the projection-order error vector.
    5. Apply updated weights to produce the filtered output.
    6. Return a SignalPayload with the APA error signal.

Math:
    Weight update equation:

    $$\\mathbf{w}(n+1) = \\mathbf{w}(n) + \\mu \\mathbf{X}^T \\left( \\mathbf{X} \\mathbf{X}^T + \\delta \\mathbf{I} \\right)^{-1} \\mathbf{e}(n)$$

    where:
    - $\\mathbf{X} \\in \\mathbb{R}^{P \\times L}$ is the data matrix (P = projection_order, L = filter_length)
    - $\\mu$ is the step_size
    - $\\delta$ is a regularisation constant
    - $\\mathbf{e}(n)$ is the P-dimensional error vector

References:
    - Ozeki, K. & Umeda, T. (1984). "An adaptive filtering algorithm using an orthogonal projection
      to an affine subspace." Electronics & Communications in Japan, 67(5), 19-27.
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

_apf_delta = 1e-6


def _apf(
    signal_data: np.ndarray,
    reference_data: np.ndarray,
    filter_length: int,
    projection_order: int,
    step_size: float,
) -> np.ndarray:
    """Run the affine projection adaptive filter loop and return the error signal."""
    n_samples = len(signal_data)
    w = np.zeros(filter_length)
    e_out = np.zeros(n_samples)
    start = filter_length + projection_order - 1
    for n in range(start, n_samples):
        X = np.stack(
            [signal_data[n - p - filter_length : n - p][::-1] for p in range(projection_order)],
            axis=0,
        )
        d = reference_data[n - projection_order + 1 : n + 1][::-1]
        y = X @ w
        e_vec = d - y
        gram = X @ X.T + _apf_delta * np.eye(projection_order)
        w = w + step_size * X.T @ np.linalg.solve(gram, e_vec)
        e_out[n] = e_vec[0]
    return e_out


class AffineProjectionFilter(Knot):
    """Affine projection adaptive filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: Knot | int,
        projection_order: Knot | int,
        step_size: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            filter_length=filter_length,
            projection_order=projection_order,
            step_size=step_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        reference: SignalPayload,
        filter_length: int,
        projection_order: int,
        step_size: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the affine projection adaptive filter to the signal using the reference.

        Args:
            signal: Input signal payload to filter.
            reference: Reference signal payload used to drive the adaptive weight update.
            filter_length: Number of filter taps (must be a positive integer).
            projection_order: APA projection order (must be a positive integer).
            step_size: Step size controlling convergence speed (must be positive).

        Returns:
            SignalPayload of the APA error signal.

        Raises:
            ValueError: If filter_length, projection_order, or step_size are invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("AffineProjectionFilter: filter_length must be a positive integer")
        if not isinstance(projection_order, int) or projection_order <= 0:
            raise ValueError("AffineProjectionFilter: projection_order must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("AffineProjectionFilter: step_size must be positive")
        if signal.frame.sample_rate_hz != reference.frame.sample_rate_hz:
            raise ValueError("AffineProjectionFilter: signal and reference sample rates must match")

        sig_data = signal.data[0] if signal.data.ndim > 1 else signal.data
        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data

        result = await asyncio.to_thread(
            _apf, sig_data, ref_data, filter_length, projection_order, step_size
        )

        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:apa",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
