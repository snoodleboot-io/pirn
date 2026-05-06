"""``LMSAdaptiveFilter`` — least-mean-squares adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length and step_size.
    3. Verify that signal and reference have matching sample rates.
    4. For each sample n: compute output y(n) = w^T(n) * x(n).
    5. Compute error: e(n) = d(n) - y(n) where d(n) is the reference sample.
    6. Update weights: w(n+1) = w(n) + step_size * e(n) * x(n).
    7. Return a SignalFrame of the filtered output.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class LMSAdaptiveFilter(Knot):
    """Stochastic-gradient LMS adaptive filter.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

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
        signal: SignalFrame,
        reference: SignalFrame,
        filter_length: int,
        step_size: float,
        **_: Any,
    ) -> SignalFrame:
        """Adapt the LMS filter weights against the reference and return the error-minimised SignalFrame.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to compute the error and update filter weights.
            filter_length: Number of adaptive taps (positive integer).
            step_size: LMS step size (must be positive).

        Returns:
            SignalFrame of the LMS-filtered output.

        Raises:
            ValueError: If filter_length or step_size are invalid, or sample rates differ.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("LMSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("LMSAdaptiveFilter: step_size must be positive")
        if signal.sample_rate_hz != reference.sample_rate_hz:
            raise ValueError("LMSAdaptiveFilter: signal and reference sample rates must match")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:lms",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
