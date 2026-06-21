"""``EchoCanceller`` — acoustic echo cancellation.

Algorithm:
    1. Receive the microphone (near-end) and far-end reference signal payloads.
    2. Validate filter_length and step_size.
    3. Verify that microphone and far_end have matching sample rates.
    4. Model the echo path using an LMS adaptive filter of length filter_length.
    5. For each sample n: estimate echo y(n) = w^T * x_far(n).
    6. Compute error: e(n) = mic(n) - y(n).
    7. Update weights: w(n+1) = w(n) + step_size * e(n) * x_far(n).
    8. Return a SignalPayload with the estimated echo removed.

Math:
    LMS weight update for echo path modelling:

    $$\\mathbf{w}(n+1) = \\mathbf{w}(n) + \\mu \\, e(n) \\, \\mathbf{x}_{\\text{far}}(n)$$

    where:
    - $\\mathbf{w}(n) \\in \\mathbb{R}^L$ models the acoustic echo path
    - $\\mu \\in (0, 1]$ is the step_size
    - $e(n) = s(n) - \\mathbf{w}^T(n) \\mathbf{x}_{\\text{far}}(n)$ is the residual

References:
    - Sondhi, M.M. & Berkley, D.A. (1980). "Silencing echoes on the telephone network."
      Proc. IEEE, 68(8), 948-963.
    - Haykin, S. (2002). "Adaptive Filter Theory" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


def _lms_echo(
    mic_data: np.ndarray,
    far_data: np.ndarray,
    filter_length: int,
    step_size: float,
) -> np.ndarray:
    """Run LMS-based echo cancellation and return the residual (echo-cancelled) signal."""
    n_samples = len(mic_data)
    filter_weights = np.zeros(filter_length)
    e_out = np.zeros(n_samples)
    for sample_index in range(filter_length, n_samples):
        far_buffer = far_data[sample_index - filter_length : sample_index][::-1]
        echo_estimate = filter_weights @ far_buffer
        residual = mic_data[sample_index] - echo_estimate
        filter_weights = filter_weights + step_size * residual * far_buffer
        e_out[sample_index] = residual
    return e_out


class EchoCanceller(Knot):
    """Acoustic echo canceller using LMS adaptive filtering."""

    def __init__(
        self,
        *,
        microphone: Knot,
        far_end: Knot,
        filter_length: Knot | int,
        step_size: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            microphone=microphone,
            far_end=far_end,
            filter_length=filter_length,
            step_size=step_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        microphone: SignalPayload,
        far_end: SignalPayload,
        filter_length: int,
        step_size: float,
        **_: Any,
    ) -> SignalPayload:
        """Remove acoustic echo from the microphone signal using the far-end reference.

        Args:
            microphone: Near-end microphone signal payload containing speech plus echo.
            far_end: Far-end reference signal payload used to model the echo path.
            filter_length: Number of LMS taps (positive integer).
            step_size: LMS step size in (0, 1].

        Returns:
            SignalPayload with the estimated echo removed.

        Raises:
            ValueError: If filter_length or step_size are invalid, or sample rates differ.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("EchoCanceller: filter_length must be a positive integer")
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError("EchoCanceller: step_size must be in range (0, 1]")
        if microphone.frame.sample_rate_hz != far_end.frame.sample_rate_hz:
            raise ValueError("EchoCanceller: microphone and far_end sample rates must match")

        mic_data = microphone.data[0] if microphone.data.ndim > 1 else microphone.data
        far_data = far_end.data[0] if far_end.data.ndim > 1 else far_end.data

        result = await asyncio.to_thread(_lms_echo, mic_data, far_data, filter_length, step_size)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{microphone.frame.signal_id}:echo_cancelled",
                channel_count=1,
                sample_rate_hz=microphone.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
