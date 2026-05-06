"""``MultitaperEstimator`` — Slepian-taper PSD with low spectral leakage.

Algorithm:
    1. Receive the input signal frame, time_bandwidth, and taper_count.
    2. Validate time_bandwidth (positive float) and taper_count (positive integer).
    3. Compute taper_count DPSS tapers from ``scipy.signal.windows.dpss`` with
       the given time-bandwidth product NW.
    4. Multiply the signal by each taper and compute the periodogram.
    5. Average the taper periodograms (possibly with adaptive weighting).
    6. Return a SpectrumFrame with bins equal to half the sample count plus one.

Math:
    DPSS concentration:

    $$\\lambda_k = \\int_{-W}^{W} |U_k(f)|^2 df \\to 1 \\quad \\text{as} \\quad NW \\to \\infty$$

    Multitaper PSD:

    $$\\hat{S}_{\\text{MT}}(f) = \\frac{1}{K} \\sum_{k=0}^{K-1} \\lambda_k \\hat{S}_k(f)$$

References:
    - Thomson, D.J. (1982). "Spectrum estimation and harmonic analysis." Proc. IEEE, 70(9), 1055-1096.
    - scipy.signal.windows.dpss: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.dpss.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class MultitaperEstimator(Knot):
    """Multitaper PSD via discrete prolate spheroidal sequences (DPSS).

    Production needs ``scipy.signal.windows.dpss`` plus a multitaper
    averaging routine.
    """

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
        signal: SignalFrame,
        time_bandwidth: float,
        taper_count: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the PSD via Slepian-taper averaging and return a SpectrumFrame.

        Args:
            signal: Signal to estimate the multitaper power spectral density from.
            time_bandwidth: DPSS time-bandwidth product NW (positive float).
            taper_count: Number of DPSS tapers to average (positive integer).

        Returns:
            SpectrumFrame with bins equal to half the sample count plus one.

        Raises:
            ValueError: If time_bandwidth or taper_count are invalid.
        """
        if not isinstance(time_bandwidth, (int, float)) or time_bandwidth <= 0:
            raise ValueError(
                "MultitaperEstimator: time_bandwidth must be positive"
            )
        if not isinstance(taper_count, int) or taper_count <= 0:
            raise ValueError(
                "MultitaperEstimator: taper_count must be a positive integer"
            )
        n = max(signal.samples_per_channel, 1)
        resolution = (
            signal.sample_rate_hz / n
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n // 2 + 1,
            frequency_resolution_hz=resolution,
        )
