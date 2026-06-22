"""``IIRFilter`` — generic infinite impulse response filter.

Algorithm:
    1. Receive the input signal payload, numerator, and denominator.
    2. Validate that both are non-empty, denominator[0] is non-zero, and all
       values are real numbers.
    3. Convert b, a to SOS via scipy.signal.tf2sos, then apply sosfilt.
    4. Return a filtered SignalPayload.

Math:
    IIR difference equation:

    $$y(n) = \\frac{1}{a_0} \\left( \\sum_{k=0}^{M} b_k x(n-k) - \\sum_{k=1}^{N} a_k y(n-k) \\right)$$

    Transfer function:

    $$H(z) = \\frac{B(z)}{A(z)} = \\frac{\\sum_{k=0}^{M} b_k z^{-k}}{\\sum_{k=0}^{N} a_k z^{-k}}$$

References:
    - scipy.signal.lfilter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall. Chapter 6.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


class IIRFilter(Knot):
    """Apply a pre-designed IIR (b, a) coefficient set."""

    def __init__(
        self,
        *,
        signal: Knot,
        numerator: Knot | tuple,
        denominator: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            numerator=numerator,
            denominator=denominator,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        numerator: Sequence[float],
        denominator: Sequence[float],
        **_: Any,
    ) -> SignalPayload:
        """Apply the configured IIR (b, a) coefficients to the input signal.

        Args:
            signal: Signal payload to filter with the configured (b, a) transfer function.
            numerator: Non-empty sequence of numerator (b) coefficients.
            denominator: Non-empty sequence of denominator (a) coefficients;
                first element must be non-zero.

        Returns:
            SignalPayload of the IIR-filtered output.

        Raises:
            ValueError: If numerator or denominator are invalid.
            TypeError: If any coefficient is not a real number.
        """
        numerator_coeffs = tuple(numerator)
        denominator_coeffs = tuple(denominator)
        if not numerator_coeffs:
            raise ValueError("IIRFilter: numerator must be non-empty")
        if not denominator_coeffs:
            raise ValueError("IIRFilter: denominator must be non-empty")
        if denominator_coeffs[0] == 0:
            raise ValueError("IIRFilter: denominator[0] must be non-zero")
        for coefficient in (*numerator_coeffs, *denominator_coeffs):
            if not isinstance(coefficient, (int, float)):
                raise TypeError("IIRFilter: every coefficient must be a real number")

        b_arr = np.array(numerator_coeffs)
        a_arr = np.array(denominator_coeffs)
        sos = await asyncio.to_thread(ss.tf2sos, b_arr, a_arr)
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:iir",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
