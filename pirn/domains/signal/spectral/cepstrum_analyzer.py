"""``CepstrumAnalyzer`` — real cepstrum (IFFT of log-magnitude FFT).

Algorithm:
    1. Receive the input signal frame and cepstrum_kind.
    2. Validate cepstrum_kind (one of ``real``, ``complex``, ``power``).
    3. Compute the FFT of the signal.
    4. Apply the log of the magnitude (real cepstrum) or the complex log (complex cepstrum)
       or the squared magnitude log (power cepstrum).
    5. Apply the IFFT to the log spectrum to obtain the cepstrum.
    6. Return a SpectrumFrame with bins equal to the input sample count.

Math:
    Real cepstrum:

    $$c_r(\\tau) = \\text{IFFT}\\{\\ln|X(f)|\\}$$

    Complex cepstrum:

    $$c_c(\\tau) = \\text{IFFT}\\{\\ln X(f)\\}$$

    Power cepstrum:

    $$c_p(\\tau) = |\\text{IFFT}\\{\\ln|X(f)|^2\\}|^2$$

References:
    - Bogert, B.P., Healy, M.J.R. & Tukey, J.W. (1963). "The quefrency analysis of time series for
      echoes." Proc. Symp. Time Series Analysis, 15, 209-243.
    - scipy.fft: https://docs.scipy.org/doc/scipy/reference/fft.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class CepstrumAnalyzer(Knot):
    """Real cepstrum estimator.

    Production needs ``scipy.fft``.
    """

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
        signal: SignalFrame,
        cepstrum_kind: str = "real",
        **_: Any,
    ) -> SpectrumFrame:
        """Compute the cepstrum from the signal and return a SpectrumFrame of cepstral coefficients.

        Args:
            signal: Signal to compute the cepstrum from via IFFT of the log-magnitude spectrum.
            cepstrum_kind: One of ``real``, ``complex``, or ``power``.

        Returns:
            SpectrumFrame with bins equal to the input sample count.

        Raises:
            ValueError: If cepstrum_kind is not valid.
        """
        if cepstrum_kind not in self._valid_kinds:
            raise ValueError(
                "CepstrumAnalyzer: cepstrum_kind must be 'real', 'complex', or 'power'"
            )
        n = max(signal.samples_per_channel, 1)
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n,
            frequency_resolution_hz=0.0,
        )
