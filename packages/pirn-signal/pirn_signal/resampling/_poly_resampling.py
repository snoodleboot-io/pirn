"""``PolyResampling`` — shared polyphase resampling helper (private, not a Knot).

Factors out the ``scipy.signal.resample_poly`` call and the rate-to-factor
conversion shared by the resampling knots (:class:`ArbitraryResamplerPipeline`,
:class:`ClockDriftCorrector`, :class:`MultiRateFusionPipeline`,
:class:`PolyphaseResampler`, and :class:`RationalResamplerPipeline`). Each knot calls
it from its own ``process()`` via ``asyncio.to_thread``.

Algorithm:
    Resampling from one sample rate to another:

    1. Read each rate as the exact rational number its shortest decimal
       representation denotes (``1000.4`` is ``5002/5``), so the ratio is exact
       rather than truncated to integers.
    2. Form the ratio ``target / source = up / down`` in lowest terms.
    3. When both factors are at most ``_max_factor``, run polyphase resampling with
       exactly those factors (its anti-aliasing filter has ``20 max(up, down) + 1``
       taps, which the bound keeps tractable).
    4. Otherwise — a ratio such as a parts-per-million clock drift — resample at the
       exact ratio by bandlimited interpolation (:class:`BandlimitedInterpolation`)
       instead of approximating the ratio.

Math:
    $$\\frac{L}{M} = \\frac{f_{\\text{target}}}{f_{\\text{source}}}, \\qquad
      N_{\\text{out}} = \\left\\lceil N_{\\text{in}} \\frac{L}{M} \\right\\rceil$$

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing."
      Prentice-Hall.
    - scipy.signal.resample_poly:
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from pirn_signal.bindings.scipy_signal_binding import ScipySignalBinding
from pirn_signal.resampling._bandlimited_interpolation import BandlimitedInterpolation


class PolyResampling:
    """Polyphase resampling shared by ``pirn_signal.resampling`` knots."""

    _max_factor: ClassVar[int] = 10_000

    @staticmethod
    def resample_poly(
        data: NDArray[np.floating[Any]], up: int, down: int
    ) -> NDArray[np.floating[Any]]:
        ss = ScipySignalBinding.load()
        return ss.resample_poly(data, up, down, axis=-1)

    @staticmethod
    def rational_factors(source_rate_hz: float, target_rate_hz: float) -> tuple[int, int]:
        """Return the exact ``(up, down)`` in lowest terms with ``up / down = target / source``."""
        ratio = Fraction(repr(float(target_rate_hz))) / Fraction(repr(float(source_rate_hz)))
        return ratio.numerator, ratio.denominator

    @staticmethod
    def resample_rate(
        data: NDArray[np.floating[Any]], source_rate_hz: float, target_rate_hz: float
    ) -> NDArray[np.floating[Any]]:
        """Resample ``data`` along its last axis from ``source_rate_hz`` to ``target_rate_hz``.

        Polyphase at the exact rational ratio when both factors are at most
        ``_max_factor``; otherwise bandlimited interpolation at the exact ratio.
        """
        up, down = PolyResampling.rational_factors(source_rate_hz, target_rate_hz)
        if max(up, down) <= PolyResampling._max_factor:
            return PolyResampling.resample_poly(data, up, down)
        return BandlimitedInterpolation.resample(data, source_rate_hz, target_rate_hz)
