"""``Interpolator`` — generic interpolation knot.

Algorithm:
    1. Receive the input signal frame, target_sample_rate_hz, and kind.
    2. Validate target_sample_rate_hz (positive float) and kind (one of
       ``linear``, ``cubic``, ``quadratic``, ``spline``).
    3. Compute a continuous-time representation using the selected interpolation
       method (``scipy.interpolate.interp1d`` or equivalent).
    4. Evaluate the interpolant at the new sample times spaced at
       1 / target_sample_rate_hz.
    5. Return a SignalFrame at the target rate with the proportionally larger sample count.

Math:
    Resampled sample count:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\frac{f_{\\text{target}}}{f_{\\text{in}}} \\right\\rfloor$$

    Cubic spline evaluation at sample times $t_k = k / f_{\\text{target}}$.

References:
    - Stein, E.M. & Shakarchi, R. (2003). "Fourier Analysis: An Introduction." Princeton UP.
    - scipy.interpolate.interp1d: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Interpolator(Knot):
    """Interpolate a signal to a new (higher) sample rate.

    Production needs ``scipy.interpolate`` or ``scipy.signal``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        target_sample_rate_hz: Knot | float,
        kind: Knot | str = "cubic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            target_sample_rate_hz=target_sample_rate_hz,
            kind=kind,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        target_sample_rate_hz: float,
        kind: str = "cubic",
        **_: Any,
    ) -> SignalFrame:
        """Interpolate the signal to the configured target sample rate.

        Args:
            signal: Signal to interpolate to a higher sample rate.
            target_sample_rate_hz: Target sample rate in Hz (positive float).
            kind: Interpolation method — ``linear``, ``cubic``, ``quadratic``, or ``spline``.

        Returns:
            SignalFrame at the configured target sample rate with an adjusted sample count.

        Raises:
            ValueError: If target_sample_rate_hz or kind are invalid.
        """
        if not isinstance(target_sample_rate_hz, (int, float)) or target_sample_rate_hz <= 0:
            raise ValueError("Interpolator: target_sample_rate_hz must be positive")
        if kind not in frozenset({"linear", "cubic", "quadratic", "spline"}):
            raise ValueError(
                "Interpolator: kind must be 'linear', 'cubic', 'quadratic', or 'spline'"
            )
        if signal.sample_rate_hz > 0:
            ratio = target_sample_rate_hz / signal.sample_rate_hz
            new_samples = int(signal.samples_per_channel * ratio)
        else:
            new_samples = signal.samples_per_channel
        return SignalFrame(
            signal_id=f"{signal.signal_id}:interp",
            channel_count=signal.channel_count,
            sample_rate_hz=float(target_sample_rate_hz),
            samples_per_channel=new_samples,
        )
