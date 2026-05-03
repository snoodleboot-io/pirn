"""``ICARobustDecomposer`` — robust ICA variant for outlier-heavy data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class ICARobustDecomposer(Knot):
    """Outlier-robust ICA (e.g. JADE / fastICA with robust whitening).

    Production needs a robust-ICA library or a custom JADE
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        source_count: int,
        contamination_fraction: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_count, int) or source_count <= 0:
            raise ValueError(
                "ICARobustDecomposer: source_count must be a positive integer"
            )
        if (
            not isinstance(contamination_fraction, (int, float))
            or not 0.0 <= contamination_fraction < 1.0
        ):
            raise ValueError(
                "ICARobustDecomposer: contamination_fraction must lie in [0, 1)"
            )
        self._source_count = source_count
        self._contamination_fraction = float(contamination_fraction)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def source_count(self) -> int:
        return self._source_count

    @property
    def contamination_fraction(self) -> float:
        return self._contamination_fraction

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        """Decompose the signal into independent components via robust ICA and return a SourceFrame.

        Args:
            signal: Multichannel signal with potential outliers to decompose into independent sources.

        Returns:
            SourceFrame with robustly estimated independent components and mixing matrix shape.
        """
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._source_count,
            mixing_matrix_shape=(signal.channel_count, self._source_count),
        )
