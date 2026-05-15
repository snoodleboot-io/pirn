"""``NLMSAdaptiveFilter`` — normalised LMS adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal payloads.
    2. Validate filter_length, step_size, and regularization.
    3. For each sample n: compute output y(n) = w^T(n) * x(n).
    4. Compute error: e(n) = d(n) - y(n).
    5. Normalise step by input power: mu_n = step_size / (||x(n)||^2 + regularization).
    6. Update weights: w(n+1) = w(n) + mu_n * e(n) * x(n).
    7. Return a SignalPayload of the error signal.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _nlms(
    signal_data: np.ndarray,
    reference_data: np.ndarray,
    filter_length: int,
    step_size: float,
    regularization: float,
) -> np.ndarray:
    """Run the NLMS adaptive filter loop and return the error signal."""
    n_samples = len(signal_data)
    output = np.zeros(n_samples)
    filter_weights = np.zeros(filter_length)
    for sample_index in range(filter_length, n_samples):
        input_buffer = signal_data[sample_index - filter_length : sample_index][::-1]
        filter_output = filter_weights @ input_buffer
        error = reference_data[sample_index] - filter_output
        mu_n = step_size / (regularization + input_buffer @ input_buffer)
        filter_weights = filter_weights + mu_n * error * input_buffer
        output[sample_index] = error
    return output


class NLMSAdaptiveFilter(Knot):
    """Normalised LMS adaptive filter (LMS with input-power normalisation)."""

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
        signal: SignalPayload,
        reference: SignalPayload,
        filter_length: int,
        step_size: float,
        regularization: float = 1e-6,
        **_: Any,
    ) -> SignalPayload:
        """Apply the normalised LMS filter to the signal using the reference.

        Args:
            signal: Input signal payload to filter.
            reference: Reference signal payload used to drive the normalised weight update.
            filter_length: Number of adaptive taps (positive integer).
            step_size: NLMS step size (must be positive).
            regularization: Small constant preventing division by zero (non-negative).

        Returns:
            SignalPayload containing the NLMS error signal.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("NLMSAdaptiveFilter: filter_length must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("NLMSAdaptiveFilter: step_size must be positive")
        if not isinstance(regularization, (int, float)) or regularization < 0:
            raise ValueError("NLMSAdaptiveFilter: regularization must be non-negative")
        if signal.frame.sample_rate_hz != reference.frame.sample_rate_hz:
            raise ValueError("NLMSAdaptiveFilter: signal and reference sample rates must match")

        sig_data = signal.data[0] if signal.data.ndim > 1 else signal.data
        ref_data = reference.data[0] if reference.data.ndim > 1 else reference.data

        result = await asyncio.to_thread(
            _nlms, sig_data, ref_data, filter_length, step_size, regularization
        )

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:nlms",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
