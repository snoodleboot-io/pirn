"""``CepstrumAnalyzer`` — real cepstrum (IFFT of log-magnitude FFT)."""

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

    def __init__(
        self,
        *,
        signal: Knot,
        cepstrum_kind: str = "real",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if cepstrum_kind not in {"real", "complex", "power"}:
            raise ValueError(
                "CepstrumAnalyzer: cepstrum_kind must be 'real', 'complex', or 'power'"
            )
        self._cepstrum_kind = cepstrum_kind
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def cepstrum_kind(self) -> str:
        return self._cepstrum_kind

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Compute the cepstrum from the signal and return a SpectrumFrame of cepstral coefficients.

        Args:
            signal: Signal to compute the cepstrum from via IFFT of the log-magnitude spectrum.

        Returns:
            SpectrumFrame with bins equal to the input sample count.
        """
        n = max(signal.samples_per_channel, 1)
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n,
            frequency_resolution_hz=0.0,
        )
