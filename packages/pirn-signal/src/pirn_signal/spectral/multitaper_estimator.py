"""``MultitaperEstimator`` — Slepian-taper PSD with low spectral leakage.

Algorithm:
    1. Receive the input signal payload, time_bandwidth, and taper_count.
    2. Validate time_bandwidth (positive float) and taper_count (positive integer).
    3. Compute DPSS tapers via ``scipy.signal.windows.dpss``.
    4. Apply each taper to the signal, FFT each, average power across tapers.
    5. Return a SpectrumPayload with bins = samples // 2 + 1.

Math:
    Multitaper PSD:

    $$\\hat{S}_{\\text{MT}}(f) = \\frac{1}{K} \\sum_{k=0}^{K-1} \\lambda_k \\hat{S}_k(f)$$

References:
    - Thomson, D.J. (1982). "Spectrum estimation and harmonic analysis." Proc. IEEE, 70(9), 1055-1096.
    - scipy.signal.windows.dpss: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.dpss.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy.signal import windows

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


def _compute_multitaper(
    data: np.ndarray,
    n: int,
    time_bandwidth: float,
    taper_count: int,
) -> np.ndarray:
    tapers = windows.dpss(n, time_bandwidth, Kmax=taper_count)
    tapered = data[..., np.newaxis, :] * tapers
    spectra = np.fft.rfft(tapered, axis=-1)
    pxx = np.mean(np.abs(spectra) ** 2, axis=-2)
    return pxx


class MultitaperEstimator(Knot):
    """Multitaper PSD via discrete prolate spheroidal sequences (DPSS)."""

    def __init__(
        self,
        *,
        signal: Knot,
        time_bandwidth: Knot | float,
        taper_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            time_bandwidth=time_bandwidth,
            taper_count=taper_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        time_bandwidth: float,
        taper_count: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the PSD via Slepian-taper averaging and return a SpectrumPayload.

        Args:
            signal: Signal payload to estimate the multitaper power spectral density from.
            time_bandwidth: DPSS time-bandwidth product NW (positive float).
            taper_count: Number of DPSS tapers to average (positive integer).

        Returns:
            SpectrumPayload with PSD data and bins = samples // 2 + 1.

        Raises:
            ValueError: If time_bandwidth or taper_count are invalid.
        """
        if not isinstance(time_bandwidth, (int, float)) or time_bandwidth <= 0:
            raise ValueError("MultitaperEstimator: time_bandwidth must be positive")
        if not isinstance(taper_count, int) or taper_count <= 0:
            raise ValueError("MultitaperEstimator: taper_count must be a positive integer")

        sample_count = signal.data.shape[-1]
        pxx = await asyncio.to_thread(
            _compute_multitaper,
            signal.data,
            sample_count,
            float(time_bandwidth),
            taper_count,
        )

        freq_bins = sample_count // 2 + 1
        freq_res = (
            signal.frame.sample_rate_hz / sample_count
            if signal.frame.sample_rate_hz > 0 and sample_count > 0
            else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=pxx,
        )
