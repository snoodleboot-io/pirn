"""``CepstrumAnalyzer`` — real cepstrum (IFFT of log-magnitude FFT).

Algorithm:
    1. Receive the input signal payload and cepstrum_kind.
    2. Validate cepstrum_kind (one of ``real``, ``complex``, ``power``).
    3. Compute X = np.fft.rfft(signal.data, axis=-1).
    4. Compute log_X = np.log(np.abs(X) + 1e-10).
    5. Compute cepstrum = np.fft.irfft(log_X, axis=-1).
    6. Return a SpectrumPayload with frequency_bins = cepstrum.shape[-1].

Math:
    Real cepstrum:

    $$c_r(\\tau) = \\text{IFFT}\\{\\ln|X(f)|\\}$$

References:
    - Bogert, B.P., Healy, M.J.R. & Tukey, J.W. (1963). "The quefrency analysis of time series for
      echoes." Proc. Symp. Time Series Analysis, 15, 209-243.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


def _compute_cepstrum(data: np.ndarray) -> np.ndarray:
    spectrum = np.fft.rfft(data, axis=-1)
    log_spectrum = np.log(np.abs(spectrum) + 1e-10)
    return np.fft.irfft(log_spectrum, axis=-1)


class CepstrumAnalyzer(Knot):
    """Real cepstrum estimator via IFFT of log-magnitude spectrum."""

    _valid_kinds = frozenset({"real", "complex", "power"})

    def __init__(
        self,
        *,
        signal: Knot,
        cepstrum_kind: Knot | str = "real",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            cepstrum_kind=cepstrum_kind,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        cepstrum_kind: str = "real",
        **_: Any,
    ) -> SpectrumPayload:
        """Compute the cepstrum from the signal and return a SpectrumPayload.

        Args:
            signal: Signal payload to compute the cepstrum from.
            cepstrum_kind: One of ``real``, ``complex``, or ``power``.

        Returns:
            SpectrumPayload with cepstral data and frequency_bins = cepstrum.shape[-1].

        Raises:
            ValueError: If cepstrum_kind is not valid.
        """
        if cepstrum_kind not in self._valid_kinds:
            raise ValueError(
                "CepstrumAnalyzer: cepstrum_kind must be 'real', 'complex', or 'power'"
            )

        cepstrum = await asyncio.to_thread(_compute_cepstrum, signal.data)
        freq_bins = cepstrum.shape[-1]

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=0.0,
            ),
            data=cepstrum,
        )
