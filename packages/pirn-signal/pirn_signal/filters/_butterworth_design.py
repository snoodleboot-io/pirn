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

import numpy as np


class ButterworthDesign:
    """Butterworth IIR design + causal application shared by ``pirn_signal.filters`` knots."""

    @staticmethod
    def design_and_apply(
        data: np.ndarray,
        order: int,
        cutoff_hz: float | tuple[float, float],
        band_type: str,
        fs: float,
    ) -> np.ndarray:
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
        try:
            from scipy import signal as ss  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "ButterworthDesign requires 'scipy'. Install via pip install pirn-signal[signal]"
            ) from exc
        btype_map = {
            "lowpass": "low",
            "highpass": "high",
            "bandpass": "bandpass",
            "bandstop": "bandstop",
        }
        sos = ss.butter(order, cutoff_hz, btype=btype_map[band_type], fs=fs, output="sos")
        return np.asarray(ss.sosfilt(sos, data, axis=-1))
