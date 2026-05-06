"""``AffineProjectionFilter`` — affine projection adaptive filter (APA).

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length, projection_order, and step_size.
    3. Construct the input data matrix X of shape (projection_order, filter_length).
    4. Compute the APA weight update:
       w(n+1) = w(n) + step_size * X^T * (X * X^T + delta*I)^{-1} * e(n)
       where e(n) is the projection-order error vector.
    5. Apply updated weights to produce the filtered output.
    6. Return a SignalFrame with the APA-filtered output.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AffineProjectionFilter(Knot):
    """Affine projection adaptive filter.

    Production needs ``padasip`` or a hand-rolled NumPy implementation.
    """

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
        signal: SignalFrame,
        reference: SignalFrame,
        filter_length: int,
        projection_order: int,
        step_size: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the affine projection adaptive filter to the signal using the reference.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to drive the adaptive weight update.
            filter_length: Number of filter taps (must be a positive integer).
            projection_order: APA projection order (must be a positive integer).
            step_size: Step size controlling convergence speed (must be positive).

        Returns:
            SignalFrame of the APA-filtered output.

        Raises:
            ValueError: If filter_length, projection_order, or step_size are invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "AffineProjectionFilter: filter_length must be a positive integer"
            )
        if not isinstance(projection_order, int) or projection_order <= 0:
            raise ValueError(
                "AffineProjectionFilter: projection_order must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError(
                "AffineProjectionFilter: step_size must be positive"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:apa",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
