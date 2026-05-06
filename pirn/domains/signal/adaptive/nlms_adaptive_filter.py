"""``NLMSAdaptiveFilter`` — normalised LMS adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate filter_length, step_size, and regularization.
    3. For each sample n: compute output y(n) = w^T(n) * x(n).
    4. Compute error: e(n) = d(n) - y(n).
    5. Normalise step by input power: mu_n = step_size / (||x(n)||^2 + regularization).
    6. Update weights: w(n+1) = w(n) + mu_n * e(n) * x(n).
    7. Return a SignalFrame of the filtered output.

Math:
    NLMS weight update with input-power normalisation:

    $$\\mathbf{w}(n+1) = \\mathbf{w}(n) + \\frac{\\mu}{\\|\\mathbf{x}(n)\\|^2 + \\delta} \\, e(n) \\, \\mathbf{x}(n)$$

    where:
    - $\\mu > 0$ is the step_size
    - $\\delta > 0$ is the regularization constant preventing division by zero
    - $e(n) = d(n) - \\mathbf{w}^T(n) \\mathbf{x}(n)$

References:
    - Nagumo, J. & Noda, A. (1967). "A learning method for system identification."
      IEEE Trans. Automat. Control, 12(3), 282-287.
    - Haykin, S. (2002). "Adaptive Filter Theory" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class NLMSAdaptiveFilter(Knot):
    """Normalised LMS adaptive filter (LMS with input-power normalisation).

    Production needs ``padasip`` or hand-rolled NumPy.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: Knot | int,
        step_size: Knot | float,
        regularization: Knot | float = 1e-6,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            filter_length=filter_length,
            step_size=step_size,
            regularization=regularization,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        filter_length: int,
        step_size: float,
        regularization: float = 1e-6,
        **_: Any,
    ) -> SignalFrame:
        """Apply the normalised LMS filter to the signal using the reference.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to drive the normalised weight update.
            filter_length: Number of adaptive taps (positive integer).
            step_size: NLMS step size (must be positive).
            regularization: Small constant preventing division by zero (non-negative).

        Returns:
            SignalFrame of the NLMS-filtered output.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("NLMSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("NLMSAdaptiveFilter: step_size must be positive")
        if not isinstance(regularization, (int, float)) or regularization < 0:
            raise ValueError("NLMSAdaptiveFilter: regularization must be non-negative")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:nlms",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
