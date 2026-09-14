"""``Interpolator`` — generic interpolation knot.

Algorithm:
    1. Receive the input signal frame, target_sample_rate_hz, and kind.
    2. Validate target_sample_rate_hz (positive float) and kind (one of
       ``linear``, ``cubic``, ``quadratic``, ``spline``).
    3. Compute a continuous-time representation using the selected interpolation
       method (``scipy.interpolate.interp1d`` or equivalent).
    4. Evaluate the interpolant at the new sample times spaced at
       1 / target_sample_rate_hz.
    5. Return a SignalPayload at the target rate with the proportionally larger sample count.

Math:
    Resampled sample count:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\frac{f_{\\text{target}}}{f_{\\text{in}}} \\right\\rfloor$$

    Cubic spline evaluation at sample times $t_k = k / f_{\\text{target}}$.

References:
    - Stein, E.M. & Shakarchi, R. (2003). "Fourier Analysis: An Introduction." Princeton UP.
    - scipy.interpolate.interp1d: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.scipy_interpolate_binding import ScipyInterpolateBinding
from pirn_signal.types.signal_payload import SignalPayload


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
        signal: SignalPayload,
        target_sample_rate_hz: float,
        kind: str = "cubic",
        **_: Any,
    ) -> SignalPayload:
        """Interpolate the signal to the configured target sample rate.

        Args:
            signal: Signal to interpolate to a higher sample rate.
            target_sample_rate_hz: Target sample rate in Hz (positive float).
            kind: Interpolation method — ``linear``, ``cubic``, ``quadratic``, or ``spline``.

        Returns:
            SignalPayload at the configured target sample rate with an adjusted sample count.

        Raises:
            ValueError: If target_sample_rate_hz or kind are invalid.
        """
        if not isinstance(target_sample_rate_hz, (int, float)) or target_sample_rate_hz <= 0:
            raise ValueError("Interpolator: target_sample_rate_hz must be positive")
        if kind not in frozenset({"linear", "cubic", "quadratic", "spline"}):
            raise ValueError(
                "Interpolator: kind must be 'linear', 'cubic', 'quadratic', or 'spline'"
            )

        src_rate = signal.metadata.sample_rate_hz
        result = await asyncio.to_thread(
            Interpolator._interpolate, signal.data, src_rate, float(target_sample_rate_hz), kind
        )

        return signal.derive(
            "interp",
            result,
            sample_rate_hz=float(target_sample_rate_hz),
        )

    @staticmethod
    def _interpolate(
        data: NDArray[np.floating[Any]], src_rate: float, tgt_rate: float, kind: str
    ) -> NDArray[np.floating[Any]]:
        interpolate = ScipyInterpolateBinding.load()
        n_in = data.shape[-1]
        n_out = round(n_in * tgt_rate / src_rate)
        t_in: NDArray[np.float64] = np.arange(n_in, dtype=np.float64) / src_rate
        t_out: NDArray[np.float64] = np.arange(n_out, dtype=np.float64) / tgt_rate
        interp_kind = "cubic" if kind == "spline" else kind
        return interpolate.interp1d_extrapolate(t_in, data, t_out, kind=interp_kind, axis=-1)
