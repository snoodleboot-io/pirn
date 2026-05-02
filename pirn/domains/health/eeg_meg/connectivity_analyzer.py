"""``ConnectivityAnalyzer`` — pairwise channel connectivity.

Production version uses ``mne_connectivity`` (PLV, coherence, wPLI).
This stub returns a zero-filled symmetric matrix as a nested mapping.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class ConnectivityAnalyzer(Knot):
    """Compute pairwise connectivity between channels."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        channel_names: Sequence[str],
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "ConnectivityAnalyzer: signal must be a SignalFrame"
            )
        if not isinstance(channel_names, (list, tuple)):
            raise TypeError(
                "ConnectivityAnalyzer: channel_names must be list/tuple"
            )
        for name in channel_names:
            if not isinstance(name, str):
                raise TypeError(
                    "ConnectivityAnalyzer: every channel name must be string"
                )
        if method not in ("plv", "coherence", "wpli"):
            raise ValueError(
                "ConnectivityAnalyzer: method must be one of plv/coherence/wpli"
            )
        self._signal = signal
        self._channel_names = tuple(channel_names)
        self._method = method
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Mapping[str, float]]:
        return {
            ch: {other: 0.0 for other in self._channel_names}
            for ch in self._channel_names
        }
