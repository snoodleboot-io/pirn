"""``ChirpletDecomposer`` — chirplet-transform decomposition."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class ChirpletDecomposer(Knot):
    """Chirplet-transform decomposition for non-stationary signals.

    Production needs a chirplet library or a custom matching-pursuit
    implementation on top of ``scipy``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        chirplet_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(chirplet_count, int) or chirplet_count <= 0:
            raise ValueError(
                "ChirpletDecomposer: chirplet_count must be a positive integer"
            )
        self._chirplet_count = chirplet_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def chirplet_count(self) -> int:
        return self._chirplet_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._chirplet_count,
            frequency_resolution_hz=0.0,
        )
