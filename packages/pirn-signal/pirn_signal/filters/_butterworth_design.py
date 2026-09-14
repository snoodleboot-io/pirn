"""``ButterworthDesign`` — shared Butterworth IIR design/apply helper (private, not a Knot).

Factors out the ``scipy.signal.butter`` + ``sosfilt`` design-and-apply logic
duplicated across :class:`ButterworthFilter`, :class:`LowPassFilter`,
:class:`HighPassFilter`, :class:`BandPassFilter`, :class:`BandStopFilter`, and
:class:`CausalRealtimeFilter`. Each knot calls
:meth:`ButterworthDesign.design_and_apply` from its own ``process()`` via
``asyncio.to_thread``.

References:
    [1] Butterworth, S. (1930). "On the theory of filter amplifiers."
        Wireless Engineer, 7, 536-541.
    [2] scipy.signal.butter:
        https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from pirn_signal.bindings.scipy_signal_binding import ScipySignalBinding


class ButterworthDesign:
    """Butterworth IIR design + causal application shared by ``pirn_signal.filters`` knots."""

    @staticmethod
    def design_and_apply(
        data: NDArray[np.floating[Any]],
        order: int,
        cutoff_hz: float | tuple[float, float],
        band_type: str,
        fs: float,
    ) -> NDArray[np.floating[Any]]:
        """Design a Butterworth SOS filter and apply it causally via ``sosfilt``.

        Args:
            data: Sample array to filter, shaped ``(..., samples)``.
            order: Filter order (positive integer).
            cutoff_hz: Cutoff frequency in Hz; scalar for lowpass/highpass,
                ``(low, high)`` tuple for bandpass/bandstop.
            band_type: One of ``lowpass``, ``highpass``, ``bandpass``, ``bandstop``.
            fs: Sample rate in Hz.

        Returns:
            The filtered sample array, same shape as ``data``.
        """
        ss = ScipySignalBinding.load()
        btype_map: dict[str, str] = {
            "lowpass": "low",
            "highpass": "high",
            "bandpass": "bandpass",
            "bandstop": "bandstop",
        }
        sos = ss.butter_sos(order, cutoff_hz, btype_map[band_type], fs)
        return ss.sosfilt(sos, data, axis=-1)
