"""``SeismicBandpassFilter`` — apply trapezoidal bandpass filter to seismic data.

Algorithm:
    1. Receive a seismic data dict and four frequency corners in Hz:
       ``low_cut_hz``, ``low_pass_hz``, ``high_pass_hz``, ``high_cut_hz``.
    2. Validate that all four values are positive and strictly ordered.
    3. Design an Ormsby (trapezoidal) bandpass filter in the frequency domain.
    4. Apply the filter to each trace.
    5. Return the filtered data dict.

Math:
    Ormsby trapezoidal filter shape in the frequency domain:

    $$H(f) = \\begin{cases}
      0 & f < f_{lc} \\\\
      \\frac{f - f_{lc}}{f_{lp} - f_{lc}} & f_{lc} \\le f < f_{lp} \\\\
      1 & f_{lp} \\le f \\le f_{hp} \\\\
      \\frac{f_{hc} - f}{f_{hc} - f_{hp}} & f_{hp} < f \\le f_{hc} \\\\
      0 & f > f_{hc}
    \\end{cases}$$

References:
    - Ormsby, J.F.A. (1961). Design of numerical filters with applications to
      missile data processing. *Journal of the ACM*, 8(3), 440-466.
    - Sheriff, R.E. & Geldart, L.P. (1995). *Exploration Seismology*, 2nd ed.
      Cambridge University Press, Chapter 9 (filtering).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SeismicBandpassFilter(Knot):
    """Apply a trapezoidal (Ormsby-style) bandpass filter to seismic trace data."""

    def __init__(
        self,
        *,
        data: Knot,
        low_cut_hz: Knot | float,
        low_pass_hz: Knot | float,
        high_pass_hz: Knot | float,
        high_cut_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            data=data,
            low_cut_hz=low_cut_hz,
            low_pass_hz=low_pass_hz,
            high_pass_hz=high_pass_hz,
            high_cut_hz=high_cut_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        data: dict[str, Any],
        low_cut_hz: float,
        low_pass_hz: float,
        high_pass_hz: float,
        high_cut_hz: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Apply the bandpass filter to each trace in the seismic dataset.

        Args:
            data: Dict with ``traces`` (list of dicts with ``samples``) and
                ``sample_interval_ms`` (float).
            low_cut_hz: Low-cut (high-pass roll-off start) frequency in Hz.
            low_pass_hz: Low-pass (high-pass roll-off end) frequency in Hz.
            high_pass_hz: High-pass (low-pass roll-off start) frequency in Hz.
            high_cut_hz: High-cut (low-pass roll-off end) frequency in Hz.

        Returns:
            Dict with same structure as input plus ``filtered: True``.
        """
        for label, value in (
            ("low_cut_hz", low_cut_hz),
            ("low_pass_hz", low_pass_hz),
            ("high_pass_hz", high_pass_hz),
            ("high_cut_hz", high_cut_hz),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"SeismicBandpassFilter: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"SeismicBandpassFilter: {label} must be positive")
        if not (low_cut_hz < low_pass_hz < high_pass_hz < high_cut_hz):
            raise ValueError(
                "SeismicBandpassFilter: frequencies must satisfy "
                "low_cut_hz < low_pass_hz < high_pass_hz < high_cut_hz"
            )
        if not isinstance(data, dict):
            raise TypeError("SeismicBandpassFilter: data must be a dict")
        sample_interval_ms: float = float(data.get("sample_interval_ms", 4.0))
        dt = sample_interval_ms * 1e-3

        def _ormsby(samples: list[float]) -> list[float]:
            arr = np.asarray(samples, dtype=np.float64)
            n = len(arr)
            if n == 0:
                return samples
            freqs = np.fft.rfftfreq(n, d=dt)
            spectrum = np.fft.rfft(arr)
            h = np.zeros_like(freqs)
            f_lc, f_lp, f_hp, f_hc = low_cut_hz, low_pass_hz, high_pass_hz, high_cut_hz
            for i, f in enumerate(freqs):
                fa = abs(f)
                if fa < f_lc or fa > f_hc:
                    h[i] = 0.0
                elif fa < f_lp:
                    h[i] = (fa - f_lc) / (f_lp - f_lc)
                elif fa <= f_hp:
                    h[i] = 1.0
                else:
                    h[i] = (f_hc - fa) / (f_hc - f_hp)
            filtered = np.fft.irfft(spectrum * h, n=n)
            return filtered.tolist()

        filtered_traces = [
            {**tr, "samples": _ormsby(tr.get("samples", []))} for tr in data.get("traces", [])
        ]
        return {**data, "traces": filtered_traces, "filtered": True}
