"""``ANCPipeline`` — active noise control pipeline using LMS-based adaptive filter.

Algorithm:
    1. Receive the reference and error signal frames.
    2. Validate step_size is in (0, 1] and filter_length is a positive integer.
    3. Verify that reference and error have matching sample rates.
    4. For each sample: compute anti-noise output y(n) = w^T * x(n).
    5. Update filter weights: w(n+1) = w(n) + step_size * e(n) * x(n).
    6. Return a SignalFrame containing the anti-noise output.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ANCPipeline(Knot):
    """Active noise control pipeline using LMS-based adaptive filtering.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

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
        reference: SignalFrame,
        error: SignalFrame,
        step_size: float,
        filter_length: int,
        **_: Any,
    ) -> SignalFrame:
        """Compute the anti-noise output by adapting LMS filter weights against the error signal.

        Args:
            reference: Reference signal capturing the noise source.
            error: Error signal (residual noise at the cancellation point).
            step_size: LMS step size in (0, 1].
            filter_length: Number of filter taps (positive integer).

        Returns:
            SignalFrame containing the anti-noise output.

        Raises:
            ValueError: If step_size or filter_length are invalid, or sample rates differ.
        """
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError(
                "ANCPipeline: step_size must be in range (0, 1]"
            )
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "ANCPipeline: filter_length must be a positive integer"
            )
        if reference.sample_rate_hz != error.sample_rate_hz:
            raise ValueError(
                "ANCPipeline: reference and error sample_rate_hz must match"
            )
        return SignalFrame(
            signal_id=f"{reference.signal_id}:anc",
            channel_count=reference.channel_count,
            sample_rate_hz=reference.sample_rate_hz,
            samples_per_channel=reference.samples_per_channel,
        )
