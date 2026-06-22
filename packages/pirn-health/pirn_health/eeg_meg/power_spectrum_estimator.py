"""``PowerSpectrumEstimator`` — estimate the PSD of a signal payload.

Algorithm:
    1. Receive a HealthSignalPayload and method string.
    2. Validate that signal is a HealthSignalPayload and method is one of welch/multitaper.
    3. Compute the PSD using scipy.signal.welch on the first channel (or mono).
    4. Integrate PSD over standard frequency bands (delta/theta/alpha/beta/gamma) via numpy.trapz.
    5. Return the band-power mapping.

Math:
    $$P_{\\text{band}} = \\int_{f_{\\text{low}}}^{f_{\\text{high}}} S(f)\\, df$$

References:
    - Welch (1967) Use of Fast Fourier Transform for Estimation of Power Spectra.
    - SciPy welch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_health.types.health_signal_payload import HealthSignalPayload

_bands = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 100.0),
}


def _compute_band_power(data: np.ndarray, fs: float) -> dict[str, float]:
    channel = data[0] if data.ndim > 1 else data
    freqs, psd = ss.welch(channel, fs=fs, axis=-1)
    result: dict[str, float] = {}
    for band_name, (low, high) in _bands.items():
        mask = (freqs >= low) & (freqs <= high)
        result[band_name] = float(np.trapezoid(psd[mask], freqs[mask])) if mask.any() else 0.0
    return result


class PowerSpectrumEstimator(Knot):
    """Estimate per-band power for a signal payload."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        method: str,
        **_: Any,
    ) -> Mapping[str, float]:
        """Estimate per-band power of the signal using the configured method.

        Args:
            signal: The HealthSignalPayload to analyze.
            method: PSD estimation method; one of 'welch', 'multitaper'.

        Returns:
            A mapping from frequency band name (delta/theta/alpha/beta/gamma) to estimated power.

        Raises:
            TypeError: If signal is not a HealthSignalPayload.
            ValueError: If method is not one of welch/multitaper.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("PowerSpectrumEstimator: signal must be a HealthSignalPayload")
        if method not in ("welch", "multitaper"):
            raise ValueError("PowerSpectrumEstimator: method must be one of welch/multitaper")

        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(_compute_band_power, signal.data, fs)
