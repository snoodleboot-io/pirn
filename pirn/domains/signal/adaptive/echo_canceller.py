"""``EchoCanceller`` — acoustic echo cancellation.

Algorithm:
    1. Receive the microphone (near-end) and far-end reference signal frames.
    2. Validate filter_length and step_size.
    3. Verify that microphone and far_end have matching sample rates.
    4. Model the echo path using an LMS adaptive filter of length filter_length.
    5. For each sample n: estimate echo y(n) = w^T * x_far(n).
    6. Compute error: e(n) = mic(n) - y(n).
    7. Update weights: w(n+1) = w(n) + step_size * e(n) * x_far(n).
    8. Return a SignalFrame with the estimated echo removed.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class EchoCanceller(Knot):
    """Acoustic echo canceller using LMS adaptive filtering.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

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
        microphone: SignalFrame,
        far_end: SignalFrame,
        filter_length: int,
        step_size: float,
        **_: Any,
    ) -> SignalFrame:
        """Remove acoustic echo from the microphone signal using the far-end reference.

        Args:
            microphone: Near-end microphone signal containing speech plus echo.
            far_end: Far-end reference signal used to model the echo path.
            filter_length: Number of LMS taps (positive integer).
            step_size: LMS step size in (0, 1].

        Returns:
            SignalFrame with the estimated echo removed.

        Raises:
            ValueError: If filter_length or step_size are invalid, or sample rates differ.
        """
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "EchoCanceller: filter_length must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError(
                "EchoCanceller: step_size must be in range (0, 1]"
            )
        if microphone.sample_rate_hz != far_end.sample_rate_hz:
            raise ValueError(
                "EchoCanceller: microphone and far_end sample rates must match"
            )
        return SignalFrame(
            signal_id=f"{microphone.signal_id}:echo_cancelled",
            channel_count=microphone.channel_count,
            sample_rate_hz=microphone.sample_rate_hz,
            samples_per_channel=microphone.samples_per_channel,
        )
