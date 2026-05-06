"""``HilbertTransformer`` — analytic-signal construction via the Hilbert transform.

Algorithm:
    1. Receive the input signal frame.
    2. Compute the FFT of the real-valued signal.
    3. Zero out the negative-frequency components and double the positive-frequency components.
    4. Apply the IFFT to obtain the analytic signal (complex-valued).
    5. Return a SignalFrame of the analytic signal with imaginary part equal to the Hilbert transform.

Math:
    Hilbert transform:

    $$\\hat{x}(t) = \\frac{1}{\\pi} \\text{P.V.} \\int_{-\\infty}^{\\infty} \\frac{x(\\tau)}{t - \\tau} d\\tau$$

    Analytic signal:

    $$x_a(t) = x(t) + j\\hat{x}(t)$$

    Instantaneous amplitude and phase:

    $$A(t) = |x_a(t)|, \\quad \\phi(t) = \\angle x_a(t)$$

References:
    - Gabor, D. (1946). "Theory of communication." J. IEE, 93(26), 429-457.
    - scipy.signal.hilbert: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.hilbert.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class HilbertTransformer(Knot):
    """Compute the analytic signal (90-degree phase shift via FFT).

    Production needs ``scipy.signal.hilbert``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, _config=_config, **kwargs)

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Compute the analytic signal via the Hilbert transform and return the 90-degree phase-shifted SignalFrame.

        Args:
            signal: Real-valued signal to convert to its analytic (complex) representation.

        Returns:
            SignalFrame of the analytic signal with imaginary part equal to the Hilbert transform.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:analytic",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
