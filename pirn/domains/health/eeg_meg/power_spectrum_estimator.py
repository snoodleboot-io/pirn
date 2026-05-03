"""``PowerSpectrumEstimator`` — estimate the PSD of a signal frame.

Production version uses Welch / Multitaper via ``mne.time_frequency``
or ``scipy.signal.welch``. This stub returns a band-power mapping.
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
        signal: SignalFrame,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "PowerSpectrumEstimator: signal must be a SignalFrame"
            )
        if method not in ("welch", "multitaper"):
            raise ValueError(
                "PowerSpectrumEstimator: method must be one of welch/multitaper"
            )
        self._signal = signal
        self._method = method
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        """Estimate per-band power of the signal using the configured method and return band-name-to-power mapping.

        Returns:
            A mapping from frequency band name (delta/theta/alpha/beta/gamma) to estimated power.
        """
        return {
            "delta": 0.0,
            "theta": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
        }
