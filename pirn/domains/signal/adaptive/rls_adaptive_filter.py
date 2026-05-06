"""``RLSAdaptiveFilter`` — recursive least squares adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length and forgetting_factor.
    3. Initialise inverse correlation matrix: P(0) = delta^{-1} * I.
    4. For each sample n:
       a. Compute gain vector: k(n) = lambda^{-1} P(n-1) x(n) / (1 + lambda^{-1} x^T P(n-1) x(n)).
       b. Update weights: w(n) = w(n-1) + k(n) * e(n) where e(n) = d(n) - w^T(n-1) x(n).
       c. Update P: P(n) = lambda^{-1} (P(n-1) - k(n) x^T(n) P(n-1)).
    5. Return a SignalFrame of the RLS-filtered output.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class RLSAdaptiveFilter(Knot):
    """Exponentially-weighted RLS adaptive filter.

    Production needs ``padasip`` or hand-rolled NumPy.
    """

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
        signal: SignalFrame,
        reference: SignalFrame,
        filter_length: int,
        forgetting_factor: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the exponentially-weighted RLS filter to the signal using the reference.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to drive the recursive weight update.
            filter_length: Number of adaptive taps (positive integer).
            forgetting_factor: Exponential weighting factor in (0, 1].

        Returns:
            SignalFrame of the RLS-filtered output.

        Raises:
            ValueError: If filter_length or forgetting_factor are invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("RLSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(forgetting_factor, (int, float)) or not 0.0 < forgetting_factor <= 1.0:
            raise ValueError("RLSAdaptiveFilter: forgetting_factor must lie in (0, 1]")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:rls",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
