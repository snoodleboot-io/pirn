"""``ArtifactRemover`` — ICA-based artifact removal.

Production version uses ``mne.preprocessing.ICA`` or AutoReject.
This stub validates inputs and returns the signal unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class ArtifactRemover(Knot):
    """Remove EOG/ECG/muscle artifacts from a signal frame."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        n_components: int,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("ArtifactRemover: signal must be a SignalFrame")
        if not isinstance(n_components, int):
            raise TypeError("ArtifactRemover: n_components must be int")
        if n_components <= 0:
            raise ValueError(
                "ArtifactRemover: n_components must be positive"
            )
        if method not in ("infomax", "fastica", "picard"):
            raise ValueError(
                "ArtifactRemover: method must be one of infomax/fastica/picard"
            )
        self._signal = signal
        self._n_components = n_components
        self._method = method
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SignalFrame:
        return self._signal
