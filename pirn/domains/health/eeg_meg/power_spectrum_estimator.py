"""``PowerSpectrumEstimator`` — estimate the PSD of a signal frame.

Production version uses Welch / Multitaper via ``mne.time_frequency``
or ``scipy.signal.welch``. This stub returns a band-power mapping.

Algorithm:
    1. Receive a SignalFrame and method string.
    2. Validate that signal is a SignalFrame and method is one of welch/multitaper.
    3. Compute the power spectral density using the specified method.
    4. Integrate PSD over standard frequency bands (delta/theta/alpha/beta/gamma).
    5. Return the band-power mapping.

Math:
    $$P_{\\text{band}} = \\int_{f_{\\text{low}}}^{f_{\\text{high}}} S(f)\\, df$$

References:
    - Welch (1967) Use of Fast Fourier Transform for Estimation of Power Spectra.
    - MNE time-frequency: https://mne.tools/stable/auto_tutorials/time-freq/
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class PowerSpectrumEstimator(Knot):
    """Estimate per-band power for a signal frame."""

    def __init__(
        self,
        *,
        signal: Knot | SignalFrame,
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
        signal: SignalFrame,
        method: str,
        **_: Any,
    ) -> Mapping[str, float]:
        """Estimate per-band power of the signal using the configured method and return band-name-to-power mapping.

        Args:
            signal: The SignalFrame to analyze.
            method: PSD estimation method; one of 'welch', 'multitaper'.

        Returns:
            A mapping from frequency band name (delta/theta/alpha/beta/gamma) to estimated power.

        Raises:
            TypeError: If signal is not a SignalFrame.
            ValueError: If method is not one of welch/multitaper.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "PowerSpectrumEstimator: signal must be a SignalFrame"
            )
        if method not in ("welch", "multitaper"):
            raise ValueError(
                "PowerSpectrumEstimator: method must be one of welch/multitaper"
            )
        return {
            "delta": 0.0,
            "theta": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
        }
