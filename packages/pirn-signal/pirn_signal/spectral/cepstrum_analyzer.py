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
            cepstrum_kind: ``real`` (inverse transform of the log magnitude),
                ``power`` (of the log power spectrum) or ``complex`` (of the complex
                logarithm, magnitude and unwrapped phase).

        Returns:
            SpectrumPayload with cepstral data and frequency_bins = cepstrum.shape[-1].

        Raises:
            ValueError: If cepstrum_kind is not valid.
        """
        if cepstrum_kind not in self._valid_kinds:
            raise ValueError(
                "CepstrumAnalyzer: cepstrum_kind must be 'real', 'complex', or 'power'"
            )

        cepstrum = await asyncio.to_thread(
            CepstrumAnalyzer._compute_cepstrum, signal.data, cepstrum_kind
        )
        freq_bins = cepstrum.shape[-1]

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.metadata.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=0.0,
            ),
            data=cepstrum,
        )

    @staticmethod
    def _compute_cepstrum(data: np.ndarray, cepstrum_kind: str) -> np.ndarray:
        """Compute the requested cepstrum along the last axis.

        * ``real`` — inverse transform of the log magnitude spectrum,
          :math:`c_r = \\mathcal{F}^{-1}\\{\\log|X|\\}` (Bogert 1963).
        * ``power`` — inverse transform of the log power spectrum,
          :math:`c_p = \\mathcal{F}^{-1}\\{\\log|X|^2\\}` (Childers 1977): the
          cepstrum of the power spectrum, twice the real cepstrum for a real signal
          but the quantity the power-cepstrum literature quotes.
        * ``complex`` — inverse transform of the complex logarithm, log magnitude plus
          the unwrapped phase, :math:`c_c = \\mathcal{F}^{-1}\\{\\log|X| + j\\arg X\\}`
          (Oppenheim & Schafer 1975, ch. 10). Unlike the real cepstrum it is
          invertible, so it separates a non-minimum-phase excitation from its filter.

        Args:
            data: Samples, ``(..., n)``.
            cepstrum_kind: ``real``, ``power`` or ``complex``.

        Returns:
            The cepstrum, real-valued, shaped like ``data`` along the last axis.
        """
        if cepstrum_kind == "complex":
            spectrum = np.fft.fft(data, axis=-1)
            log_spectrum = np.log(np.abs(spectrum) + 1e-10) + 1j * np.unwrap(
                np.angle(spectrum), axis=-1
            )
            return np.real(np.fft.ifft(log_spectrum, axis=-1))
        spectrum = np.fft.rfft(data, axis=-1)
        magnitude = np.abs(spectrum) + 1e-10
        log_spectrum = 2.0 * np.log(magnitude) if cepstrum_kind == "power" else np.log(magnitude)
        return np.fft.irfft(log_spectrum, axis=-1)
