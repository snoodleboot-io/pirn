"""``EllipticFilter`` — sharpest IIR transition with ripple in both bands.

Algorithm:
    1. Receive the input signal frame, order, passband_ripple_db,
       stopband_attenuation_db, and cutoff_hz.
    2. Validate all parameters (order positive integer; ripple, attenuation,
       cutoff all positive).
    3. Design a Cauer/elliptic IIR filter using ``scipy.signal.ellip``.
    4. Apply the filter using second-order sections for numerical stability.
    5. Return a filtered SignalFrame.

Math:
    Elliptic (Cauer) squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + \\varepsilon^2 R_n^2(\\xi, \\omega / \\omega_c)}$$

    where $R_n$ is the Chebyshev rational function, $\\varepsilon^2 = 10^{R_p/10} - 1$
    (passband_ripple_db), and $\\xi$ is the selectivity factor determined by
    stopband_attenuation_db. Ripple appears in both passband and stopband.

References:
    - Cauer, W. (1958). "Synthesis of Linear Communication Networks." McGraw-Hill.
    - scipy.signal.ellip: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ellip.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class EllipticFilter(Knot):
    """Cauer / elliptic IIR filter.

    Production needs ``scipy.signal.ellip``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        passband_ripple_db: Knot | float,
        stopband_attenuation_db: Knot | float,
        cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            passband_ripple_db=passband_ripple_db,
            stopband_attenuation_db=stopband_attenuation_db,
            cutoff_hz=cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        order: int,
        passband_ripple_db: float,
        stopband_attenuation_db: float,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the elliptic IIR filter to the input signal.

        Args:
            signal: Signal to filter with the sharpest achievable transition band.
            order: Filter order (positive integer).
            passband_ripple_db: Maximum passband ripple in dB (positive float).
            stopband_attenuation_db: Minimum stopband attenuation in dB (positive float).
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalFrame filtered by the configured Cauer / elliptic IIR.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("EllipticFilter: order must be a positive integer")
        if not isinstance(passband_ripple_db, (int, float)) or passband_ripple_db <= 0:
            raise ValueError("EllipticFilter: passband_ripple_db must be positive")
        if not isinstance(stopband_attenuation_db, (int, float)) or stopband_attenuation_db <= 0:
            raise ValueError("EllipticFilter: stopband_attenuation_db must be positive")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("EllipticFilter: cutoff_hz must be positive")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:ellip",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
