"""``ConnectivityAnalyzer`` — pairwise channel connectivity.

Production version uses ``mne_connectivity`` (PLV, coherence, wPLI).
This stub returns a zero-filled symmetric matrix as a nested mapping.

Algorithm:
    1. Receive a SignalFrame, channel_names sequence, and method string.
    2. Validate types and that method is one of plv/coherence/wpli.
    3. Compute pairwise connectivity between all channel pairs using the method.
    4. Return a symmetric nested mapping of channel-to-channel scores.


References:
    - mne-connectivity: https://mne.tools/mne-connectivity/stable/
    - Bastos & Schoffelen (2016) A Tutorial Review of Functional Connectivity Analysis Methods.
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
        signal: Knot | SignalFrame,
        channel_names: Knot | Sequence[str],
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            channel_names=channel_names,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        channel_names: Sequence[str],
        method: str,
        **_: Any,
    ) -> Mapping[str, Mapping[str, float]]:
        """Compute pairwise connectivity between all channel pairs using the configured method.

        Args:
            signal: The SignalFrame to analyze.
            channel_names: Sequence of channel name strings.
            method: Connectivity method; one of 'plv', 'coherence', 'wpli'.

        Returns:
            A nested mapping from channel name to a mapping of other channel names to connectivity scores.

        Raises:
            TypeError: If signal is not SignalFrame or channel_names is not list/tuple of strings.
            ValueError: If method is not one of plv/coherence/wpli.
        """
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
        return {
            ch: {other: 0.0 for other in channel_names}
            for ch in channel_names
        }
